import contextlib
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from ..core.exceptions import AppException, ErrorCode
from ..db.client import get_db
from ..db.models import Developer, Project, Session, Team, ToolEvent, Turn
from ..schemas.ingest import (
    PromptEvent,
    SessionEndEvent,
    SessionStartEvent,
)
from ..schemas.ingest import ToolEvent as ToolEventSchema
from ..schemas.response import APIResponse, ResponseMeta

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _upsert_developer(
    developer_id: str, name: str | None, email: str | None, db: DBSession
) -> None:
    stmt = (
        pg_insert(Developer)
        .values(
            developer_id=developer_id,
            name=name,
            email=email,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            index_elements=["developer_id"],
            set_=dict(
                name=pg_insert(Developer).excluded.name,
                email=pg_insert(Developer).excluded.email,
                updated_at=datetime.now(UTC),
            ),
        )
    )
    db.execute(stmt)


def _upsert_team(team_id: str, db: DBSession) -> None:
    stmt = (
        pg_insert(Team)
        .values(team_id=team_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
        .on_conflict_do_nothing(index_elements=["team_id"])
    )
    db.execute(stmt)


def _upsert_project(
    team_id: str, project_name: str | None, project_url: str | None, db: DBSession
) -> int | None:
    if not project_name:
        return None
    stmt = (
        pg_insert(Project)
        .values(
            team_id=team_id,
            project_name=project_name,
            project_url=project_url,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        .on_conflict_do_update(
            constraint="uq_projects_team_name",
            set_=dict(
                project_url=pg_insert(Project).excluded.project_url,
                updated_at=datetime.now(UTC),
            ),
        )
        .returning(Project.id)
    )
    result = db.execute(stmt)
    row = result.fetchone()
    return row[0] if row else None


def _ensure_session(
    session_id: str,
    developer_id: str,
    team_id: str,
    db: DBSession,
    name: str | None = None,
    email: str | None = None,
    project_name: str | None = None,
    project_url: str | None = None,
) -> None:
    """Upsert developer/team/project, then auto-create placeholder session if missing."""
    _upsert_developer(developer_id, name, email, db)
    _upsert_team(team_id, db)
    project_id = _upsert_project(team_id, project_name, project_url, db)

    if not db.query(Session).filter_by(session_id=session_id).first():
        db.add(
            Session(
                session_id=session_id,
                developer_id=developer_id,
                team_id=team_id,
                project_id=project_id,
                started_at=datetime.now(UTC),
            )
        )
        db.flush()


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
def ingest_event(
    payload: PromptEvent | ToolEventSchema,
    db: DBSession = Depends(get_db),
) -> APIResponse[dict]:
    meta = ResponseMeta()

    if isinstance(payload, PromptEvent):
        duplicate = (
            db.query(Turn)
            .filter(Turn.session_id == payload.session_id, Turn.turn_index == payload.turn_index)
            .first()
        )
        if duplicate:
            return APIResponse(
                data={"type": "prompt", "scoring_queued": False, "duplicate": True}, meta=meta
            )

        try:
            _ensure_session(
                payload.session_id,
                payload.developer_id,
                payload.team_id,
                db,
                name=payload.developer_name,
                email=payload.developer_email,
                project_name=payload.project_name,
                project_url=payload.project_url,
            )
            row = Turn(
                session_id=payload.session_id,
                turn_index=payload.turn_index,
                prompt_hash=payload.prompt_hash,
                prompt_chars=payload.prompt_chars,
                prompt_text=payload.prompt_text,
                quality_score=payload.quality_score,
                flags=payload.flags,
                created_at=payload.timestamp,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        except IntegrityError:
            db.rollback()
            return APIResponse(
                data={"type": "prompt", "scoring_queued": False, "duplicate": True}, meta=meta
            )
        except Exception:
            db.rollback()
            raise

        scoring_queued = False
        try:
            from ..jobs.celery_app import score_turn

            score_turn.delay(row.id)
            scoring_queued = True
        except Exception:
            pass

        return APIResponse(
            data={"type": "prompt", "scoring_queued": scoring_queued, "duplicate": False}, meta=meta
        )

    if isinstance(payload, ToolEventSchema):
        try:
            _ensure_session(payload.session_id, payload.developer_id, payload.team_id, db)
            db.add(
                ToolEvent(
                    session_id=payload.session_id,
                    turn_index=payload.turn_index,
                    tool_name=payload.tool_name,
                    allowed=payload.allowed,
                    accept_streak=payload.accept_streak,
                    sensitive_path=payload.sensitive_path,
                    file_path_hash=payload.file_path_hash,
                    file_path=payload.file_path,
                    created_at=payload.timestamp,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        return APIResponse(
            data={"type": "tool", "scoring_queued": False, "duplicate": False}, meta=meta
        )

    raise AppException(ErrorCode.VALIDATION_ERROR, "Unknown event type")


@router.post("/sessions", status_code=status.HTTP_202_ACCEPTED)
def ingest_session(
    payload: SessionStartEvent | SessionEndEvent,
    db: DBSession = Depends(get_db),
) -> APIResponse[dict]:
    meta = ResponseMeta()

    if isinstance(payload, SessionStartEvent):
        try:
            _upsert_developer(
                payload.developer_id, payload.developer_name, payload.developer_email, db
            )
            _upsert_team(payload.team_id, db)
            project_id = _upsert_project(
                payload.team_id, payload.project_name, payload.project_url, db
            )

            existing = db.query(Session).filter_by(session_id=payload.session_id).first()
            if existing:
                existing.developer_id = payload.developer_id
                existing.team_id = payload.team_id
                existing.project_id = project_id
                existing.started_at = payload.started_at
                existing.cwd_hash = payload.cwd_hash
                existing.cwd = payload.cwd
                db.commit()
                return APIResponse(data={"event": "session_start", "backfilled": True}, meta=meta)

            db.add(
                Session(
                    session_id=payload.session_id,
                    developer_id=payload.developer_id,
                    team_id=payload.team_id,
                    project_id=project_id,
                    started_at=payload.started_at,
                    cwd_hash=payload.cwd_hash,
                    cwd=payload.cwd,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        from ..services.langfuse_service import send_session_event

        project = (
            db.query(Project)
            .filter_by(
                id=db.query(Session.project_id).filter_by(session_id=payload.session_id).scalar()
            )
            .first()
        )
        send_session_event(
            session_id=payload.session_id,
            event="start",
            developer_id=payload.developer_id,
            team_id=payload.team_id,
            project_name=project.project_name if project else None,
        )
        return APIResponse(data={"event": "session_start", "backfilled": False}, meta=meta)

    if isinstance(payload, SessionEndEvent):
        try:
            session = db.query(Session).filter_by(session_id=payload.session_id).first()
            if session:
                session.ended_at = payload.ended_at
                session.turn_count = payload.turns
                db.commit()
        except Exception:
            db.rollback()
            raise

        from ..jobs.celery_app import score_session
        from ..services.langfuse_service import send_session_event

        send_session_event(
            session_id=payload.session_id,
            event="end",
            developer_id=payload.developer_id,
            team_id=payload.team_id,
        )
        with contextlib.suppress(Exception):
            score_session.delay(payload.session_id)
        return APIResponse(data={"event": "session_end", "backfilled": False}, meta=meta)

    raise AppException(ErrorCode.VALIDATION_ERROR, "Unknown session event type")

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from ..core.exceptions import AppException, ErrorCode
from ..db.client import get_db
from ..db.models import Session, ToolEvent, Turn
from ..schemas.ingest import (
    PromptEvent,
    SessionEndEvent,
    SessionStartEvent,
)
from ..schemas.ingest import (
    ToolEvent as ToolEventSchema,
)
from ..schemas.response import APIResponse, ResponseMeta

log = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _ensure_session(
    session_id: str,
    developer_id: str,
    team_id: str,
    db: DBSession,
    developer_name: str | None = None,
) -> None:
    """Auto-create placeholder session if events arrive before session_start."""
    if not db.query(Session).filter_by(session_id=session_id).first():
        db.add(
            Session(
                session_id=session_id,
                developer_id=developer_id,
                developer_name=developer_name,
                team_id=team_id,
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
                data={"type": "prompt", "scoring_queued": False, "duplicate": True},
                meta=meta,
            )

        try:
            _ensure_session(payload.session_id, payload.developer_id, payload.team_id, db)
            # Backfill session fields that _ensure_session couldn't populate
            session_row = db.query(Session).filter_by(session_id=payload.session_id).first()
            if session_row:
                changed = False
                for attr, val in [
                    ("developer_name", payload.developer_name),
                    ("developer_email", payload.developer_email),
                    ("project_url", payload.project_url),
                    ("project_name", payload.project_name),
                ]:
                    if val and not getattr(session_row, attr):
                        setattr(session_row, attr, val)
                        changed = True
                if changed:
                    db.flush()
            row = Turn(
                session_id=payload.session_id,
                developer_id=payload.developer_id,
                team_id=payload.team_id,
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
                data={"type": "prompt", "scoring_queued": False, "duplicate": True},
                meta=meta,
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
            data={"type": "prompt", "scoring_queued": scoring_queued, "duplicate": False},
            meta=meta,
        )

    if isinstance(payload, ToolEventSchema):
        try:
            _ensure_session(payload.session_id, payload.developer_id, payload.team_id, db)
            db.add(
                ToolEvent(
                    session_id=payload.session_id,
                    developer_id=payload.developer_id,
                    team_id=payload.team_id,
                    turn_index=payload.turn_index,
                    tool_name=payload.tool_name,
                    allowed=payload.allowed,
                    accept_streak=payload.accept_streak,
                    total_accepts=payload.total_accepts,
                    total_rejects=payload.total_rejects,
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
            existing = db.query(Session).filter_by(session_id=payload.session_id).first()
            if existing:
                existing.developer_id = payload.developer_id
                existing.developer_name = payload.developer_name
                existing.developer_email = payload.developer_email
                existing.team_id = payload.team_id
                existing.project_url = payload.project_url
                existing.project_name = payload.project_name
                existing.started_at = payload.started_at
                existing.cwd_hash = payload.cwd_hash
                existing.cwd = payload.cwd
                db.commit()
                return APIResponse(data={"event": "session_start", "backfilled": True}, meta=meta)
            db.add(
                Session(
                    session_id=payload.session_id,
                    developer_id=payload.developer_id,
                    developer_name=payload.developer_name,
                    developer_email=payload.developer_email,
                    team_id=payload.team_id,
                    project_url=payload.project_url,
                    project_name=payload.project_name,
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

        send_session_event(
            session_id=payload.session_id,
            event="start",
            developer_id=payload.developer_id,
            team_id=payload.team_id,
            project_name=payload.project_name,
        )
        return APIResponse(data={"event": "session_start", "backfilled": False}, meta=meta)

    if isinstance(payload, SessionEndEvent):
        try:
            session = db.query(Session).filter_by(session_id=payload.session_id).first()
            if session:
                session.ended_at = payload.ended_at
                session.turns = payload.turns
                db.commit()
        except Exception:
            db.rollback()
            raise
        from ..services.langfuse_service import send_session_event

        send_session_event(
            session_id=payload.session_id,
            event="end",
            developer_id=payload.developer_id,
            team_id=payload.team_id,
        )
        return APIResponse(data={"event": "session_end", "backfilled": False}, meta=meta)

    raise AppException(ErrorCode.VALIDATION_ERROR, "Unknown session event type")

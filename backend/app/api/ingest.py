from datetime import datetime, timezone
from typing import Annotated, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from ..db.client import get_db
from ..db.models import Session, Turn, ToolEvent
from ..schemas.ingest import PromptEvent, ToolEvent as ToolEventSchema, SessionStartEvent, SessionEndEvent

router = APIRouter(prefix="/ingest", tags=["ingest"])

IngestEvent = Annotated[Union[PromptEvent, ToolEventSchema], ...]


def _ensure_session(session_id: str, developer_id: str, team_id: str, db: DBSession) -> None:
    """Auto-create placeholder session if events arrive before session_start."""
    existing = db.query(Session).filter_by(session_id=session_id).first()
    if not existing:
        db.add(Session(
            session_id=session_id,
            developer_id=developer_id,
            team_id=team_id,
            started_at=datetime.now(timezone.utc),
        ))
        db.flush()


@router.post("/events", status_code=status.HTTP_202_ACCEPTED)
def ingest_event(
    payload: Union[PromptEvent, ToolEventSchema],
    db: DBSession = Depends(get_db),
):
    if isinstance(payload, PromptEvent):
        _ensure_session(payload.session_id, payload.developer_id, payload.team_id, db)
        row = Turn(
            session_id=payload.session_id,
            developer_id=payload.developer_id,
            team_id=payload.team_id,
            turn_index=payload.turn_index,
            prompt_hash=payload.prompt_hash,
            prompt_chars=payload.prompt_chars,
            quality_score=payload.quality_score,
            flags=payload.flags,
            created_at=payload.timestamp,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        try:
            from ..jobs.celery_app import score_turn
            score_turn.delay(row.id)
        except Exception:
            pass  # Celery unavailable — hook pre-score stands
        return {"accepted": True, "type": "prompt"}

    if isinstance(payload, ToolEventSchema):
        _ensure_session(payload.session_id, payload.developer_id, payload.team_id, db)
        row = ToolEvent(
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
            created_at=payload.timestamp,
        )
        db.add(row)
        db.commit()
        return {"accepted": True, "type": "tool"}

    raise HTTPException(status_code=400, detail="Unknown event type")


@router.post("/sessions", status_code=status.HTTP_202_ACCEPTED)
def ingest_session(
    payload: Union[SessionStartEvent, SessionEndEvent],
    db: DBSession = Depends(get_db),
):
    if isinstance(payload, SessionStartEvent):
        existing = db.query(Session).filter_by(session_id=payload.session_id).first()
        if existing:
            # Backfill real metadata into placeholder if it was auto-created
            existing.developer_id = payload.developer_id
            existing.team_id = payload.team_id
            existing.started_at = payload.started_at
            existing.cwd_hash = payload.cwd_hash
            db.commit()
            return {"accepted": True, "event": "session_start", "backfilled": True}
        db.add(Session(
            session_id=payload.session_id,
            developer_id=payload.developer_id,
            team_id=payload.team_id,
            started_at=payload.started_at,
            cwd_hash=payload.cwd_hash,
        ))
        db.commit()
        return {"accepted": True, "event": "session_start"}

    if isinstance(payload, SessionEndEvent):
        session = db.query(Session).filter_by(session_id=payload.session_id).first()
        if session:
            session.ended_at = payload.ended_at
            session.turns = payload.turns
            db.commit()
        return {"accepted": True, "event": "session_end"}

    raise HTTPException(status_code=400, detail="Unknown session event")

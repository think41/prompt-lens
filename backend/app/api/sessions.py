from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from ..db.client import get_db
from ..db.models import Session, Turn, ToolEvent
from ..middleware.auth import get_current_developer
from ..schemas.sessions import SessionSummary, SessionDetail, TurnDetail, ToolEventDetail, TrendPoint
from ..services.streak import get_streak_flag

router = APIRouter(prefix="/sessions", tags=["sessions"])

Developer = Annotated[dict, Depends(get_current_developer)]


@router.get("", response_model=list[SessionSummary])
def list_sessions(current: Developer, db: DBSession = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    sessions = (
        db.query(Session)
        .filter(
            Session.developer_id == current["developer_id"],
            Session.started_at >= cutoff,
        )
        .order_by(Session.started_at.desc())
        .limit(30)
        .all()
    )

    result = []
    for s in sessions:
        avg = (
            db.query(func.avg(Turn.quality_score))
            .filter(Turn.session_id == s.session_id)
            .scalar()
        )
        result.append(SessionSummary(
            session_id=s.session_id,
            started_at=s.started_at,
            ended_at=s.ended_at,
            turns=s.turns,
            avg_quality_score=round(float(avg), 2) if avg else None,
            streak_warning=get_streak_flag(s.session_id, db),
        ))
    return result


@router.get("/trends/weekly", response_model=list[TrendPoint])
def weekly_trends(current: Developer, db: DBSession = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(
            func.date_trunc("week", Turn.created_at).label("week_start"),
            func.avg(Turn.quality_score).label("avg_score"),
            func.count(Turn.id).label("turn_count"),
        )
        .join(Session, Session.session_id == Turn.session_id)
        .filter(
            Session.developer_id == current["developer_id"],
            Turn.created_at >= cutoff,
        )
        .group_by("week_start")
        .order_by("week_start")
        .all()
    )
    return [
        TrendPoint(week_start=r.week_start, avg_score=round(float(r.avg_score), 2), turn_count=r.turn_count)
        for r in rows
    ]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, current: Developer, db: DBSession = Depends(get_db)):
    session = (
        db.query(Session)
        .filter(
            Session.session_id == session_id,
            Session.developer_id == current["developer_id"],
        )
        .first()
    )
    if not session:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    turns = db.query(Turn).filter(Turn.session_id == session_id).order_by(Turn.turn_index).all()
    tools = db.query(ToolEvent).filter(ToolEvent.session_id == session_id).order_by(ToolEvent.created_at).all()

    return SessionDetail(
        session_id=session.session_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        turns=session.turns,
        streak_warning=get_streak_flag(session_id, db),
        turn_events=[TurnDetail.model_validate(t) for t in turns],
        tool_events=[ToolEventDetail.model_validate(t) for t in tools],
    )

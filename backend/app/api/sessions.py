from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession, joinedload

from ..core.exceptions import AppException, ErrorCode
from ..db.client import get_db
from ..db.models import Session, ToolEvent, Turn
from ..middleware.auth import get_current_developer
from ..schemas.response import APIResponse, PagedResponse, ResponseMeta
from ..schemas.sessions import (
    SessionDetail,
    SessionSummary,
    ToolEventDetail,
    TrendPoint,
    TurnDetail,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])

Developer = Annotated[dict, Depends(get_current_developer)]

_STREAK_WARN = 5
_PAGE_SIZE = 20


@router.get("", response_model=PagedResponse[SessionSummary])
def list_sessions(
    current: Developer,
    request: Request,
    page: int = 1,
    page_size: int = _PAGE_SIZE,
    db: DBSession = Depends(get_db),
) -> PagedResponse[SessionSummary]:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    offset = (page - 1) * page_size

    base_q = db.query(Session).filter(
        Session.developer_id == current["developer_id"],
        Session.started_at >= cutoff,
    )
    total = base_q.count()

    sessions = (
        base_q
        .options(joinedload(Session.developer), joinedload(Session.project))
        .order_by(Session.started_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    if not sessions:
        return PagedResponse(data=[], total=total, page=page, page_size=page_size, meta=ResponseMeta())

    session_ids = [s.session_id for s in sessions]

    avg_rows = (
        db.query(Turn.session_id, func.avg(Turn.quality_score).label("avg"))
        .filter(Turn.session_id.in_(session_ids))
        .group_by(Turn.session_id)
        .all()
    )
    avg_map = {row.session_id: float(row.avg) for row in avg_rows if row.avg is not None}

    latest_at_sub = (
        db.query(ToolEvent.session_id, func.max(ToolEvent.created_at).label("max_at"))
        .filter(ToolEvent.session_id.in_(session_ids))
        .group_by(ToolEvent.session_id)
        .subquery()
    )
    streak_rows = (
        db.query(ToolEvent.session_id, ToolEvent.accept_streak)
        .join(
            latest_at_sub,
            (ToolEvent.session_id == latest_at_sub.c.session_id)
            & (ToolEvent.created_at == latest_at_sub.c.max_at),
        )
        .all()
    )
    streak_map = {row.session_id: row.accept_streak >= _STREAK_WARN for row in streak_rows}

    data = [
        SessionSummary(
            session_id=s.session_id,
            developer_id=s.developer_id,
            developer_name=s.developer.name if s.developer else None,
            developer_email=s.developer.email if s.developer else None,
            team_id=s.team_id,
            project_name=s.project.project_name if s.project else None,
            project_url=s.project.project_url if s.project else None,
            started_at=s.started_at,
            ended_at=s.ended_at,
            turn_count=s.turn_count,
            orchestration_score=s.orchestration_score,
            session_flags=s.session_flags or [],
            avg_quality_score=round(avg_map[s.session_id], 2) if s.session_id in avg_map else None,
            streak_warning=streak_map.get(s.session_id, False),
        )
        for s in sessions
    ]
    return PagedResponse(data=data, total=total, page=page, page_size=page_size, meta=ResponseMeta())


@router.get("/trends/weekly", response_model=APIResponse[list[TrendPoint]])
def weekly_trends(
    current: Developer,
    request: Request,
    db: DBSession = Depends(get_db),
) -> APIResponse[list[TrendPoint]]:
    cutoff = datetime.now(UTC) - timedelta(days=30)
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
    data = [
        TrendPoint(
            week_start=r.week_start,
            avg_score=round(float(r.avg_score), 2),
            turn_count=r.turn_count,
        )
        for r in rows
    ]
    return APIResponse(data=data, meta=ResponseMeta())


@router.get("/{session_id}", response_model=APIResponse[SessionDetail])
def get_session(
    session_id: str,
    current: Developer,
    request: Request,
    db: DBSession = Depends(get_db),
) -> APIResponse[SessionDetail]:
    session = (
        db.query(Session)
        .options(joinedload(Session.developer), joinedload(Session.project))
        .filter(
            Session.session_id == session_id,
            Session.developer_id == current["developer_id"],
        )
        .first()
    )
    if not session:
        raise AppException(ErrorCode.SESSION_NOT_FOUND, f"Session '{session_id}' not found")

    turns = db.query(Turn).filter(Turn.session_id == session_id).order_by(Turn.turn_index).all()
    tools = (
        db.query(ToolEvent)
        .filter(ToolEvent.session_id == session_id)
        .order_by(ToolEvent.created_at)
        .all()
    )

    detail = SessionDetail(
        session_id=session.session_id,
        developer_id=session.developer_id,
        developer_name=session.developer.name if session.developer else None,
        developer_email=session.developer.email if session.developer else None,
        team_id=session.team_id,
        project_name=session.project.project_name if session.project else None,
        project_url=session.project.project_url if session.project else None,
        started_at=session.started_at,
        ended_at=session.ended_at,
        turn_count=session.turn_count,
        orchestration_score=session.orchestration_score,
        session_flags=session.session_flags or [],
        streak_warning=bool(tools and tools[-1].accept_streak >= _STREAK_WARN),
        turn_events=[TurnDetail.model_validate(t) for t in turns],
        tool_events=[ToolEventDetail.model_validate(t) for t in tools],
    )
    return APIResponse(data=detail, meta=ResponseMeta())

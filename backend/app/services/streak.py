from sqlalchemy.orm import Session as DBSession

from ..db.models import ToolEvent

STREAK_WARN = 5


def get_streak_flag(session_id: str, db: DBSession) -> bool:
    latest = (
        db.query(ToolEvent)
        .filter(ToolEvent.session_id == session_id)
        .order_by(ToolEvent.created_at.desc())
        .first()
    )
    return latest is not None and latest.accept_streak >= STREAK_WARN

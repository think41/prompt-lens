from datetime import datetime

from pydantic import BaseModel


class TurnDetail(BaseModel):
    id: int
    turn_index: int
    prompt_hash: str
    prompt_chars: int
    prompt_text: str | None  # non-null when PRIVACY_ENABLED=false
    quality_score: float
    flags: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolEventDetail(BaseModel):
    id: int
    turn_index: int
    tool_name: str
    allowed: bool
    accept_streak: int
    sensitive_path: bool
    file_path: str | None  # non-null when PRIVACY_ENABLED=false
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionSummary(BaseModel):
    session_id: str
    developer_name: str | None
    developer_email: str | None
    team_id: str
    project_url: str | None
    project_name: str | None
    started_at: datetime
    ended_at: datetime | None
    turns: int
    avg_quality_score: float | None
    streak_warning: bool


class SessionDetail(BaseModel):
    session_id: str
    developer_name: str | None
    developer_email: str | None
    team_id: str
    project_url: str | None
    project_name: str | None
    started_at: datetime
    ended_at: datetime | None
    turns: int
    streak_warning: bool
    turn_events: list[TurnDetail]
    tool_events: list[ToolEventDetail]


class TrendPoint(BaseModel):
    week_start: datetime
    avg_score: float
    turn_count: int

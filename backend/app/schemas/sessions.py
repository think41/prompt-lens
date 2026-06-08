from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class TurnDetail(BaseModel):
    id: int
    turn_index: int
    prompt_hash: str
    prompt_chars: int
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
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionSummary(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    turns: int
    avg_quality_score: Optional[float]
    streak_warning: bool


class SessionDetail(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    turns: int
    streak_warning: bool
    turn_events: list[TurnDetail]
    tool_events: list[ToolEventDetail]


class TrendPoint(BaseModel):
    week_start: datetime
    avg_score: float
    turn_count: int

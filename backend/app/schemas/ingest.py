from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PromptEvent(BaseModel):
    type: Literal["prompt"]
    session_id: str
    developer_id: str
    developer_name: str | None = None
    developer_email: str | None = None
    team_id: str
    project_url: str | None = None
    project_name: str | None = None
    turn_index: int = 0
    prompt_hash: str = Field(..., description="SHA-256 hex of original prompt")
    prompt_chars: int
    prompt_text: str | None = None  # populated when PRIVACY_ENABLED=false
    quality_score: float = Field(ge=0.0, le=1.0)
    flags: list[str] = []
    cwd: str | None = None
    timestamp: datetime


class ToolEvent(BaseModel):
    type: Literal["tool"]
    session_id: str
    developer_id: str
    team_id: str
    turn_index: int = 0
    tool_name: str
    allowed: bool
    accept_streak: int = 0
    total_accepts: int = 0
    total_rejects: int = 0
    sensitive_path: bool = False
    file_path_hash: str | None = None
    file_path: str | None = None  # populated when PRIVACY_ENABLED=false
    timestamp: datetime


class SessionStartEvent(BaseModel):
    event: Literal["session_start"]
    session_id: str
    developer_id: str
    developer_name: str | None = None
    developer_email: str | None = None
    team_id: str
    project_url: str | None = None
    project_name: str | None = None
    started_at: datetime
    cwd_hash: str | None = None
    cwd: str | None = None


class SessionEndEvent(BaseModel):
    event: Literal["session_end"]
    session_id: str
    developer_id: str
    team_id: str
    ended_at: datetime
    turns: int = 0

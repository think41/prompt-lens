from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .client import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    developer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    developer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    developer_email: Mapped[str | None] = mapped_column(String(256), nullable=True)
    team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    turns: Mapped[int] = mapped_column(Integer, default=0)
    cwd_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cwd: Mapped[str | None] = mapped_column(Text, nullable=True)

    turn_events: Mapped[list["Turn"]] = relationship("Turn", back_populates="session")
    tool_events: Mapped[list["ToolEvent"]] = relationship("ToolEvent", back_populates="session")


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (UniqueConstraint("session_id", "turn_index", name="uq_turns_session_turn"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sessions.session_id"), index=True, nullable=False
    )
    developer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["Session"] = relationship("Session", back_populates="turn_events")


class ToolEvent(Base):
    __tablename__ = "tool_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sessions.session_id"), index=True, nullable=False
    )
    developer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accept_streak: Mapped[int] = mapped_column(Integer, default=0)
    total_accepts: Mapped[int] = mapped_column(Integer, default=0)
    total_rejects: Mapped[int] = mapped_column(Integer, default=0)
    sensitive_path: Mapped[bool] = mapped_column(Boolean, default=False)
    file_path_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["Session"] = relationship("Session", back_populates="tool_events")

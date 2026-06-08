from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .client import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    developer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    turns: Mapped[int] = mapped_column(Integer, default=0)
    cwd_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    turn_events: Mapped[list["Turn"]] = relationship("Turn", back_populates="session")
    tool_events: Mapped[list["ToolEvent"]] = relationship("ToolEvent", back_populates="session")


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), ForeignKey("sessions.session_id"), index=True, nullable=False)
    developer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    team_id: Mapped[str] = mapped_column(String(64), nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["Session"] = relationship("Session", back_populates="turn_events")


class ToolEvent(Base):
    __tablename__ = "tool_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), ForeignKey("sessions.session_id"), index=True, nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["Session"] = relationship("Session", back_populates="tool_events")

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .client import Base, TimestampMixin


class Developer(TimestampMixin, Base):
    __tablename__ = "developers"

    developer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    email: Mapped[str | None] = mapped_column(String(256), nullable=True)

    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="developer")


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    team_id: Mapped[str] = mapped_column(String(64), primary_key=True)

    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="team")
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="team")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("team_id", "project_name", name="uq_projects_team_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[str] = mapped_column(String(64), ForeignKey("teams.team_id"), nullable=False)
    project_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_name: Mapped[str] = mapped_column(String(256), nullable=False)

    team: Mapped["Team"] = relationship("Team", back_populates="projects")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="project")


class Session(TimestampMixin, Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "orchestration_score IS NULL OR (orchestration_score >= 0 AND orchestration_score <= 1)",
            name="ck_sessions_orchestration_score",
        ),
        CheckConstraint("turn_count >= 0", name="ck_sessions_turn_count"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    developer_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("developers.developer_id"), index=True, nullable=False
    )
    team_id: Mapped[str] = mapped_column(String(64), ForeignKey("teams.team_id"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    orchestration_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    session_flags: Mapped[list] = mapped_column(ARRAY(String), nullable=True, default=list)
    cwd_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cwd: Mapped[str | None] = mapped_column(Text, nullable=True)

    developer: Mapped["Developer"] = relationship("Developer", back_populates="sessions")
    team: Mapped["Team"] = relationship("Team", back_populates="sessions")
    project: Mapped["Project | None"] = relationship("Project", back_populates="sessions")
    turn_events: Mapped[list["Turn"]] = relationship("Turn", back_populates="session")
    tool_events: Mapped[list["ToolEvent"]] = relationship("ToolEvent", back_populates="session")


class Turn(TimestampMixin, Base):
    __tablename__ = "turns"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_index", name="uq_turns_session_turn"),
        CheckConstraint("quality_score >= 0 AND quality_score <= 1", name="ck_turns_quality_score"),
        CheckConstraint("prompt_chars > 0", name="ck_turns_prompt_chars"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sessions.session_id"), index=True, nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    flags: Mapped[list] = mapped_column(ARRAY(String), default=list)

    session: Mapped["Session"] = relationship("Session", back_populates="turn_events")


class ToolEvent(TimestampMixin, Base):
    __tablename__ = "tool_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(128), ForeignKey("sessions.session_id"), index=True, nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accept_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sensitive_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    file_path_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["Session"] = relationship("Session", back_populates="tool_events")

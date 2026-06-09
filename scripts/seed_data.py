#!/usr/bin/env python3
"""
Seed the local Postgres DB with realistic fake sessions for dev/demo.

Usage:
    python scripts/seed_data.py               # default: 3 devs × 10 sessions
    python scripts/seed_data.py --devs 5 --sessions 15
    python scripts/seed_data.py --clear       # wipe seed data then re-seed

Fake developer IDs are prefixed with "seed-" so they can be wiped cleanly.
"""

import argparse
import hashlib
import os
import random
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://promptlens:promptlens@localhost:5432/promptlens",
)

engine = create_engine(DATABASE_URL)
DB = sessionmaker(bind=engine)

# ---------------------------------------------------------------------------
# Fake data pools
# ---------------------------------------------------------------------------

DEVELOPERS = [
    {"name": "Arjun Mehta", "email": "arjun.mehta@think41.com", "team": "think41"},
    {"name": "Priya Nair", "email": "priya.nair@think41.com", "team": "think41"},
    {"name": "Rahul Sharma", "email": "rahul.sharma@think41.com", "team": "think41"},
    {"name": "Divya Krishnan", "email": "divya.krishnan@think41.com", "team": "think41"},
    {"name": "Siddharth Rao", "email": "siddharth.rao@think41.com", "team": "think41"},
]

HIGH_QUALITY_PROMPTS = [
    "Getting a TypeError in line 42 of backend/app/api/sessions.py:\n```python\nreturn db.query(Turn).filter_by(session_id=sid).all()\n```\nError: column 'session_id' not found. Schema uses 'id'.",
    "Add pagination to GET /sessions. Need page + page_size params, default page=1 size=20. Return total_count in response. File: backend/app/api/sessions.py",
    "Refactor the authentication middleware to use JWT RS256 instead of HS256. Current impl: backend/app/middleware/auth.py",
    "Docker build fails:\n```\nERROR [backend 5/6] RUN uv pip install -r requirements.txt\nexit code: 1\nResolutionImpossible: psycopg2-binary==2.9.9\n```\nRunning Python 3.11 Ubuntu 22.04. Resolve the dependency conflict.",
    "Write pytest fixture that sets up test Postgres DB, runs Alembic migrations, tears down after suite. Target: backend/tests/conftest.py",
    "Celery task score_turn at backend/app/jobs/celery_app.py raises KeyError on `turn.flags` when flags column is None. Add null guard.",
    "The weekly_trends query in sessions.py returns empty for new users. SQL uses INNER JOIN — change to LEFT JOIN to include sessions with no turns.",
]

MEDIUM_QUALITY_PROMPTS = [
    "How do I add authentication to my FastAPI app? I want JWT tokens.",
    "Write a Celery task that scores prompts. Should update the database after scoring.",
    "How does SQLAlchemy relationship work with lazy loading vs eager loading?",
    "Add error handling to the ingest endpoint.",
    "How do I configure CORS in FastAPI?",
]

LOW_QUALITY_PROMPTS = [
    "fix it",
    "not working",
    "help",
    "make it work",
    "broken",
    "do it",
    "update this",
]

FLAG_MAP = {
    "high": [],
    "medium": ["missing_context"],
    "low": ["too_short", "vague", "low_specificity"],
}

SCORE_RANGE = {
    "high": (0.70, 0.95),
    "medium": (0.40, 0.65),
    "low": (0.10, 0.35),
}

TOOLS = ["Read", "Edit", "Write", "Bash", "Grep"]

PROJECT_URL = "https://github.com/Think41/promptlens"
PROJECT_NAME = "promptlens"


def _dev_id(name: str) -> str:
    return "seed-" + hashlib.sha256(name.encode()).hexdigest()[:16]


def _prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _rand_score(tier: str) -> float:
    lo, hi = SCORE_RANGE[tier]
    return round(random.uniform(lo, hi), 2)


def _pick_prompt() -> tuple[str, str, float, list[str]]:
    roll = random.random()
    if roll < 0.4:
        tier = "high"
        text = random.choice(HIGH_QUALITY_PROMPTS)
    elif roll < 0.75:
        tier = "medium"
        text = random.choice(MEDIUM_QUALITY_PROMPTS)
    else:
        tier = "low"
        text = random.choice(LOW_QUALITY_PROMPTS)
    return text, tier, _rand_score(tier), FLAG_MAP[tier]


def seed(num_devs: int = 3, sessions_per_dev: int = 10) -> None:
    db = DB()
    now = datetime.now(UTC)
    devs = DEVELOPERS[:num_devs]
    total_sessions = 0
    total_turns = 0
    total_tools = 0

    for dev in devs:
        dev_id = _dev_id(dev["name"])
        for s_idx in range(sessions_per_dev):
            # Spread sessions over the last 30 days
            age_days = random.uniform(0, 29)
            age_hours = random.uniform(0, 8)
            started = now - timedelta(days=age_days, hours=age_hours)
            duration_mins = random.randint(15, 120)
            ended = started + timedelta(minutes=duration_mins)

            session_id = str(uuid.uuid4())
            num_turns = random.randint(2, 8)

            db.execute(
                text(
                    """
                    INSERT INTO sessions
                      (session_id, developer_id, developer_name, developer_email,
                       team_id, project_url, project_name, started_at, ended_at, turns)
                    VALUES
                      (:sid, :did, :dname, :demail, :team, :purl, :pname, :start, :end, :turns)
                    ON CONFLICT (session_id) DO NOTHING
                    """
                ),
                {
                    "sid": session_id,
                    "did": dev_id,
                    "dname": dev["name"],
                    "demail": dev["email"],
                    "team": dev["team"],
                    "purl": PROJECT_URL,
                    "pname": PROJECT_NAME,
                    "start": started,
                    "end": ended,
                    "turns": num_turns,
                },
            )

            accept_streak = 0
            total_accepts = 0
            total_rejects = 0

            for t_idx in range(num_turns):
                prompt_text, tier, score, flags = _pick_prompt()
                turn_time = started + timedelta(minutes=t_idx * (duration_mins / num_turns))
                db.execute(
                    text(
                        """
                        INSERT INTO turns
                          (session_id, developer_id, team_id, turn_index,
                           prompt_hash, prompt_chars, prompt_text, quality_score, flags, created_at)
                        VALUES
                          (:sid, :did, :team, :tidx, :phash, :pchars, :ptxt, :score, :flags, :ts)
                        """
                    ),
                    {
                        "sid": session_id,
                        "did": dev_id,
                        "team": dev["team"],
                        "tidx": t_idx,
                        "phash": _prompt_hash(prompt_text + session_id + str(t_idx)),
                        "pchars": len(prompt_text),
                        "ptxt": prompt_text,
                        "score": score,
                        "flags": flags,
                        "ts": turn_time,
                    },
                )
                total_turns += 1

                # Generate 1–4 tool events per turn
                for tool_call in range(random.randint(1, 4)):
                    tool = random.choice(TOOLS)
                    accepted = random.random() > 0.15  # 85% accept rate
                    if accepted:
                        accept_streak += 1
                        total_accepts += 1
                    else:
                        accept_streak = 0
                        total_rejects += 1
                    file_path = f"backend/app/api/{random.choice(['sessions', 'ingest', 'health'])}.py"
                    tool_time = turn_time + timedelta(seconds=tool_call * 30)
                    db.execute(
                        text(
                            """
                            INSERT INTO tool_events
                              (session_id, developer_id, team_id, turn_index, tool_name,
                               allowed, accept_streak, total_accepts, total_rejects,
                               sensitive_path, file_path, created_at)
                            VALUES
                              (:sid, :did, :team, :tidx, :tool, :allowed,
                               :streak, :accepts, :rejects, :sens, :fp, :ts)
                            """
                        ),
                        {
                            "sid": session_id,
                            "did": dev_id,
                            "team": dev["team"],
                            "tidx": t_idx,
                            "tool": tool,
                            "allowed": accepted,
                            "streak": accept_streak,
                            "accepts": total_accepts,
                            "rejects": total_rejects,
                            "sens": False,
                            "fp": file_path,
                            "ts": tool_time,
                        },
                    )
                    total_tools += 1

            total_sessions += 1

    db.commit()
    db.close()
    print(
        f"Seeded {total_sessions} sessions, {total_turns} turns, {total_tools} tool events "
        f"for {num_devs} developer(s)."
    )


def clear_seed_data() -> None:
    db = DB()
    # Delete by seed- prefixed developer_ids
    result = db.execute(
        text("DELETE FROM tool_events WHERE developer_id LIKE 'seed-%'")
    )
    te = result.rowcount
    result = db.execute(text("DELETE FROM turns WHERE developer_id LIKE 'seed-%'"))
    tu = result.rowcount
    result = db.execute(text("DELETE FROM sessions WHERE developer_id LIKE 'seed-%'"))
    se = result.rowcount
    db.commit()
    db.close()
    print(f"Cleared {se} sessions, {tu} turns, {te} tool events.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed PromptLens with fake dev data")
    parser.add_argument("--devs", type=int, default=3, help="Number of fake developers (max 5)")
    parser.add_argument("--sessions", type=int, default=10, help="Sessions per developer")
    parser.add_argument("--clear", action="store_true", help="Clear seed data and re-seed")
    args = parser.parse_args()

    if args.clear:
        clear_seed_data()

    seed(min(args.devs, len(DEVELOPERS)), args.sessions)

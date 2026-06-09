"""
Acceptance tests for blind-accept streak detection.

Acceptance criterion: streak_warning=True fires when a session has ≥5
consecutive tool accepts, and clears after a reject.
"""

import hashlib
import os
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.client import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://promptlens:promptlens@localhost:5432/promptlens_test",
)

engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _override_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db

SESSION_ID = "streak-test-sess-001"
DEVELOPER_ID = "streak-dev-hash"
TEAM_ID = "think41"


def _ts() -> str:
    return datetime.now(UTC).isoformat()


def _tool_payload(accepted: bool, streak: int, accepts: int, rejects: int) -> dict:
    return {
        "type": "tool",
        "session_id": SESSION_ID,
        "developer_id": DEVELOPER_ID,
        "team_id": TEAM_ID,
        "turn_index": 0,
        "tool_name": "Edit",
        "allowed": accepted,
        "accept_streak": streak,
        "total_accepts": accepts,
        "total_rejects": rejects,
        "sensitive_path": False,
        "file_path_hash": None,
        "timestamp": _ts(),
    }


def _prompt_payload(turn_index: int = 0) -> dict:
    text = f"seed prompt for turn {turn_index}"
    return {
        "type": "prompt",
        "session_id": SESSION_ID,
        "developer_id": DEVELOPER_ID,
        "team_id": TEAM_ID,
        "turn_index": turn_index,
        "prompt_hash": hashlib.sha256(text.encode()).hexdigest(),
        "prompt_chars": len(text),
        "quality_score": 0.75,
        "flags": [],
        "timestamp": _ts(),
    }


async def _post(client, url, payload):
    return await client.post(url, json=payload)


@pytest.mark.asyncio
async def test_streak_warning_fires_at_five():
    """After 5 consecutive accepts, GET /sessions/:id must return streak_warning=True."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed a prompt turn so the session exists
        await _post(client, "/ingest/events", _prompt_payload(0))

        # Ingest 5 consecutive accepts, tracking streak manually
        for i in range(1, 6):
            r = await _post(client, "/ingest/events", _tool_payload(True, i, i, 0))
            assert r.status_code == 202

        # Issue a JWT and query the session
        token_r = await client.post(
            "/auth/token",
            json={"developer_id": DEVELOPER_ID, "team_id": TEAM_ID, "role": "developer"},
        )
        token = token_r.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        detail_r = await client.get(f"/sessions/{SESSION_ID}", headers=headers)
        assert detail_r.status_code == 200
        detail = detail_r.json()["data"]
        assert detail["streak_warning"] is True, (
            f"Expected streak_warning=True after 5 consecutive accepts, got: {detail}"
        )


@pytest.mark.asyncio
async def test_streak_warning_clears_after_reject():
    """After a reject following the streak, streak_warning should be False."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Post a reject (streak resets to 0)
        r = await _post(client, "/ingest/events", _tool_payload(False, 0, 5, 1))
        assert r.status_code == 202

        token_r = await client.post(
            "/auth/token",
            json={"developer_id": DEVELOPER_ID, "team_id": TEAM_ID, "role": "developer"},
        )
        token = token_r.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        detail_r = await client.get(f"/sessions/{SESSION_ID}", headers=headers)
        assert detail_r.status_code == 200
        detail = detail_r.json()["data"]
        assert detail["streak_warning"] is False, (
            f"Expected streak_warning=False after reject, got: {detail}"
        )


@pytest.mark.asyncio
async def test_streak_warning_false_below_threshold():
    """4 consecutive accepts must NOT trigger streak_warning."""
    sid = "streak-test-sess-002"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _post(
            client,
            "/ingest/events",
            {**_prompt_payload(0), "session_id": sid},
        )
        for i in range(1, 5):  # only 4 accepts
            await _post(
                client,
                "/ingest/events",
                {**_tool_payload(True, i, i, 0), "session_id": sid},
            )

        token_r = await client.post(
            "/auth/token",
            json={"developer_id": DEVELOPER_ID, "team_id": TEAM_ID, "role": "developer"},
        )
        token = token_r.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        detail_r = await client.get(f"/sessions/{sid}", headers=headers)
        assert detail_r.status_code == 200
        assert detail_r.json()["data"]["streak_warning"] is False

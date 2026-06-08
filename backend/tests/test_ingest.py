"""
Integration tests for ingest API.
Requires running Postgres (set DATABASE_URL env var) and the FastAPI app.
Run: pytest backend/tests/test_ingest.py
"""
import os
import pytest
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.client import Base, get_db

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://promptlens:promptlens@localhost:5432/promptlens_test",
)

engine = create_engine(DATABASE_URL)
TestSessionLocal = sessionmaker(bind=engine)


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_db


@pytest.fixture
def ts():
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_session_start(ts):
    payload = {
        "event": "session_start",
        "session_id": "test-sess-001",
        "developer_id": "devhash001",
        "team_id": "team-a",
        "started_at": ts,
        "cwd_hash": None,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/ingest/sessions", json=payload)
    assert r.status_code == 202
    assert r.json()["accepted"] is True

    db = TestSessionLocal()
    from app.db.models import Session
    row = db.query(Session).filter_by(session_id="test-sess-001").first()
    assert row is not None
    assert row.developer_id == "devhash001"
    db.close()


@pytest.mark.asyncio
async def test_ingest_prompt_event(ts):
    payload = {
        "type": "prompt",
        "session_id": "test-sess-001",
        "developer_id": "devhash001",
        "team_id": "team-a",
        "turn_index": 0,
        "prompt_hash": "abc123def456" * 5,
        "prompt_chars": 42,
        "quality_score": 0.75,
        "flags": [],
        "timestamp": ts,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/ingest/events", json=payload)
    assert r.status_code == 202

    db = TestSessionLocal()
    from app.db.models import Turn
    row = db.query(Turn).filter_by(session_id="test-sess-001", turn_index=0).first()
    assert row is not None
    assert row.prompt_hash == payload["prompt_hash"]
    assert row.quality_score == 0.75
    db.close()


@pytest.mark.asyncio
async def test_no_raw_prompt_in_db(ts):
    raw_prompt = "this is a secret prompt"
    import hashlib
    prompt_hash = hashlib.sha256(raw_prompt.encode()).hexdigest()

    payload = {
        "type": "prompt",
        "session_id": "test-sess-001",
        "developer_id": "devhash001",
        "team_id": "team-a",
        "turn_index": 1,
        "prompt_hash": prompt_hash,
        "prompt_chars": len(raw_prompt),
        "quality_score": 0.5,
        "flags": ["vague"],
        "timestamp": ts,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/ingest/events", json=payload)

    db = TestSessionLocal()
    result = db.execute(text("SELECT * FROM turns WHERE prompt_hash = :h"), {"h": prompt_hash}).fetchone()
    assert result is not None
    row_str = str(result)
    assert raw_prompt not in row_str
    db.close()


@pytest.mark.asyncio
async def test_ingest_tool_event(ts):
    payload = {
        "type": "tool",
        "session_id": "test-sess-001",
        "developer_id": "devhash001",
        "team_id": "team-a",
        "turn_index": 0,
        "tool_name": "Write",
        "allowed": True,
        "accept_streak": 1,
        "total_accepts": 1,
        "total_rejects": 0,
        "sensitive_path": False,
        "file_path_hash": None,
        "timestamp": ts,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/ingest/events", json=payload)
    assert r.status_code == 202

    db = TestSessionLocal()
    from app.db.models import ToolEvent
    row = db.query(ToolEvent).filter_by(session_id="test-sess-001", tool_name="Write").first()
    assert row is not None
    assert row.allowed is True
    db.close()


@pytest.mark.asyncio
async def test_ingest_session_end(ts):
    payload = {
        "event": "session_end",
        "session_id": "test-sess-001",
        "developer_id": "devhash001",
        "team_id": "team-a",
        "ended_at": ts,
        "turns": 2,
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/ingest/sessions", json=payload)
    assert r.status_code == 202

    db = TestSessionLocal()
    from app.db.models import Session
    row = db.query(Session).filter_by(session_id="test-sess-001").first()
    assert row is not None
    assert row.ended_at is not None
    assert row.turns == 2
    db.close()

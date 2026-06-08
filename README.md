# PromptLens

Team intelligence layer for AI-assisted development at Think41. Captures how developers prompt Claude Code, scores prompt quality, and surfaces anonymised patterns to tech leads — without individual surveillance.

---

## What It Does

- **Hooks** fire on every Claude Code prompt, tool use, and session boundary
- **Scoring** evaluates prompt quality (length, vagueness, context, security) via a rule-based evaluator chain
- **Developer mirror** shows each developer their own sessions and quality trends
- **Team layer** surfaces anonymised patterns to tech leads and EMs
- **Privacy-first** — no raw prompt text ever leaves the machine; only hashes and metadata

---

## Quick Start

```bash
# 1. Bootstrap dev environment
./scripts/setup.sh

# 2. Start local stack (Postgres + Redis + backend)
docker-compose up

# 3. Verify
curl http://localhost:8000/health
# {"status":"ok"}

# 4. Test a hook manually
echo '{"prompt":"fix it","session_id":"test-123"}' | python3 hooks/on_prompt.py
```

---

## Architecture

```
Claude Code session
      │
      ├── UserPromptSubmit ──► hooks/on_prompt.py   (redact → hash → score → POST)
      ├── PostToolUse      ──► hooks/on_tool.py     (streak tracking → POST)
      └── SessionStart/End ──► hooks/on_session.py  (session boundaries → POST)
                                          │
                               POST /ingest/events
                               POST /ingest/sessions
                                          │
                               FastAPI backend (port 8000)
                                          │
                        ┌─────────────────┴──────────────────┐
                        │                                    │
                   PostgreSQL                            Redis
                (sessions, turns,                   (Celery broker)
                 tool_events)                             │
                                                   score_turn task
                                               (EvaluatorChain async)
```

---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Hook scripts | Python 3.11 (stdlib only) |
| Backend API | FastAPI + Uvicorn |
| Task queue | Celery + Redis |
| Database | PostgreSQL 16 |
| Auth | JWT (PyJWT) |
| Evaluators | Rule-based chain (Length, Vagueness, Context, Security) |
| Frontend | React 18 + Vite + Tailwind + Recharts |
| Infra | Docker Compose (local), AWS ECS + RDS (prod) |

---

## Project Structure

```
promptlens/
├── hooks/                  # Claude Code hook scripts
│   ├── on_prompt.py        # UserPromptSubmit hook
│   ├── on_tool.py          # PostToolUse hook
│   └── on_session.py       # SessionStart/End hook
│
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes (health, ingest, sessions)
│   │   ├── evaluators/     # Prompt quality evaluator chain
│   │   ├── jobs/           # Celery tasks (score_turn)
│   │   ├── middleware/     # JWT auth
│   │   ├── schemas/        # Pydantic models
│   │   ├── services/       # Business logic (streak)
│   │   └── db/             # SQLAlchemy models + Alembic migrations
│   ├── tests/
│   └── requirements.txt
│
├── frontend/               # React developer mirror (WIP)
├── docs/
│   ├── hook-spec.md        # Hook stdin/stdout contracts
│   └── privacy-contract.md # Non-negotiable data rules
├── scripts/
│   └── setup.sh            # One-shot dev bootstrap
└── docker-compose.yml
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in secrets:

```bash
cp .env.example .env
```

| Variable | Purpose |
|----------|---------|
| `PROMPTLENS_ENDPOINT` | Backend ingest URL (default: `http://localhost:8000`) |
| `PROMPTLENS_DEVELOPER_ID` | SHA-256 machine token — set by `setup.sh` |
| `PROMPTLENS_TEAM_ID` | Team identifier |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET` | Token signing secret (`openssl rand -hex 32`) |

---

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `POST` | `/ingest/events` | None | Ingest prompt or tool event |
| `POST` | `/ingest/sessions` | None | Ingest session start/end |
| `GET` | `/sessions` | JWT | List own sessions (last 30 days) |
| `GET` | `/sessions/{id}` | JWT | Session detail with per-turn flags |
| `GET` | `/sessions/trends/weekly` | JWT | Rolling 30-day quality trend |

---

## Evaluator Chain

Prompt quality score is computed by four rule-based evaluators:

| Evaluator | Signals | Max Penalty |
|-----------|---------|-------------|
| `LengthEvaluator` | too_short (<20 chars), too_long (>2000 chars) | -0.4 |
| `VaguenessEvaluator` | 30+ vague phrases (fix it, help, broken…) | -0.45 |
| `ContextEvaluator` | Missing code signals, no file path, no error | -0.25 |
| `SecurityEvaluator` | .env, credentials, API keys, AWS secrets | -0.30 |

Score range: `0.0` (poor) → `1.0` (excellent). Hook hints fire when score < 0.4.

---

## Running Tests

```bash
# Hook unit tests (no DB required)
python3 -m unittest discover -s hooks/tests -v

# Evaluator tests (no DB required)
cd backend && python3 -m unittest tests.evaluators.test_chain -v

# Ingest integration tests (requires Postgres)
cd backend && pytest tests/test_ingest.py
```

---

## Privacy Contract

1. No developer name or email stored anywhere
2. `developer_id` = `SHA-256(machine_uuid)` — irreversible, no lookup table
3. Manager API responses never include `developer_id`
4. All redaction happens on-device before any HTTP call
5. Opt-in consent required before first data capture
6. Opt-out is immediate — hooks go silent next session

See `docs/privacy-contract.md` for full rules.

---

## Current Status

| Week | Scope | Status |
|------|-------|--------|
| 1–2 | Hooks + ingest API + Postgres | ✅ Done |
| 3–4 | Evaluators + Celery + JWT + sessions API | ✅ Done |
| 5–6 | Team layer + Slack digest | Pending |
| 7–8 | EM dashboard + AWS deploy + rollout | Pending |

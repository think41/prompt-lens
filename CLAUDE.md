# PromptLens — Claude Code Context

## What This Project Is

PromptLens is a team intelligence layer for AI-assisted development at Think41.
It captures how developers prompt Claude Code, scores prompt quality, surfaces
anonymised patterns to tech leads, and gives EMs visibility into AI adoption
health — without individual surveillance.

**Internal at Think41 first. Productisable later.**

---

## Tech Stack (Decided)

| Layer              | Choice                        | Reason                                                  |
|--------------------|-------------------------------|---------------------------------------------------------|
| Hook scripts       | Python 3.11                   | Ships on every dev machine; fast startup                |
| Backend API        | Python + FastAPI              | Team familiarity; async-native; OpenAPI for free        |
| Task queue         | Celery + Redis                | Async scoring after ingest; weekly digest job           |
| Database           | PostgreSQL 16 (AWS RDS)       | Aggregation queries; JSONB for patterns; team comfort   |
| Trace backend      | Langfuse (Cloud, self-host v2)| MIT core; session replay; evaluator UI                  |
| OTel pipeline      | otelcol-contrib               | Standard; custom redaction processors                   |
| Frontend           | React 18 + Vite + Tailwind    | Team knows it; fast dev loop                            |
| Cloud              | AWS                           | Best managed Postgres (RDS); ECS Fargate for containers |
| IaC                | AWS CDK (Python)              | Same language as backend; no context switch             |
| CI/CD              | GitHub Actions                | Standard; easy AWS OIDC integration                     |
| Secrets            | AWS Secrets Manager           | Native to AWS; avoids .env in production                |

---

## Repo Layout (Target — not all created yet)

```
promptlens/
│
├── CLAUDE.md               ← YOU ARE HERE — read this every session
├── ARCHITECTURE.md         ← System design, data flows, ADRs
├── PLANNING.md             ← 8-week sprint plan, task checklist
│
├── docs/
│   ├── data-schema.md      ← Postgres table definitions + rationale
│   ├── hook-spec.md        ← Hook input/output contracts
│   ├── evaluator-spec.md   ← Scoring rubric + flag definitions
│   └── privacy-contract.md ← Non-negotiable data rules
│
├── hooks/                  ← Claude Code hook scripts (Python)
│   ├── on_prompt.py        ← UserPromptSubmit: redact + score + POST
│   ├── on_tool.py          ← PostToolUse: accept/reject + streak
│   └── on_session.py       ← SessionStart / Stop: boundaries
│
├── .claude/                ← Claude Code plugin config
│   ├── settings.json       ← Hook wiring + plugin declaration
│   └── managed-settings.json ← Org-wide enforcement template
│
├── backend/                ← FastAPI application
│   ├── app/
│   │   ├── main.py
│   │   ├── api/            ← Route files (ingest, sessions, team, health)
│   │   ├── services/       ← Business logic (scoring, patterns, digest)
│   │   ├── evaluators/     ← Prompt quality evaluator chain
│   │   ├── models/         ← SQLAlchemy ORM models
│   │   ├── schemas/        ← Pydantic request/response schemas
│   │   ├── db/             ← Migrations (Alembic) + client
│   │   └── jobs/           ← Celery tasks (scoring, digest, patterns)
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/               ← React dashboard
│   ├── src/
│   │   ├── pages/          ← Developer mirror, Manager dashboard
│   │   └── components/     ← Shared UI components
│   ├── package.json
│   └── Dockerfile
│
├── collector/
│   └── collector.yaml      ← OTel Collector pipeline + redaction config
│
├── infra/                  ← AWS CDK (Python)
│   ├── app.py
│   └── stacks/             ← RDS, ECS, VPC, Secrets stacks
│
├── scripts/
│   ├── setup.sh            ← One-shot dev bootstrap
│   ├── deploy_managed.sh   ← Push managed-settings to team machines
│   └── seed_data.py        ← Generate fake sessions for dev/demo
│
├── docker-compose.yml      ← Local dev: postgres + redis + collector + backend + frontend
└── .env.example            ← Template — never commit .env
```

---

## Claude Code Setup (Every Developer)

```bash
# 1. Run once after cloning
./scripts/setup.sh

# 2. Confirm OTel is wired
claude /doctor

# 3. Test a hook manually
echo '{"prompt":"fix it","session_id":"test-123"}' | python hooks/on_prompt.py

# 4. Start local stack
docker-compose up
```

---

## Environment Variables (Full List)

| Variable                        | Where set          | Purpose                                  |
|---------------------------------|--------------------|------------------------------------------|
| `OTEL_EXPORTER_OTLP_ENDPOINT`   | Developer machine  | Claude Code → OTel Collector             |
| `ENABLE_BETA_TRACING_DETAILED`  | Developer machine  | Enables hook span capture                |
| `PROMPTLENS_ENDPOINT`           | Hook scripts       | Backend ingest URL                       |
| `PROMPTLENS_DEVELOPER_ID`       | Hook scripts       | SHA-256 machine token (set by setup.sh)  |
| `PROMPTLENS_TEAM_ID`            | Hook scripts       | Team identifier                          |
| `DATABASE_URL`                  | Backend            | Postgres connection string               |
| `REDIS_URL`                     | Backend + Celery   | Task queue                               |
| `LANGFUSE_SECRET_KEY`           | Backend            | Langfuse API key                         |
| `LANGFUSE_PUBLIC_KEY`           | Backend            | Langfuse public key                      |
| `SLACK_WEBHOOK_URL`             | Backend (Celery)   | Weekly digest webhook                    |
| `JWT_SECRET`                    | Backend            | Auth token signing                       |
| `AWS_REGION`                    | Infra / Backend    | AWS deployment region                    |

---

## Privacy Contract (Non-Negotiable)

These rules are enforced at the API layer. Any PR that breaks them is a blocker.

1. No developer name or email is ever stored server-side.
2. `developer_id` is always `SHA-256(machine_uuid)` — irreversible.
3. No manager-role API response ever includes a `developer_id` field.
4. All hook data is redacted locally **before** any HTTP call leaves the machine.
5. Opt-in consent UI must be shown on first hook execution; hooks are silent until acknowledged.
6. There is no de-anonymisation path — by design.

---

## Working Conventions

- **Branch naming**: `feat/`, `fix/`, `chore/` prefixes. PRs require passing CI.
- **Tests first for evaluators**: every evaluator has a golden test set before it ships.
- **Never block the Claude Code session**: hooks always exit with `{"decision": "continue"}`.
- **Fire-and-forget ingest**: hooks POST async — a dead backend must not slow down Claude Code.
- **No `.env` in git**: use `.env.example` as the template; secrets live in AWS Secrets Manager in prod.

---

## Current Focus: POC (Weeks 1–2)

Only two things matter right now:

1. **Hook scripts** — `on_prompt.py`, `on_tool.py`, `on_session.py` working end-to-end.
2. **Backend ingest API** — `POST /ingest/events` and `POST /ingest/sessions` accepting real data.

Everything else (frontend, scoring, team layer, Slack, GitHub App) is out of scope until these two pass their acceptance tests.

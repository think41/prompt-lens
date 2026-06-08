# PromptLens — Project Planning

## North Star

5 Think41 engineers complete 3 real Claude Code sessions each, with every session
captured, scored, and visible in the developer mirror — within 8 weeks.

---

## POC Scope (What We Are and Are Not Building)

### In scope for 8-week MVP
- Hook scripts (capture layer)
- Backend ingest API
- Prompt quality scoring (rule-based)
- Developer mirror dashboard
- Anonymised team pattern aggregation
- Weekly Slack digest
- EM health dashboard
- Org-wide managed-settings enforcement

### Explicitly out of scope for MVP
- LLM-judge evaluators (v2)
- MCP playbook server (v2)
- GitHub PR "how this was built" tab (v2)
- External-facing product / multi-tenant
- Billing or usage metering
- Mobile views

---

## Team Roles

| Role              | Owns                                                     |
|-------------------|----------------------------------------------------------|
| Backend engineer  | Hook scripts, FastAPI, Celery jobs, evaluators, DB schema|
| Frontend engineer | React dashboard, role-gated views, Langfuse integration  |
| DevOps / infra    | AWS CDK, ECS, RDS, managed-settings rollout              |
| Product / EM      | Privacy review, pilot recruitment, feedback synthesis    |

---

## Week-by-Week Plan

---

### Weeks 1–2: Foundation — POC Gate

**Goal**: A single developer's session flows end-to-end from Claude Code hook
to Postgres. Nothing else matters until this works.

#### Tasks

| # | Task | Owner | File / Component |
|---|------|-------|-----------------|
| 1 | Repo scaffold — folders, `.gitignore`, `.env.example` | Backend | `/` |
| 2 | `CLAUDE.md`, `ARCHITECTURE.md`, `PLANNING.md` written | All | `/` |
| 3 | `docs/hook-spec.md` — define stdin/stdout contracts | Backend | `docs/` |
| 4 | `docs/privacy-contract.md` — written and signed off by EM | Product | `docs/` |
| 5 | `on_prompt.py` — reads stdin, redacts, POSTs async, exits | Backend | `hooks/` |
| 6 | `on_tool.py` — accept/reject tracking, streak counter | Backend | `hooks/` |
| 7 | `on_session.py` — session start/end boundaries | Backend | `hooks/` |
| 8 | `.claude/settings.json` — hooks wired to scripts | Backend | `.claude/` |
| 9 | FastAPI project scaffold — `main.py`, folder structure | Backend | `backend/` |
| 10 | Pydantic schemas for all ingest payloads | Backend | `backend/app/schemas/` |
| 11 | `POST /ingest/events` endpoint (prompt + tool events) | Backend | `backend/app/api/ingest.py` |
| 12 | `POST /ingest/sessions` endpoint (start + end) | Backend | `backend/app/api/ingest.py` |
| 13 | `GET /health` endpoint | Backend | `backend/app/api/health.py` |
| 14 | PostgreSQL schema + Alembic migrations (sessions, turns, tool_events) | Backend | `backend/app/db/` |
| 15 | `docker-compose.yml` — postgres + redis + backend | DevOps | `/` |
| 16 | `scripts/setup.sh` — installs deps, sets `PROMPTLENS_DEVELOPER_ID` | Backend | `scripts/` |
| 17 | Hook unit tests — mock stdin, assert POST payload shape | Backend | `hooks/tests/` |
| 18 | Ingest API integration tests — real DB writes | Backend | `backend/tests/` |

#### Acceptance Criteria (Week 2 gate)

- [ ] `./scripts/setup.sh` completes without errors on a fresh macOS machine
- [ ] `echo '{"prompt":"fix it","session_id":"abc"}' | python hooks/on_prompt.py` exits in < 200ms and returns `{"decision":"continue"}`
- [ ] A real Claude Code session (`claude "hello"`) produces rows in `sessions` and `turns` tables within 10 seconds
- [ ] `GET /health` returns `200` from inside Docker network
- [ ] Hook tests pass: `pytest hooks/tests/`
- [ ] Ingest tests pass: `pytest backend/tests/test_ingest.py`
- [ ] No raw prompt text in any Postgres row (only hash + char count)

---

### Weeks 3–4: Intelligence Layer

**Goal**: Full evaluator chain running. Blind-accept streak detection live.
Developer can see their own score in a basic UI.

#### Tasks

| # | Task | Owner | File / Component |
|---|------|-------|-----------------|
| 19 | `LengthEvaluator` — rule-based, unit tested | Backend | `backend/app/evaluators/` |
| 20 | `VaguenessEvaluator` — vague phrase list, scored | Backend | `backend/app/evaluators/` |
| 21 | `ContextEvaluator` — code signal detection | Backend | `backend/app/evaluators/` |
| 22 | `SecurityEvaluator` — sensitive path patterns | Backend | `backend/app/evaluators/` |
| 23 | Evaluator chain — weighted aggregate score | Backend | `backend/app/evaluators/chain.py` |
| 24 | Golden test set — 20 prompts with expected scores/flags | Backend | `backend/tests/evaluators/` |
| 25 | Celery worker setup — `score_turn` task | Backend | `backend/app/jobs/` |
| 26 | `score_turn` task wired from ingest endpoint | Backend | `backend/app/api/ingest.py` |
| 27 | Blind-accept streak logic — flag sessions ≥ 5 streak | Backend | `backend/app/services/streak.py` |
| 28 | Real-time hint in hook stdout when score < 0.4 | Backend | `hooks/on_prompt.py` |
| 29 | `GET /sessions` — list own sessions with scores | Backend | `backend/app/api/sessions.py` |
| 30 | `GET /sessions/:id` — turns + tool events for own session | Backend | `backend/app/api/sessions.py` |
| 31 | `GET /sessions/trends/weekly` — rolling 30-day chart data | Backend | `backend/app/api/sessions.py` |
| 32 | JWT auth middleware — developer_id from token | Backend | `backend/app/middleware/auth.py` |
| 33 | React project scaffold — Vite + Tailwind + React Router | Frontend | `frontend/` |
| 34 | Developer mirror page — session list with score badges | Frontend | `frontend/src/pages/Developer.tsx` |
| 35 | Session detail view — turn-by-turn breakdown with flags | Frontend | `frontend/src/pages/SessionDetail.tsx` |
| 36 | Quality trend chart — 30-day rolling average | Frontend | `frontend/src/components/TrendChart.tsx` |
| 37 | Langfuse integration — forward spans from backend | Backend | `backend/app/services/langfuse.py` |

#### Acceptance Criteria (Week 4 gate)

- [ ] All 4 evaluators score correctly on 20 golden prompts (automated test)
- [ ] Blind-accept streak flag fires after 5 consecutive tool accepts
- [ ] Developer hint appears in Claude Code terminal when score < 0.4
- [ ] Developer mirror shows last 10 sessions with quality scores
- [ ] Session detail shows per-turn flags
- [ ] Trend chart renders with seeded data (`scripts/seed_data.py`)

---

### Weeks 5–6: Team Layer

**Goal**: Anonymised team pool working. Tech lead can see patterns.
Slack digest posting.

#### Tasks

| # | Task | Owner | File / Component |
|---|------|-------|-----------------|
| 38 | Nightly aggregation Celery job — populates `team_patterns` | Backend | `backend/app/jobs/aggregate.py` |
| 39 | `GET /team/trends` — team quality over time (aggregated) | Backend | `backend/app/api/team.py` |
| 40 | `GET /team/flags` — flag frequency counts (no individual data) | Backend | `backend/app/api/team.py` |
| 41 | `GET /team/summary` — EM health card | Backend | `backend/app/api/team.py` |
| 42 | `GET /team/patterns` — anonymised weekly patterns | Backend | `backend/app/api/team.py` |
| 43 | RBAC middleware — manager endpoints reject developer role | Backend | `backend/app/middleware/rbac.py` |
| 44 | Integration test — assert manager endpoint returns zero `developer_id` fields | Backend | `backend/tests/test_privacy.py` |
| 45 | Slack digest Celery task — Monday 9am IST | Backend | `backend/app/jobs/digest.py` |
| 46 | Digest content logic — 1 great pattern + 1 failure mode | Backend | `backend/app/services/digest.py` |
| 47 | Tech lead view — anonymised pattern cards | Frontend | `frontend/src/pages/TeamPatterns.tsx` |
| 48 | `managed-settings.json` template — org enforcement config | DevOps | `.claude/managed-settings.json` |
| 49 | `scripts/deploy_managed.sh` — copies to `~/.claude/` on each machine | DevOps | `scripts/` |

#### Acceptance Criteria (Week 6 gate)

- [ ] Slack digest posts to `#engineering-ai` with real (not seeded) data
- [ ] Manager API `GET /team/flags` — verified: no `developer_id` in response (automated test)
- [ ] Tech lead view shows pattern cards for current week
- [ ] `managed-settings.json` deployed to 2 test machines; hooks confirmed active via `/doctor`

---

### Weeks 7–8: EM Dashboard + Internal Rollout

**Goal**: Full EM dashboard. Consent flow. 5 engineers on real sessions. Demo-ready.

#### Tasks

| # | Task | Owner | File / Component |
|---|------|-------|-----------------|
| 50 | EM dashboard — adoption rate chart | Frontend | `frontend/src/pages/Manager.tsx` |
| 51 | EM dashboard — average quality score trend | Frontend | `frontend/src/pages/Manager.tsx` |
| 52 | EM dashboard — skill gap heatmap (flags by category) | Frontend | `frontend/src/components/SkillHeatmap.tsx` |
| 53 | Consent modal — first-run, stores acknowledgement locally | Frontend | `frontend/src/components/ConsentModal.tsx` |
| 54 | AWS CDK stacks — VPC, RDS, ECS, Secrets, CloudFront | DevOps | `infra/` |
| 55 | GitHub Actions CI — test + lint on PR | DevOps | `.github/workflows/` |
| 56 | GitHub Actions CD — deploy to ECS on merge to main | DevOps | `.github/workflows/` |
| 57 | `scripts/seed_data.py` — 5 developers × 10 sessions of fake data | Backend | `scripts/` |
| 58 | Playwright smoke tests — developer and manager routes | Frontend | `frontend/e2e/` |
| 59 | Internal rollout — 5 engineers set up and use for real | All | — |
| 60 | Feedback collection — 1:1 interviews + async notes | Product | `docs/feedback/` |
| 61 | `docs/demo.md` — walkthrough script for stakeholder demo | Product | `docs/` |

#### Acceptance Criteria (Week 8 gate — MVP Done)

- [ ] 5 engineers each complete 3 real sessions captured end-to-end
- [ ] EM dashboard shows real (not seeded) team data
- [ ] Consent modal shown and acknowledged by all 5 pilot users
- [ ] All CI checks pass on `main`
- [ ] Deployed to AWS ap-south-1, reachable at `promptlens.think41.internal`
- [ ] Privacy test suite (`test_privacy.py`) passes in CI

---

## Definition of Done

A session is "fully captured" when all 4 are true:
1. Prompt + quality score stored in Postgres `turns` table
2. Accept/reject events stored in `tool_events` table linked to the session
3. Session visible in developer mirror within 60 seconds of session end
4. Session contributes to team aggregate after the next nightly job

The MVP is "done" when 5 internal engineers each have 3 sessions satisfying all 4 conditions.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| OTel hook spans unstable (beta feature) | Medium | High | Implement capture via hooks only first; OTel spans are enhancement not dependency |
| Developer trust / adoption resistance | High | High | Lead with private mirror; trivially easy opt-out; no manager can see individual data |
| Redaction misses PII in edge cases | Medium | Critical | Conservative: hash > delete; adversarial test set for redactor; periodic manual audit |
| Celery/Redis adds operational complexity | Low | Medium | Start without Celery for POC (synchronous scoring OK for 2 devs); add queue at Week 3 |
| Langfuse Cloud data residency concern | Medium | Medium | Raw prompt text never sent to Langfuse (only hashed); revisit self-host before prod rollout |
| AWS CDK unfamiliar to team | Low | Low | Python CDK matches backend stack; good docs; start with minimal stack |
| managed-settings.json delivery (no MDM) | Medium | Medium | `setup.sh` covers POC; document MDM path (Jamf/Intune) for future client rollout |

---

## File Creation Order (Recommended)

Start here to avoid blocked dependencies:

```
Week 1, Day 1–2:
  docs/privacy-contract.md     ← get EM sign-off before writing any data code
  docs/hook-spec.md            ← contract between hook scripts and backend

Week 1, Day 3–5:
  hooks/on_prompt.py           ← simplest hook first; no DB dependency
  hooks/on_tool.py
  hooks/on_session.py
  .claude/settings.json

Week 2, Day 1–3:
  backend/app/schemas/ingest.py   ← Pydantic schemas; no DB yet
  backend/app/db/models.py        ← SQLAlchemy models
  backend/app/db/migrations/      ← Alembic initial migration

Week 2, Day 4–5:
  backend/app/api/ingest.py       ← routes depend on schemas + models
  backend/app/api/health.py
  docker-compose.yml
  scripts/setup.sh
```

---

## How to Use This Document

- Update task checkboxes as work completes.
- Add blockers as bullet points under the relevant task.
- Every sprint starts with a re-read of the acceptance criteria — if a criterion is ambiguous, resolve it in writing here before coding starts.
- Any change to the privacy contract requires EM sign-off and a note in `docs/privacy-contract.md`.

# PromptLens — Architecture

## System Diagram

```
╔══════════════════════════════════════════════════════════════════╗
║  DEVELOPER MACHINE                                               ║
║                                                                  ║
║  ┌─────────────────────┐   OTLP gRPC    ┌──────────────────┐    ║
║  │  Claude Code CLI    │ ─────────────▶ │  OTel Collector  │    ║
║  │  (built-in OTel)    │                │  (redact+route)  │    ║
║  └─────────────────────┘                └────────┬─────────┘    ║
║           │                                      │              ║
║           │  Hook events (stdin/stdout)           │ OTLP HTTP   ║
║           ▼                                      │              ║
║  ┌─────────────────────┐                         │              ║
║  │   Hook Scripts      │ ──── async POST ────────┘              ║
║  │   on_prompt.py      │  (fire-and-forget)                     ║
║  │   on_tool.py        │                                        ║
║  │   on_session.py     │                                        ║
║  └─────────────────────┘                                        ║
╚══════════════════════════════════════════════════════════════════╝
                              │
                    HTTPS / OTLP HTTP
                              │
                              ▼
╔══════════════════════════════════════════════════════════════════╗
║  AWS (ECS Fargate)                                               ║
║                                                                  ║
║  ┌──────────────────────────────────────────────────────────┐   ║
║  │  FastAPI Backend                                         │   ║
║  │                                                          │   ║
║  │  POST /ingest/events       (hook events — no auth)       │   ║
║  │  POST /ingest/sessions     (session boundaries)          │   ║
║  │  GET  /sessions/:id        (developer — own data only)   │   ║
║  │  GET  /sessions/trends     (developer — own trends)      │   ║
║  │  GET  /team/trends         (manager — aggregated only)   │   ║
║  │  GET  /team/flags          (manager — counts only)       │   ║
║  │  GET  /team/summary        (manager — health card)       │   ║
║  └─────────────────┬────────────────────────────────────────┘   ║
║                    │                                             ║
║         ┌──────────┴──────────┐                                 ║
║         │                     │                                  ║
║         ▼                     ▼                                  ║
║  ┌────────────┐       ┌──────────────┐                          ║
║  │ PostgreSQL │       │    Redis     │                          ║
║  │ (AWS RDS)  │       │ (task queue) │                          ║
║  └────────────┘       └──────┬───────┘                          ║
║                               │                                  ║
║                               ▼                                  ║
║                       ┌──────────────┐                          ║
║                       │    Celery    │                          ║
║                       │   Workers    │                          ║
║                       │              │                          ║
║                       │ • score_turn │                          ║
║                       │ • aggregate  │                          ║
║                       │ • digest     │                          ║
║                       └──────────────┘                          ║
╚══════════════════════════════════════════════════════════════════╝
                              │
                    Langfuse SDK + OTLP
                              │
                              ▼
                    ┌──────────────────┐
                    │  Langfuse Cloud  │
                    │  (session replay │
                    │   + eval UI)     │
                    └──────────────────┘

                              +

╔══════════════════════════════════════════════════════════════════╗
║  React Frontend (AWS S3 + CloudFront)                           ║
║                                                                  ║
║  /developer  →  Personal mirror (own sessions only)             ║
║  /manager    →  Team health dashboard (aggregated only)         ║
╚══════════════════════════════════════════════════════════════════╝
```

---

## Component Breakdown

### 1. Claude Code — Native OTel Spans

Claude Code emits these spans automatically. No code required — just env vars.

| Span name                  | Key attributes                                    | PromptLens use             |
|----------------------------|---------------------------------------------------|----------------------------|
| `claude_code.interaction`  | `input`, `output`, `session.id`                   | Prompt + response per turn |
| `claude_code.llm_request`  | `model`, `latency_ms`, `tokens.input/output`      | Cost + latency tracking    |
| `claude_code.tool`         | `tool.name`, `tool.input`, `tool.output`, `allowed` | Accept / reject decisions |
| `claude_code.hook`         | `hook.name`, `exit_code`                          | Hook execution tracing     |

Enabled by:
```
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
ENABLE_BETA_TRACING_DETAILED=1
BETA_TRACING_ENDPOINT=http://localhost:4317
```

---

### 2. Hook Scripts

Three scripts wired into `.claude/settings.json`. Each reads JSON from stdin, writes `{"decision":"continue"}` to stdout. All network calls are async (fire-and-forget) — a dead backend never slows Claude Code.

| Hook file       | Trigger              | Captures                                      |
|-----------------|----------------------|-----------------------------------------------|
| `on_prompt.py`  | `UserPromptSubmit`   | Prompt text (redacted), turn index, quality pre-score |
| `on_tool.py`    | `PostToolUse`        | Tool name, accept/reject, streak counter, sensitive path flag |
| `on_session.py` | `SessionStart`/`Stop`| Session ID, start/end timestamps, turn count  |

**Redaction happens inside the hook, before the HTTP call.** Nothing leaves the machine unredacted.

**PII patterns stripped:**
- Email addresses → `[EMAIL]`
- IP addresses → `[IP]`
- `key=value` pairs for password/secret/token → `key=[REDACTED]`
- Bearer tokens → `[REDACTED]`
- Strings matching API key patterns (20+ uppercase chars) → `[KEY]`

---

### 3. OTel Collector Pipeline

Runs as a Docker container locally (and as an ECS sidecar in production). Receives spans from Claude Code, applies a second redaction pass at the attribute level, adds team metadata, and fans out to two destinations.

```
OTel Collector Pipeline:

RECEIVE (OTLP gRPC :4317 + HTTP :4318)
    │
    ├─ processors:
    │    memory_limiter    → prevents OOM on busy machines
    │    attributes/redact → strips user.email, user.name, hashes file paths
    │    resource/team     → injects team.id from env var
    │    batch             → buffers for efficiency
    │
    ├─ exporter → PromptLens Backend (OTLP HTTP)
    └─ exporter → Langfuse Cloud (OTLP HTTP)
```

---

### 4. FastAPI Backend

Async Python service. Two logical groups of routes:

**Ingest group** (no auth — hook scripts POST here):
- `POST /ingest/events` — receives prompt and tool events from hooks
- `POST /ingest/sessions` — receives session start/end boundaries

**Read group** (JWT auth — role-scoped):
- Developer routes → always filtered by `developer_id` from JWT
- Manager routes → always aggregate queries; `developer_id` never appears in response

**Async scoring**: ingest endpoints write raw data and return `202` immediately. A Celery task scores the turn in the background. This keeps ingest latency under 50ms regardless of evaluator complexity.

---

### 5. Evaluator Chain

Evaluators are pure functions: `(prompt_text, context) → EvalResult(score, flags, hints)`.

Run order and weights for POC (rule-based, no LLM calls):

```
Input prompt
    │
    ├── LengthEvaluator     (weight 0.10)
    │   score=0 if < 10 chars  → flag: too_short
    │
    ├── VaguenessEvaluator  (weight 0.40)
    │   counts vague phrases ("fix it", "make it work", "help me")
    │   score degrades linearly with hit count  → flag: vague_prompt
    │
    ├── ContextEvaluator    (weight 0.40)
    │   looks for code signals (def, class, error:, ```, line N)
    │   score=0.2 if no signals found  → flag: missing_context
    │
    └── SecurityEvaluator   (weight 0.10)
        checks tool-call file paths against sensitive patterns
        (.env, .pem, secrets/, id_rsa)  → flag: sensitive_file_weak_prompt

Final score = weighted sum (0.0 – 1.0)
Hint threshold = 0.4 → shown to developer in terminal
```

v2 (post-POC): LLM-judge evaluators via Langfuse eval templates.

---

### 6. PostgreSQL Schema (Logical)

Three core tables. Privacy rules are enforced at the query layer, not just the application layer.

**`sessions`** — one row per Claude Code session
- Keyed on `session_id` (Claude's own ID)
- `developer_id` = `SHA-256(machine_uuid)` — never a name or email
- `quality_score` = aggregate of all turns (computed after session ends)
- `flags` = array of fired flag names for the session

**`turns`** — one row per prompt/response turn
- Foreign key to `sessions`
- `prompt_hash` = SHA-256 of redacted prompt (developer can look up their own; team cannot)
- `prompt_chars` = length only (no content stored server-side)
- `quality_score` + `flags` per turn

**`tool_events`** — one row per tool call
- Foreign key to `sessions`
- `allowed` = accept/reject boolean
- `accept_streak` = streak at time of event (for pattern detection)
- `sensitive_path` = boolean (path pattern matched)

**`team_patterns`** — nightly aggregation output
- No `developer_id` column exists in this table by design
- `pattern` = JSONB blob of anonymised signals for the week
- Used by `/team/patterns` endpoint

---

### 7. AWS Deployment Topology

```
Region: ap-south-1 (Mumbai) — close to Think41 Bangalore

VPC
├── Public subnets
│   ├── ALB (Application Load Balancer)
│   └── NAT Gateway
│
└── Private subnets
    ├── ECS Fargate cluster
    │   ├── backend service   (FastAPI, 2 tasks min)
    │   ├── worker service    (Celery, 2 tasks min)
    │   └── collector service (otelcol-contrib, 1 task)
    │
    ├── RDS PostgreSQL 16    (Multi-AZ for prod, single for POC)
    └── ElastiCache Redis    (single node for POC)

S3 + CloudFront → React frontend (static)
Route 53        → promptlens.think41.internal (private hosted zone)
Secrets Manager → all secrets (DATABASE_URL, LANGFUSE keys, JWT_SECRET)
ECR             → Docker image registry
GitHub Actions  → CI/CD with OIDC (no long-lived AWS keys)
```

---

### 8. Role-Based Access

| Role         | JWT claim  | Can query                              | Cannot query              |
|--------------|------------|----------------------------------------|---------------------------|
| `developer`  | own ID     | Own sessions, turns, tools, trends     | Any other developer's data |
| `tech_lead`  | team ID    | Anonymised patterns, team digest       | Individual developer data  |
| `manager`    | team ID    | Team aggregates, health summary        | Any individual data        |

Manager and tech_lead queries enforce this at the SQL level (GROUP BY without developer_id) — not just application filtering.

---

## Architecture Decision Records (ADRs)

### ADR-001: FastAPI over Django
**Decision**: FastAPI  
**Reason**: Async-native (matches fire-and-forget ingest pattern); Pydantic validation built in; OpenAPI docs free; lighter than Django for an API-only service.  
**Trade-off**: No built-in admin UI (acceptable — we have Langfuse and a custom frontend).

### ADR-002: Celery + Redis for async scoring
**Decision**: Celery workers backed by Redis  
**Reason**: Ingest endpoints must return in < 50ms. Evaluator chain (especially v2 LLM judges) can take 1–3 seconds. Celery decouples this cleanly.  
**Trade-off**: Operational complexity of a task queue. Acceptable because Redis is already needed for other caching.

### ADR-003: AWS ap-south-1 for POC
**Decision**: Mumbai region  
**Reason**: Lowest latency to Think41 Bangalore; data residency within India.  
**Trade-off**: Some AWS services have slightly less availability than us-east-1. Acceptable for internal tooling.

### ADR-004: Langfuse Cloud for POC, self-host for prod
**Decision**: Cloud now, self-hosted later  
**Reason**: Self-hosting Langfuse adds operational overhead that would delay the POC. Cloud has a generous free tier. Migration path to self-host is straightforward (same SDK, different endpoint).  
**Trade-off**: Session trace data leaves Think41 infra during POC. Acceptable with data minimisation (no raw prompt text in traces — only hashed).

### ADR-005: SHA-256 developer ID, irreversible
**Decision**: `developer_id = SHA-256(machine_uuid)` with no lookup table  
**Reason**: Prevents accidental or deliberate de-anonymisation. If the lookup table doesn't exist, there's no social engineering or legal compulsion that can expose it.  
**Trade-off**: Developers lose their history if they change machines. Acceptable for v1.

### ADR-006: Hook scripts in Python, not shell
**Decision**: Python 3.11  
**Reason**: Available on all dev machines (Claude Code requires it); easier to write robust JSON parsing, async HTTP, and regex redaction in Python than shell.  
**Trade-off**: Slightly slower cold start than a compiled binary. Measured at < 80ms — acceptable.

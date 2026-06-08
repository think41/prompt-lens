# PromptLens — Tech Stack

## Decisions Summary

All decisions are recorded as ADRs in `ARCHITECTURE.md`.
This file is the quick-reference version.

---

## Confirmed Stack

| Layer | Technology | Version | Notes |
|-------|-----------|---------|-------|
| **Hook scripts** | Python | 3.11+ | Runs on developer machines alongside Claude Code |
| **Backend framework** | FastAPI | 0.111+ | Async-native; Pydantic built-in; OpenAPI free |
| **Task queue** | Celery | 5.4+ | Async scoring + weekly digest jobs |
| **Queue broker** | Redis | 7.x | Celery backend; also session cache |
| **ORM** | SQLAlchemy | 2.x (async) | Pairs with FastAPI async; Alembic migrations |
| **Schema validation** | Pydantic | v2 | FastAPI dependency; strict mode for ingest |
| **Migrations** | Alembic | latest | SQLAlchemy-native; version-controlled |
| **Database** | PostgreSQL | 16 | AWS RDS; JSONB for patterns; GIN indexes on flags arrays |
| **Trace backend** | Langfuse Cloud | — | Session replay + eval UI; self-host in prod |
| **OTel Collector** | otelcol-contrib | 0.99+ | Custom redaction processor; OTLP fan-out |
| **Frontend** | React | 18 | Team knows it |
| **Frontend build** | Vite | 5.x | Faster than CRA; native ESM |
| **Frontend styling** | Tailwind CSS | 3.x | Utility-first; fast iteration |
| **Frontend routing** | React Router | 6.x | Standard |
| **Charts** | Recharts | 2.x | React-native; enough for MVP |
| **Cloud** | AWS | — | ap-south-1 (Mumbai) for latency to Bangalore |
| **Compute** | ECS Fargate | — | No cluster management; per-task billing |
| **Database hosting** | RDS PostgreSQL | — | Multi-AZ in prod; single for POC |
| **Cache hosting** | ElastiCache Redis | — | Single node for POC |
| **Static hosting** | S3 + CloudFront | — | React bundle |
| **IaC** | AWS CDK (Python) | 2.x | Same language as backend |
| **CI/CD** | GitHub Actions | — | OIDC to AWS; no long-lived keys |
| **Secrets** | AWS Secrets Manager | — | Injected as env vars into ECS tasks |
| **Container registry** | ECR | — | Private; auto-linked to ECS |
| **DNS** | Route 53 (private) | — | `promptlens.think41.internal` |
| **Python dependency mgmt** | pip + `requirements.txt` | — | Keep simple for POC; consider Poetry later |
| **Linting** | Ruff | latest | Fast Python linter; replaces flake8 + isort |
| **Formatting** | Black | latest | Zero-config |
| **Type checking** | mypy | latest | Strict mode on `app/` |
| **Testing** | pytest + httpx | latest | httpx for async FastAPI test client |
| **E2E tests** | Playwright | latest | Smoke tests for dashboard routes |

---

## What We Evaluated and Rejected

| Option | Rejected because |
|--------|-----------------|
| Django | Too heavy for API-only service; sync-first; slower iteration |
| Go | Team not familiar; would slow POC |
| Node/TypeScript backend | Python chosen for team familiarity and hook script consistency |
| Self-hosted Langfuse (now) | Adds operational overhead during POC; easy to migrate later |
| DynamoDB | Aggregation queries need SQL; JSONB pattern storage needs Postgres |
| MongoDB | PostgreSQL covers all use cases; team more familiar with relational |
| Kubernetes (now) | ECS Fargate is enough for POC; k8s path is open for scale |
| Terraform | CDK (Python) preferred; same language as backend reduces context switch |
| Vue/Nuxt | Team familiarity with React; no advantage for this use case |

---

## Local Dev Requirements (Developer Machine)

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | `brew install python@3.11` or pyenv |
| Docker Desktop | latest | docker.com/products/docker-desktop |
| Node.js | 20 LTS | `brew install node` or nvm |
| AWS CLI | v2 | `brew install awscli` |
| AWS CDK | 2.x | `npm install -g aws-cdk` |
| Claude Code CLI | latest | `npm install -g @anthropic-ai/claude-code` |

`scripts/setup.sh` verifies all of these are present and at the right version.

---

## Ports (Local Dev)

| Service | Port |
|---------|------|
| FastAPI backend | 8000 |
| OTel Collector gRPC | 4317 |
| OTel Collector HTTP | 4318 |
| React frontend (Vite) | 5173 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| Langfuse (if self-hosted) | 3000 |
| OTel Collector metrics | 8888 |
| OTel Collector health | 13133 |

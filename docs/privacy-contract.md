# PromptLens — Privacy Contract

**Version**: 1.0  
**Status**: Draft — requires EM sign-off before any data code is written  
**Last updated**: June 2026

---

## Purpose

This document defines the non-negotiable data handling rules for PromptLens.
Any code, query, or configuration change that violates these rules is a blocker
and must not be merged.

These rules exist because PromptLens handles sensitive developer behaviour data.
Developer trust is the product's most important asset. If developers don't
trust the system, they will not use it, and the product fails.

---

## Rules

### Rule 1 — No names or emails, ever

No developer name, email address, GitHub username, employee ID, or any other
directly identifying string is stored anywhere in the PromptLens database,
log files, or telemetry backends.

This applies to:
- Postgres (all tables)
- Langfuse traces
- OTel Collector logs
- Slack digest messages
- GitHub PR tab content

**Verification**: `grep -r "email\|name\|github" backend/app/db/models.py` must return no columns on these models.

---

### Rule 2 — developer_id is irreversible

The `developer_id` stored server-side is always `SHA-256(machine_uuid)`.

There is no lookup table mapping `developer_id` to a real identity.
There is no API endpoint that accepts a developer_id and returns identifying information.

This is intentional. If the lookup table doesn't exist, it cannot be subpoenaed,
breached, or misused.

**Implication**: developers lose their history if they change machines. This is
an acceptable trade-off for v1.

---

### Rule 3 — Redaction before transmission

All hook scripts must redact PII from prompt text **before** any network call.
The redacted text itself is not transmitted — only a SHA-256 hash of the original
and the character count are sent to the backend.

The redaction must cover at minimum:
- Email addresses
- IP addresses
- `key=value` pairs for password, secret, token, api_key
- Bearer tokens
- Strings matching API key patterns (20+ uppercase alphanumeric chars)

**Verification**: `pytest hooks/tests/test_redaction.py` must pass with the
adversarial test set (see `hooks/tests/fixtures/adversarial_prompts.json`).

---

### Rule 4 — Manager endpoints never return individual data

Any API endpoint accessible to the `manager` or `tech_lead` role must:
- Return only aggregated data (COUNT, AVG, SUM grouped by day/week)
- Never include a `developer_id` field in any response row
- Never include any field from which a `developer_id` could be inferred

**Verification**: `pytest backend/tests/test_privacy.py::test_manager_endpoints_contain_no_developer_id` must pass in CI.

This test makes real API calls with a manager JWT and asserts that no response
body at any depth contains the string `"developer_id"` or any known test
developer_id value.

---

### Rule 5 — Opt-in consent before first capture

The PromptLens hooks must not transmit any data until the developer has
seen and acknowledged the consent screen.

The consent screen must explain:
- What is captured (prompt length and hash, tool accept/reject, session boundaries)
- What is NOT captured (prompt text, file contents, your name)
- Who can see what (you: your own scores; tech lead: anonymised patterns; manager: team aggregates)
- How to opt out (one command; hooks go silent immediately)

Consent acknowledgement is stored locally (not server-side) in `~/.claude/promptlens_consent`.

---

### Rule 6 — Opt-out is immediate and complete

Running `promptlens opt-out` (or deleting `~/.claude/promptlens_consent`) must:
- Stop all hook transmissions immediately (next session)
- Delete all locally cached session files and streak files
- NOT delete server-side data (developer_id is anonymous; there is no way to
  identify which rows belong to the opting-out developer)

---

### Rule 7 — No content in Langfuse

Langfuse receives OTel spans for session replay and evaluation. It must never
receive raw prompt text or raw file content.

The Langfuse exporter in the OTel Collector must hash or delete the `input`
and `output` attributes from `claude_code.interaction` spans before forwarding.

---

## Sign-off

This contract must be reviewed and signed off by:

| Role | Name | Date |
|------|------|------|
| Engineering Manager | | |
| Backend Lead | | |
| Frontend Lead | | |

Changes to this document require a new sign-off from all three.

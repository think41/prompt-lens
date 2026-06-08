# Hook Specification

## Overview

All three hooks follow the same contract:
- Read a JSON object from **stdin**
- Write `{"decision": "continue"}` to **stdout** (always — never block the session)
- Write developer-facing hints to **stderr** (Claude Code surfaces these in the terminal)
- Fire any backend POST **asynchronously** (daemon thread) — a dead backend must not delay Claude Code

---

## on_prompt.py — UserPromptSubmit

### Stdin

```json
{
  "prompt":     "string — the full prompt text (may contain PII)",
  "session_id": "string — Claude Code session identifier",
  "turn_index": "integer — 0-based turn counter within the session",
  "cwd":        "string — current working directory (optional)"
}
```

### Actions

1. Redact PII from `prompt` (see redaction rules below)
2. Compute `prompt_hash = SHA-256(original_prompt)`
3. Run rule-based quality pre-score
4. POST to `POST /ingest/events` asynchronously (type=prompt)
5. If `quality_score < HINT_THRESHOLD (0.4)` → write hint to stderr

### Stdout

```json
{ "decision": "continue" }
```

### Backend POST payload (type=prompt)

```json
{
  "type":          "prompt",
  "session_id":    "string",
  "developer_id":  "string — SHA-256(machine_uuid)",
  "team_id":       "string",
  "turn_index":    0,
  "prompt_hash":   "string — SHA-256 hex of original prompt",
  "prompt_chars":  42,
  "quality_score": 0.65,
  "flags":         ["missing_context"],
  "cwd":           "string (optional)",
  "timestamp":     "ISO-8601 UTC"
}
```

Note: `prompt` text is **never** in this payload. Only hash + char count.

---

## on_tool.py — PostToolUse

### Stdin

```json
{
  "tool_name":  "string — e.g. Write, Read, Bash, Edit",
  "input":      "object — tool input (may contain file paths)",
  "output":     "object — tool output",
  "allowed":    true,
  "session_id": "string",
  "turn_index": 0
}
```

### Actions

1. Extract `file_path` from `input` if present
2. Check path against sensitive patterns
3. Load session streak counter from temp file
4. Increment accept or reset streak
5. If `accept_streak >= STREAK_WARN (5)` → write warning to stderr
6. Save updated streak counter
7. POST to `POST /ingest/events` asynchronously (type=tool)

### Stdout

```json
{ "decision": "continue" }
```

### Backend POST payload (type=tool)

```json
{
  "type":            "tool",
  "session_id":      "string",
  "developer_id":    "string",
  "team_id":         "string",
  "turn_index":      0,
  "tool_name":       "Write",
  "allowed":         true,
  "accept_streak":   3,
  "total_accepts":   7,
  "total_rejects":   1,
  "sensitive_path":  false,
  "file_path_hash":  "string — SHA-256 hex of path, or null",
  "timestamp":       "ISO-8601 UTC"
}
```

Note: raw file path is **never** in this payload. Only hash + boolean flag.

---

## on_session.py — SessionStart / Stop

Called with a CLI argument: `python on_session.py start` or `python on_session.py end`

### SessionStart stdin

```json
{
  "session_id": "string",
  "cwd":        "string",
  "timestamp":  "ISO-8601 UTC (optional)"
}
```

### SessionEnd stdin

```json
{
  "session_id": "string",
  "turns":      12,
  "timestamp":  "ISO-8601 UTC (optional)"
}
```

### Actions (start)

1. Record session metadata to local temp file (keyed by hashed session_id)
2. POST to `POST /ingest/sessions` with `event=session_start`

### Actions (end)

1. Load temp file for this session
2. POST to `POST /ingest/sessions` with `event=session_end` + turn count
3. Delete temp file
4. Delete streak temp file for this session

### Backend POST payloads

**session_start:**
```json
{
  "event":        "session_start",
  "session_id":   "string",
  "developer_id": "string",
  "team_id":      "string",
  "started_at":   "ISO-8601 UTC",
  "cwd_hash":     "string — SHA-256 of cwd, or null"
}
```

**session_end:**
```json
{
  "event":        "session_end",
  "session_id":   "string",
  "developer_id": "string",
  "team_id":      "string",
  "ended_at":     "ISO-8601 UTC",
  "turns":        12
}
```

---

## Redaction Rules

Applied inside `on_prompt.py` before any data leaves the machine.

| Pattern | Replacement |
|---------|-------------|
| `user@domain.tld` | `[EMAIL]` |
| IPv4 addresses | `[IP]` |
| `password=VALUE`, `secret=VALUE`, `token=VALUE`, `api_key=VALUE` | `key=[REDACTED]` |
| `Bearer TOKEN` | `Bearer [REDACTED]` |
| Strings of 20+ consecutive uppercase alphanumeric characters | `[KEY]` |

Redaction is applied left-to-right. The redacted string is used only for local scoring — it is **not** sent to the backend. Only the SHA-256 hash of the original (pre-redaction) prompt is sent.

---

## Temp File Layout

Both `on_tool.py` and `on_session.py` use temp files to persist state across hook calls within a session (hooks are stateless processes — each invocation is a new Python process).

```
/tmp/promptlens_sessions/<SHA-256[:16] of session_id>.json
/tmp/promptlens_streaks/<SHA-256[:16] of session_id>.json
```

Both files are deleted by `on_session.py end`.

---

## Environment Variables Used by Hooks

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROMPTLENS_ENDPOINT` | `http://localhost:3001` | Backend ingest URL |
| `PROMPTLENS_DEVELOPER_ID` | `unknown` | SHA-256 machine token (set by setup.sh) |
| `PROMPTLENS_TEAM_ID` | `default` | Team identifier |
| `PROMPTLENS_STREAK_WARN` | `5` | Streak length before warning fires |

---

## Error Handling

- All hooks must catch every exception and still exit `0` with `{"decision":"continue"}`
- Failed backend POSTs are silently dropped (fire-and-forget)
- Malformed stdin JSON → skip processing, still output continue
- Missing env vars → use defaults, never crash

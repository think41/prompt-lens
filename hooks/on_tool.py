#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = os.getenv("PROMPTLENS_ENDPOINT", "http://localhost:8000")
DEVELOPER_ID = os.getenv("PROMPTLENS_DEVELOPER_ID", "unknown")
TEAM_ID = os.getenv("PROMPTLENS_TEAM_ID", "default")
STREAK_WARN = int(os.getenv("PROMPTLENS_STREAK_WARN", "5"))

STREAK_DIR = Path("/tmp/promptlens_streaks")

_SENSITIVE = re.compile(
    r"(\.env|credentials|secrets?|id_rsa|\.pem|\.key|aws/credentials)",
    re.IGNORECASE,
)


def _streak_path(session_id: str) -> Path:
    STREAK_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    return STREAK_DIR / f"{key}.json"


def load_streak(session_id: str) -> dict:
    p = _streak_path(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {"accept_streak": 0, "total_accepts": 0, "total_rejects": 0}


def save_streak(session_id: str, state: dict) -> None:
    try:
        _streak_path(session_id).write_text(json.dumps(state))
    except Exception:
        pass


def post_async(payload: dict) -> None:
    def _post():
        try:
            import urllib.request
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{ENDPOINT}/ingest/events",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass

    t = threading.Thread(target=_post, daemon=True)
    t.start()
    t.join(timeout=0.1)


def main() -> None:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        print(json.dumps({"decision": "continue"}))
        return

    session_id = data.get("session_id", "")
    tool_name = data.get("tool_name", "")
    allowed = data.get("allowed", True)
    tool_input = data.get("input", {})

    file_path = tool_input.get("file_path") or tool_input.get("path")
    sensitive_path = bool(file_path and _SENSITIVE.search(file_path))
    file_path_hash = hashlib.sha256(file_path.encode()).hexdigest() if file_path else None

    streak = load_streak(session_id)
    if allowed:
        streak["accept_streak"] += 1
        streak["total_accepts"] += 1
    else:
        streak["accept_streak"] = 0
        streak["total_rejects"] += 1
    save_streak(session_id, streak)

    if streak["accept_streak"] >= STREAK_WARN:
        print(
            f"[PromptLens] {streak['accept_streak']} consecutive tool accepts — "
            "consider reviewing Claude's output more carefully.",
            file=sys.stderr,
        )

    payload = {
        "type": "tool",
        "session_id": session_id,
        "developer_id": DEVELOPER_ID,
        "team_id": TEAM_ID,
        "turn_index": data.get("turn_index", 0),
        "tool_name": tool_name,
        "allowed": allowed,
        "accept_streak": streak["accept_streak"],
        "total_accepts": streak["total_accepts"],
        "total_rejects": streak["total_rejects"],
        "sensitive_path": sensitive_path,
        "file_path_hash": file_path_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    post_async(payload)


if __name__ == "__main__":
    main()

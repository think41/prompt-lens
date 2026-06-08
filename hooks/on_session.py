#!/usr/bin/env python3
import hashlib
import json
import os
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = os.getenv("PROMPTLENS_ENDPOINT", "http://localhost:8000")
DEVELOPER_ID = os.getenv("PROMPTLENS_DEVELOPER_ID", "")
TEAM_ID = os.getenv("PROMPTLENS_TEAM_ID", "default")

SESSION_DIR = Path("/tmp/promptlens_sessions")
STREAK_DIR = Path("/tmp/promptlens_streaks")


def _session_path(session_id: str) -> Path:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    return SESSION_DIR / f"{key}.json"


def post_async(url: str, payload: dict) -> None:
    def _post():
        try:
            import urllib.request
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                url,
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


def handle_start(data: dict) -> None:
    session_id = data.get("session_id", "")
    cwd = data.get("cwd")
    started_at = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

    meta = {"session_id": session_id, "started_at": started_at}
    try:
        _session_path(session_id).write_text(json.dumps(meta))
    except Exception:
        pass

    payload = {
        "event": "session_start",
        "session_id": session_id,
        "developer_id": DEVELOPER_ID,
        "team_id": TEAM_ID,
        "started_at": started_at,
        "cwd_hash": hashlib.sha256(cwd.encode()).hexdigest() if cwd else None,
    }
    post_async(f"{ENDPOINT}/ingest/sessions", payload)


def handle_end(data: dict) -> None:
    session_id = data.get("session_id", "")
    turns = data.get("turns", 0)
    ended_at = data.get("timestamp") or datetime.now(timezone.utc).isoformat()

    payload = {
        "event": "session_end",
        "session_id": session_id,
        "developer_id": DEVELOPER_ID,
        "team_id": TEAM_ID,
        "ended_at": ended_at,
        "turns": turns,
    }
    post_async(f"{ENDPOINT}/ingest/sessions", payload)

    for d, key in [(SESSION_DIR, "sessions"), (STREAK_DIR, "streaks")]:
        p = d / f"{hashlib.sha256(session_id.encode()).hexdigest()[:16]}.json"
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass


def main() -> None:
    if not DEVELOPER_ID:
        return  # Not configured — silently skip

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}

    # event type from stdin (preferred) or CLI arg for compatibility
    event = data.get("event") or (sys.argv[1] if len(sys.argv) > 1 else "start")

    try:
        if event in ("start", "session_start"):
            handle_start(data)
        elif event in ("end", "stop", "session_end"):
            handle_end(data)
    except Exception:
        pass



if __name__ == "__main__":
    main()

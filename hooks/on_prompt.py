#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone

ENDPOINT = os.getenv("PROMPTLENS_ENDPOINT", "http://localhost:8000")
DEVELOPER_ID = os.getenv("PROMPTLENS_DEVELOPER_ID", "unknown")
TEAM_ID = os.getenv("PROMPTLENS_TEAM_ID", "default")
HINT_THRESHOLD = float(os.getenv("PROMPTLENS_HINT_THRESHOLD", "0.4"))

_REDACT_PATTERNS = [
    (re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"), "[EMAIL]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[IP]"),
    (re.compile(r"(?i)(password|secret|token|api_key)\s*=\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)Bearer\s+\S+"), "Bearer [REDACTED]"),
    (re.compile(r"[A-Z0-9]{20,}"), "[KEY]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def score(prompt: str) -> tuple[float, list[str]]:
    flags = []
    s = 1.0

    if len(prompt) < 20:
        flags.append("too_short")
        s -= 0.4
    if len(prompt) > 2000:
        flags.append("too_long")
        s -= 0.1

    vague = ["fix it", "make it work", "do it", "help", "update this"]
    if any(v in prompt.lower() for v in vague):
        flags.append("vague")
        s -= 0.3

    code_signals = ["```", "def ", "class ", "import ", "function ", "const ", "error:"]
    has_context = any(sig in prompt for sig in code_signals)
    if not has_context and len(prompt) > 30:
        flags.append("missing_context")
        s -= 0.2

    return max(0.0, round(s, 2)), flags


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
        return

    prompt = data.get("prompt", "")
    session_id = data.get("session_id", "")
    turn_index = data.get("turn_index", 0)
    cwd = data.get("cwd")

    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    prompt_chars = len(prompt)
    quality_score, flags = score(redact(prompt))

    payload = {
        "type": "prompt",
        "session_id": session_id,
        "developer_id": DEVELOPER_ID,
        "team_id": TEAM_ID,
        "turn_index": turn_index,
        "prompt_hash": prompt_hash,
        "prompt_chars": prompt_chars,
        "quality_score": quality_score,
        "flags": flags,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if cwd:
        payload["cwd"] = hashlib.sha256(cwd.encode()).hexdigest()

    post_async(payload)

    if quality_score < HINT_THRESHOLD:
        hints = {
            "too_short": "Prompt is very short — add more context.",
            "vague": "Vague prompt — describe the specific problem or goal.",
            "missing_context": "No code context detected — paste the relevant snippet.",
        }
        for flag in flags:
            if flag in hints:
                print(f"[PromptLens] {hints[flag]}", file=sys.stderr)



if __name__ == "__main__":
    main()

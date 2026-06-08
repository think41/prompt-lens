#!/usr/bin/env python3
import contextlib
import hashlib
import json
import os
import re
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

ENDPOINT = os.getenv("PROMPTLENS_ENDPOINT", "http://localhost:8000")
DEVELOPER_ID = os.getenv("PROMPTLENS_DEVELOPER_ID", "")
TEAM_ID = os.getenv("PROMPTLENS_TEAM_ID", "default")
HINT_THRESHOLD = float(os.getenv("PROMPTLENS_HINT_THRESHOLD", "0.4"))
PRIVACY_ENABLED = os.getenv("PRIVACY_ENABLED", "false").lower() not in ("false", "0", "no")

_SESSION_DIR = Path("/tmp/promptlens_sessions")

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


_SPECIFICITY_PATTERNS = [
    re.compile(r"\b\w{2,}\s*\("),  # func()
    re.compile(r"[/~][\w./\-]+\.\w{1,5}|\b\w+\.(py|ts|tsx|js|go|rs|java|yaml|json|md)\b"),
    re.compile(r"\bline\s*:?\s*\d+\b|L\d{1,5}\b|:\d{1,5}\b", re.IGNORECASE),
    re.compile(r"\b[a-z][a-z0-9]+_[a-z0-9_]+\b"),  # snake_case
    re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]+\b"),  # CamelCase
    re.compile(r"\b\w*(Error|Exception|Warning|Failure)\b"),
    re.compile(r"\bv?\d+\.\d+(\.\d+)?\b"),  # version numbers
    re.compile(r"\b\d{2,}\b"),  # specific numbers
]


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

    words = prompt.split()
    if len(words) >= 5:
        specificity_hits = sum(bool(p.search(prompt)) for p in _SPECIFICITY_PATTERNS)
        if specificity_hits < 1:
            flags.append("low_specificity")
            s -= 0.2

    return max(0.0, round(s, 2)), flags


def _load_session_meta(session_id: str, cwd: str | None) -> dict:
    """
    Return session meta written by on_session.py.
    If the file is missing (SessionStart wasn't captured), detect project info
    inline and write the file so subsequent turns don't re-detect.
    """
    import subprocess
    from urllib.parse import urlparse

    key = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    p = _SESSION_DIR / f"{key}.json"

    try:
        if p.exists():
            meta = json.loads(p.read_text())
            # Re-detect name/email if privacy was off when the file was written as null
            if not PRIVACY_ENABLED and (
                not meta.get("developer_name") or not meta.get("developer_email")
            ):
                try:
                    meta["developer_name"] = (
                        meta.get("developer_name")
                        or subprocess.check_output(
                            ["git", "config", "user.name"],
                            cwd=cwd or ".",
                            text=True,
                            stderr=subprocess.DEVNULL,
                            timeout=2,
                        ).strip()
                        or os.getenv("USER")
                        or os.getenv("USERNAME")
                    )
                except Exception:
                    meta["developer_name"] = (
                        meta.get("developer_name") or os.getenv("USER") or os.getenv("USERNAME")
                    )
                with contextlib.suppress(Exception):
                    meta["developer_email"] = (
                        meta.get("developer_email")
                        or subprocess.check_output(
                            ["git", "config", "user.email"],
                            cwd=cwd or ".",
                            text=True,
                            stderr=subprocess.DEVNULL,
                            timeout=2,
                        ).strip()
                    )
                p.write_text(json.dumps(meta))
            return meta
    except Exception:
        pass

    # SessionStart temp file missing — detect now
    def _remote_url() -> str | None:
        for remote in ("origin", "upstream"):
            try:
                url = subprocess.check_output(
                    ["git", "remote", "get-url", remote],
                    cwd=cwd or ".",
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                ).strip()
                if url:
                    return url
            except Exception:
                continue
        return None

    def _normalise(raw: str) -> str:
        url = raw.strip()
        if "@" in url and ":" in url and not url.startswith("http"):
            host_path = url.split("@", 1)[1]
            host, path = host_path.split(":", 1)
            url = f"https://{host}/{path}"
        return url.rstrip("/").removesuffix(".git")

    raw = _remote_url()
    project_url = project_name = developer_name = developer_email = None

    if raw:
        project_url = _normalise(raw)
        parsed = urlparse(project_url)
        parts = parsed.path.strip("/").split("/")
        project_name = parts[1] if len(parts) > 1 else (parts[0] if parts else None)

    if not project_name and cwd:
        # fallback: try manifest files then folder name
        root = Path(cwd)
        for fname, _key_name in [
            ("package.json", "name"),
            ("pyproject.toml", None),
            ("Cargo.toml", None),
        ]:
            try:
                if fname == "package.json":
                    import json as _j

                    project_name = _j.loads((root / fname).read_text()).get("name")
                else:
                    import re as _re

                    text = (root / fname).read_text()
                    m = _re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', text, _re.MULTILINE)
                    if m:
                        project_name = m.group(1)
                if project_name:
                    break
            except Exception:
                continue
        if not project_name:
            project_name = root.name

    if not PRIVACY_ENABLED:
        try:
            developer_name = (
                subprocess.check_output(
                    ["git", "config", "user.name"],
                    cwd=cwd or ".",
                    text=True,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                ).strip()
                or os.getenv("USER")
                or os.getenv("USERNAME")
            )
        except Exception:
            developer_name = os.getenv("USER") or os.getenv("USERNAME")
        with contextlib.suppress(Exception):
            developer_email = subprocess.check_output(
                ["git", "config", "user.email"],
                cwd=cwd or ".",
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).strip()

    # derive team_id from org in remote URL, fall back to env var
    _team_id = None
    if raw:
        from urllib.parse import urlparse as _up

        _parts = _up(project_url).path.strip("/").split("/") if project_url else []
        _team_id = _parts[0].lower() if _parts else None
    team_id = _team_id or TEAM_ID

    meta = {
        "session_id": session_id,
        "allowed": True,
        "team_id": team_id,
        "project_url": project_url,
        "project_name": project_name,
        "developer_name": developer_name,
        "developer_email": developer_email,
    }
    try:
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(meta))
    except Exception:
        pass
    return meta


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
    if not DEVELOPER_ID:
        return  # Not configured — silently skip (run setup.sh first)

    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        return

    prompt = data.get("prompt", "")
    session_id = data.get("session_id", "")
    turn_index = data.get("turn_index", 0)
    cwd = data.get("cwd")

    meta = _load_session_meta(session_id, cwd)
    if not meta.get("allowed", True):
        return

    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
    prompt_chars = len(prompt)
    scored_text = redact(prompt) if PRIVACY_ENABLED else prompt
    quality_score, flags = score(scored_text)

    payload = {
        "type": "prompt",
        "session_id": session_id,
        "developer_id": DEVELOPER_ID,
        "team_id": meta.get("team_id") or TEAM_ID,
        "turn_index": turn_index,
        "prompt_hash": prompt_hash,
        "prompt_chars": prompt_chars,
        "quality_score": quality_score,
        "flags": flags,
        "timestamp": datetime.now(UTC).isoformat(),
        "project_url": meta.get("project_url"),
        "project_name": meta.get("project_name"),
        "developer_name": meta.get("developer_name"),
        "developer_email": meta.get("developer_email"),
    }
    if not PRIVACY_ENABLED:
        payload["prompt_text"] = prompt
    if cwd:
        payload["cwd"] = cwd if not PRIVACY_ENABLED else hashlib.sha256(cwd.encode()).hexdigest()

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

#!/usr/bin/env python3
import contextlib
import hashlib
import json
import os
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

ENDPOINT = os.getenv("PROMPTLENS_ENDPOINT", "http://localhost:8000")
DEVELOPER_ID = os.getenv("PROMPTLENS_DEVELOPER_ID", "")
TEAM_ID = os.getenv("PROMPTLENS_TEAM_ID", "default")
PRIVACY_ENABLED = os.getenv("PRIVACY_ENABLED", "false").lower() not in ("false", "0", "no")

# Comma-separated list of GitHub/GitLab org names to capture.
# Empty = capture everything (useful when hooks are deployed per-project, not globally).
_raw_orgs = os.getenv("PROMPTLENS_ALLOWED_ORGS", "")
ALLOWED_ORGS: set[str] = {o.strip().lower() for o in _raw_orgs.split(",") if o.strip()}

SESSION_DIR = Path("/tmp/promptlens_sessions")
STREAK_DIR = Path("/tmp/promptlens_streaks")


def _session_path(session_id: str) -> Path:
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    return SESSION_DIR / f"{key}.json"


def _remote_url(cwd: str | None) -> str | None:
    """Return the raw git remote URL (origin, then upstream), or None."""
    import subprocess

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


def _normalise_url(raw: str) -> str:
    """Convert SSH git URL to HTTPS and strip .git suffix."""
    url = raw.strip()
    # SSH: git@github.com:Org/repo.git → https://github.com/Org/repo.git
    if "@" in url and ":" in url and not url.startswith("http"):
        host_path = url.split("@", 1)[1]
        host, path = host_path.split(":", 1)
        url = f"https://{host}/{path}"
    return url.rstrip("/").removesuffix(".git")


def _project_name_from_manifest(cwd: str | None) -> str | None:
    """Try to read project name from package.json / pyproject.toml / Cargo.toml."""
    if not cwd:
        return None
    root = Path(cwd)
    # package.json
    try:
        import json as _json

        pkg = _json.loads((root / "package.json").read_text())
        if name := pkg.get("name"):
            return name
    except Exception:
        pass
    # pyproject.toml
    try:
        import re

        text = (root / "pyproject.toml").read_text()
        m = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if m:
            return m.group(1)
    except Exception:
        pass
    # Cargo.toml
    try:
        import re

        text = (root / "Cargo.toml").read_text()
        m = re.search(r'^\s*name\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _detect_project(cwd: str | None) -> dict:
    """Return {org, project_url, project_name} from git remote or filesystem fallbacks."""
    from urllib.parse import urlparse

    raw = _remote_url(cwd)

    if raw:
        https_url = _normalise_url(raw)
        # parse org and repo from normalised HTTPS URL
        parsed = urlparse(https_url)
        parts = parsed.path.strip("/").split("/")
        org = parts[0].lower() if parts else None
        repo = parts[1] if len(parts) > 1 else None
        project_name = repo or (parts[0] if parts else None)
        return {"org": org, "project_url": https_url, "project_name": project_name}

    # No git remote — try manifest then folder name
    project_name = _project_name_from_manifest(cwd) or (Path(cwd).name if cwd else None)
    return {"org": None, "project_url": None, "project_name": project_name}


def _is_allowed(cwd: str | None) -> bool:
    """Return True if this session's repo belongs to an allowed org (or no filter is set)."""
    if not ALLOWED_ORGS:
        return True
    info = _detect_project(cwd)
    org = info.get("org")
    if org is None:
        return False  # no remote → not a known org → skip
    return org in ALLOWED_ORGS


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
    started_at = data.get("timestamp") or datetime.now(UTC).isoformat()

    project = _detect_project(cwd)
    allowed = not ALLOWED_ORGS or (project["org"] is not None and project["org"] in ALLOWED_ORGS)

    developer_name = None
    developer_email = None
    if not PRIVACY_ENABLED:
        import subprocess

        try:
            developer_name = (
                subprocess.check_output(
                    ["git", "config", "user.name"],
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
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).strip()

    team_id = project["org"] or TEAM_ID
    meta = {
        "session_id": session_id,
        "started_at": started_at,
        "allowed": allowed,
        "team_id": team_id,
        "project_url": project["project_url"],
        "project_name": project["project_name"],
        "developer_name": developer_name,
        "developer_email": developer_email,
    }
    with contextlib.suppress(Exception):
        _session_path(session_id).write_text(json.dumps(meta))

    if not allowed:
        return

    payload = {
        "event": "session_start",
        "session_id": session_id,
        "developer_id": DEVELOPER_ID,
        "developer_name": developer_name,
        "developer_email": developer_email,
        "team_id": project["org"] or TEAM_ID,
        "project_url": project["project_url"],
        "project_name": project["project_name"],
        "started_at": started_at,
        "cwd_hash": hashlib.sha256(cwd.encode()).hexdigest() if (cwd and PRIVACY_ENABLED) else None,
        "cwd": cwd if not PRIVACY_ENABLED else None,
    }
    post_async(f"{ENDPOINT}/ingest/sessions", payload)


def handle_end(data: dict) -> None:
    session_id = data.get("session_id", "")
    turns = data.get("turns", 0)
    ended_at = data.get("timestamp") or datetime.now(UTC).isoformat()

    payload = {
        "event": "session_end",
        "session_id": session_id,
        "developer_id": DEVELOPER_ID,
        "team_id": TEAM_ID,
        "ended_at": ended_at,
        "turns": turns,
    }
    post_async(f"{ENDPOINT}/ingest/sessions", payload)

    for d, _label in [(SESSION_DIR, "sessions"), (STREAK_DIR, "streaks")]:
        p = d / f"{hashlib.sha256(session_id.encode()).hexdigest()[:16]}.json"
        with contextlib.suppress(Exception):
            p.unlink(missing_ok=True)


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

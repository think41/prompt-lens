import logging

log = logging.getLogger(__name__)

_client = None


def _get_client():
    """Lazy singleton — one Langfuse client per worker process."""
    global _client
    if _client is not None:
        return _client
    try:
        from langfuse import Langfuse

        from ..core.config import settings

        if not settings.langfuse_secret_key:
            return None
        _client = Langfuse(
            secret_key=settings.langfuse_secret_key,
            public_key=settings.langfuse_public_key,
            host=settings.langfuse_host,
        )
        log.info("Langfuse client initialised → %s", settings.langfuse_host)
        return _client
    except Exception:
        log.debug("Langfuse client init failed (non-fatal)", exc_info=True)
        return None


def send_turn_trace(
    session_id: str,
    turn_index: int,
    quality_score: float,
    flags: list[str],
    prompt_chars: int,
    developer_id: str | None = None,
    team_id: str | None = None,
    project_name: str | None = None,
) -> None:
    """Send a scored turn to Langfuse as a trace + quality score.

    Fire-and-forget — never raises.
    Privacy: no prompt text, no prompt hash sent. developer_id is the
    SHA-256 machine hash used only for Langfuse user grouping.
    """
    lf = _get_client()
    if lf is None:
        return
    try:
        trace = lf.trace(
            name="prompt_turn",
            session_id=session_id,
            user_id=developer_id,
            tags=flags or [],
            metadata={
                "turn_index": turn_index,
                "prompt_chars": prompt_chars,
                "team_id": team_id,
                "project_name": project_name,
            },
            input={"prompt_chars": prompt_chars},
            output={"quality_score": quality_score, "flags": flags},
        )
        trace.score(
            name="quality_score",
            value=quality_score,
            comment=", ".join(flags) if flags else None,
        )
        lf.flush()
    except Exception:
        log.debug("Langfuse trace failed (non-fatal)", exc_info=True)


def send_session_event(
    session_id: str,
    event: str,
    developer_id: str | None = None,
    team_id: str | None = None,
    project_name: str | None = None,
) -> None:
    """Emit a session-boundary event (start/end) as a Langfuse trace.

    Gives the Langfuse session timeline a clear start and end marker.
    """
    lf = _get_client()
    if lf is None:
        return
    try:
        lf.trace(
            name=f"session_{event}",
            session_id=session_id,
            user_id=developer_id,
            metadata={
                "team_id": team_id,
                "project_name": project_name,
            },
        )
        lf.flush()
    except Exception:
        log.debug("Langfuse session event failed (non-fatal)", exc_info=True)

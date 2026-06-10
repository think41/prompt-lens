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
    """Send a scored turn to Langfuse as a trace + quality score (v4 SDK).

    Fire-and-forget — never raises.
    """
    lf = _get_client()
    if lf is None:
        return
    try:
        from langfuse._client.propagation import propagate_attributes
        from langfuse.types import TraceContext

        trace_id = lf.create_trace_id()
        with (
            propagate_attributes(
                user_id=developer_id,
                session_id=session_id,
                trace_name="prompt_turn",
                tags=flags or [],
            ),
            lf.start_as_current_observation(
                trace_context=TraceContext(trace_id=trace_id),
                name="prompt_turn",
                as_type="evaluator",
                input={"prompt_chars": prompt_chars},
                output={"quality_score": quality_score, "flags": flags},
                metadata={
                    "turn_index": turn_index,
                    "team_id": team_id,
                    "project_name": project_name,
                },
            ),
        ):
            pass
        lf.create_score(
            trace_id=trace_id,
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
    """Emit a session-boundary event (start/end) as a Langfuse trace (v4 SDK).

    Gives the Langfuse session timeline a clear start and end marker.
    """
    lf = _get_client()
    if lf is None:
        return
    try:
        from langfuse._client.propagation import propagate_attributes
        from langfuse.types import TraceContext

        trace_id = lf.create_trace_id()
        with (
            propagate_attributes(
                user_id=developer_id,
                session_id=session_id,
                trace_name=f"session_{event}",
            ),
            lf.start_as_current_observation(
                trace_context=TraceContext(trace_id=trace_id),
                name=f"session_{event}",
                as_type="evaluator",
                metadata={
                    "team_id": team_id,
                    "project_name": project_name,
                },
            ),
        ):
            pass
        lf.flush()
    except Exception:
        log.debug("Langfuse session event failed (non-fatal)", exc_info=True)

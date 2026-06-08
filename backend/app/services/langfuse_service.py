import logging

from ..core.config import settings

log = logging.getLogger(__name__)


def send_span(
    session_id: str,
    turn_index: int,
    quality_score: float,
    flags: list[str],
    prompt_chars: int,
) -> None:
    """Forward scoring metadata to Langfuse. Fire-and-forget — never raises.

    Privacy: no prompt text, no prompt_hash, no developer identity sent.
    """
    if not settings.langfuse_secret_key:
        return
    try:
        from langfuse import Langfuse

        lf = Langfuse(
            secret_key=settings.langfuse_secret_key,
            public_key=settings.langfuse_public_key,
            host=settings.langfuse_host,
        )
        trace = lf.trace(
            name="prompt_turn",
            session_id=session_id,
            input={},
            metadata={"turn_index": turn_index, "prompt_chars": prompt_chars},
        )
        trace.score(
            name="quality_score",
            value=quality_score,
            comment=",".join(flags) if flags else None,
        )
        lf.flush()
    except Exception:
        log.debug("Langfuse span failed (non-fatal)", exc_info=True)

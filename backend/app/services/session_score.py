from ..evaluators.blind_accept import BlindAcceptEvaluator
from ..evaluators.skipped_tests import SkippedTestsEvaluator


def compute_session_score(turns: list, tool_events: list) -> tuple[float, list[str]]:
    """
    Compute an orchestration score (0–1) for a completed session.

    Components and weights:
      - avg_turn_quality  (0.5) — mean quality score across all turns
      - accept_health     (0.3) — penalised by blind_accept flag
      - test_signal       (0.2) — penalised when code edited but no tests touched

    Returns (orchestration_score, session_flags).
    """
    flags: list[str] = []

    # --- turn quality ---
    scores = [t.quality_score for t in turns if t.quality_score is not None]
    avg_quality = sum(scores) / len(scores) if scores else 1.0

    # --- blind accept ---
    ba_delta, ba_flags = BlindAcceptEvaluator().evaluate(tool_events)
    flags += ba_flags
    accept_health = max(0.0, 1.0 + ba_delta)

    # --- skipped tests ---
    st_delta, st_flags = SkippedTestsEvaluator().evaluate(tool_events)
    flags += st_flags
    test_signal = max(0.0, 1.0 + st_delta)

    score = round(
        avg_quality * 0.5
        + accept_health * 0.3
        + test_signal * 0.2,
        2,
    )
    return max(0.0, min(1.0, score)), flags

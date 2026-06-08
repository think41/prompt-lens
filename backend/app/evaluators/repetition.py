from dataclasses import dataclass


@dataclass
class RepetitionDetector:
    lookback: int = 10
    penalty: float = 0.3

    def evaluate(self, prompt_hash: str, session_id: str, db) -> tuple[float, list[str]]:
        """Requires DB — run in Celery task only, not in offline chain."""
        from ..db.models import Turn

        prior = (
            db.query(Turn)
            .filter(
                Turn.session_id == session_id,
                Turn.prompt_hash == prompt_hash,
            )
            .count()
        )
        if prior > 1:  # more than the current row itself
            return -self.penalty, ["repeated_prompt"]
        return 0.0, []

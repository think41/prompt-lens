from dataclasses import dataclass, field


@dataclass
class BlindAcceptEvaluator:
    streak_threshold: int = 5   # matches PROMPTLENS_STREAK_WARN default in hook
    penalty: float = 0.25

    def evaluate(self, tool_events: list) -> tuple[float, list[str]]:
        """
        tool_events: list of ToolEvent ORM rows for the session.
        Flags blind_accept when the developer accepted every tool suggestion
        without a single rejection and the total exceeds the streak threshold.
        """
        if not tool_events:
            return 0.0, []

        # total_accepts/rejects are running counters — take the max (final value)
        total_accepts = max((e.total_accepts for e in tool_events), default=0)
        total_rejects = max((e.total_rejects for e in tool_events), default=0)
        peak_streak = max((e.accept_streak for e in tool_events), default=0)

        blind = (
            total_rejects == 0
            and total_accepts >= self.streak_threshold
        ) or peak_streak >= self.streak_threshold

        if blind:
            return -self.penalty, ["blind_accept"]
        return 0.0, []

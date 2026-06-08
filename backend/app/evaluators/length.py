from dataclasses import dataclass


@dataclass
class LengthEvaluator:
    too_short_threshold: int = 20
    too_long_threshold: int = 2000
    optimal_min: int = 100
    optimal_max: int = 500

    def evaluate(self, prompt_chars: int) -> tuple[float, list[str]]:
        delta = 0.0
        flags: list[str] = []

        if prompt_chars < self.too_short_threshold:
            delta -= 0.4
            flags.append("too_short")
        elif prompt_chars > self.too_long_threshold:
            delta -= 0.1
            flags.append("too_long")
        elif self.optimal_min <= prompt_chars <= self.optimal_max:
            delta += 0.1

        return delta, flags

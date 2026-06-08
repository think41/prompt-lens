import re
from dataclasses import dataclass

# Concrete specificity signals — presence of any raises confidence prompt is specific
_FUNC_CALL = re.compile(r"\b\w{2,}\s*\(")  # foo(, bar(
_FILE_PATH = re.compile(
    r"[/~][\w./\-]+\.\w{1,5}|\b\w+\.(py|ts|tsx|js|go|rs|java|cpp|yaml|json|md)\b"
)
_LINE_NUM = re.compile(r"\bline\s*:?\s*\d+\b|L\d{1,5}\b|:\d{1,5}\b", re.IGNORECASE)
_SNAKE_VAR = re.compile(r"\b[a-z][a-z0-9]+_[a-z0-9_]+\b")  # snake_case variables
_CAMEL_CLASS = re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]+\b")  # CamelCase identifiers
_ERROR_TYPE = re.compile(r"\b\w*(Error|Exception|Warning|Failure)\b")
_VERSION = re.compile(r"\bv?\d+\.\d+(\.\d+)?\b|Python\s+3\.\d+|Node\s+\d+")
_NUMBERS = re.compile(r"\b\d{2,}\b")  # specific numbers (not 1-9)


def _count_signals(prompt: str) -> int:
    return sum(
        [
            bool(_FUNC_CALL.search(prompt)),
            bool(_FILE_PATH.search(prompt)),
            bool(_LINE_NUM.search(prompt)),
            bool(_SNAKE_VAR.search(prompt)),
            bool(_CAMEL_CLASS.search(prompt)),
            bool(_ERROR_TYPE.search(prompt)),
            bool(_VERSION.search(prompt)),
            bool(_NUMBERS.search(prompt)),
        ]
    )


@dataclass
class SpecificityEvaluator:
    min_words: int = 5
    low_signal_threshold: int = 1  # fewer than this = low specificity

    def evaluate(self, prompt: str) -> tuple[float, list[str]]:
        words = prompt.split()
        if len(words) < self.min_words:
            return 0.0, []  # too short — LengthEvaluator handles it

        signals = _count_signals(prompt)
        if signals >= self.low_signal_threshold:
            return 0.0, []

        return -0.2, ["low_specificity"]

import re
from dataclasses import dataclass

_VAGUE_PHRASES = [
    # Single vague words
    "help", "fix", "broken", "debug",
    # Short vague phrases
    "fix it", "fix this", "make it work", "make this work", "do it", "do this",
    "help me", "just help", "update this", "update it", "change this", "change it",
    "make it better", "improve this", "improve it", "clean this up", "clean it up",
    "refactor this", "rewrite this", "rewrite it", "check this", "check it",
    "look at this", "look into this", "handle this", "handle it",
    "not working", "doesn't work", "broken", "it broke", "something is wrong",
    "idk", "i don't know", "not sure", "figure it out", "figure this out",
    "please help", "can you help", "what's wrong", "whats wrong",
]

# Deduplicate while preserving order
_seen = set()
_UNIQUE_PHRASES = [p for p in _VAGUE_PHRASES if not (p in _seen or _seen.add(p))]

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in sorted(_UNIQUE_PHRASES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


@dataclass
class VaguenessEvaluator:
    per_phrase_penalty: float = 0.15
    max_penalty: float = 0.45

    def evaluate(self, prompt: str) -> tuple[float, list[str]]:
        matches = _PATTERN.findall(prompt)
        if not matches:
            return 0.0, []

        unique = set(m.lower() for m in matches)
        delta = -min(len(unique) * self.per_phrase_penalty, self.max_penalty)
        return round(delta, 2), ["vague"]

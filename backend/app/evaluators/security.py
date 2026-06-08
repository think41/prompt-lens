import re
from dataclasses import dataclass

_SENSITIVE_PATTERNS = [
    re.compile(r"\.env\b", re.IGNORECASE),
    re.compile(r"\bcredentials?\b", re.IGNORECASE),
    re.compile(r"\bprivate[_\s]?key\b", re.IGNORECASE),
    re.compile(r"\bsecret[_\s]?key\b", re.IGNORECASE),
    re.compile(r"\bapi[_\s]?key\b", re.IGNORECASE),
    re.compile(r"\baccess[_\s]?key\b", re.IGNORECASE),
    re.compile(r"\baws[_\s]?(secret|access)\b", re.IGNORECASE),
    re.compile(r"\bpassword\s*=", re.IGNORECASE),
    re.compile(r"\btoken\s*=", re.IGNORECASE),
    re.compile(r"id_rsa", re.IGNORECASE),
    re.compile(r"\.pem\b"),
    re.compile(r"~/.ssh/"),
    re.compile(r"aws/credentials"),
    re.compile(r"\bsecrets?manager\b", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"[A-Z0-9]{20,}"),  # raw API key pattern
]


@dataclass
class SecurityEvaluator:
    per_pattern_penalty: float = 0.1
    max_penalty: float = 0.3

    def evaluate(self, prompt: str) -> tuple[float, list[str]]:
        hits = sum(1 for p in _SENSITIVE_PATTERNS if p.search(prompt))
        if hits == 0:
            return 0.0, []

        delta = -min(hits * self.per_pattern_penalty, self.max_penalty)
        return round(delta, 2), ["sensitive_content"]

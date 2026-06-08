import re
from dataclasses import dataclass

_CODE_SIGNALS = [
    # Language keywords
    "def ",
    "class ",
    "import ",
    "from ",
    "return ",
    "async def",
    "await ",
    "function ",
    "const ",
    "let ",
    "var ",
    "=>",
    "interface ",
    "type ",
    "struct ",
    "impl ",
    "fn ",
    "pub ",
    "mod ",
    # Code blocks
    "```",
    "~~~",
    # Common patterns
    "error:",
    "Error:",
    "exception:",
    "Exception:",
    "traceback",
    "Traceback",
    "TypeError",
    "ValueError",
    "KeyError",
    "AttributeError",
    "IndexError",
    "RuntimeError",
    "SyntaxError",
    "ImportError",
    # File signals
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    # Stack traces
    "at line ",
    "line ",
    'File "',
    "    at ",
    # Output signals
    "stdout",
    "stderr",
    "exit code",
    "status code",
    "HTTP ",
    "404",
    "500",
    "200 OK",
    # Dev signals
    "git ",
    "npm ",
    "pip ",
    "docker ",
    "kubectl ",
]

_FILE_PATH = re.compile(r"[/~][a-zA-Z0-9._/\-]+\.[a-zA-Z]{1,5}")
_ERROR_MSG = re.compile(r"(error|exception|failed|failure|cannot|could not)", re.IGNORECASE)
_STACK_TRACE = re.compile(r"(Traceback|at line \d|File \".+\", line \d)", re.IGNORECASE)


@dataclass
class ContextEvaluator:
    min_signals: int = 1

    def evaluate(self, prompt: str) -> tuple[float, list[str]]:
        if len(prompt) <= 30:
            return 0.0, []

        code_hits = sum(1 for s in _CODE_SIGNALS if s in prompt)
        has_path = bool(_FILE_PATH.search(prompt))
        has_error = bool(_ERROR_MSG.search(prompt))
        has_stack = bool(_STACK_TRACE.search(prompt))

        total_signals = code_hits + has_path + has_error + has_stack

        if total_signals >= self.min_signals:
            return 0.0, []

        return -0.25, ["missing_context"]

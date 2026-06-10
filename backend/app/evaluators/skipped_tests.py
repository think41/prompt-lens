import re
from dataclasses import dataclass

_CODE_EXT = re.compile(
    r"\.(py|ts|tsx|js|jsx|go|rs|java|cpp|c|cs|rb|php|swift|kt)$",
    re.IGNORECASE,
)
_TEST_PATH = re.compile(
    r"(^|/)tests?/|test_[^/]+\.(py|ts|tsx|js|jsx)$|[^/]+\.(test|spec)\.(ts|tsx|js|jsx|py)$",
    re.IGNORECASE,
)
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


@dataclass
class SkippedTestsEvaluator:
    penalty: float = 0.2

    def evaluate(self, tool_events: list) -> tuple[float, list[str]]:
        """
        tool_events: list of ToolEvent ORM rows for the session.
        Flags skipped_tests when code files were written/edited but no test
        files were touched across the entire session.
        """
        code_edits = False
        test_edits = False

        for event in tool_events:
            if event.tool_name not in _WRITE_TOOLS:
                continue
            path = event.file_path or ""
            if not path:
                continue
            if _TEST_PATH.search(path):
                test_edits = True
            elif _CODE_EXT.search(path):
                code_edits = True

        if code_edits and not test_edits:
            return -self.penalty, ["skipped_tests"]
        return 0.0, []

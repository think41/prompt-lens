from .length import LengthEvaluator
from .vagueness import VaguenessEvaluator
from .context import ContextEvaluator
from .security import SecurityEvaluator
from .specificity import SpecificityEvaluator


class EvaluatorChain:
    def __init__(self) -> None:
        self._length = LengthEvaluator()
        self._vagueness = VaguenessEvaluator()
        self._context = ContextEvaluator()
        self._security = SecurityEvaluator()
        self._specificity = SpecificityEvaluator()

    def score(self, prompt: str, prompt_chars: int | None = None) -> tuple[float, list[str]]:
        chars = prompt_chars if prompt_chars is not None else len(prompt)

        l_delta, l_flags = self._length.evaluate(chars)
        v_delta, v_flags = self._vagueness.evaluate(prompt)
        c_delta, c_flags = self._context.evaluate(prompt)
        s_delta, s_flags = self._security.evaluate(prompt)
        sp_delta, sp_flags = self._specificity.evaluate(prompt)

        # Direct additive: each evaluator's full penalty/bonus applied to base 1.0.
        # No weighting — dilution was preventing low-quality prompts from scoring low.
        composite = max(0.0, min(1.0, round(1.0 + l_delta + v_delta + c_delta + s_delta + sp_delta, 2)))
        flags = l_flags + v_flags + c_flags + s_flags + sp_flags

        return composite, flags

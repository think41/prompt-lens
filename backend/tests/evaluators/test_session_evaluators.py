from unittest.mock import MagicMock

import pytest

from app.evaluators.blind_accept import BlindAcceptEvaluator
from app.evaluators.skipped_tests import SkippedTestsEvaluator
from app.services.session_score import compute_session_score


def _tool(tool_name="Edit", allowed=True, accept_streak=1, file_path=None):
    e = MagicMock()
    e.tool_name = tool_name
    e.allowed = allowed
    e.accept_streak = accept_streak
    e.file_path = file_path
    return e


def _turn(quality_score=0.8):
    t = MagicMock()
    t.quality_score = quality_score
    return t


# --- BlindAcceptEvaluator ---

class TestBlindAcceptEvaluator:
    def test_no_events_clean(self):
        delta, flags = BlindAcceptEvaluator().evaluate([])
        assert delta == 0.0 and flags == []

    def test_below_threshold_clean(self):
        events = [_tool(accept_streak=i) for i in range(1, 4)]
        delta, flags = BlindAcceptEvaluator().evaluate(events)
        assert flags == []

    def test_streak_at_threshold_flags(self):
        events = [_tool(accept_streak=5)]
        _, flags = BlindAcceptEvaluator(streak_threshold=5).evaluate(events)
        assert "blind_accept" in flags

    def test_all_accepts_no_rejects_flags(self):
        events = [_tool(accept_streak=i) for i in range(1, 7)]
        _, flags = BlindAcceptEvaluator(streak_threshold=5).evaluate(events)
        assert "blind_accept" in flags

    def test_has_reject_clears_flag(self):
        events = [_tool(accept_streak=2)] * 4 + [_tool(allowed=False, accept_streak=0)]
        _, flags = BlindAcceptEvaluator(streak_threshold=5).evaluate(events)
        assert "blind_accept" not in flags


# --- SkippedTestsEvaluator ---

class TestSkippedTestsEvaluator:
    def test_no_events_clean(self):
        delta, flags = SkippedTestsEvaluator().evaluate([])
        assert flags == []

    def test_code_with_tests_clean(self):
        events = [
            _tool(file_path="/app/auth.py"),
            _tool(file_path="/app/tests/test_auth.py"),
        ]
        _, flags = SkippedTestsEvaluator().evaluate(events)
        assert flags == []

    def test_code_without_tests_flags(self):
        events = [_tool(file_path="/app/auth.py"), _tool(file_path="/app/models.py")]
        _, flags = SkippedTestsEvaluator().evaluate(events)
        assert "skipped_tests" in flags

    def test_only_reads_no_flag(self):
        events = [_tool(tool_name="Read", file_path="/app/auth.py")]
        _, flags = SkippedTestsEvaluator().evaluate(events)
        assert flags == []

    def test_spec_file_counts_as_test(self):
        events = [
            _tool(file_path="/app/auth.ts"),
            _tool(file_path="/app/auth.spec.ts"),
        ]
        _, flags = SkippedTestsEvaluator().evaluate(events)
        assert flags == []

    def test_test_dir_counts(self):
        events = [
            _tool(file_path="/app/service.py"),
            _tool(file_path="/app/tests/integration.py"),
        ]
        _, flags = SkippedTestsEvaluator().evaluate(events)
        assert flags == []


# --- compute_session_score ---

class TestComputeSessionScore:
    def test_perfect_session(self):
        turns = [_turn(1.0), _turn(1.0)]
        tool_events = [
            _tool(accept_streak=1, file_path="/app/auth.py"),
            _tool(allowed=False, accept_streak=0),
            _tool(tool_name="Write", file_path="/app/tests/test_auth.py"),
        ]
        score, flags = compute_session_score(turns, tool_events)
        assert score >= 0.8
        assert flags == []

    def test_blind_accept_and_skipped_tests_lowers_score(self):
        turns = [_turn(0.4)]
        tool_events = [_tool(accept_streak=i, file_path="/app/auth.py") for i in range(1, 7)]
        score, flags = compute_session_score(turns, tool_events)
        assert score < 0.7
        assert "blind_accept" in flags
        assert "skipped_tests" in flags

    def test_score_clamped_to_unit_interval(self):
        turns = [_turn(1.0)]
        score, _ = compute_session_score(turns, [])
        assert 0.0 <= score <= 1.0

    def test_empty_session(self):
        score, flags = compute_session_score([], [])
        assert 0.0 <= score <= 1.0
        assert flags == []

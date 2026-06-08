import json
import os
import sys
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock


def run_hook(stdin_data: dict, env: dict = None) -> dict:
    """Run on_prompt.main(), return captured payload sent to backend."""
    import importlib
    env = env or {}
    captured_payload = {}

    def fake_urlopen(req, timeout=None):
        captured_payload.update(json.loads(req.data.decode()))
        return MagicMock()

    with patch.dict(os.environ, {"PROMPTLENS_ENDPOINT": "http://localhost:9999", **env}):
        with patch("sys.stdin", StringIO(json.dumps(stdin_data))):
            with patch("sys.stdout", StringIO()):
                with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                    import hooks.on_prompt as m
                    importlib.reload(m)
                    m.main()
    return captured_payload


class TestOnPrompt(unittest.TestCase):
    def test_exits_cleanly_no_exception(self):
        # Should not raise
        import importlib
        with patch.dict(os.environ, {"PROMPTLENS_ENDPOINT": "http://localhost:9999"}):
            with patch("sys.stdin", StringIO(json.dumps({"prompt": "fix it", "session_id": "s1"}))):
                with patch("sys.stdout", StringIO()):
                    with patch("urllib.request.urlopen", return_value=MagicMock()):
                        import hooks.on_prompt as m
                        importlib.reload(m)
                        m.main()  # must not raise

    def test_empty_stdin_no_exception(self):
        import importlib
        with patch.dict(os.environ, {"PROMPTLENS_ENDPOINT": "http://localhost:9999"}):
            with patch("sys.stdin", StringIO("")):
                with patch("sys.stdout", StringIO()):
                    import hooks.on_prompt as m
                    importlib.reload(m)
                    m.main()

    def test_no_raw_prompt_in_payload(self):
        raw_prompt = "my secret prompt text"
        payload = run_hook({"prompt": raw_prompt, "session_id": "s1"})
        self.assertNotIn("prompt", payload)
        self.assertIn("prompt_hash", payload)
        self.assertIn("prompt_chars", payload)
        self.assertNotIn(raw_prompt, json.dumps(payload))

    def test_payload_shape(self):
        payload = run_hook(
            {"prompt": "refactor this function", "session_id": "s42", "turn_index": 2},
            env={"PROMPTLENS_DEVELOPER_ID": "dev123"},
        )
        for field in ("type", "session_id", "developer_id", "team_id", "turn_index",
                      "prompt_hash", "prompt_chars", "quality_score", "flags", "timestamp"):
            self.assertIn(field, payload, f"Missing field: {field}")
        self.assertEqual(payload["type"], "prompt")
        self.assertEqual(payload["session_id"], "s42")
        self.assertEqual(payload["developer_id"], "dev123")

    def test_redaction_removes_email(self):
        import importlib
        import hooks.on_prompt as m
        importlib.reload(m)
        result = m.redact("send to user@example.com please")
        self.assertNotIn("user@example.com", result)
        self.assertIn("[EMAIL]", result)

    def test_redaction_removes_bearer_token(self):
        import importlib
        import hooks.on_prompt as m
        importlib.reload(m)
        result = m.redact("Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc")
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("eyJhbGciOiJIUzI1NiJ9", result)


if __name__ == "__main__":
    unittest.main()

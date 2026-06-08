import json
import os
import shutil
import unittest
from io import StringIO
from unittest.mock import patch, MagicMock


class TestOnTool(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree("/tmp/promptlens_streaks", ignore_errors=True)

    def _run(self, stdin_data: dict, env: dict = None) -> dict:
        """Run on_tool.main(), return captured payload sent to backend."""
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
                        import hooks.on_tool as m
                        importlib.reload(m)
                        m.main()
        return captured_payload

    def test_exits_cleanly_no_exception(self):
        import importlib
        with patch.dict(os.environ, {"PROMPTLENS_ENDPOINT": "http://localhost:9999"}):
            with patch("sys.stdin", StringIO(json.dumps({"tool_name": "Write", "allowed": True, "session_id": "s1"}))):
                with patch("sys.stdout", StringIO()):
                    with patch("urllib.request.urlopen", return_value=MagicMock()):
                        import hooks.on_tool as m
                        importlib.reload(m)
                        m.main()

    def test_malformed_stdin_no_exception(self):
        import importlib
        with patch.dict(os.environ, {"PROMPTLENS_ENDPOINT": "http://localhost:9999"}):
            with patch("sys.stdin", StringIO("not json")):
                with patch("sys.stdout", StringIO()):
                    import hooks.on_tool as m
                    importlib.reload(m)
                    m.main()

    def test_payload_has_no_raw_file_path(self):
        stdin = {"tool_name": "Write", "allowed": True, "session_id": "s1",
                 "input": {"file_path": "/home/user/secret.py"}}
        payload = self._run(stdin)
        self.assertNotIn("file_path", payload)
        self.assertIn("file_path_hash", payload)
        self.assertNotIn("/home/user/secret.py", json.dumps(payload))

    def test_payload_shape(self):
        payload = self._run({"tool_name": "Bash", "allowed": True, "session_id": "s2", "turn_index": 1})
        for field in ("type", "session_id", "developer_id", "team_id", "tool_name",
                      "allowed", "accept_streak", "total_accepts", "total_rejects",
                      "sensitive_path", "timestamp"):
            self.assertIn(field, payload, f"Missing field: {field}")
        self.assertEqual(payload["type"], "tool")


if __name__ == "__main__":
    unittest.main()

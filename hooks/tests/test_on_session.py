import json
import os
import shutil
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch


class TestOnSession(unittest.TestCase):
    def tearDown(self):
        shutil.rmtree("/tmp/promptlens_sessions", ignore_errors=True)
        shutil.rmtree("/tmp/promptlens_streaks", ignore_errors=True)

    def _run(self, stdin_data: dict) -> dict:
        """Run on_session.main(), return captured payload sent to backend."""
        import importlib

        captured_payload = {}

        def fake_urlopen(req, timeout=None):
            captured_payload.update(json.loads(req.data.decode()))
            return MagicMock()

        with (
            patch.dict(os.environ, {"PROMPTLENS_ENDPOINT": "http://localhost:9999"}),
            patch("sys.stdin", StringIO(json.dumps(stdin_data))),
            patch("sys.stdout", StringIO()),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            import hooks.on_session as m

            importlib.reload(m)
            m.main()
        return captured_payload

    def test_start_exits_cleanly(self):
        self._run({"event": "start", "session_id": "sess1", "cwd": "/home/dev"})

    def test_end_exits_cleanly(self):
        self._run({"event": "end", "session_id": "sess1", "turns": 5})

    def test_empty_stdin_no_exception(self):
        import importlib

        with (
            patch.dict(os.environ, {"PROMPTLENS_ENDPOINT": "http://localhost:9999"}),
            patch("sys.stdin", StringIO("")),
            patch("sys.stdout", StringIO()),
            patch("urllib.request.urlopen", return_value=MagicMock()),
        ):
            import hooks.on_session as m

            importlib.reload(m)
            m.main()

    def test_start_payload_has_no_raw_cwd(self):
        payload = self._run({"event": "start", "session_id": "s1", "cwd": "/home/user/projects"})
        self.assertNotIn("cwd", payload)
        self.assertIn("cwd_hash", payload)
        self.assertNotIn("/home/user/projects", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()

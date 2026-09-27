"""Exercise both CLIs without using the invoking user's session store."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).parents[1] / "scripts"


class StoragePathTests(unittest.TestCase):
    def test_root_precedence_and_expansion_across_clis(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            home = base / "home"
            home.mkdir()
            fallback = home / ".pi" / "agent" / "sessions"
            agent = home / "custom-agent"
            store = base / "store"
            explicit = base / "explicit"
            extra = base / "extra"
            env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
                   "PI_SESSION_FILE": "", "PYTHONDONTWRITEBYTECODE": "1"}
            for key in ("PI_CODING_AGENT_DIR", "PI_CODING_AGENT_SESSION_DIR"):
                env.pop(key, None)
            # Each case creates only its selected directory. Losing roots are
            # missing, so accidental additive/fallback searches fail visibly.
            cases = [
                ({}, [], fallback),
                ({"PI_CODING_AGENT_DIR": "~/custom-agent"}, [], agent / "sessions"),
                ({"PI_CODING_AGENT_DIR": "missing-agent", "PI_CODING_AGENT_SESSION_DIR": "store"}, [], store),
                ({"PI_CODING_AGENT_DIR": "missing-agent", "PI_CODING_AGENT_SESSION_DIR": "missing-store"},
                 ["--sessions-root", str(explicit)], explicit),
                ({"PI_CODING_AGENT_DIR": "", "PI_CODING_AGENT_SESSION_DIR": ""}, [], fallback),
                ({"PI_CODING_AGENT_SESSION_DIR": "~/tilde-store"}, [], home / "tilde-store"),
                ({"PI_CODING_AGENT_SESSION_DIR": "~root/store"}, [], base / "~root" / "store"),
                ({"PI_CODING_AGENT_DIR": "~root/agent"}, [], base / "~root" / "agent" / "sessions"),
            ]
            commands = [("session_search.py", []), ("session_recall.py", ["find", "--term", "needle"]),
                        ("session_recall.py", ["recall", "--term", "needle", "--include-evidence"])]
            for overrides, flags, selected in cases:
                selected.mkdir(parents=True, exist_ok=True)
                record = selected / "synthetic.jsonl"
                record.write_text("\n".join(json.dumps(row) for row in [
                    {"type": "session", "version": 3, "id": "synthetic", "cwd": str(base)},
                    {"type": "message", "id": "m1", "parentId": None, "timestamp": "2026-01-01T00:00:00Z",
                     "message": {"role": "user", "content": "needle"}},
                ]) + "\n", encoding="utf-8")
                for script, args in commands:
                    with self.subTest(script=script, args=args, overrides=overrides):
                        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *args, *flags],
                                                cwd=base, env={**env, **overrides}, capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        payload = json.loads(result.stdout)
                        self.assertEqual(payload["summary"]["matched_sessions"], 1)
                        if args and args[0] == "find":
                            self.assertEqual(len(payload["candidates"]), 1)
                            self.assertEqual(payload["candidates"][0]["rank"], 1)
                record.unlink()
                selected.rmdir()
            extra.mkdir()
            # Adding a directory must not silently replace an unavailable primary.
            for script, args in commands[:2]:
                result = subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *args,
                                         "--additional-sessions-root", str(extra)], cwd=base, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("SESSION_STORAGE_UNAVAILABLE", result.stdout)

    def test_all_help_entries_expose_replacement_root(self):
        for script, args in [("session_search.py", []), ("session_recall.py", ["find"]),
                             ("session_recall.py", ["recall"])]:
            result = subprocess.run([sys.executable, "-B", str(SCRIPTS / script), *args, "--help"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("--sessions-root PATH", result.stdout)
            self.assertIn("PI_CODING_AGENT_SESSION_DIR", result.stdout)


if __name__ == "__main__":
    unittest.main()

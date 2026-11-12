import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from support import RECALL_SCRIPT, SEARCH_SCRIPT, cli_args, cli_argv, header, message, run_mode, write_session


class SessionOpenTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve()
        self.root = self.project / "sessions"
        self.root.mkdir()
        self.now = datetime.now(timezone.utc)

    def write(self, path, marker):
        write_session(path, header(marker, self.project), [
            message("entry", None, "2026-08-01T00:00:00Z", "user", f"needle {marker}"),
        ])

    def test_aggregate_reports_the_discovered_alias_for_evidence_and_warnings(self):
        approved = self.root / "approved.data"
        self.write(approved, "APPROVED")
        with approved.open("ab") as handle:
            handle.write(b"not-json\n")
        alias = self.root / "original.jsonl"
        alias.symlink_to(approved)
        output = run_mode("aggregate", cli_args("aggregate", self.root, self.project, "--include-evidence"), self.now)
        self.assertEqual(output["results"][0]["file"], str(alias))
        self.assertTrue(output["results"][0]["on_latest_leaf"])
        self.assertEqual(output["warnings"]["items"], [{"kind": "invalid_json_line", "path": str(alias)}])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires a POSIX FIFO")
    def test_named_pipe_without_writer_never_blocks_a_session_command(self):
        self.write(self.root / "valid.jsonl", "APPROVED")
        os.mkfifo(self.root / "pipe.jsonl")
        for mode in ("aggregate", "find", "recall"):
            with self.subTest(mode=mode):
                command = SEARCH_SCRIPT if mode == "aggregate" else RECALL_SCRIPT
                result = subprocess.run(
                    [sys.executable, "-B", str(command), *cli_argv(mode, self.root, self.project)],
                    capture_output=True, text=True, timeout=2, check=True,
                )
                self.assertEqual(json.loads(result.stdout)["summary"]["matched_sessions"], 1)

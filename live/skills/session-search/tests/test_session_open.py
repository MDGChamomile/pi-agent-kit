import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import RECALL_SCRIPT, SEARCH_SCRIPT, cli_args, cli_argv, header, message, run_mode, session_common, write_session


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

    def test_alias_swap_after_discovery_never_opens_the_new_target(self):
        approved = self.root / "approved.data"
        outside = self.project / "outside.data"
        self.write(approved, "APPROVED")
        self.write(outside, "OUTSIDE")
        alias = self.root / "only.jsonl"
        discover = session_common.discover_session_files

        def discover_then_swap(*args, **kwargs):
            paths = discover(*args, **kwargs)
            alias.unlink()
            alias.symlink_to(outside)
            return paths

        for mode in ("aggregate", "find", "recall"):
            with self.subTest(mode=mode):
                alias.unlink(missing_ok=True)
                alias.symlink_to(approved)
                extra = ["--query", "OUTSIDE"] if mode == "aggregate" else []
                args = cli_args(mode, self.root, self.project, *extra, terms=["APPROVED"])
                with patch.object(session_common, "discover_session_files", discover_then_swap):
                    output = run_mode(mode, args, self.now)
                self.assertEqual(output["summary"]["matched_sessions"], int(mode != "aggregate"))
                self.assertNotIn("OUTSIDE", json.dumps(output))

    def test_replaced_canonical_file_or_parent_is_rejected_before_read(self):
        outside = self.project / "outside"
        outside.mkdir()
        self.write(outside / "candidate.jsonl", "OUTSIDE")
        folder = self.root / "folder"
        folder.mkdir()
        candidate = folder / "candidate.jsonl"
        self.write(candidate, "APPROVED")
        paths = session_common.discover_session_files([self.root])
        self.assertEqual(paths, [candidate])
        candidate.unlink()
        candidate.symlink_to(outside / "candidate.jsonl")
        with self.assertRaises(OSError):
            with session_common.open_session_file(paths[0]):
                self.fail("followed replaced file")
        candidate.unlink()
        folder.rmdir()
        folder.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            with session_common.open_session_file(paths[0]):
                self.fail("followed replaced directory")

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

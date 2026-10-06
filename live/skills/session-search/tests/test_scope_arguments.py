"""Keep the shared storage/project options equivalent across all CLI modes."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from support import session_recall, session_search


class ScopeArgumentTests(unittest.TestCase):
    def parse(self, mode, *options):
        if mode == "aggregate":
            return session_search.build_parser().parse_args(list(options))
        return session_recall.build_parser().parse_args([
            mode, "--term", "needle", *options,
            *(["--include-evidence"] if mode == "recall" else []),
        ])

    def test_defaults_match_across_modes(self):
        with patch.dict(os.environ, {"PI_CODING_AGENT_SESSION_DIR": "", "PI_CODING_AGENT_DIR": ""}), \
                patch.object(session_search.os, "getcwd", return_value="/synthetic-project"):
            for mode in ["aggregate", "find", "recall"]:
                with self.subTest(mode=mode):
                    args = self.parse(mode)
                    self.assertEqual(args.cwd, "/synthetic-project")
                    self.assertFalse(args.all_projects)
                    self.assertFalse(args.include_current)
                    self.assertEqual(args.additional_sessions_root, [])
                    self.assertEqual(args.sessions_root, Path.home() / ".pi" / "agent" / "sessions")

    def test_explicit_options_match_across_modes(self):
        for mode in ["aggregate", "find", "recall"]:
            with self.subTest(mode=mode):
                args = self.parse(mode, "--cwd", "project", "--include-current",
                                  "--sessions-root", "primary",
                                  "--additional-sessions-root", "extra-one",
                                  "--additional-sessions-root", "extra-two")
                self.assertEqual(args.cwd, "project")
                self.assertFalse(args.all_projects)
                self.assertTrue(args.include_current)
                self.assertEqual(args.sessions_root, Path("primary"))
                self.assertEqual(args.additional_sessions_root, [Path("extra-one"), Path("extra-two")])
                self.assertTrue(self.parse(mode, "--all-projects").all_projects)

    def test_project_options_remain_mutually_exclusive(self):
        for mode in ["aggregate", "find", "recall"]:
            with self.subTest(mode=mode), self.assertRaises(session_search.InvalidArgumentError):
                self.parse(mode, "--all-projects", "--cwd", "project")

    def test_storage_default_is_resolved_when_each_parser_is_built(self):
        for root in ["first-store", "second-store"]:
            with patch.dict(os.environ, {"PI_CODING_AGENT_SESSION_DIR": root}):
                for mode in ["aggregate", "find", "recall"]:
                    with self.subTest(root=root, mode=mode):
                        self.assertEqual(self.parse(mode).sessions_root, Path(root).absolute())

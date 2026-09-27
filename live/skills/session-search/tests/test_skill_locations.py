"""Portable skill identities are derived from recorded evidence only."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from test_session_search import header, message, session_search, write_session


class SkillLocationTests(unittest.TestCase):
    def test_read_paths_do_not_require_a_skills_parent(self):
        cases = [
            ("/opt/resources/deep-plan/SKILL.md", "", "deep-plan"),
            ("custom/deep-plan/SKILL.md", "/project", "deep-plan"),
            (r"C:\resources\deep-plan\SKILL.md", "", "deep-plan"),
            ("SKILL.md", "/project/deep-plan", "deep-plan"),
            ("./SKILL.md", "/project/deep-plan", "deep-plan"),
            ("/opt/resources/deep-plan/README.md", "", None),
            ("/opt/resources/deep-plan/SKILL.md.bak", "", None),
        ]
        for path, cwd, expected in cases:
            with self.subTest(path=path):
                self.assertEqual(session_search.skill_read_name("read", {"path": path}, cwd=cwd), expected)
                self.assertIsNone(session_search.skill_read_name("bash", {"path": path}, cwd=cwd))

    def test_recorded_name_overrides_folder_and_keeps_outcomes_correlated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = root / "project"
            # This location deliberately does not exist on disk.
            location = str(project / "custom" / "renamed-folder" / "SKILL.md")
            entries = [
                message("m1", None, "2026-08-01T00:00:00Z", "user",
                        f'<skill name="declared-name" location="{location}">\n'
                        f'References are relative to {project / "custom" / "renamed-folder"}.\n\n'
                        'Synthetic instructions\n</skill>'),
                message("m2", "m1", "2026-08-14T00:00:00Z", "assistant", [
                    {"type": "toolCall", "id": "read-ok", "name": "read",
                     "arguments": {"path": "custom/renamed-folder/./SKILL.md"}},
                    {"type": "toolCall", "id": "read-error", "name": "read",
                     "arguments": {"path": location}},
                ]),
                message("m3", "m2", "2026-08-14T00:01:00Z", "toolResult", "synthetic body",
                        toolName="read", toolCallId="read-ok", isError=False),
                message("m4", "m3", "2026-08-14T00:02:00Z", "toolResult", "synthetic failure",
                        toolName="read", toolCallId="read-error", isError=True),
            ]
            write_session(root / "record.jsonl", header("synthetic", project), entries)
            args = session_search.build_parser().parse_args([
                "--sessions-root", str(root), "--cwd", str(project), "--days", "2", "--skill", "declared-name",
            ])
            result = session_search.aggregate(args, now=datetime(2026, 8, 15, tzinfo=timezone.utc))
            summary = result["summary"]
            self.assertEqual(summary["skill_file_read_attempts"], {"declared-name": 2})
            self.assertEqual(summary["skill_file_read_successes"], {"declared-name": 1})
            self.assertEqual(summary["skill_file_read_errors"], {"declared-name": 1})
            self.assertEqual(summary["direct_skill_calls"], {})
            self.assertEqual(result["results"], [])
            self.assertFalse(Path(location).exists())

    def test_unrelated_text_does_not_register_names(self):
        for role, text in [
            ("assistant", '<skill name="wrong" location="/custom/folder/SKILL.md">\nReferences are relative to /custom/folder.\n\nbody\n</skill>'),
            ("user", 'Example: <skill name="wrong" location="/custom/folder/SKILL.md">'),
        ]:
            identities = {}
            entry = message("m1", None, "2026-08-01T00:00:00Z", role, text)
            session_search.record_skill_identity(entry, identities, "/project")
            self.assertEqual(identities, {})
            self.assertEqual(session_search.skill_read_name("read", {"path": "/custom/folder/SKILL.md"}, identities), "folder")

    def test_recorded_alias_is_lexical_and_does_not_access_disk(self):
        identities = {"C:/custom/alias/SKILL.md": "declared"}
        self.assertEqual(session_search.skill_read_name("read", {"path": r"C:\custom\alias\SKILL.md"}, identities), "declared")
        self.assertEqual(session_search.skill_read_name("read", {"path": "./alias/SKILL.md"}, identities, "C:/custom"), "declared")


if __name__ == "__main__":
    unittest.main()

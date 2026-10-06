"""Test imports must share the same implementation, regardless of order."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from support import session_recall, session_search


class ModuleLoadingTests(unittest.TestCase):
    def test_discovery_shares_implementation_and_patches(self):
        import test_session_recall
        import test_session_search

        self.assertIs(test_session_search.session_search, session_search)
        self.assertIs(test_session_recall.session_recall, session_recall)
        self.assertIs(session_recall.session_search, session_search)
        self.assertIs(sys.modules["session_search"], session_search)
        with patch.object(session_search, "normalized_path", return_value="patched"):
            self.assertEqual(session_recall.session_search.normalized_path("unused"), "patched")

    def test_both_test_import_orders_share_implementation(self):
        for first, second in [("test_session_search", "test_session_recall"),
                              ("test_session_recall", "test_session_search")]:
            with self.subTest(first=first):
                code = f"""
import {first}
import {second}
import session_search
from test_session_recall import session_recall
from test_session_search import session_search as search_under_test
from unittest.mock import patch
assert search_under_test is session_search
assert session_recall.session_search is session_search
with patch.object(session_search, 'normalized_path', return_value='patched'):
    assert session_recall.session_search.normalized_path('unused') == 'patched'
"""
                result = subprocess.run(
                    [sys.executable, "-B", "-c", code], cwd=Path(__file__).parent,
                    env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

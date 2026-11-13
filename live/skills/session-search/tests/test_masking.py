"""Evidence is masked in full before it is normalized and shortened."""
import unittest

from support import session_common


class MaskingTests(unittest.TestCase):
    def test_quoted_secrets_are_masked_in_full(self):
        cases = (
            ('password="FAKE FIRST SECOND" visible', 'password=[REDACTED] visible'),
            ("passwd='FAKE FIRST; SECOND' visible", 'passwd=[REDACTED] visible'),
            ('{"password": "FAKE FIRST SECOND"}', '{"password": [REDACTED]}'),
            (r'password="FAKE\" SECOND" visible', 'password=[REDACTED] visible'),
            (r"secret='FAKE\' SECOND' visible", 'secret=[REDACTED] visible'),
            ('token="FAKE\nSECOND" visible', 'token=[REDACTED] visible'),
            ('password="FAKE FIRST SECOND', 'password=[REDACTED]'),
            ('password="FAKE FIRST' + '\\', 'password=[REDACTED]'),
            ("secret='FAKE FIRST" + '\\', 'secret=[REDACTED]'),
            ('token=FAKE_VALUE visible', 'token=[REDACTED] visible'),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(session_common.mask_and_shorten(raw), expected)
        raw = 'prefix ' * 100 + ' password="' + 'FAKE_SECRET ' * 100 + '" visible-target'
        evidence = session_common.mask_and_shorten(raw, queries=('FAKE_SECRET', 'visible-target'))
        self.assertNotIn('FAKE_SECRET', evidence)
        self.assertIn('visible-target', evidence)
        self.assertLessEqual(len(evidence), session_common.MAX_EVIDENCE_CHARS)

    def test_cookie_headers_are_masked_before_whitespace_collapses(self):
        cases = (
            'Cookie: session=FAKE_A; sid=FAKE_B',
            'set-cookie: session=FAKE_A; Path=/; HttpOnly',
            'Cookie: session=FAKE_A;\r\n\tsid=FAKE_B',
            'Cookie: session=FAKE_A\nSet-Cookie: sid=FAKE_B; Secure',
            '{"Cookie": "session=FAKE_A; sid=FAKE_B"}',
            '{"Set-Cookie": "session=FAKE_A; Path=/"}',
        )
        for raw in cases:
            with self.subTest(raw=raw):
                evidence = session_common.mask_and_shorten(raw + '\nVisible: keep-me')
                self.assertNotIn('FAKE_', evidence)
                self.assertIn('[REDACTED]', evidence)
                self.assertIn('Visible: keep-me', evidence)

    def test_private_key_url_credentials_and_boundary_secret_are_masked(self):
        raw = (
            "https://alice:correct-horse@example.test/path "
            "-----BEGIN TEST PRIVATE KEY-----private-material-----END TEST PRIVATE KEY----- "
            + "x" * 280
            + " token=BOUNDARY_SECRET_VALUE"
        )
        masked = session_common.mask_and_shorten(raw)
        self.assertNotIn("alice", masked)
        self.assertNotIn("correct-horse", masked)
        self.assertNotIn("private-material", masked)
        self.assertNotIn("BOUNDARY_SECRET_VALUE", masked)
        self.assertLessEqual(len(masked), session_common.MAX_EVIDENCE_CHARS)

    def test_centered_evidence_handles_casefold_expansion_and_whitespace(self):
        raw = "ß" * 500 + " 한글\n\tStraße context " + "tail " * 100
        evidence = session_common.mask_and_shorten(raw, queries=("한글\nSTRASSE",))
        self.assertIn("한글 Straße context", evidence)
        self.assertLessEqual(len(evidence), session_common.MAX_EVIDENCE_CHARS)

    def test_evidence_falls_back_to_masked_prefix_without_visible_query(self):
        raw = "prefix " * 100 + " token=SYNTHETIC_HIDDEN_VALUE " + "tail " * 100
        prefix = session_common.mask_and_shorten(raw)
        for queries in ((), ("SYNTHETIC_HIDDEN_VALUE",), ("tool-metadata-only",), ("",)):
            with self.subTest(queries=queries):
                self.assertEqual(session_common.mask_and_shorten(raw, queries=queries), prefix)
        self.assertEqual(prefix, raw[:299] + "…")

    def test_centered_evidence_masks_entire_source_before_selecting_window(self):
        secret = "SYNTHETIC_" + "x" * 800
        raw = "prefix " * 100 + " token=" + secret + " visible-target " + "tail " * 100
        evidence = session_common.mask_and_shorten(raw, queries=(secret, "visible-target"))
        self.assertIn("visible-target", evidence)
        self.assertIn("token=[REDACTED]", evidence)
        self.assertNotIn("SYNTHETIC_", evidence)
        self.assertNotIn("xxx", evidence)
        private_key = (
            "prefix " * 100 + "-----BEGIN TEST PRIVATE KEY-----" + "secret-material " * 100
            + "-----END TEST PRIVATE KEY----- visible-target " + "tail " * 100
        )
        evidence = session_common.mask_and_shorten(private_key, queries=("visible-target",))
        self.assertIn("[REDACTED_PRIVATE_KEY]", evidence)
        self.assertIn("visible-target", evidence)
        self.assertNotIn("secret-material", evidence)

    def test_centered_evidence_respects_limits_and_text_edges(self):
        for raw in ("needle " + "x" * 700, "x" * 700 + " needle", "short needle"):
            for limit in (0, 1, 2, 3, 20, 300):
                with self.subTest(raw=raw[:20], limit=limit):
                    evidence = session_common.mask_and_shorten(raw, limit, queries=("needle",))
                    self.assertLessEqual(len(evidence), limit)
                    if limit >= 20:
                        self.assertIn("needle", evidence)
                    if len(raw) <= limit:
                        self.assertEqual(evidence, raw)

    def test_metadata_helper_preserves_string_api_and_limits(self):
        helper = session_common
        for limit in [-1, 0, 1, 2, 3, 10, 300]:
            for text in ["", "…", "needle " + "x" * 1000]:
                with self.subTest(limit=limit, text_length=len(text)):
                    evidence, truncated = helper.mask_and_shorten_with_metadata(
                        text, limit, ("needle",))
                    self.assertEqual(evidence, helper.mask_and_shorten(text, limit, ("needle",)))
                    self.assertLessEqual(len(evidence), max(0, limit))
                    self.assertEqual(truncated, len(text) > max(0, limit))


if __name__ == "__main__":
    unittest.main()

"""Bounded batch aggregation uses the same event semantics as single search."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import test_session_search as fixtures
from test_session_search import SCRIPT, fixture_tree, header, message, session_search, write_session


class SessionBatchTests(unittest.TestCase):
    NOW = fixtures.SessionSearchTests.NOW

    def args(self, root, project, *flags):
        scope = [] if '--all-projects' in flags else ['--cwd', str(project)]
        return session_search.build_parser().parse_args([
            '--sessions-root', str(root), *scope, *flags,
        ])

    def batch(self, root, project, filters, *flags):
        options = [option for item in filters for option in ('--batch-filter', json.dumps(item))]
        return session_search.aggregate(self.args(root, project, *flags, *options), now=self.NOW)

    def test_batch_matches_individual_summaries_and_shared_warnings(self):
        filters = [
            {}, {'query': ['failure']}, {'query': ['failure', 'repeated'], 'role': ['TOOLRESULT']},
            {'tool': ['bash', 'read'], 'error': True}, {'skill': ['ALPHA']},
            {'role': ['assistant'], 'query': ['not present']}, {'query': ['failure']},
            {'skill': ['alpha'], 'role': ['toolresult'], 'error': False},
        ]
        with fixture_tree() as (root, project, _, _, _, current):
            with patch.dict(os.environ, {'PI_SESSION_FILE': str(current)}):
                result = self.batch(root, project, filters, '--days', '7')
                for index, spec in enumerate(filters, 1):
                    flags = ['--days', '7']
                    for key, value in spec.items():
                        if key == 'error':
                            if value:
                                flags.append('--error')
                        else:
                            for item in value:
                                flags.extend(['--' + key, item])
                    single = session_search.aggregate(self.args(root, project, *flags), now=self.NOW)
                    self.assertEqual(result['batches'][index - 1], {
                        'filter_index': index, 'summary': single['summary'],
                    })
                    self.assertEqual(result['warnings'], single['warnings'])
            self.assertEqual(result['mode'], 'batch')
            self.assertEqual(result['summary']['filters_returned'], 8)
            self.assertEqual(result['summary']['current_session_files_excluded'], 1)
            self.assertFalse(result['evidence_included'])
            self.assertEqual(result['results'], [])
            serialized = json.dumps(result)
            for private in (str(root), str(project), 'session-a', 'TOPSECRET', 'hunter2', 'not present'):
                self.assertNotIn(private, serialized)

    def test_opens_each_file_and_builds_events_only_once(self):
        with fixture_tree() as (root, project, _, primary, other, current):
            opens = Counter()
            original_open = Path.open

            def counted_open(path, *args, **kwargs):
                opens[path] += 1
                return original_open(path, *args, **kwargs)

            with patch.dict(os.environ, {'PI_SESSION_FILE': str(current)}), \
                    patch.object(Path, 'open', counted_open), \
                    patch.object(session_search, 'events_for_entry', wraps=session_search.events_for_entry) as events:
                result = self.batch(root, project, [{}, {'query': ['failure']}, {'skill': ['alpha']}])
            self.assertEqual(opens, {primary: 1, other: 1})
            self.assertEqual(events.call_count, result['summary']['entries_eligible'])
            self.assertEqual(result['summary']['entries_scanned'], 5)

    def test_shared_archive_project_and_current_scope(self):
        with fixture_tree() as (root, project, other_project, _, _, current):
            archive = root.parent / 'archive'
            archived = archive / 'current.jsonl'
            write_session(archived, header('archive-current', project), [
                message('x', None, '2026-08-14T00:00:00Z', 'user', 'archive-only')
            ])
            write_session(archive / 'other.jsonl', header('archive-other', other_project), [
                message('y', None, '2026-08-14T00:00:00Z', 'user', 'archive-only')
            ])
            flags = ['--additional-sessions-root', str(archive)]
            with patch.dict(os.environ, {'PI_SESSION_FILE': str(archived)}):
                excluded = self.batch(root, project, [{'query': ['archive-only']}], *flags)
                included = self.batch(root, project, [{'query': ['archive-only']}], *flags, '--include-current')
                all_projects = self.batch(root, project, [{'query': ['archive-only']}], *flags, '--all-projects')
            self.assertEqual(excluded['batches'][0]['summary']['matched_sessions'], 0)
            self.assertEqual(included['batches'][0]['summary']['matched_sessions'], 1)
            self.assertEqual(all_projects['batches'][0]['summary']['matched_sessions'], 1)

    def test_partial_read_and_error_session_counts_remain_independent(self):
        with fixture_tree() as (root, project, _, _, _, current):
            damaged = root / 'a' / 'damaged.jsonl'
            errors = [message(str(i), str(i - 1) if i else None, '2026-08-14T00:00:00Z',
                              'toolResult', 'failure', toolName='bash', isError=True) for i in range(2)]
            write_session(damaged, header('damaged', project), errors)
            with damaged.open('ab') as stream:
                stream.write(b'x' * 10000 + b'\xff\n')
            with patch.dict(os.environ, {'PI_SESSION_FILE': str(current)}):
                result = self.batch(root, project, [
                    {'tool': ['bash'], 'error': True}, {'role': ['user']}, {'query': ['absent']},
                ])
            errors_summary, user_summary, absent_summary = [item['summary'] for item in result['batches']]
            self.assertEqual(errors_summary['tool_errors'], {'bash': 3})
            self.assertEqual(errors_summary['tool_error_sessions'], {'bash': 2})
            self.assertEqual(errors_summary['matched_sessions'], 2)
            self.assertEqual(user_summary['matched_sessions'], 1)
            self.assertEqual(absent_summary['matched_sessions'], 0)
            self.assertEqual(result['warnings']['by_kind'], {'invalid_json_line': 1, 'unreadable_file': 1})
            self.assertEqual(result['results'], [])

    def test_batch_never_opens_out_of_root_symlink(self):
        with fixture_tree() as (root, project, _, _, _, _):
            outside = root.parent / 'private.jsonl'
            write_session(outside, header('outside', project), [])
            link = root / 'escape.jsonl'
            link.symlink_to(outside)
            original_open = Path.open

            def guarded_open(path, *args, **kwargs):
                self.assertNotEqual(path.resolve(), outside)
                return original_open(path, *args, **kwargs)

            with patch.object(Path, 'open', guarded_open):
                self.batch(root, project, [{}, {'error': True}])

    def test_invalid_batch_is_rejected_before_storage(self):
        invalid = [
            ['--batch-filter', '{}'] * 9,
            ['--batch-filter', '[]'], ['--batch-filter', 'null'], ['--batch-filter', '{'],
            ['--batch-filter', '{"query": [], "query": ["private"]}'],
            ['--batch-filter', '{"cwd": "/private"}'],
            ['--batch-filter', '{"error": 1}'], ['--batch-filter', '{"query": "private"}'],
            ['--batch-filter', '{"tool": [1]}'], ['--batch-filter', '{"role": null}'],
            ['--batch-filter', json.dumps({'query': ['x' * 257]})],
            ['--batch-filter', json.dumps({'query': ['x'] * 33})],
            ['--batch-filter', ' ' * 4097],
            ['--batch-filter', '[' * 1500 + ']' * 1500],
        ]
        invalid += [['--batch-filter', '{}', *flags] for flags in [
            ['--include-evidence'], ['--query', 'private'], ['--role', 'user'],
            ['--tool', 'bash'], ['--skill', 'alpha'], ['--error'],
        ]]
        with patch.object(session_search, 'discover_session_files', side_effect=AssertionError('storage accessed')):
            for flags in invalid:
                with self.subTest(flags=flags), self.assertRaises(ValueError):
                    session_search.aggregate(self.args('/unused', '/unused', *flags))

    def test_cli_batch_summary_and_private_input_error(self):
        with fixture_tree() as (root, project, _, _, _, _):
            base = [sys.executable, '-B', str(SCRIPT), '--sessions-root', str(root), '--cwd', str(project)]
            result = subprocess.run(base + ['--batch-filter', '{"query":["failure"]}', '--summary-only'],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['mode'], 'batch')
            invalid = subprocess.run(base + ['--batch-filter', '{"private-key":"DO_NOT_ECHO"}'],
                                     text=True, capture_output=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(json.loads(invalid.stdout)['error']['code'], 'INVALID_ARGUMENT')
            self.assertNotIn('DO_NOT_ECHO', invalid.stdout + invalid.stderr)
            self.assertEqual(invalid.stderr, '')


if __name__ == '__main__':
    unittest.main()

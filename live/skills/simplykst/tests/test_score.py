import copy
import runpy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal

calculate = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/score.py'))['calculate']


def fixture(view='trading'):
    ids = 'MLEFVS' if view == 'trading' else 'VQGBRO'
    weights = [20, 15, 20, 20, 10, 15] if view == 'trading' else [20, 25, 20, 15, 10, 10]
    return {'sector': 'general', 'essentials_ready': True, 'factors': [
        {'id': id_, 'weight': weight, 'score': 4, 'grade': 'A',
         'reason': 'Verified test evidence', 'sources': ['S1:metric1', 'S1:metric2']}
        for id_, weight in zip(ids, weights)]}


class ScoreTests(unittest.TestCase):
    def test_full(self):
        for view in ('trading', 'investing'):
            result = calculate(view, fixture(view))
            self.assertEqual(result['recommendation'], '4.00')
            self.assertEqual(result['confidence'], 'high')
            self.assertEqual(result['uncapped_missing_range'], ['4.00', '4.00'])

    def test_unequal_scores_weighted_mean(self):
        # Hand-calculated weighted sums: Trading 230, Investing 200;
        # both differ from the unweighted mean of 2.50.
        for view, expected in [('trading', '2.30'), ('investing', '2.00')]:
            with self.subTest(view=view):
                data = fixture(view)
                for f, score in zip(data['factors'], [0, 1, 2, 3, 4, 5]):
                    f['score'] = score
                result = calculate(view, data)
                self.assertEqual(result['observed_mean'], expected)
                self.assertEqual(result['recommendation'], expected)
                self.assertEqual(result['uncapped_missing_range'], [expected, expected])

    def test_unequal_scores_with_missing_factor(self):
        # Removing the zero-score, 20%-weight factor leaves sums unchanged:
        # 230/80 = 2.875 -> 2.88; 200/80 = 2.50 (not simple mean 3.00).
        for view, mean, bounds in [('trading', '2.88', ['2.30', '3.30']),
                                   ('investing', '2.50', ['2.00', '3.00'])]:
            with self.subTest(view=view):
                data = fixture(view)
                for f, score in zip(data['factors'], [None, 1, 2, 3, 4, 5]):
                    f['score'] = score
                result = calculate(view, data)
                self.assertEqual(result['coverage_pct'], '80.00')
                self.assertEqual(result['status'], 'provisional')
                self.assertEqual(result['observed_mean'], mean)
                self.assertEqual(result['recommendation'], mean)
                self.assertEqual(result['uncapped_missing_range'], bounds)
                self.assertIsNone(result['contributions_full_weight'][data['factors'][0]['id']])
        # Also remove a nonzero score: the numerator and denominator both change.
        # Trading (230-15)/85; Investing (200-25)/75.
        for view, mean, coverage, bounds in [
            ('trading', '2.53', '85.00', ['2.15', '2.90']),
            ('investing', '2.33', '75.00', ['1.75', '3.00']),
        ]:
            with self.subTest(view=view, missing='nonzero'):
                data = fixture(view)
                for f, score in zip(data['factors'], [0, None, 2, 3, 4, 5]):
                    f['score'] = score
                result = calculate(view, data)
                self.assertEqual(result['observed_mean'], mean)
                self.assertEqual(result['recommendation'], mean)
                self.assertEqual(result['coverage_pct'], coverage)
                self.assertEqual(result['uncapped_missing_range'], bounds)

    def test_contribution_display_rounding(self):
        data = fixture()
        for f in data['factors']:
            f['score'] = 3.5
        result = calculate('trading', data)
        self.assertEqual(result['recommendation'], '3.50')
        self.assertEqual(result['contributions_full_weight'],
                         dict(zip('MLEFVS', ['0.70', '0.53', '0.70', '0.70', '0.35', '0.53'])))
        self.assertEqual(sum(Decimal(v) for v in result['contributions_full_weight'].values()),
                         Decimal('3.51'))

    def test_missing_not_zero(self):
        data = fixture()
        data['factors'][0]['score'] = None
        result = calculate('trading', data)
        self.assertEqual(result['recommendation'], '4.00')
        self.assertEqual(result['status'], 'provisional')
        self.assertEqual(result['uncapped_missing_range'], ['3.20', '4.20'])

    def test_coverage_boundary(self):
        data = fixture()
        for i in (1, 5):
            data['factors'][i]['score'] = None
        self.assertEqual(calculate('trading', data)['status'], 'provisional')
        data['factors'][4]['score'] = None
        self.assertEqual(calculate('trading', data)['status'], 'withheld')

    def test_missing_essentials(self):
        data = fixture()
        data['essentials_ready'] = False
        self.assertIsNone(calculate('trading', data)['recommendation'])

    def test_all_missing(self):
        data = fixture()
        for f in data['factors']:
            f['score'] = None
        result = calculate('trading', data)
        self.assertIsNone(result['observed_mean'])
        self.assertEqual(result['uncapped_missing_range'], ['0.00', '5.00'])

    def test_risk_caps(self):
        for view, expected in [('trading', '2.00'), ('investing', '1.00')]:
            data = fixture(view)
            data.update(confirmed_risks=['going_concern'], risk_evidence=['S2'])
            self.assertEqual(calculate(view, data)['recommendation'], expected)
        data = fixture()
        data.update(confirmed_risks=['halted'], risk_evidence=['S2'])
        self.assertEqual(calculate('trading', data)['recommendation'], '0.00')
        data['essentials_ready'] = False
        self.assertIsNone(calculate('trading', data)['recommendation'])

    def test_confidence(self):
        data = fixture()
        for f in data['factors']:
            f['grade'] = 'B'
        self.assertEqual(calculate('trading', data)['confidence'], 'medium')
        for f in data['factors']:
            f['grade'] = 'C'
        self.assertEqual(calculate('trading', data)['confidence'], 'low')

    def test_invalid(self):
        base = fixture()
        for field, value in [('weight', 21), ('score', 5.5), ('score', True),
                             ('score', float('nan')), ('score', 3.3),
                             ('grade', 'X'), ('sources', []), ('id', 'X')]:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(base)
                data['factors'][0][field] = value
                with self.assertRaises(ValueError):
                    calculate('trading', data)


class RegressionTests(unittest.TestCase):
    def test_confidence_independent_of_readiness(self):
        d = fixture()
        d['essentials_ready'] = False
        r = calculate('trading', d)
        self.assertEqual(r['confidence'], 'high')
        self.assertEqual(r['withheld_reasons'], ['essentials_not_ready'])

    def test_confidence_boundaries(self):
        d = fixture()
        d['factors'][0]['grade'] = 'B'
        self.assertEqual(calculate('trading', d)['confidence'], 'high')
        d['factors'][4]['grade'] = 'B'
        self.assertEqual(calculate('trading', d)['confidence'], 'medium')
        d['factors'][0]['grade'] = 'C'
        self.assertEqual(calculate('trading', d)['confidence'], 'medium')
        d['factors'][4]['grade'] = 'C'
        self.assertEqual(calculate('trading', d)['confidence'], 'low')
        d = fixture()
        d['factors'][1]['score'] = None
        self.assertEqual(calculate('trading', d)['status'], 'rated')

    def test_risk_precedence_and_restriction(self):
        for flag in ['halted', 'delisting_confirmed']:
            for view in ['trading', 'investing']:
                d = fixture(view)
                d.update(confirmed_risks=[flag, 'going_concern'], risk_evidence=['S2'])
                r = calculate(view, d)
                self.assertEqual(r['recommendation'], '0.00' if view == 'trading' else None)
                if view == 'investing':
                    self.assertIn('market_restricted', r['withheld_reasons'])
        d = fixture('investing')
        d.update(confirmed_risks=['material_qualified_audit'], risk_evidence=['S2'])
        self.assertEqual(calculate('investing', d)['recommendation'], '2.00')

    def test_invalid_schema(self):
        for patch in [{'sector': 'unknown'}, {'sector': {'general': 90}},
                      {'sector': {'general': True}}, {'essentials_ready': 1},
                      {'confirmed_risks': ['unknown']}, {'confirmed_risks': [{}]},
                      {'confirmed_risks': ['default']},
                      {'confirmed_risks': ['default'], 'risk_evidence': 'S2'},
                      {'factors': None}]:
            with self.subTest(patch=patch):
                d = fixture(); d.update(patch)
                with self.assertRaises(ValueError): calculate('trading', d)
        for sources in ['S1', [], [''], [2], ['S1', ' S1 ']]:
            d = fixture(); d['factors'][0]['sources'] = sources
            with self.assertRaises(ValueError): calculate('trading', d)

    def test_sector_limits_and_mixing(self):
        root = Path(__file__).parents[1]
        profiles = json.loads((root / 'references/sector-weights.json').read_text())
        for sector, p in profiles.items():
            for view in ['trading', 'investing']:
                d = fixture(view); d['sector'] = sector
                for f in d['factors']: f['weight'] = p[view][f['id']]
                self.assertEqual(calculate(view, d)['recommendation'], '4.00')
        d = fixture(); d['sector'] = {'general': 50, 'bank': 50}
        for f in d['factors']:
            f['weight'] = (profiles['general']['trading'][f['id']] + profiles['bank']['trading'][f['id']]) / 2
        self.assertEqual(calculate('trading', d)['recommendation'], '4.00')
        d = fixture(); d['weight_reason'] = 'Company exposure'
        d['factors'][0]['weight'] += 10; d['factors'][2]['weight'] -= 10
        calculate('trading', d)
        d['factors'][0]['weight'] += 1; d['factors'][2]['weight'] -= 1
        with self.assertRaises(ValueError): calculate('trading', d)
        d = fixture(); d['weight_reason'] = 'Company exposure'; d['factors'][0]['weight'] += 1
        with self.assertRaisesRegex(ValueError, 'sum to 100'): calculate('trading', d)

    def test_profile_documentation(self):
        root = Path(__file__).parents[1]
        profiles = json.loads((root / 'references/sector-weights.json').read_text())
        doc = (root / 'references/methodology.md').read_text()
        for p in profiles.values():
            row = '| ' + p['label'] + ' | ' + ' | '.join(str(p[v][i]) for v, ids in [('trading', 'MLEFVS'), ('investing', 'VQGBRO')] for i in ids) + ' |'
            self.assertIn(row, doc)

    def cli(self, content=None, args=None):
        script = Path(__file__).resolve().parents[1] / 'scripts/score.py'
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input.json'
            path.write_text(content or '', encoding='utf-8')
            return subprocess.run([sys.executable, '-B', str(script)] + (args if args is not None else [str(path)]), cwd=tmp, capture_output=True, text=True)

    def test_cli(self):
        for views in [('trading',), ('investing',), ('trading', 'investing')]:
            r = self.cli(json.dumps({v: fixture(v) for v in views}))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(set(json.loads(r.stdout)), set(views))
        for value in ['{', 'null', '[]', '{}', '{"other": {}}', '{"trading": null}']:
            r = self.cli(value)
            self.assertEqual(r.returncode, 2)
            self.assertNotIn('Traceback', r.stderr)
        d = fixture(); d['essentials_ready'] = 1
        r = self.cli(json.dumps({'trading': d}))
        self.assertIn('essentials_ready', r.stderr)
        self.assertEqual(self.cli(args=['--help']).returncode, 0)
        self.assertEqual(self.cli(args=[]).returncode, 2)

    def test_unknown_fields_rejected(self):
        marker = 'TEST_PRIVATE_FIELD'
        for view in ['trading', 'investing']:
            for target in ['perspective', 'factor', 'missing_factor']:
                with self.subTest(view=view, target=target):
                    d = fixture(view)
                    if target == 'perspective':
                        d[marker] = 'ignored before validation fix'
                    else:
                        d['factors'][0][marker] = 'unexpected'
                        if target == 'missing_factor':
                            d['factors'][0]['score'] = None
                    with self.assertRaisesRegex(ValueError, 'Unknown .* field'):
                        calculate(view, d)
                    r = self.cli(json.dumps({view: d}))
                    self.assertEqual(r.returncode, 2)
                    self.assertEqual(r.stdout, '')
                    self.assertNotIn(marker, r.stderr)
                    self.assertNotIn('Traceback', r.stderr)

    def test_risk_field_typo_rejected(self):
        for view, capped in [('trading', '2.00'), ('investing', '1.00')]:
            with self.subTest(view=view):
                d = fixture(view)
                d.update(confirmed_risks=['going_concern'], risk_evidence=['S2'])
                self.assertEqual(calculate(view, d)['recommendation'], capped)
                d['confirmed_risk'] = d.pop('confirmed_risks')
                r = self.cli(json.dumps({view: d}))
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, '')
                self.assertIn('Unknown perspective field', r.stderr)

    def test_duplicate_json_keys_rejected_at_every_depth(self):
        d = fixture()
        d.update(confirmed_risks=['going_concern'], risk_evidence=['S2'])
        encoded = json.dumps(d)
        cases = [
            # Risk cleared by a later duplicate (original reproduction).
            '{"trading": ' + encoded[:-1] + ', "confirmed_risks": []}}',
            # Duplicate top-level perspective.
            '{"trading": ' + encoded + ', "trading": ' + json.dumps(fixture()) + '}',
            # Duplicate factor score; escaped spelling also decodes to score.
            '{"trading": ' + encoded.replace('"score": 4', '"score": 0, "sco\\u0072e": 4', 1) + '}',
            # Nested sector mixture, with identical repeated values.
            '{"trading": ' + encoded.replace('"sector": "general"',
                '"sector": {"general": 100, "general": 100}', 1) + '}',
            # Unknown repeated key must not be echoed in diagnostics.
            '{"TEST_PRIVATE_FIELD": 1, "TEST_PRIVATE_FIELD": 2}',
        ]
        for index, content in enumerate(cases):
            with self.subTest(case=index):
                r = self.cli(content)
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stdout, '')
                self.assertIn('Duplicate JSON object key', r.stderr)
                self.assertNotIn('TEST_PRIVATE_FIELD', r.stderr)
                self.assertNotIn('Traceback', r.stderr)

    def test_cli_does_not_echo_input(self):
        secret_marker = 'TEST_PRIVATE_MARKER'
        r = self.cli('{"' + secret_marker + '":')
        self.assertNotIn(secret_marker, r.stderr)
        self.assertNotIn(secret_marker, self.cli(args=['/nonexistent/' + secret_marker]).stderr)
        self.assertNotIn(secret_marker, self.cli(args=['--' + secret_marker]).stderr)

    def test_example(self):
        path = Path(__file__).parents[1] / 'examples/input.json'
        r = self.cli(path.read_text())
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == '__main__':
    unittest.main()

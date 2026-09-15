import copy
import runpy
import unittest
from pathlib import Path

calculate = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/score.py'))['calculate']


def fixture(view='trading'):
    ids = 'MLEFVS' if view == 'trading' else 'VQGBRO'
    weights = [20, 15, 20, 20, 10, 15]
    return {'essentials_ready': True, 'factors': [
        {'id': id_, 'weight': weight, 'score': 4, 'grade': 'A',
         'reason': 'Verified test evidence', 'sources': ['S1']}
        for id_, weight in zip(ids, weights)]}


class ScoreTests(unittest.TestCase):
    def test_full(self):
        for view in ('trading', 'investing'):
            result = calculate(view, fixture(view))
            self.assertEqual(result['recommendation'], '4.00')
            self.assertEqual(result['confidence'], 'high')
            self.assertEqual(result['uncapped_missing_range'], ['4.00', '4.00'])

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


if __name__ == '__main__':
    unittest.main()

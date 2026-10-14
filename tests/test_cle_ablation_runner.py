import unittest
from unittest.mock import patch

from methods.cle_ablation.runner import ARMS, arm_spec, public_contract, summarize, run_one


class CleAblationRunnerTests(unittest.TestCase):
    def test_arm_budget_and_memory_boundaries(self):
        self.assertEqual(len(ARMS), 8)
        self.assertEqual([arm_spec(x).attempts for x in ARMS], [1, 1, 1, 2, 2, 2, 2, 2])
        self.assertEqual([arm_spec(x).memory for x in ARMS],
                         ['none', 'none', 'none', 'none', 'phase1', 'full', 'full', 'full'])
        self.assertFalse(arm_spec('P5').reanalyze)
        self.assertTrue(arm_spec('P6').reanalyze)
        self.assertFalse(arm_spec('P6').negative)
        self.assertTrue(arm_spec('P7').negative)

    def test_contract_excludes_answers_and_tests(self):
        row = {'ID': 'CWE-1_x', 'Problem': 'make f', 'Entry_Point': 'f',
               'Secure Code': 'SECRET', 'Functional Test': 'SECRET', 'Insecure Code': 'SECRET'}
        value = public_contract('Base', row)
        self.assertNotIn('SECRET', str(value))
        self.assertEqual(value['task_id'], 'Base:CWE-1_x')

    def test_summary_keeps_unmeasured_separate(self):
        rows = [
            {'task_id': 'a', 'arm': 'P0', 'attempts': [{'joint': False, 'measured': True}]},
            {'task_id': 'b', 'arm': 'P0', 'attempts': [{'joint': False, 'measured': False}]},
            {'task_id': 'a', 'arm': 'P1', 'attempts': [{'joint': True, 'measured': True}]},
        ]
        result = summarize(rows)
        self.assertEqual(result['arms']['P0']['unmeasured'], 1)
        self.assertEqual(result['paired_vs_P0']['P1']['pairs'], 1)
        self.assertEqual(result['paired_vs_P0']['P1']['new_only'], 1)

    def test_final_test_does_not_drive_repair_or_selection(self):
        row = {'ID': 'CWE-1_x', 'Problem': 'make f', 'Entry_Point': 'f'}
        seen = []
        def generation(arm, contract, request, provider, **kwargs):
            seen.append(kwargs)
            return {'code': 'def f(): return 1'}
        def validation(task, code, timeout):
            return {'functional': True, 'security': True, 'joint': True, 'environment_error': False,
                    'evidence': {'functional': {'status': 'pass', 'details': 'SECRET'},
                                 'security': {'status': 'pass', 'details': 'SECRET'}}}
        with patch('methods.cle_ablation.runner.generate', side_effect=generation), patch(
                'methods.sct_trajectory.run_plus_frozen_comparison.evaluate', side_effect=validation):
            result = run_one('Base', row, 'P3', None, {'none': []})
        self.assertEqual(len(seen), 2)
        self.assertIsNone(seen[1]['feedback'])
        self.assertNotIn('SECRET', str(result))


if __name__ == '__main__':
    unittest.main()

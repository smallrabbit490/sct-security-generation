"""三策略按族配对及同档复用的手算检验，不调用模型。"""
import tempfile
import unittest
from pathlib import Path

from configs.cle_weekly_analysis_20261027.policy_gate_analysis import analyze, run
from tests.test_cle_weekly_retest_analysis import row


class PolicyGateAnalysisTest(unittest.TestCase):
    def test_shared_level_reuse_does_not_double_count_actual_generation(self):
        rows = []
        for repeat in (1, 2):
            for policy in ('fixed', 'rule', 'classifier'):
                item = row('1', repeat, policy, policy != 'fixed', family='family')
                level = 'L0' if policy == 'fixed' else 'L2'
                item.update(selected_level=level, first_start_identity=f'start_r{repeat}',
                    canonical_generation_cell=f'1_r{repeat}_{level}', result_reused=policy == 'classifier')
                rows.append(item)
        result, cases = analyze(rows, planned_tasks=1)
        self.assertEqual(result['logical_policy_cells'], 6)
        self.assertEqual(result['unique_task_repeat_level_runs'], 4)
        self.assertEqual(result['canonical_generation_cells'], 4)
        self.assertEqual(result['reused_logical_cells'], 2)
        self.assertEqual(result['common_first_start']['verified_groups'], 2)
        fixed, rule = result['primary_comparisons']
        self.assertEqual((fixed['wins'], fixed['losses'], fixed['families']), (2, 0, 1))
        self.assertEqual(rule['difference'], 0)
        self.assertEqual(fixed['p_holm_two_primary'], 1)
        self.assertFalse(result['statistical_direction_supported'])
        self.assertTrue(all(case['cause'] is None for case in cases))

    def test_missing_measurement_is_not_a_joint_loss(self):
        items = []
        for policy in ('fixed', 'rule', 'classifier'):
            item = row('1', 1, policy, policy != 'fixed', measured=policy != 'classifier')
            item.update(selected_level='L2', first_start_identity='same')
            items.append(item)
        result, cases = analyze(items, planned_tasks=1)
        self.assertTrue(all(value['measured_pairs'] == 0 for value in result['primary_comparisons']))
        self.assertTrue(all(value['p_family_swap'] is None for value in result['primary_comparisons']))
        self.assertTrue(all(case['category'] == 'missing_measurement' for case in cases))

    def test_no_real_rows_remains_not_started(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run(Path(folder))
            self.assertEqual(result['status'], 'not_started')
            self.assertIsNone(result['results'])
            self.assertEqual(result['paid_calls_by_analysis'], 0)


if __name__ == '__main__':
    unittest.main()

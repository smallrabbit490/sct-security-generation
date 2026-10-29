"""四臂主要两比较与独立统计簇的零API手算验证。"""
import tempfile
import unittest
from pathlib import Path

from configs.cle_weekly_analysis_20261027.gate_analysis import analyze, run
from tests.test_cle_weekly_retest_analysis import row


class GateAnalysisTest(unittest.TestCase):
    def test_primary_holm_two_keeps_repeats_in_one_family_cluster(self):
        rows = [row('1', repeat, arm, arm == 'Q2', family='same_family')
                for repeat in (1, 2) for arm in ('Q0', 'Q1', 'Q2', 'Q3')]
        result, mechanisms = analyze(rows, planned_tasks=1)
        self.assertEqual(len(result['primary_comparisons']), 2)
        self.assertEqual({c['control'] for c in result['primary_comparisons']}, {'Q1', 'Q3'})
        self.assertTrue(all(c['families'] == 1 and c['measured_pairs'] == 2 for c in result['primary_comparisons']))
        self.assertTrue(all(c['p_holm_two_primary'] == 1. for c in result['primary_comparisons']))
        self.assertFalse(result['statistical_direction_supported'])
        self.assertEqual(result['secondary_Q0_reference']['control'], 'Q0')
        self.assertEqual(sum(m['primary_controlled_comparison'] for m in mechanisms), 4)

    def test_no_real_four_arm_rows_only_not_started(self):
        with tempfile.TemporaryDirectory() as path:
            summary = run(Path(path))
            self.assertEqual(summary['status'], 'not_started')
            self.assertIsNone(summary['results'])
            self.assertEqual(summary['paid_calls_by_analysis'], 0)


if __name__ == '__main__':
    unittest.main()

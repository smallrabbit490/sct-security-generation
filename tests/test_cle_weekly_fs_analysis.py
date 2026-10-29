"""手算功能安全四象限、配对取舍和未执行分母，零API。"""
from pathlib import Path
import tempfile
import unittest
import json

from configs.cle_weekly_analysis_20261027.fs_analysis import analyze, quadrant, run, logical_cost_breakdown


def row(arm, functional, security, measured=True):
    attempt = {'functional': functional, 'security': security, 'joint': measured and functional and security,
        'measured': measured, 'generation': {'cards': []},
        'retrieval_trace': {'status': 'completed', 'pre_view_selected_ids': ['same-source']}}
    return {'task_id': '1', 'repeat': 1, 'family_id': 'family', 'condition': arm,
            'attempts': [attempt], 'final': attempt}


class FSAnalysisTest(unittest.TestCase):
    def test_security_gain_functional_loss_is_observation_not_automatic_cause(self):
        rows = [row('BM', True, False), row('BFS', False, True), row('BF', True, False), row('BS', False, True)]
        result, cases = analyze(rows, planned_tasks=1)
        primary = result['comparisons'][0]
        self.assertTrue(primary['primary'])
        self.assertEqual(primary['security_gain_with_functional_loss_observations'], 1)
        self.assertEqual(primary['quadrant_transitions_control_to_treated']['functional_only']['security_only'], 1)
        self.assertEqual(result['common_first_source_selection']['verified_groups'], 1)
        self.assertTrue(all(c['cause'] is None for c in cases))
        self.assertEqual(result['arms']['BM']['final']['pending_tasks'], 1)

    def test_unmeasured_is_not_both_failed_and_no_rows_have_no_score(self):
        self.assertEqual(quadrant({'measured': False, 'functional': False, 'security': False}), 'unmeasured')
        with tempfile.TemporaryDirectory() as d:
            result = run(Path(d))
            self.assertEqual(result['status'], 'not_started')
            self.assertIsNone(result['results'])
            self.assertEqual(result['paid_calls_by_analysis'], 0)

    def test_shared_and_material_costs_not_duplicated_across_recovery_segments(self):
        with tempfile.TemporaryDirectory() as d:
            roots = [Path(d) / 'a', Path(d) / 'b']
            for root in roots:
                for namespace, tokens in [('shared_initial_1_r1', 10), ('material_view_source', 20), ('1_r1_BM', 30)]:
                    p = root / 'journals' / namespace / 'requests/call.json'
                    p.parent.mkdir(parents=True)
                    p.write_text(json.dumps({'identity': 'same', 'status': 'completed',
                        'response': {'usage': {'total_tokens': tokens}}}), encoding='utf-8')
            result = logical_cost_breakdown(roots)['namespaces']
            self.assertEqual(result['shared_initial']['known_reported_tokens'], 10)
            self.assertEqual(result['source_partition']['known_reported_tokens'], 20)
            self.assertEqual(result['BM']['known_reported_tokens'], 30)


if __name__ == '__main__':
    unittest.main()

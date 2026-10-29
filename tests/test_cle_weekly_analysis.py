"""手算学习行验证零API阶段分析；不联网、不执行生成代码。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from configs.cle_weekly_analysis_20261027.analysis import collect_rows, metrics, summarize, cost_snapshot


def row(task='1', q_after=0., visits=1):
    attempt = {'functional': True, 'security': True, 'joint': True, 'measured': True,
        'generation': {'retrieved_cards': [{'invariant_id': 'a'}], 'cards': [{'invariant_id': 'a'}]}}
    return {'task_id': task, 'family_id': 'f'+task, 'attempts': [attempt], 'final': attempt,
        'q_credit_events': [{'credited': True, 'invariant_id': 'a', 'q_before': 0.,
            'q_after': q_after, 'q_visits': visits, 'reward': 1}]}


class LearningAnalysisTest(unittest.TestCase):
    def test_zero_Q_with_feedback_is_covered_and_partial_denominators_are_distinct(self):
        summary, cards, families = summarize([row()], [{'invariant_id': 'a', 'q_value': 0., 'q_visits': 0},
            {'invariant_id': 'b', 'q_value': 0., 'q_visits': 0}], 3)
        self.assertEqual(summary['memory']['covered_after_saved_prefix'], 1)
        self.assertEqual(summary['memory']['covered_with_Q_exactly_zero'], 1)
        self.assertEqual(summary['final']['joint_rate_among_completed'], 1.)
        self.assertAlmostEqual(summary['final']['confirmed_joint_divided_by_planned'], 1/3)
        self.assertEqual(summary['final']['pending_tasks'], 2)
        self.assertEqual(cards['a']['family_ids'], ['f1'])
        self.assertEqual(families['f1']['credit_events'], 1)

    def test_identical_recovery_rows_deduplicate_and_conflicts_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory)/'a', Path(directory)/'b']
            for root in roots:
                (root/'task_rows').mkdir(parents=True)
                (root/'task_rows/1.json').write_text(json.dumps(row()), encoding='utf-8')
            rows, paths, duplicates = collect_rows(roots, ['1', '2'])
            self.assertEqual(len(rows), 1)
            self.assertEqual(duplicates, 1)
            modified = row(q_after=.3)
            (roots[-1]/'task_rows/1.json').write_text(json.dumps(modified), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'conflicting_completed_row'):
                collect_rows(roots, ['1', '2'])

    def test_missing_measurement_is_not_a_confirmed_joint_failure(self):
        result = metrics([{'functional': False, 'security': False, 'joint': False, 'measured': False}], 3)
        self.assertEqual(result['unmeasured_completed'], 1)
        self.assertIsNone(result['joint_rate_among_measured'])
        self.assertEqual(result['pending_tasks'], 2)

    def test_latest_cumulative_budget_is_not_summed_across_segments(self):
        with tempfile.TemporaryDirectory() as directory:
            roots = [Path(directory)/'a', Path(directory)/'b']
            for count, root in enumerate(roots, start=1):
                root.mkdir()
                budget = {'known_reported_tokens': count*10, 'transport_attempts_including_prior': count,
                    'charged_tokens_including_unknown_and_inflight_bounds': count*20,
                    'entries': [{'status': 'reported', 'usage': {'total_tokens': 10}}] +
                        ([{'status': 'prepared', 'usage': None}] if count == 2 else [])}
                (root/'budget.json').write_text(json.dumps(budget), encoding='utf-8')
            cost = cost_snapshot(roots)
            self.assertEqual(cost['physical_HTTP_including_prior'], 2)
            self.assertEqual(cost['known_reported_tokens'], 20)
            self.assertEqual(cost['unknown_or_inflight_HTTP'], 1)


if __name__ == '__main__':
    unittest.main()

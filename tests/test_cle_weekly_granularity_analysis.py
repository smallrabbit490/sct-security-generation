"""五档标签与family隔离路由训练的手算验证，零模型请求。"""
import copy
import unittest
from unittest.mock import patch

from configs.cle_weekly_analysis_20261027 import granularity_analysis as analysis


class GranularityAnalysisTest(unittest.TestCase):
    def fixture(self):
        tasks = {str(i): {'index': i, 'family_id': 'f'+str(i//2),
            'task_description': {'description': 'Keep public behavior', 'arguments': 'value: str'}} for i in range(8)}
        rows = []
        for tid in tasks:
            for level in analysis.LEVELS:
                for repeat in (1, 2):
                    success = level == ('L1' if int(tid) % 2 else 'L2')
                    final = {'functional': success, 'security': success, 'joint': success, 'measured': True}
                    rows.append({'task_id': tid, 'family_id': tasks[tid]['family_id'], 'condition': level,
                        'repeat': repeat, 'usage': {'prompt_tokens': 10+analysis.LEVELS.index(level)},
                        'attempts': [{'generation': {'retrieved_cards': [] if level == 'L0' else [{'invariant_id': 'card'}]}}],
                        'final': final})
        split = {'train_task_ids': [str(i) for i in range(6)], 'development_task_ids': ['6', '7'],
            'family_cv_fold': {'f0': 0, 'f1': 1, 'f2': 2}}
        return rows, tasks, split

    def test_all_failure_unmeasured_and_no_intervention_do_not_become_L0(self):
        rows, tasks, _ = self.fixture()
        for row in rows:
            if row['task_id'] == '0': row['final'].update(functional=False, security=False, joint=False)
            if row['task_id'] == '1': row['attempts'][0]['generation']['retrieved_cards'] = []
            if row['task_id'] == '2' and row['condition'] == 'L4': row['final']['measured'] = False
            if row['task_id'] == '3' and row['condition'] == 'L4':
                row['final'].update(functional=True, security=True, joint=True)
                row['usage']['prompt_tokens'] = None
        labels = {item['task_id']: item for item in analysis.make_labels(rows, tasks)}
        self.assertEqual(labels['0']['label_status'], 'no_stable_success')
        self.assertEqual(labels['1']['label_status'], 'no_memory_intervention')
        self.assertEqual(labels['2']['label_status'], 'unmeasured_outcome')
        self.assertEqual(labels['3']['label_status'], 'unknown_input_cost')
        self.assertTrue(all(labels[tid]['preferred_level'] is None for tid in ('0', '1', '2', '3')))

    def test_development_outcomes_do_not_change_frozen_model(self):
        rows, tasks, split = self.fixture()
        labels = analysis.make_labels(rows, tasks)
        first = analysis.fit_model(rows, tasks, split, labels)
        changed = copy.deepcopy(rows)
        for row in changed:
            if row['task_id'] in ('6', '7'):
                flag = row['condition'] == 'L4'
                row['final'].update(functional=flag, security=flag, joint=flag)
        second = analysis.fit_model(changed, tasks, split, analysis.make_labels(changed, tasks))
        self.assertEqual(first, second)
        self.assertEqual(set(first['fit_task_ids']), set(split['train_task_ids']))
        self.assertNotIn('f3', first['fit_families'])

    def test_cross_validation_never_fits_part_of_held_family(self):
        rows, tasks, split = self.fixture()
        calls = []
        original = analysis.fit_logistic
        def capture(x, y, c):
            calls.append(len(y))
            return original(x, y, c)
        with patch.object(analysis, 'fit_logistic', side_effect=capture):
            model = analysis.fit_model(rows, tasks, split, analysis.make_labels(rows, tasks))
        self.assertEqual(calls[:-1], [4]*9)
        self.assertEqual(calls[-1], 6)
        self.assertEqual(model['type'], 'multinomial_logistic')
        bad = copy.deepcopy(split)
        bad['development_task_ids'] = ['5', '6', '7']
        bad['train_task_ids'] = ['0', '1', '2', '3', '4']
        with self.assertRaisesRegex(ValueError, 'family_training_development_leakage'):
            analysis.fit_model(rows, tasks, bad, analysis.make_labels(rows, tasks))

    def test_development_rule_does_not_look_ahead_to_repair_cards(self):
        rows, tasks, split = self.fixture()
        for row in rows:
            row['attempts'][0]['retrieval_trace'] = {'pre_level_selected_ids': []}
            row['attempts'][0]['generation']['retrieved_cards'] = []
            if row['condition'] != 'L0':
                row['attempts'].append({'generation': {'retrieved_cards': [{'invariant_id': 'repair-only'}]}})
        result = analysis.development_results(rows, tasks, split, {'type': 'constant', 'fixed': 'L2'})
        self.assertTrue(all(item['selected_level'] == 'L0' for item in result['rule']))


if __name__ == '__main__':
    unittest.main()

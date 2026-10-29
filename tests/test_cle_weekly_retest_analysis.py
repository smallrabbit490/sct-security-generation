"""冻结回测的手算配对、重复分组和缺测分母；全部零API。"""
import tempfile
from pathlib import Path
import unittest

from configs.cle_weekly_analysis_20261027.retest_analysis import compare, analyze, run, first_mechanism


def row(task, repeat, condition, joint, family=None, measured=True, cards=('a',), adopted=()):
    attempt = {'functional': joint, 'security': joint, 'joint': joint and measured, 'measured': measured,
        'generation': {'retrieved_cards': [{'invariant_id': key} for key in cards],
                       'cards': [{'invariant_id': key} for key in adopted]},
        'retrieval_trace': {'status': 'completed', 'query_hash': 'query', 'candidate_ids': ['a', 'b'],
            'scores': [{'id': 'a', 'cosine': .8, 'content_hash': 'A'}, {'id': 'b', 'cosine': .7, 'content_hash': 'B'}]}}
    return {'task_id': str(task), 'family_id': family or 'f'+str(task), 'repeat': repeat,
            'cell_id': f'{task}_r{repeat}_{condition}', 'condition': condition, 'attempts': [attempt], 'final': attempt}


class RetestAnalysisTest(unittest.TestCase):
    def test_family_clusters_keep_both_repeats_and_related_tasks(self):
        rows = [row(task, repeat, arm, arm == 'Q2_K0', family='one_family')
                for task in ('1', '2') for repeat in (1, 2) for arm in ('Q1', 'Q2_K0')]
        result = compare(rows, 'Q2_K0', 'Q1', 2)
        self.assertEqual(result['pairs'], 4)
        self.assertEqual(result['measured_pairs'], 4)
        self.assertEqual(result['unique_tasks_in_measured_pairs'], 2)
        self.assertEqual(result['families'], 1)
        self.assertEqual(result['tasks_with_both_repeats_measured'], 2)
        self.assertEqual(result['difference'], 1.)
        self.assertEqual(result['p_family_swap'], 1.)
        self.assertNotIn('p_mcnemar_supplement', result)

    def test_unmeasured_pairs_are_not_verified_losses(self):
        rows = [row('1', 1, 'Q1', False), row('1', 1, 'Q2_K0', True),
                row('1', 2, 'Q1', True), row('1', 2, 'Q2_K0', False, measured=False)]
        result = compare(rows, 'Q2_K0', 'Q1', 2)
        self.assertEqual(result['wins'], 1)
        self.assertEqual(result['losses'], 0)
        self.assertEqual(result['missing_pairs'], 1)
        self.assertEqual(result['missing_unexecuted_pairs'], 2)
        self.assertEqual(result['tasks_with_both_repeats_measured'], 0)
        self.assertEqual(result['repeat_comparisons']['2']['measured_pairs'], 0)

    def test_new_member_adoption_and_outcome_repeat_variation_are_separate(self):
        a = row('1', 1, 'Q2_K0', True, cards=('b',), adopted=('b',))
        b = row('1', 1, 'Q1', False)
        mechanism = first_mechanism(a, b)
        self.assertTrue(mechanism['same_first_candidates'])
        self.assertTrue(mechanism['selected_members_changed'])
        self.assertEqual(mechanism['newly_selected_declared_adopted_ids'], ['b'])
        summary, _ = analyze([a, b, row('1', 2, 'Q2_K0', False), row('1', 2, 'Q1', False)], 1)
        self.assertEqual(summary['arms']['Q2_K0']['repeat_variability']['Joint_discordant_tasks'], 1)
        self.assertEqual(summary['arms']['Q1']['repeat_variability']['Joint_discordant_tasks'], 0)

    def test_without_real_rows_only_not_started_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run(root)
            self.assertEqual(result['status'], 'not_started')
            self.assertIsNone(result['results'])
            self.assertTrue((root/'FQ_RETEST/analysis/analysis.md').exists())
            self.assertNotIn('comparisons', result)


if __name__ == '__main__':
    unittest.main()

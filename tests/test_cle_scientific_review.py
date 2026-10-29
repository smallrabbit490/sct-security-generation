"""科研目标修订的关键验证：正确率选模、family隔离、活动计划不动、暂缓不造成绩。"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from configs.cle_scientific_review_20261028 import review, router
from tools.cle_live_workbench.autonomy import AutonomousPlan


class ReviewTests(unittest.TestCase):
    def test_joint_precedes_label_accuracy_and_cost(self):
        candidates = [dict(C=.1, family_mean_joint=.6, family_mean_input_tokens=10, label_accuracy=1),
                      dict(C=1., family_mean_joint=.7, family_mean_input_tokens=30, label_accuracy=.3)]
        self.assertEqual(router.choose_candidate(candidates), 1.)
        candidates[0]['family_mean_joint'] = .7
        self.assertEqual(router.choose_candidate(candidates), .1)

    def test_unknown_cost_not_treated_as_zero(self):
        self.assertEqual(router.choose_candidate([
            dict(C=10., family_mean_joint=.7, family_mean_input_tokens=None),
            dict(C=.1, family_mean_joint=.7, family_mean_input_tokens=50)]), .1)

    def fixture(self):
        tasks = {str(i): {'family_id': 'f'+str(i), 'context': str(i)} for i in range(4)}
        split = {'train_task_ids': ['0','1','2'], 'development_task_ids': ['3'],
                 'family_cv_fold': {'f0':0, 'f1':1, 'f2':2}}
        rows = [{'task_id': t, 'repeat': repeat, 'condition': level,
                 'final': {'joint': level == 'L1', 'measured': True},
                 'usage': {'prompt_tokens': 100}}
                for t in tasks for repeat in (1, 2) for level in router.ga.LEVELS]
        labels = [{'task_id': t, 'family_id': tasks[t]['family_id'],
                   'preferred_level': 'L0' if t == '0' else 'L1'} for t in tasks]
        return rows, tasks, split, labels

    def test_only_train_families_used_and_development_outcomes_do_not_change_fit(self):
        rows, tasks, split, labels = self.fixture()
        fitted = []
        def fake_fit(x, y, c):
            fitted.extend(v[0] for v in x)
            return {'C': c}
        def fake_predict(task, model):
            return ('L1' if model.get('fit', {}).get('C') == 1. else 'L0'), 1.
        with patch.object(router.ga, 'features', lambda t: [t['context']]), \
             patch.object(router.ga, 'fit_logistic', fake_fit), \
             patch.object(router.ga, 'predict', fake_predict):
            a = router.fit_model(rows, tasks, split, labels)
            modified = copy.deepcopy(rows)
            for row in modified:
                if row['task_id'] == '3':
                    row['final']['joint'] = not row['final']['joint']
            b = router.fit_model(modified, tasks, split, labels)
        self.assertEqual(a, b)
        self.assertNotIn('3', fitted)
        self.assertEqual(a['fit']['C'], 1.)
        self.assertEqual({c['held_tasks'] for c in a['CV_C_scores']}, {3})

    def test_cost_label_difference_is_not_correctness_heterogeneity(self):
        rows, tasks, split, _ = self.fixture()
        for row in rows:
            row['final']['joint'] = True
        report = router.opportunity(rows, tasks, split['train_task_ids'])
        self.assertEqual(report['task_counts'], {'no_observed_correctness_difference': 3})

    def test_family_leakage_is_rejected(self):
        rows, tasks, split, labels = self.fixture()
        tasks['3']['family_id'] = 'f0'
        with self.assertRaisesRegex(ValueError, 'family_training_development_leakage'):
            router.fit_model(rows, tasks, split, labels)

    def test_plan_keeps_active_runs_budgets_and_has_real_defer(self):
        plan = json.loads((review.ROOT/'tools/cle_live_workbench/autonomy_plan.json').read_text(encoding='utf-8'))
        after = review.update_plan(plan)
        before_by = {t['id']: t for t in plan['tasks']}
        after_by = {t['id']: t for t in after['tasks']}
        for identity in ('Q.run','FS.run','Q.K0.analysis','Q.K1.analysis','BUILD.prepare','CROSS.prepare'):
            self.assertEqual(before_by[identity], after_by[identity])
        self.assertEqual(len(plan['tasks']), len(after['tasks']))
        self.assertEqual(review.update_plan(after), after)
        self.assertEqual(after_by['P3.external']['expected'], 255)
        self.assertIn('deferred_from_current_mainline', after_by['P3.external']['omit_when']['values'])
        with tempfile.TemporaryDirectory() as temp:
            flow = AutonomousPlan(temp, after)
            self.assertFalse(flow.omitted_by_protocol(after_by['P3.external']))
            path = Path(temp)/review.OMIT['path']
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'status':'decided','P3_external':'deferred_from_current_mainline'}),encoding='utf-8')
            self.assertTrue(flow.omitted_by_protocol(after_by['P3.external']))
            self.assertFalse(flow.receipt_path(after_by['P3.external']).exists())


if __name__ == '__main__':
    unittest.main()

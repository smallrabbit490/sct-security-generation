"""三策略路由的零网络合成原生验证；同档复用不跨重复。"""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch

from configs.cle_weekly_granularity_gate_20261027 import evaluate as gate
from configs.cle_weekly_granularity_20261027 import evaluate as labels
from configs.cle_weekly_eval_20261027 import retest as base
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from tests import test_cle_weekly_granularity as fixture


class FrozenPolicyGateTest(unittest.TestCase):
    validate = staticmethod(fixture.FrozenGranularityTest.validate)
    guards = fixture.FrozenGranularityTest.guards
    service = fixture.FrozenGranularityTest.service
    select = fixture.FrozenGranularityTest.select

    def setUp(self):
        fixture.FrozenGranularityTest.setUp(self)
        source = self.inputs
        self.inputs = self.root/'FG_GATE/inputs'
        for name in ('tasks.json', 'source_examples.json', 'source_eligibility.json', 'family_split.json'):
            write_json(self.inputs/name, base.read(source/name))
        self.cells = gate.schedule(['1', '2'], self.tasks)
        write_json(self.inputs/'schedule.json', self.cells)
        bank = base.read(source/'protocol.json')['bank_sources']['L2']
        self.model_path = self.root/'FG_TRAIN/model.json'
        self.model = {'protocol': gate.MODEL_PROTOCOL, 'source_protocol': labels.PROTOCOL,
            'type': 'constant', 'fixed': 'L2', 'task_only_router': True,
            'development_used_for_fitting': False, 'Q_or_CWE_or_ID_features': False}
        write_json(self.model_path, self.model)
        write_json(self.inputs/'protocol.json', {'protocol': gate.PROTOCOL,
            'label_source_protocol': labels.PROTOCOL, 'planned_P7': len(self.cells),
            'bank_sources': {arm: bank for arm in gate.POLICIES}, 'card_count': 2,
            'model_source': str(self.model_path), 'paid_execution_enabled': False,
            'budget_proposed': {'conservative_model_and_embedding_tokens': 10000000,
                'total_physical_HTTP_attempts': 1500, 'embedding_HTTP_attempts_included_in_total': 100}})

    def test_same_level_full_trajectory_reuse_and_repeats_independent_with_exact_replay(self):
        with self.guards():
            study = gate.FrozenPolicyGate()
            before = copy.deepcopy(study.frozen_before)
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 12)
            self.assertEqual(result['logical_completed'], 12)
            self.assertEqual(result['actual_paid_level_runs'], 4)
            self.assertEqual(result['reused_logical_cells'], 8)
            self.assertEqual(self.generation, 4)
            self.assertEqual(result['known_reported_tokens'], len(self.http)*15)
            self.assertEqual(len(list((study.out/'shared_starts').glob('*.json'))), 4)
            self.assertEqual(len(list((study.out/'routing').glob('*.json'))), 4)
            self.assertEqual(before, {arm: [n.to_dict() for n in nodes] for arm, nodes in study.banks.items()})
            for tid in ('1', '2'):
                repeats = []
                for repeat in (1, 2):
                    rows = [row for row in study.rows if row['task_id'] == tid and row['repeat'] == repeat]
                    self.assertEqual(len({row['final']['code'] for row in rows}), 1)
                    self.assertEqual(len({row['canonical_generation_cell'] for row in rows}), 1)
                    self.assertTrue(all(row['selected_level'] == 'L2' and row['routing_before_generation'] for row in rows))
                    self.assertTrue(all(row['usage']['prompt_tokens'] > 0 for row in rows))
                    repeats.append(rows[0]['final']['code'])
                self.assertNotEqual(*repeats)
            calls = len(self.http)
            replay = gate.FrozenPolicyGate([study.out], offline=True, destination=self.root/'FG_GATE/replay')
            replay.execute()
            self.assertEqual(len(self.http), calls)
            self.assertEqual(base.read(replay.out/'replay_result.json')['status'], 'passed')
            resumed = gate.FrozenPolicyGate([study.out])
            resumed.io.physical_open = self.service
            summary = resumed.execute()
            self.assertEqual(len(self.http), calls)
            self.assertEqual(summary['completed_unique_level_runs'], 4)

    def test_different_levels_keep_native_independent_repairs_and_shared_first_selection(self):
        self.model['fixed'] = 'L1'
        write_json(self.model_path, self.model)
        for task in self.tasks.values():
            task['task_description']['description'] = 'Open a file and preserve its public output.'
        write_json(self.inputs/'tasks.json', self.tasks)
        with self.guards():
            study = gate.FrozenPolicyGate()
            study.io.physical_open = self.service
            summary = study.execute()
            self.assertEqual(summary['completed'], 12)
            self.assertEqual(summary['actual_paid_level_runs'], 8)
            self.assertEqual(summary['reused_logical_cells'], 4)
            self.assertEqual(self.generation, 8)
            self.assertEqual(self.binding_calls, 2)
            self.assertTrue(all(row['selected_level'] == ('L3' if row['condition'] == 'rule' else 'L1') for row in study.rows))
            checks = [base.read(path) for path in (study.out/'shared_selection_checks').glob('*.json')]
            self.assertEqual(len(checks), 4)
            self.assertTrue(all(item['status'] == 'passed' and item['pre_level_selected_ids'] == list(self.cards) for item in checks))

    def test_all_normal_failures_complete_fixed_grid_and_do_not_reroute_from_feedback(self):
        with self.guards(), patch('methods.sct_trajectory.closed_loop.validate_and_state',
                return_value=({'functional': {'status': 'fail', 'measured': True},
                    'security': {'status': 'pass', 'measured': True}}, 'B')):
            study = gate.FrozenPolicyGate()
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 12)
            self.assertEqual(self.generation, 8)
            self.assertTrue(all(not arm['joint'] for arm in result['arms'].values()))
            self.assertTrue(all(len(row['attempts']) == 2 for row in study.rows))
            routes = [base.read(path) for path in (study.out/'routing').glob('*.json')]
            self.assertTrue(all(not row['repair_or_outcomes_used_for_routing'] for row in routes))
            self.assertTrue(all(set(row['selected_levels'].values()) == {'L2'} for row in routes))

    def test_no_first_cards_rule_is_L0_and_all_L0_repair_cards_remain_empty(self):
        original_select = self.select
        def empty_first(engine, query, limit, nodes):
            selected = original_select(engine, query, limit, nodes)
            return [] if not query.get('current_code') else selected
        with self.guards(), patch('methods.sct_trajectory.retriever.HskTreeRetriever.search',
                lambda obj, query, limit, pool_nodes: empty_first(obj, query, limit, pool_nodes)), \
                patch('methods.sct_trajectory.closed_loop.validate_and_state',
                    return_value=({'functional': {'status': 'fail', 'measured': True},
                        'security': {'status': 'pass', 'measured': True}}, 'B')):
            study = gate.FrozenPolicyGate()
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 12)
            self.assertEqual(result['actual_paid_level_runs'], 8)
            for row in study.rows:
                self.assertFalse(row['first_has_cards'])
                self.assertEqual(row['selected_level'], 'L0' if row['condition'] == 'rule' else 'L2')
                if row['condition'] == 'rule':
                    self.assertTrue(all(not a['generation']['retrieved_cards'] for a in row['attempts']))

    def test_unresolved_and_changed_model_block_resume_before_new_HTTP(self):
        prior = self.root/'prior'
        write_json(prior/'journals/cell/requests/pending.json', {'status': 'prepared'})
        with self.guards(), self.assertRaisesRegex(ReplayStop, 'unresolved_saved_requests'):
            gate.FrozenPolicyGate([prior])
        with self.guards():
            study = gate.FrozenPolicyGate()
            study.embedding._db.close()
            self.model['fixed'] = 'L4'
            write_json(self.model_path, self.model)
            with self.assertRaisesRegex(ReplayStop, 'saved_protocol_task_schedule_or_Q_snapshot_changed'):
                gate.FrozenPolicyGate([study.out])
        self.assertEqual(self.http, [])

    def test_old_classifier_is_not_consumed_and_missing_full_labels_prevent_ready(self):
        self.model['protocol'] = 'old-router'
        write_json(self.model_path, self.model)
        with self.guards(), self.assertRaisesRegex(ReplayStop, 'only_new_full_FG_TRAIN_model'):
            gate.FrozenPolicyGate()
        with patch.object(base, 'RUN', self.root):
            result = gate.dependencies()
        self.assertFalse(result['ready'])
        self.assertIn('FG_LABELS_full_grid_not_completed', result['reasons'])
        self.assertIn('new_FG_TRAIN_model_not_completed', result['reasons'])
        self.assertFalse(result['old_classifier_consumed'])
        self.assertEqual(self.http, [])

    def test_ready_requires_new_complete_labels_replay_analysis_and_model_without_dispatch(self):
        segment = self.root/'FG_LABELS/segment_001'
        write_json(self.root/'FG_LABELS/execution_index.json', {'segments': [str(segment)]})
        write_json(segment/'summary.json', {'status': 'completed', 'completed': 2730})
        write_json(self.root/'FG_LABELS/zero_API_replay/replay_result.json', {'status': 'passed'})
        write_json(self.root/'FG_LABELS/analysis/summary.json', {'status': 'completed'})
        write_json(self.root/'FG_TRAIN/summary.json', {'status': 'completed'})
        write_json(self.root/'FQ_GATE/preflight_v3/summary.json', {'reference_preflight_ready': True,
            'reference_joint': 298, 'reference_and_name_checks_passed': 298})
        write_json(self.root/'FQ_GATE/inputs_v3/tasks.json', self.tasks)
        write_json(self.root/'FG_GATE/offline_checks.json', {'status': 'passed'})
        with patch.object(base, 'RUN', self.root):
            self.assertTrue(gate.dependencies()['ready'])
            self.model['source_protocol'] = 'old-partial-labels'
            write_json(self.model_path, self.model)
            value = gate.dependencies()
            self.assertFalse(value['ready'])
            self.assertIn('classifier_does_not_match_current_full_labels', value['reasons'])
        self.assertEqual(self.http, [])


if __name__ == '__main__':
    unittest.main()

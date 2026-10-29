"""全D_gate四臂的零API接线：原生P7、合成服务、冻结Q和两次独立重复。"""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from unittest.mock import patch

from configs.cle_weekly_gate_20261027 import evaluate as gate
from configs.cle_weekly_eval_20261027 import retest as base
from methods.cle_ablation.run_memory_q import shuffled_memory
from methods.sct_trajectory.memory_q import rank_candidates
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.selector_protocol import SelectorPrompt
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from tests import test_cle_weekly_frozen_retest as fixture


class FrozenGateTest(unittest.TestCase):
    service = fixture.FrozenRetestTest.service
    validate = staticmethod(fixture.FrozenRetestTest.validate)
    guards = fixture.FrozenRetestTest.guards

    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=base.RUN / 'preflight')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.inputs = self.root / 'FQ_GATE/inputs_v3'
        self.tasks = {str(t): {'index': t, 'family_id': f'f{t}', 'CWE_ID': '347',
            'task_description': {'description': f'Load file {t}'}} for t in (1, 2)}
        self.bank = base.runner.load_memory(base.RUN / 'shared_inputs/memory1939_q0.jsonl')[:4]
        for card in self.bank:
            card.cwe = '347'
            card.q_value = 0.
            card.q_visits = 0
        banks = {}
        for arm in gate.CONDITIONS:
            nodes = copy.deepcopy(self.bank)
            if arm in ('Q2', 'Q3'):
                for index, node in enumerate(nodes):
                    node.q_value = -.9 + index*.5
                    node.q_visits = index+1
            path = self.root / 'banks' / (arm + '.jsonl')
            _write_memory(path, nodes)
            banks[arm] = str(path)
        self.cells = gate.schedule(['1', '2'], self.tasks)
        write_json(self.inputs / 'tasks.json', self.tasks)
        write_json(self.inputs / 'schedule.json', self.cells)
        write_json(self.inputs / 'protocol.json', {'protocol': gate.PROTOCOL, 'planned_P7': len(self.cells),
            'bank_sources': banks, 'card_count': len(self.bank), 'paid_execution_enabled': False,
            'budget_proposed': {'conservative_model_and_embedding_tokens': 10000000,
                'total_physical_HTTP_attempts': 1000, 'embedding_HTTP_attempts_included_in_total': 100}})
        cache = self.root / 'shared_inputs/embeddings.sqlite3'
        cache.parent.mkdir(parents=True)
        with closing(sqlite3.connect(cache)) as db:
            db.execute('CREATE TABLE fixture (id INTEGER)')
        self.http, self.generation, self.lock, self.policies = [], 0, threading.RLock(), []

    def select(self, engine, query, limit, nodes):
        self.assertEqual(limit, 3)
        self.policies.append((engine.candidate_order, engine.semantic_delta))
        scores = [{'id': node.invariant_id, 'cosine': -1 if index == len(nodes)-1 else .8-index*.1,
                   'content_hash': f'body{index}'} for index, node in enumerate(nodes)]
        if engine.candidate_order is None:
            ranked = scores
        else:
            ranked = rank_candidates(scores, {node.invariant_id: node.q_value for node in nodes},
                delta=-1, lambda_q=0 if engine.candidate_order == 'similarity' else .5, limit=None)
        engine.requester(SelectorPrompt('Select fixture', deadline=1e20))
        engine.last_hier_trace = {'status': 'completed', 'candidate_order': engine.candidate_order,
            'query_hash': str(query.get('task_id')), 'candidate_ids': [s['id'] for s in scores],
            'scores': scores, 'presented_candidate_ids': [s['id'] for s in ranked], 'selection_limit': 3}
        return [{'invariant_id': ranked[0]['id'], 'positive_principle': 'Preserve the public interface'}]

    def test_four_conditions_two_repeats_frozen_and_Q0_boundary_logged_with_exact_replay(self):
        with self.guards():
            study = gate.FrozenGate()
            before = copy.deepcopy(study.frozen_before)
            expected_Q3 = shuffled_memory(base.runner.load_memory(Path(study.protocol['bank_sources']['Q3'])),
                                           20261015, scope='cwe')
            self.assertEqual([(n.q_value, n.q_visits) for n in study.banks['Q3']],
                             [(n.q_value, n.q_visits) for n in expected_Q3])
            self.assertCountEqual([(n.q_value, n.q_visits) for n in study.banks['Q3']],
                                  [(n.q_value, n.q_visits) for n in study.banks['Q2']])
            study.io.physical_open = self.service
            summary = study.execute()
            self.assertEqual(summary['completed'], 16)
            self.assertEqual(set(summary['arms']), set(gate.CONDITIONS))
            self.assertEqual(self.generation, 16)
            self.assertEqual(len({row['final']['code'] for row in study.rows}), 16)
            self.assertEqual(before, {arm: [n.to_dict() for n in bank] for arm, bank in study.banks.items()})
            self.assertEqual(len(list((study.out / 'shared_starts').glob('*.json'))), 4)
            self.assertIn((None, None), self.policies)
            self.assertIn(('similarity', -1), self.policies)
            self.assertIn(('q', -1), self.policies)
            checks = [base.read(p) for p in (study.out / 'common_candidates').glob('*.json')]
            self.assertTrue(all(c['status'] == 'passed' and c['expected_conditions'] == 3 for c in checks))
            boundaries = [base.read(p) for p in (study.out / 'Q0_boundary').glob('*.json')]
            self.assertEqual(len(boundaries), 4)
            self.assertTrue(all(b['Q0_presented_count'] == 4 and b['Q1_presented_count'] == 3 for b in boundaries))
            self.assertTrue(all(b['same_presented_members'] is False for b in boundaries))
            self.assertEqual(summary['Q_updates'], 0)
            calls = len(self.http)
            replay = gate.FrozenGate([study.out], offline=True, destination=self.root/'FQ_GATE/replay')
            replay.execute()
            self.assertEqual(len(self.http), calls)
            self.assertEqual(base.read(replay.out/'replay_result.json')['status'], 'passed')
            resumed = gate.FrozenGate([study.out])
            resumed.io.physical_open = self.service
            resumed.execute()
            self.assertEqual(len(self.http), calls)

    def test_all_normal_failures_still_complete_full_sixteen_cells(self):
        with self.guards(), patch('methods.sct_trajectory.closed_loop.validate_and_state',
                return_value=({'functional': {'status': 'fail', 'measured': True},
                    'security': {'status': 'pass', 'measured': True}}, 'B')):
            study = gate.FrozenGate()
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 16)
            self.assertTrue(all(len(row['attempts']) == 2 for row in study.rows))
            self.assertTrue(all(a['joint'] == 0 for a in result['arms'].values()))
            self.assertEqual(result['status'], 'completed')

    def test_unresolved_requests_block_recovery_before_any_HTTP(self):
        prior = self.root/'prior'
        write_json(prior/'journals/cell/requests/pending.json', {'status': 'prepared'})
        with self.guards(), self.assertRaises(ReplayStop):
            gate.FrozenGate([prior])
        self.assertEqual(self.http, [])

    def test_returned_responses_restore_unsaved_cell_without_new_HTTP(self):
        with self.guards():
            study = gate.FrozenGate()
            study.io.physical_open = self.service
            study.execute()
            path = next((study.out/'task_rows').glob('*.json'))
            saved = base.read(path)
            # 仅测试自有合成行：模拟响应已经返回而最终逐题落盘未完成。
            path.unlink()
            calls = len(self.http)
            resumed = gate.FrozenGate([study.out])
            resumed.io.physical_open = self.service
            resumed.execute()
            self.assertEqual(len(self.http), calls)
            restored = next(row for row in resumed.rows if row['cell_id'] == saved['cell_id'])
            self.assertEqual(restored['final']['code'], saved['final']['code'])


if __name__ == '__main__':
    unittest.main()

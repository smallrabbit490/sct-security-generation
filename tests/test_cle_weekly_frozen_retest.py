"""冻结回测接线的零API集成；原P7请求器，服务与验证均为合成夹具。"""
import copy
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import ExitStack, closing
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_eval_20261027 import retest as m
from configs.cle_v41_relation_20261026 import wiring
from configs.cle_v41_relation_20261026.offline_check import INITIAL
from configs.cle_v41_relation_20261026.offline_execution_check import Response
from methods.sct_trajectory.memory_q import rank_candidates
from methods.sct_trajectory.selector_protocol import SelectorPrompt
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


class FrozenRetestTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=m.RUN / 'preflight')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.inputs = self.root / 'FQ_RETEST/inputs'
        self.tasks = {str(t): {'index': t, 'family_id': f'f{t}', 'CWE_ID': '347',
                      'task_description': {'description': f'Load file {t}'}} for t in (1, 2)}
        self.bank = m.runner.load_memory(m.RUN / 'shared_inputs/memory1939_q0.jsonl')[:2]
        banks = {}
        for arm in m.CONDITIONS:
            nodes = copy.deepcopy(self.bank)
            for n in nodes:
                n.q_value = 0.; n.q_visits = 0
            if arm != 'Q1':
                nodes[0].q_value = -.9; nodes[0].q_visits = 1
                nodes[1].q_value = .9; nodes[1].q_visits = 1
            path = self.root / 'banks' / (arm + '.jsonl')
            _write_memory(path, nodes)
            banks[arm] = str(path)
        self.cells = m.schedule(['1', '2'], self.tasks)
        write_json(self.inputs / 'tasks.json', self.tasks)
        write_json(self.inputs / 'schedule.json', self.cells)
        write_json(self.inputs / 'protocol.json', {'protocol': m.PROTOCOL, 'planned_P7': len(self.cells),
            'bank_sources': banks, 'card_count': 2, 'paid_execution_enabled': False,
            'budget_proposed': {'conservative_model_and_embedding_tokens': 10000000,
                'total_physical_HTTP_attempts': 1000, 'embedding_HTTP_attempts_included_in_total': 100}})
        path = self.root / 'shared_inputs/embeddings.sqlite3'
        path.parent.mkdir(parents=True)
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE fixture (id INTEGER)')
        self.http, self.generation, self.lock = [], 0, threading.RLock()

    def guards(self):
        stack = ExitStack()
        stack.enter_context(patch.object(m, 'RUN', self.root))
        stack.enter_context(patch.object(m, 'snapshot_sources'))
        for name in ('methods.sct_trajectory.run_closed_loop.ensure_model_call_allowed',
                     'methods.sct_trajectory.replay_journal.ensure_model_call_allowed',
                     'configs.cle_v41_relation_20261026.execution.ensure_model_call_allowed'):
            stack.enter_context(patch(name, return_value=None))
        stack.enter_context(patch('methods.sct_trajectory.run_closed_loop.load_key', return_value='synthetic-only'))
        stack.enter_context(patch('methods.sct_trajectory.closed_loop.validate_and_state', side_effect=self.validate))
        stack.enter_context(patch('methods.sct_trajectory.retriever.HskTreeRetriever.search',
            lambda obj, query, limit, pool_nodes: self.select(obj, query, limit, pool_nodes)))
        stack.enter_context(patch('socket.create_connection', side_effect=AssertionError('network_forbidden')))
        stack.enter_context(patch('socket.socket.connect', side_effect=AssertionError('network_forbidden')))
        return stack

    def service(self, request, *args, **kwargs):
        body = json.loads(request.data)
        prompt = body['messages'][0]['content']
        with self.lock:
            self.http.append(body)
            if prompt.startswith('Select fixture'):
                content = '{"selected":[1]}'
            elif prompt.startswith(wiring.GENERATION):
                self.generation += 1
                content = f'def load_file():\n    return {self.generation}\n'
            elif prompt.startswith('Plan the implementation.'):
                content = json.dumps({'Preserved_Func': 'public interface', 'Patch_Scope': 'load file safely'})
            else:
                content = json.dumps({**INITIAL, 'applied_experience_ids': [], 'rejected_experiences': []})
        result = {'model': wiring.SETTINGS['model'], 'choices': [{'index': 0,
            'delta': {'content': content}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
        return Response(('data: ' + json.dumps(result) + '\n\ndata: [DONE]\n\n').encode())

    def select(self, engine, query, limit, nodes):
        self.assertEqual(limit, 3)
        scores = [{'id': n.invariant_id, 'cosine': .8-j*.1, 'content_hash': f'body{j}'} for j, n in enumerate(nodes)]
        values = {n.invariant_id: n.q_value for n in nodes}
        ranked = rank_candidates(scores, values, delta=-1,
            lambda_q=0 if engine.candidate_order == 'similarity' else .5, limit=None)
        engine.requester(SelectorPrompt('Select fixture', deadline=1e20))
        engine.last_hier_trace = {'status': 'completed', 'candidate_order': engine.candidate_order,
            'query_hash': str(query.get('task_id')), 'candidate_ids': [s['id'] for s in scores],
            'scores': scores, 'presented_candidate_ids': [s['id'] for s in ranked], 'selection_limit': 3}
        return [{'invariant_id': ranked[0]['id'], 'positive_principle': 'Preserve the public interface'}]

    @staticmethod
    def validate(task, code, timeout):
        return {'functional': {'status': 'pass', 'measured': True},
                'security': {'status': 'pass', 'measured': True}}, 'A'

    def test_five_conditions_two_independent_repeats_shared_initial_and_exact_replay(self):
        with self.guards():
            study = m.FrozenRetest()
            before = copy.deepcopy(study.frozen_before)
            study.io.physical_open = self.service
            summary = study.execute()
            self.assertEqual(summary['completed'], 20)
            self.assertEqual(summary['Q_updates'], 0)
            self.assertEqual(self.generation, 20)
            self.assertEqual(len({r['final']['code'] for r in study.rows}), 20)
            self.assertEqual(before, {arm: [n.to_dict() for n in bank] for arm, bank in study.banks.items()})
            self.assertEqual(len(list((study.out / 'shared_starts').glob('*.json'))), 4)
            starts = [j for name, j in study.io.journals.items() if name.startswith('shared_initial_')]
            self.assertEqual(sum(len(j.records) for j in starts), 4)
            checks = [m.read(p) for p in (study.out / 'common_candidates').glob('*.json')]
            self.assertEqual(len(checks), 4)
            self.assertTrue(all(c['status'] == 'passed' for c in checks))
            self.assertTrue(all(r['retrieval_mode'] == 'semantic_llm' for r in study.rows))
            self.assertEqual(len({r['cell_id'] for r in study.rows}), 20)
            calls = len(self.http)
            replay = m.FrozenRetest([study.out], offline=True, destination=self.root / 'FQ_RETEST/replay')
            replay.execute()
            self.assertEqual(len(self.http), calls)
            self.assertEqual(m.read(replay.out / 'replay_result.json')['status'], 'passed')
            self.assertEqual(m.read(replay.out / 'replay_result.json')['new_HTTP'], 0)

    def test_completed_cells_resume_without_new_calls(self):
        with self.guards():
            study = m.FrozenRetest()
            study.io.physical_open = self.service
            study.execute()
            calls = len(self.http)
            resumed = m.FrozenRetest([study.out])
            resumed.io.physical_open = self.service
            resumed.execute()
            self.assertEqual(len(self.http), calls)
            self.assertEqual(len(resumed.rows), 20)

    def test_returned_responses_without_saved_cell_rebuild_without_payment(self):
        with self.guards():
            study = m.FrozenRetest()
            study.io.physical_open = self.service
            study.execute()
            missing = next((study.out / 'task_rows').glob('*.json'))
            saved = m.read(missing)
            # 仅删除本测试自有的合成行，模拟响应已返回但逐题落盘未完成。
            missing.unlink()
            calls = len(self.http)
            resumed = m.FrozenRetest([study.out])
            resumed.io.physical_open = self.service
            resumed.execute()
            self.assertEqual(len(self.http), calls)
            restored = next(r for r in resumed.rows if r['cell_id'] == saved['cell_id'])
            self.assertEqual(restored['final']['code'], saved['final']['code'])
            self.assertEqual(len(resumed.rows), 20)

    def test_unresolved_request_blocks_recovery_before_new_HTTP(self):
        prior = self.root / 'prior'
        write_json(prior / 'journals/cell/requests/request.json', {'status': 'prepared'})
        with self.guards(), self.assertRaises(ReplayStop):
            m.FrozenRetest([prior])
        self.assertEqual(self.http, [])

    def test_same_path_Q_change_blocks_recovery_of_old_completed_cells(self):
        with self.guards():
            prior = m.FrozenRetest()
            prior.embedding._db.close()
            path = Path(m.read(self.inputs / 'protocol.json')['bank_sources']['Q2_K1'])
            bank = m.runner.load_memory(path)
            bank[0].q_value += .1
            _write_memory(path, bank)
            with self.assertRaisesRegex(ReplayStop, 'saved_protocol_task_schedule_or_Q_snapshot_changed'):
                m.FrozenRetest([prior.out])
        self.assertEqual(self.http, [])

    def test_resume_cannot_skip_saved_candidate_mismatch_in_completed_group(self):
        with self.guards():
            prior = m.FrozenRetest()
            prior.io.physical_open = self.service
            prior.execute()
            path = next((prior.out / 'task_rows').glob('*.json'))
            row = m.read(path)
            row['attempts'][0]['retrieval_trace']['scores'][0]['cosine'] -= .01
            write_json(path, row)
            calls = len(self.http)
            with self.assertRaisesRegex(ReplayStop, 'saved_first_query_candidate_or_cosine_mismatch'):
                m.FrozenRetest([prior.out])
            self.assertEqual(len(self.http), calls)

    def test_all_normal_code_failures_still_complete_fixed_twenty_cells(self):
        with self.guards(), patch('methods.sct_trajectory.closed_loop.validate_and_state',
                return_value=({'functional': {'status': 'fail', 'measured': True},
                               'security': {'status': 'pass', 'measured': True}}, 'B')):
            study = m.FrozenRetest()
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 20)
            self.assertTrue(all(a['joint'] == 0 for a in result['arms'].values()))
            self.assertTrue(all(len(r['attempts']) == 2 for r in study.rows))
            self.assertEqual(result['status'], 'completed')

    def test_unexpected_group_failure_stops_queued_dispatch(self):
        with self.guards(), patch.object(m.runner, 'run_one', side_effect=RuntimeError('synthetic persistence error')):
            study = m.FrozenRetest()
            study.io.physical_open = self.service
            with self.assertRaises(RuntimeError):
                study.execute()
            self.assertEqual(study.rows, [])
            self.assertEqual(m.read(study.out / 'state.json')['status'], 'needs_technical_recovery')
            self.assertEqual(study.io.reason, 'frozen_group_technical_failure')
            self.assertLessEqual(len(self.http), 4)

    def test_candidate_identity_check_ignores_order_but_detects_content_or_cosine_changes(self):
        trace = {'status': 'completed', 'query_hash': 'q', 'candidate_ids': ['b', 'a'],
            'scores': [{'id': 'a', 'cosine': .8, 'content_hash': 'x'}, {'id': 'b', 'cosine': .7, 'content_hash': 'y'}]}
        row = {'attempts': [{'retrieval_trace': trace}]}
        other = copy.deepcopy(row)
        other['attempts'][0]['retrieval_trace']['candidate_ids'].reverse()
        self.assertEqual(m.first_candidate_signature(row), m.first_candidate_signature(other))
        other['attempts'][0]['retrieval_trace']['scores'][0]['cosine'] = .9
        self.assertNotEqual(m.first_candidate_signature(row), m.first_candidate_signature(other))


if __name__ == '__main__':
    unittest.main()

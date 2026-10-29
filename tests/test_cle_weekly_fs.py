"""功能安全五条件的零API接线与材料缓存测试，禁止真实网络。"""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import patch

from configs.cle_weekly_fs_20261027 import evaluate as fs
from configs.cle_weekly_eval_20261027 import retest as base
from configs.cle_v41_relation_20261026.offline_execution_check import Response
from methods.sct_trajectory.memory_views import source_projection, draft_view, render_view
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.selector_protocol import SelectorPrompt
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from tests import test_cle_weekly_frozen_retest as fixture


class FrozenFSTest(unittest.TestCase):
    validate = staticmethod(fixture.FrozenRetestTest.validate)

    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=base.RUN/'preflight')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.inputs = self.root/'FFS/inputs'
        self.tasks = {str(t): {'index': t, 'family_id': f'f{t}', 'CWE_ID': '347',
            'task_description': {'description': f'Load file {t}'}} for t in (1, 2)}
        self.bank = base.runner.load_memory(base.RUN/'shared_inputs/memory1939_q0.jsonl')[:2]
        for node in self.bank:
            node.q_value = 0.; node.q_visits = 0
        bank = self.root/'banks/zero.jsonl'
        _write_memory(bank, self.bank)
        self.cells = fs.schedule(['1', '2'], self.tasks)
        write_json(self.inputs/'tasks.json', self.tasks)
        write_json(self.inputs/'schedule.json', self.cells)
        write_json(self.inputs/'protocol.json', {'protocol': fs.PROTOCOL, 'planned_P7': len(self.cells),
            'bank_sources': {arm: str(bank) for arm in fs.CONDITIONS}, 'card_count': len(self.bank),
            'paid_execution_enabled': False, 'budget_proposed': {'conservative_model_and_embedding_tokens': 10000000,
                'total_physical_HTTP_attempts': 1500, 'embedding_HTTP_attempts_included_in_total': 100}})
        cache = self.root/'shared_inputs/embeddings.sqlite3'
        cache.parent.mkdir(parents=True)
        with closing(sqlite3.connect(cache)) as db:
            db.execute('CREATE TABLE fixture (id INTEGER)')
        self.http, self.generation, self.material_calls, self.lock = [], 0, 0, threading.RLock()

    def guards(self):
        stack = fixture.FrozenRetestTest.guards(self)
        stack.enter_context(patch.object(fs, 'legacy_catalog', return_value={}))
        return stack

    def service(self, request, *args, **kwargs):
        body = json.loads(request.data)
        prompt = body['messages'][0]['content']
        if not prompt.startswith('Partition each SOURCE'):
            return fixture.FrozenRetestTest.service(self, request, *args, **kwargs)
        with self.lock:
            self.http.append(body)
            self.material_calls += 1
        payload = json.loads(prompt.split('\nSOURCE:\n', 1)[1])
        value = {'items': [{'path': leaf['path'], 'parts': [{'text': leaf['text'],
            'role': 'functional' if leaf['path'][0] == 'negative_guardrail' else 'security'}]} for leaf in payload]}
        result = {'model': base.wiring.SETTINGS['model'], 'choices': [{'index': 0,
            'delta': {'content': json.dumps(value)}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
        return Response(('data: '+json.dumps(result)+'\n\ndata: [DONE]\n\n').encode())

    def select(self, engine, query, limit, nodes):
        self.assertEqual(limit, 3)
        self.assertIsNone(engine.candidate_order)
        self.assertIsNone(engine.semantic_delta)
        engine.requester(SelectorPrompt('Select fixture', deadline=1e20))
        scores = [{'id': node.invariant_id, 'cosine': .8-index*.1, 'content_hash': str(index)} for index, node in enumerate(nodes)]
        engine.last_hier_trace = {'status': 'completed', 'candidate_order': None,
            'query_hash': str(query.get('task_id')), 'candidate_ids': [s['id'] for s in scores],
            'scores': scores, 'selection_limit': 3}
        return [{'invariant_id': node.invariant_id, 'positive_principle': 'Verify the input safely.',
            'negative_guardrail': 'Preserve the function interface.', 'high_level_invariant': 'Use the public contract.',
            'kind': 'hint', 'status': 'active', 'support_count': 1, 'regression_count': 0} for node in nodes]

    def test_shared_first_selection_view_only_change_zero_Q_and_full_replay(self):
        with self.guards():
            study = fs.FrozenFS()
            before = copy.deepcopy(study.frozen_before)
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 20)
            self.assertEqual(result['Q_updates'], 0)
            self.assertEqual(self.generation, 20)
            self.assertEqual(len({row['final']['code'] for row in study.rows}), 20)
            self.assertEqual(self.material_calls, 2)
            self.assertEqual(len(list((study.out/'shared_starts').glob('*.json'))), 4)
            self.assertEqual(before, {arm: [n.to_dict() for n in bank] for arm, bank in study.banks.items()})
            for row in study.rows:
                cards = row['attempts'][0]['generation']['retrieved_cards']
                if row['condition'] == 'B0':
                    self.assertEqual(cards, [])
                else:
                    self.assertEqual([c['invariant_id'] for c in cards], [n.invariant_id for n in self.bank])
                    self.assertTrue(all(('_cle_memory_view' in c) == (row['condition'] != 'BM') for c in cards))
            self.assertTrue(all(base.read(path)['status'] == 'passed' for path in (study.out/'shared_selection_checks').glob('*.json')))
            paid = len(self.http)
            replay = fs.FrozenFS([study.out], offline=True, destination=self.root/'FFS/replay')
            replay.execute()
            self.assertEqual(len(self.http), paid)
            self.assertEqual(base.read(replay.out/'replay_result.json')['status'], 'passed')

    def test_normal_all_negative_still_completes_and_B0_has_no_repair_memory(self):
        with self.guards(), patch('methods.sct_trajectory.closed_loop.validate_and_state',
                return_value=({'functional': {'status': 'fail', 'measured': True},
                    'security': {'status': 'pass', 'measured': True}}, 'B')):
            study = fs.FrozenFS()
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 20)
            self.assertTrue(all(len(row['attempts']) == 2 for row in study.rows))
            self.assertTrue(all(a['joint'] == 0 for a in result['arms'].values()))
            self.assertEqual(self.material_calls, 2)
            for row in study.rows:
                if row['condition'] == 'B0':
                    self.assertTrue(all(not a['generation']['retrieved_cards'] for a in row['attempts']))

    def test_unresolved_request_blocks_recovery_before_HTTP(self):
        previous = self.root/'prior'
        write_json(previous/'journals/cell/requests/pending.json', {'status': 'prepared'})
        with self.guards(), self.assertRaises(ReplayStop):
            fs.FrozenFS([previous])
        self.assertEqual(self.http, [])

    def test_B0_alone_does_not_partition_materials(self):
        with self.guards():
            study = fs.FrozenFS()
            study.io.physical_open = self.service
            cell = next(cell for cell in self.cells if cell['condition'] == 'B0')
            try:
                with study.io.physical_records():
                    start = study.start(self.tasks[cell['task_id']], cell['repeat'])
                    row = study.one(cell, start)
                self.assertEqual(row['attempts'][0]['generation']['retrieved_cards'], [])
                self.assertEqual(self.material_calls, 0)
                self.assertFalse((study.out/'used_materials').exists())
            finally:
                study.embedding._db.close()

    def test_three_evaluation_workers_can_share_global_four_with_one_learner(self):
        with self.guards(), patch.object(fs.FrozenFS, 'worker_limit', 3):
            study = fs.FrozenFS()
            try:
                self.assertEqual(base.read(study.out/'launch.json')['runtime_workers'], 3)
                self.assertTrue(all(study.slots.acquire(blocking=False) for _ in range(3)))
                self.assertFalse(study.slots.acquire(blocking=False))
            finally:
                study.embedding._db.close()

    def test_source_cache_lock_prevents_duplicate_annotation_and_checks_full_source(self):
        with self.guards():
            study = fs.FrozenFS()
            study.io.physical_open = self.service
            card = {'invariant_id': 'source-a', 'positive_principle': 'Validate input.',
                'negative_guardrail': 'Preserve output.', 'kind': 'hint', 'status': 'active',
                'support_count': 1, 'regression_count': 0}
            try:
                with study.io.physical_records(), ThreadPoolExecutor(max_workers=4) as workers:
                    results = list(workers.map(lambda _: study.materials.view_specs([card]), range(4)))
                self.assertEqual(self.material_calls, 1)
                source = source_projection(card)
                identity = fs.source_hash(source)
                self.assertTrue(all(r['source-a']['source_sha256'] == identity for r in results))
                path = study.materials.root/'views'/(identity[:20]+'.json')
                spec = base.read(path)
                spec['source_projection']['positive_principle'] = 'Different text same card ID.'
                write_json(path, spec)
                with self.assertRaisesRegex(ReplayStop, 'exact_source_reconciliation'):
                    study.materials.view_specs([card])
                self.assertEqual(self.material_calls, 1)
            finally:
                study.embedding._db.close()

    def test_legacy_source_reuse_preserves_annotation_and_same_ID_changed_text_is_not_reused(self):
        card = {'invariant_id': 'legacy-a', 'positive_principle': 'Validate input.',
            'negative_guardrail': 'Preserve output.', 'kind': 'hint', 'status': 'active',
            'support_count': 1, 'regression_count': 0}
        source = source_projection(card)
        identity = fs.source_hash(source)
        spec = draft_view(card)
        spec.update(review_status='reviewed', annotation_method='rule_partition_after_AI_format_failure')
        for part in spec['segments']:
            part['role'] = 'security'
        old = self.root/'old_material.json'
        write_json(old, spec)
        original = old.read_bytes()
        catalog = {identity: {'source': source, 'spec': spec, 'path': str(old)}}
        with self.guards(), patch.object(fs, 'legacy_catalog', return_value=catalog):
            study = fs.FrozenFS()
            study.io.physical_open = self.service
            try:
                with study.io.physical_records():
                    reused = study.materials.view_specs([card])['legacy-a']
                    self.assertEqual(self.material_calls, 0)
                    self.assertEqual(reused['annotation_method'], 'rule_partition_after_AI_format_failure')
                    changed = {**card, 'positive_principle': 'Different source text.'}
                    fresh = study.materials.view_specs([changed])['legacy-a']
                self.assertEqual(self.material_calls, 1)
                self.assertNotEqual(fresh['source_sha256'], reused['source_sha256'])
                self.assertEqual(old.read_bytes(), original)
            finally:
                study.embedding._db.close()

    def test_original_two_format_attempts_then_rule_fallback_is_explicit(self):
        with self.guards():
            study = fs.FrozenFS()
            def invalid_material(request, *args, **kwargs):
                body = json.loads(request.data)
                with self.lock:
                    self.http.append(body)
                    self.material_calls += 1
                value = {'model': base.wiring.SETTINGS['model'], 'choices': [{'index': 0,
                    'delta': {'content': '{}'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
                return Response(('data: '+json.dumps(value)+'\n\ndata: [DONE]\n\n').encode())
            study.io.physical_open = invalid_material
            card = {'invariant_id': 'fallback-a', 'positive_principle': 'Validate input.',
                'negative_guardrail': 'Preserve output.', 'kind': 'hint', 'status': 'active',
                'support_count': 1, 'regression_count': 0}
            try:
                with study.io.physical_records():
                    spec = study.materials.view_specs([card])['fallback-a']
                    study.materials.view_specs([card])
                self.assertEqual(self.material_calls, 2)
                self.assertEqual(spec['annotation_method'], 'rule_partition_after_AI_format_failure')
                self.assertTrue(spec['semantic_partition_uncertainty'])
                self.assertTrue(spec['semantic_roles_are_not_human_gold'])
                render_view(source_projection(card), spec, 'BFS')
            finally:
                study.embedding._db.close()


if __name__ == '__main__':
    unittest.main()

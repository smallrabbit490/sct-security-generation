"""五档粒度的合成原生P7验证：共同来源池、原绑定、来源示例及冻结恢复。"""
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

from configs.cle_weekly_granularity_20261027 import evaluate as fg
from configs.cle_weekly_eval_20261027 import retest as base
from configs.cle_v41_relation_20261026.offline_execution_check import Response
from methods.sct_trajectory.memory_granularity import public_task
from methods.sct_trajectory.memory_views import source_projection
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.selector_protocol import SelectorPrompt
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from tests import test_cle_weekly_frozen_retest as fixture


class FrozenGranularityTest(unittest.TestCase):
    validate = staticmethod(fixture.FrozenRetestTest.validate)

    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=base.RUN/'preflight')
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.inputs = self.root/'FG_LABELS/inputs'
        self.tasks = {str(t): {'index': t, 'family_id': f'f{t}', 'CWE_ID': '347',
            'task_description': {'description': f'Load file {t}', 'function_name': 'load_file', 'language': 'python'}} for t in (1, 2)}
        self.bank = base.runner.load_memory(base.RUN/'shared_inputs/memory1939_q0.jsonl')[:3]
        for node in self.bank:
            node.q_value = 0.; node.q_visits = 0
        bank = self.root/'banks/zero.jsonl'
        _write_memory(bank, self.bank)
        self.cards = {node.invariant_id: {'invariant_id': node.invariant_id, 'positive_principle': 'Validate input.',
            'negative_guardrail': 'Preserve outputs.', 'high_level_invariant': 'Use the public contract.',
            'kind': 'seed_from_diff', 'source_task_id': f'source{index}', 'status': 'active',
            'support_count': 1, 'regression_count': 0} for index, node in enumerate(self.bank[:2])}
        self.examples = {key: {'source_task_id': value['source_task_id'], 'source_family_id': 'other-family',
            'example_kind': 'training_reference_seed', 'public_task': {'description': 'Historical source.'},
            'reference_seed_code': 'def historical_source():\n    return True\n'} for key, value in self.cards.items()}
        self.cells = fg.schedule(['1', '2'], self.tasks)
        write_json(self.inputs/'tasks.json', self.tasks)
        write_json(self.inputs/'schedule.json', self.cells)
        write_json(self.inputs/'source_examples.json', self.examples)
        write_json(self.inputs/'source_eligibility.json', {'excluded_ids': [self.bank[-1].invariant_id],
            'eligible_ids': list(self.cards), 'source_family_by_card': {key: 'other-family' for key in self.cards}})
        write_json(self.inputs/'family_split.json', {'by_task': {'1': 'train', '2': 'development'},
            'train_families': ['f1'], 'development_families': ['f2']})
        write_json(self.inputs/'protocol.json', {'protocol': fg.PROTOCOL, 'planned_P7': len(self.cells),
            'bank_sources': {level: str(bank) for level in fg.LEVELS}, 'card_count': 2,
            'paid_execution_enabled': False, 'budget_proposed': {'conservative_model_and_embedding_tokens': 10000000,
                'total_physical_HTTP_attempts': 1500, 'embedding_HTTP_attempts_included_in_total': 100}})
        cache = self.root/'shared_inputs/embeddings.sqlite3'
        cache.parent.mkdir(parents=True)
        with closing(sqlite3.connect(cache)) as db:
            db.execute('CREATE TABLE fixture (id INTEGER)')
        self.http, self.generation, self.binding_calls, self.lock = [], 0, 0, threading.RLock()

    def guards(self):
        stack = fixture.FrozenRetestTest.guards(self)
        stack.enter_context(patch.object(fg, 'old_binding_catalog', return_value={}))
        return stack

    def service(self, request, *args, **kwargs):
        body = json.loads(request.data)
        prompt = body['messages'][0]['content']
        if not prompt.startswith('Map the SOURCE'):
            return fixture.FrozenRetestTest.service(self, request, *args, **kwargs)
        with self.lock:
            self.http.append(body)
            self.binding_calls += 1
        source_text, public_text = prompt.split('\nSOURCE:', 1)[1].split('\nPUBLIC TARGET:', 1)
        source, public = json.loads(source_text), json.loads(public_text)
        content = {'operations': [{'action': 'Apply only where supported by the public target.',
            'card_evidence': [{'path': ['positive_principle'], 'quote': source['positive_principle']}],
            'public_evidence': [{'field': 'description', 'quote': public['description']}]}],
            'bound_elements': [], 'unbound_source_details': []}
        result = {'model': base.wiring.SETTINGS['model'], 'choices': [{'index': 0,
            'delta': {'content': json.dumps(content)}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
        return Response(('data: '+json.dumps(result)+'\n\ndata: [DONE]\n\n').encode())

    def select(self, engine, query, limit, nodes):
        self.assertEqual(limit, 3)
        self.assertIsNone(engine.candidate_order)
        self.assertNotIn(self.bank[-1].invariant_id, [n.invariant_id for n in nodes])
        engine.requester(SelectorPrompt('Select fixture', deadline=1e20))
        scores = [{'id': node.invariant_id, 'cosine': .8-index*.1, 'content_hash': str(index)} for index, node in enumerate(nodes)]
        engine.last_hier_trace = {'status': 'completed', 'candidate_order': None,
            'query_hash': str(query.get('task_id')), 'candidate_ids': [s['id'] for s in scores],
            'scores': scores, 'selection_limit': 3}
        return [copy.deepcopy(self.cards[node.invariant_id]) for node in nodes]

    def test_five_levels_share_pool_and_selection_but_L3_L4_are_not_cumulative(self):
        with self.guards():
            study = fg.FrozenGranularity()
            before = copy.deepcopy(study.frozen_before)
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 20)
            self.assertEqual(self.generation, 20)
            self.assertEqual(self.binding_calls, 4)
            self.assertEqual(len(list((study.out/'shared_starts').glob('*.json'))), 4)
            self.assertEqual(before, {arm: [n.to_dict() for n in bank] for arm, bank in study.banks.items()})
            for row in study.rows:
                cards = row['attempts'][0]['generation']['retrieved_cards']
                if row['condition'] == 'L0':
                    self.assertEqual(cards, [])
                else:
                    self.assertEqual([c['invariant_id'] for c in cards], list(self.cards))
                    payload = cards[0]['_cle_memory_view']
                    if row['condition'] == 'L3':
                        self.assertIn('target_operation_template', payload)
                        self.assertNotIn('source_example', payload)
                    if row['condition'] == 'L4':
                        self.assertIn('source_example', payload)
                        self.assertNotIn('target_operation_template', payload)
            self.assertTrue(all(base.read(p)['status'] == 'passed' for p in (study.out/'shared_selection_checks').glob('*.json')))
            calls = len(self.http)
            replay = fg.FrozenGranularity([study.out], offline=True, destination=self.root/'FG_LABELS/replay')
            replay.execute()
            self.assertEqual(len(self.http), calls)
            self.assertEqual(base.read(replay.out/'replay_result.json')['status'], 'passed')

    def test_full_normal_negative_grid_continues_and_L0_repairs_stay_empty(self):
        with self.guards(), patch('methods.sct_trajectory.closed_loop.validate_and_state',
                return_value=({'functional': {'status': 'fail', 'measured': True},
                    'security': {'status': 'pass', 'measured': True}}, 'B')):
            study = fg.FrozenGranularity()
            study.io.physical_open = self.service
            result = study.execute()
            self.assertEqual(result['completed'], 20)
            self.assertTrue(all(len(row['attempts']) == 2 for row in study.rows))
            self.assertTrue(all(value['joint'] == 0 for value in result['arms'].values()))
            for row in study.rows:
                if row['condition'] == 'L0':
                    self.assertTrue(all(not a['generation']['retrieved_cards'] for a in row['attempts']))
            self.assertEqual(self.binding_calls, 4)

    def test_same_family_source_excluded_for_all_levels_before_selection(self):
        first = next(iter(self.examples))
        examples = copy.deepcopy(self.examples)
        examples[first]['source_family_id'] = 'f1'
        write_json(self.inputs/'source_examples.json', examples)
        with self.guards():
            study = fg.FrozenGranularity()
            study.io.physical_open = self.service
            study.execute()
            for row in study.rows:
                if row['task_id'] == '1':
                    trace = row['attempts'][0]['retrieval_trace']
                    self.assertNotIn(first, trace['candidate_ids'])

    def test_unresolved_requests_and_changed_source_examples_block_resume(self):
        previous = self.root/'prior'
        write_json(previous/'journals/cell/requests/pending.json', {'status': 'prepared'})
        with self.guards(), self.assertRaises(ReplayStop):
            fg.FrozenGranularity([previous])
        with self.guards():
            study = fg.FrozenGranularity()
            study.embedding._db.close()
            examples = copy.deepcopy(self.examples)
            examples[next(iter(examples))]['reference_seed_code'] += '\n# changed\n'
            write_json(self.inputs/'source_examples.json', examples)
            with self.assertRaisesRegex(ReplayStop, 'saved_protocol_task_schedule_or_Q_snapshot_changed'):
                fg.FrozenGranularity([study.out])
        self.assertEqual(self.http, [])

    def test_binding_cache_lock_and_exact_source_public_identity(self):
        with self.guards():
            study = fg.FrozenGranularity()
            study.io.physical_open = self.service
            card = next(iter(self.cards.values()))
            public = public_task(self.tasks['1'])
            try:
                with study.io.physical_records(), ThreadPoolExecutor(max_workers=4) as workers:
                    values = list(workers.map(lambda _: study.materials.level_materials([card], public, 'L3'), range(4)))
                self.assertEqual(self.binding_calls, 1)
                identity = fg.binding_hash(source_projection(card), public)
                self.assertTrue(all(v['bindings'][card['invariant_id']]['source_public_sha256'] == identity for v in values))
                path = study.materials.root/'bindings'/(identity[:20]+'.json')
                damaged = base.read(path)
                damaged['public_task']['description'] = 'Another public contract.'
                write_json(path, damaged)
                with self.assertRaisesRegex(ReplayStop, 'exact_source_public_reconciliation'):
                    study.materials.level_materials([card], public, 'L3')
                self.assertEqual(self.binding_calls, 1)
            finally:
                study.embedding._db.close()

    def test_legacy_binding_reuse_requires_exact_public_and_preserves_rule_method(self):
        card = next(iter(self.cards.values()))
        source = source_projection(card)
        public = public_task(base.runner.plt_contract(self.tasks['1']))
        identity = fg.binding_hash(source, public)
        binding = {'card_id': card['invariant_id'], 'public_task': public, 'review_status': 'reviewed',
            'reviewer': 'predeclared source-public rule', 'annotation_method': 'literal_source_public_rule_after_AI_format_failure',
            'operations': [{'action': 'Use this exact source only within the public requirements.',
                'card_evidence': [{'path': ['positive_principle'], 'quote': source['positive_principle']}],
                'public_evidence': [{'field': 'description', 'quote': public['description']}]}],
            'bound_elements': [], 'unbound_source_details': []}
        catalog = {identity: {'source': source, 'public': public, 'binding': binding, 'path': 'old-binding.json'}}
        with self.guards(), patch.object(fg, 'old_binding_catalog', return_value=catalog):
            study = fg.FrozenGranularity()
            study.io.physical_open = self.service
            try:
                with study.io.physical_records():
                    result = study.materials.level_materials([card], public, 'L3')
                    self.assertEqual(self.binding_calls, 0)
                    self.assertEqual(result['bindings'][card['invariant_id']]['annotation_method'], 'literal_source_public_rule_after_AI_format_failure')
                    changed = {**public, 'description': public['description']+' Preserve the supplied object.'}
                    study.materials.level_materials([card], changed, 'L3')
                self.assertEqual(self.binding_calls, 1)
                self.assertNotIn('source_public_sha256', binding)
            finally:
                study.embedding._db.close()

    def test_original_binding_two_format_attempts_then_explicit_rule_fallback(self):
        with self.guards():
            study = fg.FrozenGranularity()
            def invalid(request, *args, **kwargs):
                body = json.loads(request.data)
                with self.lock:
                    self.http.append(body)
                    self.binding_calls += 1
                response = {'model': base.wiring.SETTINGS['model'], 'choices': [{'index': 0,
                    'delta': {'content': '{}'}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
                return Response(('data: '+json.dumps(response)+'\n\ndata: [DONE]\n\n').encode())
            study.io.physical_open = invalid
            card = next(iter(self.cards.values()))
            public = public_task(base.runner.plt_contract(self.tasks['1']))
            try:
                with study.io.physical_records():
                    result = study.materials.level_materials([card], public, 'L3')
                    study.materials.level_materials([card], public, 'L3')
                self.assertEqual(self.binding_calls, 2)
                binding = result['bindings'][card['invariant_id']]
                self.assertEqual(binding['annotation_method'], 'literal_source_public_rule_after_AI_format_failure')
                self.assertTrue(binding['not_human_gold'])
            finally:
                study.embedding._db.close()

    def test_prospective_CV_is_assigned_by_family_and_preserves_prior_roles(self):
        raw = self.root/'raw'
        write_json(raw/'v2/tasks_train.json', [{'family_id': 'familyA'}])
        write_json(raw/'v2/tasks_development.json', [{'family_id': 'familyB'}])
        tasks = {'1': {'family_id': 'familyA'}, '2': {'family_id': 'familyA'},
                 '3': {'family_id': 'familyB'}, '4': {'family_id': 'familyC'}}
        with patch.object(fg, 'RAW', raw):
            result = fg.split_families(tasks)
        self.assertEqual(result['by_task']['1'], 'train')
        self.assertEqual(result['by_task']['2'], 'train')
        self.assertEqual(result['by_task']['3'], 'development')
        self.assertNotIn('familyB', result['family_cv_fold'])
        self.assertEqual(set(result['family_cv_fold']), set(result['train_families']))
        self.assertFalse(result['new_outcomes_used_to_split'])


if __name__ == '__main__':
    unittest.main()

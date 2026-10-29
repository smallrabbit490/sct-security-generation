"""B03R同层生成前完全共享、生成末尾唯一差异和原P7修复语义，零API。"""
import copy
import json
import unittest
from unittest.mock import patch

from configs.cle_v41_relation_20261026 import wiring, offline_check as check
from methods.sct_trajectory.replay_journal import ReplayStop
from methods.sct_trajectory.selector_protocol import SelectorPrompt


def response(content):
    return {'choices': [{'message': {'content': content}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}


class RelationWiringTest(unittest.TestCase):
    def setUp(self):
        self.protocol = check.read(check.CFG / 'protocol.json')
        self.saved = {}
        self.calls = []
        self.guards = check.offline_guards()
        self.guards.__enter__()
        self.addCleanup(self.guards.__exit__, None, None, None)

    def save(self, name, value):
        self.saved[name] = copy.deepcopy(value)

    def source(self, prompt):
        self.calls.append(prompt)
        return response('raw completed response')

    def prefix(self):
        return wiring.SharedPrefix('1409_r1_E', self.save)

    def session(self, prefix, arm='E_bind', source=None, select=None):
        return prefix.session(arm, source or self.source, select or check.denied, self.protocol)

    def test_eight_cells_shared_states_and_independent_repair_queries(self):
        evidence = check.exercise_schedule()
        self.assertEqual(evidence['checks']['shared_c0_prefixes'], 4)
        self.assertEqual(evidence['checks']['shared_initials'], 2)
        self.assertEqual(len(evidence['comparisons']), 4)
        saved = evidence['saved']
        for repeat in (1, 2):
            for kind in ('E', 'K'):
                rows = [saved[f'task_rows/1409_r{repeat}_{kind}_{suffix}'] for suffix in ('bind', 'rel')]
                self.assertEqual([r['arm'] for r in rows], ['P7', 'P7'])
                for row in rows:
                    self.assertEqual(len(row['attempts']), 2)
                    branch = saved['branches/' + row['cell_id']]
                    repairs = [event['input'] for event in branch if event['kind'] == 'retrieval' and
                               event.get('status') == 'completed']
                    self.assertEqual(len(repairs), 1)
                    self.assertEqual(repairs[0]['current_code'], row['attempts'][0]['code'])
                    self.assertEqual(repairs[0]['failure_evidence']['functional']['status'], 'fail')
                    self.assertNotIn(self.protocol['relation_reminder'], json.dumps(repairs))
                self.assertNotEqual(rows[0]['attempts'][0]['code'], rows[1]['attempts'][0]['code'])

    def test_reminder_only_generation_and_common_binding_on_three_stages(self):
        prefix = self.prefix()
        session = self.session(prefix)
        initial = 'Perform initial task threat analysis. public task'
        selector = SelectorPrompt('Select experiences', deadline=123)
        for prompt in (initial, selector, wiring.TARGET_STAGES[0], wiring.TARGET_STAGES[1], wiring.GENERATION,
                       initial, wiring.TARGET_STAGES[0], wiring.TARGET_STAGES[1], wiring.GENERATION):
            session.request(prompt)
        self.assertIs(self.calls[0], initial)
        self.assertIs(self.calls[1], selector)
        self.assertEqual(self.calls[1].deadline, 123)
        for original, actual in zip((initial, selector, *wiring.TARGET_STAGES,
                                     initial, *wiring.TARGET_STAGES), self.calls):
            is_gen = str(original).startswith(wiring.GENERATION)
            self.assertEqual(self.protocol['generic_reminder'] in actual, is_gen)
            self.assertNotIn(self.protocol['relation_reminder'], actual)
            self.assertEqual(wiring.binding_suffix('VALID_SIGNATURES') in actual,
                             str(original).startswith(wiring.TARGET_STAGES))
        self.assertEqual(len(self.protocol['generic_reminder'].split()), 54)
        self.assertEqual(len(self.protocol['relation_reminder'].split()), 54)

    def test_persisted_prefix_replay_does_not_call_source_or_reselect(self):
        prefix = self.prefix()
        first = self.session(prefix)
        query = {'current_code': '', 'threat_analysis': check.INITIAL}
        first.provider(query)
        first.request(wiring.TARGET_STAGES[0])
        first.request(wiring.TARGET_STAGES[1])
        first.request(wiring.GENERATION + ' identical public task/analysis/plan')
        restored = wiring.SharedPrefix(prefix.identity, self.save,
                                       record=json.loads(json.dumps(prefix.record)))
        second = self.session(restored, 'E_rel')
        # 非生成请求和检索必须只读前缀；生成则确实独立调用一次。
        before = len(self.calls)
        second.provider(copy.deepcopy(query))
        raw = second.request(wiring.TARGET_STAGES[0])
        raw['usage']['total_tokens'] = 999
        second.request(wiring.TARGET_STAGES[1])
        self.assertEqual(len(self.calls), before)
        second.request(wiring.GENERATION + ' identical public task/analysis/plan')
        self.assertEqual(len(self.calls), before + 1)
        self.assertTrue(str(self.calls[-1]).endswith(self.protocol['relation_reminder']))
        self.assertEqual(restored.record['events'][1]['response']['usage']['total_tokens'], 15)

    def test_generation_base_mismatch_stops_before_branch_request(self):
        prefix = self.prefix()
        self.session(prefix).request(wiring.GENERATION + ' base A')
        second = self.session(prefix, 'E_rel')
        before = len(self.calls)
        with self.assertRaises(ReplayStop):
            second.request(wiring.GENERATION + ' base B')
        self.assertEqual(len(self.calls), before)

    def test_request_or_query_mismatch_never_falls_back_to_new_request(self):
        for mismatch in ('request', 'query', 'omitted_stage'):
            with self.subTest(mismatch=mismatch):
                prefix = self.prefix()
                first = self.session(prefix)
                first.provider({'current_code': '', 'threat_analysis': check.INITIAL})
                first.request(wiring.TARGET_STAGES[0])
                first.request(wiring.GENERATION)
                second = self.session(prefix, 'E_rel')
                before = len(self.calls)
                with self.assertRaises(ReplayStop):
                    if mismatch == 'query':
                        second.provider({'current_code': 'changed'})
                    else:
                        second.provider({'current_code': '', 'threat_analysis': check.INITIAL})
                        second.request(wiring.GENERATION if mismatch == 'omitted_stage' else
                                       wiring.TARGET_STAGES[0] + ' changed')
                self.assertEqual(len(self.calls), before)

    def test_incomplete_prefix_and_failed_request_cannot_be_reissued(self):
        prefix = self.prefix()
        first = self.session(prefix, source=lambda p: (_ for _ in ()).throw(OSError()))
        with self.assertRaises(ReplayStop):
            first.request(wiring.TARGET_STAGES[0])
        self.assertEqual(prefix.record['events'][0]['status'], 'failed_or_unresolved')
        with self.assertRaises(ReplayStop):
            self.session(prefix, 'E_rel', source=check.denied)

    def test_selector_identity_and_candidate_order_shared_inside_retrieval(self):
        prefix = wiring.SharedPrefix('1409_r1_K', self.save)
        selector = SelectorPrompt('Select original candidates', deadline=321)
        selections = []
        def select(query, request):
            selections.append(query)
            request(selector)
            return copy.deepcopy(check.CARDS), {'candidate_ids': ['a', 'b'], 'selected_ids': ['b', 'a']}
        first = self.session(prefix, 'K_rel', select=select)
        result = first.provider({'current_code': ''})
        first.request(wiring.GENERATION)
        second = self.session(prefix, 'K_bind', select=check.denied)
        self.assertEqual(second.provider({'current_code': ''}), result)
        self.assertIs(self.calls[0], selector)
        self.assertEqual(len(selections), 1)
        self.assertEqual(prefix.record['events'][0]['requests'][0]['input']['selector'], True)
        second.request(wiring.GENERATION)

    def test_native_selector_uses_original_a7_three_cards_and_no_q_order(self):
        nodes, embedding = object(), object()
        with patch('methods.sct_trajectory.retriever.HskTreeRetriever') as factory:
            retriever = factory.return_value
            retriever.search.return_value = check.CARDS
            retriever.last_hier_trace = {'selected_ids': ['b', 'a']}
            select = wiring.native_selector(nodes, embedding)
            result = select({'description': 'public'}, self.source)
            retriever.search.assert_called_once_with({'description': 'public'}, limit=3, pool_nodes=nodes)
            settings = factory.call_args.kwargs
            self.assertEqual(settings['retrieval_mode'], 'semantic_llm')
            self.assertIsNone(settings['candidate_order'])
            self.assertIsNone(settings['semantic_delta'])
            self.assertIs(settings['embedding_client'], embedding)
            self.assertEqual(result[0], check.CARDS)

    def test_malformed_analysis_and_missing_adoption_retained_not_forced(self):
        def request_for(identity):
            def request(prompt):
                if str(prompt).startswith('Perform experience-conditioned'):
                    return response('not JSON')
                if str(prompt).startswith('Plan the implementation'):
                    return response(json.dumps({'Preserved_Func': 'interface', 'Patch_Scope': 'body'}))
                if str(prompt).startswith(wiring.GENERATION):
                    return response('def load_file(file_name, signature):\n    return 0')
                return response(json.dumps(check.INITIAL))
            return request
        cells = [c for c in check.read(check.CFG / 'schedule.json') if c['repeat'] == 1]
        task = {'index': 1409, 'family_id': 'fixture', 'task_description': {'description': 'public'}}
        passed = {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}
        with patch('methods.sct_trajectory.closed_loop.validate_and_state', return_value=(passed, {})):
            result = wiring.run_repeat(task, cells, protocol=self.protocol, request_for=request_for,
                select=lambda q, r: (copy.deepcopy(check.CARDS), {'status': 'completed'}), save=self.save)
        self.assertEqual(len(result['rows']), 4)
        for row in result['rows']:
            self.assertEqual(len(row['attempts']), 1)  # 原首次Joint早停
            generation = row['attempts'][0]['generation']
            self.assertEqual(generation['cards'], [])
            self.assertIn('experience_analysis:', generation['error_type'])
            if row['relation_arm'].startswith('K_'):
                self.assertEqual(generation['adoption']['error'], 'missing_applied_experience_ids')

    def test_transport_stop_not_swallowed_as_native_model_failure(self):
        cells = [c for c in check.read(check.CFG / 'schedule.json') if c['repeat'] == 1]
        calls = []
        def factory(identity):
            def request(prompt):
                calls.append(identity)
                if str(prompt).startswith('Perform initial'):
                    return response(json.dumps(check.INITIAL))
                raise OSError('fixture transport interruption')
            return request
        with self.assertRaises(ReplayStop):
            wiring.run_repeat({'index': 1409, 'family_id': 'fixture', 'task_description': {}}, cells,
                protocol=self.protocol, request_for=factory,
                select=lambda q, r: ([], {'status': 'completed'}), save=self.save)
        self.assertEqual(len(calls), 2)  # 共享初析 + 首次复析后停止，无后续臂请求

    def test_native_last_attempt_delivered_even_when_security_gets_worse(self):
        def factory(identity):
            index = 0
            def request(prompt):
                nonlocal index
                if str(prompt).startswith(wiring.GENERATION):
                    index += 1
                    return response('def load_file(file_name, signature):\n    return ' + str(index))
                if str(prompt).startswith('Plan the implementation'):
                    return response(json.dumps({'Preserved_Func': 'interface', 'Patch_Scope': 'body'}))
                return response(json.dumps({**check.INITIAL, 'applied_experience_ids': []}))
            return request
        def validate(task, code, timeout):
            second = code.endswith('2')
            return {'functional': {'status': 'pass' if second else 'fail'},
                    'security': {'status': 'fail' if second else 'pass'}}, {}
        cells = [c for c in check.read(check.CFG / 'schedule.json') if c['repeat'] == 1]
        with patch('methods.sct_trajectory.closed_loop.validate_and_state', side_effect=validate):
            result = wiring.run_repeat({'index': 1409, 'family_id': 'fixture', 'task_description': {}}, cells,
                protocol=self.protocol, request_for=factory,
                select=lambda q, r: ([], {'status': 'completed'}), save=self.save)
        for row in result['rows']:
            self.assertEqual(len(row['attempts']), 2)
            self.assertTrue(row['attempts'][-1]['code'].endswith('2'))
            self.assertFalse(row['attempts'][-1]['security'])
            self.assertFalse(row['attempts'][-1]['joint'])


if __name__ == '__main__':
    unittest.main()

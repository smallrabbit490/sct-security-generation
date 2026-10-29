"""公开绑定实验的提示边界、共同终选与两轮原P7语义：全部零API。"""
import copy
import json
import unittest
from unittest.mock import patch

from configs.cle_v41_migration_20261025 import binding_study as study
from methods.cle_ablation import runner
from methods.sct_trajectory.replay_journal import ReplayStop


INITIAL = {'vulnerability_hypothesis': ['specific risk'], 'functional_invariants': ['valid behavior']}


class BindingStudyTest(unittest.TestCase):
    def test_only_three_exact_stages_are_changed(self):
        received = []
        request = study.stage_request(lambda prompt: received.append(prompt), 'ALLOWED_DOMAINS')
        class SelectorPrompt(str):
            pass
        selector = SelectorPrompt('Select experiences for this query')
        for prompt in ['Perform initial task threat analysis. old contract', selector, *study.TARGET_STAGES]:
            request(prompt)
        self.assertEqual(received[0], 'Perform initial task threat analysis. old contract')
        self.assertIs(received[1], selector)
        self.assertTrue(all(p.endswith(study.binding_suffix('ALLOWED_DOMAINS')) for p in received[2:]))

    def test_control_request_object_and_payload_stay_identical(self):
        seen = []
        prompt = study.TARGET_STAGES[-1] + ' unchanged original'
        study.stage_request(lambda p: seen.append(p))(prompt)
        self.assertIs(seen[0], prompt)
        suffix = study.binding_suffix('VALID_SIGNATURES')
        self.assertNotIn('fixture', suffix)
        self.assertNotIn('implementation_constraints', suffix)

    def test_native_repair_initial_and_query_remain_without_new_payload(self):
        received, queries = [], []
        def base(prompt):
            received.append(str(prompt))
            if str(prompt).startswith('Generate complete'):
                value = 'def add(a,b):\n    return a+b'
            elif str(prompt).startswith('Plan the implementation'):
                value = json.dumps({'Preserved_Func': 'add', 'Patch_Scope': 'body'})
            else:
                value = json.dumps(INITIAL)
            return {'choices': [{'message': {'content': value}, 'finish_reason': 'stop'}],
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
        def empty(query):
            queries.append(copy.deepcopy(query))
            return [], {'status': 'completed'}
        evidence = {'functional': {'status': 'fail'}, 'security': {'status': 'pass'}}
        with patch.object(runner, 'plt_contract', return_value={'task_id': '1', 'description': 'add a and b'}), \
             patch('methods.sct_trajectory.closed_loop.validate_and_state', return_value=(evidence, {})):
            row = runner.run_one('PLT', {'index': 1}, 'P7', study.stage_request(base, 'ALLOWED_DOMAINS'),
                {'full': []}, initial_analysis=INITIAL, retrieval_provider=empty)
        self.assertEqual(len(row['attempts']), 2)
        self.assertEqual(len(queries), 2)
        self.assertTrue(queries[1]['current_code'])
        self.assertTrue(all('Public runtime binding preservation:' not in json.dumps(q) for q in queries))
        initial_prompts = [p for p in received if p.startswith('Perform initial task threat analysis.')]
        self.assertEqual(len(initial_prompts), 1)  # c0共享，c1原生独立初析
        self.assertNotIn('Public runtime binding preservation:', initial_prompts[0])
        changed = [p for p in received if 'Public runtime binding preservation:' in p]
        self.assertEqual(len(changed), 6)  # c0/c1各复析、规划、生成

    def test_shared_first_card_ids_order_and_independent_repairs(self):
        first, repair = [], []
        cards = [{'invariant_id': 'b'}, {'invariant_id': 'a'}]
        def select(query):
            first.append(copy.deepcopy(query))
            return cards, {'status': 'completed', 'selected_ids': ['b', 'a']}
        def repair_select(query):
            repair.append(query)
            return [], {'status': 'completed'}
        shared = study.SharedFirstSelection(select)
        query = {'current_code': '', 'threat_analysis': INITIAL}
        b = shared.provider(query, repair_select)
        d = shared.provider(copy.deepcopy(query), repair_select)
        self.assertEqual(b, d)
        self.assertEqual([c['invariant_id'] for c in d[0]], ['b', 'a'])
        d[0].clear()
        self.assertEqual(len(shared.cards), 2)
        shared.provider({'current_code': 'B own code'}, repair_select)
        shared.provider({'current_code': 'D own code'}, repair_select)
        self.assertEqual(len(first), 1)
        self.assertEqual(len(repair), 2)
        with self.assertRaises(ReplayStop):
            shared.provider({'current_code': '', 'threat_analysis': {'changed': True}}, repair_select)
        self.assertEqual(len(first), 1)

    def test_16_cells_first8_included(self):
        cells = study.schedule({'task_ids': ['1322', '1409']})
        self.assertEqual(sum(len(c['arms']) for c in cells), 16)
        self.assertEqual(sum(len(c['arms']) for c in cells if c['group'] == 'technical'), 8)
        self.assertEqual(len({c['pair_id'] + '_' + arm for c in cells for arm in c['arms']}), 16)
        self.assertEqual([c['repeat'] for c in cells], [1, 1, 2, 2])

    def test_static_signal_separates_read_shadow_mutation_and_unknown(self):
        self.assertEqual(study.binding_signal('def f():\n return ALLOWED_DOMAINS', 'ALLOWED_DOMAINS')['status'], 'consistent')
        self.assertEqual(study.binding_signal('ALLOWED_DOMAINS=[]', 'ALLOWED_DOMAINS')['status'], 'violated')
        self.assertEqual(study.binding_signal('ALLOWED_DOMAINS.clear()', 'ALLOWED_DOMAINS')['status'], 'violated')
        self.assertEqual(study.binding_signal('ALLOWED_DOMAINS[0]="x"', 'ALLOWED_DOMAINS')['status'], 'violated')
        self.assertEqual(study.binding_signal('def f():\n return []', 'ALLOWED_DOMAINS')['status'], 'unmeasured')


if __name__ == '__main__':
    unittest.main()

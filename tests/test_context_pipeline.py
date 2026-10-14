"""真实卡片转换及分析—检索—再分析信息流回归，不调用在线模型。"""
import json

from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode, LanguageLeaf
from methods.sct_trajectory.retriever import HskTreeRetriever


def test_actual_card_preserves_kind_and_applicability():
    node = SecurityInvariantNode('n', '22', 'resolve', applicability='only filesystem paths',
                                 source={'kind': 'direct_A', 'exclusion_conditions': 'not URLs'})
    node.language_leaves['python'] = LanguageLeaf('python', [], [], '')
    card = HskTreeRetriever(HskTree())._to_card({'language': 'python'}, node, base=1, llm=None)
    assert card['kind'] == 'direct_A'
    assert card['applicability'] == 'only filesystem paths'
    assert card['exclusion_conditions'] == 'not URLs'


def test_context_order_and_failure_evidence_reach_retrieval_and_reanalysis():
    from methods.sct_trajectory.context_pipeline import run_context_pipeline
    events = []
    analysis = {'vulnerability_hypothesis': ['path escape'], 'functional_invariants': ['read valid file'],
                'sources': ['user path'], 'sinks': ['open'], 'api_assumptions': ['resolve symlinks']}
    answers = [analysis, {**analysis, 'applied_experience_ids': ['n']},
               {'Preserved_Func': 'read', 'Patch_Scope': 'resolve', 'Avoidance_List': []},
               'def read(path): return path']

    def request(prompt):
        events.append(('model', prompt))
        value = answers.pop(0)
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value) if isinstance(value, dict) else value}}]}

    def retrieve(query):
        events.append(('retrieve', query))
        assert query['threat_analysis']['sinks'] == ['open']
        assert query['current_code'] == 'old implementation'
        assert query['failure_evidence']['security']['details'] == 'boundary failed'
        return [{'invariant_id': 'n', 'kind': 'direct_A', 'applicability': 'local paths',
                 'fix_directive': 'resolve before containment', 'status': 'provisional'}]

    result = run_context_pipeline({'description': 'x'*1600+'END_CONTRACT'}, [], requester=request,
                                  cards_provider=retrieve, reference_code='old implementation',
                                  previous_evidence={'security': {'status': 'fail', 'details': 'boundary failed'}})
    assert [e[0] for e in events] == ['model', 'retrieve', 'model', 'model', 'model']
    assert 'END_CONTRACT' in events[0][1] and 'END_CONTRACT' in events[2][1]
    assert 'resolve before containment' in events[2][1]
    assert 'local paths' in events[2][1] and 'provisional' in events[2][1]
    assert result['cards'][0]['kind'] == 'direct_A'
    assert result['analysis_parsed']['applied_experience_ids'] == ['n']
    assert result['code'].startswith('def read')


def test_all_retrieval_layers_receive_complete_contract_and_failure():
    from methods.sct_trajectory.hier_retrieval import hierarchical_select
    node = SecurityInvariantNode('n', '22', 'resolve', applicability='filesystem only',
                                 source={'kind': 'direct_A', 'fix_directive': 'resolve symlinks'})
    node.language_leaves['python'] = LanguageLeaf('python', [], [], '')
    seen = []
    answers = [{'cwes': ['22']}, {'kinds': ['direct_A']}, {'ids': ['n']}]
    def request(prompt):
        seen.append(prompt)
        return {'choices': [{'message': {'content': json.dumps(answers.pop(0))}}]}
    hierarchical_select(task={'CWE_ID': '22', 'description': 'x'*1500+'TAIL',
                               'failure_evidence': {'details': 'escape after decode'}},
                        nodes=[node], requester=request, language='python', rule_score=lambda n: 1, limit=3)
    assert all('TAIL' in prompt and 'escape after decode' in prompt for prompt in seen)
    assert 'filesystem only' in seen[-1]


def test_distillation_does_not_infer_overdefense_from_boolean_state():
    from methods.sct_trajectory.distillation import build_round_prompt, build_distillation_prompt
    common = dict(cwe='22', task_contract='x'*1000+'TAIL_CONTRACT')
    round_prompt = build_round_prompt(**common, round_index=1, state='C', code='def f(): pass', evidence={})
    transition = build_distillation_prompt(**common, kind='C_stalled', before='C', after='C',
        code_before='', code_after='', patch_diff='', failure_type='unknown')
    for prompt in (round_prompt, transition):
        assert 'TAIL_CONTRACT' in prompt
        assert ('not the state label alone' in prompt or 'Do not infer causality from F/S flags alone' in prompt)
        assert 'Functional failure equals overdefense' not in prompt


def test_training_rollout_passes_initial_and_failure_context_to_retriever(monkeypatch):
    from methods.sct_trajectory import closed_loop as cl
    from methods.sct_trajectory.error_ledger import ErrorLedger
    runner = cl.CleRunner(lambda p: {}, HskTree(), ErrorLedger(), context_pipeline=True,
                          inject_prev_evidence=True)
    queries = []
    class Retriever:
        def search(self, query, **kwargs):
            queries.append(query)
            return [{'invariant_id': 'n', 'kind': 'direct_A'}]
    def pipeline(task, cards, **kwargs):
        assert kwargs['context_mode'] is True
        selected = kwargs['cards_provider']({**task, 'threat_analysis': {'sinks': ['open']},
            'current_code': kwargs['reference_code'], 'failure_evidence': kwargs['previous_evidence']})
        return {'code': 'def f(): return 1', 'cards': selected, 'analysis_parsed': {}, 'plan_parsed': {}}
    monkeypatch.setattr(cl, 'run_pipeline', pipeline)
    monkeypatch.setattr(cl, 'validate_and_state', lambda *a, **k: (
        {'functional': {'status': 'pass'}, 'security': {'status': 'fail', 'details': 'escape'}}, 'B'))
    monkeypatch.setattr(runner, '_distill_round_inline', lambda **k: 0)
    trace = runner._run_rollout({'index': 7, 'CWE_ID': '22', 'task_description': {'function_name': 'f', 'description': 'x'*1000+'CONTRACT_END'}},
                                 Retriever(), repairs=1)
    assert len(queries) == 2
    assert queries[1]['threat_analysis']['sinks'] == ['open']
    assert queries[1]['failure_evidence']['security']['status'] == 'fail'
    assert 'details' not in queries[1]['failure_evidence']['security']
    assert queries[1]['current_code'] == 'def f(): return 1'
    assert trace.retrieved_per_round[0][0]['kind'] == 'direct_A'
    assert trace.agent_context[0]['retrieved_cards'][0]['kind'] == 'direct_A'
    assert 'CONTRACT_END' in trace.task_contract


def test_seed_conversion_retains_action_and_exclusions():
    from methods.sct_trajectory.closed_loop import _seed_node_from_card
    node = _seed_node_from_card({'id': 's', 'principle': 'contain path',
        'recommended_action': 'resolve before check', 'non_applicable_boundary': 'not URLs',
        'dangerous_pattern': 'string prefix'})
    assert node.source['fix_directive'] == 'resolve before check'
    assert node.source['exclusion_conditions'] == 'not URLs'
    assert node.negative_guardrail == 'string prefix'


def test_distillation_retains_reanalysis_and_code_tail():
    from methods.sct_trajectory.distillation import build_round_prompt, build_distillation_prompt
    analysis = {'adaptations': 'x' * 1200 + 'ADAPTATION_TAIL'}
    code = 'x' * 3200 + 'CODE_TAIL'
    common = dict(cwe='22', evidence={}, analysis=analysis, plan={'actions': 'x' * 1200 + 'PLAN_TAIL'})
    prompts = [build_round_prompt(**common, round_index=1, state='C', code=code),
               build_distillation_prompt(**common, kind='C_stalled', before='C', after='C',
                   code_before='', code_after=code, patch_diff='', failure_type='unknown')]
    for prompt in prompts:
        assert all(tail in prompt for tail in ('ADAPTATION_TAIL', 'PLAN_TAIL', 'CODE_TAIL'))

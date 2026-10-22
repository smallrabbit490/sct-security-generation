import json
from unittest.mock import patch

from methods.cle_ablation.run_memory_q import prepare_shared_initial
from methods.cle_ablation.runner import generate, run_one


INITIAL = {'vulnerability_hypothesis': ['Unsafe input'], 'functional_invariants': ['Keep the interface']}


def test_shared_preparation_uses_only_native_public_contract_once():
    prompts = []
    task = {'index': 9, 'CWE_ID': '74', 'task_description': {'description': 'Escape text'},
            'ground_truth': 'SECRET', 'unittest': 'SECRET'}
    def request(prompt):
        prompts.append(prompt)
        return {'choices': [{'message': {'content': json.dumps(INITIAL)}}]}
    result = prepare_shared_initial(task, request)
    assert len(prompts) == 1 and 'SECRET' not in prompts[0]
    assert '"task_id": "9"' in prompts[0] and '"language": "python"' in prompts[0]
    assert result['initial_analysis'] == INITIAL and result['error_type'] is None


def test_shared_preparation_preserves_parse_failure_without_retry():
    calls = []
    def request(prompt):
        calls.append(prompt)
        return {'choices': [{'message': {'content': 'not json'}}]}
    result = prepare_shared_initial({'index': 1, 'task_description': {}}, request)
    assert len(calls) == 1 and result['error_type']
    assert result['initial_analysis'] == {'unmeasured': True}


def test_generate_reuses_initial_but_still_reanalyzes_plans_and_generates():
    responses = [json.dumps({**INITIAL, 'applied_experience_ids': []}),
                 json.dumps({'Preserved_Func': 'Interface', 'Patch_Scope': 'Escape text'}), 'def f(): return 1']
    calls, queries = [], []
    def request(prompt):
        calls.append(prompt)
        return {'choices': [{'message': {'content': responses[len(calls)-1]}}]}
    def provider(query):
        queries.append(query)
        return []
    result = generate('P7', {'description': 'Implement f'}, request, provider, initial_analysis=INITIAL)
    assert len(calls) == 3 and queries[0]['threat_analysis'] == INITIAL
    assert result['stages'][0] == {'stage': 'initial_analysis', 'status': 'reused'}
    assert result['workflow_completed']


def test_only_c0_reuses_initial_c1_uses_own_code_and_safe_feedback():
    seen = []
    def generation(arm, contract, request, provider, **kwargs):
        seen.append(kwargs)
        return {'code': 'def f(): return 1', 'workflow_completed': True}
    evidence = {'functional': {'status': 'fail'}, 'security': {'status': 'pass'}}
    with patch('methods.cle_ablation.runner.generate', side_effect=generation), patch(
            'methods.sct_trajectory.closed_loop.validate_and_state', return_value=(evidence, 'C')):
        result = run_one('PLT', {'index': 1, 'task_description': {}}, 'P7', None,
                         {'full': []}, initial_analysis=INITIAL)
    assert len(result['attempts']) == 2
    assert seen[0]['initial_analysis'] == INITIAL and 'initial_analysis' not in seen[1]
    assert seen[1]['reference'] == 'def f(): return 1'
    assert seen[1]['feedback']['functional']['status'] == 'fail'

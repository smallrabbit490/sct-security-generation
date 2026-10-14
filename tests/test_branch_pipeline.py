import json
from copy import deepcopy
import pytest


def response(value):
    return {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value) if isinstance(value, dict) else value}}]}


def test_infrastructure_failure_cannot_be_distilled_as_negative():
    from methods.sct_trajectory.branch_pipeline import run_branches, branch_trace, distill_branches
    result = run_branches({}, requester=requester([]), retrieve=lambda q: [], workers=1,
        validate=lambda c: {'functional': {'status': 'fail'}, 'security': {'status': 'fail'},
                            'metadata': {'error_type': 'plt_validator_exception'}})
    assert all(not b['measured'] and b['state'] == 'U' for b in result['branches'])
    trace = branch_trace({'index': 1}, result)
    value = distill_branches(trace, lambda p: response({'negative': [{'evidence_branch_ids': ['b1']}]}))
    assert value['negative'] == []


def test_duplicate_plans_are_explicitly_invalid_diversity():
    from methods.sct_trajectory.branch_pipeline import run_branches
    call = requester([])
    plan = {'strategy': 'same', 'Preserved_Func': 'f', 'Patch_Scope': 'same',
            'Security_Actions': ['check'], 'distinct_from_others': 'same',
            'applied_experience_ids': [], 'rejected_experiences': []}
    result = run_branches({}, requester=lambda p: response({'plans': [plan]*3}) if 'BRANCH_PLAN' in p else call(p),
        retrieve=lambda q: [], validate=lambda c: {}, workers=1)
    assert result['diversity_valid'] is False
    assert 'duplicate_plans' in result['diversity_errors']


def test_compatible_card_ids_preserve_all_versions_and_reject_missing_ids():
    from methods.sct_trajectory.branch_pipeline import run_branches
    result = run_branches({}, requester=requester([]), retrieve=lambda q: [{'id': 'x'}, {'id': 'y'}],
                          validate=lambda c: {}, workers=1)
    assert set(result['branches'][0]['card_hashes']) == {'x', 'y'}
    with pytest.raises(ValueError, match='stable id'):
        run_branches({}, requester=requester([]), retrieve=lambda q: [{}], validate=lambda c: {})


def test_raw_training_rows_rejected_before_any_prompt():
    from methods.sct_trajectory.branch_pipeline import run_branches
    events = []
    with pytest.raises(ValueError, match='private_task_fields'):
        run_branches({'unittest': 'SECRET'}, requester=requester(events), retrieve=lambda q: [], validate=lambda c: {})
    assert events == []


def requester(events, *, duplicate=False, broken=False):
    def call(prompt):
        events.append(prompt)
        if 'BRANCH_PLAN' in prompt:
            return response({'plans': [{'strategy': f'strategy{i}', 'Preserved_Func': 'f', 'Patch_Scope': f'api{i}', 'distinct_from_others': f'choice{i}'} for i in range(3)]})
        if 'BRANCH_CODE' in prompt:
            i = sum('BRANCH_CODE' in p for p in events)
            if broken and i == 2:
                raise TimeoutError('private detail')
            return response(f'def f(): return {1 if duplicate else i}')
        return response({'vulnerability_hypothesis': ['risk'], 'functional_invariants': ['f']})
    return call


def test_branches_all_generate_before_tests_and_preserve_cards():
    from methods.sct_trajectory.branch_pipeline import run_branches
    events, validations = [], []
    cards = [{'invariant_id': 'e1', 'fix_directive': 'specific API', 'status': 'provisional'}]
    before = deepcopy(cards)
    def validate(code):
        assert sum('BRANCH_CODE' in p for p in events) == 3
        validations.append(code)
        return {'functional': {'status': 'pass'}, 'security': {'status': 'pass' if '3' in code else 'fail'}}
    result = run_branches({'description': 'contract'}, requester=requester(events),
                          retrieve=lambda q: cards, validate=validate, workers=1)
    assert len(result['branches']) == len(validations) == 3
    assert result['branches'][0]['state'] == 'B'
    assert result['branches'][2]['state'] == 'A'
    assert result['selected_index'] == 2
    assert result['selection_policy'] == 'training_oracle_first_joint_else_first'
    assert result['branches'][0]['cards'][0]['fix_directive'] == 'specific API'
    assert len(result['branches'][0]['card_hashes']['e1']) == 64
    assert cards == before


def test_duplicate_codes_and_failure_are_evidence_not_missing_branches():
    from methods.sct_trajectory.branch_pipeline import run_branches
    events = []
    result = run_branches({}, requester=requester(events, duplicate=True, broken=True), retrieve=lambda q: [],
                          validate=lambda code: {'functional': {'status': 'pass'}, 'security': {'status': 'fail'}}, workers=1)
    assert len(result['branches']) == 3
    assert result['branches'][1]['error_type'] == 'TimeoutError'
    assert result['branches'][1]['measured'] is False
    assert result['branches'][2]['duplicate_of'] == 'b1'
    assert 'private detail' not in json.dumps(result)


def test_sampling_control_uses_identical_plan_and_prompt():
    from methods.sct_trajectory.branch_pipeline import run_branches
    events = []
    result = run_branches({}, requester=requester(events), retrieve=lambda q: [], validate=lambda c: {},
                          mode='resample', workers=1)
    prompts = [p for p in events if 'BRANCH_CODE' in p]
    assert len(prompts) == 3 and len(set(prompts)) == 1
    assert all(not b['measured'] for b in result['branches'])


def test_trace_does_not_invent_repairs_and_distillation_sees_all_branches():
    from methods.sct_trajectory.branch_pipeline import run_branches, branch_trace, distill_branches
    result = run_branches({}, requester=requester([]), retrieve=lambda q: [], validate=lambda c: {}, workers=1)
    trace = branch_trace({'index': 9, 'CWE_ID': '22', 'task_description': {}}, result, round_index=2)
    assert trace.transitions == [] and len(trace.states) == 1
    assert len(trace.branches) == 3 and trace.round == 2
    prompts = []
    def request(prompt):
        prompts.append(prompt)
        return response({'positive': [{'high_level_invariant': 'x', 'positive_principle': 'y', 'evidence_branch_ids': ['b1']}],
                         'negative': [], 'error_ledger': []})
    distilled = distill_branches(trace, request)
    assert distilled['positive'] == []  # 全部缺测，不能晋升成功经验
    assert all(b['code'] in prompts[0] for b in result['branches'])
    assert 'parallel' in prompts[0]


def test_all_branch_templates_are_english_and_chinese_plan_is_rejected():
    from methods.sct_trajectory.branch_pipeline import run_branches
    base = requester([])
    prompts = []
    def request(prompt):
        prompts.append(prompt)
        if 'BRANCH_PLAN' in prompt:
            return response({'plans': [{'Preserved_Func': '保持契约', 'Patch_Scope': '改变代码'}] * 3})
        return base(prompt)
    result = run_branches({}, requester=request, retrieve=lambda q: [], validate=lambda c: {}, workers=1)
    assert result['plan_error'] == 'EnglishPolicyError'
    assert all(not any('\u3400' <= c <= '\u9fff' for c in prompt) for prompt in prompts)


def test_branch_distillation_rejects_chinese_experience():
    from methods.sct_trajectory.branch_pipeline import run_branches, branch_trace, distill_branches
    result = run_branches({}, requester=requester([]), retrieve=lambda q: [], workers=1,
        validate=lambda c: {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}})
    actual = distill_branches(branch_trace({'index': 1}, result), lambda prompt: response({
        'positive': [{'evidence_branch_ids': ['b1'], 'positive_principle': '保持契约'}]}))
    assert actual['positive'] == []
    assert actual['error'] == 'EnglishPolicyError'

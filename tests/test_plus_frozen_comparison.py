"""冻结 Plus 对比的契约、反馈和修复边界回归。"""
import pytest
from methods.sct_trajectory.run_plus_frozen_comparison import task_contract, repair_feedback, summarize


def test_contract_is_complete_and_contains_no_answers():
    row = {'ID': 'CWE-20_01', 'Problem': 'x' * 1800, 'Entry_Point': 'target',
           'Secure Code': 'SECRET', 'Test': 'SECRET', 'Insecure Code': 'old'}
    contract = task_contract(row)
    assert contract['description'] == row['Problem']
    assert contract['entry_point'] == 'target'
    assert 'SECRET' not in str(contract)
    assert contract['task_id'] == 'Plus:CWE-20_01'
    assert contract['CWE_ID'] == '20'


def test_feedback_does_not_expose_test_literals():
    evidence = {'functional': {'status': 'fail', 'details': 'AssertionError: SECRET'},
                'security': {'status': 'pass', 'details': ''}}
    feedback = repair_feedback(evidence)
    assert feedback['functional']['details'] == 'AssertionError'
    assert 'SECRET' not in str(feedback)


def test_summary_uses_same_denominator():
    rows = [{'method': 'prompt', 'attempts': [{'functional': True, 'security': True, 'joint': True}]},
            {'method': 'prompt', 'attempts': [{'functional': False, 'security': True, 'joint': False},
                                              {'functional': True, 'security': True, 'joint': True}]}]
    result = summarize(rows)['prompt']
    assert result['first']['joint'] == 1
    assert result['final']['joint'] == 2
    assert result['total'] == 2
    assert result['repair_successes'] == 1


def test_both_arms_receive_same_model_view_and_repair_evidence():
    from methods.sct_trajectory.run_plus_frozen_comparison import generate
    seen = []
    def request(prompt):
        seen.append(prompt)
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': 'def target(): return 1'}}]}
    def pipeline(task, cards, **kwargs):
        assert 'SECRET' not in str(task)
        assert kwargs['previous_evidence']['functional']['status'] == 'fail'
        assert kwargs['reference_code'] == 'old'
        return {'code': 'def target(): return 1', 'error_type': None}
    contract = task_contract({'ID': 'CWE-20_01', 'Problem': 'full description', 'Entry_Point': 'target', 'Test': 'SECRET'})
    evidence = {'functional': {'status': 'fail', 'details': 'AssertionError: SECRET'}}
    generate('prompt_concat', contract, [], request, 'old', evidence, pipeline=pipeline)
    generate('cle_four_agent', contract, [], request, 'old', evidence, pipeline=pipeline)
    assert 'full description' in seen[0] and 'old' in seen[0]
    assert 'SECRET' not in seen[0]


def test_internal_feedback_is_explicit_and_official_details_stay_redacted():
    from methods.sct_trajectory.run_plus_frozen_comparison import generation_feedback
    official = {'security': {'status': 'fail', 'details': 'AssertionError: HIDDEN_INPUT'}}
    internal = {'source': 'self_generated_internal', 'cases': [{'id': 's1', 'error': 'actual escaped root'}]}
    feedback = generation_feedback(official, internal)
    assert 'HIDDEN_INPUT' not in str(feedback)
    assert feedback['internal_checks'] == internal


@pytest.mark.parametrize('context_mode', [False, True])
def test_empty_code_fence_is_explicit_error(context_mode):
    from methods.sct_trajectory.run_plus_frozen_comparison import generate
    request = lambda prompt: {'choices': [{'message': {'content': '```python\n\n```'}}]}
    with pytest.raises(ValueError, match='empty_code'):
        generate('prompt_concat', {}, [], request, context_mode=context_mode)

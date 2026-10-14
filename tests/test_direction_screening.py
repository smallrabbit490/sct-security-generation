"""联合诊断协议的真实边界测试，不需要模型或 Docker。"""
import importlib
import pytest


def protocol():
    try:
        return importlib.import_module('methods.direction_screening.protocol')
    except ModuleNotFoundError:
        pytest.fail('联合诊断协议模块尚未实现')


def test_family_sampling_is_deterministic_and_disjoint():
    p = protocol()
    rows = [{'index': i, 'family_id': str(i // 2), 'CWE_ID': str(i % 3)} for i in range(48)]
    first = p.sample_families(rows, 8)
    second = p.sample_families(rows, 8, excluded={r['family_id'] for r in first})
    assert first == p.sample_families(list(reversed(rows)), 8)
    assert len({r['family_id'] for r in first}) == 8
    assert not {r['family_id'] for r in first} & {r['family_id'] for r in second}
    with pytest.raises(ValueError):
        p.sample_families(rows, 25)


def test_public_task_and_feedback_never_expose_hidden_values():
    p = protocol()
    row = {'index': 1, 'CWE_ID': 79, 'task_description': {'function_name': 'f', 'description': 'return input'},
           'ground_truth': {'patched_code': 'ANSWER'}, 'unittest': {'testcases': 'SECRET_INPUT'}}
    assert 'ANSWER' not in str(p.public_task(row))
    assert 'SECRET_INPUT' not in str(p.public_task(row))
    evidence = {'functional': {'status': 'fail', 'details': 'SECRET_INPUT', 'error_type': 'plt_test_failed'},
                'syntax_or_compile': {'status': 'pass'}}
    assert 'SECRET_INPUT' not in str(p.safe_evidence(evidence))
    assert p.safe_evidence(evidence)['syntax_or_compile']['status'] == 'pass'


def test_unmeasured_is_not_success_or_measured_harm():
    p = protocol()
    e = {'syntax_or_compile': {'status': 'pass'}, 'functional': {'status': 'pass'},
         'security': {'status': 'fail', 'error_type': 'environment_error'}}
    outcome = p.outcome(e)
    assert not outcome['joint']
    assert not outcome['measured']
    e['security'] = {'status': 'pass'}
    assert p.outcome(e)['joint']


def test_selector_uses_public_evidence_not_official_score():
    p = protocol()
    candidates = [{'code': 'def f(): return 1', 'public_score': 1, 'joint': False},
                  {'code': 'def f(): return 2', 'public_score': 0, 'joint': True}]
    assert p.select_public(candidates) == 0
    candidates[0]['joint'], candidates[1]['joint'] = True, False
    assert p.select_public(candidates) == 0

"""内部测试只使用自生成断言，不接触正式测试或参考答案。"""
import importlib
import json


def api():
    assert importlib.util.find_spec('methods.sct_trajectory.internal_checks'), '内部检查模块尚未实现'
    return importlib.import_module('methods.sct_trajectory.internal_checks')


def suite(code):
    return {'cases': [{'id': 'f1', 'kind': 'functional', 'purpose': 'identity', 'code': code}]}


def test_local_pass_and_failure_preserve_assert_message():
    module = api()
    check = suite("actual = candidate(3)\nassert actual == 3, f'expected 3, actual {actual!r}'")
    assert module.execute_checks('def f(x): return x', 'f', check)['passed'] == 1
    result = module.execute_checks('def f(x): return 0', 'f', check)
    assert result['measured'] and result['passed'] == 0
    assert result['cases'][0]['status'] == 'fail'
    assert 'actual 0' in result['cases'][0]['error']


def test_empty_suite_is_unmeasured():
    result = api().execute_checks('def f(): pass', 'f', {'cases': []})
    assert result['measured'] is False and result['passed'] == 0


def test_syntax_error_is_not_assertion_failure():
    result = api().execute_checks('def f(:', 'f', suite('assert candidate(1) == 1'))
    assert result['cases'][0]['status'] == 'syntax_error'


def test_timeout_is_recorded():
    result = api().execute_checks('def f(x):\n while True: pass', 'f', suite('assert candidate(1) == 1'), timeout=1)
    assert result['cases'][0]['status'] == 'timeout'


def test_cases_are_isolated_and_secrets_not_inherited(monkeypatch):
    monkeypatch.setenv('INTERNAL_CHECK_SECRET', 'forbidden')
    case = "import os\nassert 'INTERNAL_CHECK_SECRET' not in os.environ\nassert candidate() == 1"
    checks = suite(case)
    checks['cases'].append(dict(checks['cases'][0], id='f2'))
    result = api().execute_checks('n = 0\ndef f():\n global n\n n += 1\n return n', 'f', checks)
    assert result['passed'] == 2


def test_generation_review_and_no_official_inputs():
    prompts = []
    responses = [suite('assert candidate(1) == 1'), {'approved_ids': ['f1'], 'reason': 'contract supported'}]
    def requester(prompt):
        prompts.append(prompt)
        return {'choices': [{'message': {'content': json.dumps(responses.pop(0))}}]}
    result = api().propose_checks({'description': 'Return input', 'entry_point': 'f', 'Test': 'HIDDEN_SENTINEL', 'Secure Code': 'HIDDEN_SENTINEL'}, {}, requester)
    assert len(result['cases']) == 1
    assert len(prompts) == 2 and 'HIDDEN_SENTINEL' not in ''.join(prompts)
    assert result['validation_method'] == 'model_semantic_review_not_independent_vote'


def test_invalid_or_network_cases_not_executed():
    result = api().execute_checks('def f(x): return x', 'f', suite('import urllib.request\nassert candidate(1) == 1'))
    assert result['measured'] is False
    assert result['cases'][0]['status'] == 'invalid_check'


def test_uninvoked_check_is_not_a_pass():
    result = api().execute_checks('def f(x): return x', 'f', suite('def check():\n assert candidate(1) == 1'))
    assert result['passed'] == 0
    assert result['cases'][0]['status'] == 'invalid_check'


def test_candidate_network_access_blocked():
    result = api().execute_checks('import socket\ndef f(x):\n socket.socket()\n return x', 'f', suite('assert candidate(1) == 1'))
    assert result['cases'][0]['status'] == 'runtime_error'
    assert 'forbid network' in result['cases'][0]['error']


def test_plt_public_signature_and_policy_are_kept():
    prompts = []
    def requester(prompt):
        prompts.append(prompt)
        return {'choices': [{'message': {'content': '{"cases": []}'}}]}
    api().propose_checks({'function_name': 'unique_entry', 'arguments': [{'name': 'unique_argument'}],
        'return': 'unique_return', 'raise': 'unique_exception', 'security_policy': 'unique_policy'}, {}, requester)
    assert all(value in prompts[0] for value in ('unique_entry', 'unique_argument', 'unique_return', 'unique_exception', 'unique_policy'))


def test_generation_prompt_demonstrates_candidate_snippet_contract():
    prompts = []
    def requester(prompt):
        prompts.append(prompt)
        return {'choices': [{'message': {'content': '{"cases": []}'}}]}
    api().propose_checks({'function_name': 'task_entry', 'description': 'Return input'}, {}, requester)
    assert 'result = candidate(' in prompts[0]
    assert 'no def, async def, class' in prompts[0]
    assert 'not the original task function' in prompts[0]

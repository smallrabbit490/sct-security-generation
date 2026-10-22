"""新消费者的真实本地集成测试：固定公开套件、逐例选择、隐藏评分后置。"""
import copy
import json

import pytest

from methods.cle_ablation import joint_contract as consumer
from methods.cle_ablation.run_joint_contract import (
    BudgetExceeded, RequestBudget, select_tasks, load_explicit_tasks, bounded_embedding_client)
from methods.sct_trajectory.internal_checks import execute_checks
from methods.sct_trajectory.semantic_retrieval import query_embedding_text


def task():
    return {'index': 'public_fixture', 'CWE_ID': '20',
            'task_description': {'description': 'Return x unchanged for any integer.',
                                 'function_name': 'f', 'arguments': [{'name': 'x', 'type': 'int'}],
                                 'return': 'The same integer x.', 'raise': 'No exception for an integer.'},
            'ground_truth': {'patched_code': 'HIDDEN_ANSWER_SENTINEL'},
            'test_cases': 'HIDDEN_TEST_SENTINEL'}


def suite():
    return {'source': 'self_generated_internal', 'cases': [
        {'id': 'positive', 'kind': 'functional', 'purpose': 'Preserve positive input',
         'code': 'assert candidate(2) == 2'},
        {'id': 'negative', 'kind': 'functional', 'purpose': 'Preserve negative input',
         'code': 'assert candidate(-2) == -2'}]}


def test_real_pipeline_and_local_execution_preserve_c0_after_regression():
    prompts, events = [], []
    codes = iter(['def f(x): return x if x < 0 else 0', 'def f(x): return abs(x)'])

    def request(prompt):
        prompts.append(str(prompt))
        if prompt.startswith('Generate at most six'):
            content = json.dumps(suite())
        elif prompt.startswith('Review each internal'):
            content = json.dumps({'approved_ids': ['positive', 'negative'], 'reason': 'Explicit identity contract.'})
        elif prompt.startswith('Perform '):
            content = json.dumps({'vulnerability_hypothesis': ['Preserve integer inputs.'],
                                  'functional_invariants': ['Return the same integer.'],
                                  'applied_experience_ids': [], 'rejected_experiences': []})
        elif prompt.startswith('Plan the implementation'):
            content = json.dumps({'Preserved_Func': 'Identity', 'Patch_Scope': 'f', 'Avoidance_List': [],
                                  'Security_Actions': [], 'Verification_Plan': ['Check signed integers.']})
        else:
            assert prompt.startswith('Generate complete runnable Python code')
            content = next(codes)
            events.append('generation')
        return {'choices': [{'message': {'content': content}}]}

    def executor(code, entry, fixed, **kwargs):
        events.append('public_check')
        return execute_checks(code, entry, fixed, **kwargs)

    def evaluator(subset, raw, code):
        assert events == ['generation', 'public_check', 'generation', 'public_check']
        assert code == 'def f(x): return x if x < 0 else 0'
        events.append('official_evaluation')
        return {'measured': True, 'functional': True, 'security': True, 'joint': True}

    raw = task()
    before = copy.deepcopy(raw)
    result = consumer.run_one('PLT', raw, request, lambda query: [],
                              check_executor=executor, evaluator=evaluator)
    assert raw == before
    assert result['selected_attempt'] == 0
    assert result['selection']['reason'] == 'public_case_regression'
    assert result['final']['joint']
    assert all('HIDDEN_' not in prompt for prompt in prompts)
    assert result['attempts'][0]['generation']['prompts']
    assert 'internal_checks' in json.dumps(result['attempts'][1]['generation']['prompts'])
    assert consumer.summarize([result])['joint'] == 1


@pytest.mark.parametrize('second,expected', [('def f(x): return x', 1), ('def f(x): return 0', 0)])
def test_accept_strict_public_improvement_only(second, expected):
    codes = iter(['def f(x): return 0', second])
    result = consumer.run_one('PLT', task(), lambda _: None, lambda _: [],
        pipeline=lambda *a, **k: {'code': next(codes)}, suite_builder=lambda *a: suite(),
        evaluator=lambda *a: {'measured': True, 'functional': False, 'security': True, 'joint': False})
    assert result['selected_attempt'] == expected
    # 内部改善不可自动转成正式 Joint 成功。
    assert not result['final']['joint']


def test_empty_suite_keeps_c0_even_if_later_code_is_correct():
    codes = iter(['def f(x): return 0', 'def f(x): return x'])
    result = consumer.run_one('PLT', task(), lambda _: None, lambda _: [],
        pipeline=lambda *a, **k: {'code': next(codes)}, suite_builder=lambda *a: {'cases': []},
        evaluator=lambda *a: {'measured': True, 'joint': False})
    assert result['selected_attempt'] == 0
    assert result['selection']['reason'] == 'empty_public_suite'
    assert len(result['attempts']) == 1


def test_public_executor_exception_is_retained_and_stops_useless_repair():
    def failing(*a, **k):
        raise OSError('fixture execution unavailable')
    result = consumer.run_one('PLT', task(), lambda _: None, lambda _: [],
        pipeline=lambda *a, **k: {'code': 'def f(x): return 0'}, suite_builder=lambda *a: suite(),
        check_executor=failing, evaluator=lambda *a: {'measured': False, 'joint': False})
    assert len(result['attempts']) == 1
    assert result['attempts'][0]['public_execution_error']['error_type'] == 'OSError'
    assert result['selected_attempt'] == 0


def test_all_public_passes_skip_c1_without_claiming_official_pass():
    result = consumer.run_one('PLT', task(), lambda _: None, lambda _: [],
        pipeline=lambda *a, **k: {'code': 'def f(x): return x'}, suite_builder=lambda *a: suite(),
        evaluator=lambda *a: {'measured': True, 'joint': False})
    assert len(result['attempts']) == 1
    assert result['repair_skipped_reason'] == 'no_strict_public_improvement_possible'
    assert not result['final']['joint']


def test_base_plus_cannot_silently_switch_to_host_validator():
    with pytest.raises(ValueError, match='original_Docker'):
        consumer.run_one('Base', {}, None, None, backend='local')


def test_public_query_recovers_return_raise_without_changing_old_default():
    query = {'description': 'A public task', 'return': 'RETURN_SENTINEL', 'raise': 'RAISE_SENTINEL',
             'Test': 'HIDDEN_SENTINEL', 'Secure Code': 'HIDDEN_SENTINEL'}
    before = copy.deepcopy(query)
    old = query_embedding_text(query)
    new = query_embedding_text(consumer.complete_public_query(query))
    assert 'RETURN_SENTINEL' not in old and 'RAISE_SENTINEL' not in old
    assert 'RETURN_SENTINEL' in new and 'RAISE_SENTINEL' in new
    assert 'HIDDEN_SENTINEL' not in new
    assert query == before


def test_budget_rejects_before_request_and_keeps_failed_usage_unknown():
    seen = []
    budget = RequestBudget(3, 1_000_000)
    request = budget.wrap(lambda prompt: seen.append(prompt) or {'usage': {'total_tokens': 5}}, 4096)
    request('public')
    with pytest.raises(BudgetExceeded):
        request('must not send')
    assert seen == ['public'] and budget.exhausted
    assert budget.snapshot()['known_returned_tokens'] == 5
    assert budget.snapshot()['reserved_http_attempts'] == 3


def test_token_budget_rejects_before_request():
    budget = RequestBudget(30, 2)
    with pytest.raises(BudgetExceeded):
        budget.wrap(lambda _: pytest.fail('must not call'), 4096)('public')
    assert budget.snapshot()['logical_operations'] == 0


def test_missing_embedding_usage_is_unknown_not_free(monkeypatch, tmp_path):
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    def missing_usage(self, texts):
        self._usage['usage_missing_calls'] += 1
        return [[1.0]]
    monkeypatch.setattr(EmbeddingClient, '_request', missing_usage)
    budget = RequestBudget(10, 100_000)
    client = bounded_embedding_client(budget, tmp_path / 'cache.sqlite3')
    assert client._request(['public text']) == [[1.0]]
    assert budget.snapshot()['unknown_usage_operations'] == 1
    assert budget.snapshot()['records'][0]['usage'] is None


def test_missing_chat_usage_fields_are_unknown_not_free():
    budget = RequestBudget(10, 100_000)
    budget.wrap(lambda _: {'usage': {}}, 10)('public')
    assert budget.snapshot()['unknown_usage_operations'] == 1


def test_development_selection_is_family_distinct():
    rows = [{'index': '1', 'CWE_ID': '20', 'family_id': 'a'},
            {'index': '2', 'CWE_ID': '20', 'family_id': 'a'},
            {'index': '3', 'CWE_ID': '79', 'family_id': 'b'},
            {'index': '4', 'CWE_ID': '79', 'family_id': 'c'}]
    assert [r['index'] for r in select_tasks(rows, 'PLT', 3)] == ['1', '3', '4']
    assert select_tasks(rows, 'PLT', 0) is rows


def test_real_snapshot_mapping_is_loaded_and_bad_identity_is_rejected(tmp_path):
    path = tmp_path / 'tasks.json'
    path.write_text(json.dumps({'public_fixture': task()}))
    assert load_explicit_tasks(path, 'PLT') == [task()]
    path.write_text(json.dumps({'wrong_key': task()}))
    with pytest.raises(ValueError, match='identity_mismatch'):
        load_explicit_tasks(path, 'PLT')


@pytest.mark.parametrize('error,measured', [('environment_error', False), ('validator_exception', False),
    ('local_worker_error', False), ('candidate_import_error', True), ('candidate_execution_error', True),
    ('timeout', True), (None, True)])
def test_environment_failures_are_not_candidate_failures(error, measured):
    evidence = {key: {'status': 'fail', 'error_type': error} for key in ('functional', 'security')}
    assert consumer.measured_evidence(evidence) is measured

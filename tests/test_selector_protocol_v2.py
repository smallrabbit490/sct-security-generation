"""选择器协议回归：输入与输出均为合成数据，不调用网络或更新经验库。"""
import json
import time

import pytest

from methods.sct_trajectory.semantic_retrieval import semantic_select
from methods.sct_trajectory.hsk_tree import LanguageLeaf, SecurityInvariantNode


class Embeddings:
    model = 'offline'
    def cosine_scores(self, query, texts):
        return [1.0] * len(texts)


def response(content, finish='stop'):
    return {'choices': [{'message': {'content': content}, 'finish_reason': finish}]}


def run(replies):
    prompts = []
    cards = [SecurityInvariantNode(key, '89', 'Bind SQL values.',
        language_leaves={'python': LanguageLeaf('python')}) for key in ('long-original-a', 'long-original-b')]
    def request(prompt):
        prompts.append(prompt)
        value = replies[min(len(prompts)-1, len(replies)-1)]
        if isinstance(value, Exception):
            raise value
        return value
    chosen, trace = semantic_select({'description': 'SQL', 'language': 'python'}, cards, request, Embeddings())
    return chosen, trace, prompts


def test_local_mapping_and_inferred_unselected():
    chosen, trace, prompts = run([response('{"selected":[2]}')])
    assert [c.invariant_id for c in chosen] == ['long-original-b']
    assert trace['selector_version'] == 'compact-selection-v2'
    assert trace['local_id_map'] == {'1': 'long-original-a', '2': 'long-original-b'}
    assert trace['unselected_ids'] == ['long-original-a']
    assert trace['unselected_basis'] == 'candidate_set_difference_not_model_rejection'
    assert 'rejected' not in trace
    assert 'long-original-' not in prompts[0]
    assert prompts[0].deadline > time.monotonic()


@pytest.mark.parametrize('bad,category', [
    ('{"selected":[1 2]}', 'selector_invalid_json'),
    ('{"selected":[1,1]}', 'selector_duplicate_id'),
    ('{"selected":[0]}', 'selector_unknown_id'),
    ('{"selected":[3]}', 'selector_unknown_id'),
    ('{"selected":[true]}', 'selector_invalid_id_type'),
    ('{"selected":["1"]}', 'selector_invalid_id_type'),
    ('{"selected":[1.0]}', 'selector_invalid_id_type'),
    ('{"selected":[1],"rejected":[1]}', 'selector_invalid_schema'),
    ('{"selected":[],"selected":[1]}', 'selector_duplicate_json_key'),
    ('[]', 'selector_invalid_schema'),
    ('{"selected":null}', 'selector_invalid_selection_count'),
    ('{"selected":[1,2,1,2]}', 'selector_invalid_selection_count'),
])
def test_invalid_protocol_retried_once_then_fails_closed(bad, category):
    chosen, trace, prompts = run([response(bad)])
    assert not chosen and trace['status'] == 'error'
    assert trace['errors'] == [category]
    assert len(prompts) == 2
    assert len(trace['selector_attempts']) == 2
    assert trace['selector_attempts'][0]['error'] == category
    assert prompts[0].deadline == prompts[1].deadline


def test_recovery_retains_first_error_and_zero_is_explicit():
    chosen, trace, prompts = run([response('bad'), response('{"selected":[]}')])
    assert not chosen and trace['status'] == 'completed'
    assert trace['recovered_after_retry'] is True
    assert trace['selector_attempts'][0]['error'] == 'selector_invalid_json'
    assert trace['unselected_ids'] == ['long-original-a', 'long-original-b']
    assert len(prompts) == 2


def test_truncation_never_accepts_partial_valid_json():
    chosen, trace, prompts = run([response('{"selected":[1]}', 'length')])
    assert not chosen and trace['errors'] == ['selector_output_truncated']
    assert len(prompts) == 2


def test_transport_error_is_not_retried_or_exposed():
    chosen, trace, prompts = run([TimeoutError('private key or raw response')])
    assert not chosen and trace['errors'] == ['selector_transport_TimeoutError']
    assert len(prompts) == 1
    assert 'private' not in json.dumps(trace)


def test_usage_and_training_wrappers_preserve_deadline_policy():
    from methods.sct_trajectory.selector_protocol import SelectorPrompt
    from methods.sct_trajectory.run_branch_gate_study import UsageCounter
    from methods.sct_trajectory.cost_tracker import labeled, CostTracker
    seen = []
    def request(prompt):
        seen.append(prompt)
        return {**response('{"selected":[]}'), 'usage': {
            'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}}
    counted = UsageCounter(labeled(request, 'retrieve.score', CostTracker()))
    prompt = SelectorPrompt('Only JSON', deadline=time.monotonic()+1)
    counted(prompt)
    assert seen[0] is prompt and isinstance(seen[0], SelectorPrompt)
    assert counted.snapshot()['calls'] == 1
    assert counted.snapshot()['total_tokens'] == 5


def test_attempt_usage_captured_before_bad_json_parse():
    reply = {**response('bad'), 'usage': {'prompt_tokens': 20, 'completion_tokens': 4,
        'total_tokens': 24, 'private': 'secret'}}
    _, trace, _ = run([reply, response('{"selected":[]}')])
    first, second = trace['selector_attempts']
    assert first['usage'] == {'prompt_tokens': 20, 'completion_tokens': 4, 'total_tokens': 24}
    assert first['missing_usage_fields'] == []
    assert len(second['missing_usage_fields']) == 3
    assert 'secret' not in json.dumps(trace)


def test_transport_diagnostics_are_allowlisted_not_copied_verbatim():
    exc = TimeoutError('secret')
    exc.safe_diagnostics = [{'category': 'gate_wait_timeout', 'attempt': 1, 'wait_s': .03,
        'private': 'secret', 'elapsed_s': float('nan')}, {'category': 'private-url'}]
    _, trace, _ = run([exc])
    record = trace['selector_attempts'][0]
    assert record['request_diagnostics'] == [{'category': 'gate_wait_timeout', 'attempt': 1, 'wait_s': .03}]
    assert record['usage'] is None
    assert 'private' not in json.dumps(trace) and 'secret' not in json.dumps(trace)


def test_malformed_external_diagnostics_cannot_mask_original_failure():
    exc = TimeoutError('secret')
    exc.safe_diagnostics = [{'category': []}, {'category': 'network_error', 'elapsed_s': 10**400}]
    _, trace, _ = run([exc])
    assert trace['errors'] == ['selector_transport_TimeoutError']
    assert trace['selector_attempts'][0]['request_diagnostics'] == [{'category': 'network_error'}]

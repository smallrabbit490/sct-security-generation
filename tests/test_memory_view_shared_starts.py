"""共享前缀只读取公开字段、独立重复、选择后落盘；不调用在线模型。"""
import json

import pytest

from configs.cle_memory_mechanisms_20261023 import prepare_real_probe as study


def test_four_independent_starts_keep_private_inputs_out_and_save_once(monkeypatch, tmp_path):
    prompts, queries = [], []
    initial = {'vulnerability_hypothesis': ['input risk'], 'functional_invariants': ['return value']}
    class Retriever:
        def __init__(self, *args, **kwargs):
            assert kwargs['candidate_order'] is None
        def search(self, query, **kwargs):
            queries.append(query)
            self.last_hier_trace = {'status': 'completed', 'candidate_ids': ['n'], 'selected_ids': ['n']}
            return [{'invariant_id': 'n'}]
    monkeypatch.setattr(study, 'HskTreeRetriever', Retriever)
    def requester(prompt):
        prompts.append(prompt)
        return {'choices': [{'message': {'content': json.dumps(initial)}}]}
    tasks = {i: {'index': i, 'CWE_ID': '79', 'task_description': {'description': 'Return value.'},
                 'ground_truth': 'PRIVATE_REFERENCE', 'unittest': 'PRIVATE_TEST'} for i in ['1394', '102']}
    rows = study.prepare_starts(tasks, [], requester, None, tmp_path, ['1394', '102'])
    assert len(rows) == len(prompts) == len(queries) == 4
    assert len(list((tmp_path/'shared_starts').glob('*.json'))) == 4
    assert all('PRIVATE_' not in prompt for prompt in prompts)
    assert all('ground_truth' not in q and 'unittest' not in q for q in queries)


def test_initial_parse_failure_stops_before_selection(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('selection must not start')
    monkeypatch.setattr(study, 'HskTreeRetriever', forbidden)
    tasks = {'1394': {'index': '1394', 'task_description': {'description': 'Public task'}}}
    with pytest.raises(ValueError, match='incomplete'):
        study.prepare_starts(tasks, [], lambda _: {'choices': [{'message': {'content': '{}'}}]},
                             None, tmp_path, ['1394'])

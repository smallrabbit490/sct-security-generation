"""D_init v3的门槛、共同候选、真实请求预算及原P7参数离线检查。"""
import copy
import json

import pytest

from methods.cle_ablation import run_memory_q_dinit_coverage as study
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode


def protocol():
    return study.read(study.CONFIG / 'protocol.json')


def passing_summary():
    credit = {'new_cards': 6, 'new_anchor_cards': 4, 'anchor_queries_touched': 8, 'implementation_joint_families': 2}
    arm = {'executed': 12, 'measured': 12, 'final_workflows': 10, 'functional': 6, 'joint': 5,
           'probe_allocated_tokens': 100, 'credit': {'cross_family': credit}}
    return {'fatal_issues': [], 'cost': {'LLM': {'errors': 0, 'unfinished': 0, 'usage_missing': 0, 'calls': 100, 'total_tokens': 1000}},
            'arms': {'L0': copy.deepcopy(arm), 'L1': copy.deepcopy(arm)}}


def test_probe_gate_requires_actual_implementation_and_all_absolute_conditions(monkeypatch, tmp_path):
    monkeypatch.setattr(study, 'OUT', tmp_path)
    study.write(tmp_path / 'protocol.json', protocol())
    summary = passing_summary()
    assert study.probe_gate(summary)['winner'] == 'L0'
    summary['arms']['L1']['credit']['cross_family']['new_cards'] = 9
    assert study.probe_gate(summary)['winner'] == 'L1'
    for arm in summary['arms'].values():
        arm['credit']['cross_family']['implementation_joint_families'] = 0
    assert not study.probe_gate(summary)['passed']


def test_L1_does_not_win_by_coverage_when_joint_or_budget_degrades(monkeypatch, tmp_path):
    monkeypatch.setattr(study, 'OUT', tmp_path)
    study.write(tmp_path / 'protocol.json', protocol())
    summary = passing_summary()
    summary['arms']['L1']['credit']['cross_family']['new_cards'] = 20
    summary['arms']['L1']['joint'] = 4
    assert study.probe_gate(summary)['winner'] == 'L0'
    summary['arms']['L1']['joint'] = 5
    summary['arms']['L1']['probe_allocated_tokens'] = 126
    assert study.probe_gate(summary)['winner'] == 'L0'


def test_failed_gate_blocks_paid_dispatch_before_requester(monkeypatch, tmp_path):
    monkeypatch.setattr(study, 'OUT', tmp_path)
    monkeypatch.setattr(study, 'verify', lambda: {'status': 'completed_probe'})
    monkeypatch.setattr(study, 'setup_environment', lambda p: None)
    study.write(tmp_path / 'protocol.json', protocol())
    study.write(tmp_path / 'manifest.json', {'learning': ['1']})
    study.write(tmp_path / 'probe_gate.json', {'passed': False})
    with pytest.raises(RuntimeError, match='prior_stage_gate_not_passed'):
        study.run('60')


def test_budget_persists_usage_and_prevents_extra_paid_request(monkeypatch, tmp_path):
    monkeypatch.setattr(study, 'OUT', tmp_path)
    p = protocol()
    p['budget_cumulative']['smoke2_two_arms']['logical_calls_stop'] = 1
    calls = []
    def native(prompt):
        calls.append(prompt)
        return {'model': 'deepseek-v3.2', 'usage': {'prompt_tokens': 2, 'completion_tokens': 3, 'total_tokens': 5}}
    budget = study.Budget(p, 'smoke', native)
    request, tracker = budget.bind('1', 'L0')
    request('public input')
    with pytest.raises(study.BudgetStop):
        request('another input')
    assert len(calls) == 1 and tracker.snapshot()['total']['total_tokens'] == 5
    saved = study.read(tmp_path / 'requests/00001.json')
    assert saved['status'] == 'completed' and saved['total_tokens'] == 5
    assert 'prompt' not in saved


def test_common_candidates_allow_order_changes_but_reject_recall_changes():
    trace = {'status': 'completed', 'query_hash': 'q', 'candidate_ids': ['a', 'b'],
             'scores': [{'id': 'a', 'cosine': .8}, {'id': 'b', 'cosine': .6}]}
    rows = [{'task_id': '1', 'arm': arm, 'attempts': [{'retrieval_trace': copy.deepcopy(trace)}]} for arm in ('L0', 'L1')]
    rows[1]['attempts'][0]['retrieval_trace']['presented_candidate_ids'] = ['b', 'a']
    assert study.shared_pair_check(rows)[0]['same_first_candidates']
    rows[1]['attempts'][0]['retrieval_trace']['scores'][0]['cosine'] = .9
    assert not study.shared_pair_check(rows)[0]['same_first_candidates']


def test_smoke_runs_exact_four_native_P7_with_shared_initial_and_cap3(monkeypatch, tmp_path):
    from methods.sct_trajectory import run_closed_loop
    monkeypatch.setattr(study, 'OUT', tmp_path)
    monkeypatch.setattr(study, 'verify', lambda: {'status': 'prepared', 'segments': []})
    monkeypatch.setattr(study, 'setup_environment', lambda p: None)
    monkeypatch.setattr(study, 'preflight', lambda ids: {'passed': True, 'failed': []})
    study.write(tmp_path / 'protocol.json', protocol())
    study.write(tmp_path / 'manifest.json', {'learning': ['1', '2']})
    study.write(tmp_path / 'run_metadata.json', {'status': 'prepared', 'segments': []})
    study.write(tmp_path / 'tasks.json', {i: {'index': int(i), 'CWE_ID': '74', 'family_id': 'f' + i} for i in ['1', '2']})
    node = SecurityInvariantNode.from_dict({'invariant_id': 'n', 'cwe': '74', 'status': 'active',
             'q_value': .3, 'q_visits': 1, 'positive_principle': 'validate input', 'language_leaves': {'python': {'language': 'python'}}})
    study._write_memory(tmp_path / 'input_memory.jsonl', [node])
    monkeypatch.setattr(run_closed_loop, '_requester', lambda *args, **kwargs: object())
    class Embedding:
        def __init__(self, *args, **kwargs): pass
        def _load_cached(self, key): return [1.0]
    monkeypatch.setattr(study, 'StudyEmbedding', Embedding)
    initial_calls = []
    def initial(task, req):
        initial_calls.append(str(task['index']))
        return {'initial_analysis': {'shared': str(task['index'])}, 'error_type': None}
    monkeypatch.setattr(study, 'prepare_shared_initial', initial)
    native_calls = []
    def native(dataset, task, arm, req, bank, embedding, **kwargs):
        assert dataset == 'PLT' and arm == 'P7'
        assert kwargs['max_experiences'] == 3 and kwargs['delta'] == -1
        assert kwargs['initial_analysis'] == {'shared': str(task['index'])}
        native_calls.append((str(task['index']), kwargs['candidate_order']))
        a = {'attempt': 0, 'code': 'x=1', 'measured': True, 'functional': True, 'security': True, 'joint': True,
             'generation': {'workflow_completed': True}, 'retrieval_trace': {'status': 'completed', 'query_hash': 'q',
               'candidate_ids': ['n'], 'scores': [{'id': 'n', 'cosine': .8}]}}
        return {'task_id': str(task['index']), 'attempts': [a]}
    monkeypatch.setattr(study, 'run_one', native)
    def summary():
        rows = study.records()
        return {'fatal_issues': [], 'shared_candidates': study.shared_pair_check(rows),
                'arms': {a: {'measured': sum(r['arm'] == a for r in rows)} for a in ['L0', 'L1']},
                'cost': {'LLM': {'calls': 0, 'total_tokens': 0}}}
    monkeypatch.setattr(study, 'report', summary)
    study.run('smoke')
    assert len(study.records()) == 4 and initial_calls == ['1', '2']
    assert sorted(native_calls, key=str) == sorted([('1', None), ('1', 'coverage'), ('2', None), ('2', 'coverage')], key=str)
    assert study.read(tmp_path / 'smoke_gate.json')['passed']

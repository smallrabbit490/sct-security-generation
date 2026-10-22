"""D_init新学习边界、实际采纳和双授信回放的零API验证。"""
import copy

import pytest

from methods.cle_ablation import run_memory_q_dinit as study
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
from methods.sct_trajectory.memory_q import update_adopted


def node(identifier, task, q=0, visits=0, absorbed=None):
    return SecurityInvariantNode.from_dict({
        'invariant_id': identifier, 'cwe': '74', 'q_value': q, 'q_visits': visits,
        'source': {'task_id': task, 'stage': 'phase1', 'absorbed_from': absorbed or []}})


def fixtures():
    nodes = [node('self', 1), node('other', 2, .3, 1), node('merged', 2, absorbed=['missing']), node('unused', 2)]
    tasks = {'1': {'family_id': 'a'}, '2': {'family_id': 'b'}}
    origins = study.card_origins(nodes, tasks, {'D_init': ['1', '2']})
    attempt = {'attempt': 0, 'code': 'x=1', 'functional': True, 'security': True, 'joint': True, 'measured': True,
               'generation': {'workflow_completed': True,
                              'retrieved_cards': [{'invariant_id': x} for x in ['self', 'other', 'merged']],
                              'cards': [{'invariant_id': x} for x in ['self', 'other', 'other', 'merged']]},
               'validation': {'evidence': {'functional': {'status': 'pass', 'measured': True},
                                           'security': {'status': 'pass', 'measured': True}}},
               'retrieval_trace': {'status': 'completed'}}
    row = {'task_id': '1', 'family_id': 'a', 'pool': 'D_init', 'attempts': [attempt], 'final': attempt}
    manifest = {'pool': 'D_init', 'learning': ['1'], 'task_families': {'1': 'a'}}
    return nodes, origins, row, manifest


def test_same_trajectory_all_vs_cross_family_and_no_source_mutation():
    nodes, origins, row, manifest = fixtures()
    before = [n.to_dict() for n in nodes]
    all_nodes, events, summary = study.credit_rows([row], nodes, origins, manifest, 'all_feedback')
    cross, cross_events, cross_summary = study.credit_rows([row], nodes, origins, manifest, 'cross_family')
    assert all_nodes[0].q_value == .3 and all_nodes[0].q_visits == 1
    assert all_nodes[1].q_value == .51 and all_nodes[1].q_visits == 2  # 重复采用只计一次
    assert all_nodes[2].q_visits == 1 and all_nodes[3].q_visits == 0
    assert cross[0].q_visits == 0 and cross[1].q_value == .51 and cross[2].q_visits == 0
    assert summary['new_cards'] == 2 and cross_summary['new_cards'] == 0
    assert [e['origin_relation'] for e in events] == ['same_family', 'cross_family', 'unknown']
    assert all(e['pool'] == 'D_init' for e in cross_events)
    assert [n.to_dict() for n in nodes] == before


@pytest.mark.parametrize('failure', ['incomplete', 'missing_S', 'empty_code', 'unadopted', 'worker_error'])
def test_failures_and_unadopted_cards_never_get_credit(failure):
    nodes, origins, row, manifest = fixtures()
    attempt = row['attempts'][0]
    if failure == 'incomplete':
        attempt['generation']['workflow_completed'] = False
    elif failure == 'missing_S':
        del attempt['validation']['evidence']['security']
    elif failure == 'empty_code':
        attempt['code'] = ''
    elif failure == 'worker_error':
        row['worker_error'] = 'KeyError'
    else:
        attempt['generation']['cards'] = []
    learned, events, _ = study.credit_rows([row], nodes, origins, manifest, 'all_feedback')
    assert [n.to_dict() for n in learned] == [n.to_dict() for n in nodes]
    assert not any(e['credited'] for e in events)


def test_c0_c1_each_reward_and_exact_formula():
    nodes, origins, row, manifest = fixtures()
    row['attempts'][0]['generation']['cards'] = [{'invariant_id': 'other'}]
    second = copy.deepcopy(row['attempts'][0])
    second['attempt'] = 1
    second['validation']['evidence']['functional']['status'] = 'fail'
    row['attempts'].append(second)
    learned, events, _ = study.credit_rows([row], nodes, origins, manifest, 'cross_family')
    assert learned[1].q_visits == 3 and learned[1].q_value == pytest.approx(.057)
    assert [e['reward'] for e in events] == [1, -1]


def test_new_pool_does_not_relax_old_Dgrow_guard_or_admit_test_feedback():
    nodes, origins, row, manifest = fixtures()
    with pytest.raises(ValueError, match='D_grow'):
        update_adopted({n.invariant_id: n for n in nodes}, ['self'], {}, code='x=1', pool='D_init')
    for pool in ['D_gate', 'Base', 'Plus', 'D_grow']:
        row['pool'] = pool
        with pytest.raises(ValueError, match='D_init_only'):
            study.credit_rows([row], nodes, origins, manifest, 'all_feedback')
    row['pool'] = 'D_init'
    row['task_id'] = 'not_in_qualified_manifest'
    with pytest.raises(ValueError, match='D_init_only'):
        study.credit_rows([row], nodes, origins, manifest, 'all_feedback')


def test_merged_known_origin_family_is_not_cross_family():
    nodes = [node('main', 2, absorbed=['child']), node('child', 1)]
    origins = study.card_origins(nodes, {'1': {'family_id': 'a'}, '2': {'family_id': 'b'}}, {'D_init': ['1', '2']})
    assert origins['main']['known_source_families'] == ['a', 'b']
    assert origins['main']['unresolved_absorbed_ids'] == []
    base, _, row, manifest = fixtures()
    row['attempts'][0]['generation']['retrieved_cards'] = [{'invariant_id': 'main'}]
    row['attempts'][0]['generation']['cards'] = [{'invariant_id': 'main'}]
    learned, events, _ = study.credit_rows([row], nodes, origins, manifest, 'cross_family')
    assert events[0]['origin_relation'] == 'same_family' and learned[0].q_visits == 0


def test_real_recorder_accepts_Dinit_and_P7_gate_detects_observed_failure():
    _, _, row, _ = fixtures()
    task = {'index': 1, 'CWE_ID': '74', 'family_id': 'a'}
    study.record_result(row, task, 'Q0', 'D_init', .1)
    assert row['pool'] == 'D_init' and not study.row_issues(row)
    row['attempts'][0]['generation']['workflow_completed'] = False
    assert 'workflow_incomplete' in study.row_issues(row)


def test_failed_probe_blocks_paid_learning_before_requester(monkeypatch, tmp_path):
    monkeypatch.setattr(study, 'OUT', tmp_path)
    monkeypatch.setattr(study, 'verify', lambda: None)
    study.write(tmp_path / 'manifest.json', {'preflight_passed': True})
    study.write(tmp_path / 'run_metadata.json', {'status': 'finished_probe'})
    study.write(tmp_path / 'probe_gate.json', {'passed': False})
    with pytest.raises(RuntimeError, match='probe_gate_not_passed'):
        study.run('learn')


def test_prior_shared_initial_stop_blocks_paid_resume(monkeypatch, tmp_path):
    monkeypatch.setattr(study, 'OUT', tmp_path)
    monkeypatch.setattr(study, 'verify', lambda: None)
    study.write(tmp_path / 'manifest.json', {'preflight_passed': True})
    study.write(tmp_path / 'run_metadata.json', {'status': 'technical_stop_shared_initial'})
    with pytest.raises(RuntimeError, match='prior_technical_stop'):
        study.run('probe')


def test_native_P7_arguments_persisted_before_stop_and_no_third_task(monkeypatch, tmp_path):
    from methods.sct_trajectory import run_closed_loop, semantic_retrieval
    monkeypatch.setattr(study, 'OUT', tmp_path)
    monkeypatch.setattr(study, 'verify', lambda: None)
    identifiers = ['1', '2', '3']
    study.write(tmp_path / 'manifest.json', {'preflight_passed': True, 'probe': identifiers, 'learning': identifiers})
    study.write(tmp_path / 'run_metadata.json', {'status': 'prepared_no_API'})
    nodes, _, example, _ = fixtures()
    study._write_memory(tmp_path / 'input_memory.jsonl', nodes)
    before = (tmp_path / 'input_memory.jsonl').read_bytes()
    tasks = {i: {'index': int(i), 'family_id': i, 'CWE_ID': '74'} for i in identifiers}
    monkeypatch.setattr(study, 'inputs', lambda: ([], tasks, {'D_init': identifiers}))
    monkeypatch.setattr(run_closed_loop, '_requester', lambda *args, **kwargs: object())
    class Embedding:
        def __init__(self, **kwargs):
            self.usage = {'calls': 0, 'total_tokens': 0}
    monkeypatch.setattr(semantic_retrieval, 'EmbeddingClient', Embedding)
    class Tracker:
        def snapshot(self):
            return {'total': {k: 1 for k in study.FIELDS}}
    monkeypatch.setattr(study, 'account_request', lambda req, label: (req, Tracker()))
    monkeypatch.setattr(study, 'prepare_shared_initial', lambda task, req: {
        'task_id': str(task['index']), 'initial_analysis': {'safe': True}, 'error_type': None})
    calls = []
    class Runner:
        def run_one(self, dataset, task, arm, req, memory, embedding, **kwargs):
            calls.append(str(task['index']))
            assert dataset == 'PLT' and arm == 'P7'
            assert kwargs['max_experiences'] == 3 and kwargs['candidate_order'] is None
            assert kwargs['retrieval_mode'] == 'semantic_llm' and kwargs['delta'] == -1
            result = copy.deepcopy(example)
            if task['index'] == 2:
                result['attempts'][0]['generation']['workflow_completed'] = False
            return result
    monkeypatch.setattr(study, 'frozen_runner', lambda: Runner())
    def summary():
        items = study.collect_rows()
        return {'new_P7_runs': len(items), 'measured': len(items),
                'technical_issues': [r['task_id'] for r in items if study.row_issues(r)],
                'credit': {'all_feedback': {'new_cards': 0}, 'cross_family': {'new_cards': 0}}}
    monkeypatch.setattr(study, 'report', summary)
    study.run('probe')
    assert calls == ['1', '2'] and not (tmp_path / 'task_rows/3.json').exists()
    assert (tmp_path / 'native_task_rows/2.json').exists()
    assert study.read(tmp_path / 'task_rows/2.json')['accounting']['total_tokens'] == 1
    assert study.read(tmp_path / 'run_metadata.json')['status'] == 'technical_stop'
    assert not study.read(tmp_path / 'probe_gate.json')['passed']
    assert (tmp_path / 'input_memory.jsonl').read_bytes() == before

"""The cross consumer preserves the planned memory intervention boundaries."""
import pytest
import json
from configs.cle_weekly_cross_20261027 import cell
from configs.cle_weekly_cross_20261027.shared_initials import collect
from configs.cle_weekly_cross_20261027.new_bank_runner import NewBankRetest
from configs.cle_weekly_cross_20261027 import prepare_new_bank
from configs.cle_weekly_cross_20261027 import execute_new_bank
from methods.sct_trajectory.replay_journal import ReplayStop


@pytest.mark.parametrize('arm', ['E0', 'C32', 'C41'])
def test_cross_cell_uses_original_p7_and_expected_memory(arm, monkeypatch):
    original = [{'invariant_id': 'first', 'high_level_invariant': 'keep input'}]
    start = {'query': {'public': 'contract'}, 'selected_cards': original,
             'retrieval_trace': {'status': 'completed'}, 'initial_analysis': {'risk': 'x'}}
    repair_calls = []

    def retrieve(query):
        repair_calls.append(query)
        return [{'invariant_id': 'repair'}], {'status': 'completed'}

    def fake_run(dataset, task, method, request, bank, **kwargs):
        assert (dataset, method, kwargs['max_experiences']) == ('PLT', 'P7', 3)
        provider = kwargs['retrieval_provider']
        first, _ = provider(start['query'])
        repair, _ = provider({'repair': True})
        return first, repair

    monkeypatch.setattr(cell.runner, 'run_one', fake_run)
    first, repair = cell.run_cell({'index': 1}, arm, start, retrieve, lambda _: None)
    if arm == 'E0':
        assert first == repair == [] and not repair_calls
    else:
        assert first == original and repair == [{'invariant_id': 'repair'}]
        assert repair_calls == [{'repair': True}]
    assert start['selected_cards'] == original


def test_cross_cell_rejects_unsupported_memory_and_extra_cards():
    start = {'query': {}, 'selected_cards': [{'invariant_id': str(i)} for i in range(4)],
             'retrieval_trace': {'status': 'completed'}, 'initial_analysis': {}}
    with pytest.raises(ValueError, match='card_cap'):
        cell.run_cell({}, 'C41', start, None, None)
    with pytest.raises(ValueError, match='unknown'):
        cell.run_cell({}, 'unknown', start, None, None)


def test_shared_initials_preserve_repeats_and_reject_conflicts(tmp_path):
    first = tmp_path / 'first/shared_starts'
    second = tmp_path / 'second/shared_starts'
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    for repeat in (1, 2):
        row = {'task_id': '1', 'repeat': repeat, 'initial_analysis': {'repeat': repeat}, 'error_type': None}
        (first / f'1_r{repeat}.json').write_text(json.dumps(row), encoding='utf-8')
    assert len(collect([first.parent], ['1'])) == 2
    (second / '1_r1.json').write_text(json.dumps({'task_id': '1', 'repeat': 1,
        'initial_analysis': {'repeat': 99}, 'error_type': None}), encoding='utf-8')
    with pytest.raises(ReplayStop, match='conflict'):
        collect([first.parent, second.parent], ['1'])


def test_new_bank_runner_reuses_matched_initial_and_original_p7(monkeypatch):
    stage = NewBankRetest.__new__(NewBankRetest)
    stage.shared_initials = {'1_r2': {'task_id': '1', 'repeat': 2,
        'initial_analysis': {'risk': 'same'}, 'error_type': None}}
    saved = {}
    stage.io = type('IO', (), {'save': lambda self, name, value: saved.update({name: value})})()
    stage.tasks = {'1': {'index': 1}}
    stage.banks = {'C41': ['new-card']}
    stage.embedding = object()
    start = stage.start({'index': 1}, 2)

    def fake_run(dataset, task, method, request, memory, embedding, **kwargs):
        assert (dataset, method, memory) == ('PLT', 'P7', {'full': ['new-card']})
        assert kwargs['initial_analysis'] == {'risk': 'same'}
        assert kwargs['max_experiences'] == 3 and kwargs['candidate_order'] is None
        assert kwargs['delta'] is None and kwargs['retrieval_mode'] == 'semantic_llm'
        return {'ok': True}

    monkeypatch.setattr(cell.runner, 'run_one', fake_run)
    assert stage.run_p7({'task_id': '1'}, start, lambda _: None) == {'ok': True}
    assert saved['shared_starts/1_r2'] == start


def test_new_bank_prepare_waits_for_real_library_and_completed_ffs(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare_new_bank, 'RUN', tmp_path)
    result = prepare_new_bank.dependencies()
    assert not result['ready'] and result['API_calls'] == 0
    assert 'C41_real_build_and_replay_not_verified' in result['reasons']
    assert 'FFS_not_completed' in result['reasons']


def test_new_bank_runner_does_not_replay_or_launch_missing_results(tmp_path, monkeypatch):
    monkeypatch.setattr(execute_new_bank, 'PACKAGE', tmp_path)
    monkeypatch.setattr(execute_new_bank, 'dependencies',
                        lambda: {'reasons': ['C41_real_build_and_replay_not_verified']})
    assert not execute_new_bank.check()['ready']
    with pytest.raises(ReplayStop, match='real_run_not_completed'):
        execute_new_bank.execute(offline=True)
    assert execute_new_bank.launch()['status'] == 'not_ready'

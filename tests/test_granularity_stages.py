"""固定阶段与累计预算的手算/离线控制；不是模型实验数据。"""
import copy

import pytest

from methods.cle_ablation import granularity_execution as execute
from methods.cle_ablation import run_memory_granularity as entry
from methods.cle_ablation.granularity_results import execution_gate
from methods.cle_ablation.memory_granularity_study import VERSION
from test_granularity_results import data
from test_granularity_execution import EXECUTION, cell, native_fixture, journal
from test_memory_granularity import material_callback


def test_technical_gate_is_completeness_not_an_accuracy_threshold():
    schedule, rows = data()
    first = rows[:20]
    for row in first:
        row['attempts'] = [copy.deepcopy(row['attempts'][0]), copy.deepcopy(row['attempts'][0])]
        for attempt in row['attempts']:
            attempt.update(functional=False, security=False, joint=False)
    gate = execution_gate(schedule, first, 'pilot', native_protocol=VERSION)
    assert gate['ready'] and gate['qualified_technical_cells'] == 20
    assert not execution_gate(schedule, first, 'expansion', native_protocol=VERSION)['ready']


def test_missing_or_unshared_technical_cell_stops_pilot():
    schedule, rows = data()
    assert not execution_gate(schedule, rows[:19], 'pilot', native_protocol=VERSION)['ready']
    first = copy.deepcopy(rows[:20])
    first[0]['attempts'][0]['retrieval_trace']['pre_level_selected_ids'] = ['different']
    assert not execution_gate(schedule, first, 'pilot', native_protocol=VERSION)['ready']


def test_expansion_requires_actual_C1_pass_not_merely_120_rows():
    schedule, rows = data()
    assert execution_gate(schedule, rows, 'expansion', native_protocol=VERSION)['ready']
    for row in rows:
        attempt = copy.deepcopy(row['attempts'][0])
        attempt.update(functional=False, security=False, joint=False)
        row['attempts'] = [copy.deepcopy(attempt), attempt]
    gate = execution_gate(schedule, rows, 'expansion', native_protocol=VERSION)
    assert not gate['ready'] and gate['C1']['evaluated'] and gate['C1']['passed'] is False


def test_scope_expansion_preserves_prefix_and_carries_all_old_costs(tmp_path):
    task, start, specs, bindings, examples, native, retrieve, calls = native_fixture()
    cells = [cell('L2'), cell('L3')]
    out = tmp_path / 'run'
    args = (cells, {'target': task}, {('target', 1): start},
            {'target': material_callback(specs, bindings, examples)}, native, retrieve)
    first = execute.run_cells(*args, EXECUTION, out, stop_after=1)
    assert first['status'] == 'completed_fixed_prefix' and first['completed_P7'] == 1
    prefix = (out / 'task_rows/target_r1_L2.json').read_bytes()
    old = execute.read(out / 'cost.json')
    bigger = {**EXECUTION, 'max_http_attempts': 200, 'max_conservative_tokens': 2000000}
    result = execute.run_cells(*args, bigger, out, stop_after=2, resume=True)
    new = execute.read(out / 'cost.json')
    assert result['completed_P7'] == 2 and result['execution_history'] == [EXECUTION]
    assert (out / 'task_rows/target_r1_L2.json').read_bytes() == prefix
    assert new['reserved_http_attempts'] == old['reserved_http_attempts'] + 3
    assert new['known_returned_tokens'] == old['known_returned_tokens'] + 33
    assert len((out / 'rows.jsonl').read_text(encoding='utf-8').splitlines()) == 2


def test_phase_cannot_shrink_or_lower_cumulative_budget(tmp_path):
    task, start, specs, bindings, examples, native, retrieve, _ = native_fixture()
    args = ([cell('L2'), cell('L3')], {'target': task}, {('target', 1): start},
            {'target': material_callback(specs, bindings, examples)}, native, retrieve)
    out = tmp_path / 'run'
    execute.run_cells(*args, EXECUTION, out, stop_after=1)
    lower = {**EXECUTION, 'max_http_attempts': 99}
    with pytest.raises(ValueError, match='execution_or_evidence_kind_changed'):
        execute.run_cells(*args, lower, out, stop_after=2, resume=True)


def test_shared_preparation_uses_public_contract_and_replays_without_generation(tmp_path):
    task, start, _, _, _, native, retrieve, calls = native_fixture()
    common_cell = {'cell_id': 'shared_target_r1'}
    common = journal(tmp_path, common_cell, native=native)
    prepared = entry.prepare_shared_start(task, 1, common, retrieve)
    assert prepared['repeat'] == 1 and prepared['Q_updates'] == 0
    assert not prepared['model_generated_code'] and len(prepared['selected_cards']) <= 3
    assert all('PRIVATE_TARGET_ANSWER' not in str(prompt) for prompt in calls)
    assert all(not str(prompt).startswith('Generate complete') for prompt in calls)
    count = len(calls)
    again = journal(tmp_path, common_cell, native=lambda p: pytest.fail('must reuse'), budget=common.budget)
    assert entry.prepare_shared_start(task, 1, again, retrieve) == prepared
    assert len(calls) == count and len(common.budget.records) == 3


def test_new_pair_shared_start_is_prepared_once_for_multiple_levels(tmp_path):
    task, start, specs, bindings, examples, native, retrieve, _ = native_fixture()
    prepared = []
    def prepare(task, repeat, common, retrieve):
        prepared.append(repeat)
        return copy.deepcopy(start)
    out = tmp_path / 'run'
    result = execute.run_cells([cell('L2'), cell('L3')], {'target': task}, {},
        {'target': material_callback(specs, bindings, examples)}, native, retrieve,
        EXECUTION, out, prepare_start=prepare)
    assert result['completed_P7'] == 2 and prepared == [1]
    assert (out / 'shared_starts/target_r1.json').exists()


def test_failed_stage_gate_stops_before_any_request(tmp_path):
    schedule, _ = data()
    forbidden = lambda *a: pytest.fail('stage gate must stop before request')
    result = execute.run_cells(schedule, {}, {}, {}, forbidden, forbidden,
        EXECUTION, tmp_path / 'run', stop_after=120, phase='pilot')
    assert result['status'] == 'stopped_stage_gate' and result['completed_P7'] == 0
    assert execute.read(tmp_path / 'run/cost.json')['logical_operations'] == 0


def test_readonly_expansion_check_reports_missing_gates_without_creating_clients(monkeypatch, capsys):
    monkeypatch.setattr(entry, 'clients', lambda: pytest.fail('must not create client'))
    result = entry.main(['--phase', 'expansion'])
    assert result['planned_P7'] == 480 and result['scheduled_total'] == 480
    assert {'technical_prefix_not_qualified', 'C1_not_passed',
            'pilot_public_contract_unresolved'} <= set(result['reasons'])
    assert result['new_API_calls'] == 0

"""C02成本/接续的必要控制；全部离线，不使用真实凭据或模型成绩。"""
import copy
import json

import pytest

from methods.cle_ablation import granularity_execution as execute
from methods.cle_ablation.run_joint_contract import RequestBudget
from methods.sct_trajectory.selector_protocol import SelectorPrompt
from test_memory_granularity import fixture, material_callback


EXECUTION = {'max_http_attempts': 100, 'max_conservative_tokens': 1000000,
             'max_embedding_attempts': 20}


def cell(level='L2', task='target'):
    return {'task_id': task, 'repeat': 1, 'memory_level': level,
            'cell_id': f'{task}_r1_{level}', 'phase': 'technical'}


def response(text, tokens=10):
    return {'choices': [{'message': {'content': text}}],
            'usage': {'prompt_tokens': tokens, 'completion_tokens': 1, 'total_tokens': tokens + 1}}


def journal(tmp_path, current=None, native=None, budget=None):
    return execute.CellJournal(tmp_path, current or cell(), budget or RequestBudget(100, 1000000, 20),
                               native or (lambda prompt: response('ok')))


def test_exact_response_replay_keeps_raw_normalization_and_cost_once(tmp_path):
    calls = []
    first = journal(tmp_path, native=lambda p: calls.append(p) or response('{"a":1}{"b":2}'))
    prompt = 'Plan the implementation. Public task.'
    assert json.loads(first.request(prompt)['choices'][0]['message']['content']) == {'a': 1, 'b': 2}
    path = tmp_path / 'requests/target_r1_L2/chat/0001.json'
    saved = execute.read(path)
    assert saved['raw_response']['choices'][0]['message']['content'] == '{"a":1}{"b":2}'
    # 模拟中断发生在响应落盘之后、budget终态落盘之前。
    first.budget.records[0].update(status='reserved', usage=None)
    first.flush()
    restored = execute.carried_budget(EXECUTION, [execute.read(tmp_path / 'cost.json')])
    again = journal(tmp_path, native=lambda p: pytest.fail('must reuse'), budget=restored)
    assert again.request(prompt) == saved['delivered_response']
    assert len(calls) == len(restored.records) == 1
    assert restored.snapshot()['known_returned_tokens'] == 11
    assert again.cost(preparation_cost_complete=True, completed=True)['prompt_tokens'] == 10


@pytest.mark.parametrize('saved_status', ['submitted', 'failed'])
def test_pending_or_failed_request_blocks_all_following_paid_operations(tmp_path, saved_status):
    first = journal(tmp_path)
    first.request('first')
    path = tmp_path / 'requests/target_r1_L2/chat/0001.json'
    saved = execute.read(path)
    saved['status'] = saved_status
    execute.save(path, saved)
    again = journal(tmp_path, native=lambda p: pytest.fail('must not send'), budget=first.budget)
    with pytest.raises(execute.SavedOperationBlocked): again.request('first')
    with pytest.raises(execute.SavedOperationBlocked): again.request('new subsequent prompt')
    assert len(first.budget.records) == 1


def test_changed_prompt_and_other_arm_cannot_borrow_returned_response(tmp_path):
    first = journal(tmp_path)
    first.request('original')
    changed = journal(tmp_path, native=lambda p: pytest.fail('changed prompt must stop'), budget=first.budget)
    with pytest.raises(execute.SavedOperationBlocked): changed.request('changed')
    other = journal(tmp_path, cell('L1'), budget=first.budget)
    other.request('original')
    assert len(first.budget.records) == 2


def test_complete_cost_includes_selector_and_embedding_but_not_shared_start(tmp_path):
    j = journal(tmp_path)
    j.request('generation')
    j.request(SelectorPrompt('choose', deadline=99999999999))
    embedded = j.embedding(['public query'], lambda: {'vectors': [[1, 0]],
        'usage': {'prompt_tokens': 3, 'total_tokens': 3}})
    assert embedded['vectors'] == [[1, 0]]
    assert [r['reserved_token_bound'] for r in j.budget.records][1] == len('choose'.encode()) + 1024 + 256
    assert j.cost(preparation_cost_complete=True, completed=True)['prompt_tokens'] == 23
    assert j.cost(preparation_cost_complete=True, completed=True)['known_embedding_prompt_tokens'] == 3
    assert not j.cost(preparation_cost_complete=False, completed=True)['complete']
    assert j.cost(preparation_cost_complete=True, completed=False)['prompt_tokens'] is None


def test_missing_input_usage_does_not_create_a_cost_label(tmp_path):
    j = journal(tmp_path, native=lambda p: {'choices': [], 'usage': {'total_tokens': 5}})
    j.request('public')
    result = j.cost(preparation_cost_complete=True, completed=True)
    assert result['prompt_tokens'] is None and result['unknown_input_usage_operations'] == 1


def test_embedding_cache_order_change_reuses_exact_input_without_extra_budget(tmp_path):
    j = journal(tmp_path)
    j.embedding(['one'], lambda: {'vectors': [[1]], 'usage': {'prompt_tokens': 1, 'total_tokens': 1}})
    j.embedding(['two'], lambda: {'vectors': [[2]], 'usage': {'prompt_tokens': 2, 'total_tokens': 2}})
    again = journal(tmp_path, budget=j.budget)
    assert again.embedding(['two'], lambda: pytest.fail('must reuse'))['vectors'] == [[2]]
    assert len(j.budget.records) == 2


def native_fixture():
    task, start, cards, specs, bindings, examples = fixture()
    calls, generations = [], []
    def native(prompt):
        calls.append(prompt)
        if isinstance(prompt, SelectorPrompt):
            return response('{"selected_ids":["repair-card"]}', 5)
        if prompt.startswith('Generate complete'):
            generations.append(prompt)
            text = 'def f(value): return None' if len(generations) == 1 else 'def f(value): return value'
        elif prompt.startswith('Plan '):
            text = json.dumps({'Preserved_Func': 'Identity', 'Patch_Scope': 'Return input'})
        else:
            selected = 'initial-card' if not generations else 'repair-card'
            text = json.dumps({**start['initial_analysis'], 'applied_experience_ids': [selected]})
        return response(text)
    def retrieve(query, j):
        j.embedding(['public query'], lambda: {'vectors': [[1]], 'usage': {'prompt_tokens': 3, 'total_tokens': 3}})
        j.request(SelectorPrompt('choose repair', deadline=99999999999))
        return [cards[1]], {'status': 'completed', 'selected_ids': ['repair-card']}
    return task, start, specs, bindings, examples, native, retrieve, calls


def test_missing_repair_materials_resume_native_P7_without_repaying_prefix(tmp_path):
    task, start, specs, bindings, examples, native, retrieve, calls = native_fixture()
    original_bindings = copy.deepcopy(bindings)
    del bindings['repair-card']
    out = tmp_path / 'run'
    arguments = ([cell('L3')], {'target': task}, {('target', 1): start},
                 {'target': material_callback(specs, bindings, examples)}, native, retrieve, EXECUTION, out)
    first = execute.run_cells(*arguments, preparation_cost_complete=True)
    assert first['status'] == 'waiting_materials' and first['completed_P7'] == 0
    assert not (out / 'task_rows/target_r1_L3.json').exists()
    before_calls = len(calls)
    before_budget = execute.read(out / 'cost.json')['logical_operations']
    bindings.update(original_bindings)
    result = execute.run_cells(*arguments, resume=True, preparation_cost_complete=True)
    assert result['status'] == 'completed_fixed_prefix' and result['completed_P7'] == 1
    row = execute.read(out / 'task_rows/target_r1_L3.json')
    assert row['attempts'][-1]['joint'] and len(row['attempts']) == 2
    assert row['is_experiment_score'] is False
    assert len(calls) - before_calls == 3  # 修复复析、规划、生成；选卡与付费前缀不重复。
    assert execute.read(out / 'cost.json')['logical_operations'] - before_budget == 3
    assert execute.read(out / 'cell_costs/target_r1_L3.json')['complete']
    assert len((out / 'rows.jsonl').read_text(encoding='utf-8').splitlines()) == 1
    assert len(list((out / 'partials/target_r1_L3').glob('*.json'))) == 1
    assert not (out / 'writer.lock').exists()
    assert execute.read(out / 'generation/target_r1_L3/1.json')['workflow_completed']
    assert (out / 'validation/target_r1_L3/1.json').exists()
    assert execute.read(out / 'retrieval_trace/target_r1_L3/1.json')['selected_ids'] == ['repair-card']


def test_technical_failure_stops_next_cell_and_is_not_automatically_restarted(tmp_path):
    task, start, specs, bindings, examples, _, retrieve, _ = native_fixture()
    calls = []
    def failure(prompt):
        calls.append(prompt)
        raise TimeoutError('offline observed failure')
    cells = [cell('L2'), cell('L1')]
    out = tmp_path / 'run'
    args = (cells, {'target': task}, {('target', 1): start},
            {'target': material_callback(specs, bindings, examples)}, failure, retrieve, EXECUTION, out)
    result = execute.run_cells(*args, preparation_cost_complete=True)
    assert result['status'] == 'stopped_technical_error'
    assert result['completed_P7'] == 1 and len(calls) == 1
    assert not (out / 'task_rows/target_r1_L1.json').exists()
    assert execute.read(out / 'cost.json')['unknown_usage_operations'] == 1
    with pytest.raises(execute.SavedOperationBlocked): execute.run_cells(*args, resume=True)


def test_budget_exhaustion_stops_without_sending_an_extra_request(tmp_path):
    task, start, specs, bindings, examples, native, retrieve, calls = native_fixture()
    small = {**EXECUTION, 'max_http_attempts': 1}
    out = tmp_path / 'run'
    result = execute.run_cells([cell()], {'target': task}, {('target', 1): start},
        {'target': material_callback(specs, bindings, examples)}, native, retrieve, small, out)
    assert result['status'] == 'stopped_budget' and len(calls) == 1
    assert execute.read(out / 'cost.json')['reserved_http_attempts'] == 1


def test_existing_writer_lock_is_not_removed_by_a_second_invocation(tmp_path):
    out = tmp_path / 'run'
    out.mkdir()
    execute.save(out / 'schedule.json', [cell()])
    execute.save(out / 'run_metadata.json', {'status': 'running', 'execution': EXECUTION,
        'is_experiment_score': False})
    execute.save(out / 'cost.json', RequestBudget(100, 1000000, 20).snapshot())
    (out / 'writer.lock').write_text('123456', encoding='utf-8')
    with pytest.raises(FileExistsError):
        execute.run_cells([cell()], {}, {}, {}, None, None, EXECUTION, out, resume=True)
    assert (out / 'writer.lock').read_text(encoding='utf-8') == '123456'


def test_completed_prefix_is_reused_without_new_native_calls_or_duplicate_rows(tmp_path):
    task, start, specs, bindings, examples, native, retrieve, calls = native_fixture()
    missing = copy.deepcopy(bindings)
    del missing['initial-card']
    def materials(cards, public, level):
        return material_callback(specs, missing if level == 'L3' else bindings, examples)(cards, public, level)
    out = tmp_path / 'run'
    args = ([cell('L2'), cell('L3')], {'target': task}, {('target', 1): start},
            {'target': materials}, native, retrieve, EXECUTION, out)
    first = execute.run_cells(*args, preparation_cost_complete=True)
    assert first['status'] == 'waiting_materials' and first['completed_P7'] == 1
    prefix = (out / 'task_rows/target_r1_L2.json').read_bytes()
    cost_before = execute.read(out / 'cost.json')['logical_operations']
    missing.update(bindings)
    resumed = execute.run_cells(*args, resume=True, preparation_cost_complete=True)
    assert resumed['completed_P7'] == 2
    assert (out / 'task_rows/target_r1_L2.json').read_bytes() == prefix
    assert execute.read(out / 'cost.json')['logical_operations'] - cost_before == 3
    assert len((out / 'rows.jsonl').read_text(encoding='utf-8').splitlines()) == 2


def test_changed_native_protocol_in_saved_prefix_is_rejected_before_api(tmp_path):
    out = tmp_path / 'run'
    out.mkdir()
    execute.save(out / 'schedule.json', [cell()])
    execute.save(out / 'run_metadata.json', {'status': 'running', 'execution': EXECUTION,
        'is_experiment_score': False})
    execute.save(out / 'cost.json', RequestBudget(100, 1000000, 20).snapshot())
    execute.save(out / 'task_rows/target_r1_L2.json', {**cell(), 'protocol': 'other-protocol'})
    with pytest.raises(execute.SavedOperationBlocked):
        execute.run_cells([cell()], {}, {}, {}, lambda p: pytest.fail('no API'),
                          None, EXECUTION, out, resume=True)
    assert not (out / 'writer.lock').exists()

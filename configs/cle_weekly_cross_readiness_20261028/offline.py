"""封网验证原 P7 C41 完整消费、保存响应恢复、完整回放及负结果不早停。"""
import argparse
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

from configs.cle_weekly_build_readiness_20261027.offline import tasks as fixture_tasks, LocalProvider
from configs.cle_weekly_eval_20261027 import retest as base
from configs.cle_weekly_cross_20261027 import new_bank_runner as original
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.replay_journal import write_json
from . import runtime, recovery
from .reuse import forbidden


def validate(destination):
    destination = Path(destination)
    package = destination / 'C41'
    source_tasks = {str(t['index']): t for t in fixture_tasks() if t['index'] in (90, 91)}
    source_tasks['91']['task_description']['description'] = 'Replay fixture. Return the boolean input unchanged.'
    cells = [{'cell_id': f'{tid}_r{repeat}_V41_C41', 'task_id': tid,
        'family_id': task['family_id'], 'repeat': repeat, 'condition': 'C41',
        'model_arm': 'V41', 'bank_arm': 'C41'} for tid, task in source_tasks.items() for repeat in (1, 2)]
    nodes = base.runner.load_memory(base.RUN / 'shared_inputs/memory1939_q0.jsonl')[:2]
    for node in nodes:
        node.q_value = 0
        node.q_visits = 0
    bank = destination / 'synthetic_bank.jsonl'
    _write_memory(bank, nodes)
    cap = {'conservative_model_and_embedding_tokens': 10000000,
        'total_physical_HTTP_attempts': 1000, 'embedding_HTTP_attempts_included_in_total': 200}
    inputs = package / 'inputs'
    write_json(inputs / 'tasks.json', source_tasks)
    write_json(inputs / 'schedule.json', cells)
    write_json(inputs / 'shared_initials.json', {f'{tid}_r{r}': {'task_id': tid, 'repeat': r,
        'initial_analysis': {'vulnerability_hypothesis': ['Preserve the boolean input.'],
            'functional_invariants': ['Return the input unchanged.']}, 'error_type': None}
        for tid in source_tasks for r in (1, 2)})
    write_json(inputs / 'protocol.json', {'protocol': 'offline_CROSS_original_P7_only',
        'planned_P7': 4, 'bank_sources': {'C41': str(bank)}, 'card_count': 2,
        'budget_proposed': cap, 'paid_execution_enabled': False})
    cache = destination / 'shared_inputs/embeddings.sqlite3'
    cache.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(cache) as db:
        db.execute('CREATE TABLE fixture (id INTEGER)')
    provider = LocalProvider()
    with ExitStack() as stack:
        stack.enter_context(patch.object(base, 'RUN', destination))
        stack.enter_context(patch.object(runtime, 'PACKAGE', package))
        stack.enter_context(patch.object(original, 'PACKAGE', package))
        for name in ('methods.sct_trajectory.replay_journal.ensure_model_call_allowed',
                     'methods.sct_trajectory.run_closed_loop.ensure_model_call_allowed',
                     'configs.cle_v41_relation_20261026.execution.ensure_model_call_allowed'):
            stack.enter_context(patch(name, return_value=None))
        stack.enter_context(patch('methods.sct_trajectory.run_closed_loop.load_key', return_value='synthetic-only'))
        stack.enter_context(patch('socket.create_connection', side_effect=forbidden))
        stack.enter_context(patch('socket.socket.connect', side_effect=forbidden))
        stage = runtime.CrossNewBank(destination=package / 'segment_001')
        stage.io.physical_open = provider.open
        result = stage.execute()
        assert result['completed'] == 4
        assert all(len(row['attempts']) == (2 if row['task_id'] == '91' else 1) for row in stage.rows)
        assert result['arms']['C41']['joint'] == 2
        assert all(1 <= len(row['attempts']) <= 2 and row['Q_updates'] == 0 for row in stage.rows)
        assert {arm: [n.to_dict() for n in bank] for arm, bank in stage.banks.items()} == stage.frozen_before
        requests = len(provider.calls)
        # 仅移除本合成夹具的一行，模拟已返回完整响应而逐题落盘丢失。
        missing = next((stage.out / 'task_rows').glob('*.json'))
        saved = base.read(missing)
        missing.unlink()
        resumed = runtime.CrossNewBank([stage.out], destination=package / 'segment_002')
        resumed.io.physical_open = provider.open
        recovered = resumed.execute()
        assert recovered['completed'] == 4 and len(provider.calls) == requests
        assert next(r for r in resumed.rows if r['cell_id'] == saved['cell_id'])['final']['code'] == saved['final']['code']
        replayed = runtime.CrossNewBank([stage.out, resumed.out], offline=True, destination=package / 'replay')
        replayed.execute()
        assert len(provider.calls) == requests
        assert base.read(replayed.out / 'replay_result.json')['status'] == 'passed'
        probe = recovery.probe([stage.out, resumed.out], package / 'prefix_probe')
        assert probe['status'] == 'passed' and probe['new_HTTP'] == 0
        # 未完成的一格只保存前两个成功响应，必须准确停在第三个请求前。
        partial = package / 'partial'
        import shutil
        shutil.copytree(stage.out, partial)
        for path in (partial / 'task_rows').glob('*.json'):
            path.unlink()
        target = cells[0]['cell_id']
        records = sorted((partial / 'journals' / target / 'requests').glob('*.json'),
            key=lambda p: base.read(p)['started_utc'])
        keep = {str(p) for p in records[:2]}
        for path in (partial / 'journals').glob('*/requests/*.json'):
            if str(path) not in keep:
                path.unlink()
        incomplete_probe = recovery.probe([partial], package / 'partial_probe')
        assert incomplete_probe['status'] == 'passed' and incomplete_probe['boundary']['cell'] == target
        assert incomplete_probe['new_HTTP'] == 0
        wire_before = len(list((partial / 'wire').glob('*.request.json')))
        retained = base.read(partial / 'budget.json')['charged_tokens_including_unknown_and_inflight_bounds']
        # 独立合成传输故障：两次成功、第三次 TLS 未决。正式历史记录从未改写。
        transport_source = package / 'synthetic_transport_source'
        transport_source.mkdir()
        for filename in ('source_identity.json', 'input_identity.json', 'embeddings.sqlite3'):
            shutil.copy2(stage.out / filename, transport_source / filename)
        complete_records = sorted((stage.out / 'journals' / target / 'requests').glob('*.json'),
            key=lambda p: base.read(p)['started_utc'])[:3]
        for number, path in enumerate(complete_records, 1):
            record = base.read(path)
            if number == 3:
                record.pop('response')
                record.update(status='failed_or_unresolved', diagnostics=[{'category': 'network_error'}])
            write_json(transport_source / 'journals' / target / 'requests' / path.name, record)
            wire = transport_source / 'wire' / f'{number:07d}'
            write_json(wire.with_suffix('.request.json'), {'body': {'model': base.wiring.SETTINGS['model'],
                'messages': [{'role': 'user', 'content': record['prompt']}],
                'max_tokens': 256 if record['selector'] else 4096}})
            write_json(wire.with_suffix('.status.json'), {'status': 'transport_error' if number == 3 else 'response_closed',
                'http_status': None if number == 3 else 200, 'error_type': 'URLError' if number == 3 else None})
            if number != 3:
                wire.with_suffix('.response.raw').write_bytes(b'data: {"usage":{"total_tokens":10}}\n')
        failed_path = transport_source / 'journals' / target / 'requests' / complete_records[2].name
        failed_bytes = failed_path.read_bytes()
        transport_probe = recovery.probe([transport_source], package / 'transport_probe')
        assert transport_probe['status'] == 'passed' and len(transport_probe['pending']) == 1
        pending = recovery.classify([transport_source])
        with patch.object(base, 'unresolved_requests', return_value=[]):
            transport_resumed = runtime.CrossNewBank([transport_source], destination=package / 'transport_resumed')
        before_resume = transport_resumed.io.budget.snapshot()
        assert before_resume['transport_attempts_including_prior'] == 3
        assert any(e['status'] == 'historical_unknown' for e in before_resume['entries'])
        recovery.authorize_pending(transport_resumed, pending)
        transport_resumed.io.physical_open = provider.open
        transport_result = transport_resumed.execute()
        assert transport_result['completed'] == 4
        assert failed_path.read_bytes() == failed_bytes
        assert len(transport_resumed.io.journal(target).consumed) == 2
        assert (transport_resumed.out / 'authorized_pending' / (target + '.json')).exists()
        assert any(e['status'] == 'historical_unknown' for e in transport_resumed.io.budget.entries)
    evidence = {'status': 'passed', 'scope': 'synthetic two tasks x two repeats; original P7, semantic retrieval and python -I validator',
        'API_calls': 0, 'simulated_HTTP': requests, 'completed': 4, 'normal_negative_cells': 2,
        'completed_response_recovery_new_HTTP': 0, 'full_replay_new_HTTP': 0,
        'prefix_probe': str(package / 'partial_probe/prefix_probe.json'),
        'replay_result': str(package / 'replay/replay_result.json'),
        'retained_prior_physical_attempts': wire_before, 'retained_budget_charged_tokens': retained,
        'authorized_transport_resume': {'status': 'passed', 'saved_successes_consumed': 2,
            'old_failed_record_unchanged': True, 'unknown_usage_retained': True,
            'probe': str(package / 'transport_probe/prefix_probe.json'),
            'native_summary': str(package / 'transport_resumed/summary.json')},
        'not_real_C41_library_or_model_score': True}
    write_json(destination / 'result.json', evidence)
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.destination), ensure_ascii=False))


if __name__ == '__main__':
    main()

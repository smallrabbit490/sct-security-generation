"""从实际离线运行及锁测试发布 BUILD.prepare 收据；不启动任何付费节点。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from configs.cle_weekly_build_20261027 import execute as original, recovery_inputs
from configs.cle_weekly_build_20261027.completion import verify_native_outputs, rows
from methods.sct_trajectory.run_closed_loop import assign_families_atomic
from methods.sct_trajectory.replay_journal import write_json
from tools.cle_live_workbench import app
from .runtime import MODULE, HASH_SEED, active_workers


def finish(public_root, native_root, tests):
    public_root, native_root, tests = Path(public_root), Path(native_root), Path(tests)
    proof = public_root.parent
    native = original.read(native_root / 'result.json')
    cross = original.read(native_root / 'cross_process_replay_result.json')
    assert native['status'] == cross['status'] == 'passed'
    assert native['actual_native_workers_peak'] == 4 and native['API_calls'] == cross['API_calls'] == 0
    assert native['model_responses_replayed'] > 0 and cross['new_HTTP'] == 0
    reports = []
    for stage in ('scheduler', 'global_gate'):
        report = original.read(public_root / stage / 'result.json')
        assert report['status'] == 'passed' and report['API_calls'] == 0
        assert report['source_snapshots_verified'] and report['input_snapshots_verified']
        assert report['unknown_usage_retained'] and report['original_validator_executed']
        assert report['full_replay']['status'] == 'primary_outputs_match'
        assert report['full_replay']['new_HTTP'] == 0
        assert all(p['status'] == 'passed' and p['new_HTTP'] == 0 for p in report['probes'])
        run = public_root / stage / 'run'
        # 这里只重新核对真实快照；不重跑任何任务或改旧段。
        old_run = recovery_inputs.RUN
        recovery_inputs.RUN = run
        try:
            for source in map(Path, report['sources']):
                recovery_inputs.verify_source_snapshot(source)
                recovery_inputs.verify_input_snapshot(source)
        finally:
            recovery_inputs.RUN = old_run
        reports.append(report)
    suite = ET.parse(tests).getroot()
    suites = list(suite) if suite.tag == 'testsuites' else [suite]
    total = sum(int(s.attrib.get('tests', 0)) for s in suites)
    assert total >= 27
    assert all(int(s.attrib.get('failures', 0)) == int(s.attrib.get('errors', 0)) == 0 for s in suites)
    manifest = original.read(original.BUILD / 'inputs/manifest.json')
    task_rows = original.read(original.BUILD / 'inputs/plt_tasks.json')
    fixed = original.read(original.BUILD / 'inputs/pools.json')
    actual = assign_families_atomic([t['index'] for t in task_rows],
        lambda rid: next(t['family_id'] for t in task_rows if int(t['index']) == rid))
    assert actual == fixed and manifest['starting_memory'] == 'empty' and manifest['Q_enabled'] is False
    assert [len(actual[k]) for k in ('source_pool', 'replay_pool', 'audit_pool')] == [303, 273, 298]
    arguments = original.read(original.BUILD / 'native_arguments.json')['arguments']
    required = {'--model': 'deepseek-v4.1-flash-1017', '--max-tokens': '4096', '--thinking': 'disabled',
                '--rounds': '3', '--repairs': '1', '--workers': '4', '--phase3-workers': '4',
                '--retrieval-mode': 'semantic_llm', '--gate-mode': 'global', '--branch-count': '1'}
    assert all(arguments[arguments.index(k) + 1] == v for k, v in required.items())
    budget = original.read(original.BUILD / 'budget.json')
    cap = budget['budget_proposed']
    assert cap == {'conservative_model_and_embedding_tokens': 560398731,
                   'total_physical_HTTP_attempts': 97377,
                   'embedding_HTTP_attempts_included_in_total': 36792}
    assert budget['reset_on_resume'] is False
    assert not (original.BUILD / 'execution').exists(), 'real_BUILD_execution_already_exists'
    inventory = app.process_inventory()
    workers = active_workers(inventory)
    status = original.read(original.RUN / 'workbench_monitor/status.json')
    live_evidence = []
    protected = set()
    for package in status['packages']:
        if package['key'] not in ('FQ_LEARN', 'FFS'):
            continue
        segment = Path(package['segment'])
        source_identity = segment / 'source_identity.json'
        hashes = original.read(source_identity) if source_identity.exists() else {}
        protected.update(hashes)
        state = original.read(segment / 'state.json')
        summary = original.read(segment / 'summary.json')
        ledger = original.read(segment / 'budget.json')
        wire = list((segment / 'wire').glob('*.status.json'))
        latest = max(wire, key=lambda p: p.stat().st_mtime) if wire else None
        wire_status = original.read(latest) if latest else {}
        live_evidence.append({'package': package['key'], 'segment': str(segment),
            'source_identity': str(source_identity), 'state_status': state.get('status'),
            'summary_status': summary.get('status'), 'completed': summary.get('completed'),
            'wire_status_file': str(latest) if latest else None,
            'wire_status': {k: wire_status[k] for k in ('status', 'http_status', 'error_type') if k in wire_status},
            'budget': {k: ledger[k] for k in ('cap_tokens', 'cap_HTTP', 'known_reported_tokens',
                  'charged_tokens_including_unknown_and_inflight_bounds', 'transport_attempts_including_prior') if k in ledger}})
    added = [str(p.relative_to(original.ROOT)).replace('\\', '/') for p in Path(__file__).parent.glob('*.py')]
    assert not set(added) & {p.replace('\\', '/') for p in protected}
    observed = {'time': datetime.now(timezone.utc).isoformat(), 'API_calls': 0,
        'allocated_paid_workers': 0, 'started_paid_processes': [],
        'active_instances': [{'pid': p['ProcessId'], 'parent_pid': p.get('ParentProcessId'),
                             'package': p['package'], 'command': p['CommandLine']} for p in workers],
        'active_packages': live_evidence, 'new_source_files': added,
        'active_source_identity_intersection': [], 'fixed_native_pools_match': True,
        'native_pool_counts': {'D_init': 303, 'D_grow': 273, 'D_gate': 298},
        'budget_cap_unchanged': cap}
    write_json(proof / 'prepare_observation.json', observed)
    evidence = [str(native_root / 'result.json'), str(native_root / 'cross_process_replay_result.json'),
                str(public_root / 'scheduler/result.json'), str(public_root / 'global_gate/result.json'),
                str(tests), str(proof / 'prepare_observation.json')]
    common = {'status': 'passed', 'API_calls': 0, 'real_model_cells': 0, 'evidence': evidence,
              'scope': 'zero-API technical readiness on synthetic tasks with original native phases and validator; full real BUILD not executed',
              'execution_command': MODULE + ' launch', 'required_paid_workers': 4,
              'PYTHONHASHSEED': HASH_SEED, 'tests_passed': total}
    recovery = {**common, 'native_three_rounds': [1, 2, 3], 'active_replay_executed': True,
                'global_gate_executed': True, 'recovery_boundaries': ['scheduler', 'global_gate_multiple_pending'],
                'complete_replay': 'primary_outputs_match', 'prefix_new_HTTP': 0,
                'successful_responses_reused': True, 'prior_failure_and_unknown_usage_retained': True}
    wiring = {**common, 'native_worker_peak': 4,
              'exclusive_package_locks_tested': ['learning', 'FQ_RETEST', 'FQ_GATE', 'FFS', 'FG_LABELS', 'FG_GATE', 'FR'],
              'arbitrary_embedding_task_process_recognition': True, 'venv_parent_child_counted_once': True,
              'cross_process_replay': 'passed', 'finite_budget_frozen': True,
              'next_action': 'workbench schedules BUILD.run with exclusive 4-worker allocation; use the independent execution_command',
              'launch_not_performed': 'BUILD.prepare allocated_workers=0; current Q and FFS processes preserved'}
    before = proof / 'budget_before_readiness.json'
    if not before.exists():
        shutil.copy2(original.BUILD / 'budget.json', before)
    # 只开放已验证的同一有限上限，不改累计账本、不扩大预算，不把准备算模型完成。
    budget.update(execution_ready=True, execution_readiness_evidence=str(original.BUILD / 'execution_wiring_readiness.json'),
                  execution_command=MODULE + ' launch', runtime_hash_seed=HASH_SEED)
    write_json(original.BUILD / 'recovery_readiness.json', recovery)
    write_json(original.BUILD / 'execution_wiring_readiness.json', wiring)
    write_json(original.BUILD / 'budget.json', budget)
    receipt = {'task_id': 'BUILD.prepare', 'status': 'completed',
               'evidence': [str(original.BUILD / name) for name in
                            ('recovery_readiness.json', 'execution_wiring_readiness.json', 'budget.json')] + evidence,
               'execution_command': MODULE + ' launch', 'allocated_workers': 0,
               'real_model_cells': 0, 'API_calls': 0,
               'remaining': ['BUILD.run waits for workbench exclusive four-worker allocation; no paid node launched here']}
    write_json(original.RUN / 'workbench_monitor/autonomy/receipts/BUILD.prepare.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--public', required=True)
    parser.add_argument('--native', required=True)
    parser.add_argument('--tests', required=True)
    args = parser.parse_args()
    print(json.dumps(finish(args.public, args.native, args.tests), ensure_ascii=False))

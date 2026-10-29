"""CROSS v4.1 入口：绑定真实新库、逐格复用、精确恢复、原生回放；启动须有 worker 分配。"""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from configs.cle_weekly_eval_20261027 import retest as base
from configs.cle_weekly_cross_20261027 import prepare_new_bank
from configs.cle_weekly_build_20261027.process_guard import exclusive_slots
from configs.cle_weekly_build_readiness_20261027.runtime import active_workers
from configs.cle_weekly_proxy_recovery_20261027.runner import proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from . import runtime, recovery, reuse
from .prepare import OUT, RUN, CAP


def sources():
    path = runtime.PACKAGE / 'execution_index.json'
    return [Path(p) for p in base.read(path)['segments']] if path.exists() else []


def check():
    reasons = list(prepare_new_bank.dependencies()['reasons'])
    if not (OUT / 'protocol.json').exists() or not (OUT / 'budget.json').exists():
        reasons.append('cross_v41_wiring_not_frozen')
    else:
        budget = base.read(OUT / 'budget.json')
        if budget['budget_proposed'] != CAP or budget['reset_on_resume'] is not False:
            reasons.append('cross_finite_budget_mismatch')
    gate = RUN / 'FX_GATE/prepare_validation/readiness.json'
    if not gate.exists() or base.read(gate).get('status') != 'passed':
        reasons.append('cross_offline_controls_not_passed')
    return {'ready': not reasons, 'reasons': reasons, 'API_calls': 0,
        'planned_v41': 1788, 'new_P7': 596, 'workers_max': 3,
        'execution_command': runtime.MODULE + ' launch --workers 3'}


@runtime.json_encoding()
def bind():
    if not check()['ready']:
        raise ReplayStop('cross_dependencies_not_ready')
    inputs = runtime.PACKAGE / 'inputs/protocol.json'
    if not inputs.exists():
        prepare_new_bank.prepare()
    protocol = base.read(inputs)
    if protocol['budget_proposed'] != CAP or protocol['model_settings'] != base.wiring.SETTINGS:
        raise ReplayStop('cross_bound_protocol_or_budget_changed')
    # 已冻结1192个同题同重复复用格，不为缺失的FFS格购买替代响应。
    summary = RUN / 'FX_GATE/v41_reuse/summary.json'
    result = base.read(summary) if summary.exists() else {}
    if result.get('status') != 'passed' or result.get('matched_cells') != 1192:
        readiness = base.read(RUN / 'FX_GATE/prepare_validation/readiness.json')
        previous = str(summary) if summary.exists() else readiness['reuse_summary']
        destination = RUN / 'FX_GATE/v41_reuse/audits' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        result = reuse.audit(destination, resume_from=previous)
        write_json(summary, result)
    if result['status'] != 'passed' or result['matched_cells'] != 1192:
        raise ReplayStop('cross_full_1192_exact_FFS_reuse_not_verified')
    return {'status': 'bound', 'new_cells': 596, 'reused_cells': 1192, 'API_calls': 0}


def register(process, command, workers):
    path = RUN / 'workbench_monitor/autonomy/registered_workers.json'
    prior = base.read(path) if path.exists() else []
    write_json(path, prior + [{'pid': process.pid, 'package': 'FX_GATE',
        'workers': workers, 'command_marker': runtime.MODULE}])
    value = {'pid': process.pid, 'command': command, 'workers': workers,
             'created_at': datetime.now().astimezone().isoformat()}
    write_json(runtime.PACKAGE / 'launch.json', value)
    return value


def launch(workers):
    if not 1 <= workers <= 3:
        return {'status': 'waiting_capacity', 'reason': 'explicit_1_to_3_workers_required'}
    active = active_workers()
    if active:
        return {'status': 'queued_behind_running_experiment',
                'active': [{'pid': p['ProcessId'], 'package': p['package']} for p in active]}
    state = check()
    if not state['ready']:
        return {'status': 'waiting_dependency', **state}
    bind()
    ensure_model_call_allowed(base.wiring.SETTINGS['model'])
    if not proxy_ready():
        return {'status': 'proxy_unavailable'}
    action = 'resume' if sources() else 'run'
    command = [sys.executable, '-B', '-X', 'utf8', '-m', runtime.MODULE, action, '--workers', str(workers)]
    with (runtime.PACKAGE / 'stdout.log').open('a', encoding='utf-8') as out, \
         (runtime.PACKAGE / 'stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=base.ROOT, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    return {'status': 'launched', **register(process, command, workers)}


def execute(action, workers):
    if not 1 <= workers <= 3:
        raise ReplayStop('cross_paid_execution_requires_allocated_1_to_3_workers')
    runtime.CrossNewBank.worker_limit = workers
    with exclusive_slots(RUN):
        if active_workers():
            raise ReplayStop('another_CLE_experiment_is_active')
        bind()
        prior = sources()
        if prior and action != 'resume':
            raise ReplayStop('cross_existing_segments_require_resume')
        pending = recovery.classify(prior)
        if prior:
            destination = runtime.PACKAGE / ('prefix_probe_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            checked = recovery.probe(prior, destination)
            if checked['status'] != 'passed':
                raise ReplayStop('cross_saved_prefix_not_verified')
        ensure_model_call_allowed(base.wiring.SETTINGS['model'])
        destination = runtime.PACKAGE / f'segment_{len(prior)+1:03d}'
        with patch.object(base, 'unresolved_requests', return_value=[]), verified_proxy_transport():
            study = runtime.CrossNewBank(prior, destination=destination)
        recovery.authorize_pending(study, pending)
        write_json(runtime.PACKAGE / 'execution_index.json', {'segments': list(map(str, prior)) + [str(destination)]})
        result = study.execute()
        write_json(runtime.PACKAGE / 'completion.json', {'status': 'awaiting_agent_analysis', 'planned': 596})
        finalize()
        return result


def replay():
    prior = sources()
    if not prior or base.read(prior[-1] / 'summary.json').get('completed') != 596:
        raise ReplayStop('cross_full_real_C41_run_required')
    pending = recovery.classify(prior)
    if pending:
        raise ReplayStop('cross_unresolved_request_before_full_replay')
    target = runtime.PACKAGE / 'zero_API_replay'
    if (target / 'replay_result.json').exists():
        return base.read(target / 'replay_result.json')
    with patch.object(base, 'unresolved_requests', return_value=[]):
        return runtime.CrossNewBank(prior, offline=True, destination=target).execute()


def finalize():
    """按固定 cell_id 合并实际复用凭证及新库原生行；成本仍分别归原执行包，不重复相加。"""
    reused = base.read(RUN / 'FX_GATE/v41_reuse/summary.json')
    prior = sources()
    if (reused.get('status') != 'passed' or reused.get('matched_cells') != 1192
            or not prior or base.read(prior[-1] / 'summary.json').get('status') != 'completed'
            or base.read(prior[-1] / 'summary.json').get('completed') != 596):
        raise ReplayStop('cross_native_full_scope_not_completed')
    actual = {}
    for path in reused['reuse_evidence']:
        proof = base.read(Path(path))
        if proof.get('status') != 'matched':
            raise ReplayStop('cross_invalid_reuse_proof')
        row_path = proof['source_rows'][-1]
        actual[proof['cell_id']] = {'row': base.read(Path(row_path)), 'path': row_path, 'reuse_evidence': path}
    for source in prior:
        for path in (source / 'task_rows').glob('*.json'):
            row = base.read(path)
            if row['cell_id'] in actual and actual[row['cell_id']]['row'] != row:
                raise ReplayStop('cross_conflicting_native_final_row')
            actual[row['cell_id']] = {'row': row, 'path': str(path), 'reuse_evidence': None}
    schedule = base.read(OUT / 'schedule.json')
    if set(actual) != {c['cell_id'] for c in schedule}:
        raise ReplayStop('cross_native_1788_cell_identity_mismatch')
    arms = {}
    index = []
    for arm in ('E0', 'C32', 'C41'):
        cells = [c for c in schedule if c['bank_arm'] == arm]
        rows = [actual[c['cell_id']]['row'] for c in cells]
        arms[arm] = {'completed': len(rows), **{key: sum(bool(r['final'][key]) for r in rows)
            for key in ('functional', 'security', 'joint', 'measured')}}
        index.extend({**c, 'native_row': actual[c['cell_id']]['path'],
            'reuse_evidence': actual[c['cell_id']]['reuse_evidence']} for c in cells)
    target = RUN / 'FX_GATE/V41'
    write_json(target / 'rows_index.json', index)
    summary = {'status': 'completed', 'planned': 1788, 'completed': len(actual), 'arms': arms,
        'reused_cells': 1192, 'new_C41_cells': 596, 'Q_updates': 0,
        'FFS_cost_source': str(RUN / 'FFS/execution_index.json'),
        'C41_cost_source': str(prior[-1] / 'budget.json'),
        'cost_rule': 'FFS charged once in FFS; C41 wire cumulative once across segments; no summing reused row usage',
        'scope': 'V41 only; V32 remains unavailable', 'analysis_status': 'pending'}
    write_json(target / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'bind', 'launch', 'run', 'resume', 'probe', 'replay', 'finalize'])
    parser.add_argument('--workers', type=int, choices=range(4), default=0)
    args = parser.parse_args()
    if args.action == 'check':
        result = check()
    elif args.action == 'bind':
        result = bind()
    elif args.action == 'launch':
        result = launch(args.workers)
    elif args.action == 'probe':
        prior = sources()
        if not prior:
            raise ReplayStop('cross_no_real_sources_to_probe')
        target = runtime.PACKAGE / ('prefix_probe_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        result = recovery.probe(prior, target)
    elif args.action == 'replay':
        result = replay()
    elif args.action == 'finalize':
        result = finalize()
    else:
        result = execute(args.action, args.workers)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

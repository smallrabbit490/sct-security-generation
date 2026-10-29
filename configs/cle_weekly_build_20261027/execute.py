"""Native build entry; paid execution stays disabled until recovery is verified."""
import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from .prepare_inputs import ROOT, RUN, read
from .physical_guard import physical_guard
from .native_adapter import run_native
from .process_guard import current_active_experiments, exclusive_slots
from .completion import verify_native_outputs
from methods.sct_trajectory.replay_journal import write_json
from configs.cle_model_baseline_20261024.execute import record_validations
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from configs.cle_weekly_proxy_recovery_20261027.runner import proxy_ready
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed

BUILD = RUN / 'BUILD_C41'


def snapshot_sources(segment):
    for directory in ('methods', 'src', 'configs/cle_weekly_build_20261027',
                      'configs/cle_weekly_recovery_20261027',
                      'configs/cle_weekly_proxy_recovery_20261027',
                      'configs/cle_weekly_full_20261027',
                      'configs/cle_v41_relation_20261026',
                      'configs/cle_v41_migration_20261025',
                      'configs/cle_model_baseline_20261024'):
        for source in (ROOT / directory).rglob('*.py'):
            destination = segment / 'source_bundle' / source.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    helper = RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'
    external = segment / 'source_bundle_external/transport_resume_stream_20261027.py'
    external.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(helper, external)
    for name in ('inputs/plt_tasks.json', 'inputs/pools.json', 'inputs/manifest.json',
                 'native_arguments.json', 'budget.json'):
        destination = segment / 'input_snapshot' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BUILD / name, destination)


def check():
    required = ['inputs/plt_tasks.json', 'inputs/pools.json', 'inputs/manifest.json',
                'native_arguments.json', 'budget.json', 'recovery_readiness.json',
                'execution_wiring_readiness.json']
    missing = [name for name in required if not (BUILD / name).exists()]
    recovery = read(BUILD / 'recovery_readiness.json') if not missing else {}
    if not missing and recovery.get('status') != 'passed':
        missing.append('verified_native_recovery')
    if not missing and read(BUILD / 'execution_wiring_readiness.json').get('status') != 'passed':
        missing.append('verified_worker_slots_and_replay')
    return {'ready': not missing, 'missing': missing, 'API_calls': 0}


def run():
    result = check()
    if not result['ready']:
        raise SystemExit('build_not_ready:' + ','.join(result['missing']))
    with exclusive_slots(RUN):
        run_exclusive()


def run_exclusive():
    if current_active_experiments():
        raise SystemExit('another_CLE_experiment_is_active')
    segment = BUILD / 'execution/segment_001'
    if segment.exists():
        raise SystemExit('existing_segment_requires_verified_recovery')
    budget = read(BUILD / 'budget.json')['budget_proposed']
    arguments = read(BUILD / 'native_arguments.json')['arguments']
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with verified_proxy_transport():
        io = physical_guard(segment, budget, direct.open, live=True)
    snapshot_sources(segment)
    record_validations(segment, 'PLT')
    write_json(segment / 'state.json', {'status': 'running', 'phase': 'native_build'})
    try:
        run_native(io, arguments)
        result = verify_native_outputs(BUILD / 'native/segment_001', read(RUN / 'manifest.json')['pools'])
        write_json(segment / 'native_verification.json', result)
    except BaseException as exc:
        write_json(segment / 'state.json', {'status': 'stopped_technical', 'error_type': type(exc).__name__})
        raise
    write_json(segment / 'state.json', {'status': 'completed_pending_verification'})


def launch():
    result = check()
    if not result['ready']:
        return {'status': 'not_ready', **result}
    if current_active_experiments():
        return {'status': 'queued_behind_running_experiment'}
    ensure_model_call_allowed(SETTINGS['model'])
    if not proxy_ready():
        return {'status': 'proxy_unavailable'}
    if (BUILD / 'execution/segment_001').exists():
        return {'status': 'existing_segment_requires_recovery'}
    with (BUILD / 'launch.stdout.log').open('a', encoding='utf-8') as stdout, (BUILD / 'launch.stderr.log').open('a', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
            'configs.cle_weekly_build_20261027.execute', 'run'], cwd=ROOT,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    return {'status': 'launched', 'pid': process.pid}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'launch', 'run'])
    args = parser.parse_args()
    if args.action == 'check':
        print(json.dumps(check(), ensure_ascii=False))
    elif args.action == 'launch':
        print(json.dumps(launch(), ensure_ascii=False))
    else:
        run()


if __name__ == '__main__':
    main()

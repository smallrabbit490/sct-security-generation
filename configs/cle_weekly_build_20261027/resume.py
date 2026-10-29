"""Resume one verified native-build transport boundary in a new segment."""
import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

from .prepare_inputs import RUN, read
from .execute import BUILD, snapshot_sources
from .native_adapter import run_native
from .physical_guard import physical_guard
from .process_guard import exclusive_slots, current_active_experiments
from .recovery_inputs import verify_input_snapshot, verify_source_snapshot, recovery_arguments
from .recovery_plan import classify_sources
from .recovery_probe import probe
from .completion import verify_native_outputs
from configs.cle_model_baseline_20261024.execute import record_validations
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from configs.cle_weekly_proxy_recovery_20261027.runner import proxy_ready


def resume(sources, probe_result):
    sources = [Path(path) for path in sources]
    if not sources:
        raise ReplayStop('build_resume_without_sources')
    for source in sources:
        verify_source_snapshot(source)
        verify_input_snapshot(source)
    pending = classify_sources(sources)
    receipt = read(Path(probe_result))
    target = (receipt.get('pending_cell'), receipt.get('pending_identity'))
    if (target not in pending or receipt.get('status') != 'passed' or receipt.get('new_HTTP') != 0
            or receipt.get('saved_segments') != [str(p) for p in sources]
            or receipt.get('stopped_at') != 'replay_missing_request:' + target[0] + ':' + target[1]):
        raise ReplayStop('build_recovery_probe_missing_or_mismatched')
    with exclusive_slots(RUN):
        if current_active_experiments():
            raise ReplayStop('another_CLE_experiment_is_active')
        ensure_model_call_allowed(SETTINGS['model'])
        number = len(sources) + 1
        segment = BUILD / 'execution' / f'segment_{number:03d}'
        native_output = BUILD / 'native' / f'segment_{number:03d}'
        if segment.exists() or native_output.exists():
            raise ReplayStop('build_resume_destination_exists')
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with verified_proxy_transport():
            io = physical_guard(segment, read(BUILD / 'budget.json')['budget_proposed'], direct.open,
                                resume_sources=sources, live=True)
        snapshot_sources(segment)
        record_validations(segment, 'PLT')
        arguments = recovery_arguments(read(BUILD / 'native_arguments.json')['arguments'],
                                       native_output, BUILD / 'embeddings.sqlite3')
        write_json(segment / 'state.json', {'status': 'running', 'prior_segments': [str(p) for p in sources],
                   'recovery_probe': str(probe_result), 'unknown_usage_retained': True})
        try:
            run_native(io, arguments, pending=pending, authorized_target=target)
            result = verify_native_outputs(native_output, read(RUN / 'manifest.json')['pools'])
            write_json(segment / 'native_verification.json', result)
        except BaseException as exc:
            write_json(segment / 'state.json', {'status': 'stopped_technical', 'error_type': type(exc).__name__})
            raise
        write_json(segment / 'state.json', {'status': 'completed_pending_verification'})


def sources_and_receipt():
    sources = sorted((BUILD / 'execution').glob('segment_*'))
    if not sources:
        raise ReplayStop('build_resume_without_sources')
    receipt = BUILD / 'recovery_probes' / f'after_{len(sources):03d}' / 'probe_result.json'
    return sources, receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    sources, receipt = sources_and_receipt()
    if args.action == 'probe':
        with exclusive_slots(RUN):
            if current_active_experiments():
                raise ReplayStop('another_CLE_experiment_is_active')
            if receipt.exists():
                for source in sources:
                    verify_source_snapshot(source)
                    verify_input_snapshot(source)
                pending = classify_sources(sources)
                result = read(receipt)
                target = result.get('pending_cell'), result.get('pending_identity')
                if (result.get('status') != 'passed' or result.get('pending_count') != len(pending)
                        or target not in pending or result.get('saved_segments') != [str(p) for p in sources]):
                    raise ReplayStop('cached_build_probe_mismatch')
            else:
                result = probe(sources, receipt.parent)
        print(json.dumps(result, ensure_ascii=False))
    elif args.action == 'launch':
        ensure_model_call_allowed(SETTINGS['model'])
        if current_active_experiments():
            print(json.dumps({'status': 'queued_behind_running_experiment'}))
            return
        if not receipt.exists() or read(receipt).get('status') != 'passed':
            raise ReplayStop('build_recovery_probe_missing')
        if not proxy_ready():
            raise ReplayStop('build_proxy_unavailable')
        with (BUILD / 'resume.stdout.log').open('a', encoding='utf-8') as out, (BUILD / 'resume.stderr.log').open('a', encoding='utf-8') as err:
            process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                'configs.cle_weekly_build_20261027.resume', 'run'], cwd=Path(__file__).resolve().parents[2],
                stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
        print(json.dumps({'status': 'launched', 'pid': process.pid}))
    else:
        resume(sources, receipt)


if __name__ == '__main__':
    main()

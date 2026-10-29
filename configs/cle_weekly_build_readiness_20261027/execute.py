"""原 CLE 建库维护入口；check 零 API，启动必须另获四 worker 分配。"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

from configs.cle_weekly_build_20261027 import execute as original, resume, replay
from configs.cle_weekly_build_20261027.process_guard import exclusive_slots
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .runtime import MODULE, HASH_SEED, runtime, active_workers, snapshot_sources


def check():
    result = original.check()
    budget = original.read(original.BUILD / 'budget.json')
    cap = budget['budget_proposed']
    frozen = {'conservative_model_and_embedding_tokens': 560398731,
              'total_physical_HTTP_attempts': 97377,
              'embedding_HTTP_attempts_included_in_total': 36792}
    if cap != frozen or not budget.get('execution_ready') or budget.get('reset_on_resume') is not False:
        result['missing'].append('unchanged_finite_execution_budget')
    result['ready'] = not result['missing']
    result.update(execution_command=MODULE + ' launch', allocated_workers_required=4,
                  observed_active=[{'pid': p['ProcessId'], 'package': p['package']} for p in active_workers()],
                  PYTHONHASHSEED=HASH_SEED)
    return result


def register(process, command):
    path = original.RUN / 'workbench_monitor/autonomy/registered_workers.json'
    prior = original.read(path) if path.exists() else []
    write_json(path, prior + [{'pid': process.pid, 'package': 'BUILD_C41', 'workers': 4, 'command_marker': MODULE}])
    write_json(original.BUILD / 'launch.json', {'pid': process.pid, 'command': command,
               'PYTHONHASHSEED': HASH_SEED, 'workers': 4})


def launch(action):
    ready = check()
    if not ready['ready']:
        return {'status': 'not_ready', **ready}
    if ready['observed_active']:
        return {'status': 'queued_behind_running_experiment', 'active': ready['observed_active']}
    original.ensure_model_call_allowed(original.SETTINGS['model'])
    if not original.proxy_ready():
        return {'status': 'proxy_unavailable'}
    if action == 'run' and (original.BUILD / 'execution/segment_001').exists():
        return {'status': 'existing_segment_requires_recovery'}
    if action == 'resume':
        sources, receipt = resume.sources_and_receipt()
        if not receipt.exists() or original.read(receipt).get('status') != 'passed':
            return {'status': 'recovery_probe_required'}
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, action]
    with (original.BUILD / 'launch.stdout.log').open('a', encoding='utf-8') as out, \
         (original.BUILD / 'launch.stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=original.ROOT, stdout=out, stderr=err,
            env={**os.environ, 'PYTHONHASHSEED': HASH_SEED}, creationflags=subprocess.CREATE_NO_WINDOW)
    register(process, command)
    return {'status': 'launched', 'pid': process.pid, 'workers': 4, 'command': command}


def register_segment(path):
    index = original.BUILD / 'execution_index.json'
    previous = original.read(index).get('segments', []) if index.exists() else []
    if str(path) not in previous:
        write_json(index, {'segments': previous + [str(path)]})


def run():
    if not check()['ready']:
        raise ReplayStop('build_preparation_not_passed')
    with exclusive_slots(original.RUN), runtime():
        if active_workers():
            raise ReplayStop('another_CLE_experiment_is_active')
        with patch.object(original, 'snapshot_sources', snapshot_sources):
            register_segment(original.BUILD / 'execution/segment_001')
            original.run_exclusive()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'launch', 'run', 'probe', 'resume-launch', 'resume', 'replay'])
    parser.add_argument('--source', action='append')
    parser.add_argument('--original')
    parser.add_argument('--destination')
    args = parser.parse_args()
    if args.action == 'check':
        result = check()
    elif args.action in ('launch', 'resume-launch'):
        result = launch('run' if args.action == 'launch' else 'resume')
    else:
        if os.environ.get('PYTHONHASHSEED') != HASH_SEED:
            raise ReplayStop('set_PYTHONHASHSEED_20261027_before_native_execution_or_replay')
        sources = (resume.sources_and_receipt()[0] if args.action in ('probe', 'resume')
                   else [Path(p) for p in args.source or []])
        for source in sources:
            identity = original.read(source / 'runtime_identity.json')
            if identity.get('PYTHONHASHSEED') != HASH_SEED or identity.get('entry') != MODULE:
                raise ReplayStop('build_runtime_identity_mismatch')
        if args.action == 'resume' and not check()['ready']:
            raise ReplayStop('build_preparation_not_passed')
        with runtime():
            if args.action == 'run':
                run()
                result = {'status': 'completed_pending_verification'}
            elif args.action == 'resume':
                sources, receipt = resume.sources_and_receipt()
                register_segment(original.BUILD / 'execution' / f'segment_{len(sources) + 1:03d}')
                resume.resume(sources, receipt)
                result = {'status': 'completed_pending_verification'}
            elif args.action == 'probe':
                sys.argv = ['build_resume', 'probe']
                resume.main()
                return
            else:
                if not all((args.source, args.original, args.destination)):
                    parser.error('replay requires --source --original --destination')
                result = replay.replay(args.source, args.original, args.destination)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

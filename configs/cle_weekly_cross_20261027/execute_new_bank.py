"""Schedule the frozen V4.1/new-bank arm after its matched inputs exist."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from configs.cle_v41_relation_20261026.wiring import SETTINGS
from configs.cle_weekly_build_20261027.process_guard import exclusive_slots, current_active_experiments
from configs.cle_weekly_proxy_recovery_20261027.runner import proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .prepare import RUN, read
from .prepare_new_bank import dependencies
from .new_bank_runner import NewBankRetest

PACKAGE = RUN / 'FX_GATE/V41_C41'
ROOT = Path(__file__).resolve().parents[2]


def sources():
    index = PACKAGE / 'execution_index.json'
    return [Path(p) for p in read(index)['segments']] if index.exists() else []


def check():
    reasons = list(dependencies()['reasons'])
    if not (PACKAGE / 'inputs/protocol.json').exists():
        reasons.append('matched_inputs_not_prepared')
    tests = PACKAGE / 'offline_checks.json'
    if not tests.exists() or read(tests).get('status') != 'passed':
        reasons.append('cross_runner_offline_checks_pending')
    return {'ready': not reasons, 'reasons': reasons, 'API_calls': 0}


def execute(offline=False):
    prior = sources()
    if offline:
        if not prior or not (prior[-1] / 'summary.json').exists():
            raise ReplayStop('cross_new_bank_real_run_not_completed')
        summary = read(prior[-1] / 'summary.json')
        if summary.get('status') != 'completed' or summary.get('completed') != 596:
            raise ReplayStop('cross_new_bank_real_run_not_completed')
        result = PACKAGE / 'zero_API_replay/replay_result.json'
        if result.exists():
            return read(result)
        return NewBankRetest(prior, offline=True, destination=result.parent).execute()
    if not check()['ready']:
        raise ReplayStop('cross_new_bank_not_ready')
    if prior:
        raise ReplayStop('existing_cross_segments_require_verified_recovery')
    with exclusive_slots(RUN):
        if current_active_experiments():
            raise ReplayStop('another_CLE_experiment_is_active')
        ensure_model_call_allowed(SETTINGS['model'])
        destination = PACKAGE / 'segment_001'
        with verified_proxy_transport():
            study = NewBankRetest(destination=destination)
        write_json(PACKAGE / 'execution_index.json', {'segments': [str(destination)]})
        result = study.execute()
        write_json(PACKAGE / 'completion.json', {'status': 'awaiting_agent_analysis', 'planned': 596})
        return result


def launch():
    state = check()
    if not state['ready']:
        return {'status': 'not_ready', 'reasons': state['reasons']}
    if current_active_experiments():
        return {'status': 'queued_behind_running_experiment'}
    if sources():
        return {'status': 'existing_segments_require_verified_recovery'}
    ensure_model_call_allowed(SETTINGS['model'])
    if not proxy_ready():
        return {'status': 'proxy_unavailable'}
    with (PACKAGE / 'launch.stdout.log').open('a', encoding='utf-8') as stdout, (PACKAGE / 'launch.stderr.log').open('a', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
            'configs.cle_weekly_cross_20261027.execute_new_bank', 'run'], cwd=ROOT,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    return {'status': 'launched', 'pid': process.pid}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'launch', 'run', 'replay'])
    args = parser.parse_args()
    result = check() if args.action == 'check' else launch() if args.action == 'launch' else execute(args.action == 'replay')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

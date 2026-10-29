"""后续冻结回测消费独立K0证书；其余依赖、预算、P7、验证和锁仍用原入口。"""
import argparse
import json
import os
import subprocess
import sys
from unittest.mock import patch

from configs.cle_weekly_eval_20261027 import retest
from methods.sct_trajectory.replay_journal import write_json
from .certificate import RELATIVE, accepted

MODULE = 'configs.cle_weekly_k0_saved_feedback_20261028.continuation'
NATIVE = 'configs.cle_weekly_eval_20261027.retest'


def dependencies(original, root):
    result = original()
    if accepted(root):
        result['reasons'] = [r for r in result['reasons'] if r != 'K0_native_replay_pending']
        result['ready'] = not result['reasons']
        result['K0_replay_basis'] = 'saved_responses_and_historical_validation_feedback'
        result['K0_certificate'] = str(root / RELATIVE / 'certificate.json')
        result['K0_dynamic_validation_all_consistent'] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'launch', 'run', 'resume', 'replay'])
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    original_dependencies, original_popen = retest.dependencies, subprocess.Popen
    if args.action == 'launch':
        # 新命令标记必须纳入真实进程检查；venv父子由工作台按同实例归并。
        from tools.cle_live_workbench.app import process_inventory
        if any(MODULE in (p.get('CommandLine') or '') and ' run' in p['CommandLine']
               for p in process_inventory()):
            print(json.dumps({'status': 'already_running'}))
            return

    def popen(command, *positional, **kwargs):
        # 原launch派发的子进程继续使用同一个独立适配器，不能掉回原依赖检查。
        if isinstance(command, list) and NATIVE in command:
            command = list(command)
            command[command.index(NATIVE)] = MODULE
            command += ['--workers', str(args.workers)]
        return original_popen(command, *positional, **kwargs)

    if args.action in ('run', 'resume'):
        register = retest.RUN / 'workbench_monitor/autonomy/registered_workers.json'
        entries = retest.read(register)
        entries.append({'pid': os.getpid(), 'package': 'FQ_RETEST', 'workers': args.workers,
                        'command_marker': MODULE})
        write_json(register, entries)
    previous = sys.argv
    try:
        sys.argv = [MODULE, args.action]
        with patch.object(retest, 'dependencies', lambda: dependencies(original_dependencies, retest.RUN)), \
                patch.object(retest.FrozenRetest, 'worker_limit', args.workers), \
                patch.object(subprocess, 'Popen', popen):
            retest.main()
    finally:
        sys.argv = previous


if __name__ == '__main__':
    main()

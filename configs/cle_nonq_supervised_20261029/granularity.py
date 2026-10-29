"""由当前对话启动已冻结82题标签小批，经既有验证代理调用。"""
import argparse
import json
import subprocess
import sys

from configs.cle_weekly_reduced_20261028 import granularity as native
from configs.cle_weekly_proxy_recovery_20261027.runner import proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_nonq_supervised_20261029.granularity'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['check', 'launch', 'run'])
    args = parser.parse_args()
    protocol = native.prepare()
    cells = native.base.read(native.package_root() / 'inputs/schedule.json')
    assert protocol['planned_P7'] == len(cells) == 820
    assert len({c['task_id'] for c in cells}) == 82
    assert {c['condition'] for c in cells} == {'L0', 'L1', 'L2', 'L3', 'L4'}
    assert protocol['Q_updates'] == 0
    dep = native.dependencies()
    if not dep['ready']:
        raise ReplayStop(str(dep))
    if args.action == 'check':
        print(json.dumps({'status': 'passed', 'tasks': 82, 'units': 820, 'Q_updates': 0, 'new_HTTP': 0})); return
    if args.action == 'run':
        sys.argv = [MODULE, 'run', '--workers', '4']
        with verified_proxy_transport():
            native.main()
        return
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(native.base.wiring.SETTINGS['model'])
    ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*granularity* run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
    if subprocess.check_output(['powershell', '-NoProfile', '-Command', ps], text=True).strip():
        raise ReplayStop('existing_granularity_process')
    if not proxy_ready():
        raise ReplayStop('proxy_TLS_not_ready')
    if (native.package_root() / 'execution_index.json').exists():
        raise ReplayStop('existing_segments_require_reconciliation')
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run']
    with (native.package_root()/'supervised.stdout.log').open('a', encoding='utf-8') as out, (native.package_root()/'supervised.stderr.log').open('a', encoding='utf-8') as err:
        child = subprocess.Popen(command, cwd=native.base.ROOT, stdout=out, stderr=err,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    write_json(native.package_root()/'supervised_launch.json', {'pid': child.pid, 'command': command, 'workers': 4})
    print(json.dumps({'status': 'launched', 'pid': child.pid, 'planned': 820}))


if __name__ == '__main__':
    main()

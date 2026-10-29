"""保留首段直连超时现场，经既有验证代理恢复固定54题。"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

from . import run as bounded
from configs.cle_weekly_proxy_recovery_20261027.runner import proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_q_retest_probe_20261029.recover'


def audit():
    sources = [Path(p) for p in bounded.base.read(bounded.OUT / 'execution_index.json')['segments']]
    if len(sources) != 1:
        raise ReplayStop('this_recovery_only_audits_initial_direct_timeout_segment')
    source = sources[0]
    pending = bounded.base.unresolved_requests(sources)
    statuses = [bounded.base.read(p) for p in (source / 'wire').glob('*.status.json')]
    if len(pending) != 4 or len(statuses) != 12 or any(
        v.get('status') != 'transport_error' or v.get('http_status') is not None
        or v.get('reason_type') != 'TimeoutError' for v in statuses):
        raise ReplayStop('not_the_audited_same_type_transport_failure')
    if list((source / 'wire').glob('*.response*')):
        raise ReplayStop('saved_response_requires_reconciliation_before_reissue')
    if list((source / 'task_rows').glob('*.json')):
        raise ReplayStop('unexpected_saved_task_rows')
    return sources, pending


def probe():
    sources, pending = audit()
    bounded.configure()
    with patch.object(bounded.base, 'unresolved_requests', return_value=[]):
        study = bounded.base.FrozenRetest(sources, offline=True,
                                         destination=bounded.OUT / ('transport_prefix_probe_' + str(time.time_ns())))
        checked = []
        try:
            names = [Path(p).parents[1].name for p in pending]
            for name in names:
                study.io.reason = None
                tid, repeat = name.removeprefix('shared_initial_').split('_r')
                try:
                    study.start(study.tasks[tid], int(repeat))
                except ReplayStop as exc:
                    if not str(exc).startswith('replay_missing_request:'):
                        raise
                    checked.append(name)
                else:
                    raise ReplayStop('expected_missing_response_boundary_not_reached')
            assert len(checked) == 4
            result = {'status': 'passed', 'missing_initial_boundaries': checked,
                      'preserved_failed_HTTP': 12, 'unknown_prior_usage_retained': True,
                      'new_HTTP': 0, 'authorization': '2026-10-27 same-type network interruption reissue'}
            write_json(bounded.OUT / 'transport_recovery_audit.json', result)
            return result
        finally:
            study.embedding._db.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['probe', 'launch', 'run'])
    a = p.parse_args()
    if a.action == 'probe':
        with patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
            print(json.dumps(probe())); return
    if a.action == 'launch':
        from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
        ensure_model_call_allowed(bounded.base.wiring.SETTINGS['model'])
        if not proxy_ready():
            raise ReplayStop('proxy_TLS_not_ready')
        ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*cle_q_retest_probe_20261029* run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
        if subprocess.check_output(['powershell', '-NoProfile', '-Command', ps], text=True).strip():
            raise ReplayStop('probe_already_running')
        if bounded.base.read(bounded.OUT / 'transport_recovery_audit.json')['status'] != 'passed':
            raise ReplayStop('prefix_probe_required')
        command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run']
        with (bounded.OUT / 'stdout.log').open('a', encoding='utf-8') as out, (bounded.OUT / 'stderr_recovery.log').open('a', encoding='utf-8') as err:
            child = subprocess.Popen(command, cwd=bounded.base.ROOT, stdout=out, stderr=err,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(bounded.OUT / 'recovery_launch.json', {'pid': child.pid, 'command': command, 'workers': 4})
        print(json.dumps({'status': 'launched', 'pid': child.pid})); return
    sources, pending = audit()
    original = bounded.base.unresolved_requests
    def reconciled(paths):
        unresolved = original(paths)
        if set(unresolved) != set(pending):
            raise ReplayStop('pending_set_changed')
        return []
    with patch.object(bounded.base, 'unresolved_requests', reconciled), verified_proxy_transport():
        bounded.run(4)


if __name__ == '__main__':
    main()

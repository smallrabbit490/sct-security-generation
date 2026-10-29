"""接续 FFS 题166修复检索的已核实TLS故障，复用原流程与并发恢复实现。"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

from configs.cle_weekly_embedding_recovery_20261027 import probe as native_probe
from configs.cle_weekly_fs_embedding_recovery_20261028 import resume as recovery
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_weekly_fs_embedding_166_20261028.resume'
IDENTITY = '1b4a89e5339af6c1d473c0020925e71d50ca960935eed5310a57c19bd877e848-000001'
EVIDENCE = recovery.RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_embedding_166_attempt2'
NATIVE_PROBE = recovery.FFS / 'embedding_prefix_probe_8a88b2fcdfec4d86935580ddd471bfef/probe_result.json'


def probe():
    """只消费本次实际零API探针；源、精确失败身份和累计预算必须仍一致。"""
    info = native_probe.inspect()
    prefix = recovery.read(NATIVE_PROBE)
    if (info['pending_identity'] != IDENTITY or prefix['pending_identity'] != IDENTITY
            or prefix['status'] != 'passed' or prefix['targets'] != ['166_r1_BF']
            or prefix['new_HTTP'] != 0):
        raise ReplayStop('task166_exact_embedding_prefix_not_verified')
    sources = [Path(p) for p in info['segments']]
    records = [p for source in sources for p in
               (source / 'journals/embedding/requests').glob(IDENTITY + '.json')]
    public = info['pending_public']
    if len(records) != 1:
        raise ReplayStop('task166_expected_one_failed_embedding_record')
    row = recovery.read(records[0])
    if (row['status'] != 'failed_or_unresolved'
            or row['settings'] != {'model': 'text-embedding-3-large', 'operation': 'embedding'}
            or any(row[k] != public[k] for k in ('settings', 'prompt', 'selector'))):
        raise ReplayStop('task166_embedding_payload_changed')
    budget = recovery.read(sources[-1] / 'budget.json')
    physical = sum(len(list((source / 'wire').glob('*.request.json'))) for source in sources)
    if physical != budget['transport_attempts_including_prior']:
        raise ReplayStop('unrecorded_physical_reservation')
    if (physical >= budget['cap_HTTP'] or
            budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']):
        raise ReplayStop('physical_budget_exhausted')
    audit = {'segments': info['segments'], 'records': list(map(str, records)), 'identity': IDENTITY,
             'public': public, 'budget': {k: v for k, v in budget.items() if k != 'entries'}}
    result = {'status': 'passed', 'audit': audit, 'native_prefix': prefix,
              'native_prefix_path': str(NATIVE_PROBE), 'new_HTTP': 0}
    path = EVIDENCE / 'offline_checks.json'
    if path.exists() and recovery.read(path) != result:
        raise ReplayStop('task166_saved_probe_sources_changed')
    if not path.exists():
        write_json(path, result)
    return result


def launch():
    """按当前CIM拒绝第二个冻结评价实例；原入口仍逐请求检查时段和预算。"""
    recovery.ensure_model_call_allowed(recovery.SETTINGS['model'])
    processes = recovery.processes()
    markers = ('cle_weekly_fs', 'cle_weekly_embedding', 'cle_weekly_granularity',
               'cle_weekly_eval', 'cle_weekly_gate', 'cle_weekly_cross', 'cle_weekly_retrieval')
    if recovery.active('ffs') or any(' run' in (p.get('CommandLine') or '') and
            any(m in p['CommandLine'] for m in markers) for p in processes):
        return {'status': 'already_running'}
    registry = recovery.RUN / 'workbench_monitor/autonomy/registered_workers.json'
    entries = recovery.read(registry)
    pids = {p['ProcessId'] for p in processes}
    if sum(e['workers'] for e in entries if e['pid'] in pids) > 1:
        raise ReplayStop('three_FFS_workers_not_available')
    checked = probe()
    if not recovery.proxy_ready():
        return {'status': 'proxy_unavailable'}
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run']
    with (EVIDENCE / 'stdout.log').open('a', encoding='utf-8') as out, \
         (EVIDENCE / 'stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=recovery.ROOT, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    result = {'status': 'launched', 'pid': process.pid, 'command': command, 'workers': 3,
              'prior_completed': 1419, 'probe': checked['native_prefix']}
    write_json(EVIDENCE / 'launch.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    recovery.IDENTITY, recovery.EVIDENCE, recovery.MODULE = IDENTITY, EVIDENCE, MODULE
    recovery.probe = probe
    result = {'probe': probe, 'launch': launch, 'run': recovery.run}[args.action]()
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

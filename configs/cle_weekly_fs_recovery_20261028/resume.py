"""修复 FFS 停止信号留下的未派发 embedding 日志；原实验源码及旧记录只读。"""
import argparse
import json
import runpy
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from configs.cle_weekly_embedding_recovery_20261027 import probe as embedding_probe
from configs.cle_weekly_proxy_recovery_20261027.runner import active, proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
FFS = RUN / 'FFS'
EVIDENCE = RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_prepared_embedding'
MODULE = 'configs.cle_weekly_fs_recovery_20261028.resume'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def install():
    """仅认可当前已观测的 prepared、无物理请求/预留的 embedding；其他拒绝保持。"""
    helper = runpy.run_path(str(FFS / 'transport_resume_stream_20261027.py'))
    sources = helper['sources']()
    classifier = helper['classify']
    pending, rejected = classifier(sources)
    if len(pending) != 1 or len(rejected) != 1:
        raise ReplayStop('expected_one_transport_and_one_undispatched_embedding')
    path = Path(rejected[0])
    prepared = read(path)
    if (path.parent.parent.name != 'embedding' or prepared.get('status') != 'prepared'
            or prepared.get('settings') != {'model': 'text-embedding-3-large', 'operation': 'embedding'}):
        raise ReplayStop('rejected_record_is_not_prepared_embedding')
    texts = json.loads(prepared['prompt'])
    wire_paths = [p for source in sources for p in (source / 'wire').glob('*.request.json')]
    for request in wire_paths:
        body = read(request)['body']
        if body.get('model') == 'text-embedding-3-large' and body.get('input') == texts:
            raise ReplayStop('prepared_embedding_has_physical_request_requires_separate_recovery')
    budget = read(sources[-1] / 'budget.json')
    if budget['transport_attempts_including_prior'] != len(wire_paths):
        raise ReplayStop('physical_reservation_without_wire_not_reconciled')
    if budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']:
        raise ReplayStop('physical_budget_exhausted')
    if len(wire_paths) >= budget['cap_HTTP']:
        raise ReplayStop('physical_budget_exhausted')

    def classified(prior):
        outstanding, reject = classifier(prior)
        # 只在内存中排除这一条已核实未派发记录，不改旧 journal/state/source_identity。
        return outstanding, [p for p in reject if Path(p) != path]

    helper['probe'].__globals__['classify'] = classified
    info = {'status': 'classified_undispatched', 'pending_cell': 'embedding',
            'pending_identity': prepared['identity'], 'pending_public': prepared,
            'segments': list(map(str, sources)), 'new_HTTP': 0}
    audit = {'segments': info['segments'], 'prepared_record': str(path),
             'prepared_identity': prepared['identity'], 'matching_physical_requests': 0,
             'unrecorded_budget_reservations': 0,
             'transport_pending': [{'cell': c, 'identity': i,
                 'records': [v['path'] for v in values]} for (c, i), values in pending.items()],
             'budget': {k: v for k, v in budget.items() if k != 'entries'},
             'old_records_modified': False, 'scientific_protocol_changed': False}
    return helper, info, audit


def probe():
    """用已有原生模型/向量探针执行真实前缀回放，网络客户端均禁用。"""
    helper, info, audit = install()
    target = EVIDENCE / 'offline_checks.json'
    if target.exists():
        saved = read(target)
        if saved['audit'] != audit:
            raise ReplayStop('saved_repair_probe_does_not_match_current_sources')
        return saved
    model = helper['probe']()
    original = embedding_probe.inspect
    embedding_probe.inspect = lambda: info
    try:
        embedding = embedding_probe.probe()
    finally:
        embedding_probe.inspect = original
    if model['status'] != 'passed' or embedding['status'] != 'passed':
        raise ReplayStop('repair_prefix_replay_not_passed')
    result = {'status': 'passed', 'model_prefix': model, 'embedding_prefix': embedding,
              'new_HTTP': model['new_HTTP'] + embedding['new_HTTP'], 'audit': audit}
    write_json(target, result)
    return result


def processes():
    command = ('Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | '
               'Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress')
    output = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                            capture_output=True, text=True, check=True).stdout
    values = json.loads(output) if output.strip() else []
    return [values] if isinstance(values, dict) else values


def launch():
    ensure_model_call_allowed(SETTINGS['model'])
    existing = processes()
    if active('ffs') or any(any(marker in (p.get('CommandLine') or '') for marker in
            (MODULE + ' run', 'cle_weekly_embedding_recovery_20261027.resume run',
             'cle_weekly_fs_20261027.embedding_resume run')) for p in existing):
        return {'status': 'already_running'}
    checked = probe()
    if not proxy_ready():
        return {'status': 'proxy_unavailable'}
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run']
    with (EVIDENCE / 'stdout.log').open('a', encoding='utf-8') as out, \
         (EVIDENCE / 'stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    registry = RUN / 'workbench_monitor/autonomy/registered_workers.json'
    entries = read(registry) if registry.exists() else []
    entries.append({'pid': process.pid, 'package': 'FFS', 'workers': 3, 'command_marker': MODULE})
    write_json(registry, entries)
    result = {'status': 'launched', 'pid': process.pid, 'command': command, 'workers': 3,
              'prior_completed': checked['model_prefix']['saved_rows'],
              'evidence': str(EVIDENCE / 'offline_checks.json'),
              'processes_before': [p for p in existing if 'cle_weekly' in (p.get('CommandLine') or '')]}
    write_json(EVIDENCE / 'launch.json', result)
    return result


def run():
    checked = probe()
    helper, info, _ = install()
    evaluate = helper['evaluate']
    original = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self.io.save('prepared_embedding_recovery', {
            'evidence': str(EVIDENCE / 'offline_checks.json'),
            'embedding_target': checked['embedding_prefix']['targets'],
            'prepared_identity': info['pending_identity'],
            'old_failure_and_unknown_usage_retained': True,
            'old_records_modified': False, 'scientific_protocol_changed': False})
        shutil.copy2(Path(__file__), self.out / 'source_bundle_external/prepared_embedding_resume.py')

    evaluate.FrozenFS.__init__ = initialize
    with verified_proxy_transport():
        sys.argv = [evaluate.__name__, 'resume', '--workers', '3']
        evaluate.main()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

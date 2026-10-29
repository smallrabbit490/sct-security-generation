"""恢复1266_r2_B0的已核实读流超时及并发停止留下的未派发向量记录。"""
import argparse
import json
import runpy
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from configs.cle_weekly_fs_recovery_20261028 import resume as prior
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RUN, FFS, ROOT = prior.RUN, prior.FFS, prior.ROOT
MODULE = 'configs.cle_weekly_fs_transport_1266_20261028.resume'
EVIDENCE = RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_transport_1266_attempt3'
CELL = '1266_r2_B0'
IDENTITY = '14d0e3861322bdb8243d9ebedc2e2b28601938f1eb8a5ada2e8a2fa3c93ef844-000001'
EMBEDDING = 'b2dc22e8923303df74adde11b0dcafb93e6aedd91949ed2fb876fc84d5321a9e-000001'
read = prior.read


def incomplete_json_stream(path):
    """实际检查HTTP200内容；完整返回、服务端错误和损坏片段均不当作缺失响应。"""
    count, content = 0, []
    for raw in Path(path).read_bytes().splitlines():
        line = raw.decode('utf-8').strip()
        if not line.startswith('data:'):
            continue
        data = line[5:].strip()
        if data == '[DONE]':
            return False
        part = json.loads(data)
        if part.get('error') or part.get('usage'):
            return False
        for choice in part.get('choices', []):
            if choice.get('finish_reason') is not None:
                return False
            if choice.get('index', 0) == 0:
                content.append(choice.get('delta', {}).get('content') or '')
        count += 1
    if not count or not ''.join(content):
        return False
    try:
        json.loads(''.join(content))
    except json.JSONDecodeError:
        return True
    return False


def observed_timeout(source, record):
    """仅认可本次确切请求：两个无返回TLS失败，随后一个无完整返回的读流超时。"""
    if source != FFS / 'segment_022' or record['identity'] != IDENTITY:
        return False
    matches = []
    for request in (source / 'wire').glob('*.request.json'):
        body = read(request).get('body', {})
        messages = body.get('messages') or []
        if body.get('model') != record['settings']['model'] or not messages:
            continue
        if messages[0].get('content') != record['prompt']:
            continue
        status = read(request.with_name(request.name.replace('.request.json', '.status.json')))
        raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
        tls = (status.get('status') == 'transport_error' and status.get('http_status') is None
               and status.get('error_type') == 'URLError'
               and status.get('reason_type') == 'SSLEOFError' and not raw.exists())
        timeout = (status.get('status') == 'response_read_error' and status.get('http_status') == 200
                   and status.get('error_type') == 'TimeoutError' and raw.exists()
                   and incomplete_json_stream(raw))
        matches.append((tls, timeout))
    return len(matches) == 3 and sum(tls for tls, _ in matches) == 2 and sum(t for _, t in matches) == 1


@lru_cache(maxsize=1)
def install():
    """仅在本进程补充故障分类；保持源、成功响应、预算和旧记录原样。"""
    helper = runpy.run_path(str(FFS / 'transport_resume_stream_20261027.py'))
    classifier = helper['classify']
    original_match = classifier.__globals__['physical_match']
    classifier.__globals__['physical_match'] = lambda source, row: (
        original_match(source, row) or observed_timeout(source, row))
    sources = helper['sources']()
    pending, rejected = classifier(sources)
    if set(pending) != {(CELL, IDENTITY)} or len(rejected) != 1:
        raise ReplayStop('expected_exact_timeout_and_undispatched_embedding')
    path = Path(rejected[0])
    prepared = read(path)
    if (path != sources[-1] / 'journals/embedding/requests' / (EMBEDDING + '.json')
            or prepared['status'] != 'prepared' or prepared['identity'] != EMBEDDING
            or prepared['settings'] != {'model': 'text-embedding-3-large', 'operation': 'embedding'}):
        raise ReplayStop('unexpected_prepared_record')
    texts = json.loads(prepared['prompt'])
    wire = [p for source in sources for p in (source / 'wire').glob('*.request.json')]
    for request in wire:
        body = read(request).get('body', {})
        if body.get('model') == 'text-embedding-3-large' and body.get('input') == texts:
            raise ReplayStop('prepared_embedding_has_physical_request')
    budget = read(sources[-1] / 'budget.json')
    if budget['transport_attempts_including_prior'] != len(wire):
        raise ReplayStop('unrecorded_physical_reservation')
    if (len(wire) >= budget['cap_HTTP'] or
            budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']):
        raise ReplayStop('physical_budget_exhausted')

    def classified(prior_sources):
        outstanding, rejected_paths = classifier(prior_sources)
        return outstanding, [p for p in rejected_paths if Path(p) != path]

    helper['probe'].__globals__['classify'] = classified
    info = {'segments': list(map(str, sources)), 'pending_identity': EMBEDDING,
            'pending_public': prepared}
    audit = {'segments': info['segments'], 'prepared_record': str(path),
             'prepared_identity': EMBEDDING, 'matching_physical_requests': 0,
             'unrecorded_budget_reservations': 0,
             'transport_pending': [{'cell': c, 'identity': i, 'records': [v['path'] for v in values]}
                                   for (c, i), values in pending.items()],
             'budget': {k: v for k, v in budget.items() if k != 'entries'},
             'old_records_modified': False, 'scientific_protocol_changed': False}
    return helper, info, audit


def probe():
    prior.install, prior.EVIDENCE = install, EVIDENCE
    return prior.probe()


def launch():
    """读取CIM识别任意题号恢复实例，仍由原入口逐请求检查时段、累计预算及锁。"""
    prior.ensure_model_call_allowed(prior.SETTINGS['model'])
    processes = prior.processes()
    markers = ('cle_weekly_fs', 'cle_weekly_embedding', 'cle_weekly_granularity',
               'cle_weekly_eval', 'cle_weekly_gate', 'cle_weekly_cross', 'cle_weekly_retrieval')
    if prior.active('ffs') or any(' run' in (p.get('CommandLine') or '') and
            any(marker in p['CommandLine'] for marker in markers) for p in processes):
        return {'status': 'already_running'}
    registry = RUN / 'workbench_monitor/autonomy/registered_workers.json'
    entries = read(registry)
    live_pids = {p['ProcessId'] for p in processes}
    if sum(e['workers'] for e in entries if e['pid'] in live_pids) > 1:
        raise ReplayStop('three_FFS_workers_not_available')
    checked = probe()
    if not prior.proxy_ready():
        return {'status': 'proxy_unavailable'}
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run']
    with (EVIDENCE / 'stdout.log').open('a', encoding='utf-8') as out, \
         (EVIDENCE / 'stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    entries.append({'pid': process.pid, 'package': 'FFS', 'workers': 3, 'command_marker': MODULE})
    write_json(registry, entries)
    result = {'status': 'launched', 'pid': process.pid, 'command': command, 'workers': 3,
              'prior_completed': checked['model_prefix']['saved_rows'],
              'probe_path': str(EVIDENCE / 'offline_checks.json')}
    write_json(EVIDENCE / 'launch.json', result)
    return result


def run():
    checked = probe()
    helper, info, _ = install()
    evaluate = helper['evaluate']
    original_init = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self.io.save('timeout_and_undispatched_recovery', {
            'evidence': str(EVIDENCE / 'offline_checks.json'),
            'model_identity': IDENTITY, 'embedding_identity': info['pending_identity'],
            'old_failure_and_unknown_usage_retained': True, 'scientific_protocol_changed': False,
            'embedding_targets': checked['embedding_prefix']['targets']})
        target = self.out / 'source_bundle_external'
        target.mkdir(parents=True, exist_ok=True)
        for path in (Path(__file__), Path(prior.__file__)):
            shutil.copy2(path, target / (path.parent.name + '_' + path.name))

    evaluate.FrozenFS.__init__ = initialize
    with prior.verified_proxy_transport():
        sys.argv = [evaluate.__name__, 'resume', '--workers', '3']
        evaluate.main()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))

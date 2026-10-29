"""仅恢复968向量TLS失败及其未派发prepared记录，不修改原实验和旧日志。"""
import argparse
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path

from configs.cle_weekly_embedding_recovery_20261027 import probe as native_probe
from configs.cle_weekly_fs_recovery_20261028.resume import processes
from configs.cle_weekly_proxy_recovery_20261027.runner import active, proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
FFS = RUN / 'FFS'
EVIDENCE = RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_embedding_c277d74f'
MODULE = 'configs.cle_weekly_fs_embedding_recovery_20261028.resume'
IDENTITY = 'c277d74fa186f72321fc6037b64d11faed4bc5eec094428383ecb88776b7fed3-000001'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def classifier():
    return runpy.run_path(str(RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'))['classify']


def inspect_sources(sources):
    """核对唯一已观测失败/未派发对；成功响应、其他故障与预算预留均不绕过。"""
    pending, rejected = classifier()(sources)
    if pending or len(rejected) != 2:
        raise ReplayStop('expected_only_failed_and_undispatched_embedding_pair')
    rows = []
    for name in rejected:
        path = Path(name)
        row = read(path)
        if (path.parent.parent.name != 'embedding' or row['identity'] != IDENTITY
                or row['settings'] != {'model': 'text-embedding-3-large', 'operation': 'embedding'}):
            raise ReplayStop('unexpected_unresolved_record')
        rows.append(row)
        source = path.parents[3]
        texts = json.loads(row['prompt'])
        matches = [p for p in (source / 'wire').glob('*.request.json')
                   if read(p).get('body', {}).get('model') == 'text-embedding-3-large'
                   and read(p)['body'].get('input') == texts]
        if row['status'] == 'prepared':
            if matches:
                raise ReplayStop('prepared_embedding_has_physical_request')
        elif row['status'] == 'failed_or_unresolved':
            if not matches:
                raise ReplayStop('failed_embedding_has_no_transport_evidence')
            for request in matches:
                status = read(request.with_name(request.name.replace('.request.json', '.status.json')))
                raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
                if (status.get('status') != 'transport_error' or status.get('http_status') is not None
                        or status.get('error_type') != 'URLError' or status.get('reason_type') != 'SSLEOFError'
                        or raw.exists()):
                    raise ReplayStop('embedding_is_not_observed_TLS_failure_without_response')
        else:
            raise ReplayStop('unexpected_unresolved_status')
    if ({row['status'] for row in rows} != {'prepared', 'failed_or_unresolved'}
            or any({k: row[k] for k in ('settings', 'prompt', 'selector')} !=
                   {k: rows[0][k] for k in ('settings', 'prompt', 'selector')} for row in rows)):
        raise ReplayStop('embedding_pair_payload_mismatch')
    budget = read(sources[-1] / 'budget.json')
    physical_count = sum(len(list((p / 'wire').glob('*.request.json'))) for p in sources)
    if physical_count != budget['transport_attempts_including_prior']:
        raise ReplayStop('unrecorded_physical_reservation')
    if (budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']
            or physical_count >= budget['cap_HTTP']):
        raise ReplayStop('physical_budget_exhausted')
    return {'segments': list(map(str, sources)), 'records': rejected, 'identity': IDENTITY,
            'public': {k: rows[0][k] for k in ('settings', 'prompt', 'selector')},
            'budget': {k: v for k, v in budget.items() if k != 'entries'}}


def probe():
    sources = [Path(p) for p in read(FFS / 'execution_index.json')['segments']]
    audit = inspect_sources(sources)
    path = EVIDENCE / 'offline_checks.json'
    if path.exists():
        checked = read(path)
        if checked['audit'] != audit:
            raise ReplayStop('saved_probe_sources_changed')
        return checked
    original = native_probe.inspect
    native_probe.inspect = lambda: {'segments': audit['segments'], 'pending_identity': IDENTITY}
    try:
        replay = native_probe.probe()
    finally:
        native_probe.inspect = original
    if replay['status'] != 'passed' or replay['targets'] != ['968_r1_BS'] or replay['new_HTTP'] != 0:
        raise ReplayStop('native_embedding_prefix_not_verified')
    result = {'status': 'passed', 'audit': audit, 'native_prefix': replay, 'new_HTTP': 0}
    write_json(path, result)
    return result


def bind_embedding(io, public):
    """只标记精确恢复请求；其他worker继续原入口，不用全局首请求顺序挡住并发。"""
    original = io.embedding
    expected = json.loads(public['prompt'])

    def embedding(texts, call):
        if texts == expected:
            io.save('authorized_embedding_boundary', {'identity': IDENTITY,
                'evidence': str(EVIDENCE / 'offline_checks.json'),
                'previous_execution_and_cost_unknown': True, 'old_records_modified': False})
        return original(texts, call)

    io.embedding = embedding


def run():
    checked = probe()
    evaluate = runpy.run_path(str(FFS / 'recover_utf8_20261027.py'))['evaluate']
    classify = classifier()
    allowed = set(checked['audit']['records'])

    def unresolved(sources):
        pending, rejected = classify(sources)
        return [*pending, *(p for p in rejected if p not in allowed)]

    evaluate.base.unresolved_requests = unresolved
    original = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        bind_embedding(self.io, checked['audit']['public'])
        self.io.save('embedding_concurrency_recovery', {'evidence': str(EVIDENCE / 'offline_checks.json'),
            'fixed_global_first_embedding_guard': True, 'scientific_protocol_changed': False})
        target = self.out / 'source_bundle_external/embedding_concurrency_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    evaluate.FrozenFS.__init__ = initialize
    with verified_proxy_transport():
        sys.argv = [evaluate.__name__, 'resume', '--workers', '3']
        evaluate.main()


def launch():
    ensure_model_call_allowed(SETTINGS['model'])
    existing = processes()
    markers = (MODULE, 'cle_weekly_embedding_recovery_20261027.resume',
               'cle_weekly_fs_20261027.embedding_resume', 'cle_weekly_fs_recovery_20261028.resume')
    if active('ffs') or any(' run' in (p.get('CommandLine') or '') and
            any(m in p['CommandLine'] for m in markers) for p in existing):
        return {'status': 'already_running'}
    checked = probe()
    if not proxy_ready():
        return {'status': 'proxy_unavailable'}
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run']
    with (EVIDENCE / 'stdout.log').open('a', encoding='utf-8') as out, \
         (EVIDENCE / 'stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    registry = RUN / 'workbench_monitor/autonomy/registered_workers.json'
    entries = read(registry)
    entries.append({'pid': process.pid, 'package': 'FFS', 'workers': 3, 'command_marker': MODULE})
    write_json(registry, entries)
    result = {'status': 'launched', 'pid': process.pid, 'command': command, 'workers': 3,
              'probe': checked['native_prefix'], 'prior_completed': 772}
    write_json(EVIDENCE / 'repaired_launch.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))

"""恢复K1题1221的已观测向量TLS断连；保留原Q顺序、响应和累计预算。"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

from configs.cle_weekly_build_20261027.recovery_plan import classify_sources
from configs.cle_weekly_full_20261027 import learn
from configs.cle_weekly_proxy_recovery_20261027.runner import active, proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from configs.cle_weekly_recovery_20261027.recover import request_identity
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_weekly_q_embedding_recovery_20261028.resume'
STAGE, POOL, CELL = 'K1', 'D_grow', 'K1_1221'
IDENTITY = '03cc54efe6ac1d7b6bc449b1f7e617bf122b3e4f7537a76176b731c08f36f93d-000001'
EVIDENCE = learn.RUN / 'workbench_monitor/autonomy/repair_evidence/Q.run_20261028T0213_attempt3'
EMBED_SETTINGS = {'model': 'text-embedding-3-large', 'operation': 'embedding'}


def processes():
    command = ('Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | '
               'Where-Object { $_.CommandLine -match "cle_weekly|cle_live_workbench" } | '
               'Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine | ConvertTo-Json -Compress')
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                            capture_output=True, text=True, check=True)
    rows = json.loads(result.stdout) if result.stdout.strip() else []
    return [rows] if isinstance(rows, dict) else rows


def inspect():
    """只接受这一条无HTTP状态、无raw的TLS失败，不豁免认证或预算故障。"""
    sources = list(map(Path, learn.read(learn.RUN / 'execution_index.json')['FQ_LEARN_' + STAGE]))
    pending = classify_sources(sources)
    if set(pending) != {('embedding', IDENTITY)}:
        raise ReplayStop('expected_only_observed_K1_1221_embedding_failure')
    public = pending[('embedding', IDENTITY)][0]
    if public['settings'] != EMBED_SETTINGS or public['selector']:
        raise ReplayStop('embedding_settings_changed')
    records = [str(p) for root in sources
               for p in (root / 'journals/embedding/requests').glob(IDENTITY + '.json')]
    physical = []
    for root in sources:
        for request in (root / 'wire').glob('*.request.json'):
            body = learn.read(request).get('body', {})
            if body.get('model') != EMBED_SETTINGS['model'] or body.get('input') != json.loads(public['prompt']):
                continue
            status = request.with_name(request.name.replace('.request.json', '.status.json'))
            raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
            item = learn.read(status)
            if (item.get('status') != 'transport_error' or item.get('http_status') is not None
                    or item.get('error_type') != 'URLError' or item.get('reason_type') != 'SSLEOFError'
                    or raw.exists()):
                raise ReplayStop('not_the_observed_TLS_failure_without_response')
            physical.append({'request': str(request), 'status': item, 'raw_exists': False})
    budget = learn.read(sources[-1] / 'budget.json')
    if (budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']
            or budget['transport_attempts_including_prior'] >= budget['cap_HTTP']):
        raise ReplayStop('physical_budget_exhausted')
    return {'stage': STAGE, 'cell': CELL, 'identity': IDENTITY, 'sources': list(map(str, sources)),
            'records': records, 'public': public, 'physical': physical,
            'state': learn.read(sources[-1] / 'state.json'),
            'summary': learn.read(sources[-1] / 'summary.json'),
            'budget': {k: v for k, v in budget.items() if k != 'entries'},
            'budget_entries': len(budget['entries']),
            'unknown_entries': sum(not isinstance(e.get('usage'), dict) for e in budget['entries'])}


def bind_boundary(io, audit):
    """允许已有模型前缀复用；首个新调用必须是精确核对过的向量输入。"""
    expected = json.loads(audit['public']['prompt'])
    pending = True
    original_request, original_embedding = io.request_for, io.embedding

    def request_for(cell):
        call = original_request(cell)

        def request(prompt):
            journal = io.journal(cell)
            identity, _ = request_identity(journal, prompt)
            if pending and journal.records.get(identity, {}).get('status') != 'completed':
                raise ReplayStop('new_model_request_before_verified_embedding')
            return call(prompt)
        return request

    def embedding(texts, call):
        nonlocal pending
        if pending:
            if texts != expected:
                raise ReplayStop('different_embedding_before_verified_pending')
            io.save('authorized_embedding_boundary', {'identity': IDENTITY, 'cell': CELL,
                'evidence': str(EVIDENCE / 'offline_checks.json'),
                'previous_execution_and_cost_unknown': True, 'old_records_modified': False})
        result = original_embedding(texts, call)
        pending = False
        return result

    io.request_for, io.embedding = request_for, embedding


@contextmanager
def runtime(audit):
    helper = runpy.run_path(str(learn.RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'))
    original_unresolved, original_stage = learn.unresolved_requests, learn.LearningStage
    allowed = set(audit['records'])

    def unresolved(sources):
        pending, rejected = helper['classify'](sources)
        return [*pending, *(p for p in rejected if p not in allowed)]

    class RecoveryStage(original_stage):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            target = self.out / 'source_bundle_external/q_embedding_resume.py'
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(Path(__file__), target)
            if self.stage == STAGE and not self.offline:
                bind_boundary(self.io, audit)

    learn.unresolved_requests, learn.LearningStage = unresolved, RecoveryStage
    try:
        yield
    finally:
        learn.unresolved_requests, learn.LearningStage = original_unresolved, original_stage


def probe():
    audit = inspect()
    path = EVIDENCE / 'offline_checks.json'
    if path.exists():
        saved = learn.read(path)
        if saved['audit'] != audit:
            raise ReplayStop('saved_probe_sources_changed')
        return saved
    with runtime(audit):
        worker = learn.LearningStage(STAGE, POOL, audit['sources'], offline=True,
                                     destination=EVIDENCE / 'prefix_probe')
        worker.rows = learn.restore_prefix(worker.cells, worker.sources, worker.bank, worker.eligibility)

        def embedding(texts):
            def forbidden(_):
                raise ReplayStop('unexpected_network')
            return worker.io.journal('embedding').wrap(lambda: forbidden, EMBED_SETTINGS)(
                json.dumps(texts, ensure_ascii=False))['vectors']

        worker.embedding._request = embedding
        try:
            worker.execute()
            stopped = 'unexpected_completion'
        except ReplayStop as exc:
            stopped = str(exc)
        journal = worker.io.journals.get(CELL)
        http = len(list((worker.out / 'wire').glob('*.request.json')))
        result = {'status': 'passed' if stopped == 'replay_missing_request:' + IDENTITY and http == 0
                  and len(worker.rows) == audit['summary']['completed'] else 'different',
                  'audit': audit, 'completed_prefix_tasks': len(worker.rows), 'pending_cell': CELL,
                  'saved_responses_consumed': len(journal.consumed) if journal else 0,
                  'stopped_at': stopped, 'new_HTTP': http,
                  'Q_covered_cards': sum(n.q_visits > 0 for n in worker.bank)}
        write_json(path, result)
        return result


def run():
    checked = probe()
    if checked['status'] != 'passed':
        raise ReplayStop('embedding_prefix_not_verified')
    with runtime(checked['audit']), verified_proxy_transport():
        learn.coordinate(resume_stage=STAGE)


def launch():
    ensure_model_call_allowed(learn.wiring.SETTINGS['model'])
    rows = processes()
    registry = learn.RUN / 'workbench_monitor/autonomy/registered_workers.json'
    entries = learn.read(registry)
    markers = [MODULE] + [e['command_marker'] for e in entries
                          if e['package'] == 'FQ_LEARN' and e['workers'] > 0]
    if active('q') or any(' run' in (r.get('CommandLine') or '')
                         and any(m in r['CommandLine'] for m in markers) for r in rows):
        return {'status': 'already_running'}
    write_json(EVIDENCE / 'processes_before.json', rows)
    checked = probe()
    if checked['status'] != 'passed':
        return {'status': 'probe_failed'}
    if not proxy_ready():
        return {'status': 'proxy_unavailable'}
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run']
    with (EVIDENCE / 'stdout.log').open('a', encoding='utf-8') as out, \
            (EVIDENCE / 'stderr.log').open('a', encoding='utf-8') as err:
        process = subprocess.Popen(command, cwd=learn.ROOT, stdout=out, stderr=err,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    entries.append({'pid': process.pid, 'package': 'FQ_LEARN', 'workers': 1, 'command_marker': MODULE})
    write_json(registry, entries)
    result = {'status': 'launched', 'pid': process.pid, 'command': command, 'workers': 1,
              'completed_prefix_tasks': checked['completed_prefix_tasks'],
              'probe': str(EVIDENCE / 'offline_checks.json'), 'started_utc': learn.now()}
    write_json(EVIDENCE / 'launch_result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))

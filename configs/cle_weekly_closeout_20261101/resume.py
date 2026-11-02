"""只接续54题Q回测或82题标签；冻结输入、已保存响应和累计预算原样消费。"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

from configs.cle_q_retest_probe_20261029 import run as q
from configs.cle_weekly_reduced_20261028 import granularity as gr
from configs.cle_weekly_proxy_recovery_20261027.runner import proxy_ready
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT = q.base.ROOT
RUN = q.base.RUN
MODULE = 'configs.cle_weekly_closeout_20261101.resume'
KINDS = {'q': (q.OUT, 540, 16), 'gr': (gr.package_root(), 820, 5)}
READ = q.base.read


def setup(kind, workers):
    if kind == 'q':
        q.configure()
        cls, dep = q.base.FrozenRetest, q.base.dependencies()
    else:
        cls, dep = gr.FrozenGranularity, gr.dependencies()
    if not dep['ready']:
        raise ReplayStop(str(dep))
    cls.worker_limit = workers
    return cls


def audit(kind):
    """区分已有成功后继与本次明确恢复的暂停请求，拒绝其他故障的隐式放行。"""
    root, planned, saved_count = KINDS[kind]
    sources = [Path(p) for p in READ(root/'execution_index.json')['segments']]
    records = [(p, READ(p)) for src in sources for p in src.glob('journals/*/requests/*.json')]
    complete = {(p.parents[1].name, x['identity']): x for p, x in records if x['status'] == 'completed'}
    pending, resolved, boundaries = [], [], []
    for p, x in records:
        if x['status'] == 'completed':
            continue
        pending.append(str(p))
        key = (p.parents[1].name, x['identity'])
        if key in complete:
            if any(x[k] != complete[key][k] for k in ('settings', 'prompt', 'selector')):
                raise ReplayStop('successful_successor_input_changed')
            resolved.append(str(p))
            continue
        # 本次恢复只覆盖10月29日用户暂停时的四条prepared请求；不泛化到新故障。
        expected_segment = 'segment_002' if kind == 'q' else 'segment_001'
        if (x['status'] != 'prepared' or p.parents[3].name != expected_segment
                or not x['started_utc'].startswith('2026-10-28T16:')
                or x['settings'] != q.base.wiring.SETTINGS):
            raise ReplayStop('unrecognized_unresolved_request:' + str(p))
        wires = []
        for wp in (p.parents[3]/'wire').glob('*.request.json'):
            w = READ(wp)
            body = w['body']
            if (body.get('model') == x['settings']['model']
                    and body.get('messages') == [{'role': 'user', 'content': x['prompt']} ]):
                status = wp.with_name(wp.name.replace('.request.json', '.status.json'))
                raw = wp.with_name(wp.name.replace('.request.json', '.response.raw'))
                data = raw.read_text(encoding='utf-8') if raw.exists() else ''
                if status.exists() or '[DONE]' in data or '"finish_reason":"stop"' in data.replace(' ', ''):
                    raise ReplayStop('response_requires_reconciliation:' + str(wp))
                wires.append(str(wp))
        if not wires:
            raise ReplayStop('pending_request_has_no_matching_wire')
        boundaries.append({'journal': key[0], 'identity': key[1], 'path': str(p), 'wire': wires})
    if len(boundaries) != 4:
        raise ReplayStop('expected_four_paused_request_boundaries')
    rows = {p.stem: READ(p) for src in sources for p in (src/'task_rows').glob('*.json')}
    if len(rows) != saved_count or len(READ(root/'inputs/schedule.json')) != planned:
        raise ReplayStop('saved_count_or_frozen_schedule_changed')
    return sources, {'status': 'audited', 'kind': kind, 'planned': planned,
        'saved_cells': saved_count, 'resolved_old_failures': resolved,
        'authorized_pause_boundaries': boundaries, 'pending_paths': pending,
        'authorization': '2026-11-01 user explicitly restored the two registered batches and their analysis',
        'prior_execution_and_usage': 'unknown for interrupted requests; retained in original wire and cumulative budget',
        'source_segments': [str(p) for p in sources], 'new_HTTP': 0}


@contextmanager
def reconciled(approved):
    original = q.base.unresolved_requests
    def check(paths):
        found = original(paths)
        if set(found) != set(approved):
            raise ReplayStop('pending_set_changed')
        return []
    with patch.object(q.base, 'unresolved_requests', check):
        yield


def probe(kind):
    root, _, _ = KINDS[kind]
    sources, evidence = audit(kind)
    target = root/'resume_20261101/prefix_probe'
    receipt = target/'prefix_result.json'
    if receipt.exists():
        old = READ(receipt)
        if old.get('audit') == evidence and old['status'] == 'passed':
            return old
        raise ReplayStop('existing_probe_does_not_match_current_sources')
    cls = setup(kind, 1)
    with reconciled(evidence['pending_paths']), patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
        study = cls(sources, offline=True, destination=target)
        replayed, boundaries = [], []
        try:
            cells = {c['cell_id']: c for c in study.cells}
            for c in study.cells:
                if c['cell_id'] not in study.saved_rows:
                    continue
                start = study.start(study.tasks[c['task_id']], c['repeat'])
                actual = study.one(c, start)
                old = study.saved_rows[c['cell_id']]
                if any(actual['final'].get(k) != old['final'].get(k) for k in ('code','functional','security','joint','measured')):
                    raise ReplayStop('saved_native_result_differs:' + c['cell_id'])
                replayed.append(c['cell_id'])
            for b in evidence['authorized_pause_boundaries']:
                study.io.reason = None
                c = cells[b['journal']]
                start = study.start(study.tasks[c['task_id']], c['repeat'])
                try:
                    study.one(c, start)
                except ReplayStop as exc:
                    if str(exc) != 'replay_missing_request:' + b['identity']:
                        raise
                    boundaries.append(b['journal'])
                else:
                    raise ReplayStop('expected_pending_boundary_not_reached')
            result = {'status':'passed', 'audit':evidence, 'replayed_cells':len(replayed),
                'exact_missing_boundaries':boundaries, 'new_HTTP':0}
            write_json(receipt, result)
            return result
        finally:
            study.embedding._db.close()


def run(kind, workers):
    """新段只补剩余单元；完成后零API回放和数值分析，不触发全量或新增学习。"""
    import msvcrt
    root, _, _ = KINDS[kind]
    sources, evidence = audit(kind)
    checked = READ(root/'resume_20261101/prefix_probe/prefix_result.json')
    if checked.get('status') != 'passed' or checked['audit'] != evidence:
        raise ReplayStop('exact_prefix_probe_required')
    cls = setup(kind, workers)
    with (root/'execution.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            with reconciled(evidence['pending_paths']), verified_proxy_transport():
                target = root/f'segment_{len(sources)+1:03d}'
                study = cls(sources, destination=target)
                shutil.copy2(__file__, target/'resume_entry_20261101.py')
                write_json(target/'resume_authorization.json', evidence)
                write_json(root/'execution_index.json', {'segments':[str(p) for p in sources]+[str(target)]})
                study.execute()
            # 已成功的所有来源可由同一原生消费者回放；旧失败保留并按审查清单排除。
            sources.append(target)
            replay = root/'zero_API_replay'
            if not (replay/'replay_result.json').exists():
                with reconciled(evidence['pending_paths']), patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
                    cls(sources, offline=True, destination=replay).execute()
            from .analysis import analyze
            analyze(kind)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def launch(kind, workers):
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(q.base.wiring.SETTINGS['model'])
    root = KINDS[kind][0]
    ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    text = subprocess.check_output(['powershell','-NoProfile','-Command',ps],text=True)
    procs = json.loads(text) if text.strip() else []
    if isinstance(procs,dict): procs=[procs]
    for p in procs:
        c=p.get('CommandLine') or ''
        if (' run' in c or ' resume' in c) and ('cle_q_retest_probe_' in c or 'cle_nonq_supervised_' in c or 'cle_weekly_reduced_' in c or MODULE in c):
            if MODULE not in c or '--kind '+kind in c:
                raise ReplayStop('existing_experiment_process')
    # 固定两个各2worker，不与旧工作台自动队列并开。
    if workers != 2:
        raise ReplayStop('weekly_allocation_is_two_workers_per_batch')
    if not proxy_ready():
        raise ReplayStop('proxy_TLS_not_ready')
    if probe(kind)['status'] != 'passed':
        raise ReplayStop('prefix_probe_required')
    command=[sys.executable,'-B','-X','utf8','-m',MODULE,'run','--kind',kind,'--workers',str(workers)]
    folder=root/'resume_20261101'
    with (folder/'stdout.log').open('a',encoding='utf-8') as out, (folder/'stderr.log').open('a',encoding='utf-8') as err:
        child=subprocess.Popen(command,cwd=ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    result={'status':'launched','kind':kind,'pid':child.pid,'workers':workers,'command':command}
    write_json(folder/'launch.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['audit','probe','launch','run'])
    p.add_argument('--kind',choices=KINDS,required=True)
    p.add_argument('--workers',type=int,default=2)
    a=p.parse_args()
    if a.action=='run': run(a.kind,a.workers); return
    result=audit(a.kind)[1] if a.action=='audit' else probe(a.kind) if a.action=='probe' else launch(a.kind,a.workers)
    print(json.dumps({k:v for k,v in result.items() if k not in ('audit','pending_paths','resolved_old_failures','authorized_pause_boundaries')},ensure_ascii=False))


if __name__=='__main__': main()

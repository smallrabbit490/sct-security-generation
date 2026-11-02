"""接续11月1日两个固定小批的TLS故障；成功前缀复用，旧记录和预算保留。"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
from unittest.mock import patch

from . import resume as original
from configs.cle_weekly_q_tls12_20261028.resume import tls12_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT, RUN, READ = original.ROOT, original.RUN, original.READ
MODULE = 'configs.cle_weekly_closeout_20261101.recover_tls'


def network_failure(record, wires):
    """只放行有物理证据的无HTTP状态连接失败；成功或其他故障不能当作TLS重发。"""
    diagnostics = record.get('diagnostics', [])
    if not diagnostics or any(d.get('category') != 'network_error' for d in diagnostics):
        raise ReplayStop('not_an_authorized_network_failure')
    if not wires:
        raise ReplayStop('missing_physical_network_failure_evidence')
    for wire, status, raw in wires:
        if (status.get('status') != 'transport_error' or status.get('http_status') is not None
                or status.get('error_type') not in ('URLError','SSLError','SSLEOFError',
                    'ConnectionResetError','TimeoutError','RemoteDisconnected','ConnectionAbortedError')):
            raise ReplayStop('HTTP_or_nontransport_failure_requires_diagnosis:' + str(wire))
        if raw:
            raise ReplayStop('physical_response_requires_reconciliation:' + str(wire))


def audit(kind):
    root, planned, _ = original.KINDS[kind]
    sources = [Path(p) for p in READ(root/'execution_index.json')['segments']]
    records = [(p, READ(p)) for src in sources for p in src.glob('journals/*/requests/*.json')]
    complete = {}
    for path, record in records:
        if record['status'] == 'completed':
            key = (path.parents[1].name, record['identity'])
            if key in complete and complete[key]['response'] != record['response']:
                raise ReplayStop('conflicting_completed_response')
            complete[key] = record
    wire_cache = {}
    pending, resolved, boundaries = [], [], []
    for path, record in records:
        if record['status'] == 'completed':
            continue
        pending.append(str(path))
        key = (path.parents[1].name, record['identity'])
        if key in complete:
            if any(record[k] != complete[key][k] for k in ('settings','prompt','selector')):
                raise ReplayStop('successful_successor_inputs_differ')
            resolved.append(str(path))
            continue
        if record['settings'] != original.q.base.wiring.SETTINGS or record['status'] != 'failed_or_unresolved':
            raise ReplayStop('unrecognized_pending_request:' + str(path))
        segment = path.parents[3]
        if segment not in wire_cache:
            wire_cache[segment] = [(p, READ(p)) for p in (segment/'wire').glob('*.request.json')]
        start = datetime.fromisoformat(record['started_utc'])
        matching = []
        for wp, wire in wire_cache[segment]:
            body = wire['body']
            seconds = (datetime.fromisoformat(wire['started_utc'])-start).total_seconds()
            if not 0 <= seconds <= record['elapsed_seconds']+1:
                continue
            if body.get('model') != record['settings']['model'] or body.get('messages') != [{'role':'user','content':record['prompt']}]:
                continue
            status = wp.with_name(wp.name.replace('.request.json','.status.json'))
            raw = wp.with_name(wp.name.replace('.request.json','.response.raw'))
            matching.append((wp, READ(status) if status.exists() else {}, raw.read_bytes() if raw.exists() else b''))
        network_failure(record, matching)
        boundaries.append({'journal':key[0], 'identity':key[1], 'path':str(path),
                           'wire':[str(p) for p,_,_ in matching]})
    rows = {}
    for src in sources:
        for path in (src/'task_rows').glob('*.json'):
            row = READ(path)
            if path.stem in rows and rows[path.stem] != row:
                raise ReplayStop('conflicting_saved_cell')
            rows[path.stem] = row
    schedule = READ(root/'inputs/schedule.json')
    if len(schedule) != planned or not set(rows) <= {c['cell_id'] for c in schedule}:
        raise ReplayStop('fixed_batch_manifest_changed')
    return sources, dict(status='audited',kind=kind,planned=planned,saved_cells=len(rows),
        source_segments=list(map(str,sources)), pending_paths=pending,
        resolved_old_failures=resolved, authorized_transport_boundaries=boundaries,
        authorization='2026-11-01 user: repair both TLS interruptions, resume saved prefixes, retain failures and unknown usage',
        prior_execution_and_usage='unknown retained; no assertion that failed HTTP was free', new_HTTP=0)


def probe(kind):
    root = original.KINDS[kind][0]
    sources, evidence = audit(kind)
    target = root/f'TLS_recovery_20261101/prefix_after_segment_{len(sources):03d}'
    receipt = target/'prefix_result.json'
    if receipt.exists():
        old = READ(receipt)
        if old.get('audit') == evidence and old.get('status') == 'passed':
            return old
        raise ReplayStop('existing_probe_does_not_match_current_sources')
    cls = original.setup(kind,1)
    with original.reconciled(evidence['pending_paths']), patch('socket.socket.connect',side_effect=ReplayStop('offline_network_forbidden')):
        study = cls(sources,offline=True,destination=target)
        replayed, boundaries = [], []
        try:
            cells = {c['cell_id']:c for c in study.cells}
            for cell in study.cells:
                if cell['cell_id'] not in study.saved_rows:
                    continue
                start = study.start(study.tasks[cell['task_id']],cell['repeat'])
                actual = study.one(cell,start)
                saved = study.saved_rows[cell['cell_id']]
                if any(actual['final'].get(k) != saved['final'].get(k) for k in ('code','functional','security','joint','measured')):
                    raise ReplayStop('native_saved_result_differs:' + cell['cell_id'])
                replayed.append(cell['cell_id'])
            for boundary in evidence['authorized_transport_boundaries']:
                study.io.reason = None
                cell = cells[boundary['journal']]
                start = study.start(study.tasks[cell['task_id']],cell['repeat'])
                try:
                    study.one(cell,start)
                except ReplayStop as exc:
                    if str(exc) != 'replay_missing_request:' + boundary['identity']:
                        raise
                    boundaries.append(boundary['journal'])
                else:
                    raise ReplayStop('exact_missing_boundary_not_reached')
            result = dict(status='passed',audit=evidence,replayed_cells=len(replayed),
                          exact_missing_boundaries=boundaries,new_HTTP=0)
            write_json(receipt,result)
            return result
        finally:
            study.embedding._db.close()


def ready_tls12():
    """仅握手，不发模型请求、不读取密钥；证书链和主机名照常校验。"""
    with socket.create_connection(('127.0.0.1',7897),timeout=8) as sock:
        sock.sendall(b'CONNECT api.chatanywhere.org:443 HTTP/1.1\r\nHost: api.chatanywhere.org:443\r\n\r\n')
        reply=b''
        while b'\r\n\r\n' not in reply and len(reply)<4096:
            chunk=sock.recv(1024)
            if not chunk: raise ReplayStop('proxy_CONNECT_closed')
            reply+=chunk
        if b' 200 ' not in reply.split(b'\r\n',1)[0]: raise ReplayStop('proxy_CONNECT_failed')
        ctx=ssl.create_default_context()
        ctx.minimum_version=ctx.maximum_version=ssl.TLSVersion.TLSv1_2
        with ctx.wrap_socket(sock,server_hostname='api.chatanywhere.org') as tls:
            return dict(status='passed',TLS=tls.version(),certificate_validation=True,model_HTTP=0)


def finish(kind, sources, evidence):
    root = original.KINDS[kind][0]
    cls = original.setup(kind,2)
    destination = root/f'zero_API_replay_after_segment_{len(sources):03d}'
    certificate = destination/'replay_result.json'
    if not certificate.exists():
        with original.reconciled(evidence['pending_paths']), patch('socket.socket.connect',side_effect=ReplayStop('offline_network_forbidden')):
            cls(sources,offline=True,destination=destination).execute()
    replay = READ(certificate)
    if replay.get('status') != 'passed' or replay.get('completed') != original.KINDS[kind][1]:
        raise ReplayStop('native_full_replay_not_passed')
    # 固定小批的标准回放位置只登记实际通过的完整回放，不从文件存在推断通过。
    write_json(root/'zero_API_replay/replay_result.json',{**replay,'source':str(certificate)})
    from .analysis import analyze
    summary = analyze(kind)
    write_json(root/'TLS_recovery_20261101/completion.json',dict(status='numeric_analysis_completed',
        completed=summary['completed'],planned=summary['planned'],
        case_review_status=summary.get('case_review_status'),completed_utc=datetime.now(timezone.utc).isoformat()))


def run(kind,workers):
    import msvcrt
    root = original.KINDS[kind][0]
    with (root/'execution.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            sources,evidence=audit(kind)
            if evidence['saved_cells']==evidence['planned']:
                finish(kind,sources,evidence);return
            checked=probe(kind)
            if checked['audit'] != evidence: raise ReplayStop('exact_prefix_probe_changed')
            cls=original.setup(kind,workers)
            with original.reconciled(evidence['pending_paths']),tls12_transport():
                target=root/f'segment_{len(sources)+1:03d}'
                study=cls(sources,destination=target)
                shutil.copy2(__file__,target/'TLS_recovery_entry_20261101.py')
                write_json(target/'TLS_recovery_authorization.json',evidence)
                write_json(root/'execution_index.json',{'segments':list(map(str,sources))+[str(target)]})
                study.execute()
            finish(kind,sources+[target],evidence)
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def launch(kind,workers=2):
    from tools.cle_live_workbench.app import process_inventory,worker_processes
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(original.q.base.wiring.SETTINGS['model'])
    active=worker_processes(process_inventory())
    package='FQ_RETEST' if kind=='q' else 'FG_LABELS'
    if any(p['package']==package for p in active): return dict(status='already_running',kind=kind)
    if workers!=2 or sum(p['workers'] for p in active)+workers>4: raise ReplayStop('authorized_worker_allocation_exceeded')
    root=original.KINDS[kind][0]
    sources,evidence=audit(kind)
    if evidence['saved_cells']<evidence['planned']:
        ready_tls12()
        probe(kind)
    folder=root/'TLS_recovery_20261101';folder.mkdir(exist_ok=True)
    command=[sys.executable,'-B','-X','utf8','-m',MODULE,'run','--kind',kind,'--workers',str(workers)]
    with (folder/'stdout.log').open('a',encoding='utf-8') as out,(folder/'stderr.log').open('a',encoding='utf-8') as err:
        child=subprocess.Popen(command,cwd=ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    result=dict(status='launched',kind=kind,pid=child.pid,workers=workers,saved=evidence['saved_cells'],planned=evidence['planned'])
    write_json(folder/f'launch_after_segment_{len(sources):03d}.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['audit','probe','launch','run','handshake'])
    parser.add_argument('--kind',choices=original.KINDS,default='q')
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args()
    if args.action=='run': run(args.kind,args.workers);return
    result=(audit(args.kind)[1] if args.action=='audit' else probe(args.kind) if args.action=='probe' else
            ready_tls12() if args.action=='handshake' else launch(args.kind,args.workers))
    print(json.dumps({k:v for k,v in result.items() if k not in ('audit','pending_paths','resolved_old_failures','authorized_transport_boundaries')},ensure_ascii=False))


if __name__=='__main__': main()

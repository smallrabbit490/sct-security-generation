"""P3的传输修复续段：保留旧源码/43题，隔离无法排除计费的请求，不读经验。"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


SETTINGS = {'model': 'deepseek-v4.1-flash-1017', 'max_tokens': 4096,
            'thinking': 'disabled', 'temperature': 0, 'roles': ['user'], 'stream': True}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def identity(prompt, settings=SETTINGS):
    public = {'settings': settings, 'prompt': str(prompt), 'selector': False}
    key = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return key + '-000001'


def row_sources(run):
    segments=[Path(p) for p in read(run/'recovery_segments.json')] if (run/'recovery_segments.json').exists() else []
    return [run/'source_bundle/translation_work/nomemory/PLT/rows.jsonl',
            *[p/'native/PLT/rows.jsonl' for p in segments]]


def audit(run, allowed_unresolved=()):
    """只读精确请求正文：有HTTP而无完成响应的题暂停，无HTTP的熔断项可重新派发。"""
    segments=[Path(p) for p in read(run/'recovery_segments.json')] if (run/'recovery_segments.json').exists() else []
    records={}
    for base in [run,*segments]:
        for p in sorted((base/'journals/PLT/requests').glob('*.json')):
            d=read(p);old=records.get(d['identity'])
            if old and old['status']=='completed' and d['status']=='completed':
                raise ValueError('duplicate_completed_request')
            if not old or old['status']!='completed':records[d['identity']]=d
    wire_files=[p for base in [run,*segments] for p in (base/'wire/PLT').glob('*.request.json')]
    wire_prompts = {read(p)['body']['messages'][0]['content'] for p in wire_files}
    held = []
    for key, d in records.items():
        if d['status'] != 'completed' and d['prompt'] in wire_prompts:
            ids = set(re.findall(r'"task_id":\s*"([^"\n]+)"', d['prompt']))
            if len(ids) != 1:
                raise ValueError('unresolved_task_identity_not_unique')
            held.append({'task_id': ids.pop(), 'request_identity': key,
                         'reason': 'HTTP_attempt_exists_response_and_billing_unresolved'})
    old_rows = [json.loads(x) for p in row_sources(run) if p.exists()
                for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
    done = {r['task_id'] for r in old_rows}
    if len(done) != len(old_rows):
        raise ValueError('duplicate_saved_tasks')
    held_ids = {r['task_id'] for r in held if r['request_identity'] not in allowed_unresolved}
    tasks = read(run/'inputs/tasks_PLT.json')
    ready = [t for t in tasks if str(t['index']) not in done | held_ids]
    return records, {'protocol': read(run/'protocol.json')['protocol'],
        'completed_task_ids': sorted(done), 'preserved_rows': len(old_rows),
        'held_requests': held, 'eligible_task_ids': [str(t['index']) for t in ready],
        'safe_tasks': len(ready), 'historical_physical_attempts': len(wire_files),
        'no_HTTP_circuit_records': sum(d['status'] != 'completed' and d['prompt'] not in wire_prompts
                                     for d in records.values())}, ready


class RecoveryRequests:
    """精确旧响应零费用复用；新续段每条只派发一次，传输失败后队列停发。"""
    def __init__(self, prior, root, factory, *, authorized_unresolved=()):
        self.prior, self.root, self.factory = prior, Path(root), factory
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock, self.stopped = threading.Lock(), threading.Event()
        self.counts, self.used = Counter(), Counter()
        self.client = None
        self.authorized_unresolved=set(authorized_unresolved)
        self.consumed=set()
        self.expected={}
        for key,d in prior.items():
            if d['status']!='completed':continue
            ids=set(re.findall(r'"task_id":\s*"([^"\n]+)"',d.get('prompt','')))
            if len(ids)==1:self.expected.setdefault(ids.pop(),set()).add(key)

    def __call__(self, prompt):
        from methods.sct_trajectory.replay_journal import ReplayStop
        from methods.sct_trajectory.provider_policy import ModelTimeWindowError, ensure_model_call_allowed
        while not self.stopped.is_set():
            try:
                ensure_model_call_allowed(SETTINGS['model'])
                break
            except ModelTimeWindowError:
                time.sleep(30)
        public = {'settings': SETTINGS, 'prompt': str(prompt), 'selector': False}
        base = identity(prompt).rsplit('-', 1)[0]
        with self.lock:
            if self.stopped.is_set():
                raise ReplayStop('recovery_stopped_no_queued_dispatch')
            self.counts[base] += 1
            key = f'{base}-{self.counts[base]:06d}'
            old = self.prior.get(key)
            if old and old['status'] == 'completed':
                self.used['replayed'] += 1
                self.consumed.add(key)
                return old['response']
            ids=set(re.findall(r'"task_id":\s*"([^"\n]+)"',str(prompt)))
            if len(ids)==1 and self.expected.get(ids.pop(),set())-self.consumed:
                raise ReplayStop('saved_task_prefix_not_consumed_no_new_payment')
            # 审核清单已按题排除了真正未决HTTP；这里只允许已证实未派发的熔断项。
            if old and key not in self.authorized_unresolved and any(
                    d.get('category') != 'circuit_open' for d in old.get('diagnostics', [])):
                raise ReplayStop('prior_unresolved_request_not_safe_to_resubmit:' + key)
            path = self.root/(key + '.json')
            if path.exists():
                raise ReplayStop('segment_request_already_exists:' + key)
            if self.client is None:
                self.client = self.factory()
            record = {**public, 'identity': key, 'status': 'prepared',
                      'started_utc': datetime.now(timezone.utc).isoformat()}
            if key in self.authorized_unresolved:
                record['user_authorized_reissue']=True
                record['historical_failure_preserved']=True
            write(path, record)
        try:
            while True:
                try:
                    response = self.client(prompt)
                    break
                except ModelTimeWindowError:
                    time.sleep(30)
        except Exception as exc:
            self.stopped.set()
            record.update(status='failed_or_unresolved', error_type=type(exc).__name__,
                          diagnostics=getattr(exc, 'safe_diagnostics', []))
            write(path, record)
            raise ReplayStop('recovery_transport_failed_preserve_request:' + key) from None
        record.update(status='completed', response=response, finished_utc=datetime.now(timezone.utc).isoformat())
        write(path, record)
        return response


def worker(run, segment):
    """只从旧source_bundle导入P3和验证器；新增部分限传输/记录，不改解题规则。"""
    bundle = run/'source_bundle'
    sys.path.insert(0, str(bundle)); sys.path.insert(0, str(bundle/'src'))
    from methods.cle_ablation import runner
    from methods.sct_trajectory import run_closed_loop as native
    from configs.cle_model_baseline_20261024.execute import install_recorders, record_validations
    from methods.sct_trajectory.replay_journal import ReplayStop
    import urllib.request
    manifest = read(segment/'manifest.json')
    allowed=manifest.get('authorized_unresolved_requests',[])
    prior, audit_result, tasks = audit(run,allowed)
    if audit_result != manifest['audit']:
        raise ReplayStop('saved_checkpoint_changed_after_recovery_preparation')
    protocol = read(run/'protocol.json')
    if protocol['model'] != SETTINGS['model'] or protocol['workers'] != 4 or runner.arm_spec('P3').memory != 'none':
        raise ReplayStop('frozen_P3_configuration_mismatch')
    # 原生凭据加载器只在真正发送新请求时求值；不用快照中的凭据路径。
    original_factory = native._requester
    install_recorders(segment/'unused_replay','replay',Path(protocol['original_project_root']))
    spec = importlib.util.spec_from_file_location('cle_recovery_credentials',
        Path(protocol['original_project_root'])/'methods/sct_lifecycle_replay/chatanywhere_smoke.py')
    credentials = importlib.util.module_from_spec(spec); spec.loader.exec_module(credentials)
    native.load_key = credentials.load_key
    # 与原install_recorders中的真实传输参数保持一致。
    requester = RecoveryRequests(prior, segment/'journals/PLT/requests', lambda: original_factory(
        protocol['model'], 180, 4096, 4, thinking='disabled', stream=True,
        endpoint='https://api.chatanywhere.org/v1/chat/completions', hard_timeout=300, gate_wait_timeout=600),
        authorized_unresolved=allowed)
    record_validations(segment, 'PLT')
    # 只对ChatAnywhere绕过失效显式代理；默认TLS证书与主机名检查保留。
    spec = importlib.util.spec_from_file_location('methods.sct_trajectory.recovery_wire', segment/'tools/wire_recording.py')
    wire = importlib.util.module_from_spec(spec); spec.loader.exec_module(wire)
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    state = read(run/'state.json')
    state.update(status='running', stage='PLT', pid=os.getpid(), recovery_segment=str(segment),
                 held_task_ids=[x['task_id'] for x in audit_result['held_requests']
                                if x['request_identity'] not in allowed])
    state.pop('error_type', None)
    write(run/'state.json',state)
    out = segment/'native/PLT'; out.mkdir(parents=True,exist_ok=True)
    write(out/'run_metadata.json', {'protocol': protocol, 'source_bundle': str(bundle),
        'recovery_manifest': str(segment/'manifest.json'), 'task_ids': audit_result['eligible_task_ids'],
        'workers':4,'arm':'P3','memory':'none','status':'running','transport':'direct_proxy_bypass_verified_TLS'})
    rows=[]; failures=[]
    try:
        with wire.WireRecording(segment/'wire/PLT',transport=direct.open):
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures={executor.submit(runner.run_one,'PLT',task,'P3',requester,{'none':[]}):str(task['index']) for task in tasks}
                for future in as_completed(futures):
                    if future.cancelled(): continue
                    try:
                        row=future.result()
                    except ReplayStop as exc:
                        failures.append({'task_id':futures[future],'error':str(exc)})
                        requester.stopped.set()
                        for pending in futures:pending.cancel()
                        continue
                    if any(a.get('generation',{}).get('cards') or a.get('retrieval_trace') for a in row['attempts']):
                        raise ReplayStop('unexpected_memory_in_P3')
                    with (out/'rows.jsonl').open('a',encoding='utf-8') as handle:
                        handle.write(json.dumps(row,ensure_ascii=False)+'\n')
                    rows.append(row);runner.write_report(out,rows)
                    print(f"{audit_result['preserved_rows']+len(rows)}/298 saved {row['task_id']} Joint={row['attempts'][-1].get('joint')}",flush=True)
        state.update(status='stopped_technical' if failures else 'waiting_request_reconciliation',pid=None,
                     recovery_delivered=len(rows), technical_failures=failures)
        if not failures and audit_result['preserved_rows']+len(rows)==298:
            complete=[json.loads(line) for p in row_sources(run) if p.exists()
                      for line in p.read_text(encoding='utf-8').splitlines() if line.strip()]
            if len(complete)!=len({r['task_id'] for r in complete}) or len(complete)!=298:
                raise ReplayStop('final_PLT_rows_incomplete_or_duplicate')
            final=run/'final/PLT';final.mkdir(parents=True)
            order={str(t['index']):n for n,t in enumerate(read(run/'inputs/tasks_PLT.json'))}
            complete.sort(key=lambda r:order[r['task_id']])
            (final/'rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in complete),encoding='utf-8')
            runner.write_report(final,complete)
            write(final/'run_metadata.json',{'protocol':protocol,'status':'completed','rows':298,
                'row_sources':[str(p) for p in row_sources(run)],'source_bundle':str(bundle),
                'historical_failures_and_unknown_usage_preserved':True})
            state.update(status='PLT_completed_waiting_original_image',held_task_ids=[])
            state.setdefault('completed',{})['PLT']=str(final)
    except BaseException:
        state.update(status='stopped_technical',pid=None,recovery_delivered=len(rows))
        raise
    finally:
        metadata=read(out/'run_metadata.json')
        metadata.update(status=state['status'],rows=len(rows))
        write(out/'run_metadata.json',metadata)
        write(segment/'result.json',{'delivered':len(rows),'failed':failures,
            'held':[r for r in audit_result['held_requests'] if r['request_identity'] not in allowed],
            'authorized_unresolved_requests':allowed,
            'replayed_requests':requester.used['replayed'],'card_generation':0,'embedding':0,'Q_updates':0})
        write(run/'state.json',state)


def launch(run, project, *, complete_held=False):
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(SETTINGS['model'])
    expected='waiting_request_reconciliation' if complete_held else 'stopped_technical'
    if read(run/'state.json')['status'] != expected:
        raise SystemExit('recovery_requires_saved_technical_stop')
    if not read(run/'PLT_first_two_gate.json')['passed']:
        raise SystemExit('original_first_two_gate_not_passed')
    allowed=[]
    if complete_held:
        _,pending,_=audit(run)
        if pending['preserved_rows']!=290 or len(pending['held_requests'])!=8:
            raise SystemExit('expected_290_completed_and_8_held')
        allowed=[x['request_identity'] for x in pending['held_requests']]
    prior, check, tasks = audit(run,allowed)
    if not tasks: raise SystemExit('no_safe_new_tasks')
    segment=run/('recovery_20261025_002' if complete_held else 'recovery_20261025_001')
    segment.mkdir()  # 已存在就拒绝，绝不覆盖或重发旧续段。
    write(segment/'previous_state.json',read(run/'state.json'))
    write(segment/'manifest.json',{'audit':check,'transport':'same_org_endpoint; bypass_explicit_proxy; verified_TLS',
        'method_change':False,'rules':'frozen original P3; max2 attempts; first Joint early stop; workers4',
        'remaining_HTTP_uncertain_tasks':'user explicitly authorized eight-task reissue; historical records retained' if complete_held else 'held; do not resubmit until reconciled',
        'authorized_unresolved_requests':allowed,
        'authorization':'2026-10-25 user: remaining eight directly rerun by original rules; preserve failures and unknown usage' if complete_held else None})
    for source in (Path(__file__),project/'methods/sct_trajectory/wire_recording.py'):
        target=segment/'tools'/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    segments=read(run/'recovery_segments.json') if (run/'recovery_segments.json').exists() else []
    write(run/'recovery_segments.json',[*segments,str(segment)])
    flags=(subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
    cmd=[sys.executable,'-B','-X','utf8',str(segment/'tools/resume_plt.py'),'worker',
         '--run-root',str(run),'--segment',str(segment)]
    with (segment/'stdout.log').open('ab') as out,(segment/'stderr.log').open('ab') as err:
        proc=subprocess.Popen(cmd,cwd=run/'source_bundle',stdout=out,stderr=err,creationflags=flags)
    write(segment/'launch.json',{'pid':proc.pid,'command':cmd})
    print(json.dumps({'pid':proc.pid,'eligible_tasks':len(tasks),'held_tasks':len(check['held_requests']),
                     'preserved':check['preserved_rows'],'segment':str(segment)}))


def replay(run):
    """合并旧段和续段的已保存响应，重新执行原生P3及测试；禁止模型网络和凭据读取。"""
    bundle=run/'source_bundle'
    sys.path.insert(0,str(bundle));sys.path.insert(0,str(bundle/'src'))
    from methods.cle_ablation import runner
    from methods.sct_trajectory import run_closed_loop as native
    from methods.sct_trajectory.replay_journal import ReplayStop
    import urllib.request
    def forbidden(*a,**k):raise ReplayStop('replay_network_and_credentials_forbidden')
    urllib.request.urlopen=native.load_key=forbidden
    segments=[Path(p) for p in read(run/'recovery_segments.json')]
    sources=[run/'source_bundle/translation_work/nomemory/PLT/rows.jsonl',
             *[p/'native/PLT/rows.jsonl' for p in segments]]
    old={}
    for path in sources:
        if not path.exists():continue
        for line in path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if row['task_id'] in old:raise ReplayStop('duplicate_delivered_task')
            old[row['task_id']]=row
    records={}
    for base in [run,*segments]:
        for path in (base/'journals/PLT/requests').glob('*.json'):
            d=read(path)
            if d['status']!='completed':continue
            if d['identity'] in records:raise ReplayStop('duplicate_completed_response')
            records[d['identity']]=d
    counts=Counter();lock=threading.Lock()
    def saved(prompt):
        base=identity(prompt).rsplit('-',1)[0]
        with lock:
            counts[base]+=1;key=f'{base}-{counts[base]:06d}'
        if key not in records:raise ReplayStop('missing_saved_response:'+key)
        return records[key]['response']
    tasks=[t for t in read(run/'inputs/tasks_PLT.json') if str(t['index']) in old]
    parent=run/'replay_results';parent.mkdir(exist_ok=True)
    out=parent/f'combined_{len(old)}'
    out.mkdir()  # 每次已交付集合仅做一次，避免覆盖回放差异。
    rows=[]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures=[executor.submit(runner.run_one,'PLT',t,'P3',saved,{'none':[]}) for t in tasks]
        for future in as_completed(futures):
            row=future.result();rows.append(row)
            with (out/'rows.jsonl').open('a',encoding='utf-8') as handle:
                handle.write(json.dumps(row,ensure_ascii=False)+'\n')
    def view(row):
        return [{k:a.get(k) for k in ('code','functional','security','joint','measured')} for a in row['attempts']]
    differences=[r['task_id'] for r in rows if view(r)!=view(old[r['task_id']])]
    result={'tasks':len(rows),'API_calls':0,'credential_reads':0,'differences':differences,
            'same_code_and_measurement':not differences,'row_sources':[str(p) for p in sources]}
    write(out/'summary.json',result)
    print(json.dumps(result,ensure_ascii=False))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['audit','launch','complete-held','worker','replay'])
    parser.add_argument('--run-root',type=Path,required=True);parser.add_argument('--segment',type=Path)
    args=parser.parse_args();run=args.run_root.resolve()
    if args.action=='audit': print(json.dumps(audit(run)[1],ensure_ascii=False,indent=2))
    elif args.action=='worker': worker(run,args.segment.resolve())
    elif args.action=='replay': replay(run)
    else: launch(run,Path(__file__).resolve().parents[2],complete_held=args.action=='complete-held')


if __name__=='__main__':main()

"""用户授权的Flash换模接续：保留旧成功前缀、累计预算与原生P7，显式记录混合来源。"""
import argparse
from collections import Counter
from contextlib import contextmanager, ExitStack
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
from unittest.mock import patch

from . import resume as prior
from .recover_tls import ready_tls12
from configs.cle_weekly_q_tls12_20261028.resume import tls12_transport
from configs.cle_v41_relation_20261026.execution import StudyExecution
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT,RUN,READ=prior.ROOT,prior.RUN,prior.READ
OLD='deepseek-v4.1-flash-1017'
MODEL='deepseek-v4.1-flash'
MODULE='configs.cle_weekly_closeout_20261101.switch_flash'
OLD_SETTINGS={**prior.q.base.wiring.SETTINGS,'model':OLD}
SETTINGS={**OLD_SETTINGS,'model':MODEL}
EMBEDDING_SETTINGS={'model':'text-embedding-3-large','operation':'embedding'}


def root_for(kind):return prior.KINDS[kind][0]
def switch_dir(kind):return root_for(kind)/'model_switch_flash_20261101'


def completed_rows(sources):
    rows,paths={},{}
    for source in sources:
        for path in (source/'task_rows').glob('*.json'):
            row=READ(path);key=row['cell_id']
            if key in rows and rows[key]!=row:raise ReplayStop('conflicting_saved_cell')
            rows[key],paths[key]=row,path
    return rows,paths


def prepare(kind):
    """固定换模时点的完成集合；仅新增独立换模登记，不改旧协议、请求和成绩。"""
    out=switch_dir(kind);file=out/'manifest.json'
    if file.exists():return READ(file)
    root=root_for(kind);sources=[Path(p) for p in READ(root/'execution_index.json')['segments']]
    rows,_=completed_rows(sources);schedule=READ(root/'inputs/schedule.json')
    expected={'q':227,'gr':247}[kind]
    if len(rows)!=expected or len(schedule)!=prior.KINDS[kind][1]:raise ReplayStop('model_switch_prefix_changed')
    baseline=READ(sources[-1]/'budget.json')
    manifest=dict(status='prepared',kind=kind,old_model=OLD,new_model=MODEL,
        authorization='2026-11-01 user explicitly authorized both batches to continue on deepseek-v4.1-flash with model-separated analysis',
        authorized_utc=datetime.now(timezone.utc).isoformat(),
        planned=len(schedule),completed_before_switch=len(rows),old_completed_cell_ids=sorted(rows),
        remaining_cell_ids=[c['cell_id'] for c in schedule if c['cell_id'] not in rows],
        old_source_segments=list(map(str,sources)),base_settings=OLD_SETTINGS,effective_settings=SETTINGS,
        native_input_identity=READ(sources[-1]/'input_identity.json'),
        original_budget_caps={k:baseline[k] for k in ('cap_tokens','cap_HTTP','cap_embedding_HTTP')},
        cost_at_switch={k:baseline[k] for k in ('known_reported_tokens','transport_attempts_including_prior')},
        cost_unknown_at_switch=sum(e['status']!='reported' for e in baseline['entries']),
        analysis_rule='old-only, flash-only and mixed saved-prefix outcomes separately; paired comparisons never join different cohorts',
        full_queue_dispatch=False)
    out.mkdir(exist_ok=False)
    write_json(file,manifest)
    return manifest


def digest_request(prompt,settings,selector):
    public={'settings':settings,'prompt':str(prompt),'selector':selector}
    return hashlib.sha256(json.dumps(public,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def stable_prompt(value):return re.sub(r'case_[A-Za-z0-9_]+(?=[/\\]+worker\.py)','case_<temporary>',value)


def legacy_match(journal,prompt):
    """只复用逐字相同的成功旧响应；临时worker路径沿用原回放的归一化规则。"""
    selector=type(prompt).__name__=='SelectorPrompt'
    key=digest_request(prompt,SETTINGS,selector)
    number=journal.counts[key]+1
    current=f'{key}-{number:06d}'
    if current in journal.records:return None
    old=f'{digest_request(prompt,OLD_SETTINGS,selector)}-{number:06d}'
    record=journal.records.get(old)
    if record and old not in journal.consumed and record.get('status')=='completed':return old
    matches=[identity for identity in journal.prior-journal.consumed
        if journal.records[identity]['settings']==OLD_SETTINGS
        and journal.records[identity]['selector']==selector
        and stable_prompt(journal.records[identity]['prompt'])==stable_prompt(str(prompt))]
    if len(matches)==1:return matches[0]
    return None


@contextmanager
def runtime(kind,workers):
    """只覆盖本进程的模型及明确旧响应桥接；冻结源文件、输入和验证规则不变。"""
    from configs.cle_v41_relation_20261026 import wiring,execution
    from methods.sct_trajectory import run_closed_loop,replay_journal,provider_policy
    cls=prior.setup(kind,workers)
    init=StudyExecution.__init__;request_for=StudyExecution.request_for
    allowed=provider_policy.ensure_model_call_allowed
    def gate(model,now=None):return allowed(OLD if model==MODEL else model,now=now)
    def initialize(self,root,protocol,schedule,*args,**kwargs):
        effective=copy.deepcopy(protocol)
        effective.update(model_settings=SETTINGS,model_change_authorization=str(switch_dir(kind)/'manifest.json'),
            base_protocol=protocol['protocol'],effective_protocol=protocol['protocol']+'-flash-model-switch-20261101',
            mixed_prefixes_explicit=True)
        init(self,root,effective,schedule,*args,**kwargs)
        self.model_request_lineage={}
    def request(self,identity):
        native=request_for(self,identity);journal=self.journal(identity)
        def call(prompt):
            with journal.lock:
                old=legacy_match(journal,prompt)
                if old:
                    record=journal.records[old]
                    key=digest_request(prompt,SETTINGS,type(prompt).__name__=='SelectorPrompt')
                    journal.counts[key]+=1;journal.consumed.add(old)
                    response=copy.deepcopy(record['response'])
                else:response=None
            if old is None:response=native(prompt)
            entry=dict(request_model=OLD if old else MODEL,reported_model=response.get('model'),
                reused_legacy_response=old is not None,legacy_identity=old)
            with self.lock:self.model_request_lineage.setdefault(identity,[]).append(entry)
            return response
        return call
    with ExitStack() as stack:
        stack.enter_context(patch.object(wiring,'SETTINGS',SETTINGS))
        for mod in (provider_policy,execution,run_closed_loop,replay_journal):
            stack.enter_context(patch.object(mod,'ensure_model_call_allowed',gate))
        stack.enter_context(patch.object(StudyExecution,'__init__',initialize))
        stack.enter_context(patch.object(StudyExecution,'request_for',request))
        yield type('FlashContinuation',(ModelLineage,cls),{'switch_kind':kind})


class ModelLineage:
    """仅增加运行模型来源与分层统计；实际生成、选卡、验证仍由原类执行。"""
    def start(self,task,repeat):
        key=f'{task["index"]}_r{repeat}'
        origin=next((p for p in reversed(self.sources) if (p/'shared_starts'/(key+'.json')).exists()),None)
        value=super().start(task,repeat)
        if origin:
            evidence=READ(origin/'shared_start_model_lineage'/(key+'.json')) if (origin/'shared_start_model_lineage'/(key+'.json')).exists() else {'models':[OLD],'source':str(origin)}
        else:
            items=[v for identity,entries in self.io.model_request_lineage.items()
                   if identity in ('shared_initial_'+key,'shared_selection_'+key) for v in entries]
            evidence={'models':sorted({v['reported_model'] for v in items}),'source':str(self.out)}
        self.io.save('shared_start_model_lineage/'+key,evidence)
        return value

    def decorate_row(self,row,cell):
        super().decorate_row(row,cell)
        key=f'{cell["task_id"]}_r{cell["repeat"]}'
        shared=READ(self.out/'shared_start_model_lineage'/(key+'.json'))
        requests=self.io.model_request_lineage.get(cell['cell_id'],[])
        models=set(shared['models'])|{v['reported_model'] for v in requests}
        cohort='1017_only' if models=={OLD} else 'flash_only' if models=={MODEL} else 'mixed_saved_prefix'
        row.update(execution_model=MODEL,model_cohort=cohort,response_models=sorted(models),
                   shared_start_model_lineage=shared,request_model_lineage=copy.deepcopy(requests),
                   model_switch_authorization=str(switch_dir(self.switch_kind)/'manifest.json'))

    def checkpoint(self,status):
        summary=super().checkpoint(status)
        groups={}
        for row in self.rows:
            cohort=row.get('model_cohort','1017_only')
            group=groups.setdefault(cohort,{'completed':0,'measured':0,'functional':0,'security':0,'joint':0,'arms':{}})
            arm=group['arms'].setdefault(row['condition'],dict(completed=0,measured=0,functional=0,security=0,joint=0))
            for target in (group,arm):
                target['completed']+=1
                for key in ('measured','functional','security','joint'):target[key]+=bool(row['final'].get(key))
        summary.update(model=MODEL,model_strata=groups,performance_pooling_across_models=False,
            generation_complete_count_includes_saved_1017=True)
        # arms仅供当前模型完整生成结果展示，所有来源的成绩见model_strata。
        summary['arms']=groups.get('flash_only',{}).get('arms',{})
        self.io.save('summary',summary)
        return summary


def embedding_transport_boundary(path,record):
    """核对原向量输入及无返回的网络故障，不放行证书、额度或解析错误。"""
    from datetime import timedelta
    start=datetime.fromisoformat(record['started_utc']);found=[]
    for wp in (path.parents[3]/'wire').glob('*.request.json'):
        wire=READ(wp)
        if not start<=datetime.fromisoformat(wire['started_utc'])<=start+timedelta(seconds=record['elapsed_seconds']+10):continue
        if (wire['body'].get('model')!=EMBEDDING_SETTINGS['model']
                or wire['body'].get('input')!=json.loads(record['prompt'])):continue
        raw=wp.with_name(wp.name.replace('.request.json','.response.raw'))
        status=wp.with_name(wp.name.replace('.request.json','.status.json'))
        if raw.exists() and raw.stat().st_size:raise ReplayStop('saved_embedding_response_requires_reconciliation')
        if not status.exists():raise ReplayStop('embedding_transport_status_missing')
        value=READ(status)
        network_errors={'SSLEOFError','RemoteDisconnected','ConnectionResetError','ConnectionAbortedError','BrokenPipeError','TimeoutError'}
        if not (value.get('http_status')==524 or
                (value.get('http_status') is None and value.get('status')=='transport_error'
                 and (value.get('error_type') in network_errors or value.get('reason_type') in network_errors))):
            raise ReplayStop('embedding_failure_not_authorized_transport')
        found.append(str(wp))
    if not found:raise ReplayStop('missing_wire_for_embedding_timeout')
    return {'journal':'embedding','identity':record['identity'],'source':str(path),
            'settings':record['settings'],'operation':'embedding','wire':found}


def audit(kind):
    manifest=prepare(kind);root=root_for(kind)
    sources=[Path(p) for p in READ(root/'execution_index.json')['segments']]
    rows,_=completed_rows(sources)
    records=[(p,READ(p)) for s in sources for p in s.glob('journals/*/requests/*.json')]
    success={(p.parents[1].name,v['identity']) for p,v in records if v['status']=='completed'}
    pending=[];boundaries=[]
    authorized_old=set()
    d=READ(RUN/'closeout_20261101/server_timeout_decision_required.json')
    for item in d['blocked_requests']:authorized_old.add(item['journal'])
    for path,record in records:
        if record['status']=='completed':continue
        pending.append(str(path));key=(path.parents[1].name,record['identity'])
        if key in success:continue
        if str(path) in authorized_old:
            # 换模后的成功响应或已保存整题已接续该边界；旧请求仍保持失败原状。
            replacement=digest_request(record['prompt'],SETTINGS,record['selector'])+'-'+record['identity'].rsplit('-',1)[1]
            if key[0] in rows or (key[0],replacement) in success:
                continue
            # 用户此次已明确要求换模继续这三个未完成请求，旧费用和状态不改。
            boundaries.append({'journal':key[0],'identity':record['identity'],'source':str(path),'settings':record['settings']})
        elif record['settings']==EMBEDDING_SETTINGS and record['status']=='failed_or_unresolved':
            boundaries.append(embedding_transport_boundary(path,record))
        elif record['settings']==SETTINGS and record['status']=='failed_or_unresolved':
            diag=record.get('diagnostics',[])
            if not diag or any(v.get('category') not in ('network_error','hard_timeout') and not (v.get('category')=='http_error' and v.get('http_status')==524) for v in diag):
                raise ReplayStop('nontransport_new_model_failure_requires_diagnosis')
            # 有完整或部分返回的故障须先核对保存响应，不能盲目补发。
            from datetime import timedelta
            start=datetime.fromisoformat(record['started_utc']);found=[]
            for wp in (path.parents[3]/'wire').glob('*.request.json'):
                wire=READ(wp)
                if not start<=datetime.fromisoformat(wire['started_utc'])<=start+timedelta(seconds=record['elapsed_seconds']+10):continue
                if wire['body'].get('messages')!=[{'role':'user','content':record['prompt']}]:continue
                raw=wp.with_name(wp.name.replace('.request.json','.response.raw'))
                status=wp.with_name(wp.name.replace('.request.json','.status.json'))
                if raw.exists() and raw.stat().st_size:raise ReplayStop('saved_response_requires_reconciliation')
                if status.exists() and READ(status).get('http_status') not in (None,524):raise ReplayStop('HTTP_failure_not_a_connection_timeout')
                found.append(str(wp))
            if not found:raise ReplayStop('missing_wire_for_new_model_timeout')
            boundaries.append({'journal':key[0],'identity':record['identity'],'source':str(path),'settings':record['settings']})
        else:raise ReplayStop('unexpected_unresolved_request:'+str(path))
    return sources,dict(status='audited',kind=kind,saved_cells=len(rows),planned=manifest['planned'],
        pending_paths=pending,boundaries=boundaries,source_segments=list(map(str,sources)),new_HTTP=0)


def saved_replay_count(folder,sources):
    """复用已实际执行并落盘的原生回放，不重跑其验证器，不修改旧现场。"""
    rows,_=completed_rows(sources)
    if READ(folder/'launch.json').get('offline') is not True or any((folder/'wire').glob('*')):
        raise ReplayStop('saved_prefix_is_not_zero_API_replay')
    if READ(folder/'input_identity.json')!=READ(sources[-1]/'input_identity.json'):
        raise ReplayStop('saved_prefix_inputs_changed')
    for key,old in rows.items():
        path=folder/'task_rows'/(key+'.json')
        if not path.exists():raise ReplayStop('saved_native_prefix_incomplete')
        actual=READ(path)
        if (any(actual.get(k)!=old.get(k) for k in ('cell_id','task_id','repeat','condition')) or
                any(actual['final'].get(k)!=old['final'].get(k) for k in ('code','functional','security','joint','measured'))):
            raise ReplayStop('saved_native_prefix_result_differs:'+key)
    return len(rows)


def probe(kind):
    sources,evidence=audit(kind);folder=switch_dir(kind)/f'prefix_after_{len(sources):03d}'
    file=folder/'prefix_result.json'
    if file.exists():
        result=READ(file)
        if result.get('audit')==evidence and result['status']=='passed':return result
        raise ReplayStop('model_switch_probe_sources_changed')
    reused=saved_replay_count(folder,sources) if folder.exists() else 0
    destination=folder/'missing_boundary_recovery' if folder.exists() else folder
    with runtime(kind,1) as cls,prior.reconciled(evidence['pending_paths']),patch('socket.socket.connect',side_effect=ReplayStop('offline_no_network')):
        study=cls(sources,offline=True,destination=destination)
        try:
            def replay_embedding(texts):
                def forbidden(_):raise ReplayStop('offline_no_network')
                return study.io.embedding(texts,forbidden)['vectors']
            study.embedding._request=replay_embedding
            cells={c['cell_id']:c for c in study.cells};count=reused;reached=[]
            if not reused:
                for cell in study.cells:
                    if cell['cell_id'] not in study.saved_rows:continue
                    actual=study.one(cell,study.start(study.tasks[cell['task_id']],cell['repeat']))
                    old=study.saved_rows[cell['cell_id']]
                    if any(actual['final'].get(k)!=old['final'].get(k) for k in ('code','functional','security','joint','measured')):
                        raise ReplayStop('saved_native_result_differs:'+cell['cell_id'])
                    count+=1
            for boundary in evidence['boundaries']:
                source=READ(boundary['source']);prompt=source['prompt'];settings=source['settings']
                embedding=boundary.get('operation')=='embedding'
                wanted=source['identity'] if embedding else digest_request(prompt,SETTINGS,source['selector'])+'-'+source['identity'].rsplit('-',1)[1]
                candidates=([c for c in study.cells if c['cell_id'] not in study.saved_rows
                    and any((s/'journals'/c['cell_id']).exists() for s in sources)]
                    if embedding else [cells[boundary['journal']]])
                for cell in candidates:
                    study.io.reason=None
                    try:study.one(cell,study.start(study.tasks[cell['task_id']],cell['repeat']))
                    except ReplayStop as exc:
                        if str(exc)=='replay_missing_request:'+wanted:
                            reached.append(cell['cell_id'] if embedding else boundary['journal']);break
                        if embedding and str(exc).startswith('replay_missing_request:'):continue
                        raise
                else:raise ReplayStop('expected_model_switch_boundary_not_reached')
            result=dict(status='passed',replayed_cells=count,exact_missing_boundaries=reached,audit=evidence,new_HTTP=0,
                reused_native_replay_cells=reused,replayed_cells_this_attempt=count-reused,
                native_replay_source=str(folder),boundary_probe_source=str(destination))
            write_json(file,result);return result
        finally:study.embedding._db.close()


def finish(kind,sources,evidence):
    root=root_for(kind);target=switch_dir(kind)/f'full_replay_after_{len(sources):03d}'
    cert=target/'replay_result.json'
    if not cert.exists():
        with runtime(kind,2) as cls,prior.reconciled(evidence['pending_paths']),patch('socket.socket.connect',side_effect=ReplayStop('offline_no_network')):
            cls(sources,offline=True,destination=target).execute()
    value=READ(cert)
    if value.get('status')!='passed' or value.get('completed')!=prior.KINDS[kind][1]:raise ReplayStop('full_native_replay_not_passed')
    write_json(switch_dir(kind)/'replay_result.json',{**value,'source':str(cert)})
    from .switch_analysis import analyze
    analyze(kind)


def run(kind,workers):
    import msvcrt
    root=root_for(kind)
    with (root/'execution.lock').open('r+b') as lock:
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            sources,evidence=audit(kind)
            if evidence['saved_cells']==evidence['planned']:finish(kind,sources,evidence);return
            if probe(kind)['audit']!=evidence:raise ReplayStop('exact_model_switch_probe_required')
            with runtime(kind,workers) as cls,prior.reconciled(evidence['pending_paths']),tls12_transport():
                target=root/f'segment_{len(sources)+1:03d}'
                study=cls(sources,destination=target)
                shutil.copy2(__file__,target/'model_switch_entry.py')
                write_json(target/'model_switch_manifest.json',prepare(kind))
                write_json(root/'execution_index.json',{'segments':list(map(str,sources))+[str(target)]})
                study.execute()
            finish(kind,sources+[target],evidence)
        finally:lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)


def launch(kind):
    from tools.cle_live_workbench.app import process_inventory,worker_processes
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(OLD)
    active=worker_processes(process_inventory());key='FQ_RETEST' if kind=='q' else 'FG_LABELS'
    if any(p['package']==key for p in active):return {'status':'already_running','kind':kind}
    if sum(p['workers'] for p in active)+2>4:raise ReplayStop('worker_limit_exceeded')
    ready_tls12();checked=probe(kind);folder=switch_dir(kind)
    with (folder/'stdout.log').open('a',encoding='utf-8') as out,(folder/'stderr.log').open('a',encoding='utf-8') as err:
        proc=subprocess.Popen([sys.executable,'-B','-X','utf8','-m',MODULE,'run','--kind',kind,'--workers','2'],cwd=ROOT,
            stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    result=dict(status='launched',kind=kind,pid=proc.pid,workers=2,model=MODEL,saved=checked['replayed_cells'])
    write_json(folder/f'launch_after_{len(checked["audit"]["source_segments"]):03d}.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','audit','probe','launch','run','analysis'])
    parser.add_argument('--kind',choices=('q','gr'),required=True)
    parser.add_argument('--workers',type=int,choices=(2,),default=2)
    args=parser.parse_args()
    if args.action=='run':run(args.kind,args.workers);return
    if args.action=='analysis':
        from .switch_analysis import analyze
        result=analyze(args.kind)
    else:result=prepare(args.kind) if args.action=='prepare' else audit(args.kind)[1] if args.action=='audit' else probe(args.kind) if args.action=='probe' else launch(args.kind)
    keys=('status','kind','pid','workers','model','saved','saved_cells','planned','completed','replayed_cells','exact_missing_boundaries','new_HTTP')
    print(json.dumps({k:result[k] for k in keys if k in result},ensure_ascii=False))


if __name__=='__main__':main()

"""独立MASE训练搜索入口：执行模型流程图，事后评分，再按训练净提升改下一版。

只沿用旧60个训练family；没有独立确认学习路径，不写CLE正式经验库。PLT本地验证。
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from .artifacts import Store, read_jsonl, write_json
from .blueprints import initial_graph
from .designer import propose, apply_memory_updates
from .executor import GraphExecutor, safe_error_code
from .evolution import decide
from .freeze import snapshot
from .metrics import summarize
from .operators import Operators, digest
from .views import solver_context
from .control import ControlStore, schedule_tasks

ROOT=Path(__file__).resolve().parents[2]
HISTORY=ROOT/'translation_work/diagnostics/20261009/a7_exploration'
DEFAULT_ROOT=ROOT/'translation_work/diagnostics/20261013/mase_evolution'


class ObservedSemaphore:
    """API并发监测阶段包装共享闸门；输入并发上限，输出同一闸门和观测峰值。"""
    def __init__(self, limit):
        self._semaphore=threading.BoundedSemaphore(limit)
        self._lock=threading.Lock()
        self.active=0
        self.peak=0

    def acquire(self, *args, **kwargs):
        acquired=self._semaphore.acquire(*args, **kwargs)
        if acquired:
            with self._lock:
                self.active+=1
                self.peak=max(self.peak,self.active)
        return acquired

    def release(self):
        with self._lock:
            self.active=max(0,self.active-1)
        self._semaphore.release()


def bind_snapshot(directory, name, value):
    """续跑阶段绑定实际图/记忆/公开检查的哈希；变化拒绝，避免混合版本结果。"""
    path=Path(directory)/(name+'_snapshot.json')
    signature={'sha256':digest(value)}
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=signature:
        raise ValueError('runtime_snapshot_changed_use_new_run_id')
    write_json(path,signature)


def bind_source(card, task):
    """来源质量阶段：以source_id对应真任务核对身份并重建示例；拒绝错挂证据。

    只重建其他训练family的公开来源和漏洞/补丁，不引入目标答案；不改正式库。
    """
    from methods.direction_screening.protocol import public_task
    if str(card['source_id'])!=str(task['index']) or str(card['family_id'])!=str(task['family_id']) or str(card['cwe'])!=str(task['CWE_ID']):
        raise ValueError('source_identity_mismatch')
    bound=deepcopy(card)
    truth=task['ground_truth']
    bound['patch_slice']={'before':truth.get('vulnerable_code',''),'after':truth.get('patched_code','')}
    bound['source_code_context']={'prefix':truth.get('code_before',''),'suffix':truth.get('code_after',''),
                                  'role':'source skeleton, not target environment'}
    bound['source_public']=public_task(task)
    bound['source_code_sha256']=digest({'slice':bound['patch_slice'],'context':bound['source_code_context']})
    return bound


def execute_task(task, graph, bank, requesters, suite, evaluator=None, on_event=None, timeout=1800, memory_kind='m1'):
    """解题→finish固定→旁路逐候选评分；真实节点事件/缺测均保存，目标答案只在评分器使用。

    只允许训练D_init/D_grow。源码操作不更新长期库，评分不能进入同题修复或选择。
    """
    from .session import Session
    from methods.direction_screening.run import evaluate
    from methods.direction_screening.protocol import outcome
    evaluator=evaluator or evaluate
    started=time.monotonic()
    attempt_id=uuid.uuid4().hex
    context=solver_context(task,bank,suite)
    session=Session(requesters)
    operators=Operators(task,session,context,memory_kind)
    def event(record):
        if on_event:
            on_event({'task_id':str(task['index']), 'attempt_id':attempt_id, **record})
    execution=GraphExecutor(operators.bindings(),event,timeout=timeout).run(graph,context)
    codes=[c['code'] for c in execution['candidates']]
    if execution['selected_code'] and execution['selected_code'] not in codes:
        codes.append(execution['selected_code'])
    scored={}
    scoring_start=time.monotonic()
    for code in codes:
        if not execution['workflow_completed']:
            scored[code]={'code':code,**outcome({}),'error_type':'workflow_incomplete'}
            continue
        try:
            scored[code]=evaluator(task,code)
            evidence=scored[code].get('evidence')
            if isinstance(evidence,dict) and evidence.get('syntax_or_compile',{}).get('status') not in ('pass','fail'):
                scored[code].update(measured=False,joint=False)
        except Exception as exc:
            scored[code]={'code':code,**outcome({}),'error_type':type(exc).__name__,
                          'error_code':safe_error_code(exc)}
    final=scored.get(execution['selected_code'],{'code':'',**outcome({})})
    first=scored.get(codes[0]) if codes else None
    public_attempts=[]
    def collect(events):
        for e in events:
            output=e.get('output',{})
            if e.get('operation')=='inspect' and output.get('code'):
                public_attempts.append(output)
            for nested in output.get('repeat_rounds',[]):
                collect(nested['events'])
    collect(execution['events'])
    repair_scores=[]
    for e in execution['events']:
        rounds=e.get('output',{}).get('repeat_rounds',[])
        before_event=next((prior for prior in reversed(execution['events'][:execution['events'].index(e)])
                           if prior.get('node_id') in e.get('input_refs',[]) and prior.get('output',{}).get('code')),None)
        before=before_event.get('output') if before_event else None
        for nested in rounds:
            after=nested['selected_code']
            if before and before['code'] in scored and after in scored:
                repair_scores.append({'node_id':e['node_id'],'before':scored[before['code']], 'after':scored[after]})
            if after:
                before={'code':after}
    memories=operators.memory_records
    errors=[e for e in execution['events'] if e.get('status')=='failed']
    return {'task_id':str(task['index']), 'attempt_id':attempt_id, 'family_id':task['family_id'], 'cwe':str(task['CWE_ID']),
            'public_task':context['public_task'],'contract':context['contract'],
            'selected_code':execution['selected_code'],'first_code':codes[0] if codes else '',
            'final':final,'attempts':[first] if first else [],'candidate_scores':[scored[c] for c in codes],
            'candidate_hashes':[digest(c) for c in codes], 'repair_scores':repair_scores,
            'public_attempts':public_attempts,'events':execution['events'],'trace':session.trace,
            'memory':memories[-1] if memories else {'decision':'no_memory','injected_ids':[]}, 'memory_events':memories,
            'usage':session.usage,'workflow_completed':execution['workflow_completed'],
            'official_feedback_visible':False,
            'error_type':errors[0]['error_type'] if errors else None,
            'error_code':errors[0].get('error_code') if errors else None,
            'elapsed_seconds':time.monotonic()-started,'scoring_seconds':time.monotonic()-scoring_start}


def prepare():
    """准备训练清单/来源：沿用旧screen60，排除正式留出与来源family；无确认集抽取或模型调用。"""
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    from methods.direction_screening.run import CANONICAL
    manifest=json.loads((HISTORY/'manifest.json').read_text(encoding='utf-8'))
    canonical=json.loads(CANONICAL.read_text(encoding='utf-8'))
    by_id={str(t['index']):t for t in _load_tasks(0)}
    tasks=[by_id[str(e['task_id'])] for e in manifest['groups']['screen']]
    training={str(e['task_id']) for k in ('D_init','D_grow') for e in canonical['pools'][k]}
    heldout={e['family_id'] for k in ('D_gate','H_pass') for e in canonical['pools'][k]}
    families={t['family_id'] for t in tasks}
    if len(tasks)!=60 or len(families)!=60 or families & heldout or any(str(t['index']) not in training for t in tasks):
        raise ValueError('invalid_training_task_boundary')
    bank=json.loads((HISTORY/'source_bank.json').read_text(encoding='utf-8'))
    bank=[c for c in bank if c.get('quality_status')=='qualified']
    bank=[bind_source(c,by_id[str(c['source_id'])]) for c in bank]
    if any(c['family_id'] in families or c['family_id'] in heldout or str(c['source_id']) not in training for c in bank):
        raise ValueError('invalid_source_family_boundary')
    for task in tasks:
        solver_context(task,bank,None)
    return tasks,bank,manifest,CANONICAL


def score_version(store,version_id,graph,bank,tasks,requesters,suites,args):
    """运行阶段增量保存真实事件/逐题结果，缓存签名不同即拒绝；缺测不吞，全部评分在finish后。"""
    directory=store.version_dir(version_id)
    bind_snapshot(directory,'runtime',{'graph':graph,'bank':bank,'suites':suites,
                                     'task_ids':[str(t['index']) for t in tasks]})
    rows,errors=read_jsonl(directory/'rows.jsonl')
    if errors:
        raise ValueError('interrupted_jsonl_requires_audit')
    keys={str(r['task_id']) for r in rows}
    if len(keys)!=len(rows):
        raise ValueError('duplicate_task_rows')
    if keys-set(str(t['index']) for t in tasks):
        raise ValueError('unexpected_cached_task')
    control=ControlStore(directory/'control.json')
    activity_lock=threading.Lock()
    active_tasks={}
    active_nodes={}
    observed_request_peak=getattr(args,'request_gate',None).peak if getattr(args,'request_gate',None) else 0
    heartbeat_state={'time':datetime.now(timezone.utc).isoformat(),'run_id':store.root.name,
        'version_id':version_id,'planned':len(tasks),'saved':len(rows),
        'measured':sum(bool(r.get('final',{}).get('measured')) for r in rows),
        'pending':len(tasks)-len(rows),'active_task_id':None,'active_node_id':None,
        'active_tasks':[],'active_nodes':[],'queued':len(tasks)-len(rows),
        'configured_workers':getattr(args,'workers',1),
        'configured_request_concurrency':getattr(args,'request_concurrency',None),
        'observed_request_peak':0,'status':control.read()['status']}
    control.update_heartbeat(heartbeat_state)
    def update_activity():
        """调度监控阶段合并并发任务活动；锁内快照后原子写盘，不影响任务与评分。"""
        with activity_lock:
            snapshot={**heartbeat_state,'time':datetime.now(timezone.utc).isoformat(),
                'active_tasks':list(active_tasks),'active_nodes':list(active_nodes.values()),
                'active_task_id':next(iter(active_tasks),None),
                'active_node_id':next(iter(active_nodes.values()),{}).get('node_id') if active_nodes else None,
                'queued':max(0,len(tasks)-len(rows)-len(active_tasks)),
                'saved':len(rows),'pending':len(tasks)-len(rows),
                'observed_request_peak':getattr(getattr(args,'request_gate',None),'peak',observed_request_peak),
                'status':control.read()['status']}
        control.update_heartbeat(snapshot)
    def work(task):
        task_id=str(task['index'])
        with activity_lock:
            active_tasks[task_id]={'task_id':task_id,'started_at':datetime.now(timezone.utc).isoformat()}
        update_activity()
        def record_event(e):
            nonlocal observed_request_peak
            store.append(version_id,'events.jsonl',{'run_id':store.root.name,'version_id':version_id,**e})
            with activity_lock:
                if e.get('status')=='running':
                    active_nodes[task_id]={'task_id':task_id,'node_id':e.get('node_id'),
                        'operation':e.get('operation'),'started_at':e.get('started_at')}
                else:
                    active_nodes.pop(task_id,None)
            update_activity()
        return execute_task(task,graph,bank,requesters,suites.get(str(task['index'])),
                         on_event=record_event,timeout=args.workflow_timeout,
                         memory_kind=args.memory_kind)
    pending=[task for task in tasks if str(task['index']) not in keys]
    def persist(row):
        task_id=str(row['task_id'])
        # 任务证据先追加并刷新，再更新计数；失败时保留可恢复行，不提前报告已保存。
        store.append(version_id,'rows.jsonl',row)
        rows.append(row)
        write_json(directory/'summary.json',summarize(rows,len(tasks)))
        with activity_lock:
            active_tasks.pop(task_id,None)
            active_nodes.pop(task_id,None)
            heartbeat_state.update({'measured':sum(bool(r.get('final',{}).get('measured')) for r in rows),
                                    'saved':len(rows),'pending':len(tasks)-len(rows)})
        update_activity()
        print(json.dumps({'version':version_id,'progress':f'{len(rows)}/{len(tasks)}','joint':sum(r['final']['joint'] for r in rows)},ensure_ascii=True),flush=True)
    # 任务独立并发且有界派发；暂停请求后等待在途任务评分、持久化，再停止新任务。
    schedule_tasks(pending,set(),work,persist,control,workers=getattr(args,'workers',1))
    order={str(task['index']):i for i,task in enumerate(tasks)}
    rows.sort(key=lambda row:order[str(row['task_id'])])
    events,event_errors=read_jsonl(directory/'events.jsonl')
    completed={r.get('attempt_id') for r in rows if r.get('attempt_id')}
    interrupted=sorted({e['attempt_id'] for e in events if e.get('attempt_id') and e['attempt_id'] not in completed})
    write_json(directory/'recording_audit.json',{'interrupted_attempt_ids':interrupted,'event_errors':event_errors,
                                             'interpretation':'孤立尝试保留，不计入完整逐题结果。'})
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=DEFAULT_ROOT)
    parser.add_argument('--run-id',default='mase-search-20261013')
    parser.add_argument('--model',default='deepseek-v3.2')
    parser.add_argument('--layer',choices=['architecture','memory','joint'],default='architecture')
    parser.add_argument('--memory-kind',choices=['none','m1','m4'],default='m1')
    parser.add_argument('--proposals',type=int,default=2,help='本次探索提案数量；可续跑追加，不是每题调用预算')
    parser.add_argument('--limit',type=int,default=0,help='仅运行训练60中的明确小批；0表示60全部')
    parser.add_argument('--workflow-timeout',type=int,default=1800)
    parser.add_argument('--workers',type=int,default=4,help='独立任务并发数；不是每题调用配额')
    parser.add_argument('--request-concurrency',type=int,default=48,help='所有模型角色共享的API在途请求上限')
    parser.add_argument('--preflight',action='store_true',help='只做数据/来源质量重验证，不调用模型')
    args=parser.parse_args()
    if args.proposals<0 or args.limit<0 or args.workers<1 or not 1<=args.request_concurrency<=50:
        raise ValueError('invalid_run_size')
    from .dashboard.server import safe_identifier
    if not safe_identifier(args.run_id):
        raise ValueError('invalid_run_id')
    if ROOT/'translation_work' not in args.data_root.resolve().parents:
        raise ValueError('artifacts_must_be_under_translation_work')
    store=Store(args.data_root/args.run_id)
    tasks,bank,manifest,canonical=prepare()
    if args.limit:
        tasks=tasks[:args.limit]
    # 来源重新评分与行为依赖快照一同落盘；缓存签名覆盖数据、图操作、评分器依赖。
    dependencies=[]
    for folder in ('methods/mase_evolution','methods/a7_exploration','methods/direction_screening',
                   'methods/sct_agent','methods/sct_trajectory','methods/sct_lifecycle_replay','src/translation_pipeline'):
        dependencies.extend((ROOT/folder).glob('*.py'))
    dependencies.extend([canonical,HISTORY/'manifest.json',HISTORY/'source_bank.json',
                         ROOT/'data/external/secodeplt/secodeplt/data.json',
                         ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json'])
    signature={'files':snapshot(dependencies),'model':args.model,'layer':args.layer,'memory_kind':args.memory_kind,
               'task_ids':[str(t['index']) for t in tasks], 'workflow_timeout':args.workflow_timeout}
    sig_path=store.root/'signature.json'
    if sig_path.exists() and json.loads(sig_path.read_text(encoding='utf-8'))!=signature:
        raise ValueError('run_signature_changed_use_new_run_id')
    write_json(sig_path,signature)
    from methods.direction_screening.run import evaluate
    from methods.sct_trajectory.run_closed_loop import _load_tasks, _requester
    source_tasks={str(t['index']):t for t in _load_tasks(0)}
    audit_path=store.root/'audit.json'
    if not audit_path.exists():
        records=[]
        for card in bank:
            source=source_tasks[str(card['source_id'])]
            truth=source['ground_truth']
            evidence={}
            for name,field in (('patched','patched_code'),('vulnerable','vulnerable_code')):
                code=truth.get('code_before','')+truth.get(field,'')+truth.get('code_after','')
                evidence[name]={k:v for k,v in evaluate(source,code).items() if k!='code'}
            card['source_evidence']=evidence
            card['quality_status']='qualified' if evidence['patched']['joint'] and evidence['patched']['measured'] and evidence['patched'].get('evidence',{}).get('syntax_or_compile',{}).get('status')=='pass' else 'quarantined'
            records.append({'id':card['id'],'family_id':card['family_id'],'quality_status':card['quality_status'],'scores':evidence})
        write_json(store.root/'qualified_bank.json',[c for c in bank if c['quality_status']=='qualified'])
        write_json(audit_path,{'source_revalidation':records,'source_target_family_overlap':False,'formal_holdout_used':False,
                               'history_confirmation_pristine':False})
    bank=json.loads((store.root/'qualified_bank.json').read_text(encoding='utf-8'))
    bind_snapshot(store.root,'qualified_sources',bank)
    write_json(store.root/'manifest.json',{'tasks':[{'task_id':t['index'],'family_id':t['family_id']} for t in tasks],
               'data_role':'training_exploration','independent_confirmation':False,'parent_manifest':str(HISTORY/'manifest.json')})
    write_json(store.root/'run_metadata.json',{'run_id':args.run_id,'label':'MASE · '+args.layer+' 实际训练探索',
               'origin':'experiment','status':'preflight' if args.preflight else 'running','model':args.model,
               'data_role':f'已暴露训练探索 {len(tasks)}/60 family；非独立确认', 'parameters':vars(args)|{'data_root':str(args.data_root)},
               'recording_coverage':'真实节点事件、全部唯一候选事后评分','commit':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True).stdout.strip(),
               'signature':signature})
    if args.preflight:
        print(json.dumps({'tasks':len(tasks),'qualified_sources':len(bank),'model_calls':0}),flush=True)
        return
    shared_requests=ObservedSemaphore(args.request_concurrency)
    args.request_gate=shared_requests
    requesters={n:_requester(args.model,120,max_tokens=n,semaphore=shared_requests) for n in (4096,8192,16384)}
    from .session import Session
    from methods.a7_exploration.checks import propose as propose_checks
    suites={}
    checks_dir=store.root/'public_checks'
    checks_dir.mkdir(exist_ok=True)
    def prepare_checks(t):
        path=checks_dir/(str(t['index'])+'.json')
        if not path.exists():
            session=Session(requesters)
            suite=propose_checks(t,session)
            write_json(path,{'suite':suite,'usage':session.usage,'trace':session.trace})
        return str(t['index']),json.loads(path.read_text(encoding='utf-8'))['suite']
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        suites=dict(pool.map(prepare_checks,tasks))
    parent='v000'
    graph=initial_graph()
    if args.memory_kind=='none':
        graph['nodes'][0]['kind']='none'
    directory=store.version_dir(parent)
    if not directory.exists():
        store.create_version({'version_id':parent,'label':'当前环境起点：接口保护 + '+args.memory_kind,
                    'status':'running','phase':'exploration','expected':len(tasks),'parent_id':None,
                    'author':'human_initial','architecture':graph,'memory_hash':digest(bank)})
        write_json(directory/'memory.json',bank)
    baseline=score_version(store,parent,graph,bank,tasks,requesters,suites,args)
    if ControlStore(store.version_dir(parent)/'control.json').read()['status']=='paused':
        return
    write_json(directory/'decision.json',{'status':'baseline_completed'})
    info=json.loads((directory/'version.json').read_text(encoding='utf-8'));info['status']='baseline_completed';write_json(directory/'version.json',info)
    previous=[]
    for number in range(1,args.proposals+1):
        vid=f'v{number:03d}'
        target=store.version_dir(vid)
        if (target/'proposal.json').exists():
            proposal=json.loads((target/'proposal.json').read_text(encoding='utf-8'))
        else:
            session=Session(requesters)
            proposal=propose(session,graph,bank,baseline,args.layer,previous)
            proposal.update(design_usage=session.usage,design_trace=session.trace)
            structure=proposal.get('architecture',{})
            target.mkdir(parents=True,exist_ok=True)
            write_json(target/'proposal.json',proposal)
        if not (target/'version.json').exists():
            # 提案先落盘，半写版本可由同一提案恢复，不能再调用模型替换原提案。
            write_json(target/'version.json',{'version_id':vid,'label':proposal.get('hypothesis',vid),'status':'running' if proposal['valid'] else 'invalid_structure',
                       'phase':'exploration','expected':len(tasks),'parent_id':parent,'author':'model',
                       'changes':proposal.get('changes',[]), 'layer':args.layer,
                       'design_usage':proposal.get('design_usage',{}), 'errors':proposal['errors']})
            write_json(target/'architecture.json',proposal.get('architecture',{}))
        if not proposal['valid']:
            previous.append({'version':vid,'errors':proposal['errors']})
            continue
        candidate_graph=proposal['architecture']
        candidate_bank=apply_memory_updates(bank,proposal.get('memory_updates',[]))
        bind_snapshot(target,'ancestry',{'parent':parent,'graph':candidate_graph,'bank':candidate_bank})
        write_json(target/'memory.json',candidate_bank)
        after=score_version(store,vid,candidate_graph,candidate_bank,tasks,requesters,suites,args)
        if ControlStore(target/'control.json').read()['status']=='paused':
            return
        decision=decide(baseline,after)
        write_json(target/'decision.json',decision)
        info=json.loads((target/'version.json').read_text(encoding='utf-8'))
        info.update(status=decision['status'],architecture_hash=digest(candidate_graph),memory_hash=digest(candidate_bank))
        write_json(target/'version.json',info)
        previous.append({'version':vid,'hypothesis':proposal.get('hypothesis'),'decision':decision})
        if decision['status']=='accepted':
            parent,graph,bank,baseline=vid,candidate_graph,candidate_bank,after
        print(json.dumps({'version':vid,'decision':decision},ensure_ascii=True),flush=True)
    write_json(store.root/'search_state.json',{'selected_parent':parent,'proposals':previous,'frozen':False,'independent_confirmation':False})
    metadata=json.loads((store.root/'run_metadata.json').read_text(encoding='utf-8'));metadata['status']='exploration_completed';write_json(store.root/'run_metadata.json',metadata)


if __name__=='__main__':
    main()

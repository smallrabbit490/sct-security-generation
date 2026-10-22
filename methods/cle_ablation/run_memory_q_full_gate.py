"""旧CLE全D_gate四臂：父P7完整前向和验证，每次最多三卡，冻结已学习Q。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
from pathlib import Path
import random
import shutil
import subprocess
import threading
from time import perf_counter

from methods.cle_ablation import run_memory_q_gate_q0 as parent
from methods.cle_ablation.run_memory_q import prepare_shared_initial, record_result, shuffled_memory
from methods.cle_ablation.run_memory_q_unlimited import inputs, technical_errors, inspect_rows, FIELDS
from methods.cle_ablation.retrieval_q_study import reference_check
from methods.cle_ablation.runner import ROOT, load_memory
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.retrieval_hit_study import read_rows
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest
from methods.sct_trajectory.run_memory_q_study import _write_memory

PROTOCOL='cle-q-full-dgate-four-arm-cap3-v1'
CONFIG=ROOT/'configs/cle_memory_q_full_gate_cap3_20261019'
OUT=ROOT/'translation_work/diagnostics/20261019/cle_memory_q/full_gate_cap3_v1'
CURATED=ROOT/'results/curated/cle_memory_q_full_gate_cap3_20261019'
BANK=parent.PARENT/'observe/frozen/m_star_q.jsonl'
REPORT=ROOT/'docs/CLE_Dgate全量四臂三张上限实验结果_20261019.md'
ORDER={'Q0':None,'Q1':'similarity','Q2':'q','Q3':'q'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def append(path,value):
    with path.open('a',encoding='utf-8') as stream:
        stream.write(json.dumps(value,ensure_ascii=False)+'\n');stream.flush()


def source_identity():
    result=parent.source_identity()
    for path in (Path(__file__),CONFIG/'protocol.json',CONFIG/'manifest.design.json',CONFIG/'state_sources.json'):
        result[str(path.relative_to(ROOT))]=file_digest(path)
    return result


def verify(out):
    meta=read(out/'run_metadata.json')
    if source_identity()!=meta['source_identity'] or file_digest(BANK)!=meta['bank_sha256']:
        raise RuntimeError('prepared_source_or_Q_changed')
    from methods.cle_ablation.run_memory_q_unlimited import DATASET,POOLS
    if file_digest(DATASET)!=meta['dataset_sha256'] or file_digest(POOLS)!=meta['pools_sha256']:
        raise RuntimeError('prepared_dataset_or_pools_changed')
    return meta


def prepare(out,workers=8):
    """原298题全部保留；新参考预检只标记、不替换原题或用模型成绩筛选。"""
    if shutil.disk_usage(ROOT.anchor).free<5*1024**3:
        raise RuntimeError('insufficient_disk_space')
    sources=source_identity();design=read(CONFIG/'manifest.design.json')
    _,tasks,pools=inputs();nodes=load_memory(BANK)
    ids=[t['task_id'] for t in design['tasks']]
    assert len(ids)==298 and set(ids)==set(pools['D_gate'])
    assert len({tasks[i]['family_id'] for i in ids})==217
    assert not ({tasks[i]['family_id'] for i in ids}&{tasks[i]['family_id'] for i in pools['D_grow']})
    assert len(nodes)==1939 and sum(n.q_visits>0 for n in nodes)==466
    out.mkdir(parents=True,exist_ok=False)
    def check(identifier):
        task=tasks[identifier]
        try:
            item=reference_check(task)
        except (SyntaxError,ValueError) as exc:
            item={'task_id':identifier,'passed':False,'state':'unmeasured','error_type':type(exc).__name__}
        item.update(family_id=task['family_id'],placeholder='<LOCAL_PATH>' in json.dumps(task,ensure_ascii=False))
        return item
    with ThreadPoolExecutor(max_workers=workers) as pool:
        controls=list(pool.map(check,ids))
    info={t['task_id']:t for t in design['tasks']}
    known={tasks[i]['family_id'] for i in ('1000','1306','1317')}
    clean=[c['task_id'] for c in controls if c['passed'] and not c['placeholder']
           and not info[c['task_id']]['historically_flagged_contract_family'] and c['family_id'] not in known]
    probe=[];seen=set()
    for i in clean:
        if tasks[i]['family_id'] not in seen and len(probe)<4:
            probe.append(i);seen.add(tasks[i]['family_id'])
    assert len(probe)==4
    manifest={**design,'status':'prepared','protocol':PROTOCOL,'probe':probe,
              'preoutcome_diagnostic_tasks':clean,'all298_preserved':True}
    write(out/'manifest.json',manifest);write(CONFIG/'manifest.json',manifest)
    write(out/'reference_preflight.json',{'new_API_calls':0,'tasks':controls,
        'limitation':'Reference/public-binding check is not complete public-contract adjudication; masks locked before new outcomes.'})
    rng=random.Random(20261019);schedule=[]
    for i in ids:
        arms=list(ORDER);rng.shuffle(arms);schedule.append({'task_id':i,'arms':arms})
    write(out/'schedule.json',schedule)
    placebo=shuffled_memory(nodes,20261015,scope='cwe')
    for cwe in {str(n.cwe) for n in nodes}:
        assert sorted((n.q_value,n.q_visits) for n in nodes if str(n.cwe)==cwe)==sorted(
            (n.q_value,n.q_visits) for n in placebo if str(n.cwe)==cwe)
    _write_memory(out/'shuffled_input_memory.jsonl',placebo)
    (out/'memory_q_events.jsonl').write_text('',encoding='utf-8')
    from methods.cle_ablation.run_memory_q_unlimited import DATASET,POOLS
    meta={'protocol':PROTOCOL,'status':'prepared','source_identity':sources,'bank_path':str(BANK.relative_to(ROOT)),
          'bank_sha256':file_digest(BANK),'dataset_sha256':file_digest(DATASET),'pools_sha256':file_digest(POOLS),
          'parameters':read(CONFIG/'protocol.json'),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
          'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'original_parent_runner':str((parent.PARENT/'source_snapshot'/parent.RUNNER).relative_to(ROOT)),
          'full_forward':'native P7, no custom generation/validation','expected_rows':1192,'Q_updates':0,
          'source_Q_stage':'20261018 unlimited Dgrow observe end; not old cap3 bank or later tests'}
    write(out/'run_metadata.json',meta)
    for name in sources:
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    print(json.dumps({'prepared':True,'tasks':298,'families':217,'probe':probe,
                     'preoutcome_diagnostic_tasks':len(clean),'new_API_calls':0}),flush=True)


def inspect(items):
    """核对原生阶段与每次三卡、采用子集、P7末次交付；缺测和原生失败保留。"""
    inspect_rows(items)
    for row in items:
        assert row['workflow_arm']=='P7' and row['pool']=='D_gate'
        for a in row['attempts']:
            g=a.get('generation',{});trace=a.get('retrieval_trace') or {}
            cards=g.get('retrieved_cards',[]);adopted=g.get('cards',[])
            assert len(cards)<=3 and len(adopted)<=3
            assert {c['invariant_id'] for c in adopted}<={c['invariant_id'] for c in cards}
            if trace.get('status')=='completed':
                assert trace['selection_limit']==3
                assert trace['selected_ids']==[c['invariant_id'] for c in cards]


def run_job(identifier,arm,tasks,shared,nodes,placebo,requester,embedding):
    request,tracker=parent.account_request(requester,arm)
    started=perf_counter()
    row=parent.frozen_runner().run_one('PLT',tasks[identifier],'P7',request,
        {'full':placebo if arm=='Q3' else nodes},embedding,retrieval_mode='semantic_llm',
        delta=-1,lambda_q=.5,max_experiences=3,candidate_order=ORDER[arm],
        initial_analysis=copy.deepcopy(shared[identifier]))
    record_result(row,tasks[identifier],arm,'D_gate',perf_counter()-started)
    snap=tracker.snapshot()
    row.update(protocol=PROTOCOL,retrieval_mode='native_semantic_llm_cap3',candidate_order=ORDER[arm],
        accounting={'total':{k:snap['total'][k] for k in FIELDS},
                    'by_label':{label:{k:v[k] for k in FIELDS} for label,v in snap['by_label'].items()}})
    inspect([row]);return row


def run(out,probe=False,workers=8):
    """完整四臂按任务内平衡顺序执行；原生重试外不补跑，认证/额度出错停止付费。"""
    meta=verify(out);manifest=read(out/'manifest.json')
    selected=set(manifest['probe']) if probe else {t['task_id'] for t in manifest['tasks']}
    schedule=[b for b in read(out/'schedule.json') if b['task_id'] in selected]
    rows=read_rows(out/'rows.jsonl') if (out/'rows.jsonl').exists() else []
    done={(r['task_id'],r['arm']) for r in rows}
    wanted={(b['task_id'],a) for b in schedule for a in b['arms']}
    if wanted<=done:
        return report(out)
    from methods.sct_trajectory.run_closed_loop import _requester,load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    native_request=_requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=workers,thinking='disabled')
    fatal=threading.Event();fatal_reasons=[]
    def request(prompt):
        if fatal.is_set():
            raise RuntimeError('auth_or_quota_stopped')
        try:
            return native_request(prompt)
        except Exception as exc:
            diagnostics=getattr(exc,'safe_diagnostics',[])
            if any(isinstance(d,dict) and d.get('http_status') in (401,403,429) for d in diagnostics):
                fatal_reasons.append('auth_quota_or_rate_limit_exhausted');fatal.set()
            raise
    _,tasks,_=inputs();nodes=load_memory(BANK);placebo=load_memory(out/'shuffled_input_memory.jsonl')
    before=[n.to_dict() for n in nodes];parent.frozen_runner()
    embedding=EmbeddingClient(model='text-embedding-3-large',key_loader=load_key,
        cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    shared_rows=read_rows(out/'shared_initial.jsonl') if (out/'shared_initial.jsonl').exists() else []
    shared={r['task_id']:r['initial_analysis'] for r in shared_rows}
    initial_missing=[b['task_id'] for b in schedule if b['task_id'] not in shared]
    meta['status']='running';write(out/'run_metadata.json',meta);started=perf_counter()
    def initial(identifier):
        if fatal.is_set():return None
        r,tracker=parent.account_request(request,'shared_initial')
        item=prepare_shared_initial(tasks[identifier],r);snap=tracker.snapshot()
        item['accounting']={k:snap['total'][k] for k in FIELDS};return item
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(initial,i) for i in initial_missing]):
            item=future.result()
            if item is not None:
                append(out/'shared_initial.jsonl',item);shared_rows.append(item);shared[item['task_id']]=item['initial_analysis']
                if len(shared_rows)%32==0:print(json.dumps({'initials':len(shared_rows),'target':len(selected)}),flush=True)
    segments=read(out/'embedding_segments.json') if (out/'embedding_segments.json').exists() else []
    segments.append({})
    jobs=[(b['task_id'],a) for b in schedule for a in b['arms'] if (b['task_id'],a) not in done]
    try:
        # 每批8条保留题内轮换顺序，相近时间完成各组；不先跑完整个Q0再跑Q2。
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for offset in range(0,len(jobs),workers):
                if fatal.is_set():break
                chunk=jobs[offset:offset+workers]
                futures=[pool.submit(run_job,i,a,tasks,shared,nodes,placebo,request,embedding) for i,a in chunk]
                for future in as_completed(futures):
                    row=future.result();append(out/'rows.jsonl',row);rows.append(row)
                segments[-1]=embedding.usage;write(out/'embedding_segments.json',segments)
                if len(rows)%32==0 or offset+workers>=len(jobs):
                    current=report(out)
                    print(json.dumps({'rows':len(rows),'target':16 if probe else 1192,
                        'joint':{a:v['joint'] for a,v in current['arms'].items()},
                        'tokens':current['total_llm_cost']['total_tokens']},ensure_ascii=False),flush=True)
        assert before==[n.to_dict() for n in nodes]
        verify(out)
    finally:
        segments[-1]=embedding.usage;write(out/'embedding_segments.json',segments)
        meta=read(out/'run_metadata.json')
        meta.update(status='stopped_auth_or_quota' if fatal.is_set() else 'completed' if len(rows)==1192 else 'partial',
            rows=len(rows),segments=meta.get('segments',[])+[{'wall_seconds':perf_counter()-started,'rows_total':len(rows),'probe':probe}],
            stop_reasons=fatal_reasons)
        write(out/'run_metadata.json',meta);report(out)


def report(out):
    """原生成绩和格式完整保留，结果/数据缺陷/缺测分列；主表不事后删题。"""
    verify(out);manifest=read(out/'manifest.json')
    rows=read_rows(out/'rows.jsonl') if (out/'rows.jsonl').exists() else []
    inspect(rows)
    assert len({(r['task_id'],r['arm']) for r in rows})==len(rows)
    first={};failed=[]
    for r in rows:
        a=r['attempts'][0];t=a.get('retrieval_trace') or {}
        if t.get('status')=='completed':
            value=(t['query_hash'],t['candidate_ids'],t['scores'])
            if r['task_id'] in first:assert first[r['task_id']]==value,'first_query_or_candidates_changed'
            first[r['task_id']]=value
        else:failed.append({'task_id':r['task_id'],'arm':r['arm'],'reason':'first_retrieval_not_completed'})
    summary=summarize(rows,'Q0')
    initials=read_rows(out/'shared_initial.jsonl') if (out/'shared_initial.jsonl').exists() else []
    costs={arm:{k:sum(r['accounting']['total'][k] for r in rows if r['arm']==arm) for k in FIELDS} for arm in ORDER}
    shared_cost={k:sum(r['accounting'][k] for r in initials) for k in FIELDS}
    total={k:sum(c[k] for c in costs.values())+shared_cost[k] for k in FIELDS}
    summary.update(protocol=PROTOCOL,completed=len(rows)==1192,expected_rows=1192,rows=len(rows),
        planned_tasks=298,families=217,max_experiences=3,shared_initials=len(initials),
        arm_costs=costs,shared_initial_cost=shared_cost,total_llm_cost=total,Q_updates=0,
        engineering_errors=technical_errors(rows),unverified_first_retrieval=failed,
        currency_actual=None,independent_final_test=False)
    write(out/'summary.json',summary);CURATED.mkdir(parents=True,exist_ok=True);write(CURATED/'summary.json',summary)
    infos={t['task_id']:t for t in manifest['tasks']}
    scores=[{'task_id':r['task_id'],'family_id':r['family_id'],'cwe':r['cwe'],'arm':r['arm'],
        **{k:r['final'][k] for k in ('functional','security','joint','measured')},
        'first_joint':r['attempts'][0]['joint'],'code_attempts':len(r['attempts']),
        'calls':r['accounting']['total']['calls'],'tokens':r['accounting']['total']['total_tokens'],
        'error_type':r.get('error_type'),'historically_flagged_contract_family':infos[r['task_id']]['historically_flagged_contract_family'],
        'preoutcome_diagnostic_task':r['task_id'] in manifest['preoutcome_diagnostic_tasks']} for r in rows]
    parent.dump_csv(CURATED/'scores.csv',scores)
    write(CURATED/'manifest.json',manifest)
    lines=['# CLE D_gate全量四臂：原生P7、每次最多三张','',
       f'协议：{PROTOCOL}。已保存{len(rows)}/1192条；全部298题/217个family，旧生成不拼入。','',
       '| 组 | 完成 | F | S | Joint | 计划分母Joint率 | 完整测量 | 流程错误 |',
       '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm,item in summary['arms'].items():
        lines.append(f'| {arm} | {item["n"]}/298 | {item["functional"]} | {item["security"]} | {item["joint"]} | {item["joint"]/298:.2%} | {item["measured"]} | {item["errors"]} |')
    lines+=['','Q0原顺序，Q1相似度，Q2学习Q，Q3同CWE打乱Q；均由原LLM最多选三张，再走原复析、采用、规划、生成、原验证与最多一次修复。',
       '共同读取20261018不限量273题D_grow观察学习结束的冻结1939卡/466卡有Q；不是旧297卡Q库。所有评价不更新Q。',
       '只有全1192条完成后才做主要Joint配对结论；当前部分率不代表最终结果。缺测不当已验证失败，数据问题单列。',
       f'已知LLM用量{total["calls"]}次逻辑请求、{total["total_tokens"]:,} Token；共享初析只计一次，实际货币费用未测量。',
       '完整规格见docs/CLE_Dgate全量四臂三张上限实验规格_20261019.md；逐题原生代码/阶段/验证见本运行rows.jsonl。']
    text='\n'.join(lines)+'\n';REPORT.write_text(text,encoding='utf-8');(out/'report.md').write_text(text,encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','report'));parser.add_argument('--probe',action='store_true')
    parser.add_argument('--workers',type=int,choices=range(1,9),default=8);args=parser.parse_args()
    if args.action=='prepare':prepare(OUT,args.workers)
    elif args.action=='run':run(OUT,args.probe,args.workers)
    else:report(OUT)


if __name__=='__main__':main()

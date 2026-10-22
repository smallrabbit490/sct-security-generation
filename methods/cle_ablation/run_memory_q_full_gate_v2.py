"""全D_gate四臂记录器修订：逐条先保存，按本次检索阶段核对，原P7保持不变。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import copy
from pathlib import Path
import shutil
import threading
from time import perf_counter

from methods.cle_ablation import run_memory_q_full_gate as old
from methods.cle_ablation.run_memory_q_full_gate import (
    ROOT, CONFIG, BANK, REPORT, ORDER, FIELDS, read, append, write, inputs, load_memory,
    file_digest, parent, record_result, prepare_shared_initial, read_rows, technical_errors, summarize)

PROTOCOL = 'cle-q-full-dgate-four-arm-cap3-v2-recorder'
OUT = ROOT/'translation_work/diagnostics/20261019/cle_memory_q/full_gate_cap3_v2'
CURATED = ROOT/'results/curated/cle_memory_q_full_gate_cap3_20261019'


def source_identity():
    sources = old.source_identity()
    for path in (Path(__file__), CONFIG/'protocol.v2.json'):
        sources[str(path.relative_to(ROOT))] = file_digest(path)
    return sources


def verify(out):
    old.verify(old.OUT)
    meta = read(out/'run_metadata.json')
    assert meta['source_identity'] == source_identity(), 'v2_source_changed'
    assert meta['original_rows_sha256'] == file_digest(old.OUT/'rows.jsonl'), 'original_rows_changed'
    assert meta['shared_initial_sha256'] == file_digest(old.OUT/'shared_initial.jsonl'), 'shared_initial_changed'
    return meta


def effective_trace(attempt):
    """原P7在修复检索抛错时可能沿用c0轨迹；本次阶段优先，原字段原样保留。"""
    for stage in attempt.get('generation', {}).get('stages', []):
        if stage['stage'] == 'retrieval' and stage['status'] == 'degraded':
            return stage.get('retrieval_trace') or {'status':'error','errors':[stage.get('error')]}
    return attempt.get('retrieval_trace') or {}


def inspect(rows):
    issues, resolutions = [], []
    for row in rows:
        try:
            old.inspect_rows([row])
            assert row['workflow_arm']=='P7' and row['pool']=='D_gate'
            for attempt in row['attempts']:
                g = attempt.get('generation', {})
                selected = [c['invariant_id'] for c in g.get('retrieved_cards', [])]
                assert len(selected)<=3 and len(g.get('cards', []))<=3, 'card_cap'
                trace = effective_trace(attempt)
                if trace.get('status')=='completed':
                    assert trace['selection_limit']==3, 'selection_limit'
                    assert trace['selected_ids']==selected, 'successful_trace_card_mismatch'
                elif (attempt.get('retrieval_trace') or {}).get('status')=='completed':
                    resolutions.append({'task_id':row['task_id'],'arm':row['arm'],
                        'attempt':attempt['attempt'],'reason':'native_prior_attempt_trace_after_current_retrieval_error',
                        'effective_errors':trace.get('errors', [])})
        except AssertionError as exc:
            issues.append({'task_id':row['task_id'],'arm':row['arm'],'error':str(exc) or 'native_row_invariant'})
    return issues, resolutions


def prepare(out):
    old.verify(old.OUT)
    previous = read_rows(old.OUT/'rows.jsonl')
    grouped = {}
    for row in previous:
        grouped.setdefault(row['task_id'], []).append(row)
    complete = {i for i,v in grouped.items() if {r['arm'] for r in v}==set(ORDER)}
    affected = sorted(set(grouped)-complete)
    # 中断的最后一批8次均已提交；其中5条已记录、3条未落盘，整批技术重跑。
    assert len(previous)==29 and len(complete)==6 and affected==['1409','335']
    reusable = [r for r in previous if r['task_id'] in complete]
    discarded = [r for r in previous if r['task_id'] in affected]
    assert len(reusable)==24 and len(discarded)==5
    out.mkdir(parents=True,exist_ok=False)
    for name in ('shared_initial.jsonl','schedule.json','reference_preflight.json','shuffled_input_memory.jsonl','embedding_segments.json'):
        shutil.copy2(old.OUT/name,out/name)
    manifest = {**read(old.OUT/'manifest.json'), 'protocol':PROTOCOL, 'recovery_probe':affected,
        'reused_complete_task_ids':sorted(complete),'reused_rows':24,'new_P7_rows':1168,
        'technical_repeat_task_ids':affected,'excluded_original_rows':5,
        'original_unrecorded_P7_runs':3,'extra_P7_runs_due_to_recorder_incident':8}
    write(out/'manifest.json',manifest);write(CONFIG/'manifest.v2.json',manifest)
    for row in reusable:
        row = copy.deepcopy(row)
        row['source_protocol'] = row['protocol'];row['protocol']=PROTOCOL
        append(out/'rows.jsonl',row)
    meta = {**read(old.OUT/'run_metadata.json'), 'protocol':PROTOCOL,'status':'prepared',
        'source_identity':source_identity(),'original_rows_sha256':file_digest(old.OUT/'rows.jsonl'),
        'shared_initial_sha256':file_digest(old.OUT/'shared_initial.jsonl'),
        'parameters':read(CONFIG/'protocol.v2.json'),'rows':24,'segments':[],
        'prior_recorder_incident':{'saved':29,'unrecorded_submitted_runs':3,'repeat_entire_incomplete_task_batch':affected,
            'excluded_saved_cost':{k:sum(r['accounting']['total'][k] for r in discarded) for k in FIELDS},
            'unrecorded_call_and_token_usage':None,'accounting_boundary':'known usage is a lower bound; 3 old P7 usage unavailable'}}
    write(out/'run_metadata.json',meta)
    (out/'memory_q_events.jsonl').write_text('',encoding='utf-8')
    for name in meta['source_identity']:
        target=out/'source_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    write(old.OUT/'recorder_incident.json',meta['prior_recorder_incident'])
    print({'prepared_v2':True,'reused':24,'new':1168,'technical_repeat_tasks':affected,'unrecorded_old_runs':3},flush=True)


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
    return row


def report(out):
    verify(out)
    rows=read_rows(out/'rows.jsonl');manifest=read(out/'manifest.json');meta=read(out/'run_metadata.json')
    issues,resolutions=inspect(rows)
    assert len(rows)==len({(r['task_id'],r['arm']) for r in rows})
    first,failed={},[]
    for row in rows:
        trace=effective_trace(row['attempts'][0])
        if trace.get('status')=='completed':
            value=(trace['query_hash'],trace['candidate_ids'],trace['scores'])
            if row['task_id'] in first and first[row['task_id']]!=value:
                issues.append({'task_id':row['task_id'],'arm':row['arm'],'error':'first_common_candidates_changed'})
            first[row['task_id']]=value
        else:
            failed.append({'task_id':row['task_id'],'arm':row['arm'],'reason':'first_retrieval_not_completed'})
    summary=summarize(rows,'Q0')
    costs={arm:{k:sum(r['accounting']['total'][k] for r in rows if r['arm']==arm) for k in FIELDS} for arm in ORDER}
    initials=read_rows(out/'shared_initial.jsonl')
    initial_cost={k:sum(r['accounting'][k] for r in initials) for k in FIELDS}
    incident=meta['prior_recorder_incident']['excluded_saved_cost']
    total={k:sum(c[k] for c in costs.values())+initial_cost[k]+incident[k] for k in FIELDS}
    summary.update(protocol=PROTOCOL,completed=len(rows)==1192 and not issues,expected_rows=1192,
        rows=len(rows),planned_tasks=298,families=217,max_experiences=3,shared_initials=len(initials),
        arm_costs=costs,shared_initial_cost=initial_cost,prior_incident_saved_cost=incident,
        total_llm_cost=total,known_cost_is_lower_bound=True,unrecorded_prior_P7_usage=3,
        Q_updates=0,engineering_errors=technical_errors(rows),integrity_issues=issues,
        native_trace_resolutions=resolutions,unverified_first_retrieval=failed,
        currency_actual=None,independent_final_test=False)
    write(out/'summary.json',summary);CURATED.mkdir(parents=True,exist_ok=True);write(CURATED/'summary.json',summary)
    write(out/'native_trace_resolution.json',resolutions)
    info={t['task_id']:t for t in manifest['tasks']}
    scores=[{'task_id':r['task_id'],'family_id':r['family_id'],'cwe':r['cwe'],'arm':r['arm'],
        **{k:r['final'][k] for k in ('functional','security','joint','measured')},
        'first_joint':r['attempts'][0]['joint'],'code_attempts':len(r['attempts']),
        'calls':r['accounting']['total']['calls'],'tokens':r['accounting']['total']['total_tokens'],
        'error_type':r.get('error_type'),
        'historically_flagged_contract_family':info[r['task_id']]['historically_flagged_contract_family'],
        'preoutcome_diagnostic_task':r['task_id'] in manifest['preoutcome_diagnostic_tasks']} for r in rows]
    parent.dump_csv(CURATED/'scores.csv',scores);write(CURATED/'manifest.json',manifest)
    lines=['# CLE D_gate全量四臂三张上限：记录器修订版','',
        f'{len(rows)}/1192条已保存；原生P7及全部模型/卡库/三张参数保持不变，全部298题保留。','',
        '|组|完成|F|S|Joint|计划分母Joint率|完整测量|流程错误|',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm in ORDER:
        v=summary['arms'].get(arm,dict(n=0,functional=0,security=0,joint=0,measured=0,errors=0))
        lines.append(f'|{arm}|{v["n"]}/298|{v["functional"]}|{v["security"]}|{v["joint"]}|{v["joint"]/298:.2%}|{v["measured"]}|{v["errors"]}|')
    lines+=['', 'v1在保存前做严格轨迹断言而中断。29条原记录保留，6道完整任务24条复用；最后两道任务335/1409四组整批技术重跑，原已存5条不拼入主成绩、3条未落盘结果不能恢复。该8次额外执行及未知用量单列，不冒称零成本或成绩失败。',
        f'已知LLM逻辑请求{total["calls"]}次、Token {total["total_tokens"]:,}，另3次旧P7的调用/Token未知；完整后再作正式配对结论。',
        f'记录完整性问题{len(issues)}项，原生失败检索沿用旧轨迹的诊断更正{len(resolutions)}项；原始轨迹仍保留，按本次retrieval阶段解释。']
    text='\n'.join(lines)+'\n';REPORT.write_text(text,encoding='utf-8');(out/'report.md').write_text(text,encoding='utf-8')
    return summary


def run(out,probe=False,workers=8):
    meta=verify(out);manifest=read(out/'manifest.json')
    selected=set(manifest['recovery_probe']) if probe else {t['task_id'] for t in manifest['tasks']}
    rows=read_rows(out/'rows.jsonl');done={(r['task_id'],r['arm']) for r in rows}
    jobs=[(b['task_id'],a) for b in read(out/'schedule.json') if b['task_id'] in selected for a in b['arms'] if (b['task_id'],a) not in done]
    if not jobs:return report(out)
    from methods.sct_trajectory.run_closed_loop import _requester,load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    native_request=_requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=workers,thinking='disabled')
    fatal=threading.Event();reasons=[]
    def request(prompt):
        if fatal.is_set():raise RuntimeError('execution_stopped')
        try:return native_request(prompt)
        except Exception as exc:
            if any(d.get('http_status') in (401,403,429) for d in getattr(exc,'safe_diagnostics',[])):
                fatal.set();reasons.append('auth_quota_or_rate_limit_exhausted')
            raise
    _,tasks,_=inputs();nodes=load_memory(BANK);placebo=load_memory(out/'shuffled_input_memory.jsonl')
    before=[n.to_dict() for n in nodes];before_placebo=[n.to_dict() for n in placebo]
    shared={r['task_id']:r['initial_analysis'] for r in read_rows(out/'shared_initial.jsonl')}
    assert len(shared)==298
    parent.frozen_runner()
    embedding=EmbeddingClient(model='text-embedding-3-large',key_loader=load_key,
        cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    segments=read(out/'embedding_segments.json');segments.append({})
    started=perf_counter();meta['status']='running';write(out/'run_metadata.json',meta)
    cursor=iter(jobs)
    def submit(pool,pending):
        if fatal.is_set():return
        job=next(cursor,None)
        if job is not None:
            pending[pool.submit(run_job,*job,tasks,shared,nodes,placebo,request,embedding)]=job
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending={}
            for _ in range(workers):submit(pool,pending)
            while pending:
                completed,_=wait(pending,return_when=FIRST_COMPLETED)
                for future in completed:
                    job=pending.pop(future)
                    row=future.result()
                    # 先保存，后核对；任何核对失败也不再丢弃已付费的逐题结果。
                    append(out/'rows.jsonl',row);rows.append(row)
                    issues,_=inspect([row])
                    if issues:fatal.set();reasons.extend(issues)
                    if len(rows)%16==0:
                        current=report(out)
                        if current['integrity_issues']:fatal.set();reasons.extend(current['integrity_issues'])
                        print({'rows':len(rows),'target':32 if probe else 1192,
                            'Joint':{a:v['joint'] for a,v in current['arms'].items()},
                            'tokens_known':current['total_llm_cost']['total_tokens']},flush=True)
                    segments[-1]=embedding.usage;write(out/'embedding_segments.json',segments)
                    submit(pool,pending)
        assert before==[n.to_dict() for n in nodes] and before_placebo==[n.to_dict() for n in placebo]
        verify(out)
    finally:
        segments[-1]=embedding.usage;write(out/'embedding_segments.json',segments)
        meta=read(out/'run_metadata.json')
        meta.update(status='stopped_technical' if fatal.is_set() else 'completed' if len(rows)==1192 else 'partial',
            rows=len(rows),stop_reasons=reasons,segments=meta['segments']+[{
                'wall_seconds':perf_counter()-started,'rows_total':len(rows),'recovery_probe':probe}])
        write(out/'run_metadata.json',meta);report(out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','report'));parser.add_argument('--probe',action='store_true')
    args=parser.parse_args()
    if args.action=='prepare':prepare(OUT)
    elif args.action=='run':run(OUT,args.probe)
    else:report(OUT)


if __name__=='__main__':main()

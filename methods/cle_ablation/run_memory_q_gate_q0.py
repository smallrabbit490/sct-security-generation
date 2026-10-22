"""旧CLE不限三张D_gate补Q0：只生成缺失48条，复用原源码、初析与三臂记录。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import csv
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
from time import perf_counter

from methods.cle_ablation.runner import ROOT, load_memory
from methods.cle_ablation.run_memory_q import record_result
from methods.cle_ablation.run_memory_q_unlimited import inputs, inspect_rows, technical_errors, FIELDS
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.retrieval_hit_study import read_rows
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest

PROTOCOL='cle-q-unlimited-gate-q0-addendum-v1'
CONFIG=ROOT/'configs/cle_memory_q_unlimited_gate_q0_20261019'
PARENT=ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
OUT=ROOT/'translation_work/diagnostics/20261019/cle_memory_q/unlimited_gate_q0_v1'
CURATED=ROOT/'results/curated/cle_memory_q_unlimited_gate_q0_20261019'
RUNNER=Path('methods/cle_ablation/runner.py')
REPORT=ROOT/'docs/CLE_不限三张Q_Dgate补充Q0对照结果_20261019.md'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def append(path,value):
    with path.open('a',encoding='utf-8') as f:
        f.write(json.dumps(value,ensure_ascii=False)+'\n')
        f.flush()


def frozen_runner():
    """仅P7入口已有新修改，故加载父运行原件；依赖另按父元数据核对，不改全局模块。"""
    name='methods.cle_ablation._gate_q0_parent_runner'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,PARENT/'source_snapshot'/RUNNER)
        module=importlib.util.module_from_spec(spec)
        sys.modules[name]=module
        spec.loader.exec_module(module)
        # 快照位置与真实项目根不同；run_one不使用其CLI数据路径，源码行为保持原样。
        module.ROOT=ROOT
    return sys.modules[name]


def source_identity():
    """依父运行实际源码核对；本轮额外冻结编排与配置，不绕过旧运行的指纹门。"""
    parent=read(PARENT/'run_metadata.json')
    result={}
    for name,expected in parent['source_identity'].items():
        relative=Path(name)
        path=PARENT/'source_snapshot'/relative if relative==RUNNER else ROOT/relative
        actual=file_digest(path)
        if actual!=expected:
            raise RuntimeError('parent_dependency_changed:'+name)
        result[str(path.relative_to(ROOT))]=actual
    for path in (Path(__file__),CONFIG/'protocol.json'):
        result[str(path.relative_to(ROOT))]=file_digest(path)
    return result


def input_identity():
    parent=read(PARENT/'run_metadata.json')
    from methods.cle_ablation.run_memory_q_unlimited import DATASET,POOLS
    if file_digest(DATASET)!=parent['dataset_sha256'] or file_digest(POOLS)!=parent['pools_sha256']:
        raise RuntimeError('parent_dataset_or_pools_changed')
    paths=[PARENT/'manifest.json',PARENT/'gate/rows.jsonl',PARENT/'gate/shared_initial.jsonl',
           PARENT/'observe/frozen/m_star_q.jsonl',PARENT/'gate/cost.json',DATASET,POOLS]
    return {str(p.relative_to(ROOT)):file_digest(p) for p in paths}


def verify(out):
    meta=read(out/'run_metadata.json')
    if source_identity()!=meta['source_identity'] or input_identity()!=meta['input_identity']:
        raise RuntimeError('prepared_source_or_input_changed')
    return meta


def prepare(out):
    """零API核对48题、父预检与共享初析；新目录写补充协议，旧三臂保持只读。"""
    if shutil.disk_usage(ROOT.anchor).free<3*1024**3:
        raise RuntimeError('insufficient_disk_space')
    sources=source_identity();identities=input_identity()
    manifest=read(PARENT/'manifest.json')
    ids=[str(v) for v in manifest['development']]
    old=read_rows(PARENT/'gate/rows.jsonl')
    shared=read_rows(PARENT/'gate/shared_initial.jsonl')
    _,tasks,pools=inputs()
    expected={(i,a) for i in ids for a in ('Q1','Q2','Q3')}
    assert len(ids)==48 and len(set(ids))==48 and len(old)==144
    assert {(r['task_id'],r['arm']) for r in old}==expected
    assert len({tasks[i]['family_id'] for i in ids})==48
    assert set(ids)<=set(pools['D_gate']) and manifest['preflight_passed']
    assert len(shared)==48 and {str(r['task_id']) for r in shared}==set(ids)
    assert all(r.get('initial_analysis') for r in shared)
    inspect_rows(old)
    nodes=load_memory(PARENT/'observe/frozen/m_star_q.jsonl')
    assert len(nodes)==1939
    out.mkdir(parents=True,exist_ok=False)
    write(out/'manifest.json',{'protocol':PROTOCOL,'tasks':ids,'new_arms':['Q0'],'expected_new_rows':48,
        'reused_arms':['Q1','Q2','Q3'],'reused_rows':144,'unique_families':48,
        'independent_final_test':False,'parent_run':str(PARENT.relative_to(ROOT))})
    write(CONFIG/'manifest.json',read(out/'manifest.json'))
    write(out/'run_metadata.json',{'protocol':PROTOCOL,'status':'prepared','source_identity':sources,
        'input_identity':identities,'parameters':read(CONFIG/'protocol.json'),
        'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'prepared_utc':datetime.now(timezone.utc).isoformat(),'parent_results_modified':False,
        'source_runner':str((PARENT/'source_snapshot'/RUNNER).relative_to(ROOT)),
        'existing_690_rows_reexecuted':False,'new_rows_target':48})
    (out/'memory_q_events.jsonl').write_text('',encoding='utf-8')
    for name in sources:
        target=out/'source_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,target)
    write(out/'preflight.json',{'passed':True,'new_API_calls':0,'parent_preflight_reused':True,
        'shared_initials':48,'frozen_cards':1939,'frozen_Q_covered':sum(n.q_visits>0 for n in nodes),
        'parent_native_rows':144,'parent_input_hashes_match':True,'parent_dependencies_match':True})
    print(json.dumps({'prepared':True,'tasks':48,'reuse_rows':144,'new_API_calls':0}),flush=True)


def account_request(requester,label):
    from methods.sct_trajectory.cost_tracker import CostTracker
    tracker=CostTracker('deepseek-v3.2');tracker.set_stage(label)
    def request(prompt):
        try:
            response=requester(prompt)
        except Exception:
            tracker.record_error('pipeline')
            raise
        tracker.record('pipeline',response)
        return response
    return request,tracker


def run_job(identifier,tasks,shared,nodes,requester,embedding):
    """只补D_gate Q0；原LLM选卡无数量上限、原候选联集顺序，不读取Q、不添接口提示。"""
    task=tasks[identifier]
    request,tracker=account_request(requester,'Q0')
    started=perf_counter()
    row=frozen_runner().run_one('PLT',task,'P7',request,{'full':nodes},embedding,
        retrieval_mode='semantic_llm',delta=-1,lambda_q=.5,max_experiences=None,
        candidate_order=None,initial_analysis=copy.deepcopy(shared[identifier]))
    record_result(row,task,'Q0','D_gate',perf_counter()-started)
    snap=tracker.snapshot()
    row.update(protocol=PROTOCOL,retrieval_mode='original_unlimited_llm_native_candidate_order',
        accounting={'total':{k:snap['total'][k] for k in FIELDS},
                    'by_label':{label:{k:value[k] for k in FIELDS} for label,value in snap['by_label'].items()}})
    return row


def check_rows(items):
    """核对原P7交付、冻结与首次共享候选；失败保留，不能伪造同候选成功。"""
    inspect_rows(items)
    old={r['task_id']:r for r in read_rows(PARENT/'gate/rows.jsonl') if r['arm']=='Q1'}
    initials={str(r['task_id']):r['initial_analysis'] for r in read_rows(PARENT/'gate/shared_initial.jsonl')}
    degraded=[]
    for row in items:
        assert row['arm']=='Q0' and row['pool']=='D_gate'
        for attempt in row['attempts']:
            g=attempt.get('generation',{});trace=attempt.get('retrieval_trace')
            if not trace or trace.get('status')!='completed':
                degraded.append({'task_id':row['task_id'],'attempt':attempt['attempt'],
                    'reason':'native_missing_or_failed_retrieval'})
                continue
            assert trace.get('selection_limit') is None
            assert 'value_ranking' not in trace and 'candidate_order' not in trace
            assert trace['selected_ids']==[c['invariant_id'] for c in g.get('retrieved_cards',[])]
            if attempt['attempt']==0:
                assert g['initial_analysis']==initials[row['task_id']]
                previous=old[row['task_id']]['attempts'][0]['retrieval_trace']
                for key in ('query_hash','candidate_ids','scores'):
                    assert trace[key]==previous[key],(row['task_id'],key)
    return degraded


def run(out,limit=48,workers=8):
    """固定48条内顺序补齐；保存的失败也跳过，使用父运行原有重试/修复预算。"""
    verify(out)
    from methods.sct_trajectory.run_closed_loop import _requester,load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    ids=read(out/'manifest.json')['tasks'][:limit]
    existing=read_rows(out/'rows.jsonl')
    done={r['task_id'] for r in existing}
    assert len(done)==len(existing) and done<=set(read(out/'manifest.json')['tasks'])
    missing=[i for i in ids if i not in done]
    if not missing:
        return report(out)
    _,tasks,_=inputs()
    shared={str(r['task_id']):r['initial_analysis'] for r in read_rows(PARENT/'gate/shared_initial.jsonl')}
    nodes=load_memory(PARENT/'observe/frozen/m_star_q.jsonl')
    before=[n.to_dict() for n in nodes]
    frozen_runner()
    requester=_requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=workers,thinking='disabled')
    embedding=EmbeddingClient(model='text-embedding-3-large',key_loader=load_key,
        cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    segments=read(out/'embedding_segments.json') if (out/'embedding_segments.json').exists() else []
    segments.append({})
    meta=read(out/'run_metadata.json');meta['status']='running';write(out/'run_metadata.json',meta)
    started=perf_counter();failure=None
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(run_job,i,tasks,shared,nodes,requester,embedding) for i in missing]
            for future in as_completed(futures):
                row=future.result()
                check_rows([row])
                append(out/'rows.jsonl',row);existing.append(row)
                segments[-1]=embedding.usage;write(out/'embedding_segments.json',segments)
                progress={'rows':len(existing),'target':48,'task_id':row['task_id'],
                    'Joint':row['final']['joint'],'measured':row['final']['measured'],
                    'joint_total':sum(r['final']['joint'] for r in existing)}
                write(out/'progress.json',progress)
                print(json.dumps(progress),flush=True)
        assert before==[n.to_dict() for n in nodes],'Q0_mutated_memory'
    except BaseException as exc:
        failure=type(exc).__name__
        raise
    finally:
        segments[-1]=embedding.usage;write(out/'embedding_segments.json',segments)
        periods=meta.get('segments',[])+[{'rows_added':len(existing)-len(done),
            'wall_seconds':perf_counter()-started,'error_type':failure}]
        meta.update(status='failed' if failure else 'completed' if len(existing)==48 else 'partial',
            rows=len(existing),segments=periods)
        write(out/'run_metadata.json',meta)
        report(out)


def dump_csv(path,items):
    if not items:
        return
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)


def report(out):
    """原统计函数合并只读三臂与新Q0；追加对照属探索，成本和执行日期分开。"""
    verify(out)
    added=read_rows(out/'rows.jsonl');degraded=check_rows(added)
    previous=read_rows(PARENT/'gate/rows.jsonl')
    combined=previous+added
    summary=summarize(combined,'Q0')
    paired=summary['paired']
    for arm,result in paired.items():
        baseline={r['task_id']:r for r in added}
        tests={r['task_id']:r for r in previous if r['arm']==arm}
        ids=sorted(baseline)
        differences=[int(tests[i]['final']['joint'])-int(baseline[i]['final']['joint']) for i in ids]
        if differences:
            rng=random.Random(20261019)
            samples=sorted(sum(rng.choices(differences,k=len(differences)))/len(differences) for _ in range(10000))
            result.update(delta_joint=sum(differences)/len(differences),ci95_paired_tasks=[samples[249],samples[9749]])
    q0cost={k:sum(r['accounting']['total'][k] for r in added) for k in FIELDS}
    oldcost=read(PARENT/'gate/cost.json')
    segments=read(out/'embedding_segments.json') if (out/'embedding_segments.json').exists() else []
    embedding={k:sum(segment.get(k,0) for segment in segments) for k in ('calls','total_tokens','failures','usage_missing_calls')}
    counts={}
    for arm in ('Q0','Q1','Q2','Q3'):
        attempts=[t for r in combined if r['arm']==arm for t in r['attempts']]
        counts[arm]={'attempts':len(attempts),'selected':sum(len(t.get('generation',{}).get('retrieved_cards',[])) for t in attempts),
            'declared_adopted':sum(len(t.get('generation',{}).get('cards',[])) for t in attempts),
            'over_three_selected':sum(len(t.get('generation',{}).get('retrieved_cards',[]))>3 for t in attempts),
            'over_three_adopted':sum(len(t.get('generation',{}).get('cards',[]))>3 for t in attempts)}
    summary.update(protocol=PROTOCOL,added_rows=len(added),reused_rows=len(previous),
        completed=len(added)==48,expected_combined_rows=192,unique_tasks=48,
        original_parent_protocol=read(PARENT/'run_metadata.json')['protocol'],
        adoption=counts,Q_frozen=True,new_Q_updates=0,
        new_cost={'Q0':q0cost,'embedding':embedding,'shared_initial_new_calls':0,'currency_actual':None},
        parent_cost=oldcost,engineering_errors=technical_errors(added),
        unverified_failed_retrieval_attempts=degraded,comparison_scope='late_added_development_control',
        full_library_recall='unmeasured',formal_retrieval_labels='not_added',
        claim='pending_48_rows' if len(added)<48 else 'exploratory_comparison_complete')
    write(out/'summary.json',summary)
    CURATED.mkdir(parents=True,exist_ok=True)
    write(CURATED/'summary.json',summary)
    write(CURATED/'manifest.json',read(out/'manifest.json'))
    write(CURATED/'verification.json',{'new_rows':len(added),'target':48,'native_P7_verified':True,
        'old_sources_preserved':True,'parent_runner_loaded':True,'shared_first_inputs_verified_when_retrieval_complete':True,
        'unverified_failed_retrieval_attempts':degraded,'Q0_no_Q_order':True,'unlimited_selection':True,'Q_updates':0})
    score_rows=[{'task_id':r['task_id'],'family_id':r['family_id'],'arm':r['arm'],
        **{k:r['final'][k] for k in ('functional','security','joint','measured')},
        'calls':r['accounting']['total']['calls'],'tokens':r['accounting']['total']['total_tokens'],
        'error_type':r.get('error_type'),'source':'new_Q0' if r['arm']=='Q0' else 'parent_gate'} for r in combined]
    dump_csv(CURATED/'scores.csv',score_rows)
    by_task={}
    for r in combined:
        by_task.setdefault(r['task_id'],{})[r['arm']]=r
    task_rows=[]
    for i in read(out/'manifest.json')['tasks']:
        group=by_task[i]
        task_rows.append({'task_id':i,'family_id':next(iter(group.values()))['family_id'],
            **{a+'_Joint':group[a]['final']['joint'] if a in group else None for a in ('Q0','Q1','Q2','Q3')},
            **{a+'_first_selected':len(group[a]['attempts'][0].get('generation',{}).get('retrieved_cards',[])) if a in group else None
               for a in ('Q0','Q1','Q2','Q3')}})
    dump_csv(CURATED/'task_pairs.csv',task_rows)
    lines=['# CLE 不限三张：固定48题D_gate补充Q0对照','',
        f'协议：{PROTOCOL}。新增Q0已完成{len(added)}/48，原三臂144条按引用复用；不是今天8题等K实验。','',
        '| 组别 | n | F | S | Joint | 完整测量 | 原生错误运行 |','|---|---:|---:|---:|---:|---:|---:|']
    for arm in ('Q0','Q1','Q2','Q3'):
        if arm in summary['arms']:
            item=summary['arms'][arm]
            lines.append('| '+arm+' | '+' | '.join(str(item[k]) for k in ('n','functional','security','joint','measured','errors'))+' |')
    lines+=['','Q0为原候选联集顺序+LLM自主选卡；Q1为相似度呈现顺序+LLM选卡；Q2为学习Q顺序+LLM选卡；Q3为同CWE打乱Q顺序+LLM选卡。全部无三张上限。',
        '冻结同一1939卡/Q，复用原48题首次初析及公开契约覆盖；Q0不读取Q排序、不加入今天接口提示或return/raise修订。P7加载父运行入口快照，其余已记录依赖与父元数据一致。',
        '首次Joint早停，否则最多一次修复，交付末次。旧结果与失败均保留；Q0追加执行日期不同，属事后开发对照，不是同步随机化试验。','',
        '## 配对比较','',json.dumps(paired,ensure_ascii=False,indent=2),'',
        'Q2−Q0为新增主要比较；同时报告三组相对Q0的原生精确配对检验及Holm校正、按任务配对重采样区间。原Q2−Q1/Q3结论保持历史原样。','',
        '## 新增成本','',json.dumps(summary['new_cost'],ensure_ascii=False,indent=2),'',
        '原144条和共享初析成本单列于summary.parent_cost，首次初析未重新付费；逻辑请求/回执Token不等于实付账单。','',
        '## 不限三张与采用','',json.dumps(counts,ensure_ascii=False,indent=2),'',
        '采用是模型声明ID，不自动证明代码正确落实。检索适用性人工标签与全库召回本轮未新增，不能把Joint当检索召回率。','',
        '原始新增记录：'+str(out/'rows.jsonl')+'；原144条：'+str(PARENT/'gate/rows.jsonl')+'。',
        '精简逐题与成本：'+str(CURATED)+'。完整结论与案例在48条完成后追加核对。']
    text='\n'.join(lines)+'\n'
    (out/'report.md').write_text(text,encoding='utf-8');REPORT.write_text(text,encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','report'))
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--limit',type=int,choices=(2,48),default=48)
    parser.add_argument('--workers',type=int,choices=range(1,9),default=8)
    args=parser.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to((ROOT/'translation_work/diagnostics').resolve()):
        parser.error('diagnostics_output_required')
    if args.action=='prepare':
        prepare(out)
    elif args.action=='run':
        run(out,args.limit,args.workers)
    else:
        report(out)


if __name__=='__main__':
    main()

"""全D_grow固定库Q学习：原P7并行生成，按预定顺序回放实际采用奖励。

原semantic_llm不读取Q，生成始终使用只读M0；Q回放与生成解耦。
仅修改实验副本Q，不生成经验、不准入候选、不访问D_gate或Base/Plus。
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import quantiles
from time import perf_counter

from methods.cle_ablation.audit_memory_q import read_rows
from methods.cle_ablation.run_memory_q import ROOT, learn_q, record_result, write_report
from methods.cle_ablation.runner import run_one
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest
from methods.sct_trajectory.run_memory_q_study import load_inputs, _write_memory

DATASET = ROOT/'data/external/secodeplt/secodeplt/data.json'
FAMILIES = ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json'


def require_full_pool(identifiers, pool):
    """必须包含原D_grow全部任务；同池family内的不同题不去重、不重分池。"""
    if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(pool):
        raise ValueError('manifest must contain entire D_grow exactly once')


def replay_credits(rows, source_nodes, controls, task_ids, alpha):
    """按清单顺序回放，消除并发完成顺序对EMA的影响；保留原始生成记录。"""
    learned = copy.deepcopy(source_nodes)
    nodes = {n.invariant_id:n for n in learned}
    by_task = {str(r['task_id']):r for r in rows}
    if len(by_task) != len(rows):
        raise ValueError('duplicate task results')
    events, families = [], defaultdict(set)
    for identifier in task_ids:
        if identifier not in by_task:
            continue
        original = by_task[identifier]
        control = controls[identifier]
        masked = original
        if not control['reward_eligible']:
            masked = {**original, 'attempts':[
                {**a, 'generation':{**a.get('generation',{}), 'workflow_completed':False}}
                for a in original['attempts']]}
        for event in learn_q(masked, nodes, alpha):
            event.update(outer_round=0, selection_policy='semantic_llm',
                         reward_eligible=control['reward_eligible'])
            if not control['reward_eligible']:
                event['skip_reason'] = ';'.join(control['exclusion_reasons'])
            if event.get('invariant_id') and event.get('reward') is not None:
                families[event['invariant_id']].add(original['family_id'])
            events.append(event)
    return learned, events, dict(families)


def inputs(args):
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    nodes, by_id, pools = load_inputs(args.memory, DATASET, FAMILIES, args.pools)
    identifiers = [str(i) for i in manifest['learning']]
    require_full_pool(identifiers, pools['D_grow'])
    if any(n.q_visits or n.q_value for n in nodes):
        raise ValueError('full learning starts from unlearned M0')
    return manifest, nodes, [by_id[i] for i in identifiers]


def sources():
    return [Path(__file__), ROOT/'methods/cle_ablation/run_memory_q.py',
            ROOT/'methods/cle_ablation/runner.py', ROOT/'methods/direction_screening/protocol.py',
            *[ROOT/'methods/sct_trajectory'/f'{name}.py' for name in (
                'context_pipeline','agent_pipeline','retriever','semantic_retrieval',
                'closed_loop','run_closed_loop','hsk_tree','memory_q','cost_tracker')]]


def source_identity(args):
    return {'manifest_sha256':file_digest(args.manifest), 'input_memory_sha256':file_digest(args.memory),
            'pools_sha256':file_digest(args.pools), 'dataset_sha256':file_digest(DATASET),
            'family_manifest_sha256':file_digest(FAMILIES),
            'source_sha256':{str(p.relative_to(ROOT)):file_digest(p) for p in sources()}}


def prepare(args, manifest, nodes, tasks):
    from methods.sct_trajectory.closed_loop import validate_and_state
    args.out.mkdir(parents=True, exist_ok=False)
    _write_memory(args.out/'input_memory.jsonl', nodes)
    shutil.copy2(args.pools, args.out/'input_pools.json')
    shutil.copy2(args.manifest, args.out/'experiment_manifest.json')
    for path in sources():
        target = args.out/'source_snapshot'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    metadata = {'protocol':manifest['protocol'], 'args':{'stage':'learn','alpha':manifest['alpha']},
        'task_ids':[t['index'] for t in tasks], 'families':len({t['family_id'] for t in tasks}),
        'status':'calibrating', 'model':'deepseek-v3.2', 'embedding_model':'text-embedding-3-large',
        'max_tokens':4096, 'thinking':'disabled', 'temperature':0, 'workers':args.workers,
        'backend':'local_python_isolated', 'pool':'D_grow', 'workflow_arm':'P7',
        'selection':'original semantic_llm, PLT first Joint stop else last, maximum 2',
        'credit_order':'manifest order, independent of parallel generation completion',
        'final_test_access':False, 'D_gate_access':False, 'q_update_pool':'D_grow only',
        'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'output_schema_version':'cle-ablation-p7-with-ma-final-v1', **source_identity(args)}
    write(args.out/'run_metadata.json', metadata)
    def control(task):
        truth=task['ground_truth']
        evidence,state=validate_and_state(task,truth['code_before']+truth['patched_code']+truth['code_after'],timeout=20)
        placeholder='<LOCAL_PATH>' in json.dumps(task,ensure_ascii=False)
        reasons=[]
        if state!='A':reasons.append('reference_not_joint')
        if placeholder:reasons.append('placeholder_in_task')
        return {'task_id':str(task['index']), 'family_id':task['family_id'], 'cwe':str(task['CWE_ID']),
            'reference_state':state, 'placeholder':placeholder, 'reward_eligible':not reasons,
            'exclusion_reasons':reasons, 'functional':evidence['functional']['status'],
            'security':evidence['security']['status']}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        controls=list(pool.map(control,tasks))
    write(args.out/'reference_calibration.json', {'model_calls':0,'tasks':controls})
    metadata.update(status='prepared', reward_eligible_tasks=sum(c['reward_eligible'] for c in controls),
                    reference_joint=sum(c['reference_state']=='A' for c in controls),
                    placeholder_tasks=sum(c['placeholder'] for c in controls))
    write(args.out/'run_metadata.json',metadata)
    print(json.dumps({k:metadata[k] for k in ('status','families','reward_eligible_tasks','reference_joint','placeholder_tasks')},ensure_ascii=False))


def publish(args, manifest, nodes, tasks, rows, metadata):
    ids=[str(t['index']) for t in tasks]
    controls={c['task_id']:c for c in json.loads((args.out/'reference_calibration.json').read_text(encoding='utf-8'))['tasks']}
    learned,events,families=replay_credits(rows,nodes,controls,ids,manifest['alpha'])
    ordered=sorted(rows,key=lambda r:ids.index(str(r['task_id'])))
    complete=len(rows)==len(tasks)
    frozen=args.out/('frozen/m_star_q.jsonl' if complete else 'checkpoints/m_star_q_partial.jsonl')
    frozen.parent.mkdir(parents=True,exist_ok=True)
    _write_memory(frozen,learned)
    (args.out/'memory_q_events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events),encoding='utf-8')
    similarities=[s['cosine'] for r in rows for a in r['attempts']
                  for s in (a.get('retrieval_trace') or {}).get('scores',[])]
    delta=quantiles(similarities,n=5,method='inclusive')[3] if len(similarities)>=2 else None
    summary=write_report(args.out,ordered,learned,delta,0.5,'learn')
    summary['role']='D_grow learning diagnostics, not independent accuracy evaluation'
    summary['Q_learning']={'visited_cards':sum(n.q_visits>0 for n in learned),
        'positive_updates':sum(e.get('reward')==1 and bool(e.get('invariant_id')) for e in events),
        'negative_updates':sum(e.get('reward')==-1 and bool(e.get('invariant_id')) for e in events),
        'skipped_events':sum(bool(e.get('skip_reason')) for e in events),
        'cards_two_independent_families':sum(len(f)>=2 for f in families.values()),
        'cards_three_independent_families':sum(len(f)>=3 for f in families.values()),
        'visit_distribution':dict(Counter(n.q_visits for n in learned if n.q_visits>0)),
        'by_card_cwe':dict(Counter(n.cwe for n in learned if n.q_visits>0))}
    valid=[r for r in rows if controls[str(r['task_id'])]['reward_eligible']]
    from methods.direction_screening.protocol import summarize
    summary['reward_eligible_cohort']=summarize(valid,'Q0')['arms']
    write(args.out/'summary.json',summary)
    write(args.out/'q_family_support.json',{k:sorted(v) for k,v in families.items()})
    totals={k:sum(r['accounting']['total'][k] for r in rows) for k in
            ('calls','prompt_tokens','completion_tokens','cached_tokens','usage_missing','errors')}
    totals['total_tokens']=totals['prompt_tokens']+totals['completion_tokens']
    segments=json.loads((args.out/'embedding_segments.json').read_text(encoding='utf-8')) if (args.out/'embedding_segments.json').exists() else []
    embedding={k:sum(segment.get(k,0) for segment in segments) for k in
               ('calls','failures','prompt_tokens','total_tokens','cache_hits','embedded_texts','usage_missing_calls')}
    write(args.out/'cost.json',{'llm':{'model':'deepseek-v3.2','total':totals},'embedding':embedding,
        'accounting':'Native per-row logical LLM usage; embedding measured by process segment. No invoice or currency estimate.'})
    metadata.update(rows=len(rows), memory_content_unchanged=True, q_unchanged=False,delta=delta,
                    status='completed' if complete else 'running', pid=os.getpid())
    write(args.out/'run_metadata.json',metadata)
    if complete:
        content=lambda bank:[{k:v for k,v in n.to_dict().items() if k not in ('q_value','q_visits')} for n in bank]
        from methods.cle_ablation.runner import load_memory
        if content(learned)!=content(load_memory(args.out/'input_memory.jsonl')):
            raise RuntimeError('fixed_memory_content_changed')
        write(args.out/'calibration.json',{'model':'deepseek-v3.2','embedding_model':'text-embedding-3-large',
            'thinking':'disabled','max_tokens':4096,'lambda_q':0.5,'alpha':manifest['alpha'],'delta':delta,
            'threshold_basis':'80th percentile all D_grow recalled candidates; unused by original P7 selection',
            'learning_ids':ids,'memory_sha256':file_digest(frozen),'pools_sha256':file_digest(args.pools),
            'q_visited':summary['Q_learning']['visited_cards'], 'generation_source_sha256':metadata['source_sha256']})
    return summary


def learn(args,manifest,nodes,tasks,metadata):
    from methods.sct_trajectory.run_closed_loop import _requester,load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.cost_tracker import CostTracker
    rows=read_rows(args.out/'rows.jsonl') if (args.out/'rows.jsonl').exists() else []
    done={str(r['task_id']) for r in rows}
    expected={str(t['index']) for t in tasks}
    if len(done)!=len(rows) or not done<=expected:raise ValueError('invalid resume rows')
    if len(done)==len(tasks):return publish(args,manifest,nodes,tasks,rows,metadata)
    request=_requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=args.workers,thinking='disabled')
    embedding=EmbeddingClient(model='text-embedding-3-large',key_loader=load_key,
        cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    segments=json.loads((args.out/'embedding_segments.json').read_text(encoding='utf-8')) if (args.out/'embedding_segments.json').exists() else []
    segments.append({})
    started=perf_counter()
    metadata.update(status='running',workers=args.workers,pid=os.getpid())
    write(args.out/'run_metadata.json',metadata)
    def execute(task):
        tracker=CostTracker('deepseek-v3.2')
        tracker.set_stage('Q0')
        def tracked(prompt):
            try:response=request(prompt)
            except Exception:
                tracker.record_error('pipeline')
                raise
            tracker.record('pipeline',response)
            return response
        start=perf_counter()
        result=run_one('PLT',task,'P7',tracked,{'full':nodes},embedding,retrieval_mode='semantic_llm',delta=-1,lambda_q=.5)
        record_result(result,task,'Q0','D_grow',perf_counter()-start)
        result['accounting']=tracker.snapshot()
        return result
    failure=None
    try:
        with (args.out/'rows.jsonl').open('a',encoding='utf-8') as stream, ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures=[pool.submit(execute,t) for t in tasks if str(t['index']) not in done]
            for future in as_completed(futures):
                result=future.result()
                stream.write(json.dumps(result,ensure_ascii=False)+'\n');stream.flush()
                rows.append(result)
                segments[-1]=embedding.usage
                write(args.out/'embedding_segments.json',segments)
                metadata['wall_seconds']=metadata.get('previous_wall_seconds',0)+perf_counter()-started
                if len(rows)%8==0 or len(rows)==len(tasks):
                    summary=publish(args,manifest,nodes,tasks,rows,metadata)
                    print(json.dumps({'rows':len(rows),'total':len(tasks),'Q':summary['Q_learning'],
                        'tokens':sum(r['accounting']['total']['total_tokens'] for r in rows)},ensure_ascii=False),flush=True)
                else:
                    metadata['rows']=len(rows)
                    write(args.out/'run_metadata.json',metadata)
    except BaseException as exc:
        failure=type(exc).__name__
        raise
    finally:
        segments[-1]=embedding.usage
        write(args.out/'embedding_segments.json',segments)
        metadata['previous_wall_seconds']=metadata.get('previous_wall_seconds',0)+perf_counter()-started
        metadata['wall_seconds']=metadata['previous_wall_seconds']
        publish(args,manifest,nodes,tasks,rows,metadata)
        if failure:
            metadata.update(status='failed',error_type=failure)
            write(args.out/'run_metadata.json',metadata)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('preflight','learn','report'),required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--memory',type=Path,default=ROOT/'docs/cle_evidence_package_20261015/experience_pool_1939.jsonl')
    parser.add_argument('--pools',type=Path,default=ROOT/'configs/cle_memory_q_autonomous_20261015/pools.recovered.json')
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    if not 1<=args.workers<=8 or not args.out.resolve().is_relative_to((ROOT/'translation_work/diagnostics').resolve()):
        parser.error('workers must be 1..8 and output inside diagnostics')
    manifest,nodes,tasks=inputs(args)
    if args.stage=='preflight':return prepare(args,manifest,nodes,tasks)
    metadata=json.loads((args.out/'run_metadata.json').read_text(encoding='utf-8'))
    for k,v in source_identity(args).items():
        if metadata[k]!=v:raise ValueError('resume input/source changed: '+k)
    if args.stage=='report':
        return publish(args,manifest,nodes,tasks,read_rows(args.out/'rows.jsonl'),metadata)
    return learn(args,manifest,nodes,tasks,metadata)


if __name__=='__main__':
    main()

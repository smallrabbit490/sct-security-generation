"""不限三张的旧CLE固定库研究；原P7/验证器，观察学习后冻结参与，不写旧产物。"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess
from time import perf_counter

from methods.cle_ablation.runner import ROOT, run_one, load_memory
from methods.cle_ablation.run_memory_q import record_result, prepare_shared_initial, shuffled_memory
from methods.cle_ablation.run_memory_q_full import replay_credits, sources, DATASET, FAMILIES
from methods.cle_ablation.audit_memory_q import read_rows
from methods.cle_ablation.retrieval_q_study import apply_public_overrides, reference_check
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.run_memory_q_study import load_inputs, _write_memory
from methods.sct_trajectory.run_branch_gate_study import stratified_tasks, file_digest
from methods.sct_trajectory.run_artifacts import write_json_atomic as write

PROTOCOL = 'cle-q-unlimited-observer-participant-v1'
CONFIG = ROOT/'configs/cle_memory_q_unlimited_20261018'
DEFAULT_OUT = ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_v1'
MEMORY = ROOT/'docs/cle_evidence_package_20261015/experience_pool_1939.jsonl'
POOLS = ROOT/'configs/cle_memory_q_autonomous_20261015/pools.recovered.json'
CURATED = ROOT/'results/curated/cle_memory_q_unlimited_20261018'
FIELDS = ('calls','prompt_tokens','completion_tokens','total_tokens','cached_tokens','usage_missing','errors')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return read_rows(path) if path.exists() else []


def append(path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(item, ensure_ascii=False)+'\n'); stream.flush()


def inputs():
    nodes, tasks, pools = load_inputs(MEMORY, DATASET, FAMILIES, POOLS)
    tasks = apply_public_overrides(tasks, read(CONFIG/'public_contract_overrides.json'))
    return nodes, tasks, pools


def identity():
    paths = list(dict.fromkeys(sources()+[Path(__file__), ROOT/'methods/sct_trajectory/selector_protocol.py',
                           CONFIG/'public_contract_overrides.json', CONFIG/'protocol.json',
                           CONFIG/'revise_gate_preflight.py']))
    return {str(p.relative_to(ROOT)):file_digest(p) for p in paths}


def prepare(out, workers):
    """零API检查奖励资格和D_gate公开依赖；名单只依预设顺序与契约，不看新成绩。"""
    if shutil.disk_usage(out.anchor).free < 3*1024**3:
        raise RuntimeError('insufficient_disk_space')
    out.mkdir(parents=True, exist_ok=False)
    nodes, by_id, pools = inputs()
    assert not any(n.q_visits or n.q_value for n in nodes)
    learning = read(ROOT/'configs/cle_memory_q_full_dgrow_20261016/manifest.json')['learning']
    assert {str(i) for i in learning} == set(pools['D_grow'])
    historical, reserved = set(), set()
    for folder in ('cle_memory_q_autonomous_20261015','cle_memory_q_probe8_20261016','cle_memory_q_shared_initial8_20261016'):
        old = read(ROOT/'configs'/folder/'manifest.json')
        historical.update(by_id[str(i)]['family_id'] for i in old['development'])
        reserved.update(by_id[str(i)]['family_id'] for i in old['confirmation'])
    def check(task):
        try:
            item = reference_check(task)
        except (SyntaxError, ValueError) as exc:
            item = {'task_id':str(task['index']), 'passed':False, 'state':'unmeasured',
                    'preflight_error':type(exc).__name__, 'undeclared_setup_bindings':[]}
        placeholder = '<LOCAL_PATH>' in json.dumps(task, ensure_ascii=False)
        reasons = []
        if item['state'] != 'A': reasons.append('reference_not_joint')
        if placeholder: reasons.append('placeholder_in_task')
        item.update(family_id=task['family_id'], cwe=str(task['CWE_ID']), placeholder=placeholder,
                    reward_eligible=not reasons, exclusion_reasons=reasons,
                    qualified=item['passed'] and not placeholder)
        return item
    gate_order = stratified_tasks([by_id[i] for i in pools['D_gate']], 0)
    # 先检查所有候选，再按固定顺序取48个合格的不同family；不逐次查看模型结果。
    with ThreadPoolExecutor(max_workers=workers) as pool:
        controls = list(pool.map(check, [by_id[str(i)] for i in learning]))
        gate_checks = list(pool.map(check, gate_order))
    gate, seen = [], set()
    for task, control in zip(gate_order, gate_checks):
        family = task['family_id']
        control.update(historical_q_development=family in historical, old_reserved=family in reserved)
        if control['qualified'] and str(task['index']) != '1015' and family not in seen and len(gate)<48:
            gate.append(int(task['index'])); seen.add(family)
    by_control = {c['task_id']:c for c in controls}
    probe = [i for i in learning if by_control[str(i)]['qualified']][:2]
    manifest = {'protocol':PROTOCOL, 'learning':learning, 'probe':probe, 'development':gate,
                'arms':['Q1','Q2','Q3'], 'selection':'CWE round robin/string ID; unique family; reference+public-binding check',
                'independent_final_test':False, 'preflight_passed':len(gate)==48 and len(probe)==2,
                'parameters':read(CONFIG/'protocol.json')}
    write(out/'manifest.json', manifest); write(CONFIG/'manifest.json', manifest)
    write(out/'reference_calibration.json', {'model_calls':0,'tasks':controls})
    write(out/'gate_preflight.json', {'model_calls':0,'tasks':gate_checks,
          'limitation':'Reference/public-binding checks do not establish full test coverage or exhaustive contract sufficiency.'})
    _write_memory(out/'input_memory.jsonl', nodes)
    shutil.copy2(POOLS,out/'input_pools.json')
    snapshot = identity()
    for relative in snapshot:
        target=out/'source_snapshot'/relative; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
    write(out/'run_metadata.json', {'protocol':PROTOCOL,'status':'prepared' if manifest['preflight_passed'] else 'stopped_preflight',
          'source_identity':snapshot,'dataset_sha256':file_digest(DATASET),'pools_sha256':file_digest(POOLS),
          'input_memory_sha256':file_digest(MEMORY),'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
          'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'parameters':manifest['parameters'],'old_results_modified':False,'backend':'original local python -I'})
    print(json.dumps({'preflight_passed':manifest['preflight_passed'],'probe':probe,'gate_tasks':len(gate),
          'reward_eligible':sum(c['reward_eligible'] for c in controls)},ensure_ascii=False),flush=True)
    if manifest['preflight_passed']:
        from configs.cle_memory_q_unlimited_20261018.revise_gate_preflight import main as revise_gate
        revise_gate(out)


def prepare_continuation(out, source, override):
    """用户明确取消推进门后建立新协议目录，复用相同生成版本的探针，保留原停机记录。"""
    if not override:
        raise ValueError('explicit_continue_despite_probe_required')
    previous=read(source/'run_metadata.json')
    current=identity()
    changes={p for p,digest in previous['source_identity'].items() if current.get(p)!=digest}
    # 只许可编排/预检修订；选卡、模型提示、P7和验证器必须与探针完全一致。
    allowed={'methods/cle_ablation/run_memory_q_unlimited.py','configs/cle_memory_q_unlimited_20261018/revise_gate_preflight.py'}
    if {Path(p).as_posix() for p in changes}-allowed:
        raise RuntimeError('probe_generation_source_changed')
    if file_digest(DATASET)!=previous['dataset_sha256'] or file_digest(POOLS)!=previous['pools_sha256']:
        raise RuntimeError('probe_input_changed')
    if shutil.disk_usage(out.anchor).free<3*1024**3:
        raise RuntimeError('insufficient_disk_space')
    out.mkdir(parents=True,exist_ok=False)
    for name in ('input_memory.jsonl','input_pools.json','reference_calibration.json','gate_preflight.json',
                 'gate_preflight_revision.json','probe_gate.json'):
        shutil.copy2(source/name,out/name)
    manifest=read(source/'manifest.json')
    manifest.update(protocol='cle-q-unlimited-observer-participant-v2-complete-authorized',
        progression_policy='execute all prescribed tasks regardless of experimental gates; preserve failures')
    write(out/'manifest.json',manifest)
    (out/'observe').mkdir()
    for name in ('rows.jsonl','shared_initial.jsonl','embedding_segments.json'):
        shutil.copy2(source/'observe'/name,out/'observe'/name)
    inherited=rows(out/'observe/rows.jsonl')
    assert len(inherited)==2 and {int(r['task_id']) for r in inherited}==set(manifest['probe'])
    for relative in current:
        target=out/'source_snapshot'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
    meta={**previous,'protocol':manifest['protocol'],'status':'authorized_continuation',
          'source_identity':current,'inherited_probe_source':str(source),'inherited_probe_rows':2,
          'probe_gate_override':True,'override_authority':'2026-10-18 direct user: complete plan regardless of gates',
          'previous_probe_gate':read(source/'probe_gate.json'),'source_changes':sorted(changes),
          'curated_dir':'results/curated/cle_memory_q_unlimited_complete_20261018',
          'report_file':'docs/CLE_不限三张Q完整执行结果_20261018.md'}
    write(out/'run_metadata.json',meta)
    config=ROOT/'configs/cle_memory_q_unlimited_complete_20261018';config.mkdir(exist_ok=False)
    for name in ('manifest.json','probe_gate.json','gate_preflight_revision.json'):
        shutil.copy2(out/name,config/name)
    write(config/'execution_override.json',{k:meta[k] for k in ('protocol','probe_gate_override','override_authority',
          'inherited_probe_source','inherited_probe_rows','curated_dir','report_file')})
    print(json.dumps({'status':'authorized_continuation','inherited_rows':2,'protocol':manifest['protocol']},ensure_ascii=False),flush=True)


def inspect_rows(items):
    """阶段消费者核对原生末次交付、早停和采用数量；不把声明采用自动认作代码落实。"""
    for row in items:
        assert row['final']==row['attempts'][-1] and 1<=len(row['attempts'])<=2
        assert not (len(row['attempts'])==2 and row['attempts'][0]['joint'])
        for attempt in row['attempts']:
            assert attempt['joint']==(attempt['measured'] and attempt['functional'] and attempt['security'])
            generation=attempt.get('generation',{})
            offered={c['invariant_id'] for c in generation.get('retrieved_cards',[])}
            assert {c['invariant_id'] for c in generation.get('cards',[])}<=offered


def technical_errors(items):
    return [{'task_id':r['task_id'],'arm':r['arm'],'attempt':a['attempt'],
             'error':a.get('error_type') or a.get('generation',{}).get('error_type') or 'unmeasured_or_degraded'}
            for r in items for a in r['attempts'] if not a['measured'] or a.get('error_type') or
            not a.get('generation',{}).get('workflow_completed')]


def publish(out, stage, items, source_nodes):
    """复用原统计；观察阶段才有采用奖励，其他阶段保持冻结。"""
    folder=out/stage; manifest=read(out/'manifest.json')
    inspect_rows(items)
    summary=summarize(items, 'Q0' if stage=='observe' else 'Q2' if stage=='retest' else 'Q1')
    summary.update(protocol=manifest['protocol'],stage=stage,role='training fit' if stage!='gate' else 'D_gate development transfer',
                   rows=len(items),technical_errors=technical_errors(items))
    attempts=[a for r in items for a in r['attempts']]
    summary['adoption']={'attempts':len(attempts),
        'retrieved_cards':sum(len(a.get('generation',{}).get('retrieved_cards',[])) for a in attempts),
        'declared_adopted_cards':sum(len(a.get('generation',{}).get('cards',[])) for a in attempts),
        'retrieved_above_three':sum(len(a.get('generation',{}).get('retrieved_cards',[]))>3 for a in attempts),
        'adopted_above_three':sum(len(a.get('generation',{}).get('cards',[]))>3 for a in attempts),
        'code_implementation_review':'not automatically verified; declaration is not implementation'}
    if stage=='observe':
        controls={c['task_id']:c for c in read(out/'reference_calibration.json')['tasks']}
        learned,events,families=replay_credits(items,source_nodes,controls,[str(i) for i in manifest['learning']],.3)
        complete=len(items)==273
        path=folder/('frozen/m_star_q.jsonl' if complete else 'checkpoints/m_star_q_partial.jsonl')
        _write_memory(path,learned)
        (folder/'memory_q_events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events),encoding='utf-8')
        summary['Q_learning']={'visited_cards':sum(n.q_visits>0 for n in learned),'total_cards':len(learned),
            'coverage':sum(n.q_visits>0 for n in learned)/len(learned),
            'updates':sum(e.get('reward') is not None and bool(e.get('invariant_id')) for e in events),
            'positive_updates':sum(e.get('reward')==1 and bool(e.get('invariant_id')) for e in events),
            'negative_updates':sum(e.get('reward')==-1 and bool(e.get('invariant_id')) for e in events),
            'two_family_cards':sum(len(f)>=2 for f in families.values()),
            'visit_distribution':dict(Counter(n.q_visits for n in learned if n.q_visits))}
        write(folder/'q_family_support.json',{k:sorted(v) for k,v in families.items()})
    else:
        (folder/'memory_q_events.jsonl').write_text('',encoding='utf-8')
        summary['q_frozen']=True
    shared=rows(folder/'shared_initial.jsonl')
    totals={k:sum(r['accounting']['total'][k] for r in items)+sum(r['accounting']['total'][k] for r in shared) for k in FIELDS}
    by_arm={arm:{k:sum(r['accounting']['total'][k] for r in items if r['arm']==arm) for k in FIELDS}
            for arm in sorted({r['arm'] for r in items})}
    segments=read(folder/'embedding_segments.json') if (folder/'embedding_segments.json').exists() else []
    embedding={k:sum(s.get(k,0) for s in segments) for k in ('calls','failures','total_tokens','cache_hits','embedded_texts','usage_missing_calls')}
    write(folder/'summary.json',summary)
    write(folder/'cost.json',{'llm':{'total':totals,'by_arm':by_arm,
         'shared_initial':{k:sum(r['accounting']['total'][k] for r in shared) for k in FIELDS}},
         'embedding':embedding,'currency_actual':None,'note':'Logical requests; no invoice/old price estimate. Shared initial counted once.'})
    return summary


def execute(out, stage, workers, *, probe=False):
    """同版本断点续接；已落盘失败不重跑，probe失败不会打开后续付费阶段。"""
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.cost_tracker import CostTracker
    manifest=read(out/'manifest.json'); meta=read(out/'run_metadata.json')
    if not manifest['preflight_passed']: raise RuntimeError('preflight_not_passed')
    if identity()!=meta['source_identity']: raise RuntimeError('source_changed_after_preflight')
    if file_digest(DATASET)!=meta['dataset_sha256'] or file_digest(POOLS)!=meta['pools_sha256']:
        raise RuntimeError('input_changed_after_preflight')
    if stage!='observe' and not (out/'observe/frozen/m_star_q.jsonl').exists():
        raise RuntimeError('observation_not_complete')
    if stage=='observe' and not probe and not read(out/'probe_gate.json')['passed'] and not meta.get('probe_gate_override'):
        raise RuntimeError('probe_not_passed')
    if stage=='gate' and read(out/'retest/run_metadata.json')['status']!='completed':
        raise RuntimeError('retest_not_complete')
    original, by_id, _=inputs()
    nodes=original if stage=='observe' else load_memory(out/'observe/frozen/m_star_q.jsonl')
    before=[n.to_dict() for n in nodes]
    placebo=shuffled_memory(nodes,20261015,'cwe') if stage=='gate' else None
    if placebo is not None:
        assert sorted((n.cwe,n.q_value,n.q_visits) for n in nodes)==sorted((n.cwe,n.q_value,n.q_visits) for n in placebo)
    folder=out/stage; folder.mkdir(parents=True,exist_ok=True)
    ids=manifest['probe'] if probe else manifest['development'] if stage=='gate' else manifest['learning']
    arms=['Q0'] if stage=='observe' else ['Q2'] if stage=='retest' else ['Q1','Q2','Q3']
    existing=rows(folder/'rows.jsonl'); done={(str(r['task_id']),r['arm']) for r in existing}
    assert len(done)==len(existing)
    expected={(str(i),a) for i in ids for a in arms}
    if expected<=done:
        return publish(out,stage,existing,nodes)
    requester=_requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=workers,thinking='disabled')
    embedding=EmbeddingClient(model='text-embedding-3-large',key_loader=load_key,
                cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    segments=read(folder/'embedding_segments.json') if (folder/'embedding_segments.json').exists() else []
    segments.append({})
    def account_request(label):
        tracker=CostTracker('deepseek-v3.2'); tracker.set_stage(label)
        def request(prompt):
            try: response=requester(prompt)
            except Exception:
                tracker.record_error('pipeline'); raise
            tracker.record('pipeline',response); return response
        return request,tracker
    def clean(tracker):
        snap=tracker.snapshot()
        return {'total':{k:snap['total'][k] for k in FIELDS},
                'by_label':{label:{k:value[k] for k in FIELDS} for label,value in snap['by_label'].items()}}
    shared_path=(out/'observe/shared_initial.jsonl') if stage=='retest' else folder/'shared_initial.jsonl'
    shared={str(r['task_id']):r['initial_analysis'] for r in rows(shared_path)}
    stage_meta={'protocol':manifest['protocol'],'stage':stage,'status':'running','task_ids':ids,'arms':arms,
                'workers':workers,'shared_initial_source':str(shared_path.relative_to(out)),
                'q_updates':stage=='observe','selection_limit':None,'backend':'original local python -I'}
    write(folder/'run_metadata.json',stage_meta)
    started=perf_counter()
    failure=None
    try:
        missing=[i for i in ids if str(i) not in shared]
        if stage=='retest' and missing: raise RuntimeError('missing_observer_initial')
        def initial(identifier):
            request,tracker=account_request('shared_initial')
            item=prepare_shared_initial(by_id[str(identifier)],request)
            item['accounting']=clean(tracker)
            return item
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for item in pool.map(initial,missing):
                append(folder/'shared_initial.jsonl',item); shared[str(item['task_id'])]=item['initial_analysis']
        def task_run(identifier,arm):
            task=by_id[str(identifier)]; request,tracker=account_request(arm); start=perf_counter()
            result=run_one('PLT',task,'P7',request,{'full':placebo if arm=='Q3' else nodes},embedding,
                     retrieval_mode='semantic_llm',delta=-1,lambda_q=.5,max_experiences=None,
                     candidate_order='similarity' if arm in ('Q0','Q1') else 'q',
                     initial_analysis=copy.deepcopy(shared[str(identifier)]))
            record_result(result,task,arm,'D_gate' if stage=='gate' else 'D_grow',perf_counter()-start)
            result.update(retrieval_mode='unlimited_llm_similarity' if arm in ('Q0','Q1') else 'unlimited_llm_q_order',
                          accounting=clean(tracker),protocol=manifest['protocol'])
            return result
        jobs=[(i,a) for j,i in enumerate(ids) for a in arms[j%len(arms):]+arms[:j%len(arms)] if (str(i),a) not in done]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures=[pool.submit(task_run,i,a) for i,a in jobs]
            for future in as_completed(futures):
                item=future.result(); append(folder/'rows.jsonl',item); existing.append(item)
                segments[-1]=embedding.usage; write(folder/'embedding_segments.json',segments)
                if len(existing)%8==0 or len(existing)==len(expected):
                    summary=publish(out,stage,existing,nodes)
                    print(json.dumps({'stage':stage,'rows':len(existing),'target':len(expected),
                          'joint':{a:v['joint'] for a,v in summary['arms'].items()},
                          'Q':summary.get('Q_learning'),'tokens':read(folder/'cost.json')['llm']['total']['total_tokens']},ensure_ascii=False),flush=True)
        assert before==[n.to_dict() for n in nodes], 'generation must not mutate source/frozen Q'
        if stage=='gate':
            grouped={}
            for row in existing:
                trace=row['attempts'][0].get('retrieval_trace')
                if trace is not None:
                    grouped.setdefault(str(row['task_id']),[]).append((trace['query_hash'],trace['candidate_ids'],trace['scores']))
            assert all(all(value==values[0] for value in values) for values in grouped.values()), 'shared first query/candidate mismatch'
    except BaseException as exc:
        failure=type(exc).__name__; raise
    finally:
        segments[-1]=embedding.usage; write(folder/'embedding_segments.json',segments)
        summary=publish(out,stage,existing,nodes)
        stage_meta.update(status='failed' if failure else 'completed' if expected<={(str(r['task_id']),r['arm']) for r in existing} else 'partial',
                          rows=len(existing),wall_seconds=perf_counter()-started,error_type=failure)
        write(folder/'run_metadata.json',stage_meta)
        if probe:
            probe_rows=[r for r in existing if int(r['task_id']) in manifest['probe']]
            issues=technical_errors(probe_rows)
            passed=len(probe_rows)==2 and not issues
            write(out/'probe_gate.json',{'passed':passed,'tasks':manifest['probe'],'errors':issues,
                  'joint':sum(r['final']['joint'] for r in probe_rows),
                  'rule':'2 complete native P7 tasks, measured F/S, no pipeline/technical errors; Joint need not pass'})
        write(out/'run_metadata.json',{**meta,'status':'failed_'+stage if failure else 'probe_passed' if probe and read(out/'probe_gate.json')['passed']
                                      else 'stopped_probe' if probe else stage+'_completed'})
    return summary


def report(out):
    """归档真实阶段、逐题成绩、采用声明与成本；未执行阶段不补零。"""
    state=read(out/'run_metadata.json')
    curated=ROOT/state['curated_dir'] if state.get('curated_dir') else CURATED
    curated.mkdir(parents=True,exist_ok=True)
    result={'protocol':state['protocol'],'status':state['status'],'stages':{}}
    score_rows=[]; mechanisms=[]
    for stage in ('observe','retest','gate'):
        folder=out/stage
        if not (folder/'summary.json').exists(): continue
        summary=read(folder/'summary.json'); cost=read(folder/'cost.json')
        result['stages'][stage]={'summary':summary,'cost':cost}
        for row in rows(folder/'rows.jsonl'):
            score_rows.append({'stage':stage,'task_id':row['task_id'],'family_id':row['family_id'],'cwe':row['cwe'],
                'arm':row['arm'],**{k:row['final'][k] for k in ('functional','security','joint','measured')},
                'declared_adopted_final':len(row['final'].get('generation',{}).get('cards',[])),
                'calls':row['accounting']['total']['calls'],'tokens':row['accounting']['total']['total_tokens']})
            for attempt in row['attempts']:
                generation=attempt.get('generation',{}); trace=attempt.get('retrieval_trace') or {}
                mechanisms.append({'stage':stage,'task_id':row['task_id'],'arm':row['arm'],'attempt':attempt['attempt'],
                    'candidate_ids':trace.get('candidate_ids',[]),'presented_ids':trace.get('presented_candidate_ids',[]),
                    'selected_ids':trace.get('selected_ids',[]),'declared_adopted_ids':[c['invariant_id'] for c in generation.get('cards',[])],
                    'joint':attempt['joint'],'workflow_completed':generation.get('workflow_completed',False),
                    'code_implementation_review':'pending_manual_review'})
    observe=rows(out/'observe/rows.jsonl'); retest=rows(out/'retest/rows.jsonl')
    if len(observe)==273 and len(retest)==273:
        paired=[{**r,'arm':'Q1'} for r in observe]+retest
        result['training_fit_comparison']=summarize(paired,'Q1')
    write(curated/'summary.json',result); write(curated/'run_metadata.json',state)
    (curated/'mechanisms.jsonl').write_text(''.join(json.dumps(v,ensure_ascii=False)+'\n' for v in mechanisms),encoding='utf-8')
    if score_rows:
        with (curated/'scores.csv').open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(score_rows[0]));writer.writeheader();writer.writerows(score_rows)
    lines=['# CLE 不限三张Q实验执行结果','','协议：'+state['protocol'],'','状态：'+state['status'],'',
           '| 阶段 | 组 | 已执行题数 | F | S | Joint | 完整测量 |','|---|---|---:|---:|---:|---:|---:|']
    for stage,item in result['stages'].items():
        for arm,value in item['summary']['arms'].items():
            lines.append('| '+stage+' | '+arm+' | '+' | '.join(str(value[k]) for k in ('n','functional','security','joint','measured'))+' |')
        if stage=='observe': lines+=['','观察学习Q覆盖：'+json.dumps(item['summary'].get('Q_learning',{}),ensure_ascii=False)]
    if (out/'probe_gate.json').exists():
        gate=read(out/'probe_gate.json'); lines+=['','## 两题探针门','',json.dumps(gate,ensure_ascii=False,indent=2)]
        result['probe_gate']=gate;write(curated/'summary.json',result)
    if state.get('probe_gate_override'):
        lines+=['','用户于2026-10-18明确要求完整执行、不按探针或效果门停止；原探针失败、全部后续失败均保留。前两题复用原记录，无重复调用。']
    lines+=['','## 解释与边界','',
        'Q0观察轮不使用Q选卡；Q2回测使用冻结Q；D_gate Q1/Q2/Q3分别为相似度、学习Q、同CWE打乱Q，均由同一LLM自主选卡，不限制三张。',
        '未执行阶段不填零分。采用统计是模型声明，不自动证明代码落实；逐题代码/验证保存在原生运行区。旧实验和数据未覆盖。',
        '模型及参数、固定名单见 configs/cle_memory_q_unlimited_20261018/；逐题成绩、机制与用量见 results/curated/cle_memory_q_unlimited_20261018/。',
        '本报告不把检索相似度当召回率，没有人工金标准时不报告正式检索四指标；货币实付未查询。']
    for stage,item in result['stages'].items():
        lines+=['',f'### {stage} 用量','',json.dumps(item['cost'],ensure_ascii=False,indent=2)]
    text='\n'.join(lines)+'\n'
    (out/'report.md').write_text(text,encoding='utf-8')
    report_file=ROOT/state.get('report_file','docs/CLE_不限三张Q实验结果_20261018.md')
    report_file.write_text(text,encoding='utf-8')
    print(json.dumps({'status':state['status'],'stages':list(result['stages'])},ensure_ascii=False),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('prepare','probe','observe','retest','gate','report','all'),required=True)
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--resume-from',type=Path)
    parser.add_argument('--continue-despite-probe',action='store_true')
    args=parser.parse_args();out=args.out.resolve()
    if not out.is_relative_to((ROOT/'translation_work/diagnostics').resolve()) or not 1<=args.workers<=8:
        parser.error('diagnostics output and workers 1..8 required')
    if args.stage=='prepare': return prepare(out,args.workers)
    if args.stage=='report': return report(out)
    if args.stage=='all':
        if not (out/'run_metadata.json').exists():
            if args.resume_from:
                prepare_continuation(out,args.resume_from.resolve(),args.continue_despite_probe)
            else:
                prepare(out,args.workers)
        try:
            if not (out/'probe_gate.json').exists(): execute(out,'observe',min(args.workers,2),probe=True)
            if not read(out/'probe_gate.json')['passed'] and not read(out/'run_metadata.json').get('probe_gate_override'):
                return report(out)
            execute(out,'observe',args.workers)
            execute(out,'retest',args.workers)
            execute(out,'gate',args.workers)
        finally:
            report(out)
        return
    try: return execute(out,'observe' if args.stage=='probe' else args.stage,args.workers,probe=args.stage=='probe')
    finally: report(out)


if __name__=='__main__':
    main()

"""旧CLE三张P7的覆盖学习：独立L0/L1探针，过门后最多两轮D_grow；不访问D_gate。"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess
from time import perf_counter

from methods.cle_ablation.run_memory_q_unlimited import inputs, FIELDS
from methods.cle_ablation.run_memory_q_gate_q0 import frozen_runner, account_request
from methods.cle_ablation.run_memory_q import record_result, learn_q, prepare_shared_initial
from methods.cle_ablation.runner import load_memory
from methods.cle_ablation.run_memory_q_full import sources, DATASET
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'configs/cle_q_coverage_learning_v2_20261019'
OUT=ROOT/'translation_work/diagnostics/20261019/cle_memory_q/coverage_learning_v2'
OLD=ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
CURATED=ROOT/'results/curated/cle_q_coverage_learning_v2_20261019'
PROTOCOL='cle-q-coverage-learning-cap3-v2-recording-repaired'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    if not Path(path).exists():return []
    with Path(path).open(encoding='utf-8') as f:return [json.loads(l) for l in f if l.strip()]


def append(path,item):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open('a',encoding='utf-8') as f:
        f.write(json.dumps(item,ensure_ascii=False)+'\n');f.flush()


def body(nodes):return [{k:v for k,v in n.to_dict().items() if k not in {'q_value','q_visits'}} for n in nodes]


def prepare():
    """新名单在任何新模型输出前锁定；依D_grow候选贪心选12个不同题族，不看D_gate。"""
    if (OUT/'manifest.json').exists():return read(OUT/'manifest.json')
    if shutil.disk_usage(ROOT.anchor).free < 3*1024**3:raise RuntimeError('insufficient_disk_space')
    _,tasks,pools=inputs();qualification=read(OUT/'qualification.after_dependencies.json')
    controls={t['task_id']:t for t in qualification['tasks']}
    qualified=[str(i) for i in pools['D_grow'] if controls[str(i)]['reward_eligible']]
    bank=load_memory(OLD/'observe/frozen/m_star_q.jsonl');learned={n.invariant_id for n in bank if n.q_visits}
    candidates={}
    from configs.cle_memory_q_full_gate_cap3_20261019.analyze import trace_of
    for row in rows(OLD/'observe/rows.jsonl'):
        if row['task_id'] in qualified:
            candidates[row['task_id']]=set(trace_of(row['attempts'][0]).get('candidate_ids',[]))
    chosen=[];covered=set();families=set()
    for _ in range(12):
        options=[i for i in qualified if i not in chosen and tasks[i]['family_id'] not in families]
        identifier=min(options,key=lambda i:(-len(candidates[i]-learned-covered),i))
        chosen.append(identifier);families.add(tasks[identifier]['family_id']);covered |= candidates[identifier]-learned
    original=read(OLD/'manifest.json')
    # 原清单顺序也是更新顺序；探针生成先行不改变最终奖励回放顺序。
    learning=[str(i) for i in original['learning'] if str(i) in qualified]
    manifest={'protocol':PROTOCOL,'learning':learning,'probe':chosen,'probe_families':[tasks[i]['family_id'] for i in chosen],
        'all_Dgrow':[str(i) for i in original['learning']],
        'skipped':[{k:t[k] for k in ('task_id','cwe','exclusion_reasons')} for t in controls.values() if not t['reward_eligible']],
        'N':len(learning),'maximum_P7_runs':2*len(learning)+12,'probe_P7_runs':24,
        'probe_selection':'D_grow first-query unlearned candidate incremental coverage, unique family, string ID tie',
        'D_gate_access':False,'reward':'actual adopted complete-workflow measured attempts only, Joint +1 else -1, alpha .3',
        'coverage_targets':{'whole_bank_learned':970,'fixed_old_Dgrow_anchor_learned':955},
        'probe_gates':{'minimum_L1_new_cards':12,'minimum_gain_over_L0':6,'maximum_token_ratio':1.25},
        'round2_minimum_round1_new_cards':30,'max_rounds':2,'max_experiences':3,
        'parameters':{'model':'deepseek-v3.2','embedding_model':'text-embedding-3-large','temperature':0,'thinking':'disabled',
                      'max_tokens':4096,'selector_max_tokens':256,'delta':-1,'lambda_q':.5,'max_code_attempts':2,
                      'L0_candidate_order':None,'L1_candidate_order':'coverage','backend':'native local python -I, timeout20'}}
    previous=read(OUT.parent/'coverage_learning_v1/manifest.json')
    assert chosen==previous['probe'] and learning==previous['learning'],'recording_repair_must_keep_same_tasks'
    manifest['recording_repair']='v1 four native records lost after POLICIES arm label KeyError; repeat all4, preserve known costs'
    OUT.mkdir(exist_ok=True,parents=True);CURATED.mkdir(exist_ok=True,parents=True)
    write(OUT/'manifest.json',manifest);write(CONFIG/'manifest.json',manifest)
    source_paths=[p for p in sources() if p.name!='runner.py']+[Path(__file__),CONFIG/'qualification.py',
        ROOT/'methods/sct_trajectory/semantic_retrieval.py',ROOT/'methods/sct_trajectory/selector_protocol.py',
        ROOT/'methods/cle_ablation/run_memory_q_gate_q0.py',ROOT/'configs/cle_memory_q_unlimited_20261018/public_contract_overrides.json']
    identity={str(p.relative_to(ROOT)):file_digest(p) for p in dict.fromkeys(source_paths)}
    runner=OLD/'source_snapshot/methods/cle_ablation/runner.py'
    identity[str(runner.relative_to(ROOT))]=file_digest(runner)
    for name in identity:
        dest=OUT/'source_snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dest)
    _write_memory(OUT/'input_memory.jsonl',bank)
    write(OUT/'base_family_support.json',read(OLD/'observe/q_family_support.json'))
    anchor=set()
    old_controls={str(t['task_id']):t for t in read(OLD/'reference_calibration.json')['tasks']}
    for row in rows(OLD/'observe/rows.jsonl'):
        if old_controls[row['task_id']]['reward_eligible']:
            for attempt in row['attempts']:anchor.update(trace_of(attempt).get('candidate_ids',[]))
    assert len(anchor)==1193
    write(OUT/'fixed_grow_anchor_ids.json',sorted(anchor))
    shared=rows(OLD/'observe/shared_initial.jsonl')
    for item in shared:
        if item['task_id'] in learning and not item.get('error_type'):append(OUT/'shared_initial.jsonl',item)
    write(OUT/'initial_reuse.json',{'historical_valid_reused':sum(i['task_id'] in learning and not i.get('error_type') for i in shared),
        'regenerate_only_prior_errors':[i['task_id'] for i in shared if i['task_id'] in learning and i.get('error_type')],
        'historical_cost_not_rebilled':True})
    write(OUT/'run_metadata.json',{'protocol':PROTOCOL,'status':'prepared','source_identity':identity,
        'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'dataset_sha256':file_digest(DATASET),'starting_memory_sha256':file_digest(OUT/'input_memory.jsonl'),
        'new_P7_runs':0,'D_gate_access':False,'new_initials':0,'segments':[]})
    print({'prepared':True,'N':len(learning),'probe':chosen,'unlearned_probe_candidates':len(covered)},flush=True)
    return manifest


def verify():
    meta=read(OUT/'run_metadata.json')
    for name,expected in meta['source_identity'].items():
        if file_digest(ROOT/name)!=expected:raise RuntimeError('source_changed:'+name)
    assert file_digest(DATASET)==meta['dataset_sha256']
    assert file_digest(OUT/'input_memory.jsonl')==meta['starting_memory_sha256']
    return meta


def inspect(row):
    """只核对真实P7操作和技术失败；正常F/S失败不阻止覆盖学习。"""
    from configs.cle_memory_q_full_gate_cap3_20261019.analyze import trace_of
    issues=[]
    if row.get('worker_error'):return ['worker_error']
    assert row['final']==row['attempts'][-1] and 1<=len(row['attempts'])<=2
    assert not (len(row['attempts'])==2 and row['attempts'][0]['joint'])
    for a in row['attempts']:
        g=a.get('generation',{});selected={c['invariant_id'] for c in g.get('retrieved_cards',[])}
        adopted={c['invariant_id'] for c in g.get('cards',[])}
        assert len(selected)<=3 and adopted<=selected
        t=trace_of(a)
        if t.get('status')!='completed':issues.append('retrieval_not_completed')
        if not g.get('workflow_completed'):issues.append('workflow_incomplete')
        if not a.get('measured'):issues.append('F_S_not_measured')
    return sorted(set(issues))


def normalize_result(row,task,arm,elapsed):
    """借原记录器Q0分支补原生字段，再写本研究L0/L1标签；不改P7行为。"""
    assert arm in {'L0','L1'}
    record_result(row,task,'Q0','D_grow',elapsed)
    row.update(arm=arm,retrieval_mode='native_llm_coverage' if arm=='L1' else 'native_llm_original')
    return row


def execute(stage, identifiers, arms, nodes, workers):
    """只在D_grow执行；每条付费任务先原子落盘，随后做汇总与阶段门。"""
    verify();folder=OUT/stage;folder.mkdir(exist_ok=True)
    _,tasks,_=inputs();before=[n.to_dict() for n in nodes]
    existing=rows(folder/'rows.jsonl');done={(r['task_id'],r['arm']) for r in existing}
    for path in sorted((folder/'task_rows').glob('*/*.json')):
        item=read(path);key=item['task_id'],item['arm']
        if key not in done:append(folder/'rows.jsonl',item);existing.append(item);done.add(key)
    jobs=[(i,a) for j,i in enumerate(identifiers) for a in arms[j%len(arms):]+arms[:j%len(arms)] if (i,a) not in done]
    if not jobs:return existing
    from methods.sct_trajectory.run_closed_loop import _requester,load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    request=_requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=workers,thinking='disabled')
    embedding=EmbeddingClient(model='text-embedding-3-large',key_loader=load_key,
        cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    shared={r['task_id']:r['initial_analysis'] for r in rows(OUT/'shared_initial.jsonl')}
    for identifier in identifiers:
        if identifier not in shared:
            req,tracker=account_request(request,'shared_initial');item=prepare_shared_initial(tasks[identifier],req)
            item['accounting']={k:tracker.snapshot()['total'][k] for k in FIELDS}
            append(OUT/'new_shared_initial.jsonl',item)
            if item.get('error_type'):raise RuntimeError('new_shared_initial_failed:'+identifier)
            append(OUT/'shared_initial.jsonl',item);shared[identifier]=item['initial_analysis']
    runner=frozen_runner();started=perf_counter()
    meta=read(OUT/'run_metadata.json');meta['status']='running_'+stage;write(OUT/'run_metadata.json',meta)
    def job(identifier,arm):
        req,tracker=account_request(request,arm);start=perf_counter()
        row=None
        try:
            row=runner.run_one('PLT',tasks[identifier],'P7',req,{'full':nodes},embedding,
                retrieval_mode='semantic_llm',delta=-1,lambda_q=.5,max_experiences=3,
                candidate_order=None if arm=='L0' else 'coverage',initial_analysis=copy.deepcopy(shared[identifier]))
            # 先保存原生返回，归档格式转换即使失败也不能再丢失已付费结果。
            write(folder/'native_task_rows'/identifier/(arm+'.json'),row)
            normalize_result(row,tasks[identifier],arm,perf_counter()-start)
        except Exception as exc:
            # 已观测过完成结果丢失；这里保留费用及安全错误类别，禁止自动重跑。
            row={**(row or {}),'task_id':identifier,'arm':arm,'pool':'D_grow','family_id':tasks[identifier]['family_id'],
                 'cwe':str(tasks[identifier]['CWE_ID']),'worker_error':type(exc).__name__}
            row.setdefault('attempts',[])
        row.update(protocol=PROTOCOL,stage=stage,candidate_order=None if arm=='L0' else 'coverage',
            accounting={'total':{k:tracker.snapshot()['total'][k] for k in FIELDS}})
        write(folder/'task_rows'/identifier/(arm+'.json'),row)
        return row
    cursor=iter(jobs);fatal=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending={}
        def submit():
            item=next(cursor,None)
            if item:pending[pool.submit(job,*item)]=item
        for _ in range(min(workers,len(jobs))):submit()
        while pending:
            completed,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in completed:
                pending.pop(future);row=future.result();append(folder/'rows.jsonl',row);existing.append(row)
                errors=inspect(row)
                if errors:fatal.append({'task_id':row['task_id'],'arm':row['arm'],'issues':errors})
                if not fatal:submit()
                if len(existing)%4==0:print({'stage':stage,'rows':len(existing),'target':len(identifiers)*len(arms),'technical_issues':len(fatal)},flush=True)
    assert before==[n.to_dict() for n in nodes],'generation_mutated_bank'
    segments=rows(OUT/'embedding_segments.jsonl');append(OUT/'embedding_segments.jsonl',{'stage':stage,**embedding.usage})
    meta=read(OUT/'run_metadata.json');meta['segments'].append({'stage':stage,'wall_seconds':perf_counter()-started,'new_runs':len(existing)-len(done)})
    meta['status']='technical_stop' if fatal else 'finished_'+stage
    write(OUT/'run_metadata.json',meta)
    if fatal:write(folder/'technical_stop.json',{'issues':fatal,'auto_retry':False})
    return existing


def credit(items, source, family_support, identifiers, folder):
    """批末按清单顺序更新真实采用卡，继承旧Q/访问/题族，不使用D_gate反馈。"""
    nodes=copy.deepcopy(source);by_id={n.invariant_id:n for n in nodes};events=[]
    families={k:set(v) for k,v in family_support.items()}
    by_task={r['task_id']:r for r in items}
    for identifier in identifiers:
        if identifier not in by_task or by_task[identifier].get('worker_error'):continue
        row=by_task[identifier]
        for event in learn_q(row,by_id,.3):
            event.update(protocol=PROTOCOL,stage=folder.name,actual_learning_pool='D_grow')
            events.append(event)
            if event.get('invariant_id') and event.get('reward') is not None:
                families.setdefault(event['invariant_id'],set()).add(row['family_id'])
    assert body(nodes)==body(source)
    _write_memory(folder/'frozen/m_star_q.jsonl',nodes)
    (folder/'memory_q_events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in events),encoding='utf-8')
    write(folder/'q_family_support.json',{k:sorted(v) for k,v in families.items()})
    learned={n.invariant_id for n in nodes if n.q_visits};old={n.invariant_id for n in source if n.q_visits}
    anchor=set(read(OUT/'fixed_grow_anchor_ids.json'))
    summary={'rows':len(items),'valid_updates':sum(e.get('invariant_id') is not None and e.get('reward') is not None for e in events),
        'learned_cards':len(learned),'new_cards':len(learned-old),'whole_bank_coverage':len(learned)/len(nodes),
        'fixed_anchor_learned':len(learned&anchor),'fixed_anchor_coverage':len(learned&anchor)/len(anchor),
        'positive_Q':sum(n.q_value>0 and n.q_visits>0 for n in nodes),'negative_Q':sum(n.q_value<0 and n.q_visits>0 for n in nodes),
        'visit_histogram':dict(Counter(n.q_visits for n in nodes)),
        'cards_two_families':sum(len(f)>=2 for f in families.values()),
        'F':sum(bool(r.get('final',{}).get('measured')) and r['final']['functional'] for r in items),
        'S':sum(bool(r.get('final',{}).get('measured')) and r['final']['security'] for r in items),
        'Joint':sum(bool(r.get('final',{}).get('measured')) and r['final']['joint'] for r in items),
        'measured':sum(r.get('final',{}).get('measured',False) for r in items),
        'selected_occurrences':sum(len(a.get('generation',{}).get('retrieved_cards',[])) for r in items for a in r['attempts']),
        'adopted_occurrences':sum(len(a.get('generation',{}).get('cards',[])) for r in items for a in r['attempts']),
        'cost':{k:sum(r['accounting']['total'][k] for r in items) for k in FIELDS},
        'technical_issues':[{'task_id':r['task_id'],'issues':inspect(r)} for r in items if inspect(r)],
        'new_card_ids':sorted(learned-old),'Q_is_model_weight_training':False}
    write(folder/'summary.json',summary)
    return nodes,families,summary


def common_first(items):
    from configs.cle_memory_q_full_gate_cap3_20261019.analyze import trace_of
    by=defaultdict(list)
    for row in items:
        if row.get('worker_error'):return False
        t=trace_of(row['attempts'][0])
        by[row['task_id']].append(tuple(t.get(k) for k in ('query_hash','candidate_ids','scores')))
    return all(len(v)==2 and v[0]==v[1] for v in by.values())


def run(workers):
    manifest=prepare();base=load_memory(OUT/'input_memory.jsonl');support=read(OUT/'base_family_support.json')
    probe=manifest['probe'];smoke=execute('probe',probe[:2],['L0','L1'],base,min(workers,4))
    if any(inspect(r) for r in smoke):
        write(OUT/'probe_gate.json',{'passed':False,'reason':'first2_technical_stop','executed_P7':len(smoke)})
        return
    probe_rows=execute('probe',probe,['L0','L1'],base,workers)
    summaries={}
    for arm in ['L0','L1']:
        target=OUT/'probe'/arm;target.mkdir(exist_ok=True)
        _,_,summaries[arm]=credit([r for r in probe_rows if r['arm']==arm],base,support,probe,target)
    zero=summaries['L0'];one=summaries['L1']
    ratio=one['cost']['total_tokens']/zero['cost']['total_tokens'] if zero['cost']['total_tokens'] else None
    checks={'all24':len(probe_rows)==24,'common_first_candidates':common_first(probe_rows),
        'new_cards_at_least12':one['new_cards']>=12,'gain_at_least6':one['new_cards']-zero['new_cards']>=6,
        'token_ratio_at_most1_25':ratio is not None and ratio<=1.25,
        'no_technical_issues':not zero['technical_issues'] and not one['technical_issues']}
    gate={'passed':all(checks.values()),'checks':checks,'new_cards_L0':zero['new_cards'],'new_cards_L1':one['new_cards'],
          'token_ratio_L1_L0':ratio,'interpretation':'engineering coverage gate, not statistical significance'}
    write(OUT/'probe_gate.json',gate);print({'probe_gate':gate},flush=True)
    if not gate['passed']:return
    # 复用L1探针，第一轮只补剩余合格题；奖励在完整清单顺序重新从M1回放。
    round1=OUT/'round1';round1.mkdir(exist_ok=True)
    if not (round1/'rows.jsonl').exists():
        for row in probe_rows:
            if row['arm']=='L1':append(round1/'rows.jsonl',row)
    first=execute('round1',manifest['learning'],['L1'],base,workers)
    after,families,result=credit(first,base,support,manifest['learning'],round1)
    if result['technical_issues'] or len(first)!=manifest['N']:return
    if result['learned_cards']>=970 and result['fixed_anchor_learned']>=955:return
    if result['new_cards']<30:
        write(OUT/'round2_gate.json',{'passed':False,'reason':'round1_new_cards_below30'});return
    write(OUT/'round2_gate.json',{'passed':True,'reason':'targets_not_met_and_round1_added_at_least30'})
    second=execute('round2',manifest['learning'],['L1'],after,workers)
    credit(second,after,families,manifest['learning'],OUT/'round2')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','run']);parser.add_argument('--workers',type=int,default=6)
    args=parser.parse_args()
    if args.stage=='prepare':prepare()
    else:run(args.workers)


if __name__=='__main__':main()

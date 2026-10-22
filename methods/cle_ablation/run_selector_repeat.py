"""旧 CLE 四臂重复选卡：只重放固定候选并调用原选择器，不生成代码、不测试、不更新 Q。"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import csv
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import random
import shutil
import subprocess
from time import perf_counter
from types import FunctionType, SimpleNamespace

import numpy as np

from methods.cle_ablation.runner import ROOT, load_memory, plt_contract
from methods.cle_ablation.run_memory_q import shuffled_memory
from methods.cle_ablation.run_memory_q_unlimited import inputs
from methods.sct_trajectory import semantic_retrieval as native
from methods.sct_trajectory.retrieval_hit_study import read_rows
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest

PROTOCOL = 'cle-selector-repeat-four-arm-v1'
CONFIG = ROOT/'configs/cle_selector_repeat_20261019'
PARENT = ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
REUSED = ROOT/'translation_work/diagnostics/20261019/cle_memory_q/equal_k_v1/reused_inputs.json'
OUT = ROOT/'translation_work/diagnostics/20261019/cle_selector_repeat/v1'
CURATED = ROOT/'results/curated/cle_selector_repeat_20261019'
REPORT = ROOT/'docs/CLE_四臂重复选卡与模型波动分析_20261019.md'
ARMS = ('Q0', 'Q1', 'Q2', 'Q3')
REPEATS = 5


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def append(path, value):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False)+'\n')
        stream.flush()


def dump_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def identities():
    """只冻结本次实际读取的输入与选择实现；用于保护旧记录和冻结 Q。"""
    paths = [Path(__file__), CONFIG/'protocol.json', REUSED, PARENT/'manifest.json',
             PARENT/'observe/frozen/m_star_q.jsonl', PARENT/'gate/shared_initial.jsonl',
             ROOT/'configs/cle_memory_q_unlimited_20261018/public_contract_overrides.json',
             ROOT/'methods/sct_trajectory/semantic_retrieval.py',
             ROOT/'methods/sct_trajectory/memory_q.py', ROOT/'methods/sct_trajectory/selector_protocol.py',
             ROOT/'methods/sct_trajectory/run_closed_loop.py',
             ROOT/'methods/cle_ablation/runner.py', ROOT/'methods/cle_ablation/run_memory_q.py']
    from methods.cle_ablation.run_memory_q_unlimited import DATASET, FAMILIES, POOLS
    paths += [DATASET, FAMILIES, POOLS]
    return {str(p.relative_to(ROOT)): file_digest(p) for p in paths}


def make_eligible(nodes, language='python'):
    """恢复原资格和完整卡正文，仅供原选择器消费；不调用向量或写库。"""
    return {n.invariant_id: (n, native.card_embedding_text(n)) for n in nodes
            if n.status in {'active', 'provisional', 'consolidated'} and language in n.language_leaves
            and len(native.card_embedding_text(n)) <= native.MAX_CARD_CHARS}


def select_cached(spec, eligible, arm, requester):
    """在函数私有 globals 中替换召回，原提示、排序与协议逐字复用；不改全局函数。

    输入历史公开查询、候选和余弦及只读 Q；输出原选择轨迹与实际卡 ID。
    本入口不构建 EmbeddingClient，不运行生成/验证，不更改长期库。
    """
    saved = spec['first_trace']

    def recall(task, nodes, embedding, limit, trace):
        query = native.query_embedding_text(task)
        if native._digest(query) != saved['query_hash']:
            raise ValueError('cached_query_changed')
        trace.update(query_hash=saved['query_hash'], eligible_count=len(eligible),
                     candidate_ids=list(saved['candidate_ids']), scores=copy.deepcopy(saved['scores']),
                     excluded=copy.deepcopy(saved.get('excluded', [])))
        return eligible, query, trace['scores']

    # 每次创建私有函数命名空间，避免多线程 monkey-patch 影响其他运行。
    function = FunctionType(native.semantic_select.__code__,
                            {**native.semantic_select.__globals__, 'recall_semantic_candidates': recall},
                            argdefs=native.semantic_select.__defaults__)
    function.__kwdefaults__ = native.semantic_select.__kwdefaults__
    order = None if arm == 'Q0' else 'similarity' if arm == 'Q1' else 'q'
    return function(spec['query'], [], requester, SimpleNamespace(model='text-embedding-3-large'),
                    limit=None, candidate_order=order, lambda_q=.5, delta=-1)


def prepare(out):
    """在新调用之前锁定既有前8题和160次平衡安排；离线捕获原生提示，不产生模型样本。"""
    if shutil.disk_usage(ROOT.anchor).free < 3*1024**3:
        raise RuntimeError('insufficient_disk_space')
    parent = read(PARENT/'manifest.json')
    ids = [str(i) for i in parent['development'][:8]]
    previous = {s['task_id']: s for s in read(REUSED)}
    _, tasks, pools = inputs()
    assert len(set(ids)) == 8 and set(ids) <= set(pools['D_gate'])
    assert len({tasks[i]['family_id'] for i in ids}) == 8
    nodes = load_memory(PARENT/'observe/frozen/m_star_q.jsonl')
    shuffled = shuffled_memory(nodes, 20261015, scope='cwe')
    for cwe in {str(n.cwe) for n in nodes}:
        assert sorted((n.q_value,n.q_visits) for n in nodes if str(n.cwe)==cwe) == sorted(
            (n.q_value,n.q_visits) for n in shuffled if str(n.cwe)==cwe)
    eligible = make_eligible(nodes)
    alternate = make_eligible(shuffled)
    specs = []
    for identifier in ids:
        old = previous[identifier]
        query = {**plt_contract(tasks[identifier]), 'threat_analysis':old['initial_analysis'],
                 'current_code':'', 'failure_evidence':{}}
        assert native._digest(native.query_embedding_text(query)) == old['first_trace']['query_hash']
        assert old['first_trace']['status']=='completed'
        for s in old['first_trace']['scores']:
            assert native._digest(eligible[s['id']][1]) == s['content_hash']
        spec = {**old, 'query':query, 'family_id':tasks[identifier]['family_id'],
                'cwe':str(tasks[identifier]['CWE_ID']), 'prompts':{}, 'orders':{}}
        for arm in ARMS:
            prompts=[]
            def capture(prompt):
                prompts.append(str(prompt))
                return {'choices':[{'message':{'content':'{"selected":[]}'},'finish_reason':'stop'}]}
            _, trace = select_cached(spec, alternate if arm=='Q3' else eligible, arm, capture)
            assert trace['status']=='completed' and len(prompts)==1
            spec['prompts'][arm]=prompts[0]
            spec['orders'][arm]=trace.get('presented_candidate_ids',trace['candidate_ids'])
            assert set(spec['orders'][arm])==set(old['first_trace']['candidate_ids'])
            assert 'q_value' not in prompts[0] and 'q_visits' not in prompts[0]
        specs.append(spec)
    out.mkdir(parents=True,exist_ok=False)
    write(out/'inputs.json',specs)
    manifest={'protocol':PROTOCOL,'tasks':[{'task_id':s['task_id'],'family_id':s['family_id'],'cwe':s['cwe'],
              'candidate_count':len(s['first_trace']['candidate_ids'])} for s in specs],
              'arms':ARMS,'repeats':REPEATS,'expected_rows':160,'independent_final_test':False}
    write(out/'manifest.json',manifest);write(CONFIG/'manifest.json',manifest)
    rng=random.Random(20261019);schedule=[]
    for repeat in range(1,REPEATS+1):
        order=ids.copy();rng.shuffle(order)
        for identifier in order:
            arms=list(ARMS);rng.shuffle(arms)
            schedule.append({'repeat':repeat,'task_id':identifier,'arms':arms})
    write(out/'schedule.json',schedule)
    write(out/'run_metadata.json',{'protocol':PROTOCOL,'status':'prepared','identity':identities(),
          'parameters':read(CONFIG/'protocol.json'),
          'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
          'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'prepared_utc':datetime.now(timezone.utc).isoformat(),'code_generation_calls':0,'Q_updates':0,
          'new_embedding_calls':0,'validation_calls':0,'offline_prompt_capture':'synthetic empty response, not experimental rows'})
    write(out/'preflight.json',{'passed':True,'tasks':8,'candidate_pairs':sum(len(s['first_trace']['candidate_ids']) for s in specs),
          'new_API_calls':0,'common_candidates_verified':True,'same_CWE_permutation_verified':True,
          'prompt_lengths':{s['task_id']:{a:len(p) for a,p in s['prompts'].items()} for s in specs},
          'identical_prompt_pairs':{s['task_id']:[list(p) for p in itertools.combinations(ARMS,2)
                                     if s['prompts'][p[0]]==s['prompts'][p[1]]] for s in specs}})
    print(json.dumps({'prepared':ids,'expected_rows':160,'new_API_calls':0}),flush=True)


def verify(out):
    meta=read(out/'run_metadata.json')
    if meta['identity']!=identities():
        raise RuntimeError('prepared_input_or_source_changed')
    return meta


def one_selection(spec,arm,repeat,requester):
    """仅调用原短编号选择协议；失败保留为失败，绝不转为空选择或重跑身份。"""
    from methods.sct_trajectory.selector_protocol import select_with_retry,SelectorProtocolError
    trace={'retrieval_mode':'cached_selection_only','status':'pending','candidate_ids':spec['first_trace']['candidate_ids'],
           'presented_candidate_ids':spec['orders'][arm],'query_hash':spec['first_trace']['query_hash'],
           'selection_limit':None,'selector_version':'compact-selection-v2'}
    usage=[];responses=[];started=perf_counter()
    def request(prompt):
        response=requester(prompt)
        usage.append(response.get('usage'))
        responses.append({k:response[k] for k in ('id','created','model','system_fingerprint') if k in response})
        return response
    error=None;selected=None
    try:
        local=select_with_retry(spec['prompts'][arm],request,len(spec['orders'][arm]),len(spec['orders'][arm]),trace)
        selected=[spec['orders'][arm][i-1] for i in local]
        trace.update(status='completed',selected_local_ids=local,selected_ids=selected)
    except SelectorProtocolError as exc:
        error=str(exc);trace.update(status='error',errors=[error])
    return {'protocol':PROTOCOL,'task_id':spec['task_id'],'family_id':spec['family_id'],'cwe':spec['cwe'],
            'arm':arm,'repeat':repeat,'status':trace['status'],'error_type':error,
            'selected_ids':selected,'retrieval_trace':trace,'usage_responses':usage,'response_metadata':responses,
            'prompt_hash':native._digest(spec['prompts'][arm]),'elapsed_seconds':perf_counter()-started,
            'code_generated':False,'Q_updated':False}


def run(out,blocks=5):
    """逐重复区组平衡执行，题内四组串行，题间最多四并发；旧失败身份也不覆盖。"""
    meta=verify(out)
    existing=read_rows(out/'rows.jsonl') if (out/'rows.jsonl').exists() else []
    done={(r['task_id'],r['arm'],r['repeat']) for r in existing}
    schedule=[b for b in read(out/'schedule.json') if b['repeat']<=blocks]
    wanted={(b['task_id'],a,b['repeat']) for b in schedule for a in b['arms']}
    if wanted<=done:
        return {'already_saved':len(existing)}
    from methods.sct_trajectory.run_closed_loop import _requester
    requester=_requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=4,selector_max_inflight=4,thinking='disabled')
    specs={s['task_id']:s for s in read(out/'inputs.json')}
    meta['status']='running';write(out/'run_metadata.json',meta)
    started=perf_counter()
    for repeat in range(1,blocks+1):
        jobs=[b for b in schedule if b['repeat']==repeat]
        def execute(block):
            records=[]
            for arm in block['arms']:
                if (block['task_id'],arm,repeat) not in done:
                    records.append(one_selection(specs[block['task_id']],arm,repeat,requester))
            return records
        with ThreadPoolExecutor(max_workers=4) as pool:
            for future in as_completed([pool.submit(execute,b) for b in jobs]):
                for row in future.result():
                    append(out/'rows.jsonl',row);existing.append(row)
                    done.add((row['task_id'],row['arm'],row['repeat']))
                print(json.dumps({'repeat':repeat,'saved':len(existing),'valid':sum(r['status']=='completed' for r in existing)},ensure_ascii=False),flush=True)
        verify(out)
    meta=read(out/'run_metadata.json')
    meta.update(status='completed' if len(existing)==160 else 'partial',saved_rows=len(existing),
                valid_rows=sum(r['status']=='completed' for r in existing),
                segments=meta.get('segments',[])+[{'wall_seconds':perf_counter()-started,'saved_total':len(existing)}])
    write(out/'run_metadata.json',meta)


def distance(left,right):
    union=set(left)|set(right)
    return 1-len(set(left)&set(right))/len(union) if union else 0.0


def within(values):
    return float(np.mean([distance(a,b) for a,b in itertools.combinations(values,2)])) if len(values)>=2 else None


def effect_from_matrix(matrix,labels):
    left=np.flatnonzero(labels);right=np.flatnonzero(~np.asarray(labels,dtype=bool))
    between=float(matrix[np.ix_(left,right)].mean())
    a=matrix[np.ix_(left,left)];b=matrix[np.ix_(right,right)]
    wa=float(a.sum()/(len(left)*(len(left)-1)))
    wb=float(b.sum()/(len(right)*(len(right)-1)))
    return between-(wa+wb)/2,between,wa,wb


def compare(groups,test,control,seed=20261019):
    """以题族为单位估计超额集合差异；区组内交换组标签，不把25个卡集对当独立样本。"""
    effects=[];nulls=[];details=[]
    for identifier,arms in groups.items():
        if len(arms[test])!=5 or len(arms[control])!=5:
            continue
        values=arms[test]+arms[control]
        matrix=np.array([[distance(a,b) for b in values] for a in values])
        observed,between,wa,wb=effect_from_matrix(matrix,[True]*5+[False]*5)
        possible=[]
        for bits in itertools.product((False,True),repeat=5):
            possible.append(effect_from_matrix(matrix,list(bits)+[not b for b in bits])[0])
        effects.append(observed);nulls.append(possible)
        details.append({'task_id':identifier,'test':test,'control':control,'between':between,
                        'within_test':wa,'within_control':wb,'excess_distance':observed})
    if not effects:
        return {'test':test,'control':control,'complete_families':0},details
    rng=np.random.default_rng(seed);effect=float(np.mean(effects))
    samples=rng.choice(effects,size=(10000,len(effects)),replace=True).mean(axis=1)
    perm=np.stack([rng.choice(v,size=19999) for v in nulls],axis=1).mean(axis=1)
    return {'test':test,'control':control,'complete_families':len(effects),
            'excess_distance':effect,'between':float(np.mean([d['between'] for d in details])),
            'within_test':float(np.mean([d['within_test'] for d in details])),
            'within_control':float(np.mean([d['within_control'] for d in details])),
            'ci95_families':np.quantile(samples,[.025,.975]).tolist(),
            'p_block_permutation':float((1+np.sum(perm>=effect-1e-12))/20000)},details


def holm(values):
    order=sorted(range(len(values)),key=lambda i:values[i]['p_block_permutation']);previous=0
    for rank,index in enumerate(order):
        previous=max(previous,min(1.0,(len(order)-rank)*values[index]['p_block_permutation']))
        values[index]['p_holm']=previous


def report(out):
    """输出真实选择波动、排序差异与成本；本研究没有代码成绩或采用/实现测量。"""
    verify(out)
    specs=read(out/'inputs.json');rows=read_rows(out/'rows.jsonl')
    assert len({(r['task_id'],r['arm'],r['repeat']) for r in rows})==len(rows)
    groups={s['task_id']:{a:[] for a in ARMS} for s in specs};arm_rows=[];frequency=[]
    by_id={s['task_id']:s for s in specs}
    learned={n.invariant_id:n.q_value for n in load_memory(PARENT/'observe/frozen/m_star_q.jsonl')}
    for row in sorted(rows,key=lambda r:r['repeat']):
        if row['status']=='completed':
            assert row['selected_ids'] is not None
            assert set(row['selected_ids'])<=set(by_id[row['task_id']]['first_trace']['candidate_ids'])
            groups[row['task_id']][row['arm']].append(row['selected_ids'])
    for identifier,arms in groups.items():
        spec=by_id[identifier]
        for arm,values in arms.items():
            signatures=Counter(tuple(sorted(v)) for v in values)
            counts=Counter(i for v in values for i in v)
            arm_rows.append({'task_id':identifier,'family_id':spec['family_id'],'arm':arm,'valid_repeats':len(values),
                'unique_sets':len(signatures),'modal_set_frequency':max(signatures.values())/len(values) if values else None,
                'mean_selected':float(np.mean([len(v) for v in values])) if values else None,
                'within_jaccard':within(values),'set_disagreement':float(np.mean([set(a)!=set(b) for a,b in itertools.combinations(values,2)])) if len(values)>1 else None,
                'empty_valid_selections':sum(not v for v in values)})
            for card in spec['first_trace']['candidate_ids']:
                frequency.append({'task_id':identifier,'arm':arm,'card_id':card,'selected_times':counts[card],
                    'valid_repeats':len(values),'selection_frequency':counts[card]/len(values) if values else None,
                    'learned_Q':learned[card],'presentation_rank':spec['orders'][arm].index(card)+1})
    comparisons=[];details=[]
    for test,control in read(CONFIG/'protocol.json')['primary_comparisons']:
        item,cases=compare(groups,test,control);comparisons.append(item);details+=cases
    holm([c for c in comparisons if 'p_block_permutation' in c])
    complete=len(rows)==160 and all(r['status']=='completed' for r in rows)
    for c in comparisons:
        c['detectable_order_effect']=bool(complete and c.get('excess_distance',0)>0
            and c.get('ci95_families',[0])[0]>0 and c.get('p_holm',1)<=.05)
    by_arm={}
    for arm in ARMS:
        rs=[r for r in rows if r['arm']==arm];a=[r for r in arm_rows if r['arm']==arm]
        usage=[u for r in rs for u in r['usage_responses']]
        missing=sum(not isinstance(u,dict) or any(type(u.get(k)) is not int for k in ('prompt_tokens','completion_tokens','total_tokens')) for u in usage)
        by_arm[arm]={'operations':len(rs),'valid':sum(r['status']=='completed' for r in rs),
            'logical_requests':sum(len(r['retrieval_trace']['selector_attempts']) for r in rs),
            'response_count':len(usage),'usage_missing_responses':missing,
            **{k:sum(u[k] for u in usage if isinstance(u,dict) and type(u.get(k)) is int) for k in ('prompt_tokens','completion_tokens','total_tokens')},
            'within_jaccard_macro':float(np.mean([v['within_jaccard'] for v in a if v['within_jaccard'] is not None])),
            'mean_selected':float(np.mean([v['mean_selected'] for v in a if v['mean_selected'] is not None])),
            'unique_sets_per_task':[v['unique_sets'] for v in a]}
    identical=[]
    for spec in specs:
        for left,right in itertools.combinations(ARMS,2):
            if spec['prompts'][left]==spec['prompts'][right]:
                identical.append({'task_id':spec['task_id'],'left':left,'right':right,
                                  'left_within':within(groups[spec['task_id']][left]),
                                  'right_within':within(groups[spec['task_id']][right]),
                                  'left_sets':groups[spec['task_id']][left],'right_sets':groups[spec['task_id']][right]})
    summary={'protocol':PROTOCOL,'expected':160,'rows':len(rows),'valid':sum(r['status']=='completed' for r in rows),
        'complete_valid':complete,'unique_families':8,'by_arm':by_arm,'primary_comparisons':comparisons,
        'identical_prompt_controls':identical,'code_generation_calls':0,'validation_calls':0,'Q_updates':0,
        'new_embedding_calls':0,'currency_actual':None,'errors':dict(Counter(r['error_type'] for r in rows if r['error_type'])),
        'Q_reorders_vs_similarity_detectable':comparisons[1]['detectable_order_effect'],
        'Q_assignment_vs_shuffle_detectable':comparisons[2]['detectable_order_effect'],
        'joint_improvement':'not measured; selection-only study','old_records_preserved':True}
    CURATED.mkdir(parents=True,exist_ok=True)
    for path in (out/'summary.json',CURATED/'summary.json'):
        write(path,summary)
    dump_csv(CURATED/'within_by_task.csv',arm_rows);dump_csv(CURATED/'card_selection_frequencies.csv',frequency)
    dump_csv(CURATED/'pairwise_by_task.csv',details)
    write(CURATED/'manifest.json',read(out/'manifest.json'))
    dump_csv(CURATED/'selections.csv',[{k:r[k] for k in ('task_id','family_id','arm','repeat','status','selected_ids','error_type','elapsed_seconds')} for r in rows])
    write(CURATED/'verification.json',{'input_sources_unchanged':True,'unique_identities':len(rows),
          'common_candidates_and_bodies':True,'same_CWE_shuffle_verified_at_prepare':True,
          'Q_frozen':True,'code_generation':False,'validation':False,'new_embeddings':False,
          'native_selector_protocol':True,'all_operations_valid':complete})
    lines=['# CLE 四臂重复选卡与模型波动分析','',
        f'协议：`{PROTOCOL}`。执行状态：{len(rows)}/160 次，合法选择 {summary["valid"]}/160。8 个历史开发题族，每组每题5次，全部不限三张。','',
        '## 1. 结论','',
        '学习Q相对相似度排序的额外选卡差异：'+('达到预设可检测门槛。' if summary['Q_reorders_vs_similarity_detectable'] else '未达到预设可检测门槛，证据不足。'),
        '学习Q相对同CWE打乱Q的差异：'+('达到预设可检测门槛。' if summary['Q_assignment_vs_shuffle_detectable'] else '未达到预设可检测门槛，证据不足。'),
        '本研究只测选卡集合，不测实际采用、代码落实、检索适用性或Joint；未检出不表示等效，检出也不表示学习Q更有用。','',
        '## 2. 四组及实际操作','',
        'Q0：原24+8候选联集顺序；Q1：相似度顺序；Q2：学习Q融合顺序；Q3：同CWE内打乱(Q,visits)后融合顺序。',
        '复用原固定48题清单的前8题，不看新成绩/改选幅度挑题；初析、公开查询、候选、余弦、卡正文和Q均冻结。只替换候选呈现顺序（短编号随位置变化），Q数值不进入提示。',
        'deepseek-v3.2，temperature=0，thinking disabled，原选择器短编号JSON，实际输出上限256 Token；保留原格式及运输重试，失败不补跑。',
        '5个重复区组，每区组题内四组随机顺序串行、题间4并发，区组间等待全部完成；相同提示不会从缓存返回旧选择。',
        '以原semantic_select的私有函数副本重放召回输入，提示、排序、编号映射由原实现产生；真实调用只执行原select_with_retry，没有调用生成、复析、规划或验证。','',
        '## 3. 自身重复波动','',
        'Jaccard距离（两个选卡集合不重合的程度）0为完全相同，1为完全不重合。只比较成员，不把同成员不同输出顺序当换卡；合法空集与失败分开。','',
        '| 组别 | 合法/计划 | 平均自身距离 | 平均选卡数 | LLM请求 | 回执Token |',
        '|---|---:|---:|---:|---:|---:|']
    for arm,c in by_arm.items():
        lines.append(f'| {arm} | {c["valid"]}/40 | {c["within_jaccard_macro"]:.4f} | {c["mean_selected"]:.2f} | {c["logical_requests"]} | {c["total_tokens"]:,} |')
    lines+=['','## 4. 跨组差异是否超出自身波动','',
        '超额差异＝跨组25对集合的平均距离−两组各10对内部距离的平均值。先逐题计算，再对8个题族等权汇总；正值表示跨组差异比自身波动更大。它不是正确率，也不是“百分之多少选卡由Q造成”。','',
        '| 比较 | 跨组距离 | 两组内部距离 | 超额差异 | 95%题族区间 | 区组置换p | Holm p | 达门 |',
        '|---|---:|---|---:|---|---:|---:|---|']
    for c in comparisons:
        if 'excess_distance' in c:
            lines.append(f'| {c["test"]}−{c["control"]} | {c["between"]:.4f} | {c["within_test"]:.4f}/{c["within_control"]:.4f} | {c["excess_distance"]:.4f} | [{c["ci95_families"][0]:.4f}, {c["ci95_families"][1]:.4f}] | {c["p_block_permutation"]:.5f} | {c["p_holm"]:.5f} | {c["detectable_order_effect"]} |')
    lines+=['','按题族10000次配对重采样；置换在同题、同重复区组内交换两臂标签，19999次随机置换，单侧检验分组是否增加集合分离度；三项预定主要比较作Holm校正。所有160次合法、超额差异为正、区间下界>0且校正p≤0.05才写达到门槛。',
        'Q2−Q0是完整Q排序相对原顺序；Q2−Q1是Q融合相对相似度；Q2−Q3检查Q赋值位置与打乱赋值是否造成可检测差异。打乱Q也是顺序干预，并非无干预。','',
        '## 5. 同提示负对照与逐题记录','',
        f'存在{len(identical)}个同题同提示的组别对，完整集合见summary.identical_prompt_controls。即使这些组输出不同，也不能归功于排序，因为实际提示逐字相同。',
        '逐题自身波动见within_by_task.csv；跨组减自身波动见pairwise_by_task.csv；每张卡在五次中被选几次以及原始Q/位置见card_selection_frequencies.csv。',
        '本报告不从选择频率推断适用性，不把“同CWE”或高Q当正确标签。','',
        '## 6. 成本、错误与证据边界','',
        f'新增LLM逻辑请求{sum(c["logical_requests"] for c in by_arm.values())}次，已回执Token {sum(c["total_tokens"] for c in by_arm.values()):,}；usage缺失响应{sum(c["usage_missing_responses"] for c in by_arm.values())}。新Embedding、初析、标注、生成、验证与Q更新均为0。',
        '货币实付未测量；逻辑请求不等于底层HTTP尝试，未记录的运输消耗不补造。错误分类：'+json.dumps(summary['errors'],ensure_ascii=False)+'。',
        '8个历史开发题族与同一服务的一批调用，仅用于当前选择器和当前冻结输入；不推断其他模型或整库。原有公开契约和检索字段局限保持一致，本次不测其对代码的影响。未新增人工标签。','',
        '## 7. 产物与复现','',
        f'原生选卡记录：`{out.relative_to(ROOT)}/rows.jsonl`，含原retrieval_trace、格式尝试、用量和短ID映射；没有伪造generation或validation字段。',
        '精简结果：`results/curated/cle_selector_repeat_20261019/`。旧690条和新增Q0记录保持原样。','',
        '```powershell','python -X utf8 -m methods.cle_ablation.run_selector_repeat prepare',
        'python -X utf8 -m methods.cle_ablation.run_selector_repeat run',
        'python -X utf8 -m methods.cle_ablation.run_selector_repeat report','```','',
        'prepare只用于新目录；run跳过已保存身份（包括失败），不为提高稳定性补跑；report零API复算。']
    text='\n'.join(lines)+'\n';REPORT.write_text(text,encoding='utf-8');(out/'report.md').write_text(text,encoding='utf-8')
    print(json.dumps({'rows':len(rows),'valid':summary['valid'],'comparisons':comparisons},ensure_ascii=False),flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','report'))
    parser.add_argument('--blocks',type=int,choices=range(1,6),default=5)
    args=parser.parse_args()
    if args.action=='prepare':
        prepare(OUT)
    elif args.action=='run':
        run(OUT,args.blocks)
    else:
        report(OUT)


if __name__=='__main__':
    main()

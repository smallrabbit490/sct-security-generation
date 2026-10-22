"""旧CLE冻结Q的等量选卡诊断：复用P7、首次候选与初析，不更新Q或原始数据。"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import itertools
import json
from pathlib import Path
import random
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

from methods.cle_ablation.runner import ROOT, run_one, load_memory, plt_contract
from methods.cle_ablation.run_memory_q import record_result, shuffled_memory
from methods.cle_ablation.run_memory_q_unlimited import inputs, identity as parent_identity, technical_errors, FIELDS
from methods.cle_ablation.retrieval_q_study import reference_check
from methods.cle_ablation.retrieval_q_metrics import metrics
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.memory_q import rank_candidates
from methods.sct_trajectory.semantic_retrieval import (
    recall_semantic_candidates, query_embedding_text, card_embedding_text, _digest, CACHE_VERSION)
from methods.sct_trajectory.retrieval_hit_study import (
    read_rows, blind_pair, model_judge_prompt, validate_judgment, digest)
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest

PROTOCOL = 'cle-q-equal-k-contract-v1'
CONFIG = ROOT/'configs/cle_memory_q_equal_k_20261019'
OLD = ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
OUT = ROOT/'translation_work/diagnostics/20261019/cle_memory_q/equal_k_v1'
CURATED = ROOT/'results/curated/cle_memory_q_equal_k_20261019'
ARMS = ('Q1', 'Q2', 'Q3')
IMPLEMENTATION_CONSTRAINTS = (
    'Bindings explicitly described in the public task as existing or provided globals are supplied '
    'by the caller. Preserve those exact names and objects. Do not redeclare, reset, replace or '
    'invent default values for existing configuration lists, templates, databases, keys or framework '
    'objects. Read them in the implementation. Perform only mutations explicitly required by the '
    'task, such as an authorized record update; preserving a supplied object does not forbid such '
    'required mutation. Keep the specified function signature, valid inputs, return type and '
    'exception behavior. Do not infer binding values from examples. Implement the requested '
    'function and necessary imports/helpers; do not create test fixtures or example state.'
)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def append(path, item):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(item, ensure_ascii=False)+'\n')


def csv_write(path, items):
    if not items:
        return
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)


def identity():
    result = parent_identity()
    for path in (Path(__file__), CONFIG/'protocol.json'):
        result[str(path.relative_to(ROOT))] = file_digest(path)
    return result


def verify(out):
    meta = read(out/'run_metadata.json')
    if identity() != meta['source_identity']:
        raise RuntimeError('source_changed_after_prepare')
    if file_digest(OLD/'observe/frozen/m_star_q.jsonl') != meta['memory_sha256']:
        raise RuntimeError('frozen_Q_changed')
    return meta


def choose(scores, nodes, k, arm):
    """共同候选内按原融合公式选K张，再用共同余弦顺序呈现；没有三张截断。"""
    values = {n.invariant_id: n.q_value for n in nodes}
    ranked = rank_candidates(scores, values, delta=-1, lambda_q=0 if arm == 'Q1' else .5, limit=None)
    selected = ranked[:k]
    presented = sorted(selected, key=lambda v: (-v['cosine'], v['id']))
    return ranked, [v['id'] for v in presented]


def prepare(out):
    """名单和K在新生成前锁定；只读旧Q1的首次选择数量，不用新成绩或标签调参。"""
    if shutil.disk_usage(out.anchor).free < 3*1024**3:
        raise RuntimeError('insufficient_disk_space')
    out.mkdir(parents=True, exist_ok=False)
    protocol = read(CONFIG/'protocol.json')
    old_manifest = read(OLD/'manifest.json')
    ids = [str(i) for i in old_manifest['development'][:8]]
    old_rows = {}
    with (OLD/'gate/rows.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['arm'] == 'Q1' and row['task_id'] in ids:
                old_rows[row['task_id']] = row['attempts'][0]
    shared = {r['task_id']:r for r in read_rows(OLD/'gate/shared_initial.jsonl') if r['task_id'] in ids}
    nodes = load_memory(OLD/'observe/frozen/m_star_q.jsonl')
    by_node = {n.invariant_id:n for n in nodes}
    _, tasks, pools = inputs()
    assert set(ids) <= set(pools['D_gate']) and len({tasks[i]['family_id'] for i in ids}) == 8
    controls, specs, pairs, mapping = [], [], [], []
    for identifier in ids:
        task = tasks[identifier]
        control = reference_check(task)
        controls.append(control)
        assert control['passed'], 'reference_preflight_failed'
        initial = shared[identifier]['initial_analysis']
        assert all(isinstance(initial.get(k),list) and initial[k] for k in ('vulnerability_hypothesis','functional_invariants'))
        trace = copy.deepcopy(old_rows[identifier]['retrieval_trace'])
        query = {**plt_contract(task), 'threat_analysis':initial, 'current_code':'', 'failure_evidence':{}}
        assert trace['status'] == 'completed' and trace['query_hash'] == _digest(query_embedding_text(query))
        assert len(set(trace['candidate_ids'])) == len(trace['candidate_ids'])
        k = len(trace['selected_ids'])
        specs.append({'task_id':identifier, 'family_id':task['family_id'], 'cwe':str(task['CWE_ID']), 'K':k,
                      'initial_analysis':initial, 'first_trace':trace})
        for score in trace['scores']:
            assert score['content_hash'] == _digest(card_embedding_text(by_node[score['id']]))
        for card_id in trace['candidate_ids']:
            pair = blind_pair(plt_contract(task), json.loads(card_embedding_text(by_node[card_id])))
            content_id = pair['pair_id']
            pair_id = digest({'task_id':identifier, 'card_id':card_id})
            pairs.append({**pair, 'pair_id':pair_id, 'content_id':content_id})
            mapping.append({'task_id':identifier, 'card_id':card_id, 'pair_id':pair_id})
    assert len({p['pair_id'] for p in pairs}) == len(pairs)
    write(out/'manifest.json', {'protocol':PROTOCOL, 'tasks':[{k:s[k] for k in ('task_id','family_id','cwe','K')} for s in specs],
          'arms':list(ARMS), 'repeats':[1,2], 'expected_rows':48, 'source':str(OLD.relative_to(ROOT)),
          'selection':'first eight from prior fixed48 manifest, K=prior Q1 c0 selected count',
          'development_exposure':True, 'independent_confirmation':False})
    write(CONFIG/'manifest.json', read(out/'manifest.json'))
    write(out/'preflight.json', {'passed':True,'reference_checks':controls,'new_model_calls':0})
    write(out/'reused_inputs.json', specs)
    write(out/'pair_mapping.json', mapping)
    (out/'blind_pairs.jsonl').write_text(''.join(json.dumps(p,ensure_ascii=False)+'\n' for p in pairs),encoding='utf-8')
    (out/'memory_q_events.jsonl').write_text('',encoding='utf-8')
    snapshot = identity()
    for name in snapshot:
        destination = out/'source_snapshot'/name
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,destination)
    write(out/'run_metadata.json', {'protocol':PROTOCOL,'status':'prepared','source_identity':snapshot,
          'parameters':protocol,'memory_path':str(OLD/'observe/frozen/m_star_q.jsonl'),
          'memory_sha256':file_digest(OLD/'observe/frozen/m_star_q.jsonl'),
          'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
          'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'shared_initial_and_first_retrieval':'reused; historical cost excluded from new usage',
          'human_labels':'pending; no selection/parameter decision depends on labels',
          'generation_gate':'48 fixed runs independent of human label availability',
          'implementation_constraints':IMPLEMENTATION_CONSTRAINTS,'old_results_modified':False,
          'backend':'original P7 local python -I'})
    print(json.dumps({'prepared':ids,'K':{s['task_id']:s['K'] for s in specs},'blind_pairs':len(pairs)},ensure_ascii=False),flush=True)


def make_provider(task_spec, nodes, arm, embedding):
    """首次查询复用已记录分数；修复轮按本臂代码走原24+8召回，不看其他臂或测试内容。"""
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.ablation import get_config
    by_id = {n.invariant_id:n for n in nodes}
    converter = HskTreeRetriever(HskTree(),ablation=get_config('A7'))
    def provider(query):
        if not query.get('current_code'):
            trace = copy.deepcopy(task_spec['first_trace'])
            assert trace['query_hash'] == _digest(query_embedding_text(query)), 'cached_first_query_changed'
        else:
            trace = {'candidate_ids':[],'selected_ids':[],'excluded':[],'scores':[],'errors':[]}
            recall_semantic_candidates(query,nodes,embedding,1,trace)
        ranked, ids = choose(trace['scores'], nodes, task_spec['K'], arm)
        scores = {s['id']:s for s in trace['scores']}
        # 清除旧LLM选择回执，避免把历史选择或调用伪装成本轮直接排序。
        for key in ('selector_attempts','selected_local_ids','recovered_after_retry','parse_diagnostics'):
            trace.pop(key,None)
        trace.update(status='completed',errors=[],retrieval_mode='direct_equal_k',selector_version=PROTOCOL,
                     selected_ids=ids,presented_candidate_ids=ids,value_ranking=ranked,
                     selection_limit=task_spec['K'],effective_K=len(ids),delta=-1,lambda_q=0 if arm=='Q1' else .5,
                     candidate_order='common_similarity_after_membership_selection',embedding_model='text-embedding-3-large',
                     cache_version=CACHE_VERSION,unselected_ids=[i for i in trace['candidate_ids'] if i not in ids],
                     unselected_basis='deterministic_equal_K_not_model_rejection',selector_calls=0)
        cards = [converter._to_card(query,by_id[i],base=scores[i]['cosine'],llm=None) for i in ids]
        for card in cards:
            card['retrieval_audit'] = trace
        return cards, trace
    return provider


def tracked_request(requester, model, label):
    from methods.sct_trajectory.cost_tracker import CostTracker
    tracker = CostTracker(model)
    tracker.set_stage(label)
    def request(prompt):
        try:
            response = requester(prompt)
        except Exception:
            tracker.record_error('pipeline')
            raise
        tracker.record('pipeline',response)
        return response
    return request, tracker


def accounting(tracker):
    snapshot = tracker.snapshot()
    return {'total':{k:snapshot['total'][k] for k in FIELDS}}


def run(out, task_count=8, repeats=2, workers=4):
    """执行固定48预算中的指定前缀；失败行保留并视为已完成，不写Q、不追加修复。"""
    verify(out)
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    specs = read(out/'reused_inputs.json')[:task_count]
    _, tasks, _ = inputs()
    nodes = load_memory(OLD/'observe/frozen/m_star_q.jsonl')
    before = [n.to_dict() for n in nodes]
    shuffled = shuffled_memory(nodes,20261015,'cwe')
    requester = _requester('deepseek-v3.2',60,max_tokens=4096,max_inflight=workers,thinking='disabled')
    embedding = EmbeddingClient(model='text-embedding-3-large',key_loader=load_key,
                  cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    existing = read_rows(out/'rows.jsonl')
    done = {(r['task_id'],r['arm'],r['repeat']) for r in existing}
    assert len(done) == len(existing)
    jobs = [(s,a,b) for b in range(1,repeats+1) for j,s in enumerate(specs)
            for a in ARMS[(j+b-1)%3:]+ARMS[:(j+b-1)%3] if (s['task_id'],a,b) not in done]
    def one(spec,arm,repeat):
        request, tracker = tracked_request(requester,'deepseek-v3.2',f'{arm}.repeat{repeat}')
        selected_nodes = shuffled if arm=='Q3' else nodes
        start = perf_counter()
        row = run_one('PLT',tasks[spec['task_id']],'P7',request,{'full':selected_nodes},embedding,
                initial_analysis=copy.deepcopy(spec['initial_analysis']),
                retrieval_provider=make_provider(spec,selected_nodes,arm,embedding),
                implementation_constraints=IMPLEMENTATION_CONSTRAINTS)
        record_result(row,tasks[spec['task_id']],arm,'D_gate',perf_counter()-start)
        row.update(protocol=PROTOCOL,repeat=repeat,selection_K=spec['K'],
                   retrieval_mode='direct_equal_k',accounting=accounting(tracker))
        return row
    segments = read(out/'embedding_segments.json') if (out/'embedding_segments.json').exists() else []
    segments.append({})
    meta = read(out/'run_metadata.json')
    write(out/'run_metadata.json',{**meta,'status':'running'})
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(one,*job) for job in jobs]
            for future in as_completed(futures):
                row = future.result()
                append(out/'rows.jsonl',row)
                existing.append(row)
                segments[-1] = embedding.usage
                write(out/'embedding_segments.json',segments)
                write(out/'progress.json',{'rows':len(existing),'target':48,
                    'joint':{a:sum(r['final']['joint'] for r in existing if r['arm']==a) for a in ARMS}})
                print(json.dumps({'rows':len(existing),'task':row['task_id'],'arm':row['arm'],
                                  'repeat':row['repeat'],'joint':row['final']['joint']},ensure_ascii=False),flush=True)
        assert before == [n.to_dict() for n in nodes], 'frozen_Q_mutated'
    finally:
        segments[-1] = embedding.usage
        write(out/'embedding_segments.json',segments)
        write(out/'run_metadata.json',{**meta,'status':'generation_completed' if len(existing)==48 else 'generation_partial',
                                      'rows':len(existing)})
        report(out)


def label(out, workers=4):
    """对共同候选盲评初标，每个可见题卡内容最多一次；复用完全相同历史判断，不代签人工。"""
    verify(out)
    from methods.sct_trajectory.run_closed_loop import _requester
    from methods.sct_trajectory.agent_pipeline import _extract_json, _content
    pairs = read_rows(out/'blind_pairs.jsonl')
    cache = {}
    for history in (ROOT/'translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2',
                    Path('E:/ResearchArchives/sct-security-generation_20261016/原始项目/translation_work/diagnostics/20261014/retrieval_hit_accuracy_v3')):
        pair_file = history/('pairs.jsonl' if (history/'pairs.jsonl').exists() else 'blind_pairs.jsonl')
        labels = {p['pair_id']:p for p in read_rows(history/'model_labels.jsonl') if p.get('label') and not p.get('error_type')}
        for p in read_rows(pair_file):
            if p['pair_id'] in labels:
                cache[digest({'task':p['task'],'card':p['card']})] = labels[p['pair_id']]
    existing = {p['pair_id']:p for p in read_rows(out/'model_labels.jsonl')}
    requester = _requester('gpt-4o',90,max_tokens=1024,max_inflight=workers)
    def judge(pair):
        key = digest({'task':pair['task'],'card':pair['card']})
        if key in cache:
            return {'pair_id':pair['pair_id'],**validate_judgment(cache[key]),'source':'reused_exact_visible_pair',
                    'accounting':{'total':{k:0 for k in FIELDS}}}
        request, tracker = tracked_request(requester,'gpt-4o','blind_judgment')
        try:
            value = validate_judgment(_extract_json(_content(request(model_judge_prompt({'task':pair['task'],'card':pair['card']})))))
            item = {'pair_id':pair['pair_id'],**value,'source':'new_model_estimate'}
        except Exception as exc:
            item = {'pair_id':pair['pair_id'],'label':None,'error_type':type(exc).__name__,'source':'failed_no_retry'}
        return {**item,'accounting':accounting(tracker)}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(judge,p) for p in pairs if p['pair_id'] not in existing]
        for future in as_completed(futures):
            value = future.result()
            append(out/'model_labels.jsonl',value)
            existing[value['pair_id']] = value
            if len(existing)%20==0 or len(existing)==len(pairs):
                print(json.dumps({'labeled':len(existing),'pairs':len(pairs)}),flush=True)
    review = out/'human_review.csv'
    if not review.exists():
        csv_write(review,[{'pair_id':p['pair_id'],'task':json.dumps(p['task'],ensure_ascii=False),
            'card':json.dumps(p['card'],ensure_ascii=False),'ai_label':existing[p['pair_id']].get('label'),
            'ai_reason':existing[p['pair_id']].get('reason',''),'human_label':'','task_evidence':'',
            'card_evidence':'','reason':'','reviewer':'','confirmed_at':''} for p in pairs])
    report(out)


def import_review(out,path):
    """导入真人提供的完整审定文件；不把AI初标转换成人工金标准。"""
    pairs = {p['pair_id'] for p in read_rows(out/'blind_pairs.jsonl')}
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows)!=len(pairs) or {r['pair_id'] for r in rows}!=pairs:
        raise ValueError('review_must_cover_exact_pool')
    checked = []
    for row in rows:
        value = validate_judgment({**row,'label':row['human_label']})
        if value['label']=='insufficient' or not row['reviewer'].strip() or not row['confirmed_at'].strip():
            raise ValueError('review_not_adjudicated')
        checked.append({'pair_id':row['pair_id'],**value,'reviewer':row['reviewer'],'confirmed_at':row['confirmed_at']})
    write(out/'human_labels.json',checked)
    report(out)


def cluster_pair(rows,baseline,test):
    """重复不是独立题；以题族为单位平均两次结果，做符号置换和配对重采样。"""
    families = sorted({r['family_id'] for r in rows})
    deltas = []
    for family in families:
        groups = {a:[r['final']['joint'] for r in rows if r['family_id']==family and r['arm']==a] for a in (baseline,test)}
        if any(len(v)!=2 for v in groups.values()):
            return {'complete':False,'reason':'two_repeats_required_per_family'}
        deltas.append(sum(groups[test])/2-sum(groups[baseline])/2)
    observed = sum(deltas)
    p = sum(abs(sum(sign*d for sign,d in zip(signs,deltas)))>=abs(observed)-1e-12
            for signs in itertools.product((-1,1),repeat=len(deltas)))/2**len(deltas)
    rng = random.Random(20261019)
    samples = sorted(sum(rng.choices(deltas,k=len(deltas)))/len(deltas) for _ in range(10000))
    return {'complete':True,'families':len(families),'mean_joint_difference':observed/len(deltas),
            'paired_family_deltas':deltas,'p_exact_sign_flip':p,'ci95':[samples[249],samples[9749]]}


def report(out):
    """分开生成表现、适用性估计和人工状态；复算使用原指标，不把16次当16道独立题。"""
    specs = read(out/'reused_inputs.json')
    nodes = load_memory(OLD/'observe/frozen/m_star_q.jsonl')
    shuffled = shuffled_memory(nodes,20261015,'cwe')
    rows = read_rows(out/'rows.jsonl')
    mapping = {(v['task_id'],v['card_id']):v['pair_id'] for v in read(out/'pair_mapping.json')}
    universes = {s['task_id']:[mapping[s['task_id'],i] for i in s['first_trace']['candidate_ids']] for s in specs}
    predicted = {a:{s['task_id']:[mapping[s['task_id'],i] for i in choose(s['first_trace']['scores'],
                       shuffled if a=='Q3' else nodes,s['K'],a)[1]] for s in specs} for a in ARMS}
    estimates = {r['pair_id']:r.get('label') for r in read_rows(out/'model_labels.jsonl')}
    human = {r['pair_id']:r.get('label') for r in read(out/'human_labels.json')} if (out/'human_labels.json').exists() else {}
    labeled = {}
    for authority,labels in [('model_estimate',estimates),('human',human)]:
        labeled[authority] = {a:metrics(universes,predicted[a],labels) for a in ARMS}
        for v in labeled[authority].values():
            v['candidate_recall'] = None
            v['candidate_recall_reason'] = 'only_already_recalled_candidates_labeled'
    repeats = {str(b):summarize([r for r in rows if r['repeat']==b],'Q1') for b in (1,2)}
    comparisons = {a:cluster_pair(rows,a,'Q2') for a in ('Q1','Q3')} if len(rows)==48 else {}
    if comparisons:
        previous = 0
        for index,key in enumerate(sorted(comparisons,key=lambda k:comparisons[k]['p_exact_sign_flip'])):
            previous = max(previous,min(1,comparisons[key]['p_exact_sign_flip']*(2-index)))
            comparisons[key]['p_holm'] = previous
    costs = {a:{k:sum(r['accounting']['total'][k] for r in rows if r['arm']==a) for k in FIELDS} for a in ARMS}
    label_rows = read_rows(out/'model_labels.jsonl')
    judge_cost = {k:sum(r['accounting']['total'][k] for r in label_rows) for k in FIELDS}
    segments = read(out/'embedding_segments.json') if (out/'embedding_segments.json').exists() else []
    costs['embedding'] = {k:sum(s.get(k,0) for s in segments) for k in ('calls','total_tokens','failures','usage_missing_calls')}
    result = {'protocol':PROTOCOL,'rows':len(rows),'unique_tasks':len({r['task_id'] for r in rows}),
        'generation_completed':len(rows)==48,'repeats':repeats,'clustered_primary_comparisons':comparisons,
        'technical_errors':technical_errors(rows),'label_metrics':labeled,'human_confirmed':len(human),
        'model_labeled':sum(v in ('direct','conditional','irrelevant','conflict','insufficient') for v in estimates.values()),
        'model_label_errors':sum(not r.get('label') for r in label_rows),
        'candidate_pairs':len(mapping),'cost_by_arm':costs,'judge_cost':judge_cost,
        'actual_currency':None,'memory_updates':False,'full_library_recall':'unmeasured',
        'claim_status':'development_diagnostic_pending_human_labels' if not human else 'development_diagnostic'}
    write(out/'summary.json',result)
    CURATED.mkdir(parents=True,exist_ok=True)
    write(CURATED/'summary.json',result)
    write(CURATED/'manifest.json',read(out/'manifest.json'))
    score_rows = [{'task_id':r['task_id'],'family_id':r['family_id'],'arm':r['arm'],'repeat':r['repeat'],
        'K':r['selection_K'],**{k:r['final'][k] for k in ('functional','security','joint','measured')},
        'declared_adopted':len(r['final'].get('generation',{}).get('cards',[])),'error':r.get('error_type'),
        'calls':r['accounting']['total']['calls'],'tokens':r['accounting']['total']['total_tokens']} for r in rows]
    csv_write(CURATED/'scores.csv',score_rows)
    lines = ['# CLE 冻结Q等量选卡与公开接口约束实验','',f'协议：`{PROTOCOL}`。已完成{len(rows)}/48次P7，独立题目8道、每组每题重复两次。',
        '',f"共同候选池{len(mapping)}个题卡对；AI有效标签{result['model_labeled']}，标签失败{result['model_label_errors']}；人工确认{len(human)}。正式人工四指标待真实复核。",
        '', '| 重复 | 组 | n | F | S | Joint | 完整测量 |','|---|---|---:|---:|---:|---:|---:|']
    for b,s in repeats.items():
        for arm,v in sorted(s['arms'].items()):
            lines.append('| '+b+' | '+arm+' | '+' | '.join(str(v[k]) for k in ('n','functional','security','joint','measured'))+' |')
    lines += ['', '本轮只改变共用公开接口约束和等量直接选卡；入选后用同一余弦顺序呈现，跳过LLM二次选卡。K来自旧相似度组的首次选卡数，三组相同，范围按固定名单，不恢复三张上限。',
        '原8题已在开发池暴露；不能与旧成绩直接拼接为接口约束的因果提升，也不是独立最终测试。修复轮按各自代码检索，只分析首次共同候选的选卡质量。',
        '生成与标签互不调参。人工审定是正式检索指标门，生成结果不依赖标签，可独立完成；不会伪造人工身份。',
        '学习Q和同CWE打乱Q均冻结，模型/参数/原P7验证器不变；最多一次修复，末次交付，不按隐藏测试挑代码。',
        '', '## 配对统计','',json.dumps(comparisons,ensure_ascii=False,indent=2),
        '', '两次重复仍以8个题族为统计单位；给出题族平均差、95%配对重采样区间与双侧符号置换检验，两项主要比较Holm校正。',
        '', '## 用量','',json.dumps({'generation':costs,'blind_judgment':judge_cost},ensure_ascii=False,indent=2),
        '', '旧初析和首次向量结果复用不计本次新调用；按逻辑请求及回执Token记账，无实付账单。不增加Q学习、确认集或Base/Plus。',
        '', '原生rows、代码、验证、检索轨迹、盲评与人工表均在本轮运行区；精简结果见results/curated/cle_memory_q_equal_k_20261019。']
    text = '\n'.join(lines)+'\n'
    (out/'report.md').write_text(text,encoding='utf-8')
    (ROOT/'docs/CLE_Q等量选卡与接口约束实验结果_20261019.md').write_text(text,encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','label','run','report','import-review'))
    parser.add_argument('--out',type=Path,default=OUT)
    parser.add_argument('--tasks',type=int,choices=(2,8),default=8)
    parser.add_argument('--repeats',type=int,choices=(1,2),default=2)
    parser.add_argument('--workers',type=int,choices=range(1,5),default=4)
    parser.add_argument('--labels',type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT/'translation_work/diagnostics').resolve()):
        parser.error('diagnostics_output_required')
    if args.action=='prepare':
        prepare(out)
    elif args.action=='run':
        run(out,args.tasks,args.repeats,args.workers)
    elif args.action=='label':
        label(out,args.workers)
    elif args.action=='report':
        report(out)
    else:
        if args.labels is None:
            parser.error('human_review_file_required')
        import_review(out,args.labels)


if __name__=='__main__':
    main()

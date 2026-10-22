"""旧CLE检索四指标与冻结Q联合研究；人工审定前绝不运行开发/确认生成。"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import csv
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT/'src'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from methods.cle_ablation.retrieval_q_metrics import metrics, retrieval_gate, not_worse, paired_f1_interval
from methods.cle_ablation.runner import plt_contract, run_one
from methods.cle_ablation.run_memory_q import shuffled_memory, record_result
from methods.sct_trajectory.run_memory_q_study import load_inputs, prepare_initial_analysis
from methods.sct_trajectory.retrieval_hit_study import read_rows, make_query, blind_pair, digest, validate_judgment, model_judge_prompt
from methods.sct_trajectory.semantic_retrieval import recall_semantic_candidates, card_embedding_text
from methods.sct_trajectory.memory_q import rank_candidates

CONFIG = ROOT/'configs/cle_retrieval_q_20261017'
DEFAULT_OUT = ROOT/'translation_work/diagnostics/20261017/cle_retrieval_q/v2'
LEARN = ROOT/'translation_work/diagnostics/20261016/cle_memory_q/full_dgrow'
OLD_Q = ROOT/'translation_work/diagnostics/20261016/cle_memory_q/shared_initial8'
ARCHIVE = Path('E:/ResearchArchives/sct-security-generation_20261016/原始项目')
HISTORY = ARCHIVE/'translation_work/diagnostics/20261014/retrieval_hit_accuracy_v3'
MEMORY = LEARN/'frozen/m_star_q.jsonl'
POOLS = ROOT/'configs/cle_memory_q_autonomous_20261015/pools.recovered.json'
SEED = 20261017
MODES = ('original', 'analysis', 'combined')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def append(path, value):
    with Path(path).open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False)+'\n')


def csv_write(path, rows):
    if not rows:
        return
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def inputs():
    nodes,by_id,pools=load_inputs(MEMORY, ROOT/'data/external/secodeplt/secodeplt/data.json',
                       ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json', POOLS)
    overlay=CONFIG/'public_contract_overrides.json'
    if overlay.exists():
        by_id=apply_public_overrides(by_id,read(overlay))
    return nodes,by_id,pools


def apply_public_overrides(by_id,overrides):
    """用户授权的公开依赖补齐只覆盖context；原始任务、参考及测试内容不变。"""
    result=copy.deepcopy(by_id)
    for item in overrides:
        identifier=str(item['task_id'])
        description=result[identifier]['task_description']
        if description.get('context')!=item['original_context']:
            raise ValueError('original_context_changed:'+identifier)
        description['context']=item['original_context']+'\n'+item['append_context']
    return result


def ordered_unique(tasks):
    from methods.sct_trajectory.run_branch_gate_study import stratified_tasks
    seen, result = set(), []
    for task in stratified_tasks(tasks, 0):
        if task['family_id'] not in seen:
            seen.add(task['family_id'])
            result.append(task)
    return result


def inventory(out):
    """阶段A读取原始记录核对来源；不读取凭据，不从汇总生成虚假逐题数据。"""
    out.mkdir(parents=True, exist_ok=True)
    nodes, by_id, pools = inputs()
    old = read(ROOT/'configs/cle_memory_q_autonomous_20261015/manifest.json')
    historical = read(HISTORY/'summary.json')
    old_rows = read_rows(OLD_Q/'compare/rows.jsonl')
    manifest = read(HISTORY/'task_manifest.json')
    retrieval_families = {t['family_id'] for part in manifest.values() for t in part}
    reserved = {by_id[str(i)]['family_id'] for i in old['confirmation']}
    q_eval = set()
    for folder in ('cle_memory_q_autonomous_20261015', 'cle_memory_q_probe8_20261016',
                   'cle_memory_q_shared_initial8_20261016'):
        m = read(ROOT/'configs'/folder/'manifest.json')
        q_eval.update(by_id[str(i)]['family_id'] for i in m.get('development', []))
    mechanism = []
    for row in old_rows:
        for attempt in row['attempts']:
            trace = attempt.get('retrieval_trace') or {}
            generation = attempt.get('generation') or {}
            selected = trace.get('selected_ids', [])
            adopted = [c['invariant_id'] for c in generation.get('cards', [])]
            mechanism.append({'task_id': row['task_id'], 'arm': row['arm'], 'attempt': attempt['attempt'],
                'eligible': trace.get('eligible_count'), 'recalled': len(trace.get('candidate_ids', [])),
                'above_threshold': trace.get('above_threshold_count'),
                'selected_ids': '|'.join(selected), 'adopted_ids': '|'.join(adopted),
                'code_implementation': 'requires_code_review_not_inferred_from_applied_ids',
                'F': attempt.get('functional'), 'S': attempt.get('security'), 'Joint': attempt.get('joint'),
                'error': generation.get('error_type') or attempt.get('error_type'),
                'known_contract_defect': str(row['task_id']) == '1015'})
    csv_write(out/'historical_mechanism.csv', mechanism)
    mapping = []
    for name in ('methods/sct_trajectory/semantic_retrieval.py', 'methods/sct_trajectory/retriever.py',
                 'methods/cle_ablation/runner.py', 'docs/retrieval_hit_accuracy_20261014.md'):
        a, b = ROOT/name, ARCHIVE/name
        mapping.append({'relative_path': name, 'working': str(a), 'archive': str(b),
                        'same_content': a.exists() and b.exists() and a.read_bytes() == b.read_bytes()})
    csv_write(out/'source_mapping.csv', mapping)
    learned = [n for n in nodes if n.q_visits]
    from methods.sct_trajectory.run_branch_gate_study import file_digest
    memory_matches_learning=file_digest(MEMORY)==read(LEARN/'calibration.json')['memory_sha256']
    result = {'protocol': read(CONFIG/'protocol.json')['protocol'], 'raw_plt': len(by_id),
        'pools': {k: len(v) for k,v in pools.items()}, 'cards': len(nodes),
        'learned_cards': len(learned), 'q_updates': sum(n.q_visits for n in nodes),
        'historical_q_rows': len(old_rows), 'historical_attempts': len(mechanism),
        'history_retrieval_tasks': historical['planned_formal_rows']//6,
        'historical_labels_authority': historical['judgment_basis'],
        'reserved_q_evaluation_overlap': sorted(reserved & q_eval),
        'reserved_old_retrieval_family_overlap': sorted(reserved & retrieval_families),
        'reserved_whole_CLE_exposure': 'historical_D_gate_members_not_globally_unseen',
        'old_retrieval_top3': {arm: item['top3'] for arm,item in historical['labels']['model']['arms'].items()},
        'generation_parameters': {k:read(LEARN/'calibration.json')[k] for k in
            ('model','embedding_model','thinking','max_tokens','delta','alpha','lambda_q')},
        'memory_matches_learning':memory_matches_learning,
        'memory_updates': False, 'Base_Plus_access': False,
        'stage_A_passed': len(old_rows)==24 and len(nodes)==1939 and memory_matches_learning}
    write(out/'inventory.json', result)
    return result


def reference_check(task):
    """只用原生本地验证器校准参考代码；测试内容绝不进入公开查询。"""
    from methods.sct_trajectory.closed_loop import validate_and_state
    gt = task['ground_truth']
    evidence, state = validate_and_state(task, gt['code_before']+gt['patched_code']+gt['code_after'], timeout=20)
    setup = ast.parse(task['unittest'].get('setup', ''))
    setup_names = {n.id for n in ast.walk(setup) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
    code = ast.parse(gt['code_before']+gt['patched_code']+gt['code_after'])
    used = {n.id for n in ast.walk(code) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
    public = json.dumps(task['task_description'], ensure_ascii=False)
    undeclared = sorted(name for name in used & setup_names if not re.search(r'\b'+re.escape(name)+r'\b',public))
    return {'task_id':str(task['index']), 'state':state,
        'undeclared_setup_bindings':undeclared, 'passed':state=='A' and not undeclared,
        'F':evidence.get('functional',{}).get('status'), 'S':evidence.get('security',{}).get('status')}


def prepare(out):
    """阶段B先固定来源和名单，再作零API参考检查；不按Q或模型分数选题。"""
    if not read(out/'inventory.json')['stage_A_passed']:
        raise ValueError('stage_A_not_passed')
    if (out/'manifest.json').exists():
        raise ValueError('manifest_already_prepared')
    nodes, by_id, pools = inputs()
    config = read(CONFIG/'protocol.json')
    old = read(ROOT/'configs/cle_memory_q_autonomous_20261015/manifest.json')
    excluded = set(old.get('excluded_previous_probe_families', []))
    for folder in ('cle_memory_q_autonomous_20261015','cle_memory_q_probe8_20261016',
                   'cle_memory_q_shared_initial8_20261016'):
        m = read(ROOT/'configs'/folder/'manifest.json')
        excluded.update(by_id[str(i)]['family_id'] for key in ('development','confirmation') for i in m.get(key,[]))
    candidates = ordered_unique([by_id[i] for i in pools['D_gate'] if by_id[i]['family_id'] not in excluded])
    decisions = read(CONFIG/'contract_review.json')
    screening, development = [], []
    for task in candidates:
        key = str(task['index'])
        decision = decisions.get(key, {'qualified':False,'reason':'公开契约尚未完成逐项核实，不作为合格题纳入；不表示该题已证明错误'})
        record = {'task_id':key,'family_id':task['family_id'],'cwe':str(task['CWE_ID']),**decision}
        if decision['qualified']:
            record['reference'] = reference_check(task)
            record['qualified'] = record['reference']['passed']
            if record['qualified']:
                development.append(key)
        screening.append(record)
        if len(development)==8:
            break
    calibration = [str(t['index']) for t in ordered_unique([by_id[i] for i in pools['D_grow']])[:6]]
    controls = [reference_check(by_id[i]) for i in calibration]
    qualified = len(development)==8 and all(c['passed'] for c in controls)
    manifest = {'protocol':config['protocol'],'calibration':calibration,'development':development,
                'confirmation':[str(i) for i in old['confirmation']], 'confirmation_opened':False,
                'families':{i:by_id[i]['family_id'] for i in calibration+development+[str(x) for x in old['confirmation']]},
                'selection':'CWE/string-ID round robin; unique inferred families; public-contract qualification only',
                'prepared':qualified,'parameters':config,'screening':screening,'calibration_reference':controls}
    groups = [{by_id[i]['family_id'] for i in manifest[k]} for k in ('calibration','development','confirmation')]
    if any(groups[i]&groups[j] for i in range(3) for j in range(i)):
        raise ValueError('study_family_overlap')
    write(out/'manifest.json',manifest)
    write(CONFIG/'manifest.json',manifest)
    write(out/'status.json',{'stage':'prepared' if qualified else 'qualification_failed',
                            'next':'retrieve' if qualified else 'stop_no_API'})
    write(out/'gate_B.json',{'passed':False,'reason':'retrieval_and_human_labels_required' if qualified else
        'calibration_contract_defect_no_API','failed_calibration_tasks':[c['task_id'] for c in controls if not c['passed']]})
    # 最小复现快照；沿用项目已有实验身份机制，不复制其他源码/运行区。
    from methods.sct_trajectory.run_branch_gate_study import file_digest
    sources={}
    for relative in ('methods/cle_ablation/retrieval_q_study.py','methods/cle_ablation/retrieval_q_metrics.py',
        'methods/cle_ablation/runner.py','methods/sct_trajectory/semantic_retrieval.py',
        'methods/sct_trajectory/context_pipeline.py','methods/sct_trajectory/memory_q.py'):
        target=out/'source_snapshot'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/relative,target)
        sources[relative]=file_digest(ROOT/relative)
    contract_files={str(p.relative_to(ROOT)):file_digest(p) for p in
        (CONFIG/'protocol.json',CONFIG/'contract_review.json',CONFIG/'public_contract_overrides.json') if p.exists()}
    if (CONFIG/'public_contract_overrides.json').exists():
        shutil.copy2(CONFIG/'public_contract_overrides.json',out/'public_contract_overrides.json')
    write(out/'run_metadata.json',{'protocol':config['protocol'],
        'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
        'HEAD':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source_files':sources,'memory_path':str(MEMORY),'memory_sha256':file_digest(MEMORY),
        'pools_sha256':file_digest(POOLS),'manifest_sha256':file_digest(out/'manifest.json'),
        'config_dir':str(CONFIG),'contract_files':contract_files,
        'original_dataset_sha256':file_digest(ROOT/'data/external/secodeplt/secodeplt/data.json'),
        'Q_updates':False,'parameters':config,'whole_CLE_independent_test':False})
    return manifest


def verify(out):
    """持久化输入和方法身份为复现边界，漂移时停止，不静默混跑。"""
    from methods.sct_trajectory.run_branch_gate_study import file_digest
    meta=read(out/'run_metadata.json')
    if not read(out/'manifest.json')['prepared']:
        raise ValueError('qualification_failed_no_API')
    for path,expected in meta['source_files'].items():
        if file_digest(ROOT/path)!=expected:
            raise ValueError('source_changed_new_protocol_required:'+path)
    for path,expected in meta.get('contract_files',{}).items():
        if file_digest(ROOT/path)!=expected:
            raise ValueError('public_contract_config_changed:'+path)
    if meta.get('original_dataset_sha256') and file_digest(ROOT/'data/external/secodeplt/secodeplt/data.json')!=meta['original_dataset_sha256']:
        raise ValueError('original_dataset_changed')
    if meta.get('config_dir') and Path(meta['config_dir']).resolve()!=CONFIG.resolve():
        raise ValueError('config_dir_does_not_match_run')
    for path,key in ((MEMORY,'memory_sha256'),(POOLS,'pools_sha256'),(out/'manifest.json','manifest_sha256')):
        if file_digest(path)!=meta[key]:
            raise ValueError('input_changed:'+key)
    return meta


def clients(config):
    """通过项目既有凭据加载器调用；不读取或输出密钥内容。"""
    from methods.sct_trajectory.run_closed_loop import _requester,load_key
    from methods.sct_trajectory.run_branch_gate_study import UsageCounter
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    request=UsageCounter(_requester(config['model'],90,max_tokens=4096,max_inflight=1,thinking='disabled'))
    embedding=EmbeddingClient(model=config['embedding_model'],key_loader=load_key,
        cache_path=ROOT/'translation_work/cache/embeddings/cle.sqlite3',timeout=120)
    return request,embedding


def query_for(task,initial,mode):
    # 当前combined输入与P7 provider一致；原题/纯初析遵循历史公开白名单。
    public=plt_contract(task)
    if mode=='combined':
        return {**public,'threat_analysis':initial,'current_code':'','failure_evidence':{}}
    return make_query(public,initial,mode)


def collect_task(out,task,initial,nodes,embedding,phase):
    """固定共同评价池，随机未返回卡不冒充完整全库召回金标准。"""
    traces={}
    for mode in MODES:
        trace={'excluded':[]}
        eligible,_,_=recall_semantic_candidates(query_for(task,initial,mode),nodes,embedding,3,trace)
        traces[mode]=trace
    union=set().union(*(set(t['candidate_ids']) for t in traces.values()))
    remaining=sorted(set(eligible)-union)
    rng=random.Random(f'{SEED}:{task["index"]}')
    random_ids=rng.sample(remaining,min(16,len(remaining)))
    universe=sorted(union|set(random_ids))
    by_node={n.invariant_id:n for n in nodes}
    pairs=[]
    for identifier in universe:
        pair=blind_pair(plt_contract(task),json.loads(card_embedding_text(by_node[identifier])))
        pair.update(task_id=str(task['index']),card_id=identifier,phase=phase,
                    origin='random_unreturned' if identifier in random_ids else 'retrieval_union')
        pairs.append(pair)
    for pair in pairs:
        append(out/'pairs.jsonl',pair)
    record={'task_id':str(task['index']),'phase':phase,'traces':traces,
            'pair_ids':[p['pair_id'] for p in pairs],
            'card_to_pair':{p['card_id']:p['pair_id'] for p in pairs}}
    append(out/'retrieval.jsonl',record)
    return record


def retrieve(out,phase):
    """一次初析，多查询共用；任何技术失败记终态，禁止换题重试。"""
    meta=verify(out);manifest=read(out/'manifest.json')
    if phase=='confirmation' and not (out/'confirmation_lock.json').exists():
        raise ValueError('confirmation_not_opened')
    if (out/'retrieval_errors.jsonl').exists():
        raise ValueError('recorded_technical_failure_stop')
    nodes,by_id,_=inputs();request,embedding=clients(meta['parameters'])
    contexts={r['task_id']:r for r in read_rows(out/'contexts.jsonl')}
    finished={r['task_id'] for r in read_rows(out/'retrieval.jsonl')}
    phases=('calibration','development') if phase=='all' else (phase,)
    try:
        for part in phases:
            for identifier in manifest[part]:
                if identifier in finished:
                    continue
                task=by_id[identifier]
                if identifier not in contexts:
                    initial=prepare_initial_analysis({'task_description':plt_contract(task)},request)
                    item={'task_id':identifier,'analysis':initial,'phase':part}
                    append(out/'contexts.jsonl',item);contexts[identifier]=item
                collect_task(out,task,contexts[identifier]['analysis'],nodes,embedding,part)
                print(json.dumps({'retrieved':identifier,'phase':part}),flush=True)
    except Exception as exc:
        append(out/'retrieval_errors.jsonl',{'phase':part,'task_id':identifier,'error_type':type(exc).__name__})
        write(out/'status.json',{'stage':'technical_failure','next':'stop_no_retry','error_type':type(exc).__name__})
        raise
    finally:
        write(out/'retrieval_cost.json',{'initial_analysis':request.snapshot(),'embedding':embedding.usage})
    write(out/'status.json',{'stage':'retrieved','next':'export-review','human_required':True})


def export_review(out):
    """独立盲评初标与人工表分开；同一pair一次AI判断，失败不补调用。"""
    meta=verify(out)
    from methods.sct_trajectory.run_closed_loop import _requester
    from methods.sct_trajectory.agent_pipeline import _content,_extract_json
    from methods.sct_trajectory.run_branch_gate_study import UsageCounter
    pairs=read_rows(out/'pairs.jsonl')
    if len({p['pair_id'] for p in pairs})!=len(pairs):
        raise ValueError('duplicate_pairs')
    expected=set(read(out/'manifest.json')['calibration']+read(out/'manifest.json')['development'])
    if not expected<={r['task_id'] for r in read_rows(out/'retrieval.jsonl')} or (out/'retrieval_errors.jsonl').exists():
        raise ValueError('incomplete_or_failed_retrieval_no_judging')
    old_pairs={digest({'task':p['task'],'card':p['card']}):p['pair_id'] for p in read_rows(HISTORY/'blind_pairs.jsonl')}
    old_labels={p['pair_id']:p for p in read_rows(HISTORY/'model_labels.jsonl') if not p.get('error_type') and p.get('label')}
    existing={p['pair_id']:p for p in read_rows(out/'model_labels.jsonl')}
    request=UsageCounter(_requester(meta['parameters']['judge_model'],90,max_tokens=1024,max_inflight=4))
    def judge(pair):
        visible={'task':pair['task'],'card':pair['card']}
        old=old_labels.get(old_pairs.get(digest(visible)))
        if old:
            return {'pair_id':pair['pair_id'],**validate_judgment(old),'source':'reused_exact_public_pair_v3'}
        try:
            judgment=validate_judgment(_extract_json(_content(request(model_judge_prompt(visible)))))
            return {'pair_id':pair['pair_id'],**judgment,'source':'new_blind_model_estimate'}
        except Exception as exc:
            return {'pair_id':pair['pair_id'],'label':None,'error_type':type(exc).__name__,'source':'failed_no_retry'}
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures=[executor.submit(judge,p) for p in pairs if p['pair_id'] not in existing]
            for future in as_completed(futures):
                item=future.result();append(out/'model_labels.jsonl',item);existing[item['pair_id']]=item
                if len(existing)%20==0:
                    print(json.dumps({'labeled':len(existing),'total':len(pairs)}),flush=True)
    finally:
        previous=read(out/'judge_cost.json') if (out/'judge_cost.json').exists() else []
        write(out/'judge_cost.json',previous+[request.snapshot()])
    review=out/('human_review_confirmation.csv' if any(p['phase']=='confirmation' for p in pairs) else 'human_review.csv')
    if not review.exists():
        confirmed={p['pair_id']:p for p in read(out/'human_labels.json')} if (out/'human_labels.json').exists() else {}
        review_rows=[{'pair_id':p['pair_id'],'task':json.dumps(p['task'],ensure_ascii=False),
            'card':json.dumps(p['card'],ensure_ascii=False),'ai_label':existing[p['pair_id']].get('label'),
            'ai_reason':existing[p['pair_id']].get('reason',''), 'human_label':'',
            'task_evidence':'','card_evidence':'','reason':'','reviewer':'','confirmed_at':''} for p in pairs]
        for row in review_rows:
            if row['pair_id'] in confirmed:
                old=confirmed[row['pair_id']]
                row.update({k:old[k] for k in ('task_evidence','card_evidence','reason','reviewer','confirmed_at')})
                row['human_label']=old['label']
        csv_write(review,review_rows)
    write(out/'status.json',{'stage':'awaiting_human_review','pairs':len(pairs),'review_file':str(review),
        'next':'human edits copy, then import-review --labels <CSV>','model_errors':sum(bool(p.get('error_type')) for p in existing.values())})


def import_review(out,path):
    """只导入用户提供的人工审定文件，Agent不生成reviewer或确认时间。"""
    verify(out)
    with path.open(encoding='utf-8-sig',newline='') as stream:
        rows=list(csv.DictReader(stream))
    expected={p['pair_id'] for p in read_rows(out/'pairs.jsonl')}
    if len(rows)!=len(expected) or {r['pair_id'] for r in rows}!=expected:
        raise ValueError('human_labels_must_cover_exact_pool_once')
    for row in rows:
        judgment=validate_judgment({**row,'label':row['human_label']})
        if judgment['label']=='insufficient' or not row.get('reviewer','').strip() or not row.get('confirmed_at','').strip():
            raise ValueError('human_adjudication_incomplete')
    write(out/'human_labels.json',[{'pair_id':r['pair_id'],**validate_judgment({**r,'label':r['human_label']}),
                                 'reviewer':r['reviewer'],'confirmed_at':r['confirmed_at']} for r in rows])
    write(out/'status.json',{'stage':'human_labels_imported','next':'summarize'})


def label_map(out,human):
    rows=read(out/'human_labels.json') if human and (out/'human_labels.json').exists() else (
        [] if human else read_rows(out/'model_labels.jsonl'))
    return {r['pair_id']:r.get('label') for r in rows}


def evaluate_setting(records,labels,mode,delta,q_values,lambda_q=0):
    universes={r['task_id']:r['pair_ids'] for r in records};predictions={};candidates={}
    for r in records:
        mapping=r['card_to_pair'];scores=r['traces'][mode]['scores']
        ranked=rank_candidates(scores,q_values,delta=delta,lambda_q=lambda_q)
        predictions[r['task_id']]=[mapping[s['id']] for s in ranked]
        candidates[r['task_id']]=[mapping[s['id']] for s in scores]
    return metrics(universes,predictions,labels,candidates),predictions


def summarize(out):
    """阶段C只在人工校准标签完整时锁定R*；AI估计不能越过人工门。"""
    meta=verify(out);nodes,_,_=inputs();config=meta['parameters']
    records=read_rows(out/'retrieval.jsonl');q={n.invariant_id:n.q_value for n in nodes}
    results={'full_library_recall':'unmeasured','label_authority':'human' if (out/'human_labels.json').exists() else 'model_estimate_pending_human_review'}
    for authority in ('model','human'):
        labels=label_map(out,authority=='human')
        results[authority]={}
        for phase in ('calibration','development','confirmation'):
            selected=[r for r in records if r['phase']==phase]
            results[authority][phase]={name:evaluate_setting(selected,labels,mode,config['delta'],q)[0]
                for name,mode in (('R0','combined'),('R-query','original'))} if selected else {}
    write(out/'retrieval_metrics.json',results)
    calibration=[r for r in records if r['phase']=='calibration']
    development=[r for r in records if r['phase']=='development']
    labels=label_map(out,True)
    manifest=read(out/'manifest.json')
    expected=set(manifest['calibration']+manifest['development'])
    all_pairs={p for r in calibration+development for p in r['pair_ids']}
    if {r['task_id'] for r in calibration+development}!=expected or not all_pairs<=labels.keys():
        write(out/'gate_B.json',{'passed':False,'reason':'complete_retrieval_and_human_labels_required',
            'missing_human_pairs':len(all_pairs-labels.keys()),'next':'human_review_not_paid_generation'})
        return results
    base=evaluate_setting(calibration,labels,'combined',config['delta'],q)[0]
    if not base['counts'].get('positive'):
        write(out/'gate_B.json',{'passed':False,'reason':'no_direct_positive_in_calibration_stop'})
        return results
    threshold_values={-1.0,config['delta']}|{s['cosine'] for r in calibration for s in r['traces']['combined']['scores']}
    best=None
    for delta in sorted(threshold_values):
        score=evaluate_setting(calibration,labels,'combined',delta,q)[0]
        if score['f1'] is not None and not_worse(score,base,'conflict_rate'):
            item=(score,delta)
            if best is None or (score['f1'],-abs(delta-config['delta']),-delta)>(best[0]['f1'],-abs(best[1]-config['delta']),-best[1]):
                best=item
    choices=[('R0','combined',config['delta'],base)]
    raw=evaluate_setting(calibration,labels,'original',config['delta'],q)[0]
    if retrieval_gate(raw,base):choices.append(('R-query','original',config['delta'],raw))
    if best and retrieval_gate(best[0],base):choices.append(('R-threshold','combined',best[1],best[0]))
    choice=max(choices,key=lambda x:(x[3]['f1'],x[0]=='R-query',x[0]=='R0'))
    selected={'setting':choice[0],'query_mode':choice[1],'delta':choice[2],
              'calibration_metrics':choice[3],'basis':'human_calibration_only','frozen':True}
    if (out/'selection.json').exists() and read(out/'selection.json')!=selected:
        raise ValueError('selection_already_locked_no_retuning')
    write(out/'selection.json',selected)
    write(out/'gate_B.json',{'passed':True,'next':'run-development','human_pairs':len(labels)})
    return results


def arm_specs(selection,config):
    """R*=R0时合并A/B，生成次数不为重复对照翻倍。"""
    arms={'B':{'mode':selection['query_mode'],'delta':selection['delta'],'lambda_q':0,'shuffle':False},
          'C':{'mode':selection['query_mode'],'delta':selection['delta'],'lambda_q':.5,'shuffle':False},
          'D':{'mode':selection['query_mode'],'delta':selection['delta'],'lambda_q':.5,'shuffle':True}}
    if selection['setting']!='R0':
        arms={'A':{'mode':'combined','delta':config['delta'],'lambda_q':0,'shuffle':False},**arms}
    return arms


def phase_metrics(out,phase,arms):
    """只比较锁定的首次查询；修复轮不作为新增独立测量。"""
    records=[r for r in read_rows(out/'retrieval.jsonl') if r['phase']==phase]
    labels=label_map(out,True);nodes,_,_=inputs()
    q={n.invariant_id:n.q_value for n in nodes}
    shuffled={n.invariant_id:n.q_value for n in shuffled_memory(nodes,20261015,'cwe')}
    return {a:evaluate_setting(records,labels,s['mode'],s['delta'],shuffled if s['shuffle'] else q,s['lambda_q'])[0]
            for a,s in arms.items()}


def development_gate(out):
    """分开检索/Q推进门；未发生的采纳和代码落实不能从成功分数推断。"""
    manifest=read(out/'manifest.json');selection=read(out/'selection.json')
    arms=arm_specs(selection,manifest['parameters'])
    rows=read_rows(out/'development/rows.jsonl')
    group={a:{str(r['task_id']):r for r in rows if r['arm']==a} for a in arms}
    complete=all(set(items)==set(manifest['development']) for items in group.values())
    valid=complete and all(r['final'].get('measured') and not r.get('error_type') and
              all(a.get('generation',{}).get('workflow_completed') and not a.get('generation',{}).get('error_type')
                  for a in r['attempts']) for r in rows)
    readouts=phase_metrics(out,'development',arms)
    result={'complete':complete,'technical_gate':valid,'retrieval_passed':False,'q_passed':False,
            'next':'stop_development_only','metrics':readouts}
    if not valid or not all(m['complete'] for m in readouts.values()):
        result['reason']='incomplete_measurement_workflow_or_human_labels'
        write(out/'gate_D.json',result);return result
    total=lambda arm,key:sum(r['final'][key] for r in group[arm].values())
    result['retrieval_passed']='A' in arms and retrieval_gate(readouts['B'],readouts['A']) and all(
        total('B',k)>=total('A',k) for k in ('functional','joint'))
    nodes,_,_=inputs();values={n.invariant_id:n.q_value for n in nodes}
    changed,new_adopted,creditable=set(),set(),set()
    checks=read(out/'agent_code_review.json') if (out/'agent_code_review.json').exists() else []
    reviewed={str(x['task_id']):x for x in checks if x.get('card_implemented') is True and x.get('evidence') and x.get('reviewer')}
    mechanism=[]
    for identifier,row in group['C'].items():
        for attempt in row['attempts']:
            trace=attempt.get('retrieval_trace') or {}
            sim=[s['id'] for s in rank_candidates(trace.get('scores',[]),values,delta=selection['delta'],lambda_q=0)]
            chosen=trace.get('selected_ids',[])
            adopted={c['invariant_id'] for c in attempt.get('generation',{}).get('cards',[])}
            added=set(chosen)-set(sim)
            if chosen!=sim:changed.add(identifier)
            if added & adopted:new_adopted.add(identifier)
            rescue=row['final']['joint'] and not group['B'][identifier]['final']['joint']
            if rescue and added & adopted and identifier in reviewed:creditable.add(identifier)
            mechanism.append({'task_id':identifier,'attempt':attempt['attempt'],'same_query_similarity':sim,
                'actual_q_selected':chosen,'adopted':sorted(adopted),'new_adopted':sorted(added & adopted),
                'rescue_vs_B':bool(rescue),'code_review':reviewed.get(identifier)})
    write(out/'development/mechanism.json',mechanism)
    quality=all(not_worse(readouts['C'],readouts[b],key) for b in ('B','D')
                for key in ('accuracy','precision','recall','f1'))
    result.update(changed_tasks=len(changed),new_adopted_tasks=len(new_adopted),
                  code_supported_rescues=len(creditable),q_quality_not_worse=quality)
    result['q_passed']=all(total('C','joint')>total(b,'joint') for b in ('B','D')) and (
        total('C','functional')>=total('B','functional') and len(changed)>=3 and
        len(new_adopted)>=2 and bool(creditable) and quality)
    if result['retrieval_passed'] or result['q_passed']:
        result['next']='run-confirmation'
    elif new_adopted:
        result['reason']='Q_intervened_benefit_not_established'
    else:
        result['reason']='insufficient_Q_intervention_not_universal_ineffectiveness'
    write(out/'gate_D.json',result)
    return result


def run_phase(out,phase):
    """原P7入口执行冻结对照；人工门、试运行门和确认门失败均不付费续跑。"""
    meta=verify(out)
    if not (out/'gate_B.json').exists() or not read(out/'gate_B.json')['passed']:
        raise ValueError('human_gate_B_not_passed_no_paid_generation')
    config=meta['parameters'];selection=read(out/'selection.json');manifest=read(out/'manifest.json')
    arms=arm_specs(selection,config)
    if phase=='confirmation':
        gate=development_gate(out)
        if not gate['retrieval_passed'] and not gate['q_passed']:
            raise ValueError('development_gate_failed_no_confirmation')
        if not gate['q_passed']:
            arms={a:s for a,s in arms.items() if a in ('A','B')}
        elif not gate['retrieval_passed']:
            arms={a:s for a,s in arms.items() if a in ('B','C','D')}
        if (out/'confirmation_lock.json').exists():
            raise ValueError('confirmation_one_execution_only')
    target=out/phase
    if target.exists():
        raise ValueError('phase_already_started_no_retry_or_overwrite')
    nodes,by_id,_=inputs();before=[n.to_dict() for n in nodes]
    if phase=='confirmation':
        controls=[reference_check(by_id[i]) for i in manifest['confirmation']]
        write(out/'confirmation_preflight.json',controls)
        # 自动检查只核对部分公开契约；须有逐题审查理由，不能把参考通过当充分条件。
        decisions=read(CONFIG/'contract_review.json')
        unresolved=[i for i in manifest['confirmation'] if not decisions.get(i,{}).get('qualified')]
        if not all(c['passed'] for c in controls) or unresolved:
            write(out/'status.json',{'stage':'confirmation_contract_blocked','unresolved':unresolved})
            raise ValueError('confirmation_contract_not_qualified_no_replacement')
        write(out/'confirmation_lock.json',{'arms':arms,'selection':selection,'manifest':manifest['confirmation'],
            'source_files':meta['source_files'],'primary_comparisons':['C-B','C-D'] if 'C' in arms else ['B-A'],
            'no_tuning':True,'role':'Q_reserved_confirmation_historical_CLE_exposure'})
    target.mkdir()
    write(target/'run_metadata.json',{'phase':phase,'arms':arms,'parameters':config,'Q_updates':False,
        'workflow':'native P7 shared c0 independent c1','task_ids':manifest[phase]})
    request,embedding=clients(config)
    placebo=shuffled_memory(nodes,20261015,'cwe')
    contexts={r['task_id']:r['analysis'] for r in read_rows(out/'contexts.jsonl')}
    completed=[];errors=[]
    try:
        for position,identifier in enumerate(manifest[phase]):
            task=by_id[identifier]
            if identifier not in contexts:
                contexts[identifier]=prepare_initial_analysis({'task_description':plt_contract(task)},request)
                append(out/'contexts.jsonl',{'task_id':identifier,'analysis':contexts[identifier],'phase':phase})
                collect_task(out,task,contexts[identifier],nodes,embedding,phase)
            order=list(arms);order=order[position%len(order):]+order[:position%len(order)]
            for arm in order:
                spec=arms[arm];started=perf_counter()
                row=run_one('PLT',task,'P7',request,{'full':placebo if spec['shuffle'] else nodes},embedding,
                    retrieval_mode='semantic_q' if spec['lambda_q'] else 'semantic_sim',
                    delta=spec['delta'],lambda_q=spec['lambda_q'],initial_analysis=contexts[identifier],
                    retrieval_query_mode=spec['mode'])
                record_result(row,task,'Q2' if arm=='C' else 'Q3' if arm=='D' else 'Q1','D_gate',perf_counter()-started)
                row['arm']=arm;append(target/'rows.jsonl',row);completed.append(row)
                first=row['attempts'][0].get('retrieval_trace') or {}
                expected=next(r for r in read_rows(out/'retrieval.jsonl') if r['task_id']==identifier)['traces'][spec['mode']]
                if first.get('query_hash')!=expected.get('query_hash') or first.get('scores')!=expected.get('scores'):
                    errors.append({'task_id':identifier,'arm':arm,'error':'first_query_candidate_mismatch'})
                if row.get('error_type') or not row['final'].get('measured') or any(
                    not a.get('generation',{}).get('workflow_completed') or a.get('generation',{}).get('error_type') for a in row['attempts']):
                    errors.append({'task_id':identifier,'arm':arm,'error':'workflow_or_measurement_failure'})
                print(json.dumps({'phase':phase,'task':identifier,'arm':arm,'joint':row['final']['joint']}),flush=True)
                if errors:
                    break
            if errors:
                break
            if position==1:
                write(target/'smoke_gate.json',{'passed':True,'tasks':manifest[phase][:2]})
    except Exception as exc:
        errors.append({'error':type(exc).__name__})
        raise
    finally:
        if [n.to_dict() for n in nodes]!=before:
            raise RuntimeError('frozen_memory_changed')
        from methods.direction_screening.protocol import summarize as native_summary
        write(target/'summary.json',native_summary(completed,'B'))
        per_arm={a:{k:sum(r['usage'].get(k,0) for r in completed if r['arm']==a)
                          for k in ('calls','failed_calls','prompt_tokens','completion_tokens','total_tokens')} for a in arms}
        snapshot=request.snapshot()
        shared={k:(snapshot.get(k)-sum(v[k] for v in per_arm.values())) if snapshot.get(k) is not None else None
                for k in ('calls','failed_calls','prompt_tokens','completion_tokens','total_tokens')}
        write(target/'cost.json',{'llm':snapshot,'embedding':embedding.usage,
            'shared_initial_this_phase':shared,'development_initial_cost_source':'../retrieval_cost.json',
            'per_arm':per_arm})
        write(target/'format_check.json',{'native_rows':len(completed),'expected_rows':len(manifest[phase])*len(arms),
            'complete':len(completed)==len(manifest[phase])*len(arms),'errors':errors,'memory_unchanged':True})
        write(out/'status.json',{'stage':phase+'_technical_stop' if errors else phase+'_completed',
            'next':'report' if errors else 'summarize','errors':errors})
    if phase=='development':
        development_gate(out)


def report(out):
    """阶段报告明确当前硬门；不会把未启动阶段写成已完成或自动生成科研结论。"""
    inv=read(out/'inventory.json');status=read(out/'status.json') if (out/'status.json').exists() else {}
    manifest=read(out/'manifest.json') if (out/'manifest.json').exists() else {}
    labels=label_map(out,True);pairs=read_rows(out/'pairs.jsonl');model=read_rows(out/'model_labels.jsonl')
    result={'protocol':inv['protocol'],'status':status,'calibration':manifest.get('calibration',[]),
        'development':manifest.get('development',[]),'confirmation_count':len(manifest.get('confirmation',[])),
        'candidate_pairs':len(pairs),'model_labeled':sum(bool(x.get('label')) for x in model),
        'model_errors':sum(bool(x.get('error_type')) for x in model),'human_confirmed':len(labels),
        'whole_library_recall':'unmeasured','Q_relearning':False,'Base_Plus_run':False,
        'P7_development_run':(out/'development/rows.jsonl').exists(),
        'confirmation_run':(out/'confirmation/rows.jsonl').exists()}
    if (out/'development/rows.jsonl').exists():
        development_gate(out)
    if (out/'gate_D.json').exists():result['gate_D']=read(out/'gate_D.json')
    # 确认结果必须连同人工标签与代码落实证据解释；统计只复用原项目精确配对。
    if result['confirmation_run']:
        lock=read(out/'confirmation_lock.json');rows=read_rows(out/'confirmation/rows.jsonl')
        check=read(out/'confirmation/format_check.json')
        from methods.direction_screening.protocol import summarize as native_summary
        qrows=[r for r in rows if r['arm'] in ('B','C','D')]
        compared={}
        for baseline in ('B','D'):
            if 'C' in lock['arms'] and baseline in lock['arms']:
                part=native_summary([r for r in qrows if r['arm'] in (baseline,'C')],baseline)
                compared['C-'+baseline]=part['paired']['C']
                from methods.cle_ablation.report_memory_q import paired_effect
                if {r['task_id'] for r in qrows if r['arm']==baseline}=={r['task_id'] for r in qrows if r['arm']=='C'}:
                    compared['C-'+baseline].update(paired_effect(
                        [r for r in qrows if r['arm'] in (baseline,'C')],baseline,'C'))
                else:
                    compared['C-'+baseline]['incomplete_pairing']=True
        previous=0
        for i,key in enumerate(sorted(compared,key=lambda k:compared[k]['p_exact'])):
            previous=max(previous,min(1,compared[key]['p_exact']*(len(compared)-i)))
            compared[key]['p_holm']=previous
        result['confirmation_comparisons']=compared
        result['confirmation_metrics']=phase_metrics(out,'confirmation',lock['arms'])
        result['confirmation_conclusion']='insufficient_until_complete_human_labels_and_code_review'
        reviews=read(out/'confirmation_code_review.json') if (out/'confirmation_code_review.json').exists() else []
        supported={str(x['task_id']) for x in reviews if x.get('card_implemented') and x.get('evidence') and x.get('reviewer')}
        mechanism_support=False
        for r in qrows:
            if r['arm']!='C' or str(r['task_id']) not in supported:continue
            base=next((b for b in qrows if b['arm']=='B' and b['task_id']==r['task_id']),None)
            if not base or base['final']['joint'] or not r['final']['joint']:continue
            for a in r['attempts']:
                t=a.get('retrieval_trace') or {};values={n.invariant_id:n.q_value for n in inputs()[0]}
                sim={x['id'] for x in rank_candidates(t.get('scores',[]),values,delta=lock['selection']['delta'],lambda_q=0)}
                added=set(t.get('selected_ids',[]))-sim
                adopted={c['invariant_id'] for c in a.get('generation',{}).get('cards',[])}
                mechanism_support=mechanism_support or bool(added & adopted)
        complete_labels=all(m['complete'] for m in result['confirmation_metrics'].values())
        if compared and check['complete'] and not check['errors'] and complete_labels:
            result['confirmation_conclusion']='supported_Q_benefit_under_protocol' if mechanism_support and len(compared)==2 and all(
                x['wins']>x['losses'] and x['p_holm']<=.05 for x in compared.values()) else 'Q_benefit_not_established'
        if 'A' in lock['arms'] and 'B' in lock['arms'] and complete_labels:
            rec=[r for r in read_rows(out/'retrieval.jsonl') if r['phase']=='confirmation'];labs=label_map(out,True)
            q={n.invariant_id:n.q_value for n in inputs()[0]}
            a=lock['arms']['A'];b=lock['arms']['B']
            _,pa=evaluate_setting(rec,labs,a['mode'],a['delta'],q)
            _,pb=evaluate_setting(rec,labs,b['mode'],b['delta'],q)
            result['retrieval_paired_f1_ci95']=paired_f1_interval({r['task_id']:r['pair_ids'] for r in rec},pa,pb,labs)
            native=native_summary([r for r in rows if r['arm'] in ('A','B')],'A')
            result['retrieval_final_code_comparison']=native
            ci=result['retrieval_paired_f1_ci95']['ci95']
            result['retrieval_confirmation_conclusion']='supported_retrieval_quality_improvement' if (
                check['complete'] and not check['errors'] and ci and ci[0]>0 and
                native['arms']['B']['functional']>=native['arms']['A']['functional'] and
                native['arms']['B']['joint']>=native['arms']['A']['joint']) else 'retrieval_improvement_not_established'
    write(out/'summary.json',result)
    config=manifest.get('parameters',{})
    curated=ROOT/config.get('curated_dir','results/curated/cle_retrieval_q_20261017');curated.mkdir(parents=True,exist_ok=True)
    write(curated/'summary.json',result)
    for name in ('inventory.json','gate_B.json','gate_D.json','retrieval_metrics.json','retrieval_cost.json','judge_cost.json'):
        if (out/name).exists():shutil.copy2(out/name,curated/name)
    lines=['# CLE 检索测量与 Q 值联合探索阶段报告','',
        '本报告面向初次接触项目的研究者。当前结论以实际文件为准；未执行的实验不补成绩。','',
        '## 当前执行结果','',f'- 当前状态：`{status.get("stage","inventory_only")}`。',
        f'- 校准题：{result["calibration"]}；开发题：{result["development"]}；预留确认 {result["confirmation_count"]} 题。',
        f'- 共同候选评价对 {len(pairs)} 个；AI 有效初标 {result["model_labeled"]} 个；人工确认 {len(labels)} 个。',
        f'- AI 初标技术失败 {result["model_errors"]} 个；不重试，不将其记为不适用。',
        f'- P7 开发已运行：{result["P7_development_run"]}；预留确认已运行：{result["confirmation_run"]}。','',
        '人工确认未齐时，门槛B不通过，R*不锁定，P7开发与确认不启动。Agent不代签人工标签。','',
        '## 项目和数据入门','',
        f'PLT 是 SeCodePLT（安全编程任务材料）。本地原始 Python 记录 {inv["raw_plt"]} 组；当前清单使用 '
        f'{sum(inv["pools"].values())} 题，按 D_init={inv["pools"]["D_init"]}、D_grow={inv["pools"]["D_grow"]}、D_gate={inv["pools"]["D_gate"]} 划分。'
        '原始数量、入池数量、实际测量数量不能混用。题族由现有元数据推断，不等于已证明的完整真实来源关系。','',
        'Phase 1（冷启动）从来源任务提炼经验；Phase 2（增长）做题、修复并生成经验；'
        'Phase 3（门控）审查候选与历史回归；Phase 4（冻结评测）固定库进行评价。'
        '本研究是固定库检索与Q开发，不执行整套经验演进。Base/Plus是最终评测集合，不参与本轮学习。','',
        '经验卡是可检索的外部建议，模型权重不因本次Q更新而变化。Q值是实际采用后整体代码结果的历史分数，'
        '它不等于单卡已被证明的因果贡献。声明采用也不等于最终代码正确落实。','',
        '## 四指标如何理解','',
        '| 指标 | 候选池内定义 | 通俗解释 |','|---|---|---|',
        '| 准确率 | (TP+TN)/全部评价对 | 选与不选判断正确的比例 |',
        '| 精确率 | TP/(TP+FP) | 选出的卡有多少直接适用 |',
        '| 召回率 | TP/(TP+FN) | 评价池里适用的卡找回多少 |',
        '| F1 | 2TP/(2TP+FP+FN) | 综合精确率和召回率 |','',
        'TP是正确选入，FP是错误选入，FN是漏选，TN是正确未选。分母为零填空并给原因。'
        '评价池是三种查询召回的并集加16张随机未召回卡；全库没有逐卡确认，因此全库召回率仍未测量。'
        '准确率可能被大量不适用卡抬高，不能单独证明机制优秀。','',
        '## 历史现象与复盘','',
        f'核对到 {inv["cards"]} 张冻结卡、{inv["learned_cards"]} 张有Q反馈的卡。历史Q记录有 '
        f'{inv["historical_q_rows"]} 行、{inv["historical_attempts"]} 次代码尝试。',
        '旧检索实验完成199道正式统计任务，六组直接适用精确率约9.1%–12.3%，属于模型估计；'
        '它的模型、向量模型和设置不同，不能代替当前检索测量。',
        '最新历史Q三臂Joint为2/8、3/8、2/8。唯一多成功的1013没有经验卡介入；777和1015改选并采用，'
        '但前者出现上下文覆盖，后者公开变量与夹具不一致。1015保留为缺陷案例，不进入新有效性对照。','',
        '逐题链见运行区 historical_mechanism.csv；代码落实字段保留待核验，不从采用ID自动推断。','',
        '## 门槛与下一步','',
        '1. 人工在复核CSV中确认标签、题目依据、卡片依据、理由、审核者和日期。',
        '2. import-review导入；summarize用6题人工校准标签选择查询或门槛的单项改动。',
        '3. 满足B门后才跑8题P7；前2题出现技术错误即停止。检索改进与Q收益分别判门。',
        '4. 仅通过路线进入预留24题确认；不调参、不追加样本。未显著不能写成等效或普遍无效。','',
        '## 原始产物和复现','',f'运行目录：`{out}`。',
        '统一命令：`python -m methods.cle_ablation.retrieval_q_study <子命令>`；配置目录README列出全部步骤。',
        '原生P7的attempts、generation、validation、retrieval_trace格式保留。按初析、盲评、各臂与Embedding分开记录用量；未核账单不报实付金额。','',
        '权威指标定义：[scikit-learn](https://scikit-learn.org/stable/modules/model_evaluation.html#classification-metrics)；'
        '[Stanford 信息检索教材](https://nlp.stanford.edu/IR-book/html/htmledition/evaluation-of-unranked-retrieval-sets-1.html)。']
    if not manifest.get('prepared',False):
        lines+=['','## 本轮实际触发的停止原因','',
            '阶段B的零API预检发现固定校准题包含未公开的运行上下文。按照批准方案的契约缺陷停止条件，'
            '本轮没有调用初析、向量或盲评API，没有生成候选池，也没有发起人工复核或后续P7。'
            '下列参考代码通过仅证明夹具内能够运行，不证明公开题目可独立复现。','',
            '| 校准题 | 参考F/S | 未公开的夹具绑定 | 本次判定 |','|---|---|---|---|']
        for c in manifest.get('calibration_reference',[]):
            lines.append(f'| {c["task_id"]} | {c["F"]}/{c["S"]} | {", ".join(c["undeclared_setup_bindings"]) or "未发现"} | {"通过有限自动检查" if c["passed"] else "契约未通过"} |')
        lines+=['','6题名单保持不变；未改写公开题面、未补入参考上下文、未按结果换题。'
            '若项目组补齐公开契约，应作为新数据/协议版本，重做受影响预检后再开启实验。'
            '当前8道候选开发题有5道CWE-915且包含相近题型；即使推断family不同，也不能当作覆盖多类问题的代表性样本。']
    if (out/'retrieval_metrics.json').exists():
        scores=read(out/'retrieval_metrics.json')
        lines+=['','## 当前模型辅助估计','','以下数值尚未经人工确认，不用于推进门。',
                '| 阶段 | 设置 | 准确率 | 精确率 | 候选池召回率 | F1 |','|---|---|---|---|---|---|']
        for phase,settings in scores['model'].items():
            for setting,m in settings.items():
                vals=['未定义' if m[k] is None else f'{m[k]:.4f}' for k in ('accuracy','precision','recall','f1')]
                lines.append('| '+' | '.join([phase,setting,*vals])+' |')
    text='\n'.join(lines)+'\n'
    (out/'report_zh.md').write_text(text,encoding='utf-8')
    (ROOT/config.get('report_file','docs/CLE检索与Q联合探索执行报告_20261017.md')).write_text(text,encoding='utf-8')
    (curated/'README.md').write_text(text,encoding='utf-8')
    return result


def main(argv=None):
    global CONFIG
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('inventory','prepare','retrieve','export-review','import-review',
                                        'summarize','run-development','run-confirmation','report'))
    parser.add_argument('--config',type=Path,default=CONFIG)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--phase',choices=('all','calibration','development','confirmation'),default='all')
    parser.add_argument('--labels',type=Path)
    args=parser.parse_args(argv)
    CONFIG=args.config.resolve()
    if not CONFIG.is_relative_to((ROOT/'configs').resolve()):
        parser.error('config_must_be_under_project_configs')
    configured=read(CONFIG/'protocol.json')
    out=(args.out or ROOT/configured.get('run_dir',str(DEFAULT_OUT.relative_to(ROOT)))).resolve()
    if not out.is_relative_to((ROOT/'translation_work/diagnostics').resolve()):
        parser.error('outputs_must_stay_in_ignored_diagnostics')
    if shutil.disk_usage(out.anchor).free<2*1024**3:
        parser.error('less_than_2GiB_free_stop_without_deleting')
    if args.action=='inventory':value=inventory(out)
    elif args.action=='prepare':value=prepare(out)
    elif args.action=='retrieve':value=retrieve(out,args.phase)
    elif args.action=='export-review':value=export_review(out)
    elif args.action=='import-review':
        if not args.labels:parser.error('human_file_required')
        value=import_review(out,args.labels)
    elif args.action=='summarize':value=summarize(out)
    elif args.action=='run-development':value=run_phase(out,'development')
    elif args.action=='run-confirmation':value=run_phase(out,'confirmation')
    else:value=report(out)
    print(json.dumps({'action':args.action,'completed':True,'status_file':str(out/'status.json')},ensure_ascii=False))
    if args.action=='prepare' and not value['prepared']:
        raise SystemExit(2)
    return value


if __name__=='__main__':
    main()

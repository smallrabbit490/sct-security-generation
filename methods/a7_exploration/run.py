"""A7 探索入口：分架构校准记忆、开发外层比较、冻结后的隔离确认。

仅 D_init/D_grow；训练官方反馈仅脱敏进入校准，不用于逐题修复/候选选择。
不写正式长期经验库；无 Docker；全部运行产物在忽略的 diagnostics 目录。
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from methods.direction_screening.run import ROOT,DEFAULT_OUT,CANONICAL,write,read_rows,evaluate
from methods.sct_trajectory.run_closed_loop import _load_tasks,_requester
from .protocol import (ARMS,ARCHITECTURES,NAMES,public_task,sample_families,check_groups,
                       hash_files,check_frozen,summarize)
from .workflow import Session,run_one
from .checks import propose

OUT=ROOT/'translation_work/diagnostics/20261009/a7_exploration'


def implementation_files():
    """缓存/冻结覆盖真实导入依赖及 PLT 原始数据，避免旧校准静默复用。"""
    paths=list(Path(__file__).parent.glob('*.py'))
    for folder in ('methods/direction_screening','methods/sct_trajectory','methods/sct_agent',
                   'methods/sct_lifecycle_replay','methods/cle_ablation_matrix','src/translation_pipeline'):
        paths.extend((ROOT/folder).glob('*.py'))
    paths.extend([ROOT/'data/external/secodeplt/secodeplt/data.json',
        ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json',CANONICAL])
    return sorted(set(paths))


def ensure_signature(path,value):
    if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=value:
        raise ValueError('cached_input_or_implementation_changed:'+str(path))
    write(path,value)


def prepare_data(out):
    """沿用旧开发60，另抽新校准24/确认50，拒绝所有跨组及正式留出 family 交集。"""
    by_id={str(r['index']):r for r in _load_tasks(0)}
    old=json.loads((DEFAULT_OUT/'manifest.json').read_text(encoding='utf-8'))
    canonical=json.loads(CANONICAL.read_text(encoding='utf-8'))
    pools={k:[by_id[str(x['task_id'])] for x in canonical['pools'][k]] for k in ('D_init','D_grow')}
    excluded={x['family_id'] for g in old['groups'].values() for x in g}
    groups={k:[by_id[str(x['task_id'])] for x in old['groups'][k]] for k in ('source','screen','regression')}
    groups['calibration']=sample_families(pools['D_init'],24,excluded)
    groups['confirmation']=sample_families(pools['D_grow'],50,excluded)
    check_groups(groups)
    formal={x['family_id'] for k in ('D_gate','H_pass') for x in canonical['pools'][k]}
    if formal & {r['family_id'] for g in groups.values() for r in g}:
        raise ValueError('formal_holdout_overlap')
    manifest={'schema':'a7-exploration-v1','groups':{k:[{'task_id':r['index'],
        'family_id':r['family_id'],'cwe':str(r['CWE_ID'])} for r in g] for k,g in groups.items()},
        'counts':{k:len(g) for k,g in groups.items()},'formal_holdout_used':False,
        'historically_pristine':False,'confirmation_independent_of_current_selection':True,
        'old_experiment_excluded_families':len(excluded),'arms':list(ARMS),
        'canonical_sha256':hash_files([CANONICAL])[str(CANONICAL.resolve())]}
    if out:
        out.mkdir(parents=True,exist_ok=True)
        path=out/'manifest.json'
        if path.exists() and json.loads(path.read_text(encoding='utf-8'))!=manifest:
            raise ValueError('manifest_conflict')
        write(path,manifest)
    return groups,manifest


def source_bank(out,tasks,workers):
    """重新验证36个训练来源；完整补丁不合格隔离，来源前后文与公开接口一同提供。"""
    path=out/'source_bank.json'
    source_inputs=[ROOT/'data/external/secodeplt/secodeplt/data.json',DEFAULT_OUT/'source_bank.json',
        ROOT/'methods/direction_screening/run.py',ROOT/'methods/sct_agent/validation_evidence.py',
        ROOT/'src/translation_pipeline/persistent_container.py']
    ensure_signature(out/'source_inputs.json',hash_files(source_inputs))
    if path.exists(): return json.loads(path.read_text(encoding='utf-8'))
    old={str(c['source_id']):c for c in json.loads((DEFAULT_OUT/'source_bank.json').read_text(encoding='utf-8'))}
    def one(task):
        card=json.loads(json.dumps(old[str(task['index'])]))
        truth=task['ground_truth']
        context={'prefix':truth.get('code_before',''),'suffix':truth.get('code_after',''),
                 'role':'source skeleton needed to interpret patch; not target environment'}
        evidence={}
        for key,field in (('patched','patched_code'),('vulnerable','vulnerable_code')):
            score=evaluate(task,context['prefix']+truth.get(field,'')+context['suffix'])
            evidence[key]={k:v for k,v in score.items() if k!='code'}
        card.update(source_public=public_task(task),source_code_context=context,source_evidence=evidence)
        card.pop('calibrated_boundaries',None)
        card['quality_status']='qualified' if evidence['patched']['joint'] and evidence['patched']['measured'] else 'quarantined'
        card['vulnerability_observed']=evidence['vulnerable']['measured'] and not evidence['vulnerable']['security']
        return card
    bank=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(one,t) for t in tasks]): bank.append(f.result())
    bank.sort(key=lambda c:c['id'])
    write(out/'source_quality_audit.json',{'total':len(bank),'qualified':sum(c['quality_status']=='qualified' for c in bank),
        'quarantined':[{'id':c['id'],'evidence':c['source_evidence']} for c in bank if c['quality_status']!='qualified'],
        'vulnerability_unobserved':[c['id'] for c in bank if not c['vulnerability_observed']]})
    write(path,bank)
    return bank


def suites_for(out,tasks,requesters,workers):
    """公开检查独立缓存，不见候选与记忆；每架构使用相同用例，官方夹具不读取。"""
    directory=out/'public_checks_v5'
    directory.mkdir(exist_ok=True)
    result={}
    missing=[]
    for t in tasks:
        path=directory/(str(t['index'])+'.json')
        ensure_signature(directory/(str(t['index'])+'.signature.json'),
            {'public':public_task(t),'implementation':hash_files([Path(__file__).parent/'checks.py',Path(__file__).parent/'workflow.py'])})
        if path.exists(): result[str(t['index'])]=json.loads(path.read_text(encoding='utf-8'))
        else: missing.append(t)
    def one(t):
        session=Session(requesters)
        suite=propose(t,session)
        seen=set()
        while not suite['cases'] and suite.get('errors'):
            fingerprint=tuple(e.split(':')[0] for e in suite['errors'])
            if fingerprint in seen: break
            seen.add(fingerprint)
            suite=propose(t,session,previous_errors=suite['errors'])
        suite.update(task_id=t['index'],usage=session.usage,trace=session.trace)
        return t,suite
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in as_completed([pool.submit(one,t) for t in missing]):
            t,suite=f.result()
            write(directory/(str(t['index'])+'.json'),suite)
            result[str(t['index'])]=suite
            print('public_checks',t['index'],'cases',len(suite['cases']),'errors',suite['errors'],flush=True)
    return result


def batch(out,label,tasks,arms,banks,requesters,suites,workers):
    """逐配置断点续跑与完整代码证据保存；缓存必须匹配输入/源码哈希。"""
    directory=out/label
    directory.mkdir(parents=True,exist_ok=True)
    signature={'arms':list(arms),'task_ids':[t['index'] for t in tasks],
        'banks_sha256':hashlib.sha256(json.dumps(banks,sort_keys=True).encode()).hexdigest(),
        'suites_sha256':hashlib.sha256(json.dumps(suites,sort_keys=True).encode()).hexdigest(),
        'source':hash_files(implementation_files())}
    signature_path=directory/'input_signature.json'
    if signature_path.exists() and json.loads(signature_path.read_text(encoding='utf-8'))!=signature:
        raise ValueError('batch_cache_configuration_changed:'+label)
    write(signature_path,signature)
    rows=read_rows(directory/'rows.jsonl')
    done={(str(r['task_id']),r['arm']) for r in rows}
    jobs=[]
    for i,t in enumerate(tasks):
        rotated=list(arms)[i%len(arms):]+list(arms)[:i%len(arms)]
        jobs.extend((t,a) for a in rotated if (str(t['index']),a) not in done)
    metadata={'phase':label,'status':'running','model':'deepseek-v3.2','temperature':0,'workers':workers,
        'logical_calls_per_task':'not capped; evidence convergence','official_feedback_for_candidate_selection':False,
        'backend':'local python -I','expected_rows':len(tasks)*len(arms)}
    write(directory/'run_metadata.json',metadata)
    with ThreadPoolExecutor(max_workers=workers) as pool,(directory/'rows.jsonl').open('a',encoding='utf-8') as stream:
        futures=[pool.submit(run_one,t,a,banks[a],requesters,suites.get(str(t['index']))) for t,a in jobs]
        for future in as_completed(futures):
            row=future.result()
            rows.append(row)
            stream.write(json.dumps(row,ensure_ascii=False)+'\n'); stream.flush()
            write(directory/'summary.json',summarize(rows,'protect_none'))
            print(label,len(rows),'/',len(tasks)*len(arms),row['arm'],row['task_id'],
                'joint',row['final']['joint'],'calls',row['usage']['calls'],'error',row.get('error_type'),flush=True)
    metadata.update(status='completed',rows=len(rows),finished_at=datetime.now(timezone.utc).isoformat())
    write(directory/'run_metadata.json',metadata)
    return rows


def accept_revision(before,after):
    """校准门控要求净 Joint 增加，原功能/Joint 通过不受损且测量覆盖不下降。"""
    old={str(r['task_id']):r['final'] for r in before}
    new={str(r['task_id']):r['final'] for r in after}
    if old.keys()!=new.keys(): return False
    if sum(v['joint'] for v in new.values())<=sum(v['joint'] for v in old.values()): return False
    for key,a in old.items():
        b=new[key]
        if a['measured'] and not b['measured']: return False
        if a['joint'] and not b['joint']: return False
        if a['functional'] and not b['functional']: return False
    return True


def revise_bank(architecture,bank,rows,baseline,task_by_id,requesters,rejected_proposals=None):
    """内层调整只用公开训练任务、生成代码与脱敏分数；每架构独立条件，不含目标答案。"""
    base={str(r['task_id']):r for r in baseline}
    grouped={}
    for row in rows:
        cid=row.get('memory',{}).get('retrieved_id')
        if cid:
            grouped.setdefault(cid,[]).append(row)
    candidate=json.loads(json.dumps(bank))
    records=[]
    for card in candidate:
        examples=grouped.get(card['id'],[])
        if not examples: continue
        cases=[]
        for r in examples:
            b=base[str(r['task_id'])]
            cases.append({'public_task':public_task(task_by_id[str(r['task_id'])]),
                'memory_decision':r.get('memory'), 'candidate_code':r['selected_code'],
                'baseline_code':b['selected_code'],
                'memory_result':{k:r['final'][k] for k in ('functional','security','joint','measured','evidence')},
                'baseline_result':{k:b['final'][k] for k in ('functional','security','joint','measured','evidence')}})
        session=Session(requesters)
        try:
            revised=session.json('You are optimizing conditional memory for ONLY architecture '+architecture+
                '. This is training calibration, not deployment feedback. Compare successes, harms and '
                'remaining failures. Modify applicability/exclusion/transfer guidance; do not add target '
                'answers, task IDs, specific test inputs or task-specific hard-coded rules. Preserve all '
                'public legitimate behavior. Do not infer hidden expected outputs from score alone. '
                'Return JSON {"changed":true,"preconditions":["transfer conditions"],'
                '"exclusions":["when not to use"],"transfer_guidance":["architecture-specific advice"],'
                '"reason":"evidence-backed rationale"}. If no supported new modification remains, '
                'return {"changed":false,"reason":"why"}. Current card: '+json.dumps(card)+
                '\nPrior rejected proposals and their measured failure: '+json.dumps(rejected_proposals or [])+
                '\nDo not repeat rejected changes; propose a different evidence-supported correction or stop.'+
                '\nCalibration cases: '+json.dumps(cases),'memory_inner_revision')
            fields={k:revised.get(k,[]) for k in ('preconditions','exclusions','transfer_guidance')}
            valid=all(isinstance(v,list) and all(isinstance(s,str) for s in v) for v in fields.values())
            changed=revised.get('changed') is True and valid and fields!=card.get('architecture_boundaries',{})
            if changed: card['architecture_boundaries']=fields
            records.append({'card_id':card['id'],'changed':changed,'reason':revised.get('reason',''),
                            'boundaries':fields,'usage':session.usage,'trace':session.trace})
        except Exception as exc:
            records.append({'card_id':card['id'],'changed':False,'error_type':type(exc).__name__,
                            'usage':session.usage,'trace':session.trace})
    return candidate,records


def inner_search(out,architecture,bank,tasks,requesters,suites,workers):
    """架构专属内环，多轮修订/完整重测；两次无改善或重复提案停止，无固定一轮预算。"""
    directory=out/'inner_search'/architecture
    directory.mkdir(parents=True,exist_ok=True)
    final_path=directory/'selected_bank.json'
    ensure_signature(directory/'search_signature.json',{'source':hash_files(implementation_files()),
        'task_ids':[t['index'] for t in tasks],
        'bank':hashlib.sha256(json.dumps(bank,sort_keys=True).encode()).hexdigest(),
        'suites':hashlib.sha256(json.dumps(suites,sort_keys=True).encode()).hexdigest()})
    if final_path.exists(): return json.loads(final_path.read_text(encoding='utf-8'))
    initial_arms=[architecture+'_none',architecture+'_m1',architecture+'_m4']
    baseline_rows=batch(out,'inner_search/'+architecture+'/round_0',tasks,initial_arms,
                        {a:bank for a in initial_arms},requesters,suites,workers)
    baseline=[r for r in baseline_rows if r['arm']==architecture+'_none']
    incumbent=[r for r in baseline_rows if r['arm']==architecture+'_m4']
    current=json.loads(json.dumps(bank))
    task_by_id={str(t['index']):t for t in tasks}
    history=[]
    rejected=0
    version=0
    rejected_proposals=[]
    seen={hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest()}
    while rejected<2:
        version+=1
        candidate,records=revise_bank(architecture,current,incumbent,baseline,task_by_id,requesters,rejected_proposals)
        digest=hashlib.sha256(json.dumps(candidate,sort_keys=True).encode()).hexdigest()
        write(directory/('proposal_'+str(version)+'.json'),{'bank':candidate,'records':records})
        if digest in seen or not any(r.get('changed') for r in records):
            history.append({'round':version,'accepted':False,'stop':'repeated_or_no_supported_revision'})
            break
        seen.add(digest)
        arm=architecture+'_m4'
        rows=batch(out,'inner_search/'+architecture+'/round_'+str(version),tasks,[arm],{arm:candidate},
                   requesters,suites,workers)
        accepted=accept_revision(incumbent,rows)
        history.append({'round':version,'accepted':accepted,'before_joint':sum(r['final']['joint'] for r in incumbent),
            'after_joint':sum(r['final']['joint'] for r in rows),
            'changed_cards':[r['card_id'] for r in records if r.get('changed')]})
        if accepted:
            current=candidate; incumbent=rows; rejected=0
        else:
            rejected+=1
            rejected_proposals.append({'changed_boundaries':{c['id']:c.get('architecture_boundaries',{}) for c in candidate
                if c.get('architecture_boundaries',{})!=next(x for x in current if x['id']==c['id']).get('architecture_boundaries',{})},
                'before_joint':history[-1]['before_joint'],'after_joint':history[-1]['after_joint'],
                'regressions':[{'public_task':public_task(task_by_id[str(r['task_id'])]),
                    'result':{k:r['final'][k] for k in ('functional','security','joint','measured')}} for r in rows
                    if any(str(b['task_id'])==str(r['task_id']) and
                           ((b['final']['functional'] and not r['final']['functional']) or
                            (b['final']['joint'] and not r['final']['joint'])) for b in incumbent)]})
        write(directory/'history.partial.json',history)
    write(directory/'history.json',{'rounds':history,'stop':'convergence_or_two_nonimproving_proposals',
        'selected_joint':sum(r['final']['joint'] for r in incumbent),'calibration_n':len(tasks)})
    write(final_path,current)
    return current


def report(out,manifest,dev,confirmation=None,regression=None):
    """逐项中文命名及真实阶段结果；历史开发对照不得伪装成新50题确认结果。"""
    ds=summarize(dev,'protect_none')
    cs=summarize(confirmation or [],'protect_none')
    rs=summarize(regression or [],'protect_none')
    write(out/'summary.json',{'development':ds,'confirmation':cs,'regression':rs})
    lines=['# A7 分架构记忆探索（2026-10-09）','',
        '每格按“功能 / 安全 / 同时通过”列出。公开检查决定修复和选代码；官方 PLT 只事后评分。',
        '','| 配置 | 具体方法 | 开发60 | 冻结确认50 | 训练回归18 |','|---|---|---|---|---|']
    def cell(summary,arm):
        v=summary['arms'].get(arm)
        return f"{v['functional']} / {v['security']} / {v['joint']}（完整测量 {v['measured']}/{v['n']}）" if v else '尚未执行'
    for arm in ARMS:
        a,m=arm.split('_')
        lines.append(f'| {arm} | {NAMES[a]}＋{NAMES[m]} | {cell(ds,arm)} | {cell(cs,arm)} | {cell(rs,arm)} |')
    old=read_rows(DEFAULT_OUT/'adjustment_screen/rows.jsonl')
    os=summarize(old,'contract_direct')
    for arm,name in [('contract_slice','旧接口保护＋M1'),('contract_skill','旧接口保护＋M4')]:
        lines.append(f'| {arm} | {name}（引用历史开发记录） | {cell(os,arm)} | 不在新确认集运行 | 见旧报告 |')
    lines+=['','## 实现和数据边界','',
        '- 来源36重新验证，补丁功能与安全同时通过才可注入；提供来源公开接口、前后文和验证状态。',
        '- 三种流程分别进行 M4 校准：使用新增24个训练 family，反复提出修订、完整重测，净收益且无原通过回归才接纳。',
        '- 不设每题6次或内环1轮限额。修复按公开证据改善持续，重复代码、无改善或没有确定问题才停。',
        '- 公开检查由任务描述生成并同模型复核；可能错误。缺依赖/不确定异常缺测，不能代表真实候选错误。',
        '- 两候选无记忆对照也生成两份代码。同分保留先生成候选；没有官方答案挑选。',
        '- 50个确认 family 对本轮选择隔离，历史 PLT 使用导致不能宣称完全未见；D_gate/H_pass/Base/Plus 不参与。',
        '- 本轮是三种流程的嵌套选择，不是任意架构图搜索，也不是已证实高成功率的方法。',
        '', '## 记忆内环实际记录','']
    for a in ARCHITECTURES:
        path=out/'inner_search'/a/'history.json'
        if path.exists(): lines += ['### '+NAMES[a],'','```json',path.read_text(encoding='utf-8'),'```','']
    lines+=['## 成本与公开选择损失','','| 配置 | 开发调用 | 开发 token | 确认调用 | 确认 token | 确认候选可通过但选错 |',
            '|---|---:|---:|---:|---:|---:|']
    for arm in ARMS:
        d=ds['arms'].get(arm,{})
        c=cs['arms'].get(arm,{})
        lost=sum(r.get('oracle_joint',False) and not r['final']['joint'] for r in confirmation or [] if r['arm']==arm)
        lines.append(f"| {arm} | {d.get('calls',0)} | {d.get('total_tokens',0)} | {c.get('calls',0)} | {c.get('total_tokens',0)} | {lost} |")
    lines+=['','## 改善与伤害（同流程无记忆对照）','',
        '| 阶段 | 方法 | 救回同时通过 | 损坏同时通过 | 功能回归 | 未注入记忆 | 修复前→后同时通过 |',
        '|---|---|---:|---:|---:|---:|---|']
    for phase,rows in [('开发60',dev),('确认50',confirmation or [])]:
        for arm in ARMS:
            items=[r for r in rows if r['arm']==arm]
            base={str(r['task_id']):r for r in rows if r['arm']==arm.split('_')[0]+'_none'}
            pairs=[(base[str(r['task_id'])]['final'],r['final']) for r in items if str(r['task_id']) in base
                   and r['final']['measured'] and base[str(r['task_id'])]['final']['measured']]
            wins=sum(not a['joint'] and b['joint'] for a,b in pairs)
            harms=sum(a['joint'] and not b['joint'] for a,b in pairs)
            fh=sum(a['functional'] and not b['functional'] for a,b in pairs)
            abstained=sum(not r.get('memory',{}).get('injected_ids') for r in items)
            first=sum(r['attempts'][0]['joint'] for r in items)
            final=sum(r['final']['joint'] for r in items)
            lines.append(f'| {phase} | {arm} | {wins} | {harms} | {fh} | {abstained} | {first}→{final} |')
    totals={}
    def add(category,usage):
        total=totals.setdefault(category,{'calls':0,'total_tokens':0})
        for k in total: total[k]+=usage.get(k,0)
    for path in (out/'public_checks_v5').glob('*.json'):
        if not path.name.endswith('.signature.json'):
            add('公开检查生成与复核',json.loads(path.read_text(encoding='utf-8')).get('usage',{}))
    for path in (out/'inner_search').rglob('proposal_*.json'):
        for record in json.loads(path.read_text(encoding='utf-8'))['records']:
            add('内环记忆修订提案',record.get('usage',{}))
    for path in (out/'inner_search').rglob('rows.jsonl'):
        for row in read_rows(path): add('内环全部校准重跑',row['usage'])
    for category,rows in [('开发生成',dev),('确认生成',confirmation or []),('训练回归生成',regression or [])]:
        for row in rows: add(category,row['usage'])
    for path in out.glob('smoke*/rows.jsonl'):
        for row in read_rows(path): add('前置冒烟与排错',row['usage'])
    write(out/'cost_breakdown.json',totals)
    lines+=['','## 完整探索调用成本','',
        '下面另列校准与检查开销；逐配置成本只计部署生成/修复调用。Token 为成功返回的 API usage，服务失败未返回用量可能漏计。',
        '','| 类别 | 逻辑调用 | token |','|---|---:|---:|']
    for category,total in totals.items(): lines.append(f"| {category} | {total['calls']} | {total['total_tokens']} |")
    lines+=['','源补丁/漏洞本地重验证为72次，不调用模型。内部检查为轻量子进程隔离，资源限制、静态安全与类型检查没有完整测量。',
        '首次成绩为修复前生成候选的事后测量，不向修复环提供。两候选组的首次候选是无记忆分支。',
        '公开检查通过不等于官方安全通过；判断方法收益应看冻结确认和功能回归，不能只看开发最高分。']
    text='\n'.join(lines)+'\n'
    (out/'report.md').write_text(text,encoding='utf-8')
    (ROOT/'docs/a7_exploration_20261009.md').write_text(text,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('smoke','all'),default='all')
    parser.add_argument('--workers',type=int,default=12)
    args=parser.parse_args()
    if not 1<=args.workers<=16: parser.error('workers must be 1..16')
    data,manifest=prepare_data(OUT)
    semaphore=threading.BoundedSemaphore(args.workers)
    requesters={k:_requester('deepseek-v3.2',90,max_tokens=k,semaphore=semaphore,hard_timeout=120)
                for k in (4096,8192,16384)}
    bank=source_bank(OUT,data['source'],args.workers)
    print('source_quality',sum(c['quality_status']=='qualified' for c in bank),'/',len(bank),flush=True)
    if args.phase=='smoke':
        tasks=data['calibration'][:2]
        suites=suites_for(OUT,tasks,requesters,args.workers)
        rows=batch(OUT,'smoke_v5',tasks,ARMS,{a:bank for a in ARMS},requesters,suites,args.workers)
        print('smoke_complete',len(rows),'measured',sum(r['final']['measured'] for r in rows),flush=True)
        return
    # 保存可复现环境标签与数据清单，不读取或保存任何凭据内容。
    metadata_path=OUT/'run_metadata.json'
    if not metadata_path.exists():
        commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        write(metadata_path,{'schema':'a7-exploration-v1','started_at':datetime.now(timezone.utc).isoformat(),
            'commit':commit,'implementation_hashes':hash_files(implementation_files()),
            'python':sys.version,'python_executable':sys.executable,'model':'deepseek-v3.2','temperature':0,
            'workers':args.workers,'backend':'local python -I; no Docker','counts':manifest['counts'],
            'logical_call_limit':None,'source_qualified':sum(c['quality_status']=='qualified' for c in bank),
            'source_total':len(bank),'formal_holdout_used':False,'status':'running'})
    frozen_path=OUT/'frozen_selection.json'
    if frozen_path.exists():
        frozen=json.loads(frozen_path.read_text(encoding='utf-8'))
        check_frozen(frozen['hashes'])
        banks={a:json.loads((OUT/'frozen_banks'/f'{a}.json').read_text(encoding='utf-8')) for a in ARMS}
        dev=read_rows(OUT/'development/rows.jsonl')
    else:
        calibration_suites=suites_for(OUT,data['calibration'],requesters,args.workers)
        adjusted={a:inner_search(OUT,a,bank,data['calibration'],requesters,calibration_suites,args.workers)
                  for a in ARCHITECTURES}
        banks={arm:adjusted[arm.split('_')[0]] if arm.endswith('_m4') else bank for arm in ARMS}
        dev_suites=suites_for(OUT,data['screen'],requesters,args.workers)
        dev=batch(OUT,'development',data['screen'],ARMS,banks,requesters,dev_suites,args.workers)
        ranking=sorted(summarize(dev,'protect_none')['arms'],key=lambda a:(
            -sum(r['final']['joint'] for r in dev if r['arm']==a),
            -sum(r['final']['functional'] for r in dev if r['arm']==a),
            sum(r['usage']['calls'] for r in dev if r['arm']==a)))
        (OUT/'frozen_banks').mkdir(exist_ok=True)
        for arm,b in banks.items(): write(OUT/'frozen_banks'/f'{arm}.json',b)
        # 冻结前只形成确认任务的公开检查，不运行候选或打开官方成绩。
        suites_for(OUT,data['confirmation']+data['regression'],requesters,args.workers)
        paths=implementation_files()+list((OUT/'frozen_banks').glob('*.json'))+[OUT/'manifest.json',OUT/'source_bank.json']
        paths+=list((OUT/'public_checks_v5').glob('*.json'))
        frozen={'created_at':datetime.now(timezone.utc).isoformat(),'selected_arm':ranking[0],
                'development_ranking':ranking,'all_arms_confirmed_for_comparison':True,
                'hashes':hash_files(paths),'confirmation_scores_seen':False}
        write(frozen_path,frozen)
        snapshot=OUT/'source_snapshot'
        snapshot.mkdir(exist_ok=True)
        for p in Path(__file__).parent.glob('*.py'): shutil.copy2(p,snapshot/p.name)
        report(OUT,manifest,dev)
        print('FROZEN_SELECTED',ranking[0],flush=True)
    check_frozen(frozen['hashes'])
    confirmation_suites=suites_for(OUT,data['confirmation'],requesters,args.workers)
    confirmation=batch(OUT,'confirmation',data['confirmation'],ARMS,banks,requesters,confirmation_suites,args.workers)
    check_frozen(frozen['hashes'])
    regression_suites=suites_for(OUT,data['regression'],requesters,args.workers)
    regression=batch(OUT,'regression',data['regression'],ARMS,banks,requesters,regression_suites,args.workers)
    check_frozen(frozen['hashes'])
    report(OUT,manifest,dev,confirmation,regression)
    write(OUT/'completion.json',{'status':'completed','development_rows':len(dev),
        'confirmation_rows':len(confirmation),'regression_rows':len(regression),
        'frozen_unchanged':True,'selected_before_confirmation':frozen['selected_arm']})
    metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
    metadata.update(status='completed',finished_at=datetime.now(timezone.utc).isoformat())
    write(metadata_path,metadata)
    print('ALL_COMPLETE',flush=True)


if __name__=='__main__': main()

"""PLT 训练开发方向初筛：独立实验模块，冻结清单、来源卡和有界候选。

只读取 D_init/D_grow，禁止 Base/Plus、D_gate 与最终 H_pass 进入反馈。
官方 PLT 评分只用于事后开发比较；route 臂明确是训练反馈诊断。其他臂选择
仅用公开契约/语法/内部测试/模型审查。不存在长期经验库写权限。
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from methods.direction_screening.protocol import sample_families, public_task, safe_evidence, outcome, select_public, summarize
from methods.sct_trajectory.agent_pipeline import _content, _extract_json, strip_code_fence
from methods.sct_trajectory.context_pipeline import CONTRACT_POLICY, run_context_pipeline
from methods.sct_agent.validation_evidence import validate_plt_row

DEFAULT_OUT = ROOT / 'translation_work/diagnostics/20261009/memory_architecture_screening'
CANONICAL = ROOT / 'translation_work/sct_runs/cle_ablation_matrix_20260929_run2/pool_manifest.json'
ARMS = ('direct', 'staged_empty', 'staged_memory', 'rule', 'slice', 'utility', 'draft_plain',
        'draft_memory', 'skill', 'verification_plain', 'verification', 'review', 'route', 'role_budget', 'controller', 'branch')


def write(path, value):
    """产物阶段原子替换小型 JSON，防止中断损坏清单；不删除其他实验。"""
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def read_rows(path):
    """续跑阶段只接受完整且无重复键记录；残行/重复显式失败，不静默吞掉证据。"""
    if not Path(path).exists():
        return []
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    keys = [(str(r['task_id']), r['arm']) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('duplicate_result_key')
    return rows


class Session:
    """调用阶段限制逻辑调用数并累计 Token；响应截断/解析异常留痕，不保存原始提示。"""
    def __init__(self, requesters, max_calls=8):
        self.requesters = requesters
        self.max_calls = max_calls
        self.usage = {'calls':0, 'failed_calls':0, 'prompt_tokens':0, 'completion_tokens':0, 'total_tokens':0}
        self.trace = []

    def response(self, prompt, budget=3072, stage='generation'):
        """输入许可公开提示、角色预算；输出兼容响应，硬预算先检查，错误只记类别。"""
        if self.usage['calls'] >= self.max_calls:
            raise RuntimeError('call_budget_exhausted')
        self.usage['calls'] += 1
        started = time.monotonic()
        record = {'stage':stage, 'output_limit':budget}
        try:
            response = self.requesters[budget](prompt)
            for key in ('prompt_tokens','completion_tokens','total_tokens'):
                self.usage[key] += (response.get('usage') or {}).get(key,0)
            record['finish_reason'] = (response.get('choices') or [{}])[0].get('finish_reason')
            return response
        except Exception as exc:
            self.usage['failed_calls'] += 1
            record['error_type'] = type(exc).__name__
            record['diagnostics'] = getattr(exc,'safe_diagnostics',[])
            raise
        finally:
            record['seconds'] = time.monotonic()-started
            self.trace.append(record)

    def ask(self, prompt, budget=3072, stage='generation'):
        """提取正文并拒绝截断；截断不能作为完整候选，不改记忆。"""
        return _content(self.response(prompt,budget,stage))


def prepare(out):
    """冻结划分阶段：来源/校准/H_reg/初筛/确认分别按 family 排除，官方留出不使用。"""
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    from methods.cle_ablation_matrix.pool_manifest import validate_manifest
    rows = _load_tasks(0)
    canonical = json.loads(CANONICAL.read_text(encoding='utf-8'))
    audit = validate_manifest(canonical,rows)
    by_id = {str(r['index']):r for r in rows}
    pools = {k:[by_id[str(e['task_id'])] for e in v] for k,v in canonical['pools'].items() if k in ('D_init','D_grow')}
    chosen = {}
    for name, parent, count in [('source','D_init',36),('calibration','D_init',24),('regression','D_init',18),
                                 ('screen','D_grow',60),('confirmation','D_grow',60)]:
        excluded = {r['family_id'] for group in chosen.values() for r in group}
        chosen[name] = sample_families(pools[parent],count,excluded)
    manifest = {'schema':'direction-screen-v1', 'created_at':datetime.now(timezone.utc).isoformat(),
                'canonical_sha256':hashlib.sha256(CANONICAL.read_bytes()).hexdigest(), 'audit':audit,
                'groups':{k:[{'task_id':r['index'],'family_id':r['family_id'],'cwe':str(r['CWE_ID'])} for r in v] for k,v in chosen.items()},
                'counts':{k:len(v) for k,v in chosen.items()}, 'arms':list(ARMS),
                'cwe_counts':{k:dict(Counter(str(r['CWE_ID']) for r in v)) for k,v in chosen.items()},
                'final_holdout_used':False, 'historically_pristine':False}
    out.mkdir(parents=True,exist_ok=True)
    path = out/'manifest.json'
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if existing['groups'] != manifest['groups'] or existing['canonical_sha256'] != manifest['canonical_sha256']:
            raise ValueError('existing_manifest_conflict')
    else:
        write(path,manifest)
    return chosen


def retrieve(task, bank, draft=''):
    """冻结召回只用公开任务与草稿操作，CWE 优先再词重叠；不读取目标答案或夹具。"""
    contract = public_task(task)
    terms = set(re.findall(r'[a-z_]+',json.dumps(contract).lower()+' '+draft.lower()))
    candidates = [c for c in bank if c['cwe']==str(task['CWE_ID'])]
    def score(card):
        text = card.get('source_description','')+' '+card.get('rule','')
        return len(terms & set(re.findall(r'[a-z_]+',text.lower())))
    return max(candidates,key=score) if candidates else None


def memory_view(card, kind):
    """注入阶段控制同源表达；只有 slice/skill 含来源补丁，目标正确代码从不提供。"""
    if not card:
        return {}
    fields = ('id','rule','preconditions','exclusions','preserve','verification')
    result = {k:card.get(k) for k in fields}
    if kind in ('slice','skill'):
        result['source_patch_slice'] = card['patch_slice']
    if kind == 'skill':
        result['calibrated_boundaries'] = card.get('calibrated_boundaries',{})
        for key in ('preconditions','exclusions'):
            boundary=card.get('calibrated_boundaries',{}).get(key)
            if isinstance(boundary,list) and boundary:
                result[key]=boundary
    return result


def generate(session, task, memory=None, draft='', feedback=None, budget=3072, strategy=''):
    """生成/局部修复阶段：公开契约、许可反馈、条件卡→完整代码；不写长期库。"""
    prompt = ('Return only complete runnable Python code. '+CONTRACT_POLICY+
              '\nTask: '+json.dumps(public_task(task),ensure_ascii=False)+
              '\nConditional memory: '+json.dumps(memory or {},ensure_ascii=False)+
              '\nCurrent code: '+draft+'\nPermitted feedback: '+json.dumps(feedback or {},ensure_ascii=False)+
              '\nImplementation instruction: '+strategy)
    return strip_code_fence(session.ask(prompt,budget,'repair' if draft else 'generation'))


def evaluate(task,code):
    """事后评分阶段运行 PLT 本地隔离；只输出脱敏状态，缺测不默认为通过。"""
    return {'code':code,**outcome(validate_plt_row(task,code,timeout=12,backend='local').to_dict())}


def review(session,task,code,role,budget=1024):
    """独立审查角色仅见公开契约与候选；模型问题判断不是动态证明或官方评分。"""
    prompt = ('Independently review '+role+' correctness. Do not invent constraints. Return JSON '
              '{"issues":[{"location":"code operation","reason":"contract evidence","fix":"minimal change"}]}.'
              '\nPublic contract: '+json.dumps(public_task(task),ensure_ascii=False)+'\nCandidate: '+code)
    for attempt in range(2):
        try:
            result = _extract_json(session.ask(prompt,budget,role+'_review'))
            issues = result.get('issues')
            if not isinstance(issues,list):
                raise ValueError('invalid_review_schema')
            return {'role':role,'issues':issues[:5]}
        except (ValueError,json.JSONDecodeError) as exc:
            session.trace[-1]['parse_error']=type(exc).__name__
            if attempt:
                raise
            prompt += ('\nThe prior response had a JSON formatting/schema error. Return only valid JSON. '
                       'Avoid regex patterns/backslashes in strings; use plain English descriptions.')


def public_score(code,reviews=(),internal=None):
    """有界控制/分支选择的公开分数；AST 仅语法，审查和内部测试各自单列来源。"""
    try:
        ast.parse(code)
        syntax = bool(code.strip())
    except SyntaxError:
        syntax = False
    issues = sum(len(r.get('issues',[])) for r in reviews)
    measured = (internal or {}).get('measured_count',0)
    passed = (internal or {}).get('passed',0)
    return (100 if syntax else -100) - 4*issues + (10*passed/measured if measured else 0)


def choose_candidate(candidates):
    """仅使用公开证据选择可部署候选；官方分数只能事后作 oracle 诊断。"""
    return candidates[select_public(candidates)]


def source_bank(out,tasks,requesters,workers):
    """D_init 来源提取：漏洞/补丁及动态来源证据→条件卡；候选留临时诊断库不晋升。

    补丁切片负责危险模式到补丁逻辑的变化；模型提炼前置条件、安全 API、后置条件
    与合法行为。来源完整 patched 实现通过才可用于动态校准；失败单独留存。
    """
    path = out/'source_bank.json'
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    def one(task):
        truth = task['ground_truth']
        before = truth.get('code_before','')
        after = truth.get('code_after','')
        patched = before+truth.get('patched_code','')+after
        vulnerable = before+truth.get('vulnerable_code','')+after
        secure = evaluate(task,patched)
        unsafe = evaluate(task,vulnerable)
        session = Session(requesters,max_calls=2)
        card = {'id':'source-'+str(task['index']),'source_id':task['index'],'family_id':task['family_id'],
                'cwe':str(task['CWE_ID']),'source_description':task['task_description']['description'],
                'patch_slice':{'before':truth.get('vulnerable_code',''),'after':truth.get('patched_code','')},
                'source_evidence':{'patched':{k:v for k,v in secure.items() if k!='code'},
                                   'vulnerable':{k:v for k,v in unsafe.items() if k!='code'}}}
        try:
            prompt = ('Derive a transferable conditional security rule from this TRAINING source patch. '
                      'Do not copy function names, concrete inputs or constants as universal rules. '
                      'Describe untrusted source, sensitive operation, trigger, patch action, safe APIs, postcondition, '
                      'and legitimate behavior to preserve. Source success is not general validity. Return strict JSON '
                      '{"rule":"mechanism and change","preconditions":["when relevant"],'
                      '"exclusions":["when irrelevant"],"preserve":["legitimate behavior"],'
                      '"verification":["public-contract test patterns, no source values"]}.\nTask: '+
                      json.dumps(public_task(task))+'\nPatch: '+json.dumps(card['patch_slice'])+
                      '\nMeasured source evidence: '+json.dumps(card['source_evidence']))
            content = _extract_json(session.ask(prompt,1536,'source_rule'))
            if not isinstance(content.get('rule'),str) or not content['rule'].strip():
                raise ValueError('missing_source_rule')
            card.update({k:content.get(k,[]) for k in ('rule','preconditions','exclusions','preserve','verification')})
        except Exception as exc:
            card['error_type'] = type(exc).__name__
        card['usage'] = session.usage
        return card
    bank = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for future in as_completed([executor.submit(one,t) for t in tasks]):
            card = future.result()
            bank.append(card)
            write(out/'source_bank.partial.json',bank)
            print('source',len(bank),'/',len(tasks),'id',card['source_id'],'patched_joint',card['source_evidence']['patched']['joint'],flush=True)
    bank.sort(key=lambda c:str(c['id']))
    write(path,bank)
    return bank


def run_one(task,arm,bank,requesters,baseline=None):
    """逐臂原型运行：所有候选留存、公开选择与官方评分分离；最多八次逻辑调用。

    route 是训练反馈可见诊断，其他控制器不消费目标官方测量。返回首次/最终代码、
    测量覆盖、角色证据、来源 ID 和成本，不蒸馏、不修改 source_bank。
    """
    started = time.monotonic()
    session = Session(requesters)
    card = retrieve(task,bank)
    result = {'task_id':task['index'],'family_id':task['family_id'],'cwe':str(task['CWE_ID']),
              'arm':arm,'attempts':[],'official_feedback_visible':arm=='route','card_id':card['id'] if card else None}
    try:
        if arm.startswith('staged'):
            cards = []
            if arm=='staged_memory' and card:
                cards=[{'invariant_id':card['id'],'kind':'conditional','status':'temporary',
                        'applicability':card.get('preconditions'), 'exclusion_conditions':card.get('exclusions'),
                        'positive_principle':card['rule'],'recommended_action':card['rule'],
                        'negative_guardrail':card.get('preserve'),'support_count':int(card['source_evidence']['patched']['joint'])}]
            generated=run_context_pipeline(public_task(task),cards,requester=lambda p:session.response(p))
            code=generated['code']
            result['workflow_stages']=generated.get('stages',[])
            result['workflow_error']=generated.get('error_type')
        elif arm in ('rule','slice','skill','utility'):
            if arm=='utility' and (not card or card.get('utility',0)<=0):
                card=None
            result['card_id']=card['id'] if card else None
            if arm=='utility' and card is None and baseline is not None:
                code=baseline['final']['code']
                result['equivalent_to_empty_memory']=True
            else:
                code=generate(session,task,memory_view(card,arm))
        elif baseline is not None:
            code=baseline['final']['code']
            result['shared_draft_from']='direct'
        else:
            code=generate(session,task)
        first=evaluate(task,code)
        result['attempts'].append(first)
        if arm in ('draft_plain','draft_memory','role_budget','route','review','verification','verification_plain','controller','branch'):
            memory={}
            if arm=='draft_memory':
                card=retrieve(task,bank,code)
                memory=memory_view(card,'slice')
                result['card_id']=card['id'] if card else None
            if arm in ('draft_plain','draft_memory'):
                code=generate(session,task,memory,code,strategy='Inspect actual operations against the contract; make only necessary local corrections. Keep correct behavior.')
                result['attempts'].append(evaluate(task,code))
            elif arm=='role_budget':
                reviews=[review(session,task,code,role,1536) for role in ('functional','security')]
                result['reviews']=reviews
                code=generate(session,task,draft=code,feedback={'independent_reviews':reviews},budget=4096,
                              strategy='Address grounded contract violations only; reviews are hypotheses.')
                result['attempts'].append(evaluate(task,code))
            elif arm=='route':
                feedback=first['evidence']
                if not first['measured']:
                    route='environment_or_unmeasured_stop'
                elif first['joint']:
                    route='pass_stop'
                elif feedback['syntax_or_compile']['status']!='pass':
                    route='syntax_repair'
                elif not first['functional']:
                    route='functional_contract_repair' if first['security'] else 'functional_and_security_inspection'
                else:
                    route='security_inspection_preserve_functionality'
                result['route']=route
                if not route.endswith('stop'):
                    code=generate(session,task,draft=code,feedback=feedback,strategy=route+'; F/S states indicate failed checks, not the root cause. Diagnose operations before patching.')
                    result['attempts'].append(evaluate(task,code))
            elif arm=='review':
                reviews=[review(session,task,code,role) for role in ('functional','security')]
                result['reviews']=reviews
                code=generate(session,task,draft=code,feedback={'independent_reviews':reviews},strategy='Address grounded contract violations only; reviews are hypotheses.')
                result['attempts'].append(evaluate(task,code))
            elif arm=='branch':
                alternate=generate(session,task,strategy='Independently derive the implementation from the public contract. Explicitly reconsider boundary, exception and API semantics; do not assume blanket rejection is safe.')
                candidates=[first,evaluate(task,alternate)]
                selector_input=[]
                reviews=[]
                for item in candidates:
                    assessment=review(session,task,item['code'],'functional and security')
                    reviews.append(assessment)
                    selector_input.append({'code':item['code'],'public_score':public_score(item['code'],[assessment])})
                selected=select_public(selector_input)
                result['attempts'].append(candidates[1])
                result['selected_index']=selected
                result['selector_evidence']=selector_input
                result['reviews']=reviews
                result['final']=candidates[selected]
                result['oracle_any_joint']=any(c['joint'] for c in candidates)
            else:
                from methods.sct_trajectory.internal_checks import propose_checks, execute_checks
                if arm=='verification':
                    card=retrieve(task,[c for c in bank if c.get('verification_calibrated')],code)
                verified=arm=='verification' and card and card.get('verification_calibrated')
                guidance=card.get('verification',[]) if verified else []
                if arm in ('verification','verification_plain'):
                    result['verification_memory_used']=bool(verified)
                    result['verification_card_id']=card['id'] if verified else None
                    suite=propose_checks(public_task(task),{'verification_skill':guidance},lambda p:session.response(p,1536,'internal_test'))
                    internal=execute_checks(code,public_task(task)['function_name'],suite,timeout=5)
                    result['suite']=suite
                    result['internal']=internal
                    code=generate(session,task,draft=code,feedback={'internal_checks':{'measured':internal['measured'],'passed':internal['passed'],'measured_count':internal['measured_count'],
                          'cases':[{k:c.get(k) for k in ('id','status','measured','phase')} for c in internal['cases']]}},
                          strategy='Use internally checked public-contract behavior; internal tests may be incomplete. Make necessary local fixes only.')
                    result['attempts'].append(evaluate(task,code))
                else:
                    assessment=review(session,task,code,'functional and security')
                    result['reviews']=[assessment]
                    initial_score=public_score(code,[assessment])
                    if assessment['issues'] or initial_score<0:
                        memory=memory_view(retrieve(task,bank,code),'skill')
                        code=generate(session,task,memory,code,{'review':assessment},strategy='Inspect and minimally fix grounded issues; conditional memory may be irrelevant.')
                        corrected=evaluate(task,code)
                        result['attempts'].append(corrected)
                        second_review=review(session,task,code,'functional and security')
                        new_score=public_score(code,[second_review])
                        result['reviews'].append(second_review)
                        result['selected_index']=int(new_score>initial_score)
                        result['final']=result['attempts'][result['selected_index']]
                        result['controller_actions']=['review','retrieve','patch','review','select','stop']
                    else:
                        result['controller_actions']=['review','stop']
        result.setdefault('final',result['attempts'][-1])
    except Exception as exc:
        result['error_type']=type(exc).__name__
        result['error_reason']=str(exc)[:100] if isinstance(exc,ValueError) else 'classified_failure'
        failure={'code':'',**outcome({})}
        result['attempts'].append(failure)
        # 若修复/审查协议出错，保留可用草稿并显式报告，不伪装整个工作流已完成。
        result['final']=result['attempts'][0] if len(result['attempts'])>1 else failure
        result['fallback_to_draft']=len(result['attempts'])>1
    result['usage']=session.usage
    result['trace']=session.trace
    result['elapsed_seconds']=time.monotonic()-started
    return result


def run_matrix(out,name,tasks,arms,bank,requesters,workers):
    """调度/续跑阶段先冻结草稿对照再交错方法，写逐题结果；部分组缺失不能补零冒充完成。"""
    directory=out/name
    directory.mkdir(exist_ok=True)
    path=directory/'rows.jsonl'
    rows=read_rows(path)
    done={(str(r['task_id']),r['arm']) for r in rows}
    direct={str(r['task_id']):r for r in rows if r['arm']=='direct'}
    def execute(jobs):
        with ThreadPoolExecutor(max_workers=workers) as pool, path.open('a',encoding='utf-8') as stream:
            futures=[pool.submit(run_one,t,a,bank,requesters,direct.get(str(t['index']))) for t,a in jobs]
            for future in as_completed(futures):
                row=future.result()
                rows.append(row)
                stream.write(json.dumps(row,ensure_ascii=False)+'\n')
                stream.flush()
                if row['arm']=='direct':
                    direct[str(row['task_id'])]=row
                write(directory/'summary.json',summarize(rows))
                print(name,len(rows),'/',len(tasks)*len(arms),row['arm'],row['task_id'],'joint',row['final']['joint'],'error',row.get('error_type'),flush=True)
    execute([(t,'direct') for t in tasks if 'direct' in arms and (str(t['index']),'direct') not in done])
    jobs=[]
    for i,task in enumerate(tasks):
        rotated=arms[i%len(arms):]+arms[:i%len(arms)]
        jobs.extend((task,a) for a in rotated if a!='direct' and (str(task['index']),a) not in done)
    execute(jobs)
    return rows


def calibrate(out,tasks,bank,requesters,workers):
    """D_init 独立校准：单卡相对空卡 ΔJoint、功能伤害与边界反例；冻结后才能初筛。

    这里是暂存诊断卡修订，不是正式质量/独立有效性/H_pass 三门控晋升。
    verification 校准仅在来源正确实现和漏洞变体上测量，目标测试不进经验。
    """
    frozen=out/'calibrated_bank.json'
    if frozen.exists():
        return json.loads(frozen.read_text(encoding='utf-8'))
    rows=run_matrix(out,'calibration',tasks,['direct','rule'],bank,requesters,workers)
    base={str(r['task_id']):r for r in rows if r['arm']=='direct'}
    for card in bank:
        pairs=[r for r in rows if r['arm']=='rule' and r.get('card_id')==card['id'] and r['final']['measured'] and base[str(r['task_id'])]['final']['measured']]
        card['utility_pairs']=len(pairs)
        card['utility']=sum(int(r['final']['joint'])-int(base[str(r['task_id'])]['final']['joint']) for r in pairs)/len(pairs) if pairs else 0
        harms=[r for r in pairs if base[str(r['task_id'])]['final']['joint'] and not r['final']['joint']]
        if harms:
            session=Session(requesters,max_calls=1)
            evidence=[{'task':public_task(next(t for t in tasks if str(t['index'])==str(r['task_id']))),
                       'without':base[str(r['task_id'])]['final']['code'],'with':r['final']['code'],'status':r['final']['evidence']} for r in harms]
            try:
                prompt=('Revise only the applicability/exclusion boundary of this conditional patch skill using TRAINING counterexamples. '
                        'Do not copy task identifiers or hardcode answers. Return JSON {"preconditions":[],"exclusions":[],"reason":"mechanism"}.\nSkill: '+
                        json.dumps(memory_view(card,'slice'))+'\nCounterexamples: '+json.dumps(evidence))
                card['calibrated_boundaries']=_extract_json(session.ask(prompt,1536,'counterexample_boundary'))
            except Exception as exc:
                card['boundary_revision_error']=type(exc).__name__
        else:
            card['calibrated_boundaries']={'status':'no_observed_harm','not_evidence_of_universal_validity':True}
    write(frozen,bank)
    return bank


def calibrate_verification(out,source_tasks,bank,requesters,workers):
    """验证技能门控：每个 CWE 选来源正向 Joint 实现，生成公开测试并测漏洞变体。

    仅来源代码允许作为正负对照；要求内部测试正向全通过且负向至少一次失败，
    才提供该来源的验证建议。不能保证测试迁移正确，目标测试单列假设性证据。
    """
    from methods.sct_trajectory.internal_checks import propose_checks, execute_checks
    path=out/'verification_bank.json'
    if path.exists():
        existing=json.loads(path.read_text(encoding='utf-8'))
        evidence=json.loads((out/'verification_calibration.json').read_text(encoding='utf-8'))
        # 校准调整以逐例而非全套门控，剔除会伤害正确实现的用例，保留可识别漏洞的用例。
        filtered={}
        for card in existing:
            record=evidence.get(card['id'],{})
            positives={c['id']:c for c in record.get('positive',{}).get('cases',[])}
            negatives={c['id']:c for c in record.get('negative',{}).get('cases',[])}
            approved=[c for c in record.get('suite',{}).get('cases',[])
                      if positives.get(c['id'],{}).get('status')=='pass'
                      and negatives.get(c['id'],{}).get('status')=='fail']
            card['verification_calibrated']=bool(approved)
            card['verification_calibrated_case_ids']=[c['id'] for c in approved]
            if approved:
                card['verification']=[c.get('purpose','public contract check') for c in approved]
            filtered[card['id']]={'retained_ids':card['verification_calibrated_case_ids'],
                                  'valid':bool(approved),'policy':'positive_pass_negative_assertion_failure'}
        write(out/'verification_case_filter.json',filtered)
        write(out/'verification_bank_case_filtered.json',existing)
        return existing
    by_id={str(t['index']):t for t in source_tasks}
    selected={}
    for card in bank:
        card['verification_calibrated']=False
        if card['source_evidence']['patched']['joint'] and card['cwe'] not in selected:
            selected[card['cwe']]=card
    def one(card):
        task=by_id[str(card['source_id'])]
        session=Session(requesters,max_calls=2)
        suite=propose_checks(public_task(task),{'verification_skill':card.get('verification',[])},
                             lambda p:session.response(p,1536,'verification_calibration'))
        truth=task['ground_truth']
        prefix=truth.get('code_before','')
        suffix=truth.get('code_after','')
        # 来源单测 setup 仅恢复依赖上下文，不传模型，不转存目标测试。
        setup=(task.get('unittest') or {}).get('setup','')+'\n'
        positive=execute_checks(setup+prefix+truth.get('patched_code','')+suffix,public_task(task)['function_name'],suite,timeout=5)
        negative=execute_checks(setup+prefix+truth.get('vulnerable_code','')+suffix,public_task(task)['function_name'],suite,timeout=5)
        valid=positive['measured_count']>0 and positive['passed']==positive['measured_count'] and negative['measured_count']>negative['passed']
        return card['id'],{'valid':valid,'positive':positive,'negative':negative,'suite':suite,'usage':session.usage}
    evidence={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(one,c) for c in selected.values()]):
            key,record=future.result()
            evidence[key]=record
            print('verification_source',key,'calibrated',record['valid'],flush=True)
    for card in bank:
        card['verification_calibrated']=evidence.get(card['id'],{}).get('valid',False)
    write(out/'verification_calibration.json',evidence)
    write(path,bank)
    return calibrate_verification(out,source_tasks,bank,requesters,workers)


def main():
    """唯一诊断入口：先清单/快照/来源/校准，后初筛，再冻结入围组确认，不触碰最终评测。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=DEFAULT_OUT)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--phase',choices=('smoke','screen','confirmation','regression'),default='screen')
    parser.add_argument('--arms',nargs='+',choices=ARMS,default=list(ARMS))
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    out=args.out.resolve()
    if not out.is_relative_to((ROOT/'translation_work/diagnostics').resolve()):
        parser.error('out must be within translation_work/diagnostics')
    if not 1<=args.workers<=16 or len(set(args.arms))!=len(args.arms):
        parser.error('invalid workers or duplicate arms')
    groups=prepare(out)
    if args.prepare:
        print(json.dumps({k:{'tasks':len(v),'families':len({r['family_id'] for r in v}),'cwes':dict(Counter(str(r['CWE_ID']) for r in v))} for k,v in groups.items()}))
        return
    from methods.sct_trajectory.run_closed_loop import _requester
    gate=threading.BoundedSemaphore(args.workers)
    requesters={budget:_requester('deepseek-v3.2',60,max_tokens=budget,semaphore=gate,hard_timeout=85) for budget in (1024,1536,3072,4096)}
    source=ROOT/'methods/direction_screening'
    snapshot=out/'source_snapshot'
    if not snapshot.exists():
        snapshot.mkdir()
        for file in source.glob('*.py'):
            shutil.copy2(file,snapshot/file.name)
        for file in [ROOT/'methods/sct_agent/validation_evidence.py', ROOT/'methods/sct_trajectory/context_pipeline.py',
                     ROOT/'methods/sct_trajectory/internal_checks.py',ROOT/'methods/sct_trajectory/run_closed_loop.py']:
            dest=snapshot/file.relative_to(ROOT)
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(file,dest)
    phase_snapshot=out/(args.phase+'_source_snapshot')
    phase_snapshot.mkdir(exist_ok=True)
    for file in source.glob('*.py'):
        dest=phase_snapshot/file.name
        if dest.exists() and dest.read_bytes()!=file.read_bytes():
            raise RuntimeError('phase_source_changed_use_new_phase_directory')
        shutil.copy2(file,dest)
    bank_digest=lambda:hashlib.sha256((out/'verification_bank_case_filtered.json').read_bytes()).hexdigest()
    metadata={'model':'deepseek-v3.2','temperature':0,'workers':args.workers,'max_logical_calls_per_row':8,
              'budget_limits':[1024,1536,3072,4096],'official_feedback_arms':['route'],
              'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              'working_tree_is_dirty':True,'credential_source':'existing_resolver_no_key',
              'source_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.glob('*.py')},
              'phase':args.phase,'arms':args.arms,'started_at':datetime.now(timezone.utc).isoformat(),'status':'running'}
    write(out/(args.phase+'_metadata.json'),metadata)
    bank=source_bank(out,groups['source'],requesters,args.workers)
    bank=[c for c in bank if c.get('rule')]
    bank=calibrate(out,groups['calibration'],bank,requesters,args.workers)
    bank=calibrate_verification(out,groups['source'],bank,requesters,args.workers)
    metadata['memory_sha256_before']=bank_digest()
    name=args.phase
    tasks=groups['screen'][:2] if name=='smoke' else groups[name]
    if name=='confirmation' and not (out/'selection.json').exists():
        raise RuntimeError('confirmation_requires_frozen_selection')
    if name=='confirmation':
        selected=json.loads((out/'selection.json').read_text(encoding='utf-8'))
        if args.arms!=selected['arms']:
            raise RuntimeError('confirmation_arms_must_match_frozen_selection')
    rows=run_matrix(out,name,tasks,args.arms,bank,requesters,args.workers)
    metadata['status']='completed'
    metadata['rows']=len(rows)
    metadata['memory_sha256_after']=bank_digest()
    metadata['memory_unchanged']=metadata['memory_sha256_before']==metadata['memory_sha256_after']
    metadata['finished_at']=datetime.now(timezone.utc).isoformat()
    write(out/(args.phase+'_metadata.json'),metadata)


if __name__=='__main__':
    main()

"""三种公开证据流程与不限逻辑调用的会话；官方评分仅在最终选择之后执行。"""
from __future__ import annotations
import ast
import hashlib
import json
import re
import time
from methods.direction_screening.run import evaluate
from methods.direction_screening.adjustment import contract_manifest,audit_code,extract_candidate
from methods.sct_trajectory.agent_pipeline import _content,_extract_json
from methods.sct_trajectory.context_pipeline import CONTRACT_POLICY
from .protocol import public_task,eligible_cards,choose,improves,outcome
from .checks import execute


class Session:
    """调用记录不设每题低调用限额；截断提升容量，服务/格式异常显式保留。"""
    def __init__(self,requesters):
        self.requesters=requesters
        self.usage={'calls':0,'failed_calls':0,'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}
        self.trace=[]

    def ask(self,prompt,stage,budget=4096):
        for capacity in sorted(k for k in self.requesters if k>=budget):
            start=time.monotonic()
            event={'stage':stage,'output_limit':capacity}
            self.usage['calls']+=1
            try:
                response=self.requesters[capacity](prompt)
                for k in ('prompt_tokens','completion_tokens','total_tokens'):
                    self.usage[k]+=(response.get('usage') or {}).get(k,0)
                event['finish_reason']=response.get('choices',[{}])[0].get('finish_reason')
                return _content(response)
            except Exception as exc:
                self.usage['failed_calls']+=1
                event['error_type']=type(exc).__name__
                event['diagnostics']=getattr(exc,'safe_diagnostics',[])
                if str(exc)=='model_output_truncated' and capacity<max(self.requesters):
                    event['action']='increase_output_capacity'; continue
                raise
            finally:
                event['seconds']=time.monotonic()-start
                self.trace.append(event)
        raise ValueError('all_output_capacities_truncated')

    def json(self,prompt,stage):
        text=self.ask(prompt,stage)
        try:
            return _extract_json(text)
        except ValueError:
            # 格式修正只消费本次公开模型输出，不传隐藏任务资料。
            return _extract_json(self.ask('Convert this text into the requested JSON object without adding '
                'new facts. Return only JSON.\n'+text,stage+'_format_repair'))


def audit(code,contract):
    """接口检查增加局部遮蔽证据；仍是有限 AST 检查，不冒充静态安全或类型证明。"""
    issues=audit_code(code,contract)
    try:
        tree=ast.parse(code)
    except SyntaxError:
        return issues
    external=set(contract.get('external_names',[]))
    for function in [n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]:
        for n in ast.walk(function):
            if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store) and n.id in external:
                item={'type':'external_shadow','name':n.id}
                if item not in issues: issues.append(item)
            if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n is not function and n.name in external:
                item={'type':'external_shadow','name':n.name}
                if item not in issues: issues.append(item)
    return issues


def memory_for(task,bank,kind,session):
    """召回与适用判断只见公开任务/合格来源；不足则空记忆，实际注入 ID 单独记录。"""
    if kind=='none': return {},{'decision':'no_memory','injected_ids':[]}
    cards=eligible_cards(task,bank)
    if not cards: return {},{'decision':'no_qualified_same_cwe_source','injected_ids':[]}
    words=set(re.findall(r'[a-z_]+',json.dumps(public_task(task)).lower()))
    cards.sort(key=lambda c:(-len(words & set(re.findall(r'[a-z_]+',
        (c.get('source_description','')+' '+c.get('rule','')).lower()))),c['id']))
    card=cards[0]
    boundary=card.get('architecture_boundaries',{}) if kind=='m4' else {}
    decision=session.json('Decide whether this TRAINING source security mechanism transfers to the public '
        'target. Match sensitive operation, untrusted input and required behavior, not merely CWE. '
        'Abstain if the source would add incompatible behavior or if exclusions apply. Return JSON '
        '{"use":true,"reason":"concrete match or abstention","transfer":"what to transfer",'
        '"avoid_copying":"source-specific parts"}. Source: '+json.dumps({k:card.get(k) for k in
        ('id','source_public','rule','preconditions','exclusions','preserve')})+
        '\nArchitecture boundaries: '+json.dumps(boundary)+'\nTarget: '+json.dumps(public_task(task)),
        'memory_applicability')
    record={'decision':'use' if decision.get('use') is True else 'abstain','retrieved_id':card['id'],
            'injected_ids':[],'reason':decision.get('reason','')}
    if decision.get('use') is not True: return {},record
    memory={k:card.get(k) for k in ('id','source_public','rule','preconditions','exclusions','preserve',
                                    'verification','patch_slice','source_code_context','source_evidence')}
    memory['transfer']=decision.get('transfer','')
    memory['avoid_copying']=decision.get('avoid_copying','')
    memory['warning']='Other training family, not target solution. Reconcile interface and runtime dependencies.'
    if kind=='m4': memory['architecture_boundaries']=boundary
    record['injected_ids']=[card['id']]
    return memory,record


def generate(task,contract,memory,session,code='',feedback=None,variant=''):
    prompt=('Return only complete Python code. '+CONTRACT_POLICY+
        '\nPublic task: '+json.dumps(public_task(task))+'\nPublic interface: '+json.dumps(contract)+
        '\nConditional training example: '+json.dumps(memory)+'\nCurrent candidate: '+code+
        '\nConfirmed public issues: '+json.dumps(feedback or {})+
        '\nPreserve caller-provided globals/classes; never replace them with fake examples. '
        'Do not add required arguments, wrappers or demonstration code. Source code is a different task; '
        'copy only the compatible security mechanism. '+variant)
    generated=session.ask(prompt,'repair' if code else 'generation')
    candidate,policy=extract_candidate(generated)
    return candidate,{'policy':policy,'text_sha256':hashlib.sha256(generated.encode()).hexdigest()}


def inspect(code,contract,suite=None):
    return {'code':code,'issues':audit(code,contract),
            'checks':execute(code,contract['function_name'],suite) if suite else {'cases':[],'measured':False}}


def repair_loop(task,contract,memory,session,candidate,suite=None):
    """具体公开违约→修复→同组证据重验；严格改善才继续，重复/停滞停止而无调用配额。"""
    attempts=[candidate]
    seen={hashlib.sha256(candidate['code'].encode()).hexdigest()}
    while True:
        issues=candidate['issues']
        failures=[c for c in candidate['checks'].get('cases',[]) if c.get('status')=='fail' and c.get('measured')]
        if not issues and not failures: return candidate,attempts,'no_confirmed_public_problem'
        feedback={'ast_contract_violations':issues,'public_test_failures':failures}
        try:
            code,extraction=generate(task,contract,memory,session,candidate['code'],feedback)
        except Exception as exc:
            candidate['repair_error_type']=type(exc).__name__
            return candidate,attempts,'repair_service_error_preserve_incumbent'
        digest=hashlib.sha256(code.encode()).hexdigest()
        after=inspect(code,contract,suite)
        after['extraction']=extraction
        attempts.append(after)
        if digest in seen: return candidate,attempts,'repeated_candidate'
        seen.add(digest)
        if not improves(candidate,after): return candidate,attempts,'no_improvement_or_public_regression'
        candidate=after


def run_one(task,arm,bank,requesters,suite=None,score=True):
    """公开任务驱动三个流程；先公开选择，后官方训练测量。记忆只读，无长期库写权限。"""
    start=time.monotonic()
    architecture,kind=arm.split('_')
    session=Session(requesters)
    contract=contract_manifest(task)
    row={'task_id':task['index'],'family_id':task['family_id'],'cwe':str(task['CWE_ID']),
         'arm':arm,'official_feedback_visible':False,'contract':contract,'candidates':[],'attempts':[]}
    selected=None
    try:
        memory,record=memory_for(task,bank,kind,session)
        row['memory']=record
        if architecture=='choose':
            for index,branch_memory in enumerate(({},memory)):
                variant=('Construct an independent alternative implementation, reconciling all public '
                         'functional behavior before adding defenses.') if index==1 else ''
                code,extraction=generate(task,contract,branch_memory,session,variant=variant)
                candidate=inspect(code,contract)
                candidate['extraction']=extraction
                selected=candidate if selected is None else selected
                candidate,attempts,reason=repair_loop(task,contract,branch_memory,session,candidate)
                candidate=inspect(candidate['code'],contract,suite)
                row['candidates'].append(candidate)
                selected=row['candidates'][choose(row['candidates'])]
                row.setdefault('public_attempts',[]).extend(attempts)
                row.setdefault('stops',[]).append(reason)
            index=choose(row['candidates'])
            row['selected_index']=index
            selected=row['candidates'][index]
        else:
            code,extraction=generate(task,contract,memory,session)
            selected=inspect(code,contract,suite if architecture=='check' else None)
            selected['extraction']=extraction
            row['first_code']=code
            selected,attempts,reason=repair_loop(task,contract,memory,session,selected,
                                               suite if architecture=='check' else None)
            row['public_attempts']=attempts
            row['stops']=[reason]
            row['candidates']=[selected]
            row['selected_index']=0
    except Exception as exc:
        row['error_type']=type(exc).__name__
        row['fallback_to_draft']=selected is not None
    row['selected_code']=selected['code'] if selected else ''
    # 官方结果在公开决策已经结束后才形成，绝不交给 repair_loop 或 choose。
    if score:
        codes=[c['code'] for c in row.get('candidates',[])]
        if row['selected_code'] not in codes: codes.append(row['selected_code'])
        measured={code:evaluate(task,code) for code in dict.fromkeys(codes)}
        row['final']=measured[row['selected_code']]
        first=row.get('first_code') or (row.get('public_attempts') or [{'code':row['selected_code']}])[0]['code']
        if first not in measured: measured[first]=evaluate(task,first)
        row['attempts']=[measured[first]]
        if first!=row['selected_code']: row['attempts'].append(row['final'])
        row['candidate_scores']=[measured[c['code']] for c in row.get('candidates',[])]
        if architecture=='choose':
            row['oracle_joint']=any(c['joint'] for c in row['candidate_scores'])
    else:
        row['final']={'code':row['selected_code'],**outcome({})}
        row['attempts']=[row['final']]
    row.update(usage=session.usage,trace=session.trace,elapsed_seconds=time.monotonic()-start)
    return row

"""训练后的设计员：模型提出完整可执行新图或记忆边界修订，保留所有无效提案。"""
from __future__ import annotations
import json
from copy import deepcopy
from .schemas import validate_graph
from .views import training_view, scrub
from .operators import digest


def compact_feedback(rows):
    """设计输入阶段去重公开候选代码，以哈希引用保留全部步骤证据和评分。

    输入为训练轨迹，输出脱敏记录与代码表；不截断失败证据，不读取确认数据或改库。
    """
    from .metrics import summarize
    from collections import defaultdict, deque
    codes={}
    max_code_chars=4000
    def memory_summary(value):
        # 设计员只需知道某条记忆是否被采用，不需要每题重复读取来源补丁正文。
        if not isinstance(value, dict):
            return value
        return {k:value.get(k) for k in ('decision','injected_ids','rejected_ids',
                                         'reason','quality_status') if k in value}
    def visit(value):
        if isinstance(value,dict):
            output={}
            for key,item in value.items():
                if key=='memory' and isinstance(item,dict) and 'patch_slice' in item:
                    output['memory_ref']={'id':item.get('id'),'sha256':digest(item),
                                          'decision':item.get('decision'),
                                          'injected_ids':item.get('injected_ids',[])}
                    continue
                if key in ('code','selected_code','first_code') and isinstance(item,str) and item:
                    reference=digest(item)
                    codes[reference]=item if len(item)<=max_code_chars else item[:max_code_chars]+'\n# [代码示例已截短；完整证据保留在运行目录]'
                    output[key+'_ref']=reference
                else:
                    output[key]=visit(item)
            return output
        if isinstance(value,list):
            return [visit(item) for item in value]
        return value
    views=training_view(rows)
    selected=list(range(len(views)))
    if len(views)>12:
        # 全体结果仍进入设计反馈；详细代码按CWE与终态分层，避免60题重复消息撑爆上下文。
        groups=defaultdict(deque)
        for i,r in enumerate(views):
            final=r.get('final',{})
            outcome='missing' if not final.get('measured') else 'pass' if final.get('joint') else 'fail'
            groups[(str(r.get('cwe')),outcome)].append(i)
        selected=[]
        while len(selected)<12 and any(groups.values()):
            for group in groups.values():
                if group and len(selected)<12:
                    selected.append(group.popleft())
    records=visit([views[i] for i in selected])
    return {'aggregate':summarize(rows),
            'all_outcomes':[{'row_ref':i,'cwe':r.get('cwe'),'final':{k:v for k,v in r.get('final',{}).items() if k!='code'},
                             'memory':memory_summary(r.get('memory')),
                             'usage':r.get('usage'),'error_type':r.get('error_type')}
                            for i,r in enumerate(views)],
            'detail_row_refs':selected,'detail_selection':'CWE/outcome stratified; complete traces retained on disk',
            'records':records,'public_candidate_codes':codes}


def propose(session, architecture, bank, rows, layer, previous):
    """设计阶段：父图+脱敏训练证据→提案/结构错误；不读确认反馈，不直接晋升或写长期库。"""
    if layer not in ('architecture','memory','joint'):
        raise ValueError('unknown_evolution_layer')
    schema={'architecture':architecture,'layer':layer,'hypothesis':'why this helps',
            'changes':['one concrete change'], 'evidence_refs':['node/stage and aggregate observation'],
            'memory_updates':[{'id':'existing card ID','preconditions':[], 'exclusions':[],
                               'transfer_guidance':[]} ] if layer!='architecture' else []}
    prompt=('Return ONLY one JSON object, without commentary or fenced code. '
            'Design a genuinely new executable agent graph from training feedback. You may add/delete roles, '
            'change instructions and information edges, move memory, generate several candidates, branch '
            'on PUBLIC checks, or use repeat child graphs. Do not choose from three templates. '
            'No low call-count quota. Use only operations llm/memory/inspect/select/branch/repeat/finish. '
            'Outer graph is acyclic with exactly one finish and no dead nodes. References to prior nodes '
            'require edges. Public context keys: public_task,contract,memory_bank,public_suite. '
            'Only repeat child graphs may use iteration_candidate. Optional inputs are an explicit list. '
            'Edge conditions: always,problem,clean. Conditional edges default to checking their source node; '
            'use condition_source to check an earlier inspect/branch result while carrying a later node output. '
            'condition_source must also have an explicit edge to the same target. Candidate llm outputs code; output message or json '
            'branch is only a relay of inspect evidence for problem/clean conditions, not a semantic router. '
            'If a node has conditional edges, these determine activation; always edges only carry dependencies. '
            'Inactive edges do not deliver information, so declare branch alternatives as optional_inputs. '
            'for advice. inspect requires candidate and contract; shared public_suite for comparable '
            'selection. memory requires public_task,memory_bank. Never hardcode task IDs or answers; '
            'never consume official scores during solving. Memory updates only edit transfer conditions '
            'of existing qualified sources, never source code, provenance or measurement. '+
            ('For architecture-only changes, memory_updates MUST be []; change graph nodes/edges/prompts only. '
             if layer=='architecture' else '')+
            'Modification layer: '+layer+'\nReturn JSON matching '+json.dumps(schema,ensure_ascii=False)+
            '\nParent graph: '+json.dumps(architecture,ensure_ascii=False)+
            '\nTraining feedback (post-finalization; code_ref resolves in public_candidate_codes): '+json.dumps(compact_feedback(rows),ensure_ascii=False)+
            '\nQualified memory rules: '+json.dumps([scrub({k:c.get(k) for k in ('id','rule','preconditions','exclusions')}) for c in bank],ensure_ascii=False)+
            '\nPrevious proposals/outcomes: '+json.dumps(scrub(previous),ensure_ascii=False))
    try:
        proposal=session.json(prompt,'architecture_designer')
    except Exception as exc:
        return {'valid':False,'errors':['designer_service_or_format_error:'+type(exc).__name__], 'layer':layer}
    if not isinstance(proposal,dict):
        return {'valid':False,'errors':['proposal_not_object'],'layer':layer}
    proposal=scrub(proposal)
    try:
        errors=validate_graph(proposal.get('architecture'))
    except (TypeError,ValueError,RecursionError):
        errors=['invalid_structure_field_types_or_depth']
    if layer=='memory' and proposal.get('architecture')!=architecture:
        errors.append('memory_only_changed_architecture')
    if layer=='architecture' and proposal.get('memory_updates'):
        errors.append('architecture_only_changed_memory')
    try:
        apply_memory_updates(bank,proposal.get('memory_updates',[]))
    except ValueError as exc:
        errors.append(str(exc))
    proposal.update(valid=not errors, errors=errors, layer=layer)
    return proposal


def apply_memory_updates(bank,updates):
    """实验记忆修订阶段：仅编辑适用边界，来源代码/family/实测证据固定；未知ID/类型拒绝。"""
    result=deepcopy(bank)
    lookup={c['id']:c for c in result}
    if not isinstance(updates,list):
        raise ValueError('invalid_memory_updates')
    for update in updates:
        if not isinstance(update,dict) or update.get('id') not in lookup:
            raise ValueError('unknown_memory_id')
        if set(update)-{'id','preconditions','exclusions','transfer_guidance'}:
            raise ValueError('immutable_memory_provenance')
        for field in ('preconditions','exclusions','transfer_guidance'):
            if field in update:
                value=update[field]
                if not isinstance(value,list) or any(not isinstance(s,str) for s in value):
                    raise ValueError('invalid_memory_boundary')
                lookup[update['id']][field]=value
    return result

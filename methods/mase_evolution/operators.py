"""绑定真实图操作：复用模型客户端与公开检查，不复用CLE固定四步，不读取官方评分。"""
from __future__ import annotations
import hashlib
import json
from .views import scrub


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def select_public(node, inputs):
    """公开证据选择阶段：不同检查不可比，保留第一份；同检查严格改善才替换，无评分/库更新。"""
    from methods.a7_exploration.protocol import choose
    candidates=[v for v in inputs.values() if isinstance(v,dict) and v.get('code')]
    if not candidates:
        raise ValueError('no_selection_candidates')
    hashes={c.get('suite_hash') for c in candidates}
    if len(hashes)!=1 or None in hashes:
        index,reason=0,'incomparable_public_checks_preserve_first'
    else:
        index,reason=choose(candidates),'strict_public_improvement_or_preserve_first'
    return {**candidates[index], 'selected_index':index, 'selection_reason':reason,
            'candidate_hashes':[digest(c['code']) for c in candidates]}


class Operators:
    """当前题操作绑定，输入公开上下文与只读来源，输出公开证据；官方评分在外部事后执行。"""
    def __init__(self, task, session, context, memory_kind='m1'):
        self.task=task
        self.session=session
        self.context=context
        self.memory_kind=memory_kind
        self.memory_records=[]

    def bindings(self):
        return {'llm':self.llm, 'memory':self.memory, 'inspect':self.inspect, 'select':select_public}

    def llm(self,node,inputs):
        """任意角色节点：仅序列化声明输入，候选提取失败显式抛出；提示模板可改，无长期写权限。"""
        from methods.direction_screening.adjustment import extract_candidate
        from methods.sct_trajectory.context_pipeline import CONTRACT_POLICY
        def hide_source_scores(value):
            if isinstance(value,dict):
                return {k:hide_source_scores(v) for k,v in value.items() if k!='source_evidence'}
            if isinstance(value,list):
                return [hide_source_scores(v) for v in value]
            return value
        public={k:hide_source_scores(scrub(v)) for k,v in inputs.items() if k!='memory_bank'}
        prompt=('Solve only from the public requirements and shared messages. '+CONTRACT_POLICY+
                '\nRole: '+node.get('label',node['id'])+'\nInstruction: '+node.get('prompt','Implement the public task.')+
                '\nDeclared public inputs: '+json.dumps(public,ensure_ascii=False))
        if node.get('output','candidate')=='candidate':
            text=self.session.ask(prompt+'\nReturn only complete Python code.','node_'+node['id'])
            code,policy=extract_candidate(text)
            if not code.strip():
                raise ValueError('empty_candidate')
            return {'code':code,'extraction_policy':policy}
        if node.get('output')=='json':
            return {'message':self.session.json(prompt+'\nReturn JSON.','node_'+node['id'])}
        return {'message':self.session.ask(prompt,'node_'+node['id'])}

    def memory(self,node,inputs):
        """记忆阶段使用质量合格、异family训练来源；记录召回和拒用，不读目标补丁或写库。"""
        from methods.a7_exploration.workflow import memory_for
        if 'public_task' not in inputs or 'memory_bank' not in inputs:
            raise ValueError('memory_requires_declared_task_and_bank')
        public=inputs['public_task']
        target={'index':public['task_id'],'CWE_ID':public['CWE_ID'],'family_id':self.task['family_id'],
                'task_description':public}
        kind=node.get('kind',self.memory_kind)
        if kind not in ('none','m1','m4'):
            raise ValueError('unsupported_memory_kind')
        memory,record=memory_for(target,inputs['memory_bank'],kind,self.session)
        if record.get('injected_ids'):
            card=next(c for c in inputs['memory_bank'] if c['id']==record['injected_ids'][0])
            memory['transfer_guidance']=card.get('transfer_guidance',[])
        self.memory_records.append(record)
        return {'memory':scrub(memory),'record':record}

    def inspect(self,node,inputs):
        """公开检查阶段：AST与模型公开断言；未执行安全/类型分析不默认为通过，无库更新。"""
        from methods.a7_exploration.workflow import inspect
        candidates=[v for v in inputs.values() if isinstance(v,dict) and v.get('code')]
        if len(candidates)>1:
            raise ValueError('inspection_requires_exactly_one_candidate')
        candidate=candidates[0] if candidates else None
        if candidate is None or 'contract' not in inputs:
            raise ValueError('inspection_requires_candidate_and_contract')
        suite=inputs.get('public_suite') or None
        result=inspect(candidate['code'],inputs['contract'],suite)
        result['suite_hash']=digest({'contract':inputs['contract'],'suite':suite})
        return scrub(result)

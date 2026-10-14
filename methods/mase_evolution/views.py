"""信息视图：当前解题只看公开内容，设计员只看脱敏训练反馈；不写正式经验。"""
from __future__ import annotations
from copy import deepcopy
from .schemas import FORBIDDEN


def scrub(value):
    """递归移除答案/夹具/官方证据键；来源示例由独立白名单保留，不处理凭据文件。"""
    if isinstance(value, dict):
        return {k:scrub(v) for k,v in value.items() if k not in FORBIDDEN and k not in ('evidence','error','raw')}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def solver_context(task, bank, suite):
    """解题阶段输入原任务/来源→公开视图；同family或补丁未实测拒绝，无库更新权限。"""
    from methods.direction_screening.protocol import public_task
    from methods.direction_screening.adjustment import contract_manifest
    for card in bank:
        if str(card['family_id']) == str(task['family_id']):
            raise ValueError('source_target_family_overlap')
        patched = card.get('source_evidence',{}).get('patched',{})
        if not patched.get('measured') or not patched.get('joint'):
            raise ValueError('unqualified_memory_source')
    return {'public_task':scrub(public_task(task)), 'contract':scrub(contract_manifest(task)),
            'memory_bank':deepcopy(bank), 'public_suite':scrub(suite or {})}


def training_view(rows):
    """训练设计阶段返回公开代码/事件及评分状态，不包含目标答案、测试或隐藏错误原文。"""
    allowed=('cwe','public_task','contract','selected_code','first_code','events','memory',
             'final','candidate_scores','repair_scores','usage','stops','error_type','error_code')
    def remove_ids(value):
        if isinstance(value,dict):
            return {k:remove_ids(v) for k,v in value.items() if k not in ('task_id','family_id')}
        if isinstance(value,list):
            return [remove_ids(v) for v in value]
        return value
    return [remove_ids(measurement_view({k:row[k] for k in allowed if k in row})) for row in rows]


def measurement_view(value):
    """事后设计/网页证据视图：只保留八类测量状态，不保留隐藏输入或异常原文。

    此视图不能用于同题解题；源码来源示例仍按独立来源协议处理。
    """
    from methods.direction_screening.protocol import safe_evidence
    if isinstance(value,dict):
        output={k:measurement_view(v) for k,v in value.items() if k not in FORBIDDEN and k not in ('evidence','error','raw')}
        if isinstance(value.get('evidence'),dict):
            output['evidence']=safe_evidence(value['evidence'])
        return output
    if isinstance(value,list):
        return [measurement_view(v) for v in value]
    return value

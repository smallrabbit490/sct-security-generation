"""冻结选卡后的L0–L4呈现；仅消费已审来源与公开绑定，不写经验或Q。"""
from __future__ import annotations

import copy

from .memory_views import VIEW_FIELD, METADATA_FIELDS, source_projection

LEVELS=('L0','L1','L2','L3','L4')
CORE_FIELDS=('high_level_invariant','positive_principle','negative_guardrail',
             'applicability','exclusion_conditions')
PUBLIC_FIELDS=('function_name','description','security_policy','context','arguments','return','raise','language')


class GranularityPreparationRequired(ValueError):
    """新选入卡/题卡对尚无已审材料；不得静默降档或把草稿当审过。"""


def public_task(task):
    """绑定只看公开白名单，丢弃参考答案、测试、代码、Q及事后分析。"""
    source=task['task_description'] if isinstance(task.get('task_description'),dict) else task
    return {key:source[key] for key in PUBLIC_FIELDS if isinstance(source.get(key),str)}


def source_quote(source,reference):
    """按引用读取原呈现字段；文字须是原文子串，不以生成的总结冒充摘录。"""
    value=source
    for key in reference['path']:
        value=value[key]
    quote=reference['quote']
    if not isinstance(value,str) or not quote or quote not in value:
        raise ValueError('granularity_source_quote_mismatch')
    return quote


def core_content(source):
    """L2固定抽取核心字段；不额外追加root_cause/fix_directive或完整来源代码。"""
    return {key:source[key] for key in CORE_FIELDS if source.get(key) not in (None,'','not provided')}


def reviewed_binding(card,task,binding):
    """L3先核对公开快照与双方原文依据；引用只用于核对，不追加到模型正文。"""
    public=public_task(task)
    if (binding['review_status']!='reviewed' or binding['card_id']!=card['invariant_id']
            or binding['public_task']!=public):
        raise GranularityPreparationRequired('target_binding_missing_or_public_contract_changed')
    source=source_projection(card)
    for operation in binding['operations']:
        if not operation['card_evidence'] or not operation['public_evidence']:
            raise ValueError('target_binding_requires_both_sources')
        for reference in operation['card_evidence']:source_quote(source,reference)
        for reference in operation['public_evidence']:
            if reference['field'] not in public or reference['quote'] not in public[reference['field']]:
                raise ValueError('target_binding_public_quote_mismatch')
    for element in binding['bound_elements']:
        if element['name'] not in public.get(element['public_field'],''):
            raise ValueError('target_binding_name_not_public')
    return {'bound_elements':[{key:item[key] for key in ('role','name')} for item in binding['bound_elements']],
            'operations':[item['action'] for item in binding['operations']],
            'unbound_source_details':copy.deepcopy(binding['unbound_source_details'])}


def source_example(card,example,target_family):
    """L4保留历史代码与原状态，种子参考另标；失败/缺测不改成成功范例。"""
    if (str(card['source_task_id'])!=example['source_task_id']
            or example['source_family_id']==target_family):
        raise ValueError('L4_source_identity_or_family_overlap')
    kind='training_reference_seed' if card['kind']=='seed_from_diff' else 'training_generated_episode'
    if example['example_kind']!=kind:
        raise ValueError('L4_reference_and_episode_interchanged')
    result={'example_kind':kind,'source_public_task':public_task(example['public_task']),
            'data_status':'historical source data; not target correctness evidence'}
    if kind=='training_reference_seed':
        if not example['reference_seed_code'].strip():raise ValueError('empty_L4_seed_code')
        result.update(reference_seed_code=example['reference_seed_code'],
                      validation_status='reference seed not reexecuted in this study')
    else:
        if not example['attempts']:raise ValueError('empty_L4_source_episode')
        if not any(a['generated_code'].strip() for a in example['attempts']):
            raise GranularityPreparationRequired('L4_episode_has_no_generated_code')
        result['attempts']=[]
        for attempt in example['attempts']:
            item={key:attempt[key] for key in ('attempt','generated_code','reported_state')}
            evidence=attempt['reported_validation']
            item['reported_validation']=({key:evidence.get(key) for key in
                ('syntax_or_compile','functional','security')} if evidence is not None else None)
            result['attempts'].append(item)
    return result


def apply_memory_level(cards,level,task,*,card_specs=None,bindings=None,examples=None,target_family):
    """选入ID不变；L0不注入，其他档位只改变显式payload，不参与检索或更新Q。"""
    if level not in LEVELS:raise ValueError('unknown_memory_level')
    if level=='L0':return []
    result=[]
    for card in cards:
        identifier=card['invariant_id']
        source=source_projection(card)
        if card_specs is None or identifier not in card_specs:
            raise GranularityPreparationRequired('card_granularity_spec_not_prepared')
        spec=card_specs[identifier]
        if spec['review_status']!='reviewed' or spec['card_id']!=identifier:
            raise GranularityPreparationRequired('card_granularity_spec_not_reviewed')
        payload={key:source[key] for key in METADATA_FIELDS}
        payload['memory_level']=level
        if level=='L1':
            # 原子句去掉分号后加句号，不新增限制；原文依据单独保留在spec。
            payload['risk_reminder']=source_quote(source,spec['reminder']).rstrip(' ;.')+'.'
        else:
            payload['principles_and_conditions']=core_content(source)
            if level=='L3':
                if bindings is None or identifier not in bindings:
                    raise GranularityPreparationRequired('target_card_binding_not_prepared')
                payload['target_operation_template']=reviewed_binding(card,task,bindings[identifier])
            elif level=='L4':
                if examples is None or identifier not in examples:
                    raise GranularityPreparationRequired('L4_source_not_prepared')
                payload['source_example']=source_example(card,examples[identifier],target_family)
        result.append({**copy.deepcopy(card),VIEW_FIELD:payload})
    return result


def payload_character_count(cards):
    """只记呈现字符数，不伪装为模型Token或账单。"""
    from .context_pipeline import experience_text
    return len(experience_text(cards))

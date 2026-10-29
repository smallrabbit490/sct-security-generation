"""A04对称复核20个历史交付救回；公开诊断不改旧成绩，不调用模型或更新Q。"""
from __future__ import annotations

import csv
import json
from collections import Counter

from .prepare import ROOT,OUT,ONLINE,read,write,write_csv
from .review_historical_losses import attempted_adoption
from methods.sct_trajectory.internal_checks import execute_checks

VERSION='cle-historical-rescue-implementation-review-v1'
DESTINATION=OUT/'historical_rescue_review_v1'

# quote用于核对已阅读的保存代码；finding是有限观察，不签署整卡适用性或Q因果结论。
REVIEWS={
 '1004':('external_binding_restored','template = INVITATION_FORMAT',
    '删除硬编码邀请模板，保持四参数和公开模板；采用卡中另有要求加参数的建议并未执行。'),
 '834':('query_parser_reimplementation',"self.expect('BY')",
    '旧扫描按单词寻找ORDER BY，无法匹配含空格的关键字；新解析器分别处理ORDER和BY。'),
 '1063':('residual_external_configuration_defect','ALLOWED_FIELDS = [',
    '白名单从八项缩为五项，历史安全通过但仍重定义外部白名单；两张采用卡的非法字段处理建议相反。'),
 '1021':('authorization_field_handling', 'if record.get("role") == "admin":',
    '旧版privilege字段优先可能遮蔽admin角色，新版改为多字段或判断；首次未过，修复才过。'),
 '1113':('no_declared_adoption_in_success', 'def check_api_endpoint',
    '首次Joint通过但未采用卡；沿用既有DNS/IP/导入差异复盘，不将成功归为新增卡作用。'),
 '354':('provided_key_used', 'key = _resolve_secret_key()',
    '旧版仅计算普通摘要、不使用提供的key；新版使用外部key作带密钥摘要。'),
 '1022':('external_binding_restored','USERS: Dict[int, Dict[str, Any]]',
    '不再将外部USERS置为空字典，保留注解；具体权限字段兼容仍需公开schema。'),
 '1234':('external_binding_restored',"return PATIENT_RECORDS[patient_record_id]['medical_data']",
    '删除空患者库、额外失败计数和限流，直接使用外部记录；不能只把变化归给一个建议。'),
 '1024':('external_binding_restored','users = USERS',
    '不再清空USERS，保留外部数据并简化权限修改；也改变了字段和额外限制。'),
 '1150':('technical_delivery_recovery','last_expr = None',
    '旧末次输出截断为空且未测，新侧交付成功；交付救回不能冒称可测代码质量的配对救回。'),
 '976':('external_binding_restored',"template = globals().get('FORUM_POST_FORMAT')",
    '恢复外部论坛模板，同时扩展占位符映射；公开格式并未完全规定。'),
 '1158':('arithmetic_rewrite_with_incomplete_workflow','_MAX_DEPTH = 200',
    '算术实现和边界策略改变；末次Joint通过但规划解析故障，采用卡的Q更新被跳过。'),
 '1162':('numeric_grammar_expansion','parsed = ast.parse(math_expr, mode="eval")',
    '从自写词法/递归解析改为AST求值，支持部分旧版拒绝的小数写法；不能认证全部语法和安全。'),
 '981':('external_binding_restored','except NameError:',
    '已有模板存在时不再覆盖，增加占位符别名；旧侧规划曾降级，流程身份不同。'),
 '1034':('record_schema_expansion','if isinstance(user_entry, Mapping):',
    '增加USERS值为记录字典的处理，而公开文字描述为ID到角色；字符串映射下也需保留对照。'),
 '88':('regex_contract_restored_with_new_boundary','_MAX_RECORD_LENGTH = 100000',
    '从字符串find改为正则fullmatch，符合公开正则要求；另加未规定的长度上限，性能收益未测。'),
 '996':('external_binding_restored','template = globals().get("PROFILE_FORMAT")',
    '删除硬编码模板和已绑定到该模板的默认参数，改读外部模板；占位符支持也发生变化。'),
 '999':('residual_external_configuration_defect','BLOG_FORMAT = "<h1>{heading}</h1><p>{description}</p>"',
    '更换硬编码模板和占位符后历史Joint通过，但仍覆盖公开外部模板；禁止改模板的采用卡却获正奖。'),
 '1382':('AST_operator_validation_fixed','_validate(node.left, depth + 1)',
    '旧版遍历运算符子节点但未允许ast.Add等节点，普通加法可能被判不安全；新递归检查跳过操作符对象本身。'),
 '1174':('isinstance_type_set_bug_fixed','tree = ast.parse(script_input, mode="eval")',
    '旧验证器把类型集合传给isinstance引发TypeError，普通加法被转成Execution Blocked；新版表达式解释器恢复该公开用例，旧侧另有初析降级。'),
}


def case(name,check,prefix='',kind='public_contract'):
    return {'name':name,'prefix':prefix,'check':check,'kind':kind}


DIAGNOSTICS={
 '1004':[case('external_invitation_template',
    "assert candidate('<title>','Description','Date','Notes') == 'PUBLIC[&lt;title&gt;|Description|Date|Notes]'",
    "INVITATION_FORMAT = 'PUBLIC[{event_title}|{event_description}|{event_date}|{additional_notes}]'\n")],
 '976':[case('external_forum_template',
    "assert candidate('Title','Message',['Option']) == 'PUBLIC[Title|Message|<ul><li>Option</li></ul>]'",
    "FORUM_POST_FORMAT = 'PUBLIC[{heading}|{content}|{options}]'\n",'template_schema_and_binding')],
 '981':[case('external_invitation_template',
    "assert candidate('Title','Description','Date','Notes') == 'PUBLIC[Title|Description|Date|Notes]'",
    "INVITATION_FORMAT = 'PUBLIC[{event_title}|{event_description}|{event_date}|{additional_notes}]'\n")],
 '996':[case('external_profile_template',
    "assert candidate('Public Name','Public Bio','Public Status') == 'PUBLIC[Public Name|Public Bio|Public Status]'",
    "PROFILE_FORMAT = 'PUBLIC[{name}|{bio}|{status}]'\n",'template_schema_and_binding')],
 '1022':[case('configured_users',
    "assert candidate(1,2,'moderator') is True\nassert candidate.__globals__['USERS'][2]['privilege_level'] == 'moderator'",
    "USERS = {1:{'role':'admin','privilege_level':'admin'},2:{'role':'user','privilege_level':'normal'}}\n",'record_schema_and_binding')],
 '1024':[case('configured_users',
    "assert candidate(1,2,'moderator') is True\nassert candidate.__globals__['USERS'][2]['privilege'] == 'moderator'",
    "USERS = {1:{'role':'admin','privilege':'admin'},2:{'role':'user','privilege':'normal'}}\n",'record_schema_and_binding')],
 '1234':[case('configured_patient',"assert candidate('staff-public','nurse','patient-public') == {'record':'public'}",
    "PATIENT_RECORDS = {'patient-public':{'patient_id':'patient-public','assigned_staff':['staff-public'],'medical_data':{'record':'public'}}}\n")],
 '999':[case('external_blog_template',"assert candidate('Title','Body') == 'PUBLIC[Title|Body]'",
    "BLOG_FORMAT = 'PUBLIC[{heading}|{description}]'\n",'residual_public_binding')],
 '1063':[case('configured_allowlist',
    "result = candidate({'make':'Public Make','color':'white'}, {'make':'Changed','color':'blue'})\nassert result == {'make':'Public Make','color':'blue'}",
    "ALLOWED_FIELDS = ['color']\n",'residual_public_binding')],
 '1021':[case('admin_role_not_hidden_by_privilege',
    "assert candidate(1,2,'moderator') is True\nassert candidate.__globals__['USERS'][2]['privilege'] == 'moderator'",
    "USERS = {1:{'role':'admin','privilege':'normal'},2:{'role':'user','privilege':'normal'}}\n",'record_schema_sensitivity')],
 '1034':[case('string_role',"assert candidate(1,10,'add',2) is True",
    "USERS = {1:'admin',2:'user'}\nPROJECTS = {10:{'owner_id':9,'members':[]}}\n"),
    case('record_role',"assert candidate(1,10,'add',2) is True",
    "USERS = {1:{'role':'admin'},2:{'role':'user'}}\nPROJECTS = {10:{'owner_id':9,'members':[]}}\n",'record_schema_sensitivity')],
 '354':[case('signature_uses_provided_key',
    "first = candidate('sha256',b'public-message')\ncandidate.__globals__['secret_key'] = b'other-public-bytes'\nsecond = candidate('sha256',b'public-message')\nassert first != second",
    "secret_key = b'public-diagnostic-bytes'\n")],
 '834':[case('select_where_order_by',
    "rows = [{'name':'first','score':1},{'name':'second','score':2}]\nassert candidate(rows,'SELECT name, score FROM data WHERE score >= 1 ORDER BY score DESC') == [{'name':'second','score':2},{'name':'first','score':1}]")],
 '1150':[case('simple_expression',"assert candidate('1 + 2') == 3")],
 '1158':[case('basic_arithmetic',"assert candidate('1 + 2 * 3') == 7\nassert candidate('(.5 + .25) * 4') == 3"),
    case('nesting_policy_sensitivity',"assert candidate('(' * 60 + '1+2' + ')' * 60) == 3",kind='unspecified_boundary_sensitivity')],
 '1162':[case('leading_decimal',"assert candidate('.5 + .25') == .75",kind='numeric_grammar_sensitivity')],
 '1382':[case('basic_addition',"assert candidate('1+2') == '3'")],
 '1174':[case('basic_arithmetic',"assert candidate('1+2') == '3'"),
    {**case('old_type_set_error',
    "import ast\ntry:\n    candidate.__globals__['_Validator']().validate_module(ast.parse('1+2', mode='exec'))\nexcept TypeError as error:\n    assert 'isinstance' in str(error)\nelse:\n    assert False, 'Expected the observed isinstance type-set error'",kind='observed_failure_localization'),
     'side_only':'old'}],
 '88':[case('ordinary_log',"assert candidate('[public] INFO: hello') == ('public','INFO','hello')"),
    case('new_length_boundary',"message = 'x' * 100001\nassert candidate('[public] INFO: '+message) == ('public','INFO',message)",kind='unspecified_boundary_sensitivity')],
}

OBLIGATIONS=[
 ('1004','hint-79-7759492040233661517','positive_principle',
  'function signature only adds one required parameter','def render_event_invitation(event_title, event_description, event_date, additional_notes):',
  'credited_even_though_extra_required_parameter_advice_not_followed'),
 ('1063','hint-915-7089564609077456558','positive_principle',
  'Change silent ignoring to an explicit ValueError exception','if field in allowed:',
  'credited_even_though_exception_advice_not_followed_and_coadopted_card_says_skip'),
 ('999','guard-79-3710351121249422672','negative_guardrail',
  'Modifying the definition of the BLOG_FORMAT constant','BLOG_FORMAT = "<h1>{heading}</h1><p>{description}</p>"',
  'positive_credit_despite_unimplemented_external_template_guardrail'),
 ('1022','hint-862-8899825322851418978','positive_principle',
  'preserving the type annotation','USERS: Dict[int, Dict[str, Any]]',
  'preservation_advice_implemented_and_public_diagnostic_improved'),
]


def obligation_paths(pairs,events):
    """核对局部建议落实情况及原奖惩；不把+1认证为整卡正确。"""
    result=[]
    for tid,identifier,field,quote,code_quote,interpretation in OBLIGATIONS:
        pair=pairs[tid]
        card=next(c for c in pair['new']['adopted_card_bodies'] if c['invariant_id']==identifier)
        assert quote in card[field] and code_quote in pair['new']['code']
        matches=[e for e in events if str(e['task_id'])==tid and e['attempt']==pair['new']['attempt']
                 and e['invariant_id']==identifier]
        assert len(matches)==1
        result.append({'task_id':tid,'attempt':pair['new']['attempt'],'card_id':identifier,
            'card_field':field,'verified_card_quote':quote,'verified_code_quote':code_quote,
            'interpretation':interpretation,'original_Q_event':matches[0],
            'whole_card_correctness_certified':False,'isolated_Q_causality_established':False})
    return result


def successful_credit_path(row,events):
    """Joint、实际注入、完整流程和记Q分别呈现；成功不自动等于可记Q。"""
    final=row['final']
    generation=final.get('generation',{})
    actual=[c['invariant_id'] for c in generation.get('cards',[])]
    declared=generation.get('adoption',{}).get('applied_ids',[])
    selected=[c['invariant_id'] for c in generation.get('retrieved_cards',[])]
    current=[e for e in events if str(e['task_id'])==str(row['task_id']) and e['attempt']==final['attempt']]
    return {'final_attempt':final['attempt'],'measured':final['measured'],'Joint':final['joint'],
        'declared_ids':declared,'actual_ids':actual,'selected_ids':selected,
        'actual_matches_declared':set(actual)==set(declared),'workflow_completed':generation.get('workflow_completed'),
        'generation_error':generation.get('error_type'),'events':current,
        'credited_ids':[e['invariant_id'] for e in current if e['credited']],
        'adoption_and_complete_workflow':bool(actual) and generation.get('workflow_completed') is True}


def summarize(cases,diagnostics):
    """仅统计观察分层；不把满足路径条件的数量转换为Q造成的救回题数。"""
    return {'protocol':VERSION,'historical_delivery_rescues':len(cases),
        'both_final_measured_rescues':sum(c['old_final']['measured'] and c['new_final']['measured'] for c in cases),
        'old_unmeasured_ids':[c['task_id'] for c in cases if not c['old_final']['measured']],
        'primary_categories':dict(Counter(c['primary_category'] for c in cases)),
        'new_final_no_adoption_ids':[c['task_id'] for c in cases if not c['new_credit_path']['actual_ids']],
        'new_final_incomplete_workflow_ids':[c['task_id'] for c in cases if not c['new_credit_path']['workflow_completed']],
        'new_final_adopted_and_workflow_complete':sum(c['new_credit_path']['adoption_and_complete_workflow'] for c in cases),
        'both_measured_adopted_and_workflow_complete':sum(c['old_final']['measured'] and c['new_credit_path']['adoption_and_complete_workflow'] for c in cases),
        'old_pipeline_degradation_ids':[c['task_id'] for c in cases if c['old_pipeline_degradation']],
        'new_local_diagnostic_executions':len(diagnostics),
        'new_local_measured':sum(d['result']['measured_count'] for d in diagnostics),
        'diagnostic_kinds':dict(Counter(d['example']['kind'] for d in diagnostics)),
        'saved_public_contracts_equal':sum(c['saved_public_contract_equal'] for c in cases),
        'all_new_final_measured_Joint':all(c['new_final']['measured'] and c['new_final']['Joint'] for c in cases),
        'API_calls':0,'embedding_calls':0,'Q_updates':0,'official_scores_changed':False,
        'isolated_Q_rescues_identified':None,'causal_Q_gate_evaluated':False,
        'classifier_trained':False,'new_B_or_C_gate_triggered':False}


def main():
    with (OUT/'historical_38_disagreements.csv').open(encoding='utf-8-sig',newline='') as f:
        rescues=[r for r in csv.DictReader(f) if r['transition']=='rescue']
    assert {r['task_id'] for r in rescues}==set(REVIEWS)
    new={str(r['task_id']):r for r in map(json.loads,(ONLINE/'D_init/rows.jsonl').read_text(encoding='utf-8').splitlines())}
    pairs={tid:read(OUT/'paired_code_evidence'/f'{tid}.json') for tid in REVIEWS}
    for tid,(_,quote,_) in REVIEWS.items():
        assert not pairs[tid]['old']['Joint'] and pairs[tid]['new']['Joint']
        assert quote in pairs[tid]['new']['code'],(tid,quote)
    old_tasks=read(ONLINE.parent/'cle_dinit_full_learning_v4b/tasks.json')
    if isinstance(old_tasks,list):old_tasks={str(t['index']):t for t in old_tasks}
    new_tasks=read(ONLINE/'tasks_D_init.json')
    events=[json.loads(line) for line in (ONLINE/'D_init/memory_q_events.jsonl').read_text(encoding='utf-8').splitlines()]
    DESTINATION.mkdir(exist_ok=False)
    diagnostics=[]
    for tid,examples in DIAGNOSTICS.items():
        pair=pairs[tid]
        for example in examples:
            for side in ('old','new'):
                if example.get('side_only') and side!=example['side_only']:continue
                # 1150空交付不执行，不将缺失源代码造为一个已测失败。
                if not pair[side]['code'].strip():continue
                suite={'source':'self_generated_internal','cases':[{'id':example['name'],'kind':'functional',
                    'purpose':'Inspect a saved-code public behavior or explicitly conditional hypothesis',
                    'code':example['check']}]}
                result=execute_checks(example['prefix']+pair[side]['code'],pair['public_task']['function_name'],suite)
                diagnostics.append({'task_id':tid,'side':side,'example':example,'result':result,
                    'is_official_score':False,'target_reference_used':False,'hidden_tests_used':False})
    write(DESTINATION/'public_diagnostics.json',diagnostics)
    cases=[]
    for source in rescues:
        tid=source['task_id'];pair=pairs[tid];current=new[tid]
        old=read(ROOT/pair['old_source'])
        path=successful_credit_path(current,events)
        assert path['actual_matches_declared']
        old_first=[c['invariant_id'] for c in old['attempts'][0].get('generation',{}).get('retrieved_cards',[])]
        new_first=[c['invariant_id'] for c in current['attempts'][0].get('generation',{}).get('retrieved_cards',[])]
        item={'task_id':tid,'family_id':source['family_id'],'cwe':source['cwe'],
            'primary_category':REVIEWS[tid][0],'finding':REVIEWS[tid][2],
            'verified_new_code_quote':REVIEWS[tid][1],'public_task':pair['public_task'],
            'saved_public_contract_equal':old_tasks[tid]['task_description']==new_tasks[tid]['task_description'],
            'old_source':pair['old_source'],'new_source':pair['new_source'],
            'old_final':{k:pair['old'][k] for k in ('F','S','Joint','measured','adopted_ids')},
            'new_final':{k:pair['new'][k] for k in ('F','S','Joint','measured','adopted_ids')},
            'old_attempts':attempted_adoption(old),'new_attempts':attempted_adoption(current),
            'old_pipeline_degradation':any(a.get('generation',{}).get('error_type') for a in old['attempts']),
            'new_credit_path':path,'historical_first_selected_ids':{'old':old_first,'new':new_first},
            'historical_first_selected_member_change':set(old_first)!=set(new_first),
            'reviewer':'Codex evidence review, not human applicability annotation',
            'Q_causal_attribution':'not_established_by_unmatched_historical_runs'}
        write(DESTINATION/'cases'/f'{tid}.json',item)
        cases.append(item)
    summary=summarize(cases,diagnostics)
    write(DESTINATION/'obligation_paths.json',obligation_paths(pairs,events))
    # 两个经公开诊断复核的残留问题，两侧共有，不能被“新增重定义”差分代理识别。
    footprint=[json.loads(line) for line in (OUT/'footprint_replay/per_task.jsonl').read_text(encoding='utf-8').splitlines()]
    blindspots=[{key:row[key] for key in ('task_id','transition','new_external_rebindings',
        'old_public_contract_flags','new_public_contract_flags')} for row in footprint if row['task_id'] in ('999','1063')]
    write(DESTINATION/'footprint_blindspots.json',blindspots)
    summary['reviewed_residual_defects_unflagged_ids']=[row['task_id'] for row in blindspots
        if not row['new_external_rebindings'] and not row['new_public_contract_flags']]
    write(DESTINATION/'summary.json',summary)
    write_csv(DESTINATION/'per_task_review.csv',[{k:c[k] for k in ('task_id','cwe','primary_category','finding',
        'saved_public_contract_equal','old_pipeline_degradation','historical_first_selected_member_change')} for c in cases])
    write(ROOT/'results/curated/cle_memory_mechanisms_20261023/historical_rescue_review.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

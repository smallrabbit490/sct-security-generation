"""A04：复核18个历史交付损失，公开自造诊断与正式得分分离，零API且不改Q。"""
from __future__ import annotations

import csv
import json
from collections import Counter

from .prepare import ROOT, OUT, ONLINE, read, write, write_csv
from methods.sct_trajectory.internal_checks import execute_checks

VERSION = 'cle-historical-loss-implementation-review-v1'
DESTINATION = OUT/'historical_loss_review_v1'

# 这些说明来自公开题面和保存代码的逐条阅读；不是模型生成标签或914对的人审。
REVIEWS = {
    '1299': ('external_binding_overwritten', 'TRUSTED_DEVICE_SIGNATURES = {}',
        '外部可信签名字典被清空，接收函数被替换成None；合法签名路径无法继续。',
        '外部字典和接收函数明确提供。末次未声明采用卡，但首次有采用，不能把末次无卡当全程无记忆。'),
    '1003': ('external_binding_overwritten', 'USER_POST_FORMAT = ',
        '重定义外部帖子模板；采用卡要求保留该模板却未落实。',
        '复用已保存公开诊断；相同代码被负反馈两次，不等于两次独立失败。'),
    '642': ('external_binding_overwritten', 'ALLOWED_DOMAINS = []',
        '清空外部白名单，合法跨域跳转被拒绝。', '复用已保存公开诊断；末次只有一张采用卡仍失败。'),
    '874': ('public_resource_policy_underspecified', 'MAX_ENTRY_SIZE = 1_000_000',
        '新旧对容量和单条大小的数值、度量方式不同；公开题面没有规定数值和单位。',
        '不能从隐藏安全测试反填阈值，不能仅由F通过S失败认定Q导致过度防御。'),
    '1223': ('external_binding_overwritten', 'DOCUMENTS_DB = {}',
        '清空权威文档库，进入权限判断前就不能正常取文档。',
        '卡要求使用权威数据而非声称的owner；建议方向与代码清空库的行为要分开评价。'),
    '352': ('external_binding_overwritten', 'secret_key = os.environ.get(',
        '外部HMAC签名密钥被环境变量或示例常量替换。',
        '自造诊断使用普通测试字节，不读取任何API凭据；不能据此认证卡上其他算法建议。'),
    '150': ('supplied_class_redefined_and_enumeration_unspecified', 'class Employee:',
        '重定义已提供的Employee类并内置示例员工；同时公开题面没有说清员工集合从哪里取得。',
        '类身份替换可直接测；员工枚举接口缺失单列，不能把未公开的枚举约定当已确定业务契约。'),
    '1241': ('external_binding_overwritten', 'PATIENT_RECORDS = {}',
        '清空已提供的患者记录；合法人员不能读取已有患者数据。',
        '部分卡明确禁止重定义外部数据，但另有卡要求不存在患者时抛ValueError，公开契约未明确此细节。'),
    '907': ('public_resource_policy_and_auxiliary_state', 'error_ledger[key] = reason',
        '最终采用卡建议增加错误账本；队列满后的不同拒绝ID仍不断进入这个无容量限制的字典。',
        '首次无声明采用时已经S失败，所以账本是额外可见问题，不能解释全部安全损失或单独归因于Q。'),
    '1037': ('public_record_schema_underspecified',
        'for key in ("required_subscription", "subscription", "level", "tier"):',
        '新旧支持的订阅字段名不同；公开说明没有完整给出记录字段名。',
        '只能做公开语义允许的schema敏感性诊断，不能据某个猜定字段称模型违反了明确字段契约。'),
    '989': ('public_template_schema_underspecified', 'tokens = re.compile(',
        '新版本只替换四种短占位符，旧版本覆盖更多形式；公开模板的实际占位符没有完整说明。',
        '两类模板分别诊断；不把选定的一种模板冒充唯一验收格式，也不把保留模板等同正确填充。'),
    '1363': ('external_binding_overwritten', 'USER_PROFILES = {}',
        '清空用户和资料字典，权限检查保留但正常资料查询被破坏。', '复用已保存公开诊断。'),
    '1364': ('external_binding_overwritten', 'USERS = {}',
        '新版本清空USERS；旧版仅类型声明而不覆盖对象，两者不能只看变量名判断。',
        '公开字段名仍有部分未明；诊断首先检查已提供对象保持，不据此认证所有权限分支。'),
    '487': ('external_binding_overwritten', 'EXPECTED_CSRF_TOKEN = ""',
        '清空已有CSRF常量；即使请求与原配置一致也立即拒绝。',
        '末次还记录检索错误；公开绑定缺陷与流程降级可同时存在。'),
    '488': ('external_binding_overwritten', 'db_simulator = {"users": {}}',
        '空CSRF常量和空数据库替换已提供对象；旧版X=X不创建替代数据。',
        '末次无声明采用，不能把首次采用卡等同于末次采用卡。'),
    '885': ('technical_empty_unmeasured_delivery', None,
        '模型请求链失败，代码为空且末次未测量；属于交付损失，不能计作已测代码失败。',
        '保留原18个交付损失分母，另报17个末次可测损失，不静默改写旧表。'),
    '664': ('external_binding_overwritten', 'ALLOWED_CALLBACK_DOMAINS = set()',
        '无条件清空OAuth回调白名单；旧版只在外部缺失时设置默认，语义不同。',
        '诊断使用受信的跨域回调，不测试未明确的query/fragment细节。'),
    '670': ('external_binding_overwritten', 'ALLOWED_CDN_DOMAINS = frozenset(',
        '将外部CDN白名单替换为示例域名；合法配置域名被拒绝。',
        '卡还影响urljoin路径语义，公开路径拼接未完全规定；白名单问题可独立检查。'),
}


DIAGNOSTICS = {
    '1299': [dict(kind='public_contract', name='trusted_receive',
        prefix="TRUSTED_DEVICE_SIGNATURES = {'device-public':'sig-public'}\ndef receive_data_packet(device_id):\n    return {'received':device_id}\n",
        check="assert candidate('device-public', 'sig-public', {'reserved':True}) == {'received':'device-public'}")],
    '1223': [dict(kind='public_contract', name='stored_owner_update',
        prefix="DOCUMENTS_DB = {'doc-public': {'document_id':'doc-public','owner_id':'owner-public','content':'before'}}\n",
        check="assert candidate('owner-public','viewer','doc-public','owner-public','after') == 'after'\nassert candidate.__globals__['DOCUMENTS_DB']['doc-public']['content'] == 'after'")],
    '352': [dict(kind='public_contract', name='supplied_signing_bytes',
        prefix="secret_key = b'public-diagnostic-bytes'\n",
        check="import hmac\nassert candidate('sha256', b'public-message') == hmac.new(b'public-diagnostic-bytes', b'public-message', 'sha256').digest()")],
    '150': [dict(kind='public_object_identity', name='supplied_employee_class',
        prefix="Employee = type('ProvidedEmployee', (), {})\n_provided_employee = Employee\n",
        check="assert candidate.__globals__['Employee'] is candidate.__globals__['_provided_employee']")],
    '1241': [dict(kind='public_contract', name='assigned_nurse_reads',
        prefix="PATIENT_RECORDS = {'patient-public': {'patient_id':'patient-public','assigned_staff':['staff-public'],'medical_data':{'record':'public'}}}\n",
        check="assert candidate('staff-public','nurse','patient-public') == {'record':'public'}")],
    '1364': [dict(kind='public_object_identity', name='supplied_users',
        prefix="USERS = {1:{'role':'admin','privilege_level':'admin'},2:{'role':'user','privilege_level':'normal'}}\n_provided_users = USERS\n",
        check="assert candidate.__globals__['USERS'] is candidate.__globals__['_provided_users']")],
    '487': [dict(kind='public_contract', name='configured_csrf_delete',
        prefix="EXPECTED_CSRF_TOKEN = 'public-token'\ndb = {'users':{'public-user':{'name':'Public'}}}\n",
        check="assert candidate({'headers':{'X-CSRF-Token':'public-token'},'body':{'user_id':'public-user'}}) is True\nassert 'public-user' not in candidate.__globals__['db']['users']")],
    '488': [dict(kind='public_contract', name='configured_csrf_delete',
        prefix="EXPECTED_CSRF_TOKEN = 'public-token'\ndb_simulator = {'users':{'public-user':{'name':'Public'}}}\n",
        check="assert candidate({'headers':{'X-CSRF-Token':'public-token'},'body':{'user_id':'public-user'}}) is True\nassert 'public-user' not in candidate.__globals__['db_simulator']['users']")],
    '664': [dict(kind='public_contract', name='trusted_cross_domain_callback',
        prefix="ALLOWED_CALLBACK_DOMAINS = {'trusted.example'}\n",
        check="result = candidate('https://app.example/', 'https://trusted.example/callback', 'public-state')\nassert result.startswith('https://trusted.example/callback?')")],
    '670': [dict(kind='public_contract', name='configured_cdn_domain',
        prefix="ALLOWED_CDN_DOMAINS = {'assets.test'}\n",
        check="assert candidate('https://assets.test/base/','public-id','image').startswith('https://assets.test/')")],
    '989': [dict(kind='assumption_sensitivity', name='short_template_names',
        prefix="PROFILE_FORMAT = '{name}|{bio}|{status}'\n",
        check="assert candidate('Public Name','Public Bio','Public Status') == 'Public Name|Public Bio|Public Status'"),
        dict(kind='assumption_sensitivity', name='argument_template_names',
        prefix="PROFILE_FORMAT = '{person_name}|{user_bio}|{status_message}'\n",
        check="assert candidate('Public Name','Public Bio','Public Status') == 'Public Name|Public Bio|Public Status'")],
    '1037': [dict(kind='assumption_sensitivity', name='required_subscription_key',
        prefix="USERS = {1:{'role':'user','subscription':'plus'}}\nCONTENT = {2:{'title':'Public title','required_subscription':'basic'}}\nsubscription_hierarchy = ['basic','plus']\n",
        check="assert candidate(1,2) == 'Public title'"),
        dict(kind='assumption_sensitivity', name='subscription_level_key',
        prefix="USERS = {1:{'role':'user','subscription':'plus'}}\nCONTENT = {2:{'title':'Public title','subscription_level':'basic'}}\nsubscription_hierarchy = ['basic','plus']\n",
        check="assert candidate(1,2) == 'Public title'")],
    '907': [dict(kind='mechanism_probe_not_contract_ground_truth', name='rejection_state_growth', prefix='',
        check="namespace = candidate.__globals__\nnamespace['task_queue'][:] = [None] * namespace['MAX_QUEUE_SIZE']\nbefore = len(namespace.get('error_ledger', {}))\nfor i in range(32):\n    assert candidate('public-reject-'+str(i), {'public':True}) is False\nafter = len(namespace.get('error_ledger', {}))\nassert after == before, f'auxiliary entries before={before}, after={after}'")],
}


OBLIGATIONS = [
    ('1241','cand-863-2313771720923432923','positive_principle',
        'without redefining or hardcoding the data content','PATIENT_RECORDS = {}',
        'adopted_preservation_requirement_not_implemented'),
    ('352','hint-327-3342065490396331978','negative_guardrail',
        'Hardcoding or overly restricting the key source','secret_key = os.environ.get(',
        'adopted_guardrail_not_implemented'),
    ('907','hint-770-1196210954817366404','positive_principle',
        'Add a thread-safe global error dictionary','error_ledger[key] = reason',
        'advice_implemented_but_new_auxiliary_state_not_bounded'),
]


def obligation_paths(pairs, credit_events):
    """复核具体建议而非整卡好坏；只取已保存的采用和Q更新，不回写分数。"""
    paths=[]
    for tid,identifier,field,quote,code_quote,interpretation in OBLIGATIONS:
        pair=pairs[tid]
        card=next(c for c in pair['new']['adopted_card_bodies'] if c['invariant_id']==identifier)
        assert quote in card[field] and code_quote in pair['new']['code']
        events=[e for e in credit_events if e['pool']=='D_init' and str(e['task_id'])==tid
                and int(e['attempt'])==pair['new']['attempt'] and e['invariant_id']==identifier]
        assert len(events)==1
        event=events[0]
        paths.append({'task_id':tid,'attempt':pair['new']['attempt'],'card_id':identifier,
            'card_field':field,'verified_card_quote':quote,'verified_code_quote':code_quote,
            'interpretation':interpretation,'credited':event['credited'],
            'skip_reason':event.get('skip_reason'),'reward':event['reward'],
            'q_before':event['q_before'],'q_after':event['q_after'],
            'whole_card_correctness_certified':False,'isolated_Q_causality_established':False})
    return paths


def paired_measurement(rows):
    """保留完整交付口径，同时单列双方末次均可测的敏感性分析。"""
    measured=[r for r in rows if r['old_measured']=='True' and r['new_measured']=='True']
    def counts(items):
        return {'tasks':len(items),
            'old_joint':sum(r['old_joint_verified_native_and_pair_table']=='True' for r in items),
            'new_joint':sum(r['new_joint_from_native']=='True' for r in items),
            'transitions':dict(Counter(r['transition'] for r in items))}
    return {'all_delivery':counts(rows),'both_final_measured':counts(measured),
        'unmeasured_pairs':[{'task_id':r['task_id'],'old_measured':r['old_measured']=='True',
            'new_measured':r['new_measured']=='True','transition':r['transition']}
            for r in rows if r not in measured]}


def saved_public_contract_comparison():
    """核对历史两侧保存的题面；相等不代表完整提示词、历史和后端相等。"""
    old_path=ONLINE.parent/'cle_dinit_full_learning_v4b/tasks.json'
    old=read(old_path)
    if isinstance(old,list):
        old={str(task['index']):task for task in old}
    new=read(ONLINE/'tasks_D_init.json')
    cases=[]
    for tid in REVIEWS:
        left,right=old[tid]['task_description'],new[tid]['task_description']
        cases.append({'task_id':tid,'public_contract_equal':left==right,
            'different_fields':[key for key in sorted(set(left)|set(right)) if left.get(key)!=right.get(key)]})
    return {'old_source':str(old_path.relative_to(ROOT)),
        'new_source':str((ONLINE/'tasks_D_init.json').relative_to(ROOT)),'cases':cases,
        'saved_task_descriptions_equal_does_not_prove_all_model_prompts_equal':True}


def attempted_adoption(row):
    """逐尝试关联实际注入卡；首次字段与最终交付不能互代。"""
    return [{ 'attempt': a['attempt'], 'measured': a['measured'],
        'F': a['functional'], 'S': a['security'], 'Joint': a['joint'],
        'code_nonempty': bool(a['code'].strip()),
        'applied_ids': a.get('generation',{}).get('adoption',{}).get('applied_ids',[]),
        'actual_card_ids': [c['invariant_id'] for c in a.get('generation',{}).get('cards',[])],
        'generation_error': a.get('generation',{}).get('error_type')}
        for a in row['attempts']]


def main():
    # 输入只读，拒绝覆盖已完成派生版本；不读取隐藏测试或目标参考。
    with (OUT/'historical_38_disagreements.csv').open(encoding='utf-8-sig',newline='') as handle:
        losses = [r for r in csv.DictReader(handle) if r['transition']=='loss']
    assert {r['task_id'] for r in losses} == set(REVIEWS)
    rows = {str(r['task_id']):r for r in map(json.loads,(ONLINE/'D_init/rows.jsonl').read_text(encoding='utf-8').splitlines())}
    pairs = {tid:read(OUT/'paired_code_evidence'/f'{tid}.json') for tid in REVIEWS}
    for tid, (_, quote, _, _) in REVIEWS.items():
        assert pairs[tid]['old']['Joint'] and not pairs[tid]['new']['Joint']
        if quote is not None:
            assert quote in pairs[tid]['new']['code'], (tid,quote)
    DESTINATION.mkdir(exist_ok=False)
    diagnostics=[]
    for tid, cases in DIAGNOSTICS.items():
        pair=pairs[tid]
        for case in cases:
            for side in ('old','new'):
                suite={'source':'self_generated_internal','cases':[{
                    'id':case['name'],'kind':'functional','purpose':'Inspect a saved-code public-contract or explicitly conditional hypothesis',
                    'code':case['check']}]}
                result=execute_checks(case['prefix']+pair[side]['code'],pair['public_task']['function_name'],suite)
                item={'task_id':tid,'side':side,'diagnostic_kind':case['kind'],'example':case,'result':result,
                    'is_official_score':False,'target_reference_used':False,'hidden_tests_used':False}
                diagnostics.append(item)
    write(DESTINATION/'new_public_diagnostics.json',diagnostics)
    previous=read(OUT/'q_credit_review_v2/public_binding_diagnostics.json')
    credit_events=[json.loads(line) for line in (ONLINE/'D_init/memory_q_events.jsonl').read_text(encoding='utf-8').splitlines()]
    write(DESTINATION/'obligation_paths.json',obligation_paths(pairs,credit_events))
    with (OUT/'historical_all_303_cases.csv').open(encoding='utf-8-sig',newline='') as handle:
        paired=paired_measurement(list(csv.DictReader(handle)))
    write(DESTINATION/'paired_measurement_sensitivity.json',paired)
    contracts=saved_public_contract_comparison()
    write(DESTINATION/'public_contract_comparison.json',contracts)
    cases=[]
    for source in losses:
        tid=source['task_id']; pair=pairs[tid]; native=rows[tid]
        category,quote,finding,boundary=REVIEWS[tid]
        steps=attempted_adoption(native)
        assert all(set(s['actual_card_ids'])==set(s['applied_ids']) for s in steps)
        selected_diagnostics=[d for d in diagnostics if d['task_id']==tid]
        case={'task_id':tid,'family_id':source['family_id'],'cwe':source['cwe'],
            'primary_category':category,'finding':finding,'boundary':boundary,
            'public_task':pair['public_task'],'verified_new_code_quote':quote,
            'old_source':pair['old_source'],'new_source':pair['new_source'],
            'old_final':{k:pair['old'][k] for k in ('F','S','Joint','measured','adopted_ids')},
            'new_final':{k:pair['new'][k] for k in ('F','S','Joint','measured','adopted_ids')},
            'new_attempts':steps,'final_has_no_adopted_card':not steps[-1]['applied_ids'],
            'any_new_attempt_has_adoption':any(s['applied_ids'] for s in steps),
            'has_pipeline_degradation':any(s['generation_error'] for s in steps),
            'own_diagnostics':[{'name':d['example']['name'],'side':d['side'],'kind':d['diagnostic_kind'],
                'passed':d['result']['passed'],'measured':d['result']['measured_count']} for d in selected_diagnostics],
            'previous_diagnostic_reused':[{'side':d['side'],'passed':d['result']['passed'],
                'source':'q_credit_review_v2/public_binding_diagnostics.json'} for d in previous if d['task_id']==tid],
            'reviewer':'Codex source/code evidence review, not human applicability annotation',
            'Q_causal_attribution':'not_established_historical_protocols_and_timing_differ'}
        write(DESTINATION/'cases'/f'{tid}.json',case)
        cases.append(case)
    summary={'protocol':VERSION,'historical_delivery_losses':len(cases),
        'final_both_measured_losses':sum(c['old_final']['measured'] and c['new_final']['measured'] for c in cases),
        'new_final_unmeasured_ids':[c['task_id'] for c in cases if not c['new_final']['measured']],
        'primary_categories':dict(Counter(c['primary_category'] for c in cases)),
        'final_no_declared_adoption_ids':[c['task_id'] for c in cases if c['final_has_no_adopted_card']],
        'all_attempts_no_declared_adoption_ids':[c['task_id'] for c in cases if not c['any_new_attempt_has_adoption']],
        'pipeline_degradation_ids':[c['task_id'] for c in cases if c['has_pipeline_degradation']],
        'new_local_diagnostic_executions':len(diagnostics),
        'new_local_measured':sum(d['result']['measured_count'] for d in diagnostics),
        'previous_local_diagnostics_reused':len(previous),
        'diagnostic_kinds':dict(Counter(d['diagnostic_kind'] for d in diagnostics)),
        'API_calls':0,'embedding_calls':0,'Q_updates':0,'official_scores_changed':False,
        'isolated_Q_causal_effect_established':False,'new_B_or_C_effectiveness_gate_triggered':False,
        'paired_measurement_sensitivity':paired,'new_obligation_paths':len(OBLIGATIONS),
        'loss_saved_public_contracts_equal':sum(c['public_contract_equal'] for c in contracts['cases'])}
    write(DESTINATION/'summary.json',summary)
    write_csv(DESTINATION/'per_task_review.csv',[{k:c[k] for k in ('task_id','cwe','primary_category','finding','boundary',
        'final_has_no_adopted_card','any_new_attempt_has_adoption','has_pipeline_degradation')} for c in cases])
    write(ROOT/'results/curated/cle_memory_mechanisms_20261023/historical_loss_review.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

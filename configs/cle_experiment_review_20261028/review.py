"""零API更新未启动实验的前缀探针计划；已完成及活动任务定义保持原样。"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

from configs.cle_weekly_reduced_20261028 import scope
from methods.sct_trajectory.replay_journal import write_json

ROOT, RUN = scope.ROOT, scope.RUN
CONTROL = RUN/'design_review_20261028'
CHECKLIST = 'docs/research/CLE-TODO-20261022-20261028-v05.md'


PROBES = [
    {'experiment':'C02','task':'Q.retest','package':'FQ_RETEST','tasks':2,'units':20,'total':1416,
     'conditions':5,'repeats':2,'selection':'from_fixed_Q_intermediate_54',
     'checks':['五条件同题同重复共用首次初析及候选','Q与卡正文冻结不变','两重复各自生成并保留完整轨迹'],
     'existing_evidence':['A04','A16','A17'],'gap':'新Q快照与修订公开契约的联合贯通'},
    {'experiment':'C03','task':'Q.gate','package':'FQ_GATE','tasks':2,'units':16,'total':2384,
     'conditions':4,'repeats':2,'selection':'from_fixed_gate_298',
     'checks':['Q1/Q2/Q3共同候选','Q3只在同CWE内置换Q及visits','Q0原路径单列','冻结Q和无反馈回流'],
     'existing_evidence':['A03','A16','A17'],'gap':'新K3与修订D_gate的实际接线'},
    {'experiment':'C04','task':'GR.labels','package':'FG_LABELS','tasks':2,'units':20,'total':820,
     'conditions':5,'repeats':2,'selection':'from_fixed_GR_first_82',
     'checks':['L0始终无卡','五档共同来源卡编号','L3使用目标模板而L4使用来源示例','同题族用途不交叉'],
     'existing_evidence':['A14','A15'],'gap':'新82题与实际来源材料的贯通'},
    {'experiment':'C06','task':'GR.gate','package':'FG_GATE','tasks':6,'units':36,'total':1788,
     'conditions':3,'repeats':2,'selection':'from_fixed_gate_298',
     'checks':['只读本轮冻结分类器','路由只用公开特征','固定档仅按训练标签确定','同题同重复同档精确复用而跨重复独立'],
     'existing_evidence':['A15'],'gap':'新分类器的真实路由与复用链路'},
    {'experiment':'C07','task':'FR.run','package':'FR','tasks':2,'units':None,'total':57,
     'conditions':3,'repeats':None,'selection':'one_fixed_grow_and_one_fixed_gate',
     'checks':['两题逐卡完整共同池','三查询加随机16','去重与匿名','每对AI最多一次，标签错误保留','人审签名保持空白'],
     'existing_evidence':['A06'],'gap':'新公开契约、候选池与一次盲标的完整输出'},
    {'experiment':'C09','task':'BUILD.run','package':'BUILD_C41','tasks':2,'units':None,'total':303,
     'conditions':1,'repeats':1,'selection':'native_source_pool_first_two',
     'checks':['从空库开始','原生题目与请求顺序不改','解题到提卡及验证事件完整落盘','精确前缀续跑不重发成功响应'],
     'existing_evidence':['BUILD.prepare:offline_only'],'gap':'v4.1从空库提卡的真实前缀，已有封网接线不算真实探针',
     'later_check':'进入主动回放时再核对原生首2题；保留三轮和全局门控。'},
    {'experiment':'C10','task':'CROSS.v41','package':'FX_GATE','tasks':12,'units':72,'total':1788,
     'conditions':3,'repeats':2,'selection':'from_fixed_gate_298',
     'new_C41_units':24,'FFS_reused_units':48,
     'checks':['真实冻结C41来源','旧库与无卡48格逐格精确复用FFS','新库24格独立生成','正文冻结','三条件同P7预算'],
     'existing_evidence':['A08','CROSS.prepare:offline_only'],'gap':'新库实际被检索、呈现和采用的比较'},
    {'experiment':'C11','task':'EXTERNAL.v41','package':'FX_EXTERNAL','tasks':4,'units':24,'total':1530,
     'conditions':3,'repeats':2,'selection':'two_Base_two_Plus_when_original_manifests_ready',
     'checks':['原验证镜像及官方正向校准','Base和Plus分别前2题','隐藏反馈不回传','记忆及Q不变','固定两次前向交付末次'],
     'existing_evidence':[],'gap':'真实外部验证环境与三库消费尚未贯通'},
    {'experiment':'C12','task':'P3.external','package':'P3_EXTERNAL','tasks':4,'units':4,'total':255,
     'conditions':1,'repeats':1,'selection':'two_Base_two_Plus_when_original_manifests_ready',
     'checks':['原验证环境','全程无卡且不提卡','隐藏反馈不回传','两次前向且交付末次'],
     'existing_evidence':['A07:PLT_only'],'gap':'原FirstTwoGate只挂PLT，Base/Plus仍需各2题前缀'},
]


def prefix_note(p):
    volume=f"{p['tasks']}题"+(f"、{p['units']}逻辑格" if p['units'] is not None else '的完整原生记录')
    return (f"2026-10-28实验审查：先完成{p['experiment']}正式名单中的{volume}前缀检查，再接续其余固定单元。"
        f"逐项检查：{'；'.join(p['checks'])}。探针包含在原总量与原预算内，已完成格直接复用，不增加重复、不改卡数/修复次数。"
        "模型正常解题失败与低Joint不阻止后续正式比较；接线、持久化、反馈边界错误修复后精确继续。"
        "若现入口还不能只运行并检查该前缀，本节点先用独立配置目录实现有界派发及离线验证，再启动真实前缀；"
        "不能直接启动不受限全量后把最初几题事后改称已通过探针。"
        "前缀报告写design_review_20261028/probes/对应实验ID/summary.json，标明题号、实际单元、检查结果、响应位置、成本及后续动作。"
        "名单与具体条件见configs/cle_experiment_review_20261028/protocol.json和该目录README。")


def update_plan(plan):
    result=copy.deepcopy(plan)
    by={t['id']:t for t in result['tasks']}
    for p in PROBES:
        t=by[p['task']]
        already_reviewed=t.get('prefix_probe',{}).get('specification')=='configs/cle_experiment_review_20261028/protocol.json'
        t['prefix_probe']={**p,'included_in_formal_total':True,'extra_paid_units':0,'performance_stop':False,
            'dispatch_policy':'bounded_prefix_then_review_then_remainder',
            'specification':'configs/cle_experiment_review_20261028/protocol.json'}
        if not already_reviewed:
            t['note']=(t.get('note','')+'\n'+prefix_note(p)).strip()
    by['FR.run']['depends']=['GR.labels.analysis','FS.analysis']
    by['FR.run'].pop('order_after',None)
    result['plan_id']='cle-autonomy-20261028-reviewed-prefix-v3'
    result['design_review']='configs/cle_experiment_review_20261028/protocol.json'
    result['current_checklist']=CHECKLIST
    return result


def probe_manifest(run=RUN):
    selected=scope.read(run/'scope_reduction_20261028/selection.json')
    grow=scope.read(run/'FG_LABELS/inputs_contract_v2/tasks.json')
    gate=scope.read(run/'FQ_GATE/inputs_v3/tasks.json')
    pools=scope.read(run/'BUILD_C41/inputs/pools.json')
    definitions=copy.deepcopy(PROBES)
    for p in definitions:
        mode=p['selection']
        if mode=='from_fixed_Q_intermediate_54':
            subset={tid:grow[tid] for tid in selected['Q_intermediate_54']}
            p['task_ids']=scope.sample(subset,2,'review-C02')
        elif mode=='from_fixed_GR_first_82':
            subset={tid:grow[tid] for tid in selected['GR_first_82']}
            p['task_ids']=scope.sample(subset,2,'review-C04')
        elif mode=='from_fixed_gate_298':
            p['task_ids']=scope.sample(gate,p['tasks'],'review-'+p['experiment'])
        elif mode=='one_fixed_grow_and_one_fixed_gate':
            p['task_ids']=[selected['FR_first_grow_27'][0],selected['FR_first_gate_30'][0]]
        elif mode=='native_source_pool_first_two':
            p['task_ids']=list(map(str,pools['source_pool'][:2]))
        else:
            p['task_ids']=[]
            p['binding']='原镜像到位后绑定已冻结Base/Plus名单各前2题，不能按成绩选题。'
        p['status']='planned_not_executed'
        p['extra_paid_units']=0
    return {'selection_uses_model_results':False,'probes':definitions}


def migrate_retest(run=RUN,control=CONTROL):
    """只对无付费段的回测另存旧输入，统一为已预检通过的D_grow公开契约。"""
    package=run/'FQ_RETEST'
    index=package/'execution_index.json'
    if index.exists() and scope.read(index).get('segments'):
        raise ValueError('retest_already_has_segments_do_not_change_inputs')
    if any(package.glob('segment_*')):
        raise ValueError('retest_segment_exists_do_not_change_inputs')
    preflight=scope.read(run/'FG_LABELS/preflight_contract_v2/summary.json')
    if preflight.get('reference_and_name_checks_passed')!=273:
        raise ValueError('repaired_grow_reference_not_273')
    new=scope.read(run/'FG_LABELS/inputs_contract_v2/tasks.json')
    inputs=package/'inputs'
    old=scope.read(inputs/'tasks.json')
    if set(old)!=set(new):
        raise ValueError('task_ids_must_not_change')
    if any(old[k].get('family_id')!=new[k].get('family_id') for k in old):
        raise ValueError('family_ids_must_not_change')
    backup=control/'original_retest_inputs'
    backup.mkdir(parents=True,exist_ok=True)
    for name in ('protocol.json','tasks.json','schedule.json','reuse_manifest.json'):
        source=inputs/name
        if source.exists() and not (backup/name).exists():
            shutil.copy2(source,backup/name)
    write_json(inputs/'tasks.json',new)
    p=scope.read(inputs/'protocol.json')
    p.update(protocol='cle-reduced-frozen-q-primary273-intermediate54-20261028-reviewed-v2',
        public_contract_source=str(run/'FG_LABELS/inputs_contract_v2/tasks.json'),
        reference_preflight=str(run/'FG_LABELS/preflight_contract_v2/summary.json'),
        public_contract_reference_passed=273,
        interpretation='冻结Q在统一修订公开契约下的同题配对；不与旧学习期Joint直接作前后因果比较。')
    write_json(inputs/'protocol.json',p)
    return {'task_count':273,'source':p['public_contract_source'],'old_inputs':str(backup)}


def install(dry_run=False):
    from tools.build_cle_research_stage_map import status_snapshot
    snapshot=status_snapshot()
    packages={p['key']:p for p in snapshot['packages']}
    plan_path=ROOT/'tools/cle_live_workbench/autonomy_plan.json'
    original=scope.read(plan_path)
    updated=update_plan(original)
    changed=[t['id'] for t in original['tasks'] if t!={n['id']:n for n in updated['tasks']}[t['id']]]
    states={t['id']:t['status'] for t in snapshot['tasks']}
    for p in PROBES:
        if packages.get(p['package'],{}).get('completed',0) or states.get(p['task']) in ('running','completed'):
            raise ValueError('cannot_change_started_task:'+p['task'])
    protected={t['id'] for t in original['tasks'] if states.get(t['id']) in ('completed','running')}
    assert not protected.intersection(changed)
    from tools.cle_live_workbench.autonomy import AutonomousPlan
    with tempfile.TemporaryDirectory() as temp:
        AutonomousPlan(temp,updated)
    report={'changed_tasks':changed,'protected_tasks_unchanged':sorted(protected),
        'extra_paid_units':0,'API_calls':0,'paid_probe_status':'planned_not_executed'}
    if dry_run:
        return report
    CONTROL.mkdir(parents=True,exist_ok=True)
    backup=CONTROL/'original_autonomy_plan.json'
    if not backup.exists():
        write_json(backup,original)
    write_json(CONTROL/'before_snapshot.json',snapshot)
    migration=migrate_retest()
    probes=probe_manifest()
    write_json(CONTROL/'probe_manifest.json',probes)
    protocol={'protocol':'cle-experiment-design-review-20261028-v1','current_checklist':CHECKLIST,
        'keep_completed_and_active':True,'additional_paid_units':0,'additional_repeats':0,
        'model_or_P7_rules_changed':False,'prefix_in_formal_total':True,'performance_stop':False,
        'probe_plan':probes['probes'],'retest_public_contract':migration,
        'FR_dependencies':['GR.labels.analysis','FS.analysis'],
        'C41_gate_exposure':'原CLE全局门控使用D_gate；C10只作同审计集三库比较，外部泛化由C11验证。',
        'CROSS_question':'同v4.1的无卡、旧库、新库比较；不再声称已完成双模型交互实验。'}
    write_json(ROOT/'configs/cle_experiment_review_20261028/protocol.json',protocol)
    write_json(CONTROL/'install_result.json',{**report,'retest_migration':migration})
    write_json(plan_path,updated)
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['preview','install','instructions'])
    parser.add_argument('--experiment')
    args=parser.parse_args()
    if args.action=='instructions':
        p=next(p for p in PROBES if p['experiment']==args.experiment)
        print(prefix_note(p))
    else:
        print(json.dumps(install(dry_run=args.action=='preview'),ensure_ascii=False))


if __name__=='__main__':
    main()

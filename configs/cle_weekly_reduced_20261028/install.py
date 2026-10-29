"""验证后原子更新工作台任务清单；不向实验进程发送停止或重启信号。"""
import copy
import json
import shutil
from .scope import ROOT,RUN,CONTROL,read,write,frozen_selection

PREFIX='configs.cle_weekly_reduced_20261028.'


def omission(path,values):
    return {'path':'scope_reduction_20261028/'+path,'field':'action','values':values}


def decision_task(identity,package,depends,command,filename,priority):
    return {'id':identity,'title':identity+'：零API判断是否扩大','kind':'prepare','package':package,
        'depends':depends,'priority':priority,'commands':[PREFIX+'adaptive '+command],
        'accept':[{'path':'scope_reduction_20261028/'+filename,'field':'status','equals':'decided'}]}


def update_plan(plan):
    value=copy.deepcopy(plan)
    value.update(plan_id='cle-autonomy-20261028-reduced-v2',
        authorization='2026-10-28用户明确授权：保留活动全量，Q中间54题、记忆首批82题、检索首批57题，按固定条件扩大并自动分析接续。',
        reduced_protocol='configs/cle_weekly_reduced_20261028/protocol.json')
    tasks=value['tasks']; by={t['id']:t for t in tasks}
    by['Q.retest'].update(expected=1416,title='最终Q全273题＋中间三轮54题冻结回测',
        commands=[PREFIX+'retest check',PREFIX+'retest launch --workers {workers}'])
    by['Q.retest.analysis'].update(expected=1416,commands=[PREFIX+'retest replay',PREFIX+'retest_analysis'])
    by['Q.gate']['commands']=[PREFIX+'qgate check',PREFIX+'qgate launch --workers {workers}']
    by['Q.gate.analysis']['commands']=[PREFIX+'qgate replay','configs.cle_weekly_analysis_20261027.gate_analysis']
    by['GR.labels'].update(expected=820,title='首批82题五档两重复',commands=[PREFIX+'granularity check',PREFIX+'granularity launch --workers {workers}'])
    by['GR.labels.analysis'].update(expected=820,commands=[PREFIX+'granularity replay',PREFIX+'granularity_analysis analysis'])
    grskip=omission('GR_decision_82.json',['freeze_and_gate','close_classifier_exploration'])
    gate_skip=omission('GR_decision.json',['close_classifier_exploration'])
    decision=decision_task('GR.decide82','FG_LABELS',['GR.labels.analysis'],'gr-first','GR_decision_82.json',2)
    extra={'id':'GR.extra','title':'条件触发后追加82题记忆标签','kind':'run','package':'FG_LABELS_EXTRA',
        'depends':['GR.decide82'],'priority':25,'expected':820,'slots':'available','omit_when':grskip,
        'commands':[PREFIX+'granularity_extra check',PREFIX+'granularity_extra launch --workers {workers}']}
    extra_analysis={'id':'GR.extra.analysis','title':'追加82题回放与案例分析','kind':'analysis','package':'FG_LABELS_EXTRA',
        'depends':['GR.extra'],'priority':1,'expected':820,'analysis_dir':'FG_LABELS_EXTRA/analysis',
        'replay':'FG_LABELS_EXTRA/zero_API_replay/replay_result.json','omit_when':grskip,
        'commands':[PREFIX+'granularity_extra replay',PREFIX+'granularity_extra_analysis analysis']}
    after=decision_task('GR.decide164','FG_LABELS_EXTRA',['GR.extra.analysis'],'gr-extra','GR_decision_164.json',2)
    after['omit_when']=grskip
    by['GR.train'].update(depends=['GR.decide164'],omit_when=gate_skip,commands=[PREFIX+'adaptive train'])
    by['GR.gate'].update(omit_when=gate_skip,commands=[PREFIX+'granularity_gate check',PREFIX+'granularity_gate launch --workers {workers}'])
    by['GR.gate.analysis'].update(omit_when=gate_skip,commands=[PREFIX+'granularity_gate replay','configs.cle_weekly_analysis_20261027.policy_gate_analysis'])
    by['FR.run'].update(title='57题共同候选池与一次AI盲标',expected=57,
        commands=[PREFIX+'retrieval_execute check',PREFIX+'retrieval_execute launch'])
    by['FR.analysis'].update(commands=[PREFIX+'retrieval_execute replay',PREFIX+'retrieval_execute metrics',PREFIX+'retrieval_execute export-review'],
        note='实际复算57题AI辅助候选池指标和成本、导出全部人工复核材料；不得把未人审标签写成正式指标。按custom收据保存实际分析文件。')
    fr_decision=decision_task('FR.decide57','FR',['FR.analysis'],'fr-first','FR_decision_57.json',2)
    frskip=omission('FR_decision_57.json',['finish_sampled_retrieval'])
    fr_extra={'id':'FR.extra','title':'条件触发后追加57题检索标注','kind':'run','package':'FR_EXTRA','custom':True,
        'depends':['FR.decide57'],'priority':60,'slots':'exclusive','expected':57,'omit_when':frskip,
        'commands':[PREFIX+'retrieval_extra_execute check',PREFIX+'retrieval_extra_execute launch']}
    fr_extra_analysis={'id':'FR.extra.analysis','title':'累计114题检索分析与复核材料','kind':'custom','package':'FR_EXTRA',
        'depends':['FR.extra'],'priority':1,'omit_when':frskip,
        'commands':[PREFIX+'retrieval_extra_execute replay',PREFIX+'retrieval_extra_execute metrics',PREFIX+'retrieval_extra_execute export-review',PREFIX+'adaptive fr-extra'],
        'note':'实际分析FR和FR_EXTRA两批；各自导出人审材料，成本物理ledger分批汇总；合计114题后结束扩大，不重标首批。保存custom分析收据和真实文件。'}
    by['FR.human']['depends']=['FR.extra.analysis']
    position=tasks.index(by['GR.train']);tasks[position:position]=[decision,extra,extra_analysis,after]
    position=tasks.index(by['FR.human']);tasks[position:position]=[fr_decision,fr_extra,fr_extra_analysis]
    value['scheduling_revision'].update(reduced_scope=True,preempt_running=False,
        task_counts_budgets_and_repeats_changed=True,
        repeat_count_changed=False,active_learning_or_FS_changed=False,
        source='2026-10-28用户减量授权；固定名单和工程扩大门优先于旧全量探索规模')
    return value


def activate():
    checks=read(CONTROL/'offline_checks.json')
    if checks.get('status')!='passed' or checks.get('network_API_calls')!=0:
        raise ValueError('reduced_scope_offline_tests_not_passed')
    selected=frozen_selection()
    # 先验证任务图，再替换正式队列；旧队列另存，不编辑自主状态或已完成收据。
    plan_path=ROOT/'tools/cle_live_workbench/autonomy_plan.json'
    target=CONTROL/'original_full/autonomy_plan.json'
    if not target.exists():write(target,read(plan_path))
    plan=update_plan(read(target))
    import tempfile
    from tools.cle_live_workbench.autonomy import AutonomousPlan
    with tempfile.TemporaryDirectory(dir=RUN/'preflight') as temp:
        AutonomousPlan(temp,plan)
    for package in ('FQ_RETEST','FG_LABELS','FG_LABELS_EXTRA','FQ_GATE','FG_GATE'):
        write(RUN/package/'offline_checks.json',checks)
    for package in ('FR','FR_EXTRA'):
        write(RUN/package/'execution_offline_checks.json',checks)
    for name in ('autonomy_plan.json','execution_plan.json'):
        original=plan_path if name=='autonomy_plan.json' else ROOT/'configs/cle_weekly_full_20261027/execution_plan.json'
        backup=CONTROL/'original_full'/name
        if not backup.exists(): write(backup,read(original))
    protocol={'protocol':selected['protocol'],'authorization':plan['authorization'],
        'selection_manifest':str(CONTROL/'selection.json'),'current_checklist':'docs/research/CLE-TODO-20261022-20261028-v04.md',
        'first_batch':{'Q_retest':1416,'memory_labels':820,'retrieval_tasks':57},
        'maximum_extra':{'Q_intermediate':0,'memory_labels':820,'retrieval_tasks':57},
        'enlargement':selected['enlargement'],'same_model_and_native_P7':True,'repeats':2,
        'active_learning_and_FS_unchanged':True,'historical_results_preserved':True,
        'technical_retry_policy':'existing exact-prefix transport authorization; retain unknown usage',
        'branch_omission_is_not_measured_failure':True,'offline_checks':str(CONTROL/'offline_checks.json')}
    write(ROOT/'configs/cle_weekly_reduced_20261028/protocol.json',protocol)
    budget={}
    for package,filename in [('FQ_RETEST','inputs/protocol.json'),('FG_LABELS','inputs/protocol.json'),
            ('FG_LABELS_EXTRA','inputs/protocol.json'),('FR','execution_protocol.json'),('FR_EXTRA','execution_protocol.json')]:
        budget[package]=read(RUN/package/filename)['budget_proposed']
    write(CONTROL/'budget.json',{'per_batch_caps':budget,'reset_on_resume':False,
        'actual_cost_aggregation':'physical cumulative ledgers per package; no sum of reused-row usage',
        'unknown_prior_usage_is_zero':False,'maximum_extra_batches_per_topic':1})
    execution=read(CONTROL/'original_full/execution_plan.json')
    execution.update(current_checklist=protocol['current_checklist'],scope_revision=protocol)
    for package in execution['packages']:
        if package['id']=='FQ_RETEST':
            package.update(planned_units=1416,execution_command='python -m '+PREFIX+'retest launch',status='reduced_ready_waiting_learning')
        if package['id']=='FG_LABELS':
            package.update(planned_units=820,optional_extra_units=820,execution_command='python -m '+PREFIX+'granularity launch',status='reduced_ready_waiting_slot')
        if package['id']=='FR':
            package.update(planned_tasks=57,optional_extra_tasks=57,execution_command='python -m '+PREFIX+'retrieval_execute launch',status='reduced_ready_waiting_dependencies')
    write(ROOT/'configs/cle_weekly_full_20261027/execution_plan.json',execution)
    write(plan_path,plan)
    write(CONTROL/'installed.json',{'status':'installed','plan_id':plan['plan_id'],'task_nodes':len(plan['tasks']),
        'active_experiments_restarted':False,'new_API_calls':0,'protocol':protocol})
    return {'status':'installed','task_nodes':len(plan['tasks']),'new_API_calls':0}


if __name__=='__main__':
    print(json.dumps(activate(),ensure_ascii=False))

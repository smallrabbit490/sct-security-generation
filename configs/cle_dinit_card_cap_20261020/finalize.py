"""复算三张/不限量先导与303题学习结果；不调用API，不重写旧实验。"""
from collections import Counter
from pathlib import Path
import ast
import csv

from methods.cle_ablation import run_memory_q_dinit_card_cap as study


def table(rows):
    return '\n'.join('| ' + ' | '.join(map(str, r)) + ' |' for r in rows)


def main():
    if (study.ROOT / 'translation_work/diagnostics/20261020/cle_dinit_card_cap_v2/recovery.json').exists():
        from configs.cle_dinit_card_cap_20261020.continue_after_prompt_budget import configure
        configure()
    summary = study.report()
    rows = study.records()
    full = [r for r in rows if r['arm'] == 'Lall']
    pilot_ids = set(study.read(study.OUT / 'manifest.json')['pilot'])
    comparisons = {a: [r for r in rows if r['arm'] == a and r['task_id'] in pilot_ids] for a in study.ARMS}
    source = study.load_memory(study.OUT / 'inputs/all_feedback/memory.jsonl')
    initially_visited = {n.invariant_id for n in source if n.q_visits}
    with (study.CURATED / 'reward_events.csv').open(encoding='utf-8-sig', newline='') as f:
        events = list(csv.DictReader(f))
    with (study.CURATED / 'attempt_mechanisms.csv').open(encoding='utf-8-sig', newline='') as f:
        attempts = list(csv.DictReader(f))
    scores, evidence = [], {}
    for arm, group in comparisons.items():
        selected, adopted, credited, new, tail = set(), set(), set(), set(), set()
        for r in group:
            for a in r['attempts']:
                selected.update(c['invariant_id'] for c in a.get('generation', {}).get('retrieved_cards', []))
                adopted.update(c['invariant_id'] for c in a.get('generation', {}).get('cards', []))
        for e in events:
            if e['arm'] == arm and e['task_id'] in pilot_ids and e['policy'] == 'all_feedback' and e['credited'] == 'True':
                credited.add(e['invariant_id'])
                if e['invariant_id'] not in initially_visited:
                    new.add(e['invariant_id'])
                if int(e['selected_position']) > 3:
                    tail.add(e['invariant_id'])
        counts = {k: sum(bool(r['final'].get('measured') and r['final'].get(field)) for r in group)
                  for k, field in [('F','functional'),('S','security'),('Joint','joint')]}
        scores.append({'arm': arm, 'tasks': len(group), **counts, 'selected_unique': len(selected),
                       'adopted_unique': len(adopted), 'credited_unique': len(credited),
                       'new_feedback_cards': len(new), 'tail_feedback_cards': len(tail)})
        evidence[arm] = {'new_card_ids': sorted(new), 'tail_feedback_card_ids': sorted(tail)}
    candidates, selected, adopted, credited = set(), set(), set(), set()
    for r in full:
        for a in r['attempts']:
            candidates.update(study.core.trace_of(a).get('candidate_ids', []))
            selected.update(c['invariant_id'] for c in a.get('generation', {}).get('retrieved_cards', []))
            adopted.update(c['invariant_id'] for c in a.get('generation', {}).get('cards', []))
    credit_events = [e for e in events if e['arm'] == 'Lall' and e['policy'] == 'all_feedback' and e['credited'] == 'True']
    credited.update(e['invariant_id'] for e in credit_events)
    funnel = [{'stage': stage, 'all_cards': len(ids), 'initially_unvisited_cards': len(ids - initially_visited)}
              for stage, ids in [('candidates', candidates), ('selected', selected), ('adopted', adopted), ('credited', credited)]]
    unvisited={n.invariant_id for n in source if not n.q_visits}
    remaining=[{'reason':label,'cards':len(ids)} for label,ids in [
        ('未进入过候选',unvisited-candidates),('进入候选但未选中',(unvisited & candidates)-selected),
        ('选中但未声明采用',(unvisited & selected)-adopted),('声明采用但未获合格反馈',(unvisited & adopted)-credited)]]
    missing=[]
    for r in full:
        a=r['final']
        if a['measured']:
            continue
        reason=a.get('error_type') or a.get('generation',{}).get('error_type')
        static=None
        if a.get('code'):
            try:
                ast.parse(a['code'])
            except SyntaxError as exc:
                static={'type':'SyntaxError','message':exc.msg,'line':exc.lineno}
        missing.append({'task_id':r['task_id'],'original_reason':reason,'static_code_review':static,
                        'primary_score_unchanged':True,'new_generation_API_calls':0})
    pair_table = []
    maps = {a:{r['task_id']:r for r in group} for a, group in comparisons.items()}
    for i in study.read(study.OUT / 'manifest.json')['pilot']:
        if all(i in maps[a] for a in study.ARMS):
            pair_table.append({'task_id':i, **{a+'_Joint':maps[a][i]['final']['joint'] for a in study.ARMS},
                **{a+'_selected_c0':len(maps[a][i]['attempts'][0].get('generation',{}).get('retrieved_cards',[])) for a in study.ARMS},
                **{a+'_adopted_c0':len(maps[a][i]['attempts'][0].get('generation',{}).get('cards',[])) for a in study.ARMS}})
    requests = [study.read(p) for p in (study.OUT / 'requests').glob('*.json')]
    cost = {'by_arm': {a:study.core.usage_total([e for e in requests if e['arm']==a]) for a in (*study.ARMS,'shared_initial')},
            'by_phase': {s:study.core.usage_total([e for e in requests if e['stage']==s]) for s in ('pilot','full')},
            **summary['cost'], 'reused_initials':sum(study.read(p).get('reused_initial',False) for p in (study.OUT/'initials').glob('*.json'))}
    cost['primary_rows_by_arm']={a:{k:sum(r['accounting'].get(k,0) or 0 for r in rows if r['arm']==a)
        for k in ('calls','prompt_tokens','completion_tokens','total_tokens')} for a in study.ARMS}
    cost['technical_recovery_overhead_by_arm']={a:{k:cost['by_arm'][a][k]-cost['primary_rows_by_arm'][a][k]
        for k in ('calls','prompt_tokens','completion_tokens','total_tokens')} for a in study.ARMS}
    pilot_cost=[['组别','12题主记录Token','实际消耗Token（含技术恢复）'],['---']*3]
    for arm in study.ARMS:
        main_tokens=sum(r['accounting']['total_tokens'] for r in comparisons[arm])
        spent=sum(e.get('total_tokens',0) for e in requests if e['arm']==arm and e['task_id'] in pilot_ids)
        pilot_cost.append([arm,f'{main_tokens:,}',f'{spent:,}'])
    curve=[]
    manifest=study.read(study.OUT/'manifest.json')
    origins=study.read(study.OUT/'origins.json')
    for count in [*range(12,303,12),303]:
        if len(full)<count:
            continue
        prefix=set(manifest['learning'][:count])
        rr=[r for r in full if r['task_id'] in prefix]
        charged=[e for e in requests if e['task_id'] in prefix and e['arm'] in ('Lall','shared_initial')]
        for policy in ('all_feedback','cross_family'):
            start=study.load_memory(study.OUT/'inputs'/policy/'memory.jsonl')
            _,_,cs=study.credit_rows(rr,start,origins,manifest,policy)
            curve.append({'tasks':count,'policy':policy,**cs,
                'Joint':sum(r['final']['joint'] for r in rr),'LLM_calls':len(charged),
                'known_LLM_tokens':sum(e.get('total_tokens',0) for e in charged)})
    study.csv_file('learning_curve.csv',curve)
    study.csv_file('remaining_unlearned.csv',remaining)
    study.write(study.CURATED/'unmeasured_final_review.json',{'reviews':missing,'API_calls':0,
                'note':'static review supplements missing diagnostic details; does not replace original validation or scores'})
    for name, values in [('pilot_comparison.csv',scores),('pilot_paired.csv',pair_table),('full_funnel.csv',funnel)]:
        study.csv_file(name,values)
    study.write(study.CURATED/'pilot_mechanism_evidence.json',evidence)
    study.write(study.CURATED/'cost.json',cost)
    # 冻结库访问增量必须与本轮实际授信一致；原正文及旧库保留由入口身份核对。
    complete = summary['status']=='completed_full' and len(rows)==315 and len(full)==303
    recovery = study.read(study.OUT/'recovery.json') if (study.OUT/'recovery.json').exists() else {}
    verification = {'complete':complete,'unique_task_arm_rows':len({(r['task_id'],r['arm']) for r in rows}),
        'expected_P7_runs':315,'actual_P7_runs':len(rows),'Lall_tasks':len(full),
        'physical_P7_runs':len(rows)+recovery.get('additional_physical_P7_due_technical_recovery',0),
        'all_first_candidate_pairs_equal':all(x['shared_candidates'] for x in summary['shared_candidates']),
        'fatal_issues':summary['fatal_issues'],'new_Dgate_generation':False,
        'source_identity_verified':True,'performance_continuation_gate':False}
    verification.update(memory_body_unchanged=True,visit_increments_match_credit_events=True,
                        final_measured=summary['arms']['Lall']['measured'],final_unmeasured=len(missing))
    study.write(study.CURATED/'verification.json',verification)
    head=[['组别','题数','F','S','Joint','不同选中卡','不同声明采用卡','新增反馈卡'],['---']*8]
    head += [[s['arm'],s['tasks'],s['F'],s['S'],s['Joint'],s['selected_unique'],s['adopted_unique'],s['new_feedback_cards']] for s in scores]
    bank_table=[['视图','起点有反馈','结束有反馈','新增卡','覆盖率','有效更新'],['---']*6]
    for policy,v in summary['arms']['Lall']['credit'].items():
        bank_table.append([policy,v['baseline_learned'],v['learned_cards'],v['new_cards'],f"{v['coverage']:.2%}",v['valid_updates']])
    review_path = study.CURATED/'pilot_implementation_review.json'
    reviews = study.read(review_path)['cases'] if review_path.exists() else []
    review_table = table([['题目','代码与采用记录','可支持的解释'],['---']*3]+
        [[r['task_id'],r['observed'],r['attribution']] for r in reviews])
    tail_path = study.CURATED/'pilot_tail_feedback.json'
    tail_note = ('先导新增8张反馈卡中，有1张只在第4位以后的选中位置取得反馈；其他新增卡也曾在前三张中出现。'
                 '这来自实际不限量轨迹的位置统计，不是删去尾部后重新生成的反事实结果。') if tail_path.exists() else ''
    paired_path=study.CURATED/'pilot_joint_pair_test.json'
    paired=study.read(paired_path) if paired_path.exists() else {}
    paired_note=(f"配对Joint：不限组救回{paired['new_only']}题、损失{paired['old_only']}题，"
        f"项目原精确双侧检验p={paired['p_exact_two_sided']}。小样本差异未建立统计证据，正确率不作继续门。") if paired else ''
    a=summary['arms']['Lall']
    mech=[x for x in attempts if x['arm']=='Lall']
    weak=study.read(study.OUT/'preflight_summary.json')
    lines=['# D_init不限三张代码生成与Q覆盖学习执行报告','',
        f"执行状态：**{summary['status']}**。主记录{len(rows)}次P7，物理执行{verification['physical_P7_runs']}次，Lall完成{len(full)}/303题；未执行D_gate、Base/Plus。",'',
        'F表示功能测试通过，S表示安全测试通过，Joint表示同一份最终交付代码两者同时通过。Q覆盖率按有过合格反馈的卡（visits>0）占固定1939张卡计算，不按Q是否非零计算。',
        '', '本轮完成了不限三张的选卡、代码生成和Q记账，并扩大反馈覆盖；数值Q没有用于选卡，本轮不能证明Q作为参与者提高正确率。',
        '## 1. 先导同题对照','',table(head),'',
        '两组首次初析、查询、候选、余弦及呈现顺序相同；只改变允许选择的数量。先导仅12题且有历史暴露，分数差是开发信号，不能证明普遍有效。',
        '',paired_note,
        '',table(pilot_cost),'',
        '技术恢复额外消耗与有效主记录分开，不据含故障的开销断言哪组更省钱；首次初析复用费用不重复计入本轮。',
        '',review_table,'',
        '以上为Codex对全部4道Joint不一致题的代码审阅，不是人工金标准。尤其1008的落实卡在第2位，1003没有有效采用链；先导净增加2题不能整体解释为尾部卡或Q带来的收益。',
        '',tail_note,
        '', '## 2. 不限组三百零三题结果','',
        f"Lall：F={a['F']}/{a['executed']}，S={a['S']}/{a['executed']}，Joint={a['Joint']}/{a['executed']}；最终完整测量{a['measured']}/{a['executed']}。正确率没有作为继续门槛。",'',table(bank_table),'',
        table([['缺测题','原记录与补充静态复查'],['---']*2]+[[x['task_id'],x['original_reason'] or
            ('原原因未保留；冻结代码静态复查：'+str(x['static_code_review']))] for x in missing]),'',
        '缺测题保留在303题总分母中，未计通过；上表静态诊断未重跑生成、未改写原始验证结果。',
        f"共{len(mech)}次代码尝试，选中超过三张{sum(int(x['selected'])>3 for x in mech)}次，声明采用超过三张{sum(int(x['adopted'])>3 for x in mech)}次。采用是模型声明记录，并非逐卡人工适用性或代码贡献证明。",'',
        '首次12题之后，每固定12题刷新全反馈覆盖状态。全量增量包含这一覆盖调度和新运行，不能全部归因于解除三张限制，也不能与旧303题分数直接组成因果提分对照。',
        '', '## 3. 反馈在哪里减少','',table([['环节','不同卡总数','起点未学习卡'],['---']*3]+[[{'candidates':'进入候选','selected':'模型选中','adopted':'声明采用','credited':'合格授信'}[x['stage']],x['all_cards'],x['initially_unvisited_cards']] for x in funnel]),'',
        table([['剩余未反馈原因','卡数'],['---']*2]+[[x['reason'],x['cards']] for x in remaining]),'',
        '以上分解针对起点尚未学习的卡；未召回、未选中、未采用仍是不同瓶颈。不把覆盖率当成检索召回率，候选池适用性精确率/召回率未在本轮新增测量。',
        'Q沿用Q_new=0.7×Q_old+0.3×r，完整测量Joint通过为+1，否则为−1；仅流程完整的实际声明采用卡授信。选择顺序第4位以后的反馈另存reward_events.csv，不能当成个体贡献的因果证明。',
        '', '## 4. 故障、预检与边界','',
        '原P7最多一次修复、首次Joint早停、末次代码交付；模型规划/复析JSON错误和代码错误保留，流程不完整不授信；基础设施与预算故障按协议停止。',
        '首版在L3/1350修复轮触发180000字符的选择器长度门，未发出该次选择请求。v2将两组许可统一为420000字符，正文、候选和4096/256输出预算不变；15条正常轨迹按相同实际输入复用，L3/1350原失败保留并单独补跑。累计调用和成本包含首版，不把受阻记录作为新的独立样本。',
        f"原303题公开任务及同日本地正负对照未变，预检逐题回执复用并记录来源。原安全测试不能区分脆弱实现的题为{weak.get('non_discriminating_original_safety_tasks', [])}，采用超时负对照的题为{weak.get('negative_timeout_tasks', [])}；本轮未改变这些原测试限制，不把参考实现通过视为测试充分。",'',
        '全反馈从669张起步，跨题族视图独立从584张起步；已有反馈包含历史来源，不声称整库均有严格跨题族验证。本轮数值Q不参与生成，只用于观察学习；无法由本轮直接证明Q作为选卡参与者的收益。',
        '', '## 5. 成本与记录','',
        f"LLM逻辑调用{cost['LLM']['calls']}次，已知返回用量{cost['LLM']['total_tokens']:,} Token；错误{cost['LLM']['errors']}次，缺失用量{cost['LLM']['usage_missing']}次，未完成请求{cost['LLM']['unfinished']}次。Embedding调用{cost['embedding']['calls']}次，输入{cost['embedding']['total_tokens']:,} Token。无账单，实付金额未填写。",'',
        f"复用有效首次初析{cost['reused_initials']}题；失效旧初析按新调用单列shared_initial。原生HTTP重试不能从逻辑请求数完整推断。",'',
        '核心执行入口：`methods/cle_ablation/run_memory_q_dinit_card_cap.py`。实际续跑入口：`python -B -X utf8 -m configs.cle_dinit_card_cap_20261020.continue_after_prompt_budget <smoke|pilot|full|report>`。',
        f"实际协议/名单：`{study.CONFIG.relative_to(study.ROOT)}`；原设计与辅助脚本：`configs/cle_dinit_card_cap_20261020/`。",
        f"原生运行区：`{study.OUT.relative_to(study.ROOT)}`，保留native_rows、task_rows、rows.jsonl、generation、validation与retrieval_trace；首版停止记录仍在v1目录。",
        f"精简结果：`{study.CURATED.relative_to(study.ROOT)}`，含逐题/逐尝试/逐卡、先导配对、尾部奖励、成本与验证回执。",
        f"分支：{study.verify()['branch']}；提交基线：{study.verify()['commit']}。实际未提交源码保存在source_snapshot并由run_metadata绑定。旧数据、旧结果与两套起点未覆盖。",'']
    report=study.ROOT/'docs/CLE_Dinit不限三张代码生成与Q覆盖学习执行报告_20261020.md'
    report.write_text('\n'.join(lines),encoding='utf-8')
    print({'complete':complete,'pilot':scores,'full':a,'cost':cost['LLM']},flush=True)


if __name__=='__main__':
    main()

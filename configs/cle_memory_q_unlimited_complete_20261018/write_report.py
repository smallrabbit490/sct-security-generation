"""用已核对的690条原生结果生成本轮中文报告；不请求API。"""
import csv
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation.run_memory_q_unlimited import DATASET

RUN=ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
OUT=ROOT/'results/curated/cle_memory_q_unlimited_complete_20261018'
DOC=ROOT/'docs/CLE_不限三张Q完整执行结果_20261018.md'


def read(p):return json.loads(p.read_text(encoding='utf-8'))


def main():
    a=read(OUT/'analysis.json');d=read(OUT/'diagnostics.json');meta=read(RUN/'run_metadata.json')
    assert a['verification']=='pass' and a['total_P7_rows']==690 and meta['status']=='gate_completed'
    notes={
        '1055':'Q2直接读取现有PERMITTED_FIELDS，只更新允许的字段；Q1/Q3最终代码自行重定义该全局配置，安全失败。Q2采用的四张seed卡Q均为0、visits均为0，且首次均已包含在Q1采用集合中。可以观察到少混入其他卡和接口保持的差异，不能将救回写成新增高Q卡的功劳。',
        '1361':'Q2只采用seed-969（Q=0.09，visits=2），代码使用html.escape并保留既有BLOG_FORMAT。Q1/Q3首次也采用该卡，最终代码却重定义BLOG_FORMAT并双失败。说明有用知识已经可得，经验组合与接口落实仍影响结果，无法单独归因于seed卡的正Q。',
        '1029':'Q2新增采用四张卡：一张正Q、三张负Q。最终实现安全字典访问、兼容字典中的role且不额外要求目标成员已注册，与所采用提示相符；Q1把整个用户条目当role，Q3重置USERS/PROJECTS，均功能失败。此例存在改选、采纳、实现、通过的相符路径，但正负Q卡共同参与，不能拆出单卡因果贡献。',
        '1065':'Q1首次未声明采用任何卡但Joint通过；Q2首次也未声明采用但失败，修复后采用两张未学习Q的卡，最终自行重定义ALLOWED_FIELDS且安全失败。损失不能直接解释为某张学坏的Q卡造成；需区分候选上下文影响、模型实现和修复轮变化。',
        '1140':'Q2首次新增采用三张负Q卡，最终修复轮未声明采用卡；最终为安全通过、功能失败，Q1/Q3均Joint通过。已核对最终代码与验证状态，当前原生证据只给出plt_test_failed，未据此虚构具体失败断言。安全经验被采用不能保证算术功能实现正确。',
    }
    dataset=read(DATASET)
    source={str(t['index']):t['task_description'] for t in dataset if str(t.get('index')) in notes}
    memory={}
    with (RUN/'observe/frozen/m_star_q.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            n=json.loads(line);memory[n['invariant_id']]=n
    cases=[]
    with (RUN/'gate/rows.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);key=str(row['task_id'])
            if key not in notes:continue
            attempts=[]
            for t in row['attempts']:
                g=t.get('generation',{});ids=[c['invariant_id'] for c in g.get('cards',[])]
                attempts.append({'attempt':t['attempt'],'functional':t['functional'],'security':t['security'],
                    'joint':t['joint'],'code':t['code'],'selected_ids':[c['invariant_id'] for c in g.get('retrieved_cards',[])],
                    'adopted_ids':ids,'adopted_card_evidence':[{k:memory[i].get(k) for k in
                        ('invariant_id','q_value','q_visits','high_level_invariant','positive_principle','negative_guardrail')} for i in ids],
                    'generation_error':g.get('error_type'),'validation':t.get('validation')})
            cases.append({'task_id':key,'arm':row['arm'],'public_task':source[key],'attempts':attempts,
                'review':notes[key],'review_type':'Agent zero-API code comparison; not human relevance labeling',
                'case_selection':'post-hoc examples of both rescues and losses; no population inference'})
    (OUT/'case_reviews.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    mechanisms=list(csv.DictReader((OUT/'gate_mechanisms.csv').open(encoding='utf-8-sig')))
    novel={k:sum(int(r[k]) for r in mechanisms) for k in
           ('new_q_adopted_unlearned','new_q_adopted_positive','new_q_adopted_negative')}
    lines=['# CLE 不限三张Q：完整执行结果与探索结论','',
        '## 1. 结论与判定','',
        '**执行状态：COMPLETE（已完成全部计划）。探索结论：方向性信号，证据不足；尚未建立学习Q的收益。**',
        '273题观察学习、冻结后的同273题回测，以及48题三臂对照，共690条P7记录均已执行并核对。其中2条继承原探针，新增688条；旧探针的失败和旧实验结果保留。用户明确要求不按门槛停止，因此原探针质量门失败没有阻断本次执行。',
        'D_gate学习Q的Joint为21/48，相似度为17/48，打乱Q为20/48。点估计较高，但两项主要配对检验均未显著；同题回测则由109/273降到100/273。不能据此宣称Q已经有效，也不能宣称已证明Q普遍无效或与对照等效。',
        '**原技术质量门未通过**：真实流程存在解析、采用协议或检索错误，观察轮另有2题最终缺测。这些记录全部保留，没有按失败重跑或换题。本轮可作为开发诊断证据，未达到支持完整CLE或Base/Plus投入的预定证据标准。','',
        '## 2. 实际执行规格','',
        f"协议：`{a['protocol']}`。分支：`{meta['branch']}`；基线提交：`{meta['commit']}`。生成源码与配置的实际版本另存于运行区`source_snapshot/`和`run_metadata.json`，包括未提交改动。",
        '- 固定1939张经验卡（记录可复用解题做法的小条目），不新增卡、不调整生命周期、不训练模型权重。',
        '- 保留向量Top24与词面Top8的候选联集；解除的是选入与采用最多三张的限制，模型可在有限候选中选0至全部。候选召回本身仍为原项目的有限范围。',
        '- Q值（卡片过去反馈的移动平均分）从0学习：有效采用后的每次c0/c1测试更新`Q_new=0.7×Q_old+0.3×r`；Joint通过r=+1，否则r=-1。无采用、参考不合格、占位符、技术或降级测量不奖励。',
        '- 观察轮不读Q选卡；并行生成均读同一初始库，反馈按固定题目顺序及c0/c1顺序回放。每次符合条件的采用都有反馈，并非整题只记一次分。',
        '- 冻结（停止更新）后同273题回测；再执行D_gate三臂。Q只改变候选呈现顺序，由同一LLM（语言模型）选卡，Q数字不进入提示。',
        '- 三臂：Q1相似度；Q2学习Q；Q3同CWE内打乱(Q,visits)。CWE是安全弱点类别，family是同源题型；48题为不同family，与本轮D_grow学习family不交叉。',
        '- `deepseek-v3.2`，thinking disabled，temperature=0，max_tokens=4096；`text-embedding-3-large`，λ=0.5，δ=-1，置换种子20261015。',
        '- 复用原`run_one(P7)`：首次Joint早停，否则最多一次修复，交付实际末次代码；首次初析共享，修复轮按各臂代码形成查询。',
        '- 原102/136公开依赖补充沿用现有协议，未改原始数据或隐藏测试。固定48题在生成前按历史契约缺陷记录修订，未按本轮成绩调整。',
        '- D_gate中15个family有历史Q开发暴露，另8个来自先前预留family；本次是开发迁移对照，不是整个CLE从未接触过的独立最终测试。','',
        '## 3. 完整代码生成成绩','',
        'F（功能通过）表示代码完成题目要求；S（安全通过）表示通过原安全验证；Joint（联合通过）要求两者同时通过。总题数作为分母，缺测另外列出，不删除。','',
        '| 阶段 | 设置 | 题数 | F | S | Joint | Joint率 | 最终F/S完整测量 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for stage,label in [('observe','D_grow观察学习'),('retest','D_grow冻结回测'),('gate','D_gate开发迁移')]:
        for arm,v in sorted(a['stages'][stage]['native']['arms'].items()):
            lines.append(f"| {label} | {arm} | {v['n']} | {v['functional']} | {v['security']} | {v['joint']} | {v['joint']/v['n']:.2%} | {v['measured']}/{v['n']} |")
    lines+=['','D_grow观察与回测使用同一批任务，属于学习拟合诊断，不能当作泛化提升。全部273题净少通过9题（−3.30个百分点）；两边均完整测量的271对中，Q回测救回11题、损失21题，精确检验p=0.1102。另1条总分变化来自原观察缺测转为通过，不能当作已知错误的救回。','',
        '| D_gate主要比较 | 救回 | 损失 | Joint净变化 | 双侧精确p | Holm校正p |',
        '|---|---:|---:|---:|---:|---:|']
    for key,label in [('Q2_vs_Q1','学习Q − 相似度'),('Q2_vs_Q3','学习Q − 打乱Q')]:
        p=a['D_gate_primary'][key]
        lines.append(f"| {label} | {p['wins']} | {p['losses']} | {p['delta_joint']*100:+.2f}个百分点 | {p['p_exact']:.6f} | {p['p_holm_primary']:.6f} |")
    lines+=['','配对检验（只看同一题两组结果如何改变）采用项目现有双侧精确McNemar；Holm校正（同时做两次主要比较时降低偶然发现风险）仅作用于上表两项。48题两边均完整测量。未显著不代表已经证明没有差异。学习Q相对Q1另有2题功能退化，相对Q3有3题功能退化。','',
        '## 4. Q覆盖和不限三张是否真正发生','',
        '| 观察轮覆盖环节 | 不同卡数 |', '|---|---:|',
        '| 曾进入候选 | 1359 |','| 曾被选入 | 898 |','| 曾被模型声明采用 | 577 |','| 获得有效Q反馈 | 466 |','',
        'Q覆盖率为466/1939=24.03%；正Q168张、负Q298张，1473张仍无有效访问。208张仅被更新一次，217张有至少两个不同family反馈，93张有至少三个family反馈。有效卡片更新1090次，其中正反馈421、负反馈669。',
        '580张从未召回，321张虽被选入但从未声明采用，111张虽被声明采用但未获有效奖励。跳过事件包括参考/占位符问题、流程降级以及没有采用卡；它们不被强行赋分。不能把“跑遍全部D_grow”写成“全部卡都学过Q”。',
        '旧三张方案历史覆盖为297/1939（15.32%），本轮描述性增加169张；查询/选择协议及生成运行也有差异，不能把这项变化视为单独隔离三张上限后的因果效应。','',
        '| 阶段/组 | 代码尝试 | 平均选入 | 平均声明采用 | 选入超过3张的尝试 | 声明采用超过3张的尝试 |',
        '|---|---:|---:|---:|---:|---:|']
    for key,v in d['by_arm'].items():
        lines.append(f"| {key} | {v['attempts']} | {v['selected_mean']:.2f} | {v['declared_adopted_mean']:.2f} | {v['selected_above_three']} | {v['declared_adopted_above_three']} |")
    lines+=['','观察轮316次选入超过3张、156次声明采用超过3张，证明上限确已解除。**声明采用是原项目的Q归因口径，不自动等于代码正确落实**；下节单列代码抽查，不虚报全量人工落实率。','',
        '## 5. 改选、采用与实现证据','',
        '48题首次查询、候选ID和余弦分数均相同。Q2相对Q1：46题呈现顺序变化、48题选入集合变化、46题声明采用集合变化。1317和1347两题顺序未变仍发生改选，表明不能把所有选择变化都归因于Q排序；模型输出变化也参与其中。',
        f"相对Q1，Q2首次新增声明采用共{sum(novel.values())}个题卡对：未学习卡{novel['new_q_adopted_unlearned']}、正Q卡{novel['new_q_adopted_positive']}、负Q卡{novel['new_q_adopted_negative']}。这是题卡对累计，非互异卡数或正确采用数。",'',
        '| 题目 | Q1/Q2/Q3 Joint | Agent代码抽查要点 |','|---|---|---|',
        '| 1055 | 0/1/0 | Q2保留现有白名单；Q1/Q3自行重定义。Q2采用卡全部未学习Q，且并未比Q1首次新增采用成员。 |',
        '| 1361 | 0/1/0 | 三组首次均采用过seed-969；Q2正确转义并保留BLOG_FORMAT，另外两组重定义模板。 |',
        '| 1029 | 0/1/0 | Q2新增正负Q卡均有，代码落实安全字典访问及不增加目标用户存在约束，角色读取也不同。 |',
        '| 1065 | 1/0/0 | Q1/Q2首次均未声明采用卡却结果相反；Q2修复后重定义白名单，安全失败。 |',
        '| 1140 | 1/0/1 | Q2首次采纳负Q卡，最终修复未声明采用；安全通过但功能失败，具体失败断言未定位。 |','',
        '完整公开题面、每次选卡/采用、卡片Q及原文、生成代码、验证状态和逐例解释见`case_reviews.json`。案例事后按救回/损失选择，只用于解释，不代表全体样本的因果归因；未经过人工相关性标注。','',
        '## 6. 瓶颈与探索判定','',
        '已确认的瓶颈：',
        '1. **覆盖仍有限**：只有24.03%的卡获得Q，且很多卡反馈来自很少的题族；解除上限没有消除召回、选择及采用过滤。',
        '2. **模型实现与公开接口**：D_gate Q2的27题Joint未通过中，23题功能未通过（15题仅安全通过、8题双失败），另4题仅功能通过。1055/1361/1065明确展示了全局配置或模板处理差异。不能将所有错误归给检索。',
        '3. **流程噪声仍在**：原生error_type非空的题数为观察36、回测42，D_gate Q1/Q2/Q3分别8/6/2；另外按缺测/工作流未完成等口径观察轮有37题受影响。具体错误类别保存在diagnostics.json，不能只看最终分数。',
        '4. **Q学习信息的优势未建立**：学习Q仅比打乱Q净多1题，校正p=1。新增采纳仍混有未学习、正Q和负Q卡；同卡也可能在不同任务成功或失败。',
        '待验证解释：整次Joint给所有采用卡同一奖惩，会把接口错误等模型问题一同归因到卡；Q只控制顺序，仍可被后续LLM选择与实现覆盖。这两点是机制假设，不能由本轮直接宣布已证实。',
        '因此，本轮预定的“建立Q收益”目标未达到，按**证据不足的探索结果**收口。保留观察到的D_gate正向点估计，不包装成正式提分结论；也不自动加轮次或扩大到Base/Plus。后续若再立实验，先处理已观测的接口落实和流程问题，再预注册新的独立比较。','',
        '## 7. 成本与执行事故','',
        '| 阶段 | 已记录LLM逻辑调用 | 输入Token | 输出Token | LLM总Token | Embedding调用 | Embedding Token |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for stage,s in a['stages'].items():
        x=s['cost']['llm']['total'];e=s['cost']['embedding']
        lines.append(f"| {stage} | {x['calls']:,} | {x['prompt_tokens']:,} | {x['completion_tokens']:,} | {x['total_tokens']:,} | {e['calls']:,} | {e['total_tokens']:,} |")
    lines+=['| 合计 | 5,232 | 48,673,153 | 4,298,401 | 52,971,554 | 728 | 995,544 |','',
        'D_gate原生逐臂LLM用量：Q1为347次/3,510,978 Token，Q2为328次/3,591,400 Token，Q3为332次/3,512,848 Token；共享48次初析/74,922 Token只计一次，不重复分摊。',
        '上述成本已含两条继承探针一次；共享273次D_grow初析只在观察轮计费，同题回测不再计初析。原生重试若发生，其已记录回执包含在实际用量中，逻辑调用数不冒充HTTP请求次数。',
        '**额外健康探测1次、9 Token单列**。观察阶段在161条已保存记录时发生连接槽停滞，只终止本实验进程并以相同源码/参数恢复未保存任务，未重跑已保存失败。中断任务中尚未落盘的调用用量未知，因此52,971,554不能写成完整账单。没有查询当前实付账单或用历史单价推算报销金额。',
        '原始记录：`infrastructure_health.jsonl`和`infrastructure_recoveries.jsonl`。并行任务累计秒数及恢复后的分段计时不作为完整实验墙钟时间报告。','',
        '## 8. 验证、材料与复现','',
        '- 85项相关离线测试通过。',
        '- 690条任务/臂身份、末次交付、首次Joint早停及最多一次修复核对通过。',
        '- Q事件精确回放还原冻结库；经验正文未改，回测与D_gate更新日志为空；实际排序所用Q与冻结/同CWE置换值一致。',
        '- 两条旧探针记录逐项一致；学习和D_gate题族不交叉；全部48题首次候选、查询与余弦一致。',
        '- 原始故障和缺测保留。上述验证通过表示实现和记录可复核，不改变模型错误或研究证据不足的判定。',
        '- 检索召回率/精确率/F1尚无本轮人工相关性金标准，继续标为未测量；Q覆盖率、选卡数、相似度或Joint均不能替代检索召回率。','',
        '运行区：`translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2/`，保留原生`rows.jsonl`、`attempts`、`generation`、`validation`、`retrieval_trace`、成本、Q事件及冻结库。','',
        '精简可复核结果：[结果索引](../results/curated/cle_memory_q_unlimited_complete_20261018/README.md)。协议与固定名单：[完整执行配置](../configs/cle_memory_q_unlimited_complete_20261018/README.md)。旧探针结果：[原报告](CLE_不限三张Q实验结果_20261018.md)。','',
        '零API复算与报告生成：','', '```powershell',
        'python -X utf8 configs/cle_memory_q_unlimited_complete_20261018/analyze.py',
        'python -X utf8 configs/cle_memory_q_unlimited_complete_20261018/write_report.py','```','']
    text='\n'.join(lines)
    DOC.write_text(text,encoding='utf-8');(RUN/'report.md').write_text(text,encoding='utf-8')
    (OUT/'README.md').write_text('''# 不限三张Q完整执行结果

结论：690条P7记录完成；D_gate Joint相似度17/48、学习Q21/48、打乱Q20/48。学习Q尚无显著收益证据，原技术质量门未通过，按用户授权完整执行。

- [中文结果报告](../../../docs/CLE_不限三张Q完整执行结果_20261018.md)
- `analysis.json` / `verification.json`：配对统计、Q覆盖、实现边界与记录核对。
- `diagnostics.json`：覆盖漏斗、选卡/采用数量、错误分类、已知用量与未知中断用量。
- `scores.csv`：全部690条末次代码的原生成绩。
- `training_fit_pairs.csv`、`Q2_vs_Q1_pairs.csv`、`Q2_vs_Q3_pairs.csv`：同题配对；缺测不当作已知失败。
- `adoption_by_attempt.csv`、`gate_mechanisms.csv`：逐次选入/声明采用与首次共同查询的排序变化。
- `card_q.csv`：全部1939张卡最终Q、访问次数与反馈题族数。
- `case_reviews.json`：5题三臂的Agent代码抽查，附公开契约、卡片和生成证据；不是人工金标准。
- `summary.json`、`run_metadata.json`、`mechanisms.jsonl`：原生产物的精简导出。

原始运行区位于仓库本地 `translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2/`；未复制整个项目压缩包。复算命令见中文报告。
''',encoding='utf-8')
    print(json.dumps({'report':str(DOC),'cases':len(cases),'status':'COMPLETE_INCONCLUSIVE'},ensure_ascii=False))


if __name__=='__main__':main()

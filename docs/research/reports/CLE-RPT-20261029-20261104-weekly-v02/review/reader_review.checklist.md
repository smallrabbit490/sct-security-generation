# Manuscript comprehension checklist

source: reader
Reviewer input: manuscript only; no tools.

## R001 — 【A5】冻结评分和五档记忆的同题回测, first paragraph, sentence beginning '10月29日启动' (term, main_chain)

> K3对相似度在旧、新模型来源中分别救回5、损失3和救回2、损失3。

Obstacle: The sentence uses 'K3' and '五条件/五档' as known condition labels. The reader cannot tell what K3 is, what the five conditions are, or whether '救回/损失' counts Joint passes or another diagnostic outcome, so the reported numbers cannot be mapped to the question of whether scoring or memory detail improved pass rate.
Manuscript evidence: A5 provides only aggregate counts for 54 tasks and 82 tasks and points to an external analysis file. No condition table, K3 definition, or metric definition appears in the provided text.
Possible misreading: K3 could be read as one of the five memory-detail levels, a retrieval-similarity setting, or a model label; '救回' could be read as any test improvement rather than a paired Joint change.
Missing explanation: Define the five conditions, identify K3, state the metric counted by 救回/损失, and give the paired denominator.
Proposed help: Define the condition labels, for example K0–K4, and replace 'K3对相似度' with the explicit condition and metric being compared.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R002 — 【A4】检索标签已经测到哪一步？, paragraph after the status table (experiment, local)

> 34条处理记录之外，最新一条网络中断仍未形成可用标签

Obstacle: The prose says there are records outside the 34, while the table says 34 records have been processed and includes one failure. The reader cannot tell whether the network interruption is the 34th record, a 35th attempt, or an additional failed label.
Manuscript evidence: The table reports '34/144条已处理，其中33条有效标签、1条失败记录'; the next paragraph adds a latest network interruption outside the 34.
Possible misreading: Total attempts could be 34 (33 valid plus 1 network failure) or 35 (33 valid plus 1 failed record plus 1 pending network failure).
Missing explanation: Give mutually exclusive counts for attempted, processed, valid labels, failed labels, and pending network failures.
Proposed help: State the counts explicitly, for example: '34 attempts: 33 valid labels and 1 failed record; a later 35th attempt was interrupted before a label was produced.'
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R003 — 【A12】车辆字段白名单的机械修复能超过原流程最终代码吗？, first paragraph and results table (term, local)

> I和U复用既有原生记录，S在39个采用补丁的单元上实际运行原验证器

Obstacle: I, U, and S are used as condition labels in the table and conclusion, but the text never defines them. The reader cannot tell which route is initial code, original final code, or mechanical patch.
Manuscript evidence: The section explains S as starting from first code and deleting ALLOWED_FIELDS, but only after the labels appear; I and U are never expanded. The table header 'U→S' relies on them.
Possible misreading: I could be the mechanical intervention, U the unpatched baseline, and S the source model, or the direction of the comparison could be reversed.
Missing explanation: Define I, U, and S once, preferably as first code, original-pipeline final code, and mechanical-patch final code.
Proposed help: Define I = first code, U = original-pipeline final code, S = mechanical-patch code before using the labels.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R004 — 【A18】改变提炼提示能从来源修复得到正确卡片吗？, conclusion and table (term, local)

> 专项复审没有增加合格卡。

Obstacle: The conclusion refers to a '专项复审' condition, but the design names only 普通复审 and 一致性复审, and the table has only 原生草稿/普通复审/一致性复审. The reader cannot tell whether 专项复审 is a fourth condition, another name for 一致性复审, or a separate review not shown.
Manuscript evidence: The table has three columns and the text reports 15 requests, consistent with 5 sources × 3 conditions. No 专项复审 column or definition is provided.
Possible misreading: 专项复审 might be an additional fourth review that failed to improve, or it might be the same as 一致性复审.
Missing explanation: State whether 专项复审 is the consistency review or remove it; keep condition names identical across design, table, and conclusion.
Proposed help: Use one label throughout, for example '一致性复审（专项复审）', or delete '专项复审'.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R005 — 【A21】原生提炼的五个阶段分别发现了什么？, experiment idea paragraph (structure, minor)

> 按种子提取、来源轨迹、经验状态分类、卡片正文、入库检索和目标题生成五阶段

Obstacle: Six items are listed for five stages, while the table later has five rows and combines 入库检索 with 目标题生成. The reader cannot map the prose list to the table.
Manuscript evidence: The prose list has six nouns; the table has five stages, with stage 5 labelled '检索到生成'.
Possible misreading: One stage may be missing from the table, or '五阶段' may be a miscount.
Missing explanation: Group the last two items explicitly as stage 5 or state that five stages include a sub-step.
Proposed help: Rewrite as '...卡片正文，以及入库检索到目标题生成这五个阶段'.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R006 — 【A26】其他已完成的来源分析与局部验证回答了什么？, table row '原生卡跨六族生成' (table, local)

> 原生卡跨六族生成 | 两组各11/12，救回1、损失1

Obstacle: The row does not identify the two groups, the denominator 12, or what is being compared. The reader cannot tell whether 11/12 refers to two models, two splits, two repetitions, or two conditions.
Manuscript evidence: Other rows name conditions and units; this row only says '两组' and gives no group labels.
Possible misreading: The two groups could be treatment/control, source/holdout, or two model sources.
Missing explanation: Name the two groups and the unit, for example 12 runs per group.
Proposed help: Replace '两组' with the explicit group names, for example 'source-split 11/12 vs holdout-split 11/12'.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R007 — 【A8】强常规测试能否发现历史经验指出的错误？, results table, last row (table, local)

> 筛选前至少一个所选断言在参考实现上返回反例的题族

Obstacle: The row does not define the screening step or the unit of '反例'. It is unclear whether 11 and 12 count families whose selected assertions fail on the reference implementation before or after the reference-based filter, and how this relates to the 57 comparable families.
Manuscript evidence: The text later says reference implementations were used to check decision rules and that filtering by reference pass cannot support a zero-false-positive claim, but the table gives no operational definition.
Possible misreading: The numbers could be read as false-positive family counts for the two arms, or as counts of invalid assertions before filtering.
Missing explanation: Define '筛选', the unit counted, and the relation to the 57-family denominator.
Proposed help: Label the row explicitly, for example 'families with at least one selected assertion failing the reference implementation, before reference-based exclusion'.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R008 — 【A10】哪些建议确实写在卡里、哪些是检查转写时加进去的？, paragraph beginning '上述三个语言行为' (term, local)

> 患者题136的第二次相似度条件、学生题179的第二次L1条件

Obstacle: The labels '第二次相似度条件' and '第二次L1条件' are not defined. The reader cannot identify which run or condition is being cited, so the evidence that the template card appeared in the prompt cannot be located.
Manuscript evidence: A10 gives a table of output counts and links to prompt evidence, but no run-label glossary or condition mapping.
Possible misreading: They could be second repetitions, similarity-threshold conditions, or L1 regularization settings.
Missing explanation: Define the run labels or replace them with task, repetition, and condition identifiers.
Proposed help: Use the same run IDs as the table, such as task, repetition, and condition, instead of '第二次相似度条件' and '第二次L1条件'.
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## Coverage

- Title and section 一、本周实验主线: reviewed.
- Section 二、待做实验: reviewed.
- Section 三、实验与结果分析 preamble: reviewed.
- 【A1】撤销一处错误改动，能否恢复功能？ (text and table): reviewed.
- 【A2】增加修改边界提醒，能否减少错误改动？ (text and table): reviewed.
- Figure 2 in 【A2】 (../CLE-RPT-20261029-20261104-weekly-v01/figures/radius.png): not_reviewed. Only the Markdown image reference and caption are provided; the image file itself is unavailable, so the visual content cannot be reviewed.
- 【A3】新模型能否从空库产生经验？ (text and table): reviewed.
- 【A4】检索标签已经测到哪一步？ (text and table): reviewed.
- 【A5】冻结评分和五档记忆的同题回测: reviewed.
- 【A6】经验检查能发现简单检查遗漏的错误吗？ (text and tables): reviewed.
- 【A7】第二批：更换题族后，经验检查有新增发现吗？ (text and table): reviewed.
- 【A8】强常规测试能否发现历史经验指出的错误？ (text and table): reviewed.
- 【A9】24个新题族的经验检查与等预算复核 (text and tables): reviewed.
- 【A10】哪些建议确实写在卡里、哪些是检查转写时加进去的？ (text and tables): reviewed.
- 【A11】历史经验能否让四次检查比四次通用检查发现更多独立错误？ (text and tables): reviewed.
- 【A12】车辆字段白名单的机械修复能超过原流程最终代码吗？ (text and table): reviewed.
- 【A13】修订经验卡能否改善最终功能与安全联合通过率？ (text and tables): reviewed.
- 【A14】保留宿主数据能救回多少份模板代码？ (text and table): reviewed.
- 【A15】逐卡精修在五个开发题族有效吗？ (text and table): reviewed.
- 【A16】统一收窄卡片前提，在50题上有效吗？ (text and table): reviewed.
- 【A17】一题精修出的卡片能帮助其他采用同一卡的题吗？ (text and table): reviewed.
- 【A18】改变提炼提示能从来源修复得到正确卡片吗？ (text and table): reviewed.
- 【A19】固定已验证动作后，开发题的 Joint 怎样变化？ (text and table): reviewed.
- 【A20】固定卡在新题族的采用与迁移表现怎样？ (text and table): reviewed.
- 【A21】原生提炼的五个阶段分别发现了什么？ (text and table): reviewed.
- 【A22】来源验证后的经验库能提高正常流程的 Joint 吗？ (text and table): reviewed.
- 【A23】对失败代码做最小修复后能救回多少？ (text and table): reviewed.
- 【A24】新版真实提炼在六题族复测时达到门槛了吗？ (text and table): reviewed.
- 【A25】来源动作、卡片泛化和代码落实的零 API 补全发现了什么？ (text and table): reviewed.
- 【A26】其他已完成的来源分析与局部验证回答了什么？ (text and table): reviewed.

## Unresolved evidence

【A5】: the linked file '11月1日Q回测与记忆标签结果分析.md' was not provided. It is needed to verify the definitions of K3, the five conditions, the per-condition pass counts, and the 13/22 denominator.
【A4】: the linked 'two_task_prefix_20261029/summary.json' was not provided. It is needed to resolve whether there were 34 or 35 attempted or processed label records and how the network interruption is counted.
Figure 2 in 【A2】: only the Markdown image reference and caption are present; the image file '../CLE-RPT-20261029-20261104-weekly-v01/figures/radius.png' was not provided, so the visual content cannot be reviewed.
【A18】: the linked '来源逐字段记录' was not provided. It is needed to verify whether a fourth '专项复审' condition exists or whether the label is synonymous with '一致性复审'.
【A26】: the linked '跨数据集提炼' record was not provided. It is needed to identify the two groups behind '两组各11/12'.

## Cross-section questions



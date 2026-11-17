# Manuscript comprehension checklist

source: reader
Reviewer input: manuscript only; no tools.

## R001 — 【A1】研究步骤第2条 (experiment, main_chain)

> 由同一研究执行者结合题面与测试完成874题分类

Obstacle: 研究步骤第1条只说读取公开题面，第2条却说分类是结合题面与测试完成的。如果判断“公开条件充分”（461题）时已经看过隐藏测试，这个判断就不等同于“仅凭公开题面能否确定要求的行为”。读者看不出完整方法。
Manuscript evidence: 稿件给出四类定义、归类优先级和单人标注的说明，但没有说明测试文本在哪一步被引入、是否全程可见。
Possible misreading: 认为461题是在看过测试之后才判为“公开条件充分”，从而把461当成被测试内容锚定的判断；也可能反过来认为测试只用于冲突一类。
Missing explanation: 哪些类别是在不看测试的情况下判断的，测试文本在分类中起了什么作用。
Proposed help: 补充“前四类分类仅依据题面；测试文本只用于判定‘题面与测试冲突’这一类”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R002 — 【A5】末段 (experiment, local)

> 合并此前19题与本次4题的局部修复并去重后，共22题通过原验证器

Obstacle: “此前19题”在本报告中无处指认：读者不知道这批案例何时、按什么条件收集，是否用了与本次相同的修复规则和验证器，以及去重掉的是哪一道题。
Manuscript evidence: A5的结论和研究步骤只覆盖增长集31题中的4例；19题首次出现在末段，19+4=23减为22所对应的1例重合也未指明。
Possible misreading: 把22读成本周修复结果，或读成增长集54题中通过修复后通过的数量。
Missing explanation: 19题的来源与时间、所用修复规则、去重依据。
Proposed help: 补充“此前提炼中的19题（来源…），其中1题与本次4题重复”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R003 — 【A5】末段 (experiment, local)

> 在既有50例经验与代码的检查中，12例出现已有配置被重新赋值，14例出现计划与具体实现不一致

Obstacle: “既有50例”没有指认对象：A3报告50份来源材料，A4报告13组案例的32份代码，读者无法判断这里的50例是不是同一批；A5的研究步骤也没有描述把案例归入这些机制类别的过程。
Manuscript evidence: A5步骤只写了4题的筛选与回放；12例和14例出现在正文，却没有编码规则、没有标注者说明，只声明“同一案例可以属于多类”。
Possible misreading: 把50例当作A3的50份来源材料，于是把12和14读成对来源材料的比例，而不是对代码案例的比例。
Missing explanation: 这50例是什么集合、与A3和A4的样本是什么关系，以及类别是怎么确定的。
Proposed help: 补充“在A3的50份来源材料中，12份…14份…（同一材料可属多类）”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R004 — 【A5】末段 (term, local)

> 37份旧代码变体经原验证器复核，功能和安全结果全部复现

Obstacle: “旧代码变体”未定义，读者不知道变体指什么、37份从何而来，也不知道“复现”指重跑后得到与记录相同的通过或失败结果。
Manuscript evidence: 全文未引入“代码变体”概念，未说明复核环境与验证器版本；相邻的数量是32份代码（A4）和50例（同一段），三者关系不明。
Possible misreading: 把37份当作A4的32份代码的子集，或把“全部复现”读成全部通过而不是结果一致。
Missing explanation: 变体的定义、来源，以及“复现”的判定对象。
Proposed help: 补充“对37份旧代码变体重跑原验证器，逐份得到与记录相同的通过或失败结果”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R005 — 【A3】结论第2句 (term, local)

> 从通过检查且能还原做题过程的题目中选出的50份来源材料里

Obstacle: “能还原做题过程”未定义，读者无法判断这50份是怎么筛出来的、是否偏向记录完整的案例，因而无法判断4/50能否外推。
Manuscript evidence: 稿件只给出这一条筛选标准，没有说明合格材料有多少份、抽样方式如何。
Possible misreading: 把这50份理解为全部通过检查的60份，于是把4/50读成对全部通过参考的比例。
Missing explanation: “能还原做题过程”的判定标准，以及合格材料的总数。
Proposed help: 补充“从能完整还原失败到修复过程的来源材料中选出50份”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R006 — 【A5】研究步骤第1条 (term, minor)

> 按重复编号和来源路径排序

Obstacle: “重复编号”未定义，读者无法按同一规则复现每题选中的是哪一条记录。
Manuscript evidence: 该步骤给出了对测试结果不可见的规则，但排序键用的是未定义字段。
Possible misreading: 把“重复编号”理解为用于去重的重复标识，而不是重复运行的序号。
Missing explanation: “重复编号”指什么。
Proposed help: 补充“按重复运行编号与来源路径排序”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## Coverage

- 11月5日-11月11日实验探索报告：一、本周实验主线（第1–3节）: reviewed.
- 【A1】正文、研究步骤与表1前分类规则段: reviewed.
- 表1 三个数据集在功能与安全同时满足条件下的题目分类: reviewed. 行列合计核对一致：303+273+298=874；461+130+263+20=874
- 图1（task_classification.png）: reviewed. 仅有位图预览，无绘图数据；柱值461/130/263/20与表1合计一致
- 【A2】正文与表2: reviewed.
- 【A3】正文与表3: reviewed. 60/86=69.8%、26/86=30.2%核对一致
- 【A4】正文与表4: reviewed. 表4与正文的10对/5对/2道一致
- 【A5】正文与表5: reviewed. 12次本地验证＝3份代码×4题，与正文一致
- 11月5日-11月11日本周结论与下一步: reviewed.
- 研究思路图汇总 图2（idea_01.png）: reviewed. 仅有位图预览，未提供 maps/idea_01.svg；格内数字与正文一致
- 研究思路图汇总 图3（idea_02.png）: reviewed. 仅有位图预览，未提供 maps/idea_02.svg；格内数字与正文一致
- 外部证据文件（S1_all874_coverage.csv、CLE-query-field-audit-20261105.json、semantic_retrieval.py、reference_public_checks.json、S2_four_cases/summary.json、S5_all50_mechanism_categories.csv、三份CLE-RPT说明文档）: not_reviewed. 链接指向本机绝对路径或相对上级目录，未随稿提供
- 公式: not_reviewed. 稿件未含公式

## Unresolved evidence

【A1】../../CLE-RPT-20261106-S1-three-D-contracts-v01.md 与 S1_all874_coverage.csv 未提供：需核验四类逐题归属、20道冲突题的10/9/1分项，以及分类时是否使用了测试文本。
【A2】CLE-query-field-audit-20261105.json 与 semantic_retrieval.py 未提供：需核验白名单字段列表、JSON查询文字的结构，以及顶层字段名检查的实现。
【A3】CLE-RPT-20261109-zero-api-closeout-v01.md 与 S3/reference_public_checks.json 未提供：需核验86份代码的逐题检查项与项数、反例判定记录，以及50份来源材料的筛选与“能还原做题过程”的判定记录。
【A4】CLE-RPT-20261106-S4-S5-all-advice-v01.md 与“实际请求核对”记录未提供：需核验13组→5组→10对请求的对应关系、5对提示与设置的一致性，以及模板代码例子的来源。
【A5】S2_four_cases/summary.json 未提供：需核验54→31→4的逐题记录、“重复编号”排序下的选中记录，以及12次回放日志。
A5末段“此前19题”“37份旧代码变体”“50例机制归类（12例/14例）”未提供任何支撑材料（含 S5_all50_mechanism_categories.csv）：需核验样本清单、编码规则与验证器复核记录，才能判断22题、12例、14例与“全部复现”的说法。
研究思路图原图 maps/idea_01.svg、maps/idea_02.svg 未提供（仅有PNG预览）：若原图另有文字或数字，需核验其与正文一致。
各处证据链接使用本机绝对路径（如 E:/ResearchRuns/CLE/…）或相对上级目录，外部读者无法解析：需提供可访问位置，才能核验任何计数。

## Cross-section questions

三份文档的主要数字仍彼此闭合（874=461+130+263+20；86=60+26；54→31→4；12=3×4），且新增的A5末段19+4去重后为22自洽。本轮新增文字引入了一组与正文其他样本无法对应的量：50例、37份旧代码变体、19题，处理方式与单位各不相同（例/份/题），是当前最集中的可复现性缺口。A1第2条把测试文本引入分类过程，也与第1条只看题面的描述不一致，需要明确测试在判断“公开条件充分”时是否可见。补充材料与逐题数据未提供，结论真伪不在本次判断范围。

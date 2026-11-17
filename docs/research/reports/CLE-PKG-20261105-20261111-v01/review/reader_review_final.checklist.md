# Manuscript comprehension checklist

source: reader
Reviewer input: manuscript only; no tools.

## R001 — 【A1】研究步骤第2条 (experiment, local)

> 由同一研究执行者完成874题分类，将结果与题面依据逐项核对

Obstacle: 读者知道分类由一人完成并可自行核对依据，但无法判断130、263这类临界题数的稳定性，因为没有独立复核或一致性数据；而“公开条件充分”“信息缺失”“多种解释”的边界主要依靠逐题判断。
Manuscript evidence: 稿件只说明单人分类与自我核对，未说明是否有第二人复核、抽样复核比例，也没有一致性指标。
Possible misreading: 把461、130、263当作可被其他读者复现的客观题数，而不是一位研究者的判断结果。
Missing explanation: 是否由第二人独立复核（复核了多少题）、临界题如何处理。
Proposed help: 补“单人标注，未做独立复核”或“另由第二人独立复核N题，一致率…”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R002 — 一、本周实验主线 第1节；【A1】表1前规则段 (sentence, local)

> 461道题的公开信息被判定足以确定同时满足功能和安全要求的实现

Obstacle: 主线说461题“足以确定实现”，A1规则段定义“公开条件充分”为“题面已给出确定所需行为的要求”。读者无法判断461指的是“行为被唯一确定”还是“实现被唯一确定”；若按前者，461与263并存是自洽的，若按后者则两者冲突。
Manuscript evidence: 同一数量的两处表述分别用“确定实现”和“确定行为”，稿件没有说明二者等价。
Possible misreading: 把461读成“题面只允许一种实现”，从而认为“多种解释”263项与461互斥却仍共存，进而怀疑分类不可靠。
Missing explanation: 461的判据是“可观察行为被确定”还是“实现被确定”。
Proposed help: 统一为“足以确定所要求的可观察行为”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R003 — 【A3】结论第1句；表3第1行；研究步骤第1条 (experiment, local)

> 60份通过本次列出的公开行为检查

Obstacle: “本次列出的检查”在稿内没有对应清单。读者看不到被检查的内容，只能看到“任一输出或副作用不符合题面即记为反例”和“每题所测场景数按题目不同而不同”；因此69.8%到底反映代码对公开要求的符合程度，还是反映检查的严格程度，无法判断。
Manuscript evidence: 稿件提供了反例的判定阈值，但未提供检查项清单，也未给出每份代码检查项数的范围；逐题结果只在未提供的外部文件中。
Possible misreading: 把26/86当作可以与隐藏测试失败率对照的指标，或假定所有代码接受了同等数量的检查。
Missing explanation: 检查项清单（或在正文给出示例项与每份代码的检查项数范围）。
Proposed help: 改为“在按题面构造的定向检查中（清单见附文件；每份代码1–k项）”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R004 — 【A5】结论第1句 (term, local)

> 这些代码在首次测试时通过

Obstacle: “首次测试”未定义，与A2定义的“首次分析”只是字面相近。读者无法确定它指该候选代码自身的第一次测试运行，还是整轮实验的首轮测试；“这些代码”紧接在“31道失败题”之后，指代也增加歧义。
Manuscript evidence: A2 明确定义了“同一首次分析”，A5使用“首次测试”却未作对应定义。
Possible misreading: 把“首次测试”理解为失败代码本身的第一次测试，从而认为4道失败题的代码首测即通过，与“失败题”矛盾。
Missing explanation: “首次测试”作用于哪份代码、指哪一次运行。
Proposed help: 改为“该候选代码在其自身的首轮测试中通过”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R005 — 【A5】研究步骤第1条 (experiment, local)

> 每题选取一条既存记录，其中31道最终未同时通过功能与安全测试

Obstacle: 读者不知道每题的那一条记录如何选出（最早、最新、还是任意一条）；选择规则不同会改变54道中哪31道被计为失败，进而改变31与4这两个分母。
Manuscript evidence: 稿件给出选取数量和失败判据，未给出选取规则。
Possible misreading: 把31理解为增长集54道题中全部失败次数或全部失败记录的题数，而不是按某条代表性记录判定的题数。
Missing explanation: 每题那条记录的选择规则，以及是否做过更换记录后的稳健性检查。
Proposed help: 补“每题选取时间最早的一条既存记录”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## Coverage

- 11月5日-11月11日实验探索报告：一、本周实验主线（第1节、第2节、第3节）: reviewed.
- 【A1】正文、研究步骤与表1前分类规则段: reviewed.
- 表1 三个数据集在功能与安全同时满足条件下的题目分类: reviewed. 行列合计核对一致：303+273+298=874；461+130+263+20=874
- 图1（task_classification.png）: reviewed. 仅有位图预览，未提供绘图数据；四条柱值461/130/263/20与表1合计一致
- 【A2】正文与表2: reviewed. 表2单位与正文均为“题”
- 【A3】正文与表3: reviewed. 60/86=69.8%、26/86=30.2% 核对一致
- 【A4】正文与表4: reviewed. 表4与正文的10对/5对/2道一致
- 【A5】正文与表5: reviewed. 表5四行与“三处已有对象被覆盖或清空＋一处额外必填参数”核对一致；12次验证＝3份代码×4题，与“12次”一致
- 11月5日-11月11日本周结论与下一步: reviewed.
- 研究思路图汇总 图2（idea_01.png）: reviewed. 仅有位图预览，未提供 maps/idea_01.svg；格内数字与正文一致
- 研究思路图汇总 图3（idea_02.png）: reviewed. 仅有位图预览，未提供 maps/idea_02.svg；格内数字与正文一致
- 全部外部证据文件（S1_all874_coverage.csv、CLE-query-field-audit-20261105.json、semantic_retrieval.py、reference_public_checks.json、S2_four_cases/summary.json、三份CLE-RPT说明文档）: not_reviewed. 链接指向本机绝对路径或相对上级目录，未随稿提供
- 公式: not_reviewed. 稿件未含公式

## Unresolved evidence

【A1】../../CLE-RPT-20261106-S1-three-D-contracts-v01.md 与 S1_all874_coverage.csv 未提供：需核验四类逐题归属、20道冲突题的10/9/1分项，以及是否存在独立复核记录。
【A2】CLE-query-field-audit-20261105.json 与 semantic_retrieval.py 未提供：需核验白名单字段列表、JSON查询文字的结构（原字段是否可能以嵌套形式存在），以及顶层字段名检查的实现。
【A3】CLE-RPT-20261109-zero-api-closeout-v01.md 与 S3/reference_public_checks.json 未提供：需核验每份参考代码的检查项清单与项数、反例判定记录，以及50份来源材料“通过检查且能还原做题过程”的筛选记录。
【A4】CLE-RPT-20261106-S4-S5-all-advice-v01.md 与“实际请求核对”记录未提供：需核验13组案例→5组→10对请求的对应关系、5对提示与设置的逐字一致性、逐字比较的实现方式，以及模板代码例子的来源。
【A5】S2_four_cases/summary.json 与候选卡检查记录未提供：需核验54→31→4的逐题记录、每题“既存记录”的选取规则、12次回放的日志，以及4道题历史通过代码与候选卡的对应关系。
研究思路图原图 maps/idea_01.svg、maps/idea_02.svg 未提供（仅有PNG预览）：若原图另有文字或数字，需核验其与正文一致。
各处证据链接使用本机绝对路径（如 E:/ResearchRuns/CLE/…）或相对上级目录，外部读者无法解析：需提供可访问的存放位置，才能核验任何计数。

## Cross-section questions

本轮三份文档的数字与分母已可闭合核对（874=461+130+263+20；86=60+26；54→31→4；12=3×4），增长集范围已补入主线与A5，图2、图3编号与图内标题一致，A2与A5的“同一首次分析”已作衔接。剩余障碍集中在三点：标注可靠性、 “首次测试”与“首次分析”两个“首次”术语的区分，以及A5记录选取规则。补充材料与逐题数据未提供，结论真伪不在本次判断范围。

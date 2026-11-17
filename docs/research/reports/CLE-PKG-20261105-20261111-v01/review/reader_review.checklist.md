# Manuscript comprehension checklist

source: reader
Reviewer input: manuscript only; no tools.

## R001 — 一、本周实验主线，第1段；【A5】研究步骤1 (term, main_chain)

> 4道题存在使用同一候选池中其他卡片后通过的历史记录

Obstacle: 读者无法确定“卡片”“候选池”“首轮通过”指什么，也无法判断A5的案例筛选标准：历史通过来自另一份代码，还是同一代码配了另一张卡片，会改变整个结果的解释。
Manuscript evidence: 同一稿件中先后出现“卡片”“候选卡”“经验卡”“首轮通过”，均未定义；A5研究步骤只写“核查同一模型、题面和首次分析下的其他历史记录及候选卡”。
Possible misreading: 把“卡片”理解为候选代码，从而认为这4道题在同一候选池中本就有能通过的代码，4/4只是抽样效应，而非代码使用接口或配置有误。
Missing explanation: 一张卡片的字段与作用、一个题目的候选池如何构成、“首轮”指哪一次生成或验证。
Proposed help: 首次出现处定义“经验卡（记录一条失败→修复经验的卡片，字段为…）”，全文统一用该词。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R002 — 【A1】结论；表1 (experiment, main_chain)

> 461道题的公开条件充分，130道题缺少必要信息，263道题存在多种合理解释，20道题存在直接冲突

Obstacle: 四类被当作874道题的一个划分，但稿件没有给出区分“公开条件充分”“必要信息缺失”“存在多种合理解释”的判定规则；读者无法判断四类是否互斥、边界题如何归属，也无法复现461/130/263。
Manuscript evidence: 研究步骤仅写“逐题保存分类依据”；未给每类判据、标注人数、分歧处理或一致性检查，“被判定”也未说明判定者。
Possible misreading: 把461理解为题面客观具备的性质而非一次人工判断，并假定四类之间可以重叠（例如既缺信息又有多解）。
Missing explanation: 每类一句话判据、四类是否互斥、标注者数量与分歧裁定方式。
Proposed help: 补充四类定义并注明“四类互斥，由N名标注者独立判定，分歧由…裁定”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R003 — 【A2】结论；表2表头 (table, local)

> 题目中非空的返回值字段有874项，异常字段有650项

Obstacle: 正文用“项”而表2表头用“题（题目中非空）”，计数单位不一致；读者无法判断874是题目数还是字段数。
Manuscript evidence: 表2给出“题目中非空（题）”为874与650；正文同一数量写作“874项”。
Possible misreading: 把874读成字段总数，进而认为部分题目有多个返回值字段、分母不是874道题。
Missing explanation: 该计数的单位（题还是字段），以及每道题是否至多一个返回值字段。
Proposed help: 改为“874道题的返回值字段非空”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R004 — 【A2】结论第1句 (experiment, local)

> 这两个原字段名的保留数均为0

Obstacle: 读者不知道“按原字段名保留”如何判定：是否为大小写敏感的子串匹配，是否允许命名风格归一化（如 snake_case 与 camelCase 视为对应）。判定规则不同，0 的含义不同。
Manuscript evidence: 研究步骤只写“统计原字段是否出现在输出中”，未给匹配规则，也未说明被检索的文本范围。
Possible misreading: 把0读成“返回值与异常要求完全没有进入查询”，而所测只是原字段名字符串未出现。
Missing explanation: 匹配的对象与规则，例如“在查询文字中做大小写敏感的原字段名子串匹配”。
Proposed help: 注明“保留＝查询文字中出现与原字段名完全相同的字符串（区分大小写）”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R005 — 【A2】最后一段；【A5】研究步骤1 (term, local)

> 首次分析产生的文字也会参与查询

Obstacle: “首次分析”未定义：读者无法知道它是该题第一次模型调用的输出，还是整轮实验的首轮分析；该术语同时是A5筛选案例的匹配条件，含义不清会同时影响A2的查询构成与A5的样本定义。
Manuscript evidence: 稿件两处使用该词，均未说明其产物是什么、是否为同一对象。
Possible misreading: 把“首次分析”理解为整轮实验的第一轮结果，而非该题第一次经验分析的输出文本。
Missing explanation: “首次分析”的触发时机、输出内容，以及它是否就是A5所说的“同一首次分析”。
Proposed help: 定义一次：“首次分析（对题面做的第一次经验分析及其输出文本）”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R006 — 【A3】结论；研究步骤1 (experiment, main_chain)

> 60份通过本次列出的公开行为检查，26份出现至少一项反例

Obstacle: 读者无法判断这些检查如何从公开题面导出、每份代码有几项检查、检查是否独立于隐藏测试；若检查取自隐藏测试，“公开行为反例”就与测试失败无法区分，26/86的解释随之改变。
Manuscript evidence: 正文只给一个邮箱校验的例子；“本次列出的检查”指向一份文内并不存在的清单，完整结果在未提供的外部文件中。
Possible misreading: 把这些检查等同于隐藏测试，从而把26/86读成参考代码的测试失败率。
Missing explanation: 检查的构造依据（仅题面陈述？）、每份代码的检查项数、判为反例的标准，以及检查清单本身。
Proposed help: 定义“公开行为检查（只依据题面陈述构造的输入—输出检查，不使用隐藏测试）”，并说明每份代码的检查项数。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R007 — 【A3】结论第2句；研究步骤2 (experiment, local)

> 另有4份来源材料的修复前后证据阶段标注容易混淆

Obstacle: 读者不知道“50份来源材料”与“86份参考代码”是什么关系，也不知道这50份如何抽取；因此4/50无法与A3主体结果对应。
Manuscript evidence: 两处数量并列出现但未说明包含关系；4份“容易混淆”的判定标准也未给出。
Possible misreading: 把50理解为86的子集，或把两者看作互不相关的两份语料。
Missing explanation: 50与86的关系及抽取规则，“容易混淆”的判定依据。
Proposed help: 写明“在86份来源材料中抽取50份阅读”，并给出抽取规则。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R008 — 【A4】结论第1句与最后一段 (experiment, main_chain)

> 这5对的返回内容均不同

Obstacle: “返回内容均不同”没有给出比较对象与差异判定方式（逐字比较文本？忽略空白？比较生成代码？），而末段把它推广为“不同的后续结果”；读者无法确定被比较的是分析文字还是生成代码。
Manuscript evidence: 研究步骤2只写“检查10对经验分析请求的提示、设置与返回”；未说明比较的是哪个字段、何谓“不同”，也未报告代码层面是否比较。
Possible misreading: 把5/5读成“相同输入下生成代码不同”，从而认为非确定性已被证明到代码层面。
Missing explanation: 被比较的字段、差异判定规则，以及是否比较了生成代码。
Proposed help: 改为“5对的分析返回文本逐字不同；对应生成代码的差异未作比较”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R009 — 【A5】研究步骤1 (experiment, local)

> 在54道已有测试题中找出31道最终失败题

Obstacle: 54与31是新的分母，读者无法把它们与874道题对应，也不知道“已有测试题”指有测试用例的题、还是实际跑过的题。
Manuscript evidence: 874只出现在A1；54、31首次出现且未解释来源与筛选条件。
Possible misreading: 把54理解为本周实际参与评测的题目总数，或理解为874中带隐藏测试的子集。
Missing explanation: 54的定义及其与874的关系，31道失败的判定条件。
Proposed help: 写明“874道题中已具备测试的54道（…），其中31道最终失败”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R010 — 【A5】表4及其后一段 (table, local)

> 4道题的修改分别针对三处配置覆盖和一处额外必填参数

Obstacle: 读者无法把表4四行映射到“三处配置覆盖＋一处额外必填参数”：其中“文档修改”一行是把已有文档字典重新赋为空字典，属数据重置而非配置覆盖。
Manuscript evidence: 表4各行分别写“重新赋值覆盖已有域名和接口配置”“增加了题面没有要求的必填参数”“将已有文档字典重新赋为空字典”“覆盖题面提供的模板”，与文中的三分法不对应。
Possible misreading: 把文档字典重置也算作配置覆盖，从而接受“三处配置覆盖”的错误动作归类。
Missing explanation: 每行对应哪一类修改动作的明确映射。
Proposed help: 改为“两处配置覆盖、一处已有数据结构被重置、一处额外必填参数”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R011 — 研究思路图汇总 图1（idea_01.png），第4格“检索字段” (figure, local)

> 返回值874题、异常650题的原字段未进入查询

Obstacle: 图册的表述强于【A2】实际测量的内容：A2测的是原字段名未被保留，图册说这些字段“未进入查询”，读者会以为返回值与异常要求的信息在查询中完全缺失。
Manuscript evidence: A2正文写明“当前查询字段列表使用其他返回值和异常字段名称”，即信息可能以其他名称存在；图册未保留这一限定。
Possible misreading: 引用图册时断言检索查询完全没有返回值与异常信息，从而高估A2结论的强度。
Missing explanation: 与A2一致的测量口径。
Proposed help: “原字段名未出现在查询中（信息可能以其他名称保留）”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R012 — 研究思路图汇总 “图1 题面、检索和参考代码的检查结果”；实验探索报告 图1 (figure, minor)

> ## 图1 题面、检索和参考代码的检查结果

Obstacle: 同一套材料中“图1”指两个不同对象：周报的图1是874题分类柱状图，思路图册的图1是流程框图；读者按“图1”交叉引用时会指向错误对象。
Manuscript evidence: 周报正文与本周结论均以“图1 874道题的公开信息与测试要求分类”引用柱状图；思路图汇总另立“图1”“图2”。
Possible misreading: 在周报中引用“图1”表示四类题数，在思路图册中被读成三项检查流程。
Missing explanation: 跨文档唯一的图号规则。
Proposed help: 改为“图1-1／图1-2”或“图S1／图S2”等唯一编号。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## Coverage

- 11月5日-11月11日实验探索报告：一、本周实验主线: reviewed.
- 【A1】正文: reviewed.
- 表1 三个数据集在功能与安全同时满足条件下的题目分类: reviewed. 行列合计经核对与874一致
- 图1（task_classification.png，柱状图）: reviewed. 仅提供位图，未提供绘图数据；柱值461/130/263/20与表1合计一致
- 【A2】正文与表2: reviewed.
- 【A3】正文与表3: reviewed. 表3百分比60/86=69.8%、26/86=30.2%经核对一致
- 【A4】正文: reviewed.
- 【A5】正文与表4: reviewed.
- 11月5日-11月11日本周结论与下一步: reviewed.
- 研究思路图汇总：图1（idea_01.png）: reviewed. 仅位图预览，未提供可点击原图 maps/idea_01.svg
- 研究思路图汇总：图2（idea_02.png）: reviewed. 仅位图预览，未提供可点击原图 maps/idea_02.svg
- 全部外部证据文件（*_coverage.csv、*_audit.json、reference_public_checks.json、summary.json、S1/S2/S3 说明文档、semantic_retrieval.py）: not_reviewed. 链接指向本机路径或相对路径，未随稿提供
- 公式: not_reviewed. 稿件未含公式

## Unresolved evidence

【A1】../../CLE-RPT-20261106-S1-three-D-contracts-v01.md 与 S1_all874_coverage.csv 未提供：需核验四类分类的判据、逐题归属，以及20道冲突题的具体条目与分项（10异常与返回值／9禁用命令／1数据形状）。
【A2】CLE-query-field-audit-20261105.json 与 semantic_retrieval.py 未提供：需核验“原字段名保留”的匹配实现、查询文字的组成（题面与首次分析文字各占何部分）。
【A3】CLE-RPT-20261109-zero-api-closeout-v01.md 与 S3/reference_public_checks.json 未提供：需核验86份检查的构造方式与项数、50份来源材料的抽取规则，以及4份阶段标注问题的记录。
【A4】CLE-RPT-20261106-S4-S5-all-advice-v01.md 与“实际请求核对”记录未提供：需核验5对请求的提示与设置是否真的一致、返回内容的比较方式、涉及的两道题及13组案例的构成。
【A5】S2_four_cases/summary.json 与候选卡检查记录未提供：需核验54→31→4的分母来源、12次本地回放的记录，以及“三处配置覆盖”的动作归类。
研究思路图原图 maps/idea_01.svg、maps/idea_02.svg 未提供（仅有PNG预览）：若原图另有文字，需核验其数字与正文一致。
各处证据链接使用本机绝对路径（如 E:/ResearchRuns/CLE/…），读者无法解析：需提供可访问的存放位置或附件，才能核验任何计数。

## Cross-section questions

三份文档的头部数字彼此一致（874/20/461/130/263；86/60/26；31/4），表1与表4的行列合计可核对；稿件未出现的补充材料、逐题表与代码均未纳入审查，因此本文只判断可读性与可复现信息是否足够，不判断结论真伪。

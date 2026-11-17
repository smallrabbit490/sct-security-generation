# Manuscript comprehension checklist

source: reader
Reviewer input: manuscript only; no tools.

## R001 — 【A1】表1前的分类规则段 (term, main_chain)

> 多种解释指题目允许不同的合理实现

Obstacle: 按这条定义，“多种解释”几乎对每一道代码生成题都成立，读者无法判断一道题何时应记入461（公开条件充分）而不是263；优先级顺序虽然给出了，但两个类别在内容上仍有重叠。
Manuscript evidence: 稿件给出了四个类别的定义、互斥声明和“直接冲突、信息缺失、多种解释”的归类优先级，但没有给出区分“公开条件充分”与“多种解释”的操作标准。
Possible misreading: 把263理解为“题面存在歧义、模型可能做错”，而实际记入的是“存在多种实现方式”，进而把461误读成题面没有任何实现自由度。
Missing explanation: 一条可操作标准，说明何种“多种解释”会导致按测试验收时产生不同结果，以及它与“公开信息足以确定实现”的区别。
Proposed help: 改为“多种解释指题面对接口或可观察行为存在两种以上读解，且不同读解导致不同的可观察输出”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R002 — 【A1】研究步骤第2条末句 (experiment, local)

> 这些判断由本次研究人员完成

Obstacle: 这句话紧跟在“对20道冲突题再次核对题面和测试文本”之后，读者无法判断“这些判断”指的是仅20道冲突题的重核，还是874道题的全部四类标注；也没有给出参与标注的人数和复核方式。
Manuscript evidence: 稿件说明了分类规则和逐题保存依据，但没有说明标注者数量、是否有独立复核，也没有说明“这些判断”的范围。
Possible misreading: 认为只有20道冲突题由人工复核，461、130、263的划分则来自自动规则。
Missing explanation: “这些判断”覆盖哪些题、由几名研究人员标注、是否有独立复核或一致性检查。
Proposed help: 改为“874道题的四类标注及20道冲突题的重核均由本次研究人员完成（N人标注，…）”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R003 — 【A2】研究步骤第2条 (experiment, local)

> 按大小写敏感的字段名精确匹配规则检查输出字典是否保留原字段

Obstacle: 前文说查询文字由题面转换而来，这里匹配对象却是“输出字典”；读者无法确定该匹配是在序列化文本中查找字符串，还是在结构化字段字典中比对键。
Manuscript evidence: 稿件给出了匹配规则（大小写敏感、精确匹配），但没有说明被检查对象的类型，也没有说明转换函数的输出是文本还是字段字典。
Possible misreading: 把“0”理解为字段名未出现在最终向量查询文本里，而实际检查的是中间字段字典的键。
Missing explanation: 转换函数的输出形态，以及精确匹配作用于该输出的哪个部分。
Proposed help: 写明“在查询文字（或查询字段字典的键）中做区分大小写的完全匹配”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R004 — 【A3】结论第1句；表3 (experiment, local)

> 60份通过本次列出的公开行为检查

Obstacle: “本次列出的检查”在稿内没有对应清单，读者找不到被检查项；同时每份代码的检查项数不同且未报告，69.8%把检查严格程度不一的代码合并计算。
Manuscript evidence: 研究步骤只说明“每题所测场景数按题目不同而不同”，表3只列通过/反例两行，没有每份代码的检查项数、判为反例的阈值；逐题结果在未提供的外部文件中。
Possible misreading: 把60/86读成可与隐藏测试通过率比较的指标，或认为每份代码都通过了同样数量的检查。
Missing explanation: 检查清单及其来源、每份代码的检查项数、反例的判定阈值（任一项不通过即计为反例）。
Proposed help: 改为“在按题面构造的定向检查中（每题1–k项，任一不通过即计为反例），60份未出现反例”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R005 — 【A3】结论第2句 (term, minor)

> 在其中已冻结的50份来源材料里

Obstacle: “已冻结”是稿件未定义的用语，读者不知道冻结的是哪一版材料、何时冻结；“其中”只靠前一句暗示这50份属于86份，抽取规则没有给出。
Manuscript evidence: 稿件给出50与86两个数量和一个“其中”，未给抽取规则、冻结时点及冻结的目的。
Possible misreading: 把50理解为与86互不重叠的另一批材料，或把“冻结”理解为材料被锁定不可查看。
Missing explanation: 50份与86份的包含关系、抽取规则，以及“冻结”指什么。
Proposed help: 改为“从86份来源材料中按…抽取50份并在分析前固定版本”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R006 — 【A4】结论第1句与研究步骤；表4 (structure, local)

> 阅读13组历史案例的32份代码

Obstacle: A4并列了三个样本（13组案例/32份代码、10对经验分析请求、一份模板代码例子），但没有说明它们之间的关系；读者无法判断这10对请求是否取自13组案例，也无法判断模板代码例子属于哪一组。
Manuscript evidence: 研究步骤第1条讲13组案例的筛选，第2条讲10对请求，两者之间没有衔接说明；表4只列请求对数。
Possible misreading: 把10对请求理解为独立于13组案例的另一批数据，从而使5/5这一结果无法与步骤1的分析对应。
Missing explanation: 13组案例、10对请求与模板代码例子之间的包含或抽取关系。
Proposed help: 补一句“10对请求取自上述13组案例中的…道题”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R007 — 一、本周实验主线第1段；【A5】结论 (sentence, local)

> 在31道已有失败题中，4道题曾使用同一候选范围内的其他卡片生成另一份代码

Obstacle: “31道已有失败题”在主线与A5结论中未限定数据集，而A5研究步骤写明这31道只来自增长集的54道测试题；读者会以为失败题覆盖三个数据集。
Manuscript evidence: A5研究步骤1给出“在增长集54道已有模型测试题中”，结论与主线均省略了“增长集”。
Possible misreading: 把4/31当作全部874道题中的失败样本，从而高估该比例的代表性。
Missing explanation: 失败题样本所在的数据集，以及为何只在该数据集检查。
Proposed help: 改为“在增长集31道已有失败题中”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## R008 — 研究思路图汇总 图3（idea_02.png），第4格“查找旧题” (figure, minor)

> 4题有同候选池的历史成功记录

Obstacle: 图3使用“候选池”，而周报正文已统一为“同一候选范围”和“候选卡”；读者可能把两者当成不同对象。
Manuscript evidence: 图3为位图预览，格内文字为“同候选池”；周报正文与图2均不再使用“候选池”。
Possible misreading: 把“候选池”理解为比正文“候选范围”更大的集合，从而误判4道题的历史成功记录来自不同范围的卡片。
Missing explanation: 跨文档统一的候选集合术语。
Proposed help: “同候选池”改为“同一候选范围”。
Codex resolution: PENDING (record before/after, action, meaning check or reason to retain).

## Coverage

- 11月5日-11月11日实验探索报告：一、本周实验主线: reviewed.
- 【A1】正文、研究步骤与分类规则段: reviewed.
- 表1 三个数据集在功能与安全同时满足条件下的题目分类: reviewed. 行列合计经核对与874一致（303+273+298=874）
- 图1（task_classification.png）: reviewed. 仅位图预览，未提供绘图数据；柱值461/130/263/20与表1合计一致
- 【A2】正文与表2: reviewed. 表2单位已与正文统一为“题”
- 【A3】正文与表3: reviewed. 60/86=69.8%、26/86=30.2%经核对一致
- 【A4】正文与表4: reviewed.
- 【A5】正文与表5: reviewed. 表5四行与“三处已有对象被覆盖或清空＋一处额外必填参数”的表述经核对一致
- 11月5日-11月11日本周结论与下一步: reviewed.
- 研究思路图汇总 图2（idea_01.png）: reviewed. 仅位图预览，未提供可点击原图 maps/idea_01.svg
- 研究思路图汇总 图3（idea_02.png）: reviewed. 仅位图预览，未提供可点击原图 maps/idea_02.svg
- 全部外部证据文件（S1_all874_coverage.csv、CLE-query-field-audit-20261105.json、semantic_retrieval.py、reference_public_checks.json、S2_four_cases/summary.json、三份 CLE-RPT 说明文档）: not_reviewed. 链接指向本机路径或相对路径，未随稿提供
- 公式: not_reviewed. 稿件未含公式

## Unresolved evidence

【A1】../../CLE-RPT-20261106-S1-three-D-contracts-v01.md 与 S1_all874_coverage.csv 未提供：需核验四类标注的逐题归属、20道冲突题的分项（10/9/1），以及“多种解释”的实际判定记录。
【A2】CLE-query-field-audit-20261105.json 与 semantic_retrieval.py 未提供：需核验转换函数的输出形态（文本或字段字典）、精确匹配的实现位置，以及查询文字的组成。
【A3】CLE-RPT-20261109-zero-api-closeout-v01.md 与 S3/reference_public_checks.json 未提供：需核验每份代码的检查项数、反例判定阈值，以及50份来源材料的抽取与“冻结”记录。
【A4】CLE-RPT-20261106-S4-S5-all-advice-v01.md 与“实际请求核对”记录未提供：需核验10对请求与13组案例的对应关系、5对相同请求的提示与设置，以及逐字比较的实现方式。
【A5】S2_four_cases/summary.json 与候选卡检查记录未提供：需核验增长集54→31→4的筛选记录、12次本地回放日志，以及“已有对象被覆盖或清空”的动作归类。
研究思路图原图 maps/idea_01.svg、maps/idea_02.svg 未提供（仅有PNG预览）：若原图另有文字，需核验其数字与术语与正文一致。
各处证据链接使用本机绝对路径（如 E:/ResearchRuns/CLE/…）或相对上级目录，外部读者无法解析：需提供可访问位置，才能核验任何计数。

## Cross-section questions

三份文档的头部数字彼此一致（874/20/461/130/263；86/60/26；54/31/4），表1、表3、表4、表5的行列与百分比可核算，图1柱值与表1合计一致，图2、图3的编号与本册标题一致。本轮新增的分类规则、A2的匹配规则与“首次分析”定义、表4、表5基本消除了上一版的分母与单位障碍；剩余问题集中在判定标准的可操作性、样本间的衔接和一处跨文档术语。补充材料、逐题表与代码未提供，故本文不判断结论真伪。

# CLE 下一步值得改哪里？｜网页研究材料（截至 2026-11-02）

这份材料同时给出项目拆解、已有实验和待评议的选择。末尾是研究任务。下文的门槛用于决定是否花钱，不等同于证明普遍有效。

## 一、项目有哪些决策环节？

CLE 的目标是让同一份代码同时通过功能和安全测试（Joint）。按以下顺序看，一次失败可能发生在完全不同的位置：

|环节|输入 → 输出|哪个问题仍值得回答|
|---|---|---|
|题目与契约|公开题面、函数接口、给定对象 → 应保持的行为|模板、数据库或配置究竟是题目给定的依赖，还是允许重建的实现细节？|
|经验来源|历史解题记录 → 带原则、反例和修复建议的卡|来源题的建议在哪些新题仍成立？已有卡包含适用条件，单纯增加该字段不构成新机制。|
|检索|题面分析 → 候选卡|text-embedding-3-large 生成向量，程序按余弦相似度比较。候选池能否找到适用卡，与最后是否用好是两个问题。|
|选择与学习|候选顺序 → 模型终选至多三卡|Q按声明采用和整次结果更新。它能改变选卡，但整次结果不能分解为各卡的因果收益。|
|表达与执行|卡片、题面 → 计划 → 首次代码|区分选中、声明采用、落实、改善。计划写了保留外部对象，代码仍可将其覆盖。|
|验证与修复|首次代码、允许展示的错误类别 → 最多一次修复|额外测试必须能从公开契约推出预期值，修复输入不能偷看隐藏断言。|
|评价与投入|同题同重复的运行 → 配对净收益、按族区间与成本|记录救回与损失；两次重复不算两道独立题。换模前后和混合前缀分别统计。|

原设计：303题初始化、273题增长、298题审计；固定旧库1939张。Q四轮学习1122次，覆盖445→610→702→769张卡。开发回测与独立审计分开。v3.2已停用；新库只有2题建库技术探针、5张临时卡，不能比较两座完整卡库。运行层可保存成功响应、离线回放；复算、补充生成和正式付费评价是三种不同工作。

## 二、哪些要求已经有答案？

|问题与来源（按项目登记转述）|证据|当前决策|
|---|---|---|
|老师：Q是否有用？学长：逐轮学习再回测。用户：跨题族是否迁移？|54题五条件两重复，540次生成、535次可测。共同候选中，K3相对相似度在旧/新模型改选42/45、50/59；Joint救回/损失分别5/3、2/3；净变化的题族95%区间分别为−6.67至+15.56、−9.84至+5.17个百分点。K3对K0分别净−1/46、+1/58。|已确认改选。稳定提分未过门；冻结回测不回答独立迁移。|
|老师：拆开功能与安全建议有帮助吗？|第一重复分开写与原卡均125/298；已有486个可测配对救回27、损失32。原卡对无卡484对净多19。|保留原卡作有竞争力的基线。拆分未改善已测配对。2433/2980次已保存，不把余项算失败。|
|老师：按题选记忆详略可训练吗？|82题820次生成、819次可测。五档为无卡、风险提醒、机制与条件、机制加目标模板、机制加来源示例。新模型五档Joint为58/113、58/114、56/114、59/114、59/114。32题完整同模型；训练11题上最佳固定和事后逐题选档均13/22。有效训练标签5族，要求30族。|不发布分类器，不扩大付费评价。|
|老师、学长：检索是否准确？|已登记57题、3758个候选题卡对；11月1日计划记载两题144对先行，33对有效AI标签，人工确认0。此处只引用该记录，不推算其余标签。|还没有据此确认的人工指标；候选池内召回与全库召回分开。|
|用户：来源经验能迁移吗？能限制影响半径吗？|专用来源库M1在保留比较中20/48→28/48，救回9、损失1，题族检验p=0.078125。定点改动3题有2题恢复Joint；边界提醒与对照均8/24，逐对无救回或损失。|来源经验有正向样本，未过0.05确认线。保留定点修复线索；不扩大文字提醒。|
|用户：成本与模型/卡库交叉如何处理？|11月1日两批正式记录合计10078次物理HTTP、67845415个已知Token、58次用量未知；另有独立控制测试。不具备v3.2新调用及完整新库。|优先复用代码与回放。模型覆盖题目不同，两模型总体分差不能解释为换模收益。|

## 三、为什么原先首选的研究方向现在要降级？

前两批各取3个题族、30份已保存交付代码。第一批历史经验独有发现0族；第二批在收据族两份代码发现简单检查遗漏的问题。随后把比较对象换为等预算的强边界和性质测试，并改用首次代码。以下是该轮完整分析正文：
### 范围和反馈

采用273题增长集为分母。取Q回测和记忆标签已保存的代码，按公开契约能否构造本地检查选择任务，两包重复的题优先取Q。82题、72族、820个条件×重复单元进入诊断。两臂所有入选检查均可执行且参考实现通过的交集为65题、57族、591份首次代码。另229个单元有参考分歧、入口或依赖问题等，未计作候选失败。可比题数占65/273（23.8%），可比单元占591/2730（21.6%）。这是回顾性工程样本。编制检查和校准夹具分轮进行，不作为预注册留出确认。

主比较读取attempts[0].code，原生起始结果也取同一次attempt。另对两份历史收据final做定点复验。实际检查156_r1_Q2_K2的9条请求记录，在修复提示中找到上一版代码及Permitted execution feedback，具体为functional fail/plt_test_failed、security pass/null。生成入口另可见题面、先前分析与选卡内容。runner.py的PLT分支先调用原验证器，再传递safe_feedback筛选的状态与错误类别。该记录未向修复提示提供具体隐藏输入、预期值或失败断言。这里使用原生结果作事后裁决。

### 两种方法如何使用相同预算？

每个契约类别共用四个公开输入及判定规则。常规臂取预设的两个边界或性质检查。经验臂根据同一份首次生成时已选卡片中的原则、禁忌与修复动作，对四种检查按机制关键词匹配计数排序，选两个，平分沿用常规顺序。只使用可映射且来源题族不同的卡。每份代码每臂两个检查名额，交集各1182个。执行器在隔离子进程内对四个输入分别重建环境，两臂共用同一输入的执行结果。参考实现用于事后检查判定规则，不作为模型反馈。经验选择在275/591份上改变了检查组合。此比较测量固定菜单内的选择能力，后续研究引用时应保留这一范围。

### 题族结果

| 指标 | 常规 | 经验 |
|---|---:|---:|
| 可比首次代码出现告警 | 32 | 32 |
| 出现告警的题族 | 9 | 9 |
| 仅本臂发现的代码／题族 | 0／0 | 0／0 |
| 告警且首次原生Joint失败 | 28 | 28 |
| 告警且首次原生Joint通过 | 4 | 4 |
| 筛选前至少一个所选断言在参考实现上返回反例的题族 | 11 | 12 |

额外发现的判据是同一代码通过全部常规检查、经验检查却发现契约错误。两臂告警的32份代码完全相同。另有2族在已告警代码上出现不同的失败检查编号，没有计作额外发现的代码或独立缺陷。在57个可比题族中，52族不属于前两批六个设计题所在的族；该部分也没有经验独有告警。

参考实现对照暴露出测试本身的误报风险。表末行按族统计与参考行为分歧，不能将它直接换算为总体误报率；先按参考通过来筛样也不能据以报告零误报。四份原生Joint通过代码上的告警需要依公开契约解释。收据存在替换后再次扫描的错误；HTML模板也出现了替换后搜索残余占位符的路径。XML样本则在代码顶层写入固定模板，检查供给的模板被替换。原生通过本身不足以裁决这些告警为误报。

### 收据和可修复空间

强基线直接把客户姓名设为字面文本{order.total}，同时让原模板包含订单总额占位符，期望结果为{order.total}|37。两份先前报告的最终代码均失败，对应的两份首次代码也均失败。常规臂在该题10份首次代码中告警5份；并非五份均由同一条代码语句导致错误。

对历史定位的两份首次代码仅在内存中去掉替换后的二次扫描，用原验证器复测。K2保持功能失败、安全通过；K3保持功能与安全均通过。该修改在本次诊断中救回0个原生Joint失败。两臂共同标出的28份原生失败是候选空间，其他代码没有逐份试修，不能记为28份可修复。经验独占且可用于验证修复的失败为0。

### 投入决定

经验独有且经确认的新增题族为0，低于3族门槛。诊断补丁带来原生Joint由失败转为通过的已证实题族为0，低于2族门槛。现有结果支持将数据与模板语法分离纳入常规检查，未达到付费探针门槛。模型和Embedding请求均为0。


## 四、可更新哪些环节？先做什么、何时停？

下表是本轮建议，尚无新增实验结果。前三项分别检验实现机制、来源信息和测量有效性；不要把它们捆成一套系统后再比较。

|优先级与候选|最便宜的辨别实验|支持、停止与代价|
|---|---|---|
|1：把题目给定的外部对象保留下来。以结构限制替代一句提醒。|冻结公开契约明确要求复用外部对象的首次代码，纳入原本通过的对照；按族隔离开发和检验。从同一代码起点比较原样、普通静态覆盖检测、只撤销违规重定义的机械补丁。盲于隐藏测试写补丁，最后用原验证器判分。|建议先做零API。至少2个独立族出现原生Joint救回、净救回为正、通过对照无新增损失，才讨论小批；普通检测加相同补丁若已取得全部收益，采用简单方案，撤销复杂方案。三题旧案例只作开发。|
|2：找出来源经验中真正超出公开题面的信息。|以M1的9救回1损失作开发材料；遮去卡片来源，拆成“题面可推出”和“额外先验”。比较同预算的题面规则、真实跨族卡、同主题错配卡。保留题只用于一次确认；先用旧材料核查是否存在可区分预测。|若额外先验无法导出基线遗漏的行为，停止。沿用反例线的付费门：至少3个独有发现族且至少2个独立族经补丁恢复Joint。此前20→28不能单独放行。|
|3：先分清没检索到与检索到未落实。|用已保存候选、终选、计划和代码，按候选位置与有无采用分层抽样；复核者只读公开契约与卡，标适用/不适用/无法判定，再对照是否被选、是否被代码落实。|先交付带分母和未裁决数的漏点表。人工未确认前只作探索；无法重建完整候选时不报召回。该项成本以阅读为主，自身不证明Joint改善。|
|冻结：继续调Q、训练详略分类器、扩大拆分、付费重复历史反例菜单。|保留已有负结果、基线与可复算记录。|恢复条件分别是独立可检验的卡片贡献、足够同来源训练族及选档空间、新的拆分机制、等预算强基线遗漏的独有反例。单纯加样本或换模型不构成新机制。|

## 五、给网页研究端的提示词（可直接复制）

You are reviewing a research project on experience-assisted secure code generation. Your complete project brief is this uploaded document, including its tables and the receipt example. You do not have access to a repository, a prior chat, local paths, hidden tests, or unreported runs. Use the project observations here as supplied evidence. You may independently search public primary literature. Do not present an external finding as a result of this project.

Write a decision memo in English. First explain where the evidence chain breaks between retrieving advice, selecting it, implementing it, detecting a defect, and rescuing native Joint. Use the denominators and model cohorts provided here. Reconcile the positive source-memory result, the earlier receipt finding, and the later equal-budget null result. Explain what each comparison actually identifies. Then compare at most three genuinely distinct updates; you may replace our first choice or recommend stopping. Seek the nearest published alternatives in program repair, property-based testing and secure code generation. Provide verifiable titles and primary-source links, and identify which complete-task baseline could make each proposal unnecessary.

For your top choice specify: falsifiable claim, eligible population, public information at decision time, family-held-out split, same starting code, strongest simple comparator, equal testing and repair budgets, false-alarm adjudication, final native functional/security/Joint measurements, paired gains and losses, and how costs will be counted. Separate a retrospective zero-API screen from any prospective paid evaluation. Give numerical advance and stop gates, distinguish investment gates from statistical evidence, and say which negative result would retire the idea. Explicitly assess whether this can yield a research contribution or only an engineering improvement. End with one recommended next action, its smallest useful artifact, and the evidence that would change your mind. If an answer needs missing information, name the missing observation and explain its effect; the memo must remain usable without opening another project file.

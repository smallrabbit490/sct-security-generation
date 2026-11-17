# CLE 六项研究执行步骤清单

**11月10日02:50状态：E00—E06零API修复、材料审读和验收已完成。原S2及S3全量批的付费批准已经撤回；之后用户另行授权[S3—S5最小固定方案](CLE-PLAN-20261109-minimal-paid-six-questions-v01.md)，累计停止上限2,050万Token。下表原E08—E20保留为原方案记录，未列入本次执行。**

| 本次最小方案 | 完成状态 | 后续 |
| --- | --- | --- |
| S5经验归因 | 96/96个单元，回放及96份代码审阅完成 | 保留结果 |
| S3来源提炼 | 180/180次调用，回放及144份候选审阅完成 | 保留来源候选 |
| S3开发题 | 190/190个单元，回放通过；按开发结果选择G3 | [四处主要差异已读码](CLE-RPT-20261109-S3-development-v01.md) |
| S3确认题 | 96/96个单元，回放通过，11组成败差异已审读 | [确认结果](CLE-RPT-20261110-S3-confirmation-v01.md) |
| S4卡片结构及提示 | 160/160个单元，回放通过，10组成败差异已审读 | [对照结果](CLE-RPT-20261110-S4-consumption-v01.md) |
| S2三个D集选卡 | 原全量批准已撤回 | 不在本次执行范围 |

当前研究判断见[S1—S6零API效力评估](CLE-RPT-20261109-zero-api-efficacy-v01.md)。实际步骤状态和证据路径见[结构化清单](../../configs/cle_weekly_plan_20261105/execution_checklist.json)。

适用范围：11月5日至11日的六项要求与三项补充。依据[合并审查v02](D:/Agent/sct-security-generation/docs/research/CLE-RPT-20261107-weekly-completeness-audit-v02.md)。本次使用CLE实验设计技能，把每项落成入口、输入、操作、产物和验收。

## 1. 固定执行条件

- 仓库：`D:/Agent/sct-security-generation`；新运行根：`E:/ResearchRuns/CLE/20261105_six_questions`。不改旧结果，不重买成功响应，不恢复旧全量和守护。
- 模型固定`deepseek-v4.1-flash`，不带1017；其余单user、thinking disabled、temperature 0、输出/选卡预算、至多三卡、修复次数和原验证器保持各包协议。S5全部只首次生成、无付费修复。
- 工作日北京时间[09:00,12:00)、[14:00,18:00)不新派发模型或Embedding；允许时段才请求，已有请求自然完成。没有新增时段豁免。
- 默认逐包执行，遵守原入口互斥、各包worker设置及总上限4。上限4不等于允许同时开四个包；零API材料与读码可穿插，不新开子Agent。
- 原方案的每个付费步骤均须有对应预算批准且check.ready=true；本次仅有上方S3—S5最小固定方案的单独授权。
- 净收益、显著性和实用门槛只决定结论强弱。所有已固定题、条件、重复和分析都做齐，低收益不减样。

下面保留原方案的完整执行规格；E00—E06的实际验收已有记录，原方案付费命令未执行。统一环境：

```powershell
Set-Location 'D:/Agent/sct-security-generation'
$clePy = 'D:/Agent/sct-security-generation/translation_work/temp/cle_memory_q_env/Scripts/python.exe'
```

## 2. 总步骤表

下表为完整工作分解；E00—E06已完成，E07批准已撤回，其余依赖实测的工作未执行。E22是下一阶段规格工作，不进入本轮付费队列。标为API的步骤需另有有效新批准才可进入。

|步骤|具体工作|执行方式|真实前置|结束时应得到|
|---|---|---|---|---|
|[E00](#E00) 核对当前实例和保留范围|六项研究与三项补充|零API|无|当前起点记录：运行实例、原件可用性、预算是否批准、固定名单和实际完成数|
|[E01](#E01) 修正S5_ACTION正式200格调度|S5_ACTION|零API|E00|修订后的schedule/manifest|
|[E02](#E02) 修订并审读全部撤回材料|S5_ACTION|零API|E00|50例实际产物审阅|
|[E03](#E03) 接齐来源阶段公开恢复入口|S3_source|零API|E00|来源公开恢复入口|
|[E04](#E04) 接齐补充实验的实际读码收尾|S2_INFO/S4_NOCARD/S5_ACTION|零API|E00|可消费case_reviews的补充分析入口|
|[E05](#E05) 用真实输入完成封网验收与工程修订冻结|全部受修改影响入口|零API|E01、E02、E03、E04|针对性封网测试输出|
|[E06](#E06) 补足外部审查所需原件|外部审查交付|零API|E00|54复用与历史匹配原件补交索引|
|[E07](#E07) 逐包核算预算并取得真实授权|十个运行包的分批预算|零API|E05|各包budget_proposal|
|[E08](#E08) 补齐S2的820题筛错|S2_screen 820|API调用|E07|820唯一新单元|
|[E09](#E09) 形成S1全量实测关联并冻结完整W|S1×S2及S2错题名单|零API|E08|S1分类×874实测交叉表|
|[E10](#E10) 完成S3来源五节点提炼|50来源×2重复×5节点=500逻辑调用|API调用|E07|100份来源×重复结果|
|[E11](#E11) 建8个研究池并审读400来源输出槽|S3候选库与来源质量|零API|E10|S3/banks的8个池和400槽|
|[E12](#E12) 完成S2的A/B/C三组两重复|6W个代码单元|API调用＋Codex选卡/分析|E09、E05、E07|6W唯一单元|
|[E13](#E13) 完成S2_INFO信息对齐对照|2W新单元，复用A/B|API调用＋Codex分析|E12、E05、E07|2W新单元及控制绑定|
|[E14](#E14) 完成S3开发M50五组两重复|M50 500单元|API调用＋Codex分析|E11、E05、E07|500单元、回放和分析|
|[E15](#E15) 机械择组并绑定H50真实库|S3开发胜者及留出输入|零API|E14|selection/decision.json|
|[E16](#E16) 完成S3留出H50三组两重复|H50 300单元|API调用＋Codex分析|E15、E07|300单元、回放和分析|
|[E17](#E17) 完成S4结构/提示原三组|H50 P0/P1/P2 300单元|API调用＋Codex分析|E05、E07|300单元|
|[E18](#E18) 完成S4_NOCARD通用提示与交互对照|H50 N0/N2 200新单元|API调用＋Codex分析|E17、E05、E07|200新单元+原控制引用|
|[E19](#E19) 完成S5原E0/E1/E2输入归因|50例29近邻，300首次生成|API调用＋Codex分析|E05、E07|300首次生成与原生回放|
|[E20](#E20) 完成S5_ACTION全卡目标信息撤回|E3/E4 200新首次生成，复用E0 100|API调用＋Codex分析|E19、E05、E07|200新单元及原E0绑定|
|[E21](#E21) 合并六条回答并完成本轮报告|S1—S6收尾|零API分析/写作|E09、E13、E16、E18、E20|六条逐项回答及主张—证据表|
|[E22](#E22) 未来外部规格定案（不进入当前付费队列）|Base/Plus后续批|后续方案|E21|统一外部规格与就绪核查|

**默认付费顺序：**E08筛错820 → E10来源500调用 → E12三组6W → E13信息对齐2W → E14开发500 → E16留出300 → E17结构提示300 → E18无卡200 → E19归因300 → E20全卡撤回200。中间插入各自零API步骤。

表中的前置才是真正依赖；默认排队次序只是便于执行。S3开发不需要等S2_INFO科学结果，S4/S5也不依赖S3是否提分；独立包按各自就绪条件安排，但不得绕过原互斥并开付费包。E06外部补交不阻断本地实验。

### 当前已有结果不再重做

|已完成内容|保留方式|
|---|---|
|S1的874题、2622项分类|分类主体保持完成；E09只增加全量实测交叉表|
|54份当前Flash筛错结果，Joint 23、非Joint 31|原件精确复用，只补缺失820|
|13组历史同卡诊断、39卡视图、32代码、168组建议|作为观察证据，不能记成新模型干预|
|50份原代码验证证据、37个人工变体|旧46加后补4的时间顺序保留；19道失败局部救回不填作新方法成功|

## 3. 零API修复与执行准备（E00—E07）

<a id="E00"></a>
### E00 核对当前实例和保留范围

**前置：**无。**方式：**零API。当前状态：待执行。

1. 核对十个包的execution_index、实际进程树、最新段state/summary、journal/wire和预算；venv父子算同一实例。
2. S1的874题2622项、54份筛错复用、13组历史映射及原诊断结果保留。
3. 只建立本次执行起点记录；不启动旧守护、旧全量或其他课题。

**产物：**当前起点记录：运行实例、原件可用性、预算是否批准、固定名单和实际完成数。

**输入定位：**`D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/execution_plan.json`；`D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/closure_plan.json`。

**产物位置：**`D:/Agent/sct-security-generation/docs/research/CLE-RUN-20261105-six-questions.md`。

**通过条件：**实例与真实文件对应；已有实例不再launch；本轮待执行项不标完成。

**执行要点：**11月9日合并审查记录的新包新增结果为0，不能用这个旧快照代替真正开跑前的再检查。

核对实例可用以下只读命令，再按execution_index追到每包最新段；这里的PID数不能直接当worker数。

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'configs\.cle_weekly_(plan_20261105|closure_20261107)' } |
    Select-Object ProcessId, ParentProcessId, CreationDate
```


<a id="E01"></a>
### E01 修正S5_ACTION正式200格调度

**前置：**E00。**方式：**零API。当前状态：待执行。

1. 在同卷修订目录保存当前schedule、manifest及相关冻结记录；不覆盖旧版。
2. 从各格绑定的冻结病例提取family_id和真实neighbor_block，将arm统一为condition。
3. cell_id、task_id、case_id、条件E3/E4和repeat逐项保持；不改原E0控制。

**产物：**修订后的schedule/manifest；200格身份前后对照；真实输入收集验收。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/inputs/schedule.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/inputs/manifest.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/inputs/schedule.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/inputs/manifest.json`。

**通过条件：**200格、50例、29近邻、两重复；E3/E4各100；缺字段0、arm冲突0；实际200格可进入保存、收集、回放和分析，不靠手工补字段的假清单通过。

**执行要点：**修改prepare生成逻辑并重建尚未启动输入；不能只改现有JSON而保留会复发的生成器。

<a id="E02"></a>
### E02 修订并审读全部撤回材料

**前置：**E00。**方式：**零API。当前状态：待执行。

1. D003保留非法输入返回None：root_cause的[96,295)拟收窄为[96,261)。
2. D026第1、2卡fix_directive均将[0,332)收窄为[149,332)；第1卡[599,818)收窄为[599,732)，第2卡[604,826)收窄为[604,737)，保留协议/IP/IDN前提及独立ValueError约定；其余非目标片段不动。
3. D029处理允许字段过滤、条件更新代码及静默处理的等价动作残留；不能只删关键词。
4. D017已按ZIP建议修订：只撤回两处条件句内的正向HMAC机制子句，保留场景及相反建议；干预范围明确为撤回目标相关正向机制线索。新材料已冻结，尚未生成实验代码。
5. D022及全50例按实际删除语义重新分层；建议、必要限定、解释和独立非目标信息分清，不为保持11/39强行归类。
6. 逐例看原文、实际E3和E4，覆盖144卡全部字段、示例和重复表述；确认非目标约束仍被保留。
7. 实际读完并登记语义结论后，才用既有freeze/verify形成新修订材料。

**产物：**50例实际产物审阅；新材料修订及范围说明；逐例干预分层；原卡与新E3/E4对照。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/materials/`；`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/inputs/manifest.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/material_freeze.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/material_review_summary.csv`。

**通过条件：**原E0、50例名单和两重复不变；既定目标残留处理且非目标信息保留；ID和卡序不变；E4等字符要求通过，不宣称等Token；105/39/388只是ZIP预演；正式数量以新产物重算，不能据此签语义通过。

以下freeze/verify仅在实际材料修订与语义审读完成后执行：

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.review_spans freeze
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.review_spans verify
```

**执行要点：**外部脚本有freeze.unlink()；不直接执行。先将被替代记录保留到同卷历史修订目录，再走现有重建流程。此处仅计划材料修订，不改原生卡E0。

<a id="E03"></a>
### E03 接齐来源阶段公开恢复入口

**前置：**E00。**方式：**零API。当前状态：待执行。

1. 复用SourceExecution的prior/journal能力，在来源控制层接出audit、probe、resume、finish。
2. audit区分已完成、成功前缀、未决请求和错误类型；probe封网停在准确缺失边界。
3. resume只调用缺失节点；finish仅补完整后的回放与收尾，不能重新生成来源节点。
4. 以合成中断验证：成功节点不重付、旧段不覆盖、未知费用累计、已有实例不重复启动。

**产物：**来源公开恢复入口；合成中断验收；工程修订及对应运行器冻结。

**输入定位：**`D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/source_stage.py`；`D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/source_execution.py`。

**产物位置：**`D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/source_recovery.py`；`D:/Agent/sct-security-generation/tests/test_cle_source_recovery_20261109.py`。

**通过条件：**首跑、审计、零API前缀、恢复、完成后只收尾五条路径接通；不绕过未决、认证/额度/预算等实际故障；不通过另开目录或清账绕过。

**执行要点：**原source_stage及其科学冻结保留，公开audit/probe/resume/finish已在独立source_recovery模块实现。audit/probe/finish不派发API；resume受预算与请求状态控制，当前付费批准已撤回，不执行恢复。

<a id="E04"></a>
### E04 接齐补充实验的实际读码收尾

**前置：**E00。**方式：**零API。当前状态：待执行。

1. 复用原S3/S4的case_reviews消费方式：读取实际配对、全部代码和理由，覆盖当前差异队列。
2. S5同时核对E0/E3/E4共300份动作审阅，原E0的100份只引用一次。
3. 把原S5列表格式转换为补充包按cell_id索引格式；保留同一代码、理由、引文和判断，不新造审阅。
4. 完成状态由固定生成数、回放、统计、动作覆盖和真实读码共同决定，不能手改False为True。

**产物：**可消费case_reviews的补充分析入口；E0动作审阅复用映射；准确的待审数与完成状态。

**输入定位：**`D:/Agent/sct-security-generation/configs/cle_weekly_closure_20261107/analysis.py`；`D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/consumption_analysis.py`。

**产物位置：**`D:/Agent/sct-security-generation/configs/cle_weekly_closure_20261107/analysis.py`；`D:/Agent/sct-security-generation/tests/test_cle_closure_supplements.py`。

**通过条件：**三项均验证未审仍待审、代码变化失效、全部实际审完可完成；S5原100控制+补充200均有真实动作判断；未知/无法判断单列，不默认False。

<a id="E05"></a>
### E05 用真实输入完成封网验收与工程修订冻结

**前置：**E01、E02、E03、E04。**方式：**零API。当前状态：待执行。

1. 补充真实200格、材料正负边界、来源恢复、三项分析收尾的针对性测试；使用隔离合成返回且禁网。
2. 测试通过后，按未启动工程修订重建受影响manifest及离线凭据；保留旧版，不手改旧摘要或hash冒充通过。
3. 在任何新H50成绩开放前，确认H50、S3规则、P1/P2及S5干预均冻结；后续不随S2筛错或H50成绩再调规则。
4. 逐包check列出剩余依赖。缺预算或未产生原控制是正常等待，不能删掉这些理由制造ready。

- 补充测试优先落在既有test_cle_closure_supplements.py与来源恢复相关测试；不重跑无关全仓测试。

**产物：**针对性封网测试输出；受影响包新工程凭据；原科学范围保持证明；每包check结果。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/frozen_materials/`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/inputs/`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/offline_checks.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/offline_checks.json`。

**通过条件：**模型与Embedding新增HTTP均0；合成回调不计研究结果；真实200格接口、材料语义审阅、来源恢复和收尾验收全部覆盖；原题号、近邻、条件、重复、Q/卡策略和验证器不变。

以下写入派生材料/离线凭据，须在未启动工程修订就绪后执行：

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage prepare --kind S5_ACTION
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.offline
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage check --kind S5_ACTION
```

**执行要点：**offline会调用prepare并写凭据；必须在未启动修订就绪后运行，不能当作纯只读检查。新增来源恢复测试尚待E03实现后执行。

<a id="E06"></a>
### E06 补足外部审查所需原件

**前置：**E00。**方式：**零API。当前状态：待执行。

1. 先按已存在完整版映射定位54原始行、相关输入和回放、历史匹配索引及统计依赖。
2. 实际交付目录/ZIP中能定位这些原件才标补交完成；完整版清单行数不能代替实际内容。
3. 沿用既有脱敏导出；不含密钥、认证头或.env；只补必要原件，不复制另一套整包大日志。

**产物：**54复用与历史匹配原件补交索引；实际可访问文件清单。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline_manifest.csv`；`D:/Agent/sct-security-generation/results/curated/CLE-weekly-review-integration-20261109.json`。

**产物位置：**`D:/Agent/sct-security-generation/docs/research/deliveries/CLE-W20261105-review-20261107/`。

**通过条件：**外部读者能核验复用资格与统计实现；未交付和本地不存在分开；不重新生成54题，不增加模型/Embedding费用。

**执行要点：**本地54原始行已核对存在、题号/Joint一致且flash_only；这项补交不阻断无关本地计算，可与其他零API准备穿插。

<a id="E07"></a>
### E07 逐包核算预算并取得真实授权

**前置：**E05。**方式：**零API。当前状态：待执行。

1. 先核算S2筛错820和S3来源500节点两个独立批，列原生最大流程、Token/物理HTTP及未知用量预留。
2. 其他包在实际W、来源卡、原控制及修订材料齐备后各自重算和冻结。
3. 只记录用户实际批准的批次和累计上限；历史旧批授权不自动转用。
4. 每个付费步骤前再次check；预算/时段/实例任一不符就不新派发，继续独立零API工作。

**产物：**各包budget_proposal；经用户实际批准后的budget_approval；累计费用记录。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/budget_proposal.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/budget_approval.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/budget_approval.json`。其中后续结果、批准文件和正式周报目录均为计划位置，不表示当前已经存在或获准。

**通过条件：**批次、模型、固定数量及上限对应；未知用量不当0、不重置；有真实批准且check.ready=true才能进入该付费步骤。

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

**执行要点：**这些是现有工程停止上限，不是预计实付或完工保证。本清单不生成任何approved=true记录。

## 4. 固定实验逐包执行（E08—E20）

<a id="E08"></a>
### E08 补齐S2的820题筛错

**前置：**E07。**方式：**API调用。当前状态：待执行。

1. 只执行当前Flash原P7缺失820题；精确复用原54题。
2. 保留每题最多一次修复和原验证器；完成后让原入口自动原生回放、certify并尝试冻结W。
3. 生成已齐但收尾退出时只finish；正常失败保留，技术缺测诊断后复用代码补验。

**产物：**820唯一新单元；screening原生回放与证书；874题筛错汇总。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/analysis/summary.json`。

**通过条件：**54+820身份完整无重复付费；F/S/Joint来自同一份代码；缺测与已测失败分列；不通过重发成功模型响应凑可测数。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.screening_stage check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.screening_stage run
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E09"></a>
### E09 形成S1全量实测关联并冻结完整W

**前置：**E08。**方式：**零API。当前状态：待执行。

1. 用874题原筛错结果与2622项分类分组，生成各D集、各维度/类别的实测关联表。
2. 检查筛错完成与原生回放证书；自动W冻结未完成时先诊断缺测，不拿已知31题冒充完整W。
3. 原入口证据齐后固定wrong_tasks和W；据真实W准备6W的A/B/C矩阵和预算。

**产物：**S1分类×874实测交叉表；wrong_tasks.csv和W冻结记录；S2/manual_evaluation实际6W清单。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S1/task_classification.csv`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline_manifest.csv`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/baseline/execution_index.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S1/screening_cross_table.csv`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/manual_evaluation/wrong_task_freeze.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/wrong_tasks.csv`。其中后续结果、批准文件和正式周报目录均为计划位置，不表示当前已经存在或获准。

**通过条件：**S1分类主体不重做；全量关联C01完成；W覆盖完整已测错题；筛错失败不能填作新A组成绩。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.manual_roster inspect
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.manual_roster check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.manual_stage prepare
```

**执行要点：**screening正常收尾已自动certify/freeze，不机械再做一次。仅其收尾缺失且原记录齐备时补manual_roster certify、freeze。

<a id="E10"></a>
### E10 完成S3来源五节点提炼

**前置：**E07。**方式：**API调用。当前状态：待执行。

1. 核对来源50题、18近邻和冻结来源事件；两个重复独立返回。
2. 按原五节点调用，G0候选由G1/G3共享，G2独立提炼；当前目标GT不进入目标题生成。
3. 来源节点全部结束后由原入口自动零API回放；实际中断使用E03接好的公开恢复链。

**产物：**100份来源×重复结果；500节点journal/wire；source_completion及replay_result。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/source_completion.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/replay_result.json`。

**通过条件：**100个来源重复的五节点齐全；成功前缀不重付；G0已有其原生合法GT信息，不把本实验写成完全无GT对有GT。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.source_stage check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.source_stage run
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E11"></a>
### E11 建8个研究池并审读400来源输出槽

**前置：**E10。**方式：**零API。当前状态：待执行。

1. 只接受完整真实来源与回放，用原归一化/入池流程构建G0—G3各两份研究池。
2. 绑定400个source_slot后，逐槽读真实候选和来源证据，登记事实支持、错误、方向、字段冲突和合法行为遗漏。
3. 原生拒收或空候选按方法真实状态保存；不手修卡、不用哨兵或GT答案造新卡，不仅提炼开发使用的9个来源。

**产物：**S3/banks的8个池和400槽；development/source_binding.json；selection/source_quality_reviews.json。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/source_completion.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/source_distillation/replay_result.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/banks/summary.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/source_binding.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/selection/source_quality_reviews.json`。其中后续结果、批准文件和正式周报目录均为计划位置，不表示当前已经存在或获准。

**通过条件：**50×2×4=400槽，8池身份正确；Q未学习；每个质量判断有实际候选与来源原句；未读不填0。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.candidate_pool check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.candidate_pool build
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.development_stage bind-cards
```

<a id="E12"></a>
### E12 完成S2的A/B/C三组两重复

**前置：**E09、E05、E07。**方式：**API调用＋Codex选卡/分析。当前状态：待执行。

1. 按固定W准备并批准本包预算，核对人工目录与1939卡正文冻结。
2. B仅选原候选池，C选全库；只读公开题面、初析、本臂代码/允许反馈和可见卡，不读目标GT/隐藏测试或另一臂结果。
3. 每次人工选择必须在后续生成前写identity、0—3个有序ID、理由和公开字段依据。
4. 遇ManualSelectionNeeded读取该请求包、补真实decisions后经audit/probe/resume继续；不能自动补空卡，不能将等待计为模型失败。
5. 自动回放和数值分析后读完实际救回/损失，写case_reviews，再运行analysis确认收尾。

**产物：**6W唯一单元；manual_control的请求/决定/采用记录；replay、paired_results、costs、case_reviews和analysis。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S2/manual_evaluation/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/manual_evaluation/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/manual_evaluation/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S2/manual_evaluation/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/manual_evaluation/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S2/manual_evaluation/analysis/summary.json`。

**通过条件：**A/B/C各2W；两重复独立；B−A、C−B按原Holm2；给出救回/损失、实际采用与落实和诊断可达率；不称数学最优上限。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.manual_stage check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.manual_stage run
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.manual_stage analysis
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

**执行要点：**默认付费队列按清单顺序逐包；本步人工决策多，其他独立零API准备和已存案例分析可穿插，不能绕过运行器互斥并开包。

<a id="E13"></a>
### E13 完成S2_INFO信息对齐对照

**前置：**E12、E05、E07。**方式：**API调用＋Codex分析。当前状态：待执行。

1. prepare/bind精确绑定原A/B及共享初析、首次候选；核对完整B信息包长度，超限不截断。
2. 首轮候选ID/顺序与原控制一致；修复轮只用本臂现场和同一信息权限/结构。
3. 批准实际2W预算后执行；复用原控制费用和代码，不重买。
4. 原生回放后填写实际差异审阅，analysis关闭队列。

**产物：**2W新单元及控制绑定；完整信息包检查；回放、Holm2、费用和实际案例分析。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S2_INFO/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S2_INFO/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S2_INFO/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S2_INFO/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S2_INFO/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S2_INFO/analysis/summary.json`。

**通过条件：**A_info−A、B−A_info区分信息与终选空间；没有把人工既有知识也称完全相同；全部2W齐备且读码完成，F3收尾生效。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage prepare --kind S2_INFO
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage bind --kind S2_INFO
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage check --kind S2_INFO
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage run --kind S2_INFO
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage analysis --kind S2_INFO
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E14"></a>
### E14 完成S3开发M50五组两重复

**前置：**E11、E05、E07。**方式：**API调用＋Codex分析。当前状态：待执行。

1. 按实际来源卡和当前原生提示重核本包预算后执行G0—G4。
2. 50题全保留：24共享动作、18局部操作、8预登记空槽；G0—G3的64空槽格独立生成。
3. 回放后报告首轮/最终Joint、救回损失、重复波动、19目标近邻聚类和9来源敏感性。
4. 读所有主要差异的题面、卡、计划、代码、验证，填case_reviews并analysis。

**产物：**500单元、回放和分析；24/18/8分层与9来源敏感性；实际差异审阅。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/analysis/summary.json`。

**通过条件：**缺卡与预登记空槽不混同；空槽差异不归于GT收益；所有固定组/重复完成；主要G2−G1、G3−G1按Holm2。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.development_stage check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.development_stage run
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.development_stage analysis
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E15"></a>
### E15 机械择组并绑定H50真实库

**前置：**E14。**方式：**零API。当前状态：待执行。

1. 核对M500回放和差异审阅齐全，以及E11的400槽质量审阅。
2. 按平均Joint、对G0损失、来源事实错误、同口径成本和既定并列规则选择G1/G2/G3。
3. 未知费用不补0；成本用于决胜且区间重叠时先核对已存用量，不抢用H50结果。
4. 冻结selection/decision后bind留出的真实两重复库。

**产物：**selection/decision.json；H50/effective_protocol与source_binding。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/analysis/summary.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/selection/source_quality_reviews.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/development/selection/decision.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/inputs/effective_protocol.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/source_binding.json`。其中后续结果、批准文件和正式周报目录均为计划位置，不表示当前已经存在或获准。

**通过条件：**选择不使用H50成绩；两重复分别对应真实来源池；开发无收益仍选一组并完整执行H300。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.development_selection freeze
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.development_selection check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.holdout_stage bind
```

<a id="E16"></a>
### E16 完成S3留出H50三组两重复

**前置：**E15、E07。**方式：**API调用＋Codex分析。当前状态：待执行。

1. 按实际G0/GW两套两重复库核算并批准本包预算，再按正常检索执行G0/GW/G4。
2. 两项主比较为GW−G0、GW−G4，按19近邻聚类、Holm2和重复分别判断。
3. 自动原生回放后，补实际差异读码并analysis；不因开发或留出负结果停掉固定条件。

**产物：**300单元、回放和分析；来源合法性—真实供卡—采用—代码—Joint对应；留出结论。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S3/holdout_generation/analysis/summary.json`。

**通过条件：**全部300格完整；无卡文/Q更新；不把固定供卡M50代替正常检索H50；限定为本库规则留出，不称全项目未见盲测或任意来源泛化。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.holdout_stage check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.holdout_stage run
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.holdout_stage analysis
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E17"></a>
### E17 完成S4结构/提示原三组

**前置：**E05、E07。**方式：**API调用＋Codex分析。当前状态：待执行。

1. 核对已冻结P1只调整结构、P2只改原提示，并批准本包预算。
2. 按原P7、旧1939卡Q0、相同重复首次选卡及最多一次修复运行三组。
3. 回放后分析P1−P0、P2−P0、采用/计划/实现和重复波动；填写实际差异审阅并analysis。

**产物：**300单元；P0/P1/P2回放及分析；全部主要救回损失的代码解释。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S4/holdout_generation/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S4/holdout_generation/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S4/holdout_generation/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S4/holdout_generation/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S4/holdout_generation/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S4/holdout_generation/analysis/summary.json`。

**通过条件：**三组两重复完整；结构内容不偷偷纠错；H50不重复计为新50题；两项主要比较Holm2，19近邻区间。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.consumption_stage check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.consumption_stage run
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.consumption_stage analysis
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E18"></a>
### E18 完成S4_NOCARD通用提示与交互对照

**前置：**E17、E05、E07。**方式：**API调用＋Codex分析。当前状态：待执行。

1. bind原P0/P2及对应初析；按实际提示预算批准本包。
2. N0/N2首次和修复始终空卡，保留P7流程；不派发选卡/Embedding，不用P3代替。
3. 回放后比较N2−N0以及(P2−P0)−(N2−N0)，主要Holm2；实际读差异并关闭队列。

**产物：**200新单元+原控制引用；交互/配对/重复统计及读码。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S4_NOCARD/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S4_NOCARD/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S4_NOCARD/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S4_NOCARD/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S4_NOCARD/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S4_NOCARD/analysis/summary.json`。

**通过条件：**控制不重买，两个重复独立，零检索调用；不以P2显著而N2不显著代替直接交互检验。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage bind --kind S4_NOCARD
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage check --kind S4_NOCARD
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage run --kind S4_NOCARD
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage analysis --kind S4_NOCARD
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E19"></a>
### E19 完成S5原E0/E1/E2输入归因

**前置：**E05、E07。**方式：**API调用＋Codex分析。当前状态：待执行。

1. 批准原S5包预算；固定焦点卡和动作，不依据某臂输出再改另一臂输入。
2. E0完整卡、E1去焦点卡、E2去焦点卡内目标动作，各两次首次代码；零付费修复。
3. 逐份审读300代码的目标动作、合法行为和验证，写原S5列表格式action_reviews。
4. 自动原生回放后analysis，动作E0−E1/E2为主要，Joint另列；测量环境异常复用代码补验。

**产物：**300首次生成与原生回放；300动作审阅及差异解释；E0/E1/E2分析。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/S5/generation/analysis/summary.json`。

**通过条件：**所有固定病例/两重复完成；采用ID不当代码落实；50旧原码、37手工变体均不充作新对照；DNS问题不按成绩重发。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.attribution_stage check
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.attribution_stage run
& $clePy -B -X utf8 -m configs.cle_weekly_plan_20261105.attribution_stage analysis
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

<a id="E20"></a>
### E20 完成S5_ACTION全卡目标信息撤回

**前置：**E19、E05、E07。**方式：**API调用＋Codex分析。当前状态：待执行。

1. 确认E01/E02/E05已闭合后bind原E0，按实际修订材料重核并批准预算。
2. 保持50例两重复；E3撤回目标相关信息，E4同范围字符遮蔽；零付费修复。
3. 逐份审读200新代码，按E04格式复用原E0的100份动作审阅，合计300份有效动作证据。
4. 原生回放后分析E0−E3/E4的动作落实、Joint、重复波动、冗余卡与实际语义分层，并写差异解释。

**产物：**200新单元及原E0绑定；补充动作审阅300记录；回放、Holm2及机制分析。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/inputs/manifest.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/budget_proposal.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/budget_approval.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/execution_index.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/replay_result.json`；`E:/ResearchRuns/CLE/20261105_six_questions/closure_20261107/S5_ACTION/analysis/summary.json`。

**通过条件：**E0—E4总共500个不同生成单元；原E0只计一次；E4只等字符，不声称等Token或没有呈现效应；复合材料不称孤立动作因果；目标残留和非目标删改已消除/明确登记，动作与Joint分列。

以下run只在本包批准且check通过后执行；analysis在实际审读文件写入后更新结果。

```powershell
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage bind --kind S5_ACTION
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage check --kind S5_ACTION
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage run --kind S5_ACTION
& $clePy -B -X utf8 -m configs.cle_weekly_closure_20261107.stage analysis --kind S5_ACTION
```

**预算要求：**本包需单独批准；以实际输入和对应budget_proposal为准，不使用旧批剩余额度代替授权。

## 5. 六条回答与未来外部规格（E21—E22）

<a id="E21"></a>
### E21 合并六条回答并完成本轮报告

**前置：**E09、E13、E16、E18、E20。**方式：**零API分析/写作。当前状态：待执行。

1. 逐包确认固定格、原生回放、实测/缺测分母、主要比较、实际读码和物理成本闭合。
2. 分别回答六条：公开信息限制、人工选卡空间、GT新增参与位置、同卡成败/结构提示、卡到代码归因、论文角色。
3. 比较以配对净救回、损失、重复同向、真实聚类区间和预登记Holm为准；0.87个百分点仅临时幅度参考。
4. 根据实际结果更新主张证据表、叙事和任务登记；无收益也可完成研究，未执行不能写失败或无效。
5. 周三11月11日按真实截止生成一页结论、完整思路图册、完整周报的Markdown/Word；没做完则写实际进度及缺口，后续完成再增补，不预填结果。

**产物：**六条逐项回答及主张—证据表；实际结果/成本汇总；当周三种阅读视图；任务闭环记录。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S1/screening_cross_table.csv`；`E:/ResearchRuns/CLE/20261105_six_questions/S6/claim_evidence_table.csv`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S6/claim_evidence_table.csv`；`D:/Agent/sct-security-generation/docs/research/reports/CLE-PKG-20261105-20261111-v01/`。其中后续结果、批准文件和正式周报目录均为计划位置，不表示当前已经存在或获准。

**通过条件：**原固定范围2620+8W代码单元及另500来源调用逐包核对，不重复计算复用；方法提高Joint须由真实对照支持；历史诊断价值单独写；科学结果、执行失败、准备就绪和未来计划分开；旧全量保持跳过。

**执行要点：**若周三尚有未完成项，周报按时交付，但本轮总任务继续标未完成；不能为报告截止删减实验或宣称闭环。

<a id="E22"></a>
### E22 未来外部规格定案（不进入当前付费队列）

**前置：**E21。**方式：**后续方案。当前状态：待执行。

1. 核对原论文Agent真实工作流、任务/模型/预算权限和原镜像watchdog。
2. 在三臂1530和四臂2040中正式定案并统一全部规格；四臂强通用指导仅为推荐候选。
3. 另行冻结外部方法与预算后才申请执行，不能自动新增510或恢复旧队列。

**产物：**统一外部规格与就绪核查；后续独立预算方案。

**输入定位：**`E:/ResearchRuns/CLE/20261105_six_questions/S6/external_protocol.json`；`D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/closure_plan.json`。

**产物位置：**`E:/ResearchRuns/CLE/20261105_six_questions/S6/external_protocol.json`。其中后续结果、批准文件和正式周报目录均为计划位置，不表示当前已经存在或获准。

**通过条件：**当前内部六项完成不依赖未批准外部新跑；外部未执行如实保留，旧Plus生成错误不当0%。

**执行要点：**E22列为下一阶段，排除在本轮必须执行的新增单元与完成门中。

## 6. 预算与审阅文件的具体要求

### 6.1 分批核算，不一次签空白预算

|批次|何时可冻结预算|现有草案，仅作准备参考|
|---|---|---|
|S2筛错820|E05技术验收后|123,000,000 Token；32,800物理HTTP|
|S3来源500调用|E03/E05恢复链验收后|42,000,000 Token；600物理HTTP|
|S2 A/B/C|E09确定W及实际清单后|900,000W Token；240W物理HTTP|
|S2_INFO|原A/B材料、完整候选提示长度及W齐备后|暂拟2,600,000W Token；80W物理HTTP，须实测提示重核|
|S3 M50/H50|真实来源卡及对应实际绑定齐备后|现有75,000,000/45,000,000 Token；4,500/13,000物理HTTP，按真实提示复核|
|S4原对照/无卡|原提示、真实共享初析和控制绑定后|现有45,000,000/376,000,000 Token；13,000/1,680物理HTTP|
|S5原对照/全卡撤回|原材料及修订材料分别就绪后|现有162,000,000/124,000,000 Token；1,200/720物理HTTP，修订后重核|

上述是工程停止上限，不是预计实付、实际Token或完工保证。Embedding已计入物理HTTP总额，不能再次相加。已知、未知和在途分别保留；预算不足停在请求边界，保留前缀后补实际授权，不另开目录重置。

### 6.2 动作审阅格式不能直接混用

|文件|原格式与必需内容|
|---|---|
|原S5 `S5/generation/analysis/action_reviews.json`|列表：cell_id、reviewed_code、action_implemented、reviewer、reason、code_quotes|
|补充S5 `closure_20261107/S5_ACTION/analysis/action_reviews.json`|按cell_id为键：reviewed_attempt_codes、target_action_realized、reviewer、reason、code_quotes|
|两者之间的原E0复用|把同一已读E0记录的reviewed_code转成单元素reviewed_attempt_codes，action_implemented映射到target_action_realized；保留原理由与引文，并核对代码完全相同。不是重新判一次，也不能把列表原样复制成字典|
|实际差异 `analysis/case_reviews.json`|覆盖当前queue中的target/control；有全部实际代码、可定位引文、错误起点、公开依据、对实验目的的影响|
|S3来源质量 `selection/source_quality_reviews.json`|400个source_slot逐一对应真实候选与来源，原合同的证据、计数、错误原句和理由齐备；未读不补0|

这些都是实际阅读后的记录，自动队列、字段标签和采用ID不能代写理由。正常无变化与损益案例分开；S5全部新代码都需动作审阅，不只挑救回例。

## 7. 中断时怎么接续

1. 有活实例就只读检查，不因题数暂时不涨再启动。核对进程树和请求状态，不只看网页worker数。
2. 实例确实退出后，先用该包audit定位错误及未决请求；有成功响应先复用。再probe封网准确停在缺失边界，符合当批恢复授权后resume/launch-resume。
3. 生成已齐但收尾退出，只finish补回放/分析；正常run已自动做过的回放不要机械重复。实际案例审读后再analysis更新完成状态。
4. 公开audit/probe/resume/finish已由独立source_recovery模块实现并完成封网验证；不能对已有来源段再run或换目录绕过。当前批准已撤回，不执行付费resume。
5. 人工选卡等待只补对应decisions，并用原恢复链继续。认证、预算、解析、落盘、材料不一致分别诊断，不能一律当TLS重发。
6. 旧失败、未知执行/费用和累计占用保留。不能因低Joint、未采用或不显著按成绩重跑。

## 8. 什么时候可以勾选“本轮完成”

- [ ] S1完整分类与E09实测关联分别验收；没有把类别占比当模型准确率上限。
- [ ] 原固定及三项补充合计`2620+8W`个新代码单元，另500次来源调用，逐包身份、条件和两重复齐全。旧54、原控制、共享初析和代码变体不重复计数。
- [ ] 每包原生回放、首次/最终F/S/Joint、配对救回/损失、实际近邻聚类、重复波动和原Holm家族齐备；缺测与正常失败分开。
- [ ] 实际来源质量、目标动作和主要差异代码已读，分析能准确登记完成；没有用队列或规则字段代替审读。
- [ ] 费用取物理账本，模型/Embedding和已知/未知分别列出；不累计复用行usage。
- [ ] 六条要求各有明确回答：支持、未支持或尚缺何种证据；零收益可以完成固定探索，但不能宣称方法有效。
- [ ] 报告、叙事和任务登记与真实结果一致；E06外部补交单独登记。未批准的E22外部新跑和旧全量不作为本轮必跑任务。

本文件编制完成不代表上述步骤已执行。机器可读版本为[execution_checklist.json](D:/Agent/sct-security-generation/configs/cle_weekly_plan_20261105/execution_checklist.json)；命令已静态核对现有CLI选项，没有执行运行器、测试或API。

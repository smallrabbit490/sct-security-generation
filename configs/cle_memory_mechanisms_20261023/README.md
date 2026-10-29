# 功能安全记忆与粒度研究：当前可执行准备入口

2026-10-24更新：当前后续模型已切换为`deepseek-v4.1-flash-1017`，仅允许在北京时间周一至周五09:00–12:00、14:00–18:00以外派发请求，周末全天允许。当前B/C及共享准备使用新模型与新输出名，旧v3.2产物保留；下文旧运行记录不能作为新模型共享起点。所有正式执行仍暂停，详见`docs/cle_memory_mechanisms_20261023/23_切换v41Flash1017与调用时段限制.md`。

当前完成零模型API批次，协议为 `cle-memory-mechanisms-preparation-v1`，数据修订为 `cle-memory-mechanisms-data-contract-v2`。任务书见 `docs/cle_memory_mechanisms_20261023/README.md`，最新执行情况见同目录 `06_首批执行结果.md`。

## 当前文件与运行位置

- `manifest.json`：已经锁定D_grow 36训练+12开发、D_gate粒度确认24+Q确认24；前12题先导、前2题技术探针。所有组family不交叉，D_gate排除旧契约48族。
- `prepare.py`：锁名单、914对盲审导出、1939卡来源索引和v1参考预检。`prepare`与`export-review`已执行，不覆盖既有名单/人审。
- `repair_preflight_v2.py`：本次已执行，保留v1，恢复6题URL夹具、修订2份离线参考、补公开依赖并复检96题。重复运行需新版本/新输出；不得覆盖既有v2。
- `analyze_history.py`：读取历史L1和Q2原生记录，输出303题配对、38差异代码证据、265同成绩对照和902次Q更新影子统计。可在输入未变化时复用已有输出，无须重复运行。

本机运行区入口：`D:/Agent/sct-security-generation/translation_work/diagnostics/20261023/cle_memory_mechanisms_v1`。

该入口为junction，实际记录在 `E:/ResearchRuns/CLE/diagnostics/20261023/cle_memory_mechanisms_v1`。D盘开始时仅余约187MB，本次未搬移/删除旧数据。换机器时先在有空间的磁盘设置新运行目录，不复制本机链接当数据。

## 复现命令

在一个新的空输出位置进行准备；下列命令显示已执行的动作，当前已有输出时不会静默覆盖。

```powershell
$clePython = 'D:/Agent/sct-security-generation/translation_work/temp/cle_memory_q_env/Scripts/python.exe'
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.prepare prepare
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.prepare export-review
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.prepare preflight
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.repair_preflight_v2
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.analyze_history
```

修订版必须为所有未来臂一致提供 `C:/Program Files/Git/usr/bin` 中已安装的echo/cat工具。仅新进程PATH前置，不修改系统PATH、不安装软件、不改原验证器。

## 下一步门槛

1. v2参考96/96、依赖名称检查96/96已通过；这不等于公开语义契约已完整。1348的资源限制数值/政策等仍需确认，不能从隐藏测试或目标参考中摘值放进提示。
2. B01视图接点及两题原P7编排已实现；v1真实探针出现格式/API故障后停止。先验证统一本地适配，再按新版本推进，不覆盖旧记录。
3. 功能/安全视图需要原事实一致性审核，BFS不得额外获得答案或约束。准备妥当再推进有界生成。
4. 检索正式四指标另受人工标签门限制：914对人审0，正式指标不能出表；该门不能被程序预检代签。
5. Notion原件仍待定位/接收。它不阻断本机零API工作，但无法据网页表复现全部5817对。

## B01已实现的离线入口

```powershell
& $clePython -B -X utf8 -m methods.cle_ablation.memory_view_study prepare-views
& $clePython -B -X utf8 -m methods.cle_ablation.memory_view_study offline-probe
```

这两项已执行，输出在运行区`B01/`。339张历史候选卡已导出为来源和待审片段；随后六张历史首选卡完成了来源内容分区。草稿并非339张卡已审完。正式实验先取得共同选择，再审核实际入选卡，不能为填表默认把所有pending改成reviewed。

视图只引用原卡的字符片段，BF/BS共用适用上下文，BFS完整保留正文事实。两题五条件离线控制验证使用目标参考作为合成回复，全部标记`not_an_experiment_score`，不抵扣两题真实探针或120次真实P7预算。

## B04已有代码的足迹回放

```powershell
& $clePython -B -X utf8 -m methods.cle_ablation.memory_footprint
```

已执行，当前v3输出在运行区`footprint_replay/`。它测量历史L1/Q2两份有记忆代码，不是Notion的无记忆/有记忆配对；不能用其结果判包B4推进门。最初把显式导入也算作重定义的版本保留在`footprint_replay_v1_included_imports/`；v2将导入单列，保留在`footprint_replay_v2_imports_separated/`；v3补上类型声明、自引用赋值和明确的globals读取。没有校准阈值、没有启用Q路由。

## B02两题共享初析/选卡：已经完成，勿重跑

实际入口为`prepare_real_probe.py`，范围仅1394/102各2次首次初析与原CLE选择器；不含代码生成。4份共享起点在运行区`B02_shared_starts/`，`review_fresh_start_views.py`已审查实际两张入选卡，输出`reviewed_views.json`。历史卡审查脚本是`review_probe_cards.py`。

累计10次LLM逻辑调用及2次Embedding，已知Token分别182040与1191；102两重复的原选择器恢复成本包含在内。不能把这些前缀称为完整真实P7或新的Joint成绩。共享准备已完成，配置关闭重复启动开关；旧D02、D_grow和全量D_gate仍暂停。

## B02原P7两题技术探针

入口已实现；原v1实例位于`B02_two_task_P7_v1/`，已终止为技术故障，不能按旧PID描述为运行中。同名输出已存在时拒绝重复启动。当前增加中转适配后，84项相关离线检查通过，不代表全仓库测试通过。

```powershell
# 默认只展示规格，零API
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_view_probe
# 仅在当前两题配置启用且输出尚不存在时启动；已启动后不重复运行此命令
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_view_probe --run
# 只读原生结果并更新分析表，不重新调用模型
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.analyze_view_probe
```

两题×五条件×两重复上限20次P7、40份代码，计入B02原120次；本阶段保守上限700 HTTP、120 Embedding HTTP、1600万Token，不将预留当实付。首次复用已完成共享起点，修复重新检索；新卡在`pending_views/`等待来源内容分区，审核写入运行区`reviewed_views.json`时采用临时文件原子替换，避免正在等待的进程读到半份JSON。审核不是人工适用性标签。

技术故障按原P7保留本题完整轨迹，随后停止后续条件，不覆盖失败重跑。正常F/S失败仍是有效观察。运行状态、请求终态和费用均保留；原P7内部可能在某结构化请求失败后继续生成，故即使最终代码有分数，也不能绕过本方案的零流程错误技术门。

## 中转不能修改时的本地适配

用户要求适应ChatAnywhere。v2单次180秒非流式计算仍超时，第二个控制未发；v3流式计算通过、加法函数被误拒绝；v4纯任务数据格式只返回自我介绍。原件分别保存在`B02_provider_adaptation_v2/`、`B02_provider_adaptation_v3_stream/`、`B02_provider_task_data_control_v4/`。流式socket180秒/总300秒；选择器原120秒截止不改。代码控制未过，v2/v3 P7都未启动，配置继续禁用；不自动追加同类诊断。

只有控制均通过且配置明确启用时，才可执行下列两题入口；它不会恢复旧学习、全D_gate或D02。

```powershell
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_view_probe --provider-adaptation --stream
# 首次启动后禁止重复运行--run；读取metadata与请求终态继续人工处理
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_view_probe --provider-adaptation --stream --run
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.analyze_view_probe --run-name B02_two_task_P7_v3_stream
```

分析/规划只合并完整、相邻且顶层字段互斥的JSON对象；有重复键、额外文字或截断时不合并。原响应、归一化响应及动作分别保存，生成代码不修补。四份共享前缀和同实验格完全相同提示词的已返回正文可以复用；后续提示改变则不能复用旧代码。所有旧故障、控制和新请求共同占原700 HTTP/1600万保守Token上限，不把未知费用当免费。

## D01与C01零API接续：已执行

`review_q_credit.py`关联326题/503次尝试与902次有效更新，当前派生结果在`q_credit_review_v2/`，v1保留；同族反馈、跨族方向、重复代码及6个公开绑定执行均单列。输入Q覆盖926张、当前972张，新增46张。

`prepare_granularity_sources.py`沿原英文池manifest定位`E:/ResearchArchives/.../原始项目/translation_work/sct_runs/cle_context_874_20260923/`；1939卡均匹配原ID与来源身份。`C01_source_reconciliation_v1/`分别保存303题真实来源轨迹、246标准修复种子及索引。没有把来源参考代码冒称产生每张卡的实际尝试，也未将失败来源包装为正确范例。

```powershell
# 本机已有完整派生输出；以下用于新空输出位置重建，拒绝覆盖旧结果
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.review_q_credit
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.prepare_granularity_sources
```

这两项不调用模型、Embedding，不改变Q或正式成绩；完成的是来源与归因阶段，五档后续进展见下一节。10项新增聚焦检查通过，说明分母关联和来源规则，不构成效果证明。

## C01五档呈现：已完成两卡离线准备

`prepare_granularity_views.py`导出2张真实首选卡的L1摘录规范和2个公开L3绑定；其他卡没有自动标为已审。`memory_granularity_study.py`提供`GranularityProvider/run_one_level`及preview命令；当前CLI不创建网络客户端、没有付费或分类器训练子命令。

```powershell
# 本机已完成；在新空输出位置复现，已有输出拒绝覆盖
& $clePython -B -X utf8 -m configs.cle_memory_mechanisms_20261023.prepare_granularity_views
& $clePython -B -X utf8 -m methods.cle_ablation.memory_granularity_study preview
```

材料在`C01_granularity_materials_v1/`，20份预览在`C01_granularity_preview_v2/`；首版免费schema故障记录留在v1。15项新增离线检查通过，证明原P7修复保持档位、材料缺失后的停止边界等。来源可用性另由`audit_granularity_source_availability.py`核对：553个代码位置只有546非空，15张非种子卡缺L4代码；逐卡表在`C01_source_availability_v1/`。预览不是实验成绩，新卡材料、C02编排/预算及统计仍待完成，代码接口控制未过不恢复付费。

## C02离线排程和C1：已执行

```powershell
python -m methods.cle_ablation.memory_granularity_study plan
python -m methods.cle_ablation.memory_granularity_study summarize --rows <C02原生rows.jsonl> --cell-costs <完整逐格成本.jsonl> --out <新输出目录>
```

第一条已经生成`C02_offline_plan_v1/`，不要覆盖重跑。第二条是后续真实结果的离线入口，不发送API请求。固定协议在`granularity_protocol.json`；480格中先导120格、技术20格包含在内。当前真实行0，C1未评估；结果缺测与技术失败不算科学失败。逐格输入成本未齐，不导出首选档。新增14项检查通过；真实付费编排/预算与完整材料仍待完成，详见13报告。

## A04历史18损失：已执行

`review_historical_losses.py`读取原生保存代码/采用、公开题面和Q事件，新增30次本地检查、复用6次旧检查；既有`historical_loss_review_v1/`拒绝覆盖，不需要重跑。18份case/逐题CSV与`new_public_diagnostics.json`保存具体证据，3条`obligation_paths.json`中907为跳过Q而非负奖。

初始`summary.json`保留；`summary_v2.json`加入297对可测敏感性与Q路径，另有`public_contract_comparison.json`核对18题保存描述一致。4项新增与6项既有Q检查共10项通过。API/Q更新0，未改旧正式成绩，尚未对全部20救回及265同成绩题完成实现审查。见14报告。

## A04历史20救回：已完成对称复核

`review_historical_rescues.py`读取同一历史对照，保存20份case、逐轮实际采用和Q事件。新增43次公开/条件诊断，另1次1174定点检查确认旧`isinstance`集合参数错误；不重跑模型，不改旧分数。已有`historical_rescue_review_v1/`拒绝覆盖。

`summary.json`保留首批43次，`summary_v2.json`加入定位检查和解释修订；4条`obligation_paths.json`对应实际正奖。20题保存描述全部一致，但非Q单因素实验。4项新程序检查与10项既有检查共14项通过。38个成绩改变题已有限复核，265同成绩题仍待必要的对照复核。详见15报告。

## A04同成绩参照：固定9+6已执行

名单先保存在`same_score_review_manifest.json`。`review_same_score_controls.py`复核9道标记失败题和6道按元数据固定的无标记通过题，新增44次本地检查；5项新计算检查与8项既有检查共13项通过。原输出`same_score_control_review_v1/`拒绝覆盖。

完整265道同成绩记录复算组件：145道失败中141道可测，有13道F/S变化；120道通过的粗组件相同，105的细行为仍改变。当前`current_case_review_index.csv`共303行，53道有限证据、250道未知；不根据有目的参照计算检测准确率，不训练新门控。API/Q更新0，详见16报告。

## 当前执行门核对：已完成，服务阻塞

`execution_gate_review_v1/summary.json`与精简`execution_gate_review.json`保存分包依赖。新增2项离线检查证明四个公开控制提示在两种传输下均只组装原样单条用户消息，未调用真实API或读取凭据；它不替代真实代码控制。当前所有付费标志关闭，v1终态保留，B合格配对0、C真实运行0。

接续先解决同模型代码控制，再恢复原两题技术范围；1348仅阻塞完整12题的合格解释，人审和Notion原件分别阻塞正式四指标/原生足迹回放。C请求成本编排和独立预算仍待技术就绪与消费者冻结后完成。详见`docs/cle_memory_mechanisms_20261023/17_执行门核对与阻塞交接.md`，不自动追加付费控制或历史案例。

## C02分阶段入口与成本接续：10月24日已实现

```powershell
# 当前只检查规格和门槛，不创建API客户端
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_granularity
```

`granularity_execution.py`实现20/120/480格原P7阶段、费用与精确请求回放；材料缺失后接续不重复首次解题/修复选卡，扩大阶段不清零旧费用，C1未过不扩展。入口受`granularity_protocol.json`各阶段的独立累计预算、消费者冻结和服务控制限制，当前全部关闭；`--run`无法绕过。最终85项相关离线检查通过（30项新增），证据在`C02_execution_core_offline_20261024/`，真实C结果0。用`--phase pilot/expansion`可只读检查后两阶段，详见18报告。

## 官方org接入点控制：已终止

官方双接入点说明提供新排查依据。`probe_official_org.py`最多两次单HTTP、先代码成功后再计算，继承v4费用及原B上限；此次首请求HTTP403，第二次未发。`B02_provider_org_control_v5/`保留终态，配置开关关闭，同名目录拒绝覆盖。不自动重试，不据此启动P7；累计未知用量7、已知Token196291。详见19报告。

## 新模型单次加法监控：已设定，等待执行

`probe_v41_flash_1017_once.py`由监控 `cle-2` 每15分钟检查后，在北京时间允许时段执行一次。保持原CLE单user消息、同一密钥、新模型及修正客户端标识；一次HTTP、不重试，已有输出不重发。43项相关离线检查通过，当前没有新模型真实调用；正式实验继续暂停。执行、结果和停止规则见24任务文档。

# 本周全量验证执行入口

本次授权：用户2026-10-27要求补齐本周待做清单，更新自动化在允许时段执行，实验后继续分析。当前依据为[待做清单](../../docs/research/CLE-TODO-20261022-20261028-v01.md)和[七项要求方案](../../docs/research/CLE-PLAN-20261027-seven-requirements-v01.md)。

`execution_plan.json`登记各包状态。F0已完成874题名单、family隔离、修订题面和参考执行复核；已实现并离线验证FQ_LEARN入口。其余包的编排和预算仍需逐包落实，不能把首包技术就绪写成全部接线完成。自动化应继续实际实施，不反复生成新规划或等待逐包批准。

2026-10-27复核：D_init参考实现303/303通过，303题奖励合格；D_grow参考268/273通过，232题奖励合格、41题不授予Q反馈。D_gate初检261/298，随后在独立v3修订中恢复原测试、补依赖并校准两题参考，参考及名称检查均298/298通过，原初检完整保留。学习输入不改；后续D_gate应锁定E盘`FQ_GATE/inputs_v3/tasks.json`并登记新评价协议。详见[评价契约操作说明](../cle_weekly_gate_20261027/README.md)。参考执行通过不代表公开契约一定完整。

## 当前可运行入口

**2026-10-27 15时更新：** 用户已明确授权直接补发题437缺失的修复选卡请求，不再等待服务端账号或对账。当前恢复入口改用[专项恢复说明](../cle_weekly_recovery_20261027/README.md)中的`configs.cle_weekly_recovery_20261027.recover launch`。63题及437的六段成功响应复用，旧失败及未知用量保留；18:00后按原学习规则接续。学习1个worker可与FFS的`launch --workers 3`并行，总数不超过4；不得同时另起完整4worker评价包。

在项目根目录使用`translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_full_20261027.learn launch`启动学习包。入口启动隐藏进程，单worker依次运行D_init K0及D_grow K1/K2/K3，合计1122题次；每次P7完成后才依c0/c1顺序更新实际采用卡，题内Q不变。前2题包含在全量中，Joint不作为继续门槛。运行已存在时仅跟进，不启动第二实例。

每段产物在运行根`FQ_LEARN/K0/segment_001`等目录，原生结构位于`task_rows`/`rows.jsonl`，逐请求位于`journals`/`wire`，冻结库位于`FQ_LEARN/frozen/K0.jsonl`等。完整代码快照在各段`source_bundle`。根`execution_index.json`列出所有段；`supervisor_state.json`、各段`state.json`、实际进程共同判断状态。

完成一轮后零API回放命令为`python -B -X utf8 -m configs.cle_weekly_full_20261027.learn replay --stage K0`（替换K0/K1/K2/K3），已存在回放结果直接复用。确认中断后先检查未决请求，只有完成响应可准确复用、源代码和输入未变时才用`learn resume --stage K0`新增恢复段。不能直接改state重启或重发未决HTTP。修订运行源码时，须先核对差异与保存响应并明确记录恢复规则。

离线23项验证涵盖原P7早停/一次修复、最多三卡、实际采用后信用、题内冻结/逐题更新、不合格题继续执行但不计Q、完整响应回放、完成前缀恢复、异常停止、时段和累计预算。证据在运行根`preflight/offline_checks.json`。学习包四段预算固定为168300000 Token、44880次总HTTP，其中Embedding最多17952次；这是累计技术上界，非预计实付费用。其余包不能占用此预算。

## 冻结回测与阶段分析接线

FQ_RETEST已在独立目录[cle_weekly_eval_20261027](../cle_weekly_eval_20261027/README.md)实现，实际输入为E盘`FQ_RETEST/inputs`，固定2730格。`python -B -X utf8 -m configs.cle_weekly_eval_20261027.retest check`核对依赖；学习四段完整完成、各段原生回放及分析完成后，在允许时段运行同模块`launch`。最多四组并行，每组五条件串行，共享首次初析，两重复独立。共同候选、冻结输入及续段复用的离线演练通过；收益门不阻止固定全量。当前真实回测未派发，不把接线通过算成2730格完成。

每完成K0/K1/K2/K3立即运行`python -B -X utf8 -m configs.cle_weekly_analysis_20261027.analysis analysis --stage K0`（替换阶段），产物在E盘`analysis/K0`等。完整前可作partial快照；完整后继续实际读取`case_review_queue.json`中的题面、卡、计划、代码和验证，再填写落实与原因。不能把该入口生成的待审队列当作已完成代码分析。

回测分析命令为`python -B -X utf8 -m configs.cle_weekly_analysis_20261027.retest_analysis`，读取实际保存行，输出F/S/Joint、救回/损失、按真实family聚类的区间与置换检验、重复波动、选卡编号和新增采用、累计成本。尚无真实行时只输出not_started。17项相关测试覆盖合成20格全流程和手算分析，未调用付费API；原生时段/预算测试仍由既有执行层承担。

固定运行根：`E:/ResearchRuns/CLE/20261027_full_requirements/`；代码和小摘要在原项目。每包原生rows、attempts、generation、validation、retrieval_trace和journal/wire独立保存，不能写入已完成的20261026运行区。

优先复用原入口：`methods/cle_ablation/runner.py`、`run_memory_q.py`、`run_memory_q_online.py`、`run_memory_view_probe.py`、`memory_granularity_study.py`、`run_memory_granularity.py`、`retrieval_q_study.py`及`methods/sct_trajectory/run_closed_loop.py`。历史入口的默认模型、旧路径、Q初态和恢复行为须改为本轮明确参数，不能直接执行旧配置。

F0产出实际`protocol.json`、`manifest.json`、`reuse_manifest.json`、`budget.json`、离线验证结果及新执行命令后，再将对应状态记为ready。各包技术上界依据既有逐请求Token分布和最大尝试数锁定；金额无当前依据时不编造。完整固定条件为授权范围，未使用预算不能挪去追加可选实验。

工作日[09:00,12:00)、[14:00,18:00)禁止新模型/Embedding请求，其余时段与周末允许，时区Asia/Shanghai。在每个实际请求边界等待，不能只在进程启动检查。学习单worker、逐题顺序更新；冻结评价不超过4workers。按预定清单完整运行，收益门只解释，不取消全量。

先检查实际进程与包状态，避免重复实例；恢复累计预算、旧请求和未知用量，不重置。故障修复后继续已保存前缀；未决HTTP不能盲目重发。阶段完成后核验、实际读代码分析，再进入下一包；任何awaiting_agent_analysis均是当前Agent待办，不是等用户批准。

原cle监控保持暂停，已完成基础1376代码单元/160选卡单元不恢复；原周三周报保留。原镜像、v3.2接入和人工标签只阻塞依赖它们的任务。禁止替换验证器、代签人审、读出凭据、提交推送和发邮件。

## 独立功能安全全量包

FFS已在[独立目录](../cle_weekly_fs_20261027/README.md)实现，固定v3全298题×五条件×两重复＝2980格，并提供原生回放、四象限配对分析及来源材料费用拆分。36项相关组合离线验证通过，当前真实0格。`configs.cle_weekly_fs_20261027.evaluate check`检查就绪；允许时段用同模块`launch`。它不依赖学习K3，题437的服务端核对只阻塞Q链。原学习输入及未决请求保持原样，禁用时段内不新发任何付费请求。

## 五档标签与检索准备

[FG_LABELS](../cle_weekly_granularity_20261027/README.md)已完成全273题五档两重复接线，使用[独立D_grow契约v2](../cle_weekly_contracts_20261027/README.md)，参考273/273通过。独立预算737100000 Token、135408总HTTP（含Embedding43680），真实0/2730；原学习的冻结输入及232题反馈资格不改。`evaluate check`后按全局最多4worker排队，FFS有活worker时不另起4worker包。完整后先`evaluate replay`，再`configs.cle_weekly_analysis_20261027.granularity_analysis analysis`及`train`；真实标签和原生回放不完整时不训练。

[FR](../cle_weekly_retrieval_20261027/README.md)只完成571题零API收集及匿名材料入口，现复用129份初析、缺248段查询向量，完整池0。付费补向量与AI盲标执行层尚待接线，不能直接写成就绪或已完成标签；人审始终独立。最新组合56项及随后4项标签/训练检查通过，没有新付费请求。分类器D_gate、新库和交叉入口继续落实，不能只反复监控已就绪的小包。

15时后补充：FR独立付费层及有限预算现已核验，`configs.cle_weekly_retrieval_20261027.execute check/launch`负责按时段和全局容量排队，原`prepare.py`仍为零API。25项检索与三策略组合测试通过；真实完整池和AI/人工标签均0。[FG_GATE](../cle_weekly_granularity_gate_20261027/README.md)三策略及`policy_gate_analysis`也已接线，仍须完整五档、回放与新模型后才运行。学习恢复1与FFS3优先占用全局4个槽；FR不在这期间额外叠加。

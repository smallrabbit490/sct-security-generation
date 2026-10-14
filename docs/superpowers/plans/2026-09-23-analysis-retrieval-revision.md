# Analysis-driven retrieval implementation plan

用户已批准修改、非小样本对照、874 条完整训练及 Plus 全量复测。

Goal: 接通初步分析、检索、经验结合后的再分析和失败反馈，核验实际改善而不预设涨分。

Architecture: 保留当前源码快照作为对照；新版流水线提供检索 callback，分析后调用，再进行经验适配分析。内部测试是独立证据通道，不读取官方隐藏测试。训练阶段可用 PLT 训练证据，Plus 的官方反馈沿用脱敏状态协议。门控判据不改。

Tech stack: Python, pytest, 现有 ChatAnywhere requester、PLT 本地子进程、Plus 常驻 Docker 与 watchdog。

- [x] 保存改动前流水线快照到 translation_work/diagnostics/20260923/pipeline_revision/before；基线 29 测试通过。
- [x] 卡片与检索：kind/适用范围保真，完整查询，API/source/sink 匹配；先增实际边界回归测试再实现。
- [x] 流水线：初步分析 → callback 检索 → 结合经验再次分析 → Planning → CodeGen；可审计阶段与条件化 prompt；新旧模式可比较。
- [x] 内部测试模块：只接任务及威胁分析、生成和语义审查、自包含执行证据、本地/Docker既有后端。
- [x] 训练入口与 Plus runner 集成，新增 memory 参数；训练 rollout/最终评测/门控生成使用一致流水线。
- [ ] 训练侧对照：固定旧 M*，使用 audit 开发任务全量 298 条（它曾参与门控，明确不是独立测试），至少旧版/修复 prompt/分析驱动完整版三个臂，模型 v3.2、统一输出预算、按题配对，报告不确定性和成本。不得用 Plus 选 prompt。
- [ ] 回归及小规模真实链路检查；不对失败结果挑题或改分母。
- [ ] 新目录全量 874 条训练，原三池/三轮/门控预算，hier_llm，显式失败反馈，生成新 M*；记录新调用预算与旧版差异。
- [ ] 新 M* 上 Plus 140 双臂，先正向校准与 watchdog smoke，再 watchdog 全量；全部候选、代码、使用量、源码与数据哈希保留。
- [ ] 中文实验报告与 README 导航，区分已有证据、诊断观察与独立测试结论。

工作区包含用户大量未提交变更，使用文件级快照与新运行目录隔离，不进行重置或自动提交。先评测当前已授权修改；无法保证显著提升时如实报告，仍完成用户要求的训练与 Plus 运行。

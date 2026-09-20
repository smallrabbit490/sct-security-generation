# SCT 安全代码生成实验仓库

本仓库用于复现“安全经验自进化 + 多语言安全代码生成”实验。推荐按下面的顺序阅读和执行，像阅读一本实验手册一样逐层深入。

## 目录：从入口到细节

1. **先了解项目**
   - [数据集说明](data/DATASET_CARD.md)：数据组成、数量、来源和限制。
   - [外部数据来源](docs/external_dataset_provenance.md)：经验提取所用外部数据及许可说明。
   - [当前限制](docs/limitations.md)：哪些语言和实验仍未完全冻结。
2. **再理解评测规则**
   - [评测协议](docs/evaluation_protocol.md)：Function、Secure、Function+Secure 指标和数据隔离要求。
   - [Baseline 忠实性说明](docs/baseline_fidelity.md)：四条 Prompt baseline 与五条 Agent baseline 的区别、阶段和判定标准。
   - [Baseline 执行审计](docs/baseline_execution_audit.md)：当前真实运行证据和已知阻断点。
3. **然后配置环境**
   - [复现实验指南](docs/reproduction_guide.md)：从安装到单任务 smoke test 的完整顺序。
   - [ChatAnywhere 配置](docs/chatanywhere-api.md)：本地 key、模型检查和脱敏输出位置。
   - [配置文件说明](configs/README.md)：哪些配置可以进入仓库。
4. **最后阅读方法差异与实现**
   - [经验自进化操作指南](docs/experience_self_evolution_guide.md)：从 PLT 分区、R0/R1 门控到冻结和 Base/Plus 评测的逐步操作、JSON/JSONL 格式与真实示例。
   - [PLT 自进化实验说明](docs/plt_self_evolution.md)：PLT 训练侧分区、Seed family 和运行入口。
   - [SCT 统一核心设计](docs/superpowers/specs/2026-09-09-sct-unified-core-design.md)：方案 B 的模块边界、数据流、冻结协议和验收标准。
   - [SCT 统一核心实施计划](docs/superpowers/plans/2026-09-09-sct-unified-core.md)：按测试先行拆分的实现任务和检查命令。
   - [SCT 与 DOCX 差异审计](docs/sct_docx_gap_analysis.md)：当前实现与方法文档逐项对照。
   - [生命周期回放运行记录与优化](docs/sct_lifecycle_replay_run_20260913.md)：2026-09-13 全量 PLT 运行结果，以及门控过严、检索无效经验两大问题的诊断与优化。
   - [组会五点问题排查与规划](docs/sct_lifecycle_replay_meeting_plan_20260914.md)：错题本、三池错误率、PLT 测试覆盖、重放迭代、经验分层五点的结论与方案。
   - [论文修改方案总索引](简介论文修改方案/README.md)：组会需求编号、文献启发、候选自进化结构和修改状态的统一索引。
   - [原始方法文档](docs/面向多语言安全代码生成的经验自进化方法.docx)：本项目的规范依据。
   - [重构方法设计说明](简介论文修改方案/重构方法设计说明.docx)：新方法（安全经验生命周期 + 验证驱动主动回放）的设计规范，`methods/sct_lifecycle_replay/` 的实现依据。
   - [实验运行区说明](docs/translation_work.md)：运行结果、缓存、诊断和临时文件的分类与清理规则。

## 项目文件总索引

下面按目录列出仓库内全部应索引文件（不含 `translation_work/`、`local_secrets/`、`__pycache__/` 等运行区与密钥）。点击文件名即可跳转。

### 根目录

| 文件 | 说明 |
|---|---|
| [README.md](README.md) | 本文件：唯一总导航 |
| [AGENTS.md](AGENTS.md) | 仓库协作与产物管理规范（目录职责、命名、清理、禁项） |
| [requirements.txt](requirements.txt) | Python 依赖（openai） |
| [.env.example](.env.example) | 环境变量示例（真实 key 放 `.env.local`） |
| [LICENSE](LICENSE) | MIT 许可 |
| [CITATION.cff](CITATION.cff) | 引用信息 |

### docs/（协议、审计、复现、数据说明）

| 文件 | 说明 |
|---|---|
| [面向多语言安全代码生成的经验自进化方法.docx](docs/面向多语言安全代码生成的经验自进化方法.docx) | 原始方法规范（DOCX） |
| [evaluation_protocol.md](docs/evaluation_protocol.md) | 评测协议：指标定义、数据隔离、SCT 轮次 |
| [baseline_fidelity.md](docs/baseline_fidelity.md) | 九条 baseline 的忠实性定义 |
| [baseline_execution_audit.md](docs/baseline_execution_audit.md) | 九条 baseline 真实运行审计（2026-09-03） |
| [experience_self_evolution_guide.md](docs/experience_self_evolution_guide.md) | 经验自进化逐步操作指南 |
| [plt_self_evolution.md](docs/plt_self_evolution.md) | PLT 训练侧自进化说明 |
| [sct_docx_gap_analysis.md](docs/sct_docx_gap_analysis.md) | SCT 实现与 DOCX 逐项差异审计 |
| [sct_lifecycle_replay_run_20260913.md](docs/sct_lifecycle_replay_run_20260913.md) | 生命周期回放全量 PLT 运行记录与门控/检索优化 |
| [sct_lifecycle_replay_meeting_plan_20260914.md](docs/sct_lifecycle_replay_meeting_plan_20260914.md) | 组会五点问题排查结论与改造规划 |
| [external_dataset_provenance.md](docs/external_dataset_provenance.md) | 外部数据来源与许可 |
| [limitations.md](docs/limitations.md) | 当前限制 |
| [reproduction_guide.md](docs/reproduction_guide.md) | 复现实验指南 |
| [chatanywhere-api.md](docs/chatanywhere-api.md) | ChatAnywhere 本地配置与检查 |
| [translation_work.md](docs/translation_work.md) | 运行区目录规范与清理规则 |
| [sct_trajectory_contrastive.md](docs/sct_trajectory_contrastive.md) | SCT 轨迹对比式自进化（新方案：四态 + 轨迹对比 + 四步 Agent） |
| [cle_negative_findings.md](docs/cle_negative_findings.md) | CLE 方法学发现：经验注入无收益的三次实验、过度防御瓶颈定位，以及有效的"功能契约冻结"干预（四次真实实验） |
| [cle_full_run_analysis_20260919.md](docs/cle_full_run_analysis_20260919.md) | 全量 874 运行分析：门控全放行、83.8% 跨 CWE 注入、47.3% 过度防御等六大问题与优化空间 |
| [cle_full_run_v2_report.md](docs/cle_full_run_v2_report.md) | 优化后全量 874 v2 对比报告：九项改动、同 task_id 配对口径、机制性指标对比 |
| [superpowers/specs/2026-09-09-sct-unified-core-design.md](docs/superpowers/specs/2026-09-09-sct-unified-core-design.md) | SCT 统一核心设计（方案 B） |
| [superpowers/specs/2026-09-03-agent-baseline-integration-design.md](docs/superpowers/specs/2026-09-03-agent-baseline-integration-design.md) | Agent baseline 集成设计（开发过程记录） |
| [superpowers/plans/2026-09-09-sct-unified-core.md](docs/superpowers/plans/2026-09-09-sct-unified-core.md) | SCT 统一核心实施计划 |
| [superpowers/plans/2026-09-03-baseline-and-sct-audit.md](docs/superpowers/plans/2026-09-03-baseline-and-sct-audit.md) | 九条 baseline 与 SCT 审计计划（开发过程记录） |
| [superpowers/plans/2026-09-03-agent-baseline-integration.md](docs/superpowers/plans/2026-09-03-agent-baseline-integration.md) | Agent baseline 集成计划（开发过程记录） |

### 简介论文修改方案/（组会需求与论文修改）

| 文件 | 说明 |
|---|---|
| [README.md](简介论文修改方案/README.md) | 总索引：需求编号 R1–R8、阅读路径、状态分类 |
| [组会内容总结.md](简介论文修改方案/组会内容总结.md) | 组会六点意见的易懂版 |
| [问题背景与方案.md](简介论文修改方案/问题背景与方案.md) | 逐项对应当前项目的数据、代码和限制 |
| [自进化论文调研.md](简介论文修改方案/自进化论文调研.md) | 18 篇自进化论文的机制与启发 |
| [自进化结构候选方案.md](简介论文修改方案/自进化结构候选方案.md) | 替代 `D_init/D_grow/D_gate` 的候选结构比较 |
| [论文修改建议.md](简介论文修改方案/论文修改建议.md) | 论文方法、实验和表述修改项 |
| [论文修改建议.docx](简介论文修改方案/论文修改建议.docx) | 适合组会批注的排版版本 |
| [论文来源与阅读说明.md](简介论文修改方案/论文来源与阅读说明.md) | 论文来源、版本和引用边界 |
| [重构方法设计说明.docx](简介论文修改方案/重构方法设计说明.docx) | 新方法（生命周期 + 主动回放）设计说明 |
| [自进化论文索引.json](简介论文修改方案/自进化论文索引.json) | 论文结构化索引 |

### data/（数据、harness、外部数据）

| 路径 | 说明 |
|---|---|
| [data/DATASET_CARD.md](data/DATASET_CARD.md) | 数据卡：数量、来源、清理与限制 |
| [data/SecEvoBasePlus/Base/](data/SecEvoBasePlus/Base/) 与 [Plus/](data/SecEvoBasePlus/Plus/) | 五语言 Base/Plus 正式评测集（Python/Cpp/Go/Java/JS 各 2 个 JSON） |
| [data/harnesses/](data/harnesses/) | C++/Go 原生功能与安全 harness（`Base|Plus` × `cpp|go` × `secure|insecure`） |
| [data/external/README.md](data/external/README.md) | 外部数据集清单与用途 |
| [data/external/secodeplt/secodeplt/data.json](data/external/secodeplt/secodeplt/data.json) | PLT 训练侧 1,411 组漏洞/修复 Python 对 |
| [data/external/secodeplt/derived_metadata/family_manifest.json](data/external/secodeplt/derived_metadata/family_manifest.json) | CWE family 与推断 Seed family 长期派生元数据 |
| data/external/ 其余子目录 | cweval、juliet、cyber_sec_eval、redcode 等外部材料（见 [external_dataset_provenance.md](docs/external_dataset_provenance.md)） |

### src/translation_pipeline/（核心流水线）

| 文件 | 说明 |
|---|---|
| [run_translate_dataset.py](src/translation_pipeline/run_translate_dataset.py) | Python → C++/Go 翻译与验证主入口 |
| [validators.py](src/translation_pipeline/validators.py) | C++/Go Docker 验证器与代码规范化 |
| [python_validator.py](src/translation_pipeline/python_validator.py) | Python Docker 验证器（Test/Test-FP/Test-SP 拆分） |
| [run_full_docker_revalidation.py](src/translation_pipeline/run_full_docker_revalidation.py) | Base/Plus 全量 Docker 重验证 |
| [run_validate_records_guarded.py](src/translation_pipeline/run_validate_records_guarded.py) | 有防护的逐记录验证 |
| [quality_metrics.py](src/translation_pipeline/quality_metrics.py) | PRCS/EQS 工程质量指标 |
| [run_quality_metrics.py](src/translation_pipeline/run_quality_metrics.py) | 质量指标运行入口 |
| [insecure_behavior.py](src/translation_pipeline/insecure_behavior.py) | 不安全行为静态判定规则 |
| [architecture_experiment.py](src/translation_pipeline/architecture_experiment.py) | 跨语言/数据划分实验 |
| [research_diagnostics.py](src/translation_pipeline/research_diagnostics.py) | 研究诊断输出 |
| [prompts.py](src/translation_pipeline/prompts.py) | 翻译/修复/验证提示词 |
| [code_extract.py](src/translation_pipeline/code_extract.py) | 从模型响应提取代码块 |
| [models.py](src/translation_pipeline/models.py) | 验证结果数据结构 |
| [paths.py](src/translation_pipeline/paths.py) | 工作目录与路径常量 |
| [zhipu_client.py](src/translation_pipeline/zhipu_client.py) | 智谱 GLM 客户端（历史兼容） |

### methods/（方法源码）

**prompting_baselines/**（四条单请求 baseline）

| 文件 | 说明 |
|---|---|
| [prompts.py](methods/prompting_baselines/prompts.py) | Greedy / Greedy+Secure / CoT / CoT+Secure 提示词 |
| [run_prompt_baseline.py](methods/prompting_baselines/run_prompt_baseline.py) | **仅桩**：只打印提示词，不调模型、不跑 Docker。四条 Prompt 的真实运行入口是 `workflow_baselines/run_true_agent_workflows.py --only-traditional` |

**workflow_baselines/**（四条 Prompt + 五条多阶段 Agent 的统一 runner）

| 文件 | 说明 |
|---|---|
| [run_true_agent_workflows.py](methods/workflow_baselines/run_true_agent_workflows.py) | 九条 baseline 的统一入口；`--only-traditional` 跑四条 Prompt，`--only-agents` 跑五条 Agent |
| [fidelity.py](methods/workflow_baselines/fidelity.py) | 五条 Agent baseline 的可机检 fidelity 合约 |

**sct_agent/**（SCT 方法：经验卡、检索、进化、门控）

| 文件 | 说明 |
|---|---|
| [run_plt_self_evolution.py](methods/sct_agent/run_plt_self_evolution.py) | PLT 训练侧 SCT 自进化入口（`D_init → M*`） |
| [finalize_plt_evaluation.py](methods/sct_agent/finalize_plt_evaluation.py) | 冻结后 CodeSecEval Base/Plus 评测适配器 |
| [run_sct_language_evolution.py](methods/sct_agent/run_sct_language_evolution.py) | 语言级 SCT 自进化入口（历史） |
| [run_coset_eagle_experiment.py](methods/sct_agent/run_coset_eagle_experiment.py) | Coset Eagle 实验（历史） |
| [schemas.py](methods/sct_agent/schemas.py) | SCT 统一审计数据结构 |
| [difference_analysis.py](methods/sct_agent/difference_analysis.py) | 漏洞—补丁差异抽取 |
| [experience_cards.py](methods/sct_agent/experience_cards.py) | 从差异与失败簇生成经验卡 |
| [failure_clustering.py](methods/sct_agent/failure_clustering.py) | 失败反馈脱敏与聚类 |
| [candidate_gates.py](methods/sct_agent/candidate_gates.py) | 质量 / 有效性 / H_pass 回归三层门控 |
| [experience_lifecycle.py](methods/sct_agent/experience_lifecycle.py) | 候选保存、晋升与冻结隔离 |
| [validation_evidence.py](methods/sct_agent/validation_evidence.py) | 多源验证证据统一接口 |
| [docker_preflight.py](methods/sct_agent/docker_preflight.py) | Base/Plus 冻结评测 Docker 前置检查 |

**sct_lifecycle_replay/**（新方法：经验生命周期 + 验证驱动主动回放）

| 文件 | 说明 |
|---|---|
| [README.md](methods/sct_lifecycle_replay/README.md) | 本目录文件索引、数据流和结果位置 |
| [run_lifecycle_replay.py](methods/sct_lifecycle_replay/run_lifecycle_replay.py) | 主入口：来源 → 回放 → 候选 → 审查 → 冻结 |
| [run_local_codeseceval.py](methods/sct_lifecycle_replay/run_local_codeseceval.py) | 本地（无 Docker）CodeSecEval Python 评测入口 |
| [schemas.py](methods/sct_lifecycle_replay/schemas.py) | 最小审计记录结构 |
| [family_manifest.py](methods/sct_lifecycle_replay/family_manifest.py) | PLT family 元数据读取与校验 |
| [split_scheduler.py](methods/sct_lifecycle_replay/split_scheduler.py) | source / replay / audit 任务分配 |
| [source_knowledge.py](methods/sct_lifecycle_replay/source_knowledge.py) | 从漏洞—补丁差异提取 seed 假设 |
| [retriever.py](methods/sct_lifecycle_replay/retriever.py) | 轻量可审计 TF-IDF 检索器 |
| [trajectory_runner.py](methods/sct_lifecycle_replay/trajectory_runner.py) | 生成代码与有限修复轨迹 |
| [trajectory_validation.py](methods/sct_lifecycle_replay/trajectory_validation.py) | PLT 本地验证证据记录 |
| [candidate_builder.py](methods/sct_lifecycle_replay/candidate_builder.py) | 从重复失败轨迹形成候选经验 |
| [active_replay.py](methods/sct_lifecycle_replay/active_replay.py) | 按不确定性/风险/覆盖/成本选择任务 |
| [llm_scheduler.py](methods/sct_lifecycle_replay/llm_scheduler.py) | LLM 驱动任务选择器 |
| [independent_audit.py](methods/sct_lifecycle_replay/independent_audit.py) | 独立证据审查归类 |
| [audit_runner.py](methods/sct_lifecycle_replay/audit_runner.py) | JointPass 对比与 H_pass 回归检查 |
| [experience_lifecycle.py](methods/sct_lifecycle_replay/experience_lifecycle.py) | C_t / M_t 状态管理与冻结边界 |
| [freeze_protocol.py](methods/sct_lifecycle_replay/freeze_protocol.py) | 冻结清单与经验库哈希 |
| [frozen_evaluation.py](methods/sct_lifecycle_replay/frozen_evaluation.py) | 冻结后 Base/Plus 评测计划与反馈隔离 |
| [language_adapters.py](methods/sct_lifecycle_replay/language_adapters.py) | 多语言编译/harness 适配接口 |
| [local_codeseceval.py](methods/sct_lifecycle_replay/local_codeseceval.py) | 本地 CodeSecEval Python 评测器 |
| [api.py](methods/sct_lifecycle_replay/api.py) | ChatAnywhere 请求适配（错误只留类型） |
| [chatanywhere_smoke.py](methods/sct_lifecycle_replay/chatanywhere_smoke.py) | DeepSeek 3.2 连通性烟测 |
| [reporting.py](methods/sct_lifecycle_replay/reporting.py) | 精简运行报告 |

**secodeplt_eval/**（官方 SeCodePLT 评测方式移植）

| 文件 | 说明 |
|---|---|
| [README.md](methods/secodeplt_eval/README.md) | 移植说明、用法与 VHDX 分析 |
| [schemas.py](methods/secodeplt_eval/schemas.py) | 与官方对齐的评测数据结构（零依赖 dataclass） |
| [template.py](methods/secodeplt_eval/template.py) | 官方 unittest 模板注入与 Windows 兼容 |
| [executor.py](methods/secodeplt_eval/executor.py) | 本地 python -I 执行（默认）与常驻 Docker 容器（官方模式） |
| [scoring.py](methods/secodeplt_eval/scoring.py) | capability/safety 打分与联合通过判定 |

**legacy_prompt_adapters/**（历史兼容，仅回放）

| 文件 | 说明 |
|---|---|
| [run_actual_5_python_methods.py](methods/legacy_prompt_adapters/run_actual_5_python_methods.py) | 旧 Python 五方法评测（依赖已删除 harness） |
| [run_coset_eagle_experiment.py](methods/legacy_prompt_adapters/run_coset_eagle_experiment.py) | 旧 Coset Eagle 实验 |
| [run_experiment.py](methods/legacy_prompt_adapters/run_experiment.py) | SeCodePLT vs CodeSecEval 经验对比 |
| [run_language_method_matrix.py](methods/legacy_prompt_adapters/run_language_method_matrix.py) | 旧语言×方法矩阵 |

### tests/（离线测试）

| 文件 | 覆盖内容 |
|---|---|
| [test_repository_smoke.py](tests/test_repository_smoke.py) | 数据量、根路径、Prompt 方法数 |
| [test_validation_regressions.py](tests/test_validation_regressions.py) | 验证器回归、常驻容器挂载根与 Go 规格 |
| [test_baseline_runtime.py](tests/test_baseline_runtime.py) | baseline 运行链路、harness 回退查找、凭据解析顺序 |
| [test_agent_workflow_fidelity.py](tests/test_agent_workflow_fidelity.py) | Agent workflow fidelity |
| [test_plt_self_evolution.py](tests/test_plt_self_evolution.py) | PLT 自进化 |
| [test_llm_scheduler.py](tests/test_llm_scheduler.py) | LLM 任务选择器 |
| [test_local_codeseceval.py](tests/test_local_codeseceval.py) | 本地 CodeSecEval 评测器 |
| [test_secodeplt_eval.py](tests/test_secodeplt_eval.py) | SeCodePLT 移植（模板注入、本地/Docker 执行器、Juliet Java 源码改写与常驻容器执行） |
| [test_sct_schemas.py](tests/test_sct_schemas.py) | SCT 数据结构 |
| [test_sct_difference_analysis.py](tests/test_sct_difference_analysis.py) | 差异分析 |
| [test_sct_experience_cards.py](tests/test_sct_experience_cards.py) | 经验卡 / 失败聚类 |
| [test_sct_candidate_gates.py](tests/test_sct_candidate_gates.py) | 三层门控 |
| [test_sct_freeze_isolation.py](tests/test_sct_freeze_isolation.py) | 冻结隔离 |
| [test_sct_validation_evidence.py](tests/test_sct_validation_evidence.py) | 验证证据 |
| [test_sct_lifecycle_replay.py](tests/test_sct_lifecycle_replay.py) | 生命周期 + 主动回放 |
| [test_active_replay.py](tests/test_active_replay.py) | 主动回放任务选择 |
| [test_agent_pipeline.py](tests/test_agent_pipeline.py) | Agent 流水线 |
| [test_distillation.py](tests/test_distillation.py) | 经验蒸馏 |
| [test_error_ledger.py](tests/test_error_ledger.py) | 错误台账 |
| [test_four_state.py](tests/test_four_state.py) | 四态判定 |
| [test_frozen_report.py](tests/test_frozen_report.py) | 冻结报告 |
| [test_gates.py](tests/test_gates.py) | 门控 |
| [test_hsk_tree.py](tests/test_hsk_tree.py) | HSK 树 |
| [test_retriever_align.py](tests/test_retriever_align.py) | 检索器对齐 |
| [test_split.py](tests/test_split.py) | 数据划分 |
| [test_trajectory_reflection.py](tests/test_trajectory_reflection.py) | 轨迹反思 |

### tools/、configs/、docker/、results/

| 文件 | 说明 |
|---|---|
| [tools/check_repository.py](tools/check_repository.py) | 仓库完整性检查（数量、脱敏） |
| [tools/sanitize_dataset.py](tools/sanitize_dataset.py) | 数据集脱敏（机器路径、密钥） |
| [tools/vhdx_watchdog.py](tools/vhdx_watchdog.py) | 跑命令并全程采样 vhdx 水位与容器数，给出"Docker 是否膨胀"的可引用判定 |
| [tools/run_baseline_server.sh](tools/run_baseline_server.sh) | 服务器侧一键启动 baseline（看门狗包裹 + 参数校验） |
| [tools/make_baseline_table.py](tools/make_baseline_table.py) | 把运行结果渲染成组会口径的两张表，并拦截"全 0 陷阱" |
| [tools/summarize_run.py](tools/summarize_run.py) | 逐方法汇总通过数与错误类型，快速判断"全 0"是模型失败还是链路故障 |
| [tools/check_chatanywhere_keys.ps1](tools/check_chatanywhere_keys.ps1) | ChatAnywhere key 脱敏检查 |
| [configs/README.md](configs/README.md) | 配置放置规则 |
| [docker/python-validator/Dockerfile](docker/python-validator/Dockerfile) | Python 验证器镜像 |
| [docker/cpp-validator/Dockerfile](docker/cpp-validator/Dockerfile) | C++ 验证器镜像 |
| [docker/go-validator/Dockerfile](docker/go-validator/Dockerfile) | Go 验证器镜像（历史定义；实际用 `golang:1.22`） |
| [docker/java-validator/Dockerfile](docker/java-validator/Dockerfile) | PLT Juliet Java 评测镜像（JDK 17 + JUnit standalone；本机默认复用已有 JDK 镜像） |
| [results/curated/README.md](results/curated/README.md) | 精简结果提交规则 |

## 方法分组

| 分组 | 方法 | 特征 |
|---|---|---|
| Prompt baseline | Greedy、Greedy + Secure Prompt、Chain-of-Thought、CoT + Secure Prompt | 单次模型请求，仅提示词不同 |
| Agent baseline | AutoSafeCoder、AgentCoder、RA-Gen、SWE-Agent、SecAwareCoder | 多阶段生成、测试、反馈、修复或候选选择 |
| 本方法 | SCT-Agent | 经验卡、失败分析、门控晋升、冻结后最终评测 |

五条 Agent baseline 必须保留原始工作流阶段，不能把 Agent 名称包装成单个 prompt。详细阶段和 fidelity 判定见 [Baseline 忠实性说明](docs/baseline_fidelity.md)。

## 代码结构

```text
data/                         SecEvoBase/Plus 数据、数据卡和原生 harness
src/translation_pipeline/     Docker 验证器和质量指标
methods/prompting_baselines/  四条直接 Prompt baseline
methods/workflow_baselines/   五条真实多阶段 Agent workflow（含 fidelity 合约）
methods/sct_agent/            SCT 经验记忆和门控进化入口
methods/sct_lifecycle_replay/ 新方法：经验生命周期 + 验证驱动主动回放
methods/legacy_prompt_adapters/历史兼容适配代码，仅用于回放
configs/                      不含密钥的运行配置
docker/                       Python/C++/Go 验证器镜像定义
results/curated/              可提交的精简结果摘要
docs/                         协议、审计、复现和数据说明
tests/                        离线回归测试（26 个文件）
tools/                        数据清洗、key 检查和仓库检查工具
```

## 数据集

`data/SecEvoBasePlus/` 包含五种语言的 Base/Plus 数据：

| 划分 | Python | C++ | Go | Java | JavaScript |
|---|---:|---:|---:|---:|---:|
| Base | 115 | 115 | 115 | 116 | 116 |
| Plus | 140 | 140 | 140 | 140 | 140 |

当前完整 Docker 验证主要覆盖 Python、C++、Go；Java 和 JavaScript 的最终验证器仍在完善。Base/Plus 是最终评测集合，不能反向更新 SCT 经验记忆。

PLT 训练侧只有 Python 数据，默认不启动 Docker，而是在本地 `python -I` 临时子进程中运行原生 `capability/safety` 数据驱动测试（兼容旧 `check(candidate)`），并记录超时与未测量项；这属于轻量沙盒，不等同于 Docker 安全隔离。Docker 仅用于冻结后的 CodeSecEval Base/Plus 和 C++/Go harness 验证。

当前正式 PLT runner 默认从 1,411 条可用记录中选择四分之一（`ceil` 为 353 条），按 28 个 CWE 配额尽量均衡，再保持 Seed Family 原子性分到 D_init/D_grow/D_gate；详见 [PLT 自进化实验说明](docs/plt_self_evolution.md)。本轮正式结果目录为 `translation_work/sct_runs/plt_python_quarter_353_20260910_132431/`。

PLT manifest 使用两层分类：`CWE family`（如 `CWE-22`，漏洞类别）和 `Seed family`（同一任务语义、代码骨架与根因的变体组）。由于上游 `data.json` 没有官方 lineage 字段，Seed family 是基于 CWE 与规范化任务语义的可复现推断；字段和限制见 [PLT 自进化实验说明](docs/plt_self_evolution.md)。

全量 PLT 两层分类位于 `data/external/secodeplt/derived_metadata/family_manifest.json`，作为后续数据划分和 family 内实验的长期派生元数据。

本轮最终 Docker 重验证结果为：Base 29/12/7、Plus 104/57/54（Function/Secure/Joint）。验证器先用官方 Secure Code 校准，Base 115/115、Plus 140/140 联合通过；校准记录位于 `translation_work/diagnostics/20260911/python_harness_calibration/`，仅作审计，不计入模型分数。

## 环境与验证器

在 Windows PowerShell 中运行，要求 Docker Desktop 已启动：

```powershell
python -m pip install -r requirements.txt
docker build -t safecoder-python-validator:local docker/python-validator
docker build -t safecoder-cpp-validator:local docker/cpp-validator
docker pull golang:1.22
```

默认模型是 `deepseek-v3.2`（**非推理模型**，`reasoning_tokens=0`，全部 `max_tokens`
预算都用于正文）。不要默认改用推理模型：`deepseek-v4-flash` 在长任务提示下会把
1024 的预算全烧在推理上（实测 `completion=1024 / reasoning=1024 / 正文为空`），
产出"代码为空、Function/Secure 全 False"的假结果。用 v4 系列必须同时把
`--max-tokens` 提到 4096 以上。

离线检查：

```powershell
python -m compileall src methods tools
python -m unittest discover -s tests -v
python tools/check_repository.py
```

跑完大批量实验后若 D 盘空间明显减少，用 [Docker 数据盘压缩指南](docs/docker_disk_hygiene.md) 和 `tools/compact_docker_vhdx.ps1` 一键回收 `docker_data.vhdx` 里已删除但未归还的空间。

**但更该做的是别让它涨**：大批量运行一律用 `tools/vhdx_watchdog.py` 包裹（见上方
「Docker 纪律」），它会全程采样水位并给出判定报告；跑完确认 `docker ps -a` 为空，
再考虑是否需要压缩。

### ChatAnywhere API key 存储位置

默认的本地 key 文件是：

```text
local_secrets/chatanywhereapi使用/apikey.txt
```

该目录已在 `.gitignore` 中忽略，文件内容只应保存在本机，不能提交到 GitHub。运行器按以下顺序读取凭据：

1. 环境变量 `CHATANYWHERE_API_KEY`；
2. 环境变量 `OPENAI_API_KEY`（仅 PLT 运行器兼容读取）；
3. `local_secrets/chatanywhereapi使用/apikey.txt` 的第一个非空行；
4. 部分历史兼容脚本还支持 `ZHIPU_API_KEY`，但新的 ChatAnywhere 实验应优先使用前两种变量或本地 key 文件。

接口地址默认是 `https://api.chatanywhere.tech/v1`。Agent baseline 使用 `CHATANYWHERE_API_BASE` 覆盖，PLT 运行器使用 `CHATANYWHERE_BASE_URL` 覆盖。README、代码、结果 JSONL 和报告中都不得写入真实 key；检查 key 是否有效请使用 [ChatAnywhere 配置与检查说明](docs/chatanywhere-api.md) 中的脱敏脚本。

## Baseline 评测快速入口

九条 baseline（4 条 Prompt + 5 条 Agent）由**同一个** runner 运行：

```text
methods/workflow_baselines/run_true_agent_workflows.py
```

- `--only-traditional` → 四条 Prompt baseline（Greedy / Greedy + Secure Prompt / CoT / CoT + Secure Prompt）
- `--only-agents` → 五条 Agent baseline（AutoSafeCoder / RA-Gen / SWE-Agent / AgentCoder / SecAwareCoder）
- 两个都不加 → 九条全跑

> `methods/prompting_baselines/run_prompt_baseline.py` **只是桩**：它只打印提示词，
> 不调模型、不跑 Docker。四条 Prompt 方法的真实实现就在上面的 runner 里。

结果统一写入被忽略的目录：

`translation_work/baseline_runs/<run-name>/<subset>/`
（`rows.jsonl` / `summary.json` / `true_agent_workflow_report.md` / `run_metadata.json`）

### 当前实验矩阵：9 条 baseline × 5 个模型

正在跑的对比实验是 **9 条 baseline（4 Prompt + 5 Agent）× 5 个模型 × {Base, Plus} × {python, cpp, go}**。

#### 模型与渠道（已逐个发最小请求实测）

| 表格用名 | 实际 model ID | 渠道 | 备注 |
|---|---|---|---|
| deepseek v4.1 flash | `deepseek-v4.1-flash` | ChatAnywhere | 非推理，`reasoning_tokens=0` |
| 5.6 luna | `gpt-5.6-luna` | ChatAnywhere | **不是 `5.6luna`**；少了 `gpt-` 前缀会 404 |
| gemini 2.5 flash | `gemini-2.5-flash` | ChatAnywhere | 非推理 |
| qwen3.5 plus | `qwen3.5-plus` | ChatAnywhere | **推理模型** |
| glm 5.3 flash | `glm-5.3-flash` | 智谱 | **推理模型** |

**两个推理模型要特别处理**：`qwen3.5-plus` 和 `glm-5.3-flash` 简单一句问候就消耗
100+ reasoning token。跑代码题必须把 `--max-tokens` 提到 **8192**；否则正文被
reasoning 吃光，表现成"代码为空 + 结果全 0"，看起来像模型不会写代码。

智谱渠道**不用改代码**——runner 支持用环境变量切换端点：

```bash
export CHATANYWHERE_API_BASE=https://open.bigmodel.cn/api/paas/v4
export CHATANYWHERE_API_KEY=<智谱 key>    # 或放 local_secrets/智谱api使用/newkey.env
```

#### 在服务器上跑

```bash
cd ~/sct-security-generation
bash tools/run_baseline_server.sh <run-name> <model> [max-tokens] [workers] [subsets] [languages] [limit]
```

例（deepseek-v4.1-flash × Base × python × 九条全跑）：

```bash
bash tools/run_baseline_server.sh val_dsv41_base_python_20260920 deepseek-v4.1-flash 4096 6 Base python 0
```

脚本内部用 `tools/vhdx_watchdog.py` 包裹，跑完在
`translation_work/diagnostics/vhdx_watchdog_<run-name>.json` 留下可引用的 Docker 判定。

#### 跑完自动出表

```bash
python tools/make_baseline_table.py --run <run-name>            # 百分比（默认）
python tools/make_baseline_table.py --run <run-name> --counts   # 通过条数
python tools/make_baseline_table.py --all --by-language         # 每个语言单独出表
python tools/make_baseline_table.py --run <name> --out docs/baseline_table.md
```

输出**两张表**（基础方法 / Agent 方法），列口径与组会模板一致：

```text
CodeSecEval (255) → SecEvalBase[func|sec|func_sec] | SecEvalPlus[func|sec|func_sec]
```

`func` / `sec` / `func_sec` 分别对应 `metrics.secure_functional` /
`secure_security` / `secure_func_sec`（`func_sec` 是最严口径，两者同时通过）。
分母 Base 115 + Plus 140 = **255**，是单语言口径；跨语言聚合时表头会自动改成实际总数。
`Ours` 不由本 runner 产出，固定留空行待 SCT 结果填入。

**表格会自动拦截"全 0 陷阱"**：若某个分组超过一半的记录代码为空（代码生成整批失败），
表下会显式打出警告。这种行看着像"模型一个都没通过"，实际是链路故障，**不能进论文**。
实测历史 `agents_full_deepseek_v32_20260906` 的 Plus 侧就是这样：280/280 条代码为空。

### 冒烟：先跑一个任务验证链路

用 vhdx 看门狗包裹，跑完直接给出"Docker 有没有膨胀"的判定：

```powershell
$PY = "D:/ANACONDA/python.exe"   # 需要装了 openai 的解释器
& $PY tools/vhdx_watchdog.py --label smoke --max-containers 16 --interval 2 -- `
  $PY methods/workflow_baselines/run_true_agent_workflows.py `
    --subsets Base --languages python cpp go --limit 1 `
    --out-name smoke_20260918 `
    --model deepseek-v3.2 --max-tokens 2048 --temperature 0 `
    --retries 1 --workers 2 --only-traditional
```

每条结果至少检查：真实模型请求、生成代码非空、`workflow_completed`、Agent 的
`fidelity_passed`、Docker Function/Secure 结果。模型生成了错误代码但流程到达终态，
属于模型结果；API 超时、代码提取异常、缺阶段或 runner 崩溃，才属于运行失败。

另外**必须**确认没有 `error_type=environment_error`——那是环境事故，不是模型结果。

### Docker 纪律：评测期间 VHDX 不涨

2026-09-17 的事故（vhdx 从 14.9 GB 涨到 67.72 GB）根因是"每个任务 `docker run --rm`
新建容器 + 中途强杀留下孤儿容器"。执行层已改成**常驻容器池**
（`src/translation_pipeline/persistent_container.py`），配套纪律见
[AGENTS.md 第九节](AGENTS.md)。要点：

1. 所有 Docker 验证走常驻容器执行层，不新写 `docker run`；
2. 池大小 >= 并发数（runner 会自动设 `SAFECODER_DOCKER_POOL_SIZE = max(--workers, 1)`）；
3. 跑前自动清理残留池容器（`cleanup_stale_containers()`）；
4. 大批量运行一律用 `tools/vhdx_watchdog.py` 包裹，产出可引用的判定报告；
5. 只读挂载 JUnit / juliet-support / Mockito 等工具链；只挂 `translation_work/`，
   绝不挂仓库根（`local_secrets/` 里有 key）。

### 会静默让结果失真的三个陷阱（已修复，勿回退）

| 陷阱 | 症状 | 正确做法 |
|---|---|---|
| harness 查找只认历史 `sandbox_dir` | C++/Go 全部落到 `compile_run_only_no_security_credit`，**不给安全学分**，像"模型全写错" | 必须回退到 `data/harnesses/<subset>/<language>/<track>/<task_id>/main.<ext>` |
| 推理模型吃光 `max_tokens` | `code` 为空、Function/Secure 全 False，像"模型不会写代码" | 用 `deepseek-v3.2`（`reasoning_tokens=0`）；用 v4 系列须把 `--max-tokens` 提到 4096+ |
| 凭据被 `.env` 快照遮蔽 | 403 余额不足 | 顺序固定：环境变量 → `apikey.txt` → `.env` 兜底 |

**通用教训**：验证链路里任何"找不到就降级"的分支都必须显式记录降级原因，
并在冒烟检查里断言不允许出现，否则会静默产出看似合理、实则全零的结果。

### PLT Java 评测

PLT Java 不走上面的 runner，走 `methods/secodeplt_eval/java_executor.py`。
数据在 `data/external/secodeplt/hf_full/jsonl/java_secure_coding-*.jsonl`
（924 条 Juliet，**869 条带单测，单测在 `meta_data.unit_test` 里**）。
不用 Maven：`javac` + JUnit standalone jar，报告走 `--reports-dir` XML。
编译失败必须记成 `measured=False`，不得与 `score=0` 混同。
细节与回归脚本见 [AGENTS.md 第九节 9.6](AGENTS.md)。

## 结果管理规则

- `rows.jsonl`：逐任务代码、trace、fidelity 和验证结果。
- `summary.json`：按方法和语言汇总的指标。
- `true_agent_workflow_report.md`：面向人工阅读的运行报告。
- `translation_work/`：实验输出、Docker 临时目录和缓存，默认不提交。
- `results/curated/`：只放精简、标注清楚、可复核的最终摘要。

不要提交 API key、`.env.local`、原始长日志、Docker VHDX、构建缓存或未脱敏响应。

SCT 的正式经验轮次 `R0–R3` 不是历史缓存：它们分别表示初始经验建立和后续候选经验进化轮次，完整定义见[评测协议](docs/evaluation_protocol.md)。

## 进一步阅读

如果你要复现实验，请按 [复现实验指南](docs/reproduction_guide.md)；如果你要判断某条 baseline 是否忠实，请按 [Baseline 忠实性说明](docs/baseline_fidelity.md)；如果你要理解 SCT 当前还缺什么，请按 [SCT 差异审计](docs/sct_docx_gap_analysis.md)。

代码采用 MIT 许可；外部 benchmark 数据仍受其原始许可证和再分发条件约束。

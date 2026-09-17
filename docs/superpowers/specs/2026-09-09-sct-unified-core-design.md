# SCT 统一核心流水线设计

日期：2026-09-09  
规范来源：`docs/面向多语言安全代码生成的经验自进化方法.docx`

## 目标

将 `methods/sct_agent` 从多个相互依赖的原型脚本整理为可审计的统一核心。外部数据边界保持 DOCX 定义的 `D_init → M0 → D_grow → C_t → D_gate/H_pass → M* → CodeSecEval-X`，内部使用“观察—假设—验证—生命周期决策”表达经验自进化。

## 边界与数据流

- `D_init`：只用于漏洞—补丁差异分析、初始经验生成和训练侧验证。
- `D_grow`：只用于经验检索、代码生成、失败脱敏/聚类和候选经验生成。
- `D_gate`：独立于 `D_grow`，只用于候选经验有效性比较。
- `H_pass`：历史已通过任务，只用于回归门控，不产生新经验。
- `CodeSecEval-X Base/Plus`：冻结后最终评测，结果不反馈给任何生成、门控或经验更新路径。

## 模块设计

### `schemas.py`

定义 `DifferenceAnalysis`、`ValidationEvidence`、`ExperienceCard`、`FailureCluster`、`GateRecord` 和 `FreezeManifest`。所有结构都可 JSON 序列化，枚举状态使用 `pass/fail/unmeasured`，避免把未执行误记为通过。

### `difference_analysis.py`

以漏洞代码、补丁代码、任务描述和训练侧测试为输入，结合 AST、统一 diff 和安全 API 规则，输出图一要求的六类字段：不可信输入、敏感操作/触发条件、补丁逻辑变化、安全 API 及约束、修复后置条件、危险模式。该模块只抽象原则，不复制完整补丁或测试常量。

### `validation_evidence.py`

封装 Python/C++/Go 现有验证器；PLT Python 默认使用 `python -I` 本地临时子进程沙盒（超时、临时目录和环境隔离），不启动 Docker。CodeSecEval 或 C++/Go harness 仍可注入 Docker 后端。统一记录语法/编译、功能、安全、静态、类型、资源、超时、异常八类证据。未安装工具或没有 harness 时写入 `unmeasured` 和原因。

### `failure_clustering.py`

先删除任务 ID、入口名、测试输入、常量、答案片段和原始长输出，再按语言、CWE、错误类别和规范化消息聚类。只有达到最低支持样本数的簇才允许生成候选经验。

### `experience_cards.py`

从 `DifferenceAnalysis` 或失败簇生成结构化经验卡，字段包含适用条件、安全原则、语言实现提示和禁止模式。提供答案/常量泄露、任务特判、重复和冲突检查。

### `candidate_gates.py`

实现三层门控：质量门控、独立 D_gate 有效性门控、H_pass 回归门控。有效性必须满足 `ΔJointPass > 0`；回归要求安全回归为零、功能退化不超过配置阈值。返回逐候选 `GateRecord`，支持 `promote/revise/reject/hold`。

### `experience_lifecycle.py`

集中处理候选经验的临时池、晋升、修订、拒绝、冻结和预算/无晋升/性能平台终止条件。只有门控全部通过的候选才可写入长期库。

## 入口职责

- `run_sct_language_evolution.py`：唯一正式 SCT 入口，串联上述模块。
- `run_plt_self_evolution.py`：PLT 训练侧适配器，负责 96 条样本的分区和 R0/R1 运行。
- `finalize_plt_evaluation.py`：只执行冻结后的 Base/Plus 评测并输出完整验证证据。
- `run_coset_eagle_experiment.py`：保留为原型/历史结果回放，不写入正式 SCT 结果。

## 冻结协议

冻结前写出模型、Prompt、检索器、采样参数、经验库摘要、数据 manifest、验证器版本、Docker 镜像摘要和 Git commit。冻结后入口拒绝写入经验库，并在元数据中记录 `feedback_channel=disabled`。

## 错误处理

模型空响应、API 超时、代码提取失败、编译失败、测试失败、资源超限和验证器异常均写入结构化 `error_type`，任务保留在分母中；单任务失败不能导致隐式删样本。

## 验收标准

1. 图一六类差异字段可由确定性 fixture 复现。
2. 动态验证分别记录功能和安全结果，并区分 `unmeasured`。
3. 候选经验不泄露任务数据，且只有 `ΔJointPass > 0` 且 H_pass 无回归时晋升。
4. 冻结后 Base/Plus 不能更新经验库。
5. 现有 Python 单元测试和新增 SCT 测试全部通过；四个入口的 `--help` 可运行。

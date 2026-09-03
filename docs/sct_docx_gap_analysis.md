# 当前 SCT 实现与方法 DOCX 差异分析

审计日期：2026-09-04（复核）

规范来源：`docs/面向多语言安全代码生成的经验自进化方法.docx`。本次以 DOCX 正文和 20 个表格的结构化提取结果为准。

## 总结

本审计与九条 baseline 的 CodeSecEval 对比运行相互独立。Baseline 使用 CodeSecEval 是实验设计要求，不构成 SCT 数据污染；下表中的“数据边界”只针对 SCT 自身的经验生成、门控、更新和最终评测路径。

当前代码包含“经验卡、检索、失败反思、候选规则、微型门控、规则文件、任务内修复”等原型组件，但尚未实现 DOCX 定义的正式实验协议。最严重的问题不是功能细节缺失，而是数据边界相反：当前语言自进化入口直接把 Base/Plus 用于 micro gate、失败归纳和规则更新，而 DOCX 与 `docs/evaluation_protocol.md` 都要求 Base/Plus 只能用于冻结后的最终评测。

此外，当前 SCT 从全新输出目录无法启动，因为仓库中缺少它默认加载的 `final_gated_sample/gate_best_rules.json`；另一个 Coset Eagle 入口直接运行时也因缺少 `run_experiment` 导入而失败。

## 逐条需求映射

状态只使用：`implemented`、`partial`、`documentation-only`、`missing`、`contradicted`。

| DOCX 要求 | 状态 | 当前实现证据 | 差异 |
|---|---|---|---|
| 明确划分 `D_init / D_grow / D_gate / CodeSecEval-X` | contradicted | `run_sct_language_evolution.py:543-551` 只暴露 Base/Plus、micro subset；默认 micro subset 为 Base | 没有四区数据模型，最终集被用作门控集 |
| 初始经验来自经执行验证的漏洞/补丁对 | partial | `architecture_experiment.py:452-475`、`run_experiment.py:274-302` 可从 secure/insecure 代码构造卡片 | 主要是启发式标签、代码截断和 diff；没有逐条重新生成并用功能/安全测试验证经验有效性 |
| 经验包含适用条件、原则、语言提示、禁止模式 | implemented | `run_sct_language_evolution.py:109-131, 191-208` | 字段基本对应 `when_to_apply / principle / implementation_hint / avoid` |
| 初始经验训练侧回放验证 | missing | 无对应验证流水线 | 目前只有后续候选整体分数比较 |
| 语义去重、冲突检查、同类合并形成 `M0` | partial | `run_sct_language_evolution.py:237-307` 做精确 identity 去重和 topic 数量限制 | 没有语义去重、规则冲突判定或合并后的重新验证 |
| 从当前经验按任务语义、语言、输入源、敏感操作、漏洞类型检索 | partial | `run_coset_eagle_experiment.py:177-190` 和 `run_experiment.py:336-348` 使用 CWE/词项重合 | 没有独立检索器，也没有显式 source/sink/敏感操作联合匹配 |
| `D_grow` 上生成并产生候选经验，不直接写长期库 | contradicted | `run_sct_language_evolution.py:446-493` 从 Base/Plus full rows 的失败生成 updates，随后立即写 active rules | 使用最终集；候选先进入活动规则，下一轮才用 micro score 决定是否回滚 |
| 编译、功能、安全、静态分析、类型、资源/超时多源验证 | partial | Python/C++/Go validators 提供编译/执行/超时及功能安全测试；quality metrics 提供轻量 warning | 没有完整静态安全分析/type checker 作为自进化验证信号；Java/JS 未接入 |
| 聚合多个相似失败并聚类归纳候选经验 | missing | `run_sct_language_evolution.py:79-106` 顺序截取最多 12 个失败；`176-234` 直接交给 LLM | 没有 failure clustering，也没有最小支持样本数 |
| 候选经验不得含任务 ID、测试输入、常量、答案 | contradicted | `failure_payload` 明确包含 `task_id`、stderr/stdout；这些在 `:215-218` 进入候选生成 prompt | Coset Eagle 另一路径有 sanitization，但正式语言进化入口仍向模型暴露标识和测试输出 |
| 同语言 API/类型/异常/资源知识扩展 | partial | 每种语言维护独立规则文件，topic 包含 import/type/resource/error | 仅 Python/C++/Go；没有系统地由验证器证据确认语言规则 |
| 源语言修复知识 -> 通用原则 -> 目标语言实现提示 | partial | security delta cards 包含 target-language risks；语言规则有 implementation hint | 没有可追踪的三阶段转换记录和跨语言独立验证 |
| 质量门控：泄露、特判、重复、冲突、边界 | partial | `is_generic_rule`、duplicate/budget filter、prompt 约束 | 无完整答案泄露扫描、语义冲突检测和适用边界验证 |
| 独立 `D_gate` 上必须带来正向 JointPass 增益 | contradicted | `gate_accepts` 在 `run_sct_language_evolution.py:328-337` 只要求不下降，相等也接受 | 不要求 `ΔJointPass > 0`，且 micro gate 默认来自 Base |
| `H_pass` 回归门控，无安全回归、功能退化受限 | missing | 无 `H_pass` 数据结构或历史通过任务回放 | 当前只比较同一 micro sample 的汇总计数 |
| 候选晋升、修订或拒绝并记录 | partial | Coset Eagle 有 rejected JSONL；language evolution 可接受或回滚 | language evolution 没有候选级拒绝记录和修订后重新门控 |
| 最大轮数、连续无晋升、性能平台、经验预算等终止条件 | partial | 有固定 `evolution_rounds` 与每 topic 数量限制 | 只有固定轮数，没有无晋升/平台/总预算停止条件 |
| 冻结模型、经验库、检索器、prompt、采样参数 | partial | `coset_eagle_final_gated` 加载固定规则并使用 clean prompt | 没有完整冻结 manifest/hash；language evolution 会根据 Base/Plus 选择 best round |
| 测试期只允许无隐藏测试反馈的任务内工具修复 | contradicted | Coset Eagle repair 使用 `final_eval` 的 sanitized pass/fail/error；legacy matrix 也评测后修复 | 即使隐藏输入被遮盖，隐藏测试的通过/失败和错误类别仍反馈给生成器 |
| 所有任务生成完成后统一跑隐藏测试，结果不反馈 | contradicted | `run_coset_eagle_experiment.py:1229-1265` 每个任务生成后立即评测并修复 | 生成和隐藏评测交织，不是统一后测 |
| 最终评测期间 `M*` 不更新 | contradicted | `run_sct_language_evolution.py:479-493` 从 full Base/Plus failures 产生并写入新规则 | 直接违反冻结协议 |
| 按原始 Seed Family 隔离数据区域 | missing | 全仓搜索无 seed-family split 实现；旧 `prepare` 仅按 CWE 取样 | 可能发生同种子增强样本跨区泄漏 |
| CodeSecEval-X 覆盖 Python/C++/Go/Java/JS | partial | 数据文件有五种语言 | 正式 SCT CLI 只允许 python/cpp/go (`run_sct_language_evolution.py:546`) |
| final hidden results 不用于错误归纳或 memory update | contradicted | full payload 来自 Base/Plus 评测并送入 `propose_rules` | 最关键的实验污染风险 |

## 可运行性缺陷

### 1. 新实验无法从空目录启动

命令使用新的 ignored 输出目录、1 个 Python task、0 个进化轮次，尚未调用模型即失败：

```text
FileNotFoundError: ... methods/legacy_prompt_adapters/final_gated_sample/gate_best_rules.json
```

调用链为 `run_sct_language_evolution.py:393 -> load_language_rules:142-146 -> load_final_gated_rules`。仓库没有该 sample 目录或规则文件，因此 R0 不是可复现地产生的。

### 2. Coset Eagle 主入口不能直接运行

`python methods/sct_agent/run_coset_eagle_experiment.py --help` 在第 35 行失败：

```text
ModuleNotFoundError: No module named 'run_experiment'
```

它只有在另一个脚本先把 legacy adapter 目录插入 `sys.path` 时才可能间接工作，入口自身不自包含。

### 3. Python 验证依赖已删除的历史 harness

当前正式 runner 最终委托到 legacy adapters；Python 路径仍调用缺失的 CodeSecEval harness。因此即使 R0 文件补齐，也会在真实生成后评测失败。

## 与 DOCX 最接近的已有部分

可以保留并重构的基础包括：

- 结构化规则字段与语言特定 memory 文件；
- Docker 化 Python/C++/Go 验证器；
- failure type 分类与 sanitized feedback 思路；
- 候选规则的静态过滤、拒绝记录和微门控记录格式；
- clean generation prompt 与 frozen rule loader 的概念；
- Function、Secure、Function+Secure 的主指标定义。

## 修复优先级

1. **P0 数据隔离**：新增 Seed Family 级 `D_init/D_grow/D_gate/CodeSecEval-X` manifest；从代码层禁止 Base/Plus 进入 evolve/gate。
2. **P0 可启动性**：实现从已验证漏洞/补丁对生成 R0；不能依赖仓库中不存在的手工 `final_gated_sample`。
3. **P0 隐藏测试隔离**：把 generation/task-local tools 与最终 hidden evaluation 拆成两个进程/阶段；hidden 结果永不返回生成器。
4. **P0 baseline fidelity**：引入五个锁 commit 的上游工作流和纯适配层，删除当前 agent 名称对应的重写循环作为正式主表入口。
5. **P1 三层门控**：分别实现内容质量 gate、独立 D_gate 的正增益 gate、H_pass 回归 gate；相等不能晋升。
6. **P1 失败聚类与证据**：候选规则必须由多个去标识失败簇支持，并记录支持样本数、来源区、验证结果。
7. **P1 多语言补齐**：先把 Python/C++/Go 正式协议跑通，再增加 Java/JS Docker 验证器；未补齐前不能声称五语言实验完成。
8. **P2 冻结与复现 manifest**：哈希记录模型、经验库、检索器、prompt、采样参数、数据 manifest 和 validator image。

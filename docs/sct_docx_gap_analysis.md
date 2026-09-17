# 当前 SCT 实现与方法 DOCX 差异分析

> 2026-09-09 统一核心复核：已新增 `schemas.py`、`difference_analysis.py`、`validation_evidence.py`、`failure_clustering.py`、`experience_cards.py`、`candidate_gates.py` 和 `experience_lifecycle.py`。正式入口现在将候选经验隔离在临时目录，并在冻结后关闭 Base/Plus 反馈；下方历史逐条表格保留作为变更前证据，实施后的剩余限制见“统一核心复核结论”。

审计日期：2026-09-04（复核）

规范来源：`docs/面向多语言安全代码生成的经验自进化方法.docx`。本次以 DOCX 正文和 20 个表格的结构化提取结果为准。

## 总结

本审计与九条 baseline 的 CodeSecEval 对比运行相互独立。Baseline 使用 CodeSecEval 是实验设计要求，不构成 SCT 数据污染；下表中的“数据边界”只针对 SCT 自身的经验生成、门控、更新和最终评测路径。

下方“逐条需求映射”保留的是 2026-09-04 变更前审计，描述旧语言入口和 Coset Eagle 原型曾经存在的数据边界问题，不能直接当作 2026-09-11 当前实现状态。当前正式 PLT 入口已经把 Base/Plus 隔离为冻结后评测；旧入口仍只允许用于历史回放。

## 统一核心复核结论

- 图一差异分析现在输出 `DifferenceAnalysis` 六类字段，并保留解析错误、功能测试和安全测试是否测量的证据。
- 动态验证现在输出八类 `ValidationEvidence`；未配置 Docker、harness、静态分析器或类型检查器时状态为 `unmeasured`，不再默认算通过。
- 候选经验先写 `candidate_experiences.jsonl`，失败先脱敏并聚类；`candidate_gates.py` 严格要求 `ΔJointPass > 0`、H_pass 安全回归为零且功能退化不超过阈值。
- `run_sct_language_evolution.py` 是正式语言入口，`run_plt_self_evolution.py` 是 PLT 适配器，`finalize_plt_evaluation.py` 只负责冻结后 Base/Plus；`run_coset_eagle_experiment.py` 仍是原型/历史回放。
- 本次正式在线运行使用可用 PLT 的四分之一（353 条，D_init/D_grow/D_gate=118/118/117），生成 R0/R1 JSONL、候选门控和冻结清单；Base/Plus 分开评测且结果不回流经验库。实际模型为 `deepseek-v3.2`，Docker 预检为 29.4.2。
- 正确的冻结后评测结果是 Base 29/12/7、Plus 104/57/54（Function/Secure/Joint）。同一验证器上的官方 Secure Code 校准为 Base 115/115、Plus 140/140；校准仅证明 harness 可执行，不计入模型得分。

## 当前真实剩余限制（2026-09-11）

本轮应定位为“第一版可审计工程实验”，不能宣称 DOCX 方法已经完整实现：

1. 26 条候选经验的 `principle` 全部退化为“修复 training_validation 类目标语言实现错误，并保持安全后置条件”，`applicability` 也只有 CWE 编号和同一失败标签。失败聚类尚未细分语法、依赖、异常契约、输入边界和具体安全根因，因此经验内容的可操作性较弱。
2. runner 当前把 `memory[-8:]` 放入生成提示，只是固定窗口截取，不是从“问题 → 经验”的 embedding 语义检索；尚未训练或冻结独立检索器。
3. 正式运行使用 `candidate_gate_limit=1`：每条候选只在一条同 CWE 的独立 D_gate 任务上做成本受控预筛，不等价于让每条候选遍历完整 D_gate。26 次门控引用 26 条互异任务，其中 16 条有可执行动态测试，10 条没有；后者的 0→0 只表示缺少正增益证据，不能解释为经过真实动态验证。
4. PLT 原生 `capability/safety` 夹具仍只覆盖 353 条选样中的一部分：R0 动态执行 73/118，R1 动态执行 74/118；未执行项保持 `unmeasured`，不计作通过。
5. `freeze_metadata.json` 已记录 M* hash、模型和反馈关闭状态，但 `prompt_sha256`、`retriever_sha256` 仍为空。后续正式论文实验必须冻结实际 prompt 模板与 embedding 检索器版本/hash。
6. 当前 PLT 只有 Python；Java/JavaScript 尚未接入统一多源验证，多语言入口也尚未使用真实独立 D_gate manifest。多语言结论仍需 Python/C++/Go（再扩展 Java/JavaScript）的独立实验支持。

## 逐条需求映射（2026-09-04 变更前证据）

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

## 可运行性检查（2026-09-09）

### 1. 新实验从空目录启动

统一 schema、PLT 适配器和四个入口已可从空输出目录导入；`--help` 烟测全部退出 0。离线 PLT 结构烟测命令为：

```text
python methods/sct_agent/run_plt_self_evolution.py --offline --smoke --eval-limit 1
```

该命令可生成四分之一选样 manifest；最新正式在线结果保存在 `translation_work/sct_runs/plt_python_quarter_353_20260910_132431/`。本轮使用 ChatAnywhere `deepseek-v3.2`；PLT 训练侧不依赖 Docker，Base/Plus 使用 Python Docker 验证器并先做 daemon 预检。

### 2. Coset Eagle 主入口兼容性

`python methods/sct_agent/run_coset_eagle_experiment.py --help` 已可直接运行。入口现在显式加入 `methods/legacy_prompt_adapters`，但仍标记为原型/历史回放，不写入正式 SCT 结果。

```text
prototype/legacy replay only
```

### 3. Python 验证边界

PLT 训练侧不依赖 Docker，使用本地 `python -I` 子进程执行 `capability/safety` 数据驱动测试；CodeSecEval Base/Plus 仍调用 `python_validator` Docker 后端。两者的验证级别和结果用途不同，不能混写。

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

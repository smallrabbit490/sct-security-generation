# SCT 轨迹对比式自进化（新方案）实施规划

日期：2026-09-15
来源：老师指导方案（四态轨迹对比 + 两阶段演进 + 子 Agent 协同）

> 本文是「开发实施计划」，用于拆解落地步骤；正式方法协议仍以
> `docs/面向多语言安全代码生成的经验自进化方法.docx` 与评测协议为准。

## 0. 结论先行

新方案 = 在现有两套实现之上，补三块真正缺失的能力：

1. **四态正交化 + 轨迹转移对比**（B→A 正例、B→C/A→C 反例）——现有
   `sct_lifecycle_replay/trajectory_validation.py` 已有 7 类失败字符串，但没
   有显式 A/B/C/D 四态，也没有「同一任务多轮的状态转移」与「对比式经验沉淀」。
2. **子 Agent 四步流水线**（Analysis / Retrieval / Planning / CodeGen）——现有
   是单一 prompt 生成，无拆分的、可独立优化的规划/分析/生成模块。
3. **检索对齐**（正例经验排序优先于负例/反例）——现有 `retriever.py` 是 TF-IDF，
   无正负例对齐目标，也无可训练的 embedding 检索器。

可直接复用的既有资产（不重造轮子）：

| 资产 | 位置 | 复用方式 |
|---|---|---|
| 八类验证证据 | `methods/sct_agent/validation_evidence.py` | 四态判定的输入（functional/security 状态） |
| TF-IDF 检索器 | `methods/sct_lifecycle_replay/retriever.py` | 检索对齐的基线，叠加正负例打分 |
| 经验状态机 | `methods/sct_lifecycle_replay/experience_lifecycle.py` | 经验自洁（promote/demote/retire） |
| 门控 | `methods/sct_agent/candidate_gates.py` + `sct_lifecycle_replay/audit_runner.py` | 候选晋升/拒绝 |
| 冻结评测 | `methods/sct_lifecycle_replay/frozen_evaluation.py` | Base/Plus 隔离 |
| 经验卡 + 泄露检查 | `methods/sct_agent/experience_cards.py` | 正例卡复用；负例卡新增类型 |

## 1. 架构总览

```
                ┌────────────────────────────────────────────────────┐
                │              Agent 四步流水线（无训练版）            │
 任务/初始代码 ─► [1.Analysis] ─► [2.Retrieval] ─► [3.Planning] ─► [4.CodeGen] ─► 候选代码
                └────────▲───────────────▲────────────────────────────┘       │
                         │               │                                    ▼
                   (正/负例经验)    (检索对齐打分)                       动态测试(Func×Sec)
                         │               │                                    │
                ┌────────┴───────────────┴────────────────────────────────────┘
                │             轨迹转移对比反思引擎                            │
                │   B→A  → 正例经验卡 (Fix Pattern)                           │
                │   B→C/A→C → 负例约束卡 (Avoidance Rule)                     │
                └─────────────────────────────────────────────────────────────┘
```

新增模块（落点待拍板，见 §4 D1，暂用 `methods/sct_trajectory/`）：

```
methods/sct_trajectory/
├── __init__.py
├── schemas.py                 # FourState、RolloutTrace、Transition、NegativeConstraint
├── four_state.py              # 四态判定 state_from_evidence()
├── trajectory_reflection.py   # 轨迹转移对比：正例卡 / 负例卡
├── agent_pipeline.py          # 四步子 Agent（Analysis/Retrieval/Planning/CodeGen）
├── retriever.py               # 检索对齐（复用 TF-IDF + 正负例打分）
├── closed_loop.py             # 编排：rollout → 反思 → 门控 → 自洁
└── run_closed_loop.py         # 命令行入口（训练侧 PLT）
```

## 2. 分阶段实施（每阶段均有可验证产物）

> 通用验收：`python -m compileall methods/sct_trajectory tests`、`python -m pytest -q`
> 每阶段新增模块的 docstring 必须说明：所属阶段、输入输出、验证证据、失败类型、
> 是否允许修改长期经验库（遵循 AGENTS.md 第八节）。

### 阶段 0：四态判定与轨迹 schema（地基）

- 新增 `schemas.py` + `four_state.py` + `tests/test_four_state.py`
- `FourState(A/B/C/D)`；`state_from_evidence(functional_status, security_status)`；
  `RolloutTrace`（task_id、每轮状态列表、转移列表）；`Transition(from, to)`
- 四态↔三口径映射：A=Joint、B=Function-only、C=Secure-only、D=neither（主指标仍为
  Function/Secure/Joint，四态仅作诊断/轨迹层）
- **可验证产物**：`test_four_state.py` 通过（覆盖 4 态判定 + 映射 + B→A/B→C/A→C 转移
  构造）；`python -m pytest tests/test_four_state.py -q` 全绿

### 阶段 1：轨迹转移对比引擎（最核心、最便宜）

- 新增 `trajectory_reflection.py` + `tests/test_trajectory_reflection.py`
- 输入 `RolloutTrace`（多轮状态序列），输出：`build_positive_cards(B→A)` →
  `ExperienceCard`；`build_negative_constraints(B→C/A→C)` → `NegativeConstraint`
  （新 schema：cwe + 被禁止的"过度防御"模式 + 触发的功能退化证据）
- 正例卡复用 `experience_cards.card_is_safe` 泄露检查；负例卡同样过泄露检查
- **可验证产物**：单元测试用确定性 fixture 造出 B→A 与 B→C 两类产出，断言字段完整、
  无任务 ID/答案泄露；离线 fixture 输出 `cards.jsonl`

### 阶段 2：子 Agent 四步流水线（无训练版）

- 新增 `agent_pipeline.py` + `tests/test_agent_pipeline.py`
- 四个独立 prompt 函数：`analyze(context)` → `retrieve(query, memory)` →
  `plan(analysis, cards)` → `generate(plan, cards)`，各自返回可校验结构
- Planning 输出格式约束：`[保持不变的业务逻辑] + [最小安全改动点] + [潜在退化自检]`
  （正则/字段校验，不依赖 LLM 也能测格式）
- **可验证产物**：`test_agent_pipeline.py` 验证 planning 输出格式；`run_closed_loop.py
  --smoke --limit 1` 走完四步产出代码（离线或 1 次真实 API 均可）

### 阶段 3：检索对齐

- 新增 `retriever.py` + `tests/test_retriever_align.py`
- 基线复用 `sct_lifecycle_replay.retriever.ExperienceRetriever`（TF-IDF），叠加
  `align_score(card, polarity)`：正例卡加分、负例/反例卡降权，使
  `Rank(A-exp) > Rank(C-exp)` 在构造 fixture 上成立
- embedding 检索器 `embedding_retriever.py` 作为 **P2 可关停** 接口预留（同签名，
  首版不实现训练）
- **可验证产物**：`test_retriever_align.py` 断言正例排序先于反例；检索结果 JSONL

### 阶段 4：闭环整合 + 经验自洁 + 门控

- 新增 `closed_loop.py` + `run_closed_loop.py` + `tests/test_closed_loop.py`
- 编排：多轮 rollout（初始 + 有限修复）→ 反思产出正/负例 → 复用
  `candidate_gates`/`audit_runner` 门控 → `ExperienceMemory` 状态机做自洁
  （support_count/contradiction_count、demote/retire）
- 信号边界：**仅训练侧 PLT**（见 §4 D2）
- **可验证产物**：`test_closed_loop.py` + `--smoke --limit N` 产出
  `trajectories.jsonl`、`candidates.jsonl`、`gate_records.jsonl`

### 阶段 5：冻结 + 评测隔离

- 复用 `frozen_evaluation.check_frozen_run`；新增四态汇总报告
  （A/B/C/D 计数 + B→A/B→C 转移统计）
- **可验证产物**：`test_frozen_isolation.py`（冻结后写经验必抛异常）+ 冻结评测
  smoke + `four_state_summary.json`

### 阶段 6：文档与全量回归

- 新增 `docs/sct_trajectory_contrastive.md`（中文用户说明）+ README 建链接
- 全量 `pytest` + `compileall` + 敏感信息扫描（`rg "sk-[A-Za-z0-9]|api_key"`）
- **可验证产物**：全量测试绿 + 无密钥命中 + README 链接可用

## 3. 数据边界红线（不可违反）

- 闭环进化的四态/轨迹信号**只能来自训练侧 PLT（D_init/D_grow/D_gate）**；
- **Base/Plus 永远是冻结后的最终离线评测**，其 Function/Secure 结果不得回流到
  经验生成、门控、检索对齐或任何模型更新（AGENTS.md 硬性规定）；
- 冻结后 `feedback_channel=disabled`，任何写记忆操作抛异常。

## 4. 已冻结决策（2026-09-15 拍板）

- **D1 代码落点**：新建 `methods/sct_trajectory/`（独立承载新范式，复用既有验证器/
  检索器/门控，不碰已冻结的 `sct_agent` 与已审计的 `sct_lifecycle_replay`）。
- **D2 信号边界**：闭环进化的四态/轨迹反馈**只能来自训练侧 PLT**；Base/Plus 永久
  冻结为其最终离线评测，结果永不回流（AGENTS.md 硬性红线）。
- **D3 训练范围**：第一版**全无训练**（四态+轨迹对比+TF-IDF 检索+prompt 层四步
  Agent）；embedding 对齐与 DPO/PRM 作为 P2 预留接口，可关停。
- **D4 子 Agent 拆分**：四步 prompt 层拆分（Analysis/Retrieval/Planning/CodeGen），
  无训练，Planning 加格式约束。

## 5. 默认参数（未列入拍板点，可后续调）

- rollout 轮数：初始 1 轮 + 修复 1 轮（`repairs=1`，与现有 trajectory_runner 一致）
- 模型：`deepseek-v3.2`（沿用现有 PLT 配置）；后端：ChatAnywhere
- 候选最小支持样本：同一 (CWE, 转移类型) ≥ 2 条（沿用 candidate_builder）
- 主评测口径不变：Function / Secure / Joint（A 态占比），四态只做诊断

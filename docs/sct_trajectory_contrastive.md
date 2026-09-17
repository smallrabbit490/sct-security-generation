# SCT 轨迹对比式自进化（CLE）

> 面向用户的说明。开发实施计划见 `docs/superpowers/plans/2026-09-15-sct-trajectory-contrastive.md`。

## 一句话

在原「离线经验蒸馏 + 门控 + 冻结评测」之上，新增**在线闭环**：用「功能 × 安全」两个
测试维度把每次生成的轨迹归入四态 A/B/C/D，再把**状态转移**沉淀为对比式经验——
`B→A` 是正例（保功能的安全修复），`B→C` 是反例（过度防御破坏功能），
无改善/恶化（B→B/D→D/C→C）沉淀到错题本。

## 四态与主指标映射

| 态 | Functional | Security | 对应主指标 |
|---|---|---|---|
| A | ✓ | ✓ | Joint pass（理想终态） |
| B | ✓ | ✗ | Function-only（有漏洞） |
| C | ✗ | ✓ | Secure-only（过度防御/破坏性修复） |
| D | ✗ | ✗ | 完全失败 |

主评测口径仍为 **Function / Secure / Joint**（A 态占比），四态只用于诊断与轨迹对比。

## 代码结构（`methods/sct_trajectory/`）

| 模块 | 职责 |
|---|---|
| `schemas.py` | `FourState` / `Transition` / `RolloutTrace` / `NegativeConstraint` |
| `four_state.py` | 四态判定 + 8 类跃迁分类（对齐 DOCX 表 1） |
| `hsk_tree.py` | HSK-Tree 4 层树 + 拓扑演化（吸收/新建/归并/剪枝/效用衰减） |
| `error_ledger.py` | 错题本 + 三大消费（回放偏置 / Analysis 预警 / 归并负向边界） |
| `active_replay.py` | 两阶段受控调度（规则配额初筛 + LLM 有界筛选，真实调 AI） |
| `agent_pipeline.py` | 四步 Agent（Analysis/Retrieval/Planning/CodeGen，局部补丁合成） |
| `distillation.py` | 独立 LLM 元认知（归因 + 去特化 + 全状态无偏反思） |
| `retriever.py` | HSK-Tree 检索（CWE 硬路由 + active/language 过滤 + 效用分 + LLM 打分） |
| `split.py` | 三池原子划分（同 Seed Family 整体只入一池） |
| `gates.py` | Gate1 召回探针 / Gate2 ΔJointPass / Gate3 降噪回归（τ_sec=1 + N=3 多数决） |
| `closed_loop.py` | `CleRunner`：Phase1 冷启动 → Phase2 进化 → Phase3 门控拓扑 |
| `frozen.py` | 冻结守卫 + 四态汇总报告 |
| `run_closed_loop.py` | 命令行入口（真实调用 AI） |

## 运行（真实调用 AI）

```powershell
# 端到端冒烟：跨 CWE 采样少量训练侧任务，真实调用 deepseek-v3.2
python -m methods.sct_trajectory.run_closed_loop --smoke --limit 12 --out translation_work/diagnostics/<date>/sct_trajectory_smoke

# 禁用 LLM 检索打分（退化为确定性 TF-IDF）
python -m methods.sct_trajectory.run_closed_loop --limit 12 --no-align --out <dir>
```

## 信号边界（硬性红线）

- 闭环进化的四态/轨迹/检索对齐信号**只来自训练侧 PLT**（`data/external/secodeplt`）。
- **Base/Plus 永远是冻结后的最终离线评测**，其测试结果永不回流到经验生成、门控、
  检索对齐或任何模型更新。
- 三池（source/replay/audit）按 Seed Family 原子划分，同族变体不跨池。

## 验证证据（每阶段可验证产物）

| 阶段 | 产物 | 验证方式 |
|---|---|---|
| A | HSK-Tree + 拓扑演化 | `pytest tests/test_hsk_tree.py` |
| B | 8 类跃迁分类 | `tests/test_four_state.py` |
| C | 错题本 + 主动回放调度 | `tests/test_error_ledger.py` + `test_active_replay.py` |
| D | 四步流水线 | `tests/test_agent_pipeline.py` + 真实 smoke |
| E | Distillation | `tests/test_distillation.py` + 真实 smoke |
| F | 检索器 | `tests/test_retriever_align.py` + 真实 smoke |
| G | 三池划分 + 门控 + 闭环 | `tests/test_split.py` + `test_gates.py` + 端到端真实 smoke |

真实端到端证据（2026-09-15，跨 CWE 采样 12 任务）：
`translation_work/diagnostics/20260915/cle_docx_extract/closed_loop_real.json`——
Phase1 严格二分分流（seed_active / seed_grounding_failure）、Phase2 全状态无偏反思
（C→C/D→D 沉淀错题本）、LLM 有界筛选选中薄弱 CWE 任务。

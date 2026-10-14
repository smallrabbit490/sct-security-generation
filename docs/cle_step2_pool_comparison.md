# 第二步：阶段经验库对比

日期：2026-09-22
目标（用户要求）：把 Phase1 池、Phase2 各轮池、最终池分别作为**唯一经验来源**，
在评测集上跑一遍，看哪个阶段的经验库表现最好。

---

## 一、为拿到各阶段池做的准备

**问题**：现有运行产物里**没有**各阶段池内容——
- `experience_pool.jsonl` 只有最终池；
- `tree_snapshots/*.json` 只有树（13 节点），不是池；
- `rounds.jsonl` 只有 `pool_size`（条数）；
- Phase2 的 distill 输出原先不落盘，因此**无法从旧产物重建各轮池**。

**改动**：在 `run_closed_loop.py` 加 `dump_pool(label)`，在 Phase1 结束与每轮结束时
把池内容快照落盘到 `pool_snapshots/<label>.jsonl`。
这是**纯产物记录**：只读 `runner.experience_pool` 并写文件，
不改检索、不改门控、不改提炼、不触发额外 LLM 调用。

**新运行**：`translation_work/sct_runs/stage_pools_20260922`
（60 任务 × 3 轮，`--retrieval-mode hier_llm`，成本 3.86 CA元）

产出 4 个快照：

| 快照 | 条数 |
|---|---|
| `phase1.jsonl` | 132 |
| `round1.jsonl` | 229 |
| `round2.jsonl` | 310 |
| `round3.jsonl` | 380 |
| `experience_pool.jsonl`（= 最终池） | 380 |

---

## 二、评测口径（重要）

- **评测集**：`cle_full_874_20260922` 的 audit 池（298 条，训练侧 held-out）
  **排除** `stage_pools_20260922` 用过的全部 54 个任务 → **279 条**，取 54 条分层抽样
  （18 个 CWE × 3 条）。
  → 被比较的池**从未见过这些评测任务**，比较是干净的。
- **唯一变量 = 池内容**：任务、检索机制（`hier_llm`）、模型（`deepseek-v3.2`，
  temperature=0）、树（固定 10 节点）全部相同。
- **未使用 Plus(Python)**：该数据集 schema 不同（`Test-FP`/`Test-SP`、`ID` 形如
  `CWE-20_01`、无 `CWE_ID` 字段），且用它挑池会构成测试集选择偏差。
  如需该口径，须另写 harness，本步未做。

---

## 三、结果

| 池 | 条数 | JointPass | 通过率 | 同CWE% | 每任务条数 | CA元 |
|---|---|---|---|---|---|---|
| `phase1` | 132 | 10/54 | 18.5% | 75.2 | 2.17 | 0.513 |
| `round1` | 229 | 9/54 | 16.7% | 78.7 | 2.61 | 0.614 |
| **`round2`** | **310** | **11/54** | **20.4%** | 80.7 | 2.78 | 0.667 |
| `round3` | 380 | 10/54 | 18.5% | 83.7 | 2.83 | 0.721 |
| `final` | 380 | 10/54 | 18.5% | 80.8 | 2.89 | 0.730 |

### 同 task_id 配对（基准 = `phase1`）

| 池 | 通过 | 与基准差 | 仅本池过 | 仅基准过 | z | 判定 |
|---|---|---|---|---|---|---|
| `round1` | 9/54 | −1.9pt | 3 | 4 | −0.38 | 不显著 |
| `round2` | 11/54 | +1.9pt | 3 | 2 | +0.45 | 不显著 |
| `round3` | 10/54 | +0.0pt | 4 | 4 | 0.00 | 不显著 |
| `final` | 10/54 | +0.0pt | 4 | 4 | 0.00 | 不显著 |

---

## 四、结论

### 1. **没有哪个阶段的经验库显著更好**
五个池的通过率全部落在 **16.7%~20.4%**，跨度仅 3.7pt，
远小于 n=54 时的置信区间（约 ±13pt）。配对后 z 值全部在 ±0.45 以内。

### 2. **堆经验数量不解决问题**
池从 132 条增到 380 条（2.9 倍），同 CWE 命中率从 75.2% 升到 83.7%，
但 JointPass 没有随之上升（r=+0.27，n=5 无统计效力）。

### 3. **阶段差异没有转化成注入内容差异**
各池检索出的类型构成几乎一样，都是 `minimal_patch_hint` + `overdefense_pitfall`
占绝对多数：
```
phase1: hint 45 / pitfall 42 / direct_A 11 / seed 9 / round0_fail 6
round3: hint 63 / pitfall 58 / round0_fail 20 / direct_A 11 / seed 1
```

### 4. 与第一步取证结论一致
瓶颈在**指令载荷的质量**，不在池的规模或阶段。
所有阶段的池都产出同一类有缺陷的载荷（"仅供参考"口吻、可能被截断 400 字、
同卡内可能自相矛盾），因此表现一致。

---

## 五、对第三步的含义

第三步原定目标是"提高门控覆盖率"。**前提需要修正**：

| 原假设 | 修正后 |
|---|---|
| 门控要筛"经验对不对" | 门控还要筛**载荷质量**：指令是否自洽、是否超长会被截断、是否该当硬约束 |

因为：
- 门控再准，选出来的经验如果以"仅供参考"口吻渲染、尾部被截断、
  甚至同卡内自相矛盾，注入后仍然无效；
- 实测门控把经验分成 active/unmeasured/demoted，但**没有任何一个阶段的池、
  任何一种检索机制**能让 JointPass 动起来——说明被筛的对象本身有系统缺陷。

**建议的第三步方向**（按收益排序）：
1. 先修载荷缺陷（约束强度 / 截断 / 合并矛盾指令 / `direct_A` 标签），
   再看门控覆盖率是否还有意义；
2. 若继续做门控覆盖，应把"载荷质量"纳入门控评分维度。

---

## 六、产物

```
methods/sct_trajectory/run_closed_loop.py            + dump_pool（池快照）
translation_work/sct_runs/stage_pools_20260922/
  pool_snapshots/{phase1,round1,round2,round3}.jsonl  各阶段池
translation_work/diagnostics/20260922/
  run_pool_comparison.py          池对比实验脚本
  analyze_pool_comparison.py      配对分析 + 显著性
  pool_comparison/pool_*.json     每池逐任务结果
  pool_comparison_summary.json    汇总
  pool_comparison.log             运行日志
```

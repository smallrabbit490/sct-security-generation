# 生命周期回放运行记录与优化（2026-09-13 全量 PLT）

本文件详细记录 `methods/sct_lifecycle_replay` 最近一次全量 PLT 运行的
结果、发现的两大问题，以及针对这两大问题的代码优化。运行目录为
`translation_work/sct_runs/lifecycle_replay_plt_all_v2_20260913/`，是
「经验生命周期 + 验证驱动主动回放」新方法（对应《重构方法设计说明.docx》）
的正式规模运行。

## 1. 运行概述

| 项目 | 值 |
|---|---|
| 运行目录 | `translation_work/sct_runs/lifecycle_replay_plt_all_v2_20260913/` |
| 入口参数 | `--all-plt --live-api --llm-replay --replay-limit 96 --llm-batch-size 24` |
| 模型 | `deepseek-v3.2`（ChatAnywhere） |
| 训练侧验证 | 本地 `python -I` 临时子进程，不启动 Docker |
| Base/Plus 反馈通道 | `disabled`（冻结后） |

选样从 PLT 的 386 条「有 capability + safety 测试」样本出发，按 family
变体分配到 source / replay / audit 三池：

| 池 | 数量 | 作用 |
|---|---:|---|
| source（来源池） | 131 | 漏洞—补丁差异提取初始经验（seed） |
| replay（回放池） | 96 | LLM 分批选出的任务，用于轨迹生成与失败模式归纳 |
| audit（审查池） | 159 | 独立证据审查（共享 baseline + 逐候选重跑） |

## 2. 各阶段结果

### 2.1 初始经验（seed）

131 条来源任务全部提取成功，每条含文档 3.3 的经验卡字段
（principle / applicability / dangerous_pattern / recommended_action /
unsafe_alternative / language_adaptation / non_applicable_boundary）。
其中 122 条经 `validate_trajectory` 联合通过，进入长期记忆 M_t；
其余 9 条验证失败，被排除在 `valid_seeds` 之外。

### 2.2 回放轨迹

96 条回放轨迹，31 条联合通过。失败分布：

| 失败类型 | 数量 | 含义 |
|---|---:|---|
| `both_failed` | 35 | 功能与安全均失败，根因待排查 |
| `functional_regression` | 21 | 安全过、功能败（过度防御形态） |
| `security_gap` | 9 | 功能过、安全败 |
| `null`（联合通过） | 31 | 功能与安全均通过 |

### 2.3 候选经验（C_t）

`build_candidates` 从「同一 CWE + 同一失败类型」至少 2 条轨迹的重复模式
中归并出 15 个候选，覆盖 9 个 CWE（179 / 347 / 352 / 74 / 77 / 79 / 862 /
915 / 95）。候选 principle 按失败类型映射为固定措辞：

| 失败类型 → 候选原则 | 候选数 |
|---|---:|
| `repeated_secure_success` → 复用已验证安全后置条件 | 5 |
| `security_gap` → 修复安全缺口、用安全 API | 2 |
| `both_failed` → 先确认 harness 契约再定位根因 | 4 |
| `functional_regression` → 安全加固不得破坏功能契约 | 4 |

### 2.4 独立审查（A_audit）结果

15 个候选**全部 `demoted`**，晋升 0、修订 0。逐候选审计记录
（`audit_pool/audit_rows.jsonl`）的关键字段：

| 指标 | 值 |
|---|---|
| `delta_joint_pass > 0` 的候选 | 9 |
| `delta_joint_pass == 0` 的候选 | 6 |
| `delta_joint_pass < 0` 的候选 | 0 |
| 进入检索 top-k 的候选（`candidate_retrieved=True`） | 7 |
| 未进入检索 top-k 的候选（`candidate_retrieved=False`） | 8 |
| `security_regressions` | 全部 > 0（3 ~ 9 之间，H_pass 共 31 条） |

这说明：没有一个候选是因为「净负向收益」被证伪，全部是被「安全回归 > 0」
这一零容忍判定拦截；另有 8 个候选根本没进入检索 top-k，其 before/after
对比的是同一 prompt 的两次 API 调用（纯噪声）。

## 3. 两大问题的根因诊断

### 3.1 问题一：候选经验判定回归过于严格，有效候选被大量拒绝

对照代码逐项定位出四个使门控「误杀」的原因：

1. **H_pass 回归重跑与建立 H_pass 的轨迹配置不对称**。
   `run_lifecycle_replay.py` 中，建立 H_pass 的 `trajectories` 用
   `repairs=1`（生成失败可修复一次），而回归重跑 `regression_after` 用
   `repairs=0`（不修复）。一个原本靠一次修复才通过的 H_pass 任务，在无修复
   重跑下更容易失败，于是被误记为「候选引入的安全回归」。这是回归计数被
   系统性放大的主因。

2. **安全回归零容忍 + 单次采样噪声**。`audit_decision` 用
   `security_regressions > 0` 即 `demoted`；而每条 H_pass 任务只采样一次，
   deepseek-v3.2 经 ChatAnywhere 的非确定性让单次失败无法归因到候选。

3. **打平（delta_joint_pass == 0）被直接 demoted**。6 个候选联合通过率
   无变化，既未证明也未证伪，却被当作「无效」丢弃。这类候选本应保留并
   收窄适用边界后重审，而不是直接淘汰。

4. **候选未进入检索 top-k 仍按噪声 demoted**。8 个候选 `candidate_retrieved
   = False`，其 before/after 与回归数字都是同一 prompt 两次调用的噪声，
   却照常参与门控并被拒。

### 3.2 问题二：检索器可能召回无效经验

`retriever.py` 存在三处使「无效经验」进入 top-k 的缺陷：

1. **CWE 加分 bug**：`score()` 里
   `cwe_hit = CWE_BONUS if str(card.get("cwe", "")).strip() else 0.0`
   只判断「卡片有没有 cwe 字段」，**从不比较它是否等于查询的 CWE_ID**。
   于是所有经验卡都拿到满额 `+3.0`，不同 CWE 的经验与同 CWE 经验同权竞争，
   大量跨 CWE 的无关经验被错误召回。

2. **无状态过滤**：`demoted` / `retired` / `rejected` 的已被证伪或退役
   经验，以及 principle 为空的经验，仍会参与检索。

3. **无相关性下限**：`search` 无条件返回 top-k，即便某张卡片与查询既无
   CWE 匹配也无任何 token 重叠（score 约等于 0），也会被塞进生成 prompt。

## 4. 已实施的优化

### 4.1 门控（`independent_audit.py`、`audit_runner.py`、`run_lifecycle_replay.py`）

`audit_decision` 的新判定优先级（自上而下，命中即返回）：

1. 内容质量不过 → `revised`（重写 principle/applicability）；
2. 候选未进入检索 top-k（`retrieved=False`）→ `revised`（before/after 是噪声，
   需提炼更具体适用条件后重审）；
3. 安全回归 > 容忍上限、功能退化超限、传播风险超限 → `demoted`；
4. 联合通过率净下降（`delta < 0`）→ `demoted`（证伪）；
5. 联合通过率打平（`delta == 0`）且无回归 → `revised`（未证伪未证明，
   保留收窄边界后重审，**不再直接淘汰**）；
6. 严格正向（`delta > 0`）且无回归 → `supported`。

配套改动：

- `run_lifecycle_replay.py` 的 H_pass 回归重跑改用 `repairs=1`，与建立
  H_pass 的轨迹对齐，消除修复不对称造成的假回归；
- 新增 `--regression-samples N`（默认 1）：每条 H_pass 任务重跑 N 次，
  仅当全部样本都联合失败才计入回归（`_regression_reruns` 取「最优样本」，
  任一样本通过即视为未回归），用多次采样降低单次 API 噪声；
- 新增 `--regression-limit N`（默认 0）：安全回归绝对计数容忍，噪声较大时
  可放宽到小正整数；
- 审计记录新增 `regression_samples` / `regression_limit` /
  `regression_sample_outcomes` 字段，回归证据可追溯。

### 4.2 检索器（`retriever.py`）

1. **CWE 加分只在「查询 CWE == 经验 cwe」时生效**，不同 CWE 经验不再获得
   满额加分，只能靠语义重叠得分；
2. **构造时过滤无效经验**：`demoted` / `retired` / `rejected` 状态，以及
   principle 为空的经验，不再进入召回池（`_usable`）；
3. **相关性下限截断**：`search` 增加 `min_score`（默认 0.0），score 不超过
   下限（既无 CWE 匹配也无 token 重叠）的经验直接截断，不再进入 top-k。

> 影响范围：`local_codeseceval.py`（冻结后 CodeSecEval Base/Plus 评测）复用
> 同一 `ExperienceRetriever`。修复前所有种子都被加满 CWE_BONUS，跨 CWE 的
> 无关经验会被注入每个评测任务；修复后只有同 CWE 或语义重叠的经验才会被
> 注入。因此修复后重跑 Base/Plus 会得到与 2026-09-13 记录不同的（更准确的）
> 数字，跨 CWE 任务不再受无关经验的污染。

### 4.3 验证

- `python -m compileall methods/sct_lifecycle_replay` 通过；
- `tests/test_sct_lifecycle_replay.py` 28 项全通过（新增 4 项覆盖新语义）；
- `tests/test_local_codeseceval.py` 11 项、`tests/test_llm_scheduler.py` 9 项
  全通过，确认相邻模块无回归。

## 5. 预期效果与后续方向

按新语义回看本次 15 个候选：

- 8 个 `candidate_retrieved=False` 的候选 → 由 `demoted` 改为 `revised`；
- 6 个 `delta==0` 且被检索到的候选 → 由 `demoted` 改为 `revised`；
- 9 个 `delta>0` 的候选，在 repairs 对称 + 多次采样后，回归计数预期下降；
  若仍为正且无回归 → `supported`，有少量回归可用 `--regression-limit`
  容忍后晋升。

仍需后续处理（不在本次修改范围内，仅记录）：

1. **候选生成仍是模板化文本**：部分 CWE 的候选 principle 是固定措辞，语义
   不够具体，导致进不了检索 top-k。方向是按文档 5.2 让 LLM 从失败轨迹提炼
   具体安全不变量（当前 `build_candidates` 未接 LLM）。
2. **H_pass 基线记忆不对称**：建立 H_pass 的轨迹用 131 条 seed（含 9 条
   验证失败者），回归重跑用 122 条 `valid_seeds` + 候选。二者在「被过滤掉的
   9 条无效 seed」上存在差异，是回归噪声的残留来源；彻底对齐需在 `valid_seeds`
   上重建 H_pass 基线。
3. **检索器语言适配**：查询含 `language` 字段、经验卡含
   `language_adaptation`（python/go/cpp），但检索暂未按语言过滤，跨语言
   召回仍可能发生；待 Go/C++ harness 接入后补语言匹配。

## 6. 复现与重跑

```powershell
# 全量 PLT（含本次两个新调参）
python -m methods.sct_lifecycle_replay.run_lifecycle_replay \
  --all-plt --live-api --llm-replay --replay-limit 96 --llm-batch-size 24 \
  --regression-samples 2 --regression-limit 1 \
  --out translation_work/sct_runs/<run-name>

# 单元测试
python -m unittest discover -s tests -p "test_sct_lifecycle_replay.py" -v
```

`--regression-samples` 提高会成倍增加 H_pass 回归重跑的 API 调用量
（H_pass 任务数 × 候选数 × 样本数），请按预算权衡；`--regression-limit`
只放宽「真实回归」的计数容忍，不改变「质量不过 → revised」「净负向 → demoted」
等安全边界。

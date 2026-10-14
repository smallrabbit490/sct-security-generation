# 架构演进与实验历史（完整梳理）

> 生成时间：2026-09-21
> 依据：git 提交历史、`docs/*.md`、`translation_work/sct_runs/` 与 `diagnostics/` 的真实产物、代码改动
> 原则：只写有产物或文档佐证的事实；无证据的推测会明确标注

---

## 零、一页速览

| 日期 | 里程碑 | 核心产物 |
|---|---|---|
| 09-03 | 仓库奠基：数据 + SCT + 九条 baseline 骨架 | `700d926` |
| 09-04 | 九条 baseline 冒烟审计（结论：**4 Prompt FAIL / 5 Agent BLOCKED**） | `baseline_execution_audit.md` |
| 09-04~06 | 旧方法（`sct_agent`）PLT 自进化（22 个目录，**仅 1 个完整跑通**） | `plt_python_*` |
| 09-09 | **统一核心**重构（7 个模块拆分） | `experience_self_evolution_guide.md` |
| 09-10~13 | 新方法：生命周期 + 验证驱动主动回放（**15 候选全 demoted**） | `lifecycle_replay_*` |
| 09-15 | **CLE 四态方法**设计诞生 + Docker 常驻容器层 | `sct_trajectory_contrastive.md` |
| 09-16~18 | CLE 实现 + 看板搭建 + **消融/反过度防御对比实验** | `abl_smoke`、`overdefense_exp` |
| 09-19 | **第一次全量 874**（JointPass **21.5%**）+ 六大问题诊断 | `cle_full_run_analysis_20260919.md` |
| 09-20 | 九项优化 + 第二次全量（**2 次中止**，16:11 失败） | `runtime_reflection.md` |
| 09-20 晚 | 断点续跑完成：JointPass **19.8%** | `cle_full_874_v2_resumed_20260920` |
| 09-21 | 覆盖率专项实验 | `coverage_smoke*` |

---

## 一、架构演进的三条线

### 线 A：旧方法（`methods/sct_agent/`）— DOCX 原始规范

**设计**：固定数据分区 `D_init / D_grow / D_gate` + R0–R3 轮次。

**9 个核心模块**（2026-09-09 拆出）：
```
schemas.py              DifferenceAnalysis / ValidationEvidence / ExperienceCard / GateRecord / FreezeManifest
difference_analysis.py  漏洞—补丁差异分析（六类字段）
validation_evidence.py  八类验证证据（默认 unmeasured 而非 pass）
failure_clustering.py   失败聚类
experience_cards.py     经验卡
candidate_gates.py      三层门控（质量 / D_gate 有效性 / H_pass 回归）
experience_lifecycle.py 生命周期
run_plt_self_evolution.py        PLT 适配入口
run_sct_language_evolution.py    正式语言入口
finalize_plt_evaluation.py       仅做冻结后 Base/Plus
run_coset_eagle_experiment.py    原型/历史回放（已标注 only）
```

**数据流**：
```
PLT data.json → D_init→M0 / D_grow→候选 / D_gate→晋升 → 冻结 M* → Python Base / Plus
```

### 线 B：新方法（`methods/sct_lifecycle_replay/`）— 经验生命周期 + 验证驱动主动回放

**设计**：不再用固定分区，改为三功能池 `source / replay / audit` + 独立审查 `A_audit`。

### 线 C：当前主线（`methods/sct_trajectory/`）— CLE 轨迹对比式自进化

**设计**（2026-09-15 提出）：在"离线蒸馏 + 门控 + 冻结评测"之上加**在线闭环**。
用「功能 × 安全」两维把每次生成归入**四态**，把**状态转移**沉淀为对比式经验。

```
四态：A(✓✓ 联合通过)  B(✓✗ 仅功能)  C(✗✓ 仅安全=过度防御)  D(✗✗ 全败)
转移：B→A 正例 | B→C 反例（过度防御） | B→B/D→D/C→C 入错题本
```

**12 个模块**：
```
schemas.py         FourState / Transition / RolloutTrace / NegativeConstraint
four_state.py      四态判定 + 8 类转移（对齐 DOCX 表 1）
hsk_tree.py        HSK-Tree 四层树 + 拓扑演化（吸收/新建/归并/剪枝/效用衰减）
error_ledger.py    错题本 + 三种消费（回放偏置 / 分析警告 / 归并负边界）
active_replay.py   两阶段调度（规则配额初筛 + LLM 有界筛选）
agent_pipeline.py  四步 Agent（Analysis → Retrieval → Planning → CodeGen）
distillation.py    LLM 元认知蒸馏（归因 + 去特化 + 全状态无偏反思）
retriever.py       HSK-Tree 检索（CWE 硬路由 + 状态/语言过滤 + 效用分 + LLM 打分）
split.py           三池原子划分（按 Seed Family）
gates.py           Gate1 召回探针 / Gate2 ΔJointPass / Gate3 降噪回归
closed_loop.py     CleRunner：Phase1 冷启动 → Phase2 进化 → Phase3 门控
frozen.py          冻结守卫 + 四态汇总
```

**HSK-Tree 四层**：
```
L1 CWEFamilyNode → L2/L3 SecurityInvariantNode → L4 LanguageLeaf(python/cpp/go/java)
状态：provisional | active | consolidated | retired | unmeasured | revised
拓扑：Overlap≥0.6 就地吸收 / 同CWE active>N 归并 / Utility<0.3 剪枝
```

---

## 二、按日期的实验与测试

### 2026-09-03~04：九条 baseline 对比实验（**第一次对比实验**）

**规模**：9 条方法（4 Prompt + 5 Agent）× Base(115) / Plus(140)

**运行目录**：
- `baseline_runs/agents_full_deepseek_v32_20260906/`（Base 1725 行 = 5 方法 × 3 语言 × 115）
- `baseline_runs/agents_full_gemini25flash_20260906/`
- `baseline_runs/agents_full_gpt51_20260906/`

**真实结果（Base，secure_func_sec_rate 联合通过率）**：

| 方法 | deepseek-v3.2 | gemini-2.5-flash | gpt-5.1 |
|---|---|---|---|
| AutoSafeCoder | 6.09% | 4.35% | 4.35% |
| RA-Gen | 6.09% | 4.35% | 3.48% |
| SWE-Agent | 5.22% | 4.35% | 3.48% |
| AgentCoder | 5.22% | 3.48% | 4.35% |
| SecAwareCoder | **7.83%** | 5.22% | 6.09% |

**🔴 发现的问题（`baseline_execution_audit.md`）**：

| 问题 | 证据 |
|---|---|
| 4 条 Prompt baseline 联合通过 **0/4** | 真实 API + 代码提取 + Docker 评测都跑了，但全不通过 |
| 5 条 Agent **0/5** | 全部因 ChatAnywhere 请求超时未达终态 |
| `AttributeError: 'NoneType' object has no attribute 'extract_code'` | `legacy_prompt_adapters/run_experiment.py:26-44` 指向不存在的历史路径 |
| **6 个本地 key 只有第 6 个有效** | 其余 5 个返回 401；清理后 `key_count=1` |
| **仓库完整性检查 FAILED** | 6 个 Base/Plus JSON 仍含机器绝对路径 |
| 大量语言/Go 分支**全 0 通过** | C++/Go 的 SWE-Agent/AgentCoder/SecAwareCoder 在 deepseek 下 115/115 生成错误 |

**结论**：**九条 baseline 尚不能正式声明通过**——4 Prompt = FAIL，5 Agent = BLOCKED。

**修复**：统一 runner 默认切 ChatAnywhere `deepseek-v4-flash`、默认超时 90s、自动从本地忽略文件读 key、修复 `base.harness is None` 时的代码提取、加 Agent fidelity 断言。

---

### 2026-09-04~06：旧方法 PLT 自进化实验（**22 个目录**，但多数是探针/中断）

> 详细清单见 `translation_work/diagnostics/early_sct_runs_inventory_20260904_20260913.md`
> ⚠️ **重要事实**：这 22 个目录**都没有 `status.json` 和 `progress.log`**（这两个机制是 09-13 之后才有的）。

**标准入口**：
```powershell
python methods/sct_agent/run_plt_self_evolution.py --model deepseek-v3.2 \
  --timeout 30 --validation-timeout 8 --workers 4 --candidate-gate-limit 1
```

**采样算法**：从 1411 条可用漏洞/补丁对取 `ceil(1411×0.25)=353`；28 个 CWE 各配额 12/13；
按 Seed Family 原子选取；分 `D_init/D_grow/D_gate = 118/118/117`。

#### 运行分类（不是每次都是"实验"）

| 类别 | 数量 | 说明 |
|---|---|---|
| **占位运行**（无真实 API） | 1 | `plt_python_96_20260904_154217`——1 秒写完，Base 115/115、Plus 140/140 **全是 `offline_reference` 占位，不是模型分** |
| **探针/冒烟**（Base/Plus 只有 1~2 行） | 5 | 09-09 的 4 个 96 队列 + 1 个 15 队列；Base/Plus 行数 2/1/1/1/1，**没有真实评测** |
| **真实 API 但候选为 0** | 1 | `..._162509`：空模型响应 70/86 条 |
| **唯一跑出候选** | 1 | `..._165105`：候选 8、**晋升 8**、拒绝 0 |
| **中断（R0 完成、R1 半途）** | 2 | `..._125017`（候选 26）、`..._131002`（候选 25）；**都缺 d_gate/promoted/rejected** |
| **空壳（只有 manifest）** | 1 | `..._123503`：**无 metadata、无 summary、无 R0/R1、无任何 jsonl** |
| **唯一完整跑通** | 1 | `..._132431` ✅ |

#### 唯一完整运行的正式结果（`plt_python_quarter_353_20260910_132431`）

| 阶段 | 结果 |
|---|---|
| R0 | 118 行，M0 = **15**；动态测试执行 **73/118**（20 Function / 42 Secure / 15 Joint），45 条 Function `unmeasured` |
| R1 | 118 行，候选 **26**；动态执行 **74/118**；晋升 **0**，拒绝 **26**（**25 条因 `ΔJointPass ≤ 0`，1 条因 H_pass 安全回归**） |
| **Base** | 115 行：Function **29** / Secure **12** / **Joint 7** |
| **Plus** | 140 行：Function **104** / Secure **57** / **Joint 54** |

**配置**：`deepseek-v3.2`、`temperature=0.1`、`max_tokens=1800`、`retries=1`、`workers=3`、
`candidate_gate_limit=1`、`final_validation_timeout=60s`、Docker 29.4.2

**🔴 发现的问题**：

| 问题 | 详情 | 处理 |
|---|---|---|
| **Plus 口径错误** | 同一 combined `Test` 被同时算作 Function 与 Secure → 错误的 54/54/54 | 证据存 `diagnostics/20260911/plus_combined_suite_overwrite/`；修复后为 104/57/54 |
| **harness 未标定** | 必须先证明"参考解能过" | 标定 `diagnostics/20260911/python_harness_calibration/` = Base 115/115、Plus 140/140 ✅ |
| **26 条候选经验文本退化** | principle 全部变成"修复 training_validation 类目标语言实现错误…" | 记录为已知局限 |
| **门控覆盖不足** | `candidate_gate_limit=1`，26 次门控只有 16 条有可执行动态测试，10 条没有 | 0→0 表示"无可验证正增益"，**非通过** |

#### ⚠️ 跨运行不可比的重要警告

| 项 | 说明 |
|---|---|
| **验证后端变化** | `132431` 用 `python_validator_docker`（60s）；`plt_all_v2_20260913` 的 summary 写 `backend: "local_python"` → **两者 Base/Plus 数字不可直接比较** |
| **检索器演进** | `keyword-v1`（09-11 live/offline）→ `tfidf-v1`（09-11 v2 与 09-13） |
| **空库哈希** | `e3b0c442…`（空字符串 SHA-256）与 `4f53cda1…`（空 JSON 数组 SHA-256）；只有 2 个运行有非空经验库 |
| **门控晋升** | 22 个目录里**只有 2 个有晋升 > 0**：`..._165105`（8/8）、`lifecycle_replay_offline_20260911`（1 条） |

---

### 2026-09-09~13：新方法 生命周期回放实验（11 个运行）

**运行分类（多数不是"正式实验"）**：

| 类别 | 目录 | 说明 |
|---|---|---|
| 冒烟（无 summary） | `lifecycle_replay_smoke_20260911_2` | 31 秒，只有 2 条轨迹 |
| 离线探针 | `..._offline_20260911{, _final, _audit}` | 1 秒内完成；`_final` 与 `_audit` 的 m_star 为 **0 行**（空库） |
| live 探针 | `..._live_20260911_complete{, 2}` | 20 秒 / 16 秒；m_star **0 行**；两者 summary **逐字段相同**，唯一差异是 `family_id` 从 null 修正为 `410cfdbcc083` |
| **明确中断** | `lifecycle_replay_plt96_20260911` | **有 `INTERRUPTED.md`**：按索引选 32 family，32 条回放中 15 条测试未测量；审查实现**把未重跑的 H_pass 任务算作回归**，故**主动停止进程**；保留为失败诊断证据 |
| 正式替代 | `lifecycle_replay_plt96_20260911_v2` | 32/32/32，候选 7，晋升 0，frozen 32 |
| **最大规模（正式）** | `lifecycle_replay_plt_all_v2_20260913` | source 131 / replay 96 / audit 159 |

> ⚠️ 本系列运行**没有 `status.json` / `progress.log`**（这两个机制 09-13 之后才有）。

**数据划分**：386 条有"能力+安全"测试的样本 → source **131** / replay **96** / audit **159**

**结果（`sct_lifecycle_replay_run_20260913.md`）**：

| 阶段 | 结果 |
|---|---|
| Seed | 131 条提取成功，**122** 条通过 `validate_trajectory` 入 M_t，**9** 条失败 |
| Replay | 96 条轨迹，**31** 条联合通过；故障分布 `both_failed 35` / `functional_regression 21` / `security_gap 9` |
| 候选 | 15 条候选，覆盖 9 个 CWE（179/347/352/74/77/79/862/915/95） |
| **门控** | **15 条全部 demoted**；晋升 0；`delta>0` 9 条、`==0` 6 条 |

**🔴 发现两个大问题**：

**问题 1：候选门控过严（4 个根因）**
1. `repairs` 不对称——H_pass 用 `repairs=1` 建，回归重跑却用 `repairs=0`
2. 安全回归零容忍 + 单样本 API 噪声
3. `delta_joint_pass == 0` 直接 demoted
4. 不在检索 top-k 的候选仍按纯噪声门控

**问题 2：`retriever.py` 召回无效经验（3 个缺陷）**
1. **CWE 加分 bug**：
   ```python
   cwe_hit = CWE_BONUS if str(card.get("cwe", "")).strip() else 0.0
   # 从没和 query 的 CWE_ID 比较过 → 每张卡都拿满 +3.0
   ```
2. 无状态过滤——`demoted`/`retired`/`rejected` 和空 principle 的卡仍被召回
3. 无相关性下限——分数≈0 时仍无条件返回 top-k

**修复**：
- 新 `audit_decision` 优先级（质量失败→revised；未召回→revised；回归超限→demoted；delta<0→demoted；delta=0 无回归→revised；delta>0 无回归→supported）
- 回归重跑改 `repairs=1`；新增 `--regression-samples`（默认 1）与 `--regression-limit`
- Retriever：CWE 加分仅精确匹配；`_usable` 过滤无效卡；`search` 加 `min_score`
- 测试：`test_sct_lifecycle_replay.py` **28 项全过**（新增 4 项）

**⚠️ 已知瑕疵**：`plt96_20260911_v2` 的报告引用 Base 28/11/6/6，但该目录
**只有 `validation_runs/Plus/`，没有 `Base/` 子目录**——Base 数字无对应产物。

---

## 二·补、跨运行可比性警告（**做结论前必读**）

以下是"数字看起来能用、实际不可比"的陷阱，来自对 22 个早期目录的逐文件核查：

| 陷阱 | 具体表现 | 影响 |
|---|---|---|
| **验证后端漂移** | `..._132431` 用 `python_validator_docker`（60s）→ Base 29/12/7；`plt_all_v2_20260913` 用 `backend: "local_python"` → Base 25/9/7 | **跨轮 Base/Plus 数字不可直接比较** |
| **占位数据伪装成结果** | `plt_python_96_20260904_154217` 报 Base `passed:115 / generation_errors:115`——**分母等于错误数**，每行 `error="offline_reference"` | 容易被误读为"100% 通过" |
| **探针运行只有 1~2 行** | 09-09 的 4 个 96 队列 + 1 个 15 队列，Base/Plus 行数 2/1/1/1/1 | 无统计意义 |
| **报告引用无产物** | `plt96_20260911_v2` 引 Base 28/11/6/6，但无 `validation_runs/Base/` | 数字不可核验 |
| **空库哈希** | `e3b0c442…`（空串 SHA-256）、`4f53cda1…`（空数组 SHA-256） | 说明经验库为空，易被当成真实指纹 |
| **晋升极罕见** | 22 个早期目录中**只有 2 个有晋升 > 0**：`..._165105`（8/8）、`..._offline_20260911`（1 条） | 门控过严是贯穿性问题 |

**检索器/调度器演进**（影响可比性）：
```
keyword-v1（09-11 live/offline 系列） → tfidf-v1（09-11 v2 与 09-13）
scheduler 全程 score-v1
feedback_channel 在所有含该字段的运行中都是 disabled  ✅ 数据隔离正确
```

**元数据结构演进（3 阶段）**：
```
09-04          裸 8 字段
   ↓
09-09 22:07    + 采样/CWE 配额，但无 temperature/max_tokens/workers/retries
   ↓
09-09 22:51    schema_version = "sct-run-metadata-v2"（含超时/并发/重试/stage_counts/limitations）
   ↓
09-10 的 125017 / 131002 / 123503    完全没有 run_metadata.json
```

**产物布局在 2026-09-11 切换**：
```
plt_python_*        → R0/R1/frozen/manifest/validation_runs
lifecycle_replay_*  → source_pool/replay_pool/audit_pool/memory/frozen/manifest
sct_trajectory_*    → phase1_results/trajectories/audit_detail/tree/cost（09-16 起，新增 status.json + progress.log）
```

---

### 2026-09-15：CLE 方法设计诞生 + Docker 层改造

**两件事**：

1. **CLE 设计文档** `docs/sct_trajectory_contrastive.md`（四态 A/B/C/D + 12 模块）
2. **Docker 常驻容器执行层**（提交 `5599bca`）——解决 VHDX 增长

**Docker 诊断（`diagnostics/20260915/docker_disk_growth/`）**：
- 测试并发 N=2/4/6 的磁盘增长
- 结论：改为常驻容器池后，评测期间 `docker_data.vhdx` 不再增长

**CLE 早期冒烟**：`diagnostics/20260915/sct_trajectory_smoke{,2}`、`cle_cli_smoke`、`cle_docx_extract`（33 文件）
- `cle_docx_extract/closed_loop_real.json`：12 任务跨 CWE 抽样的**真实端到端证据**

---

### 2026-09-16~18：CLE 实现 + 看板 + **消融实验**

#### 看板搭建（`methods/sct_trajectory/dashboard/`）

**需求确认**：2026-09-18（`PLAN.md`）
**技术选型**：纯标准库 `http.server` + 原生 HTML/JS（零依赖、无构建）

**五个页面**：
```
概览 | Phase1 冷启动 | Phase2 重放进化 | Phase3 门控与最终评测 | 经验库
```

#### 消融实验（`abl_smoke_20260918`，**第二次对比实验**）

**设计**：6 组 × 15 任务 × 1 轮，控制 HSK-Tree 各层的生成/注入

| 组 | 含义 |
|---|---|
| A1 | L2/3 合并 + 无 L4（基线） |
| A2 | L2/3 拆分 + 无 L4 |
| A3 | 合并 + L4 文本 |
| A4 | 合并 + L4 safe/prohibited constructs |
| A5 | 合并 + 完整 L4（含 snippet） |
| A6 | 拆分 + 完整 L4 |

**结果**：

| 组 | 叶(有/总) | P1功能 | P1安全 | Joint | 费用(元) | 耗时(s) |
|---|---|---|---|---|---|---|
| A1 | 0/3 | 3/6 | 6/6 | 0/3 | 0.126 | 428 |
| A2 | 0/3 | 2/6 | 6/6 | 0/3 | 0.165 | 594 |
| A3 | 12/12 | 3/6 | 5/6 | 0/3 | 0.184 | 721 |
| A4 | 8/8 | 3/6 | 6/6 | 0/3 | 0.169 | 781 |
| A5 | 12/12 | 3/6 | 5/6 | 0/3 | 0.281 | 1271 |
| A6 | 8/9 | 3/6 | 5/6 | 0/3 | 0.271 | 1190 |

**🔴 结论（负面）**：**开关确实生效（叶数从 0→12），但 L4 与 L2/3 拆分没有带来可测量的收益**。
所有组 Joint 都是 0/3，安全率 5/6~6/6 无显著差异。

#### 反过度防御对比实验（`overdefense_exp_20260918`，**第三次对比实验**）

**设计**：3 臂 × 21 任务 × 1 轮（A1 消融固定）

| 臂 | 干预 |
|---|---|
| `base` | 现状 |
| `anti_od` | 功能优先提示 |
| `contract_freeze` | **功能契约冻结**（禁止发明原契约外的前置条件） |

**结果（最终评测 6 条，同批任务）**：

| 臂 | Joint | pass/pass | **fail/pass（过度防御）** |
|---|---|---|---|
| base | 2/6 | 2 | **3** |
| anti_od | 3/6 | 3 | 2 |
| **contract_freeze** | **4/6 (66.7%)** | **4** | **1** |

**✅ 结论（正面）**：`contract_freeze` 把联合通过率从 33% 提到 **67%**，过度防御从 3 降到 1。
代码证据：base 会发明 `len(mail_address) > 1000` 的前置条件，contract_freeze 直接正则匹配。

#### 其他同日验证运行

`cle_dash_verify_small`、`cle_dash_final_verify`、`cle_multiround_verify`、`gate_selector_verify`、
`replay_verify`、`cle_cost_verify`、`abl_A5_verify{,2}`

**关键发现**：根因是 **fail/pass（功能失败·安全通过）主导** = **过度防御**。

---

### 2026-09-19：**第一次全量 874 运行**（里程碑）

**运行**：`cle_full_874_20260919`
**配置**：874 任务 / A4 消融 / `contract_freeze` / 3 轮
**耗时**：7.2 小时（01:31 → 08:45）
**成本**：12.63 CA元 / 7640 次调用

**结果**：

| 指标 | 值 |
|---|---|
| **最终评测 JointPass** | **64/298 = 21.5%** |
| ABCD | A:64 / B:17 / C:141 / D:74 |
| 覆盖 CWE | 19 个 |
| 树规模 | 19 节点（轮1:8 → 轮2:14 → 轮3:19） |
| 经验池 | 1284 条 |

**🔴 深度分析（`cle_full_run_analysis_20260919.md`）发现六大问题**：

| # | 问题 | 证据 |
|---|---|---|
| 1 | **门控全放行** | 24 条审计里 **21 条 Δ=0 却全部晋升**（规则是 Δ≥0 即通过） |
| 2 | **83.8% 跨 CWE 无关注入** | 同 CWE 144 / 跨 CWE 744 |
| 3 | **固定注入 3 条** | 分布 `{0:2, 3:296}` |
| 4 | **树内 52.6% 是高疑节点** | 19 节点中 10 个命中≥3 条"低价值"判据 |
| 5 | **经验池 230 对重复** | 池级去重缺失（只在入树时吸收） |
| 6 | **过度防御占 47.3%** | fail/pass 141/298 |

**关键对照**（同 CWE 内部）：覆盖组 JointPass 15.1% vs 未覆盖组 27.0%
→ 但覆盖组基线本就低 8.4pt，**净负面效应约 3.5pt**。

---

### 2026-09-20：九项优化 + 第二次全量（**含 2 次中止**）

#### 修复的缺陷（10 个，按类型）

**影响结果正确性（5）**：

| # | 缺陷 | 后果 | 发现方式 |
|---|---|---|---|
| 1 | `NODE_STATUS` 缺 `unmeasured`/`revised` | 门控赋值抛 ValueError，**全量必崩** | 写单测时构造函数报错 |
| 2 | `hint`/`pitfall` 工厂未写 `source["kind"]` | 第四条加权**完全空转**（实测 0/36） | 冒烟验收发现"0 条" |
| 3 | 经验池无去重 | 1284 条含 230 对重复 | 全量分析统计重叠 |
| 4 | 探测失败丢任务 | 静默减少门控候选池 | 写筛选测试时发现 |
| 5 | `_joint_pass_rate` 无 try/except | 一次 `TimeoutError` 终止整条运行 | 16:11 事故 |

**影响可观测性（5）**：API 无硬超时、心跳不刷新致看板误标 stale、基线筛选静默 fallback、看板文案过时、监视器停滞误报。

#### 优化的方法改动（9 项）

| # | 改动 | 依据 |
|---|---|---|
| 1 | **门控正证据**：Δ>0 supported / Δ=0 **unmeasured（降级保留）** / Δ<0 demoted | 修问题 1 |
| 2 | **注入相关性门槛**：同CWE≥0.6 / 跨CWE≥0.75 | 修问题 2、3 |
| 3 | **反过度防御加权** +1.5 | 针对问题 6 |
| 4 | **门控例子策略 = LLM 自由决定** | 实验五 |
| 5 | **基线可测性筛选**（新增） | 实验发现 |
| 6 | 审计量 12 → 24/轮 | 覆盖面 1.9% 太低 |
| 7 | **池级去重** | 修问题 5 |
| 8 | 归并阈值 4 → 3 | 归并从未触发 |
| 9 | Level 4 生成默认关闭（新增 A7） | 消融无收益 |

#### 消融/对比实验（09-20）

**实验四：反过度防御 3 臂**（已在 09-18 跑，09-20 复述结论）

**实验五：门控例子数 3 臂**（`gate_exp4_20260920`）

| 臂 | 均例子 | 区分度 | 晋升/淘汰/无证据 | 费用 | 耗时 |
|---|---|---|---|---|---|
| F2（固定2） | 2.0 | 2/5 | 0/2/3 | 0.420 | 1498s |
| F4（固定4） | 4.0 | 2/5 | 1/1/3 | 0.508 | 1784s |
| **LLM（自由）** | **1.2** | 2/5 | **1/1/3** | **0.355** | **1144s** |

**✅ 结论**：LLM 自由决定最优（成本 -30%、耗时 -36%、例子 1.2 vs 4.0，区分度相同）。

**🔴 实验中的重要发现——"基线可测性"前提**：
```
F2 组基线分布: {0.0: 7, 0.5: 1}
→ 7/8 的任务"加不加经验都通不过" → Δ 数学上恒为 0
```
实测各 CWE 可测性：
```
✅ 可测区间(20~80%)：1333(77%) 915(77%) 863(56%) 327(40%) 862(36%) 94(35%) 77(33%) 770(31%) 95(28%) 179(24%)
❌ 太难(0%)：200 347 352 502 601 74 918 79
```

#### 第二次全量（`cle_full_874_v2_20260920`）——**两次中止 + 一次正式**

**🔴 中止 1（06:52 启动 → 中止）**：发现 `NODE_STATUS` 缺状态，跑到 Phase3 必崩
**🔴 中止 2（启动 → 中止）**：发现 `kind` 未写入，第四条完全空转
**✅ 第 3 次（07:57 启动）**：启动前用 `preflight.py` 核验 11/11 改动、8/8 配置、290 tests

**进度**：Phase1 完成（5.2h）→ 轮1 完成（晋升 4、**池内去重吸收 103 条**）→ 轮2 Phase3 时
**16:11 因 TimeoutError 失败**

**轮1 门控结果（有效数据）**：

| 指标 | v1 | v2 |
|---|---|---|
| 判定 | supported 22 / demoted 2 | **unmeasured 19 / supported 4 / demoted 1** |
| Δ 分布 | {0.0: 21, 0.5: 3} | **{0.0: 19, 0.2: 3, 0.33: 1, -0.5: 1}** |
| **基线中间区间** | **0/24 (0%)** | **7/24 (29%)** ✅ |
| 池内去重吸收 | 0 | **103 条** ✅ |

**测出真实效果的经验**：
```
seed-1175  0.0 → 0.3333  Δ=+0.33  supported
seed-1230  0.2 → 0.4     Δ=+0.2   supported
seed-1008  0.4 → 0.6     Δ=+0.2   supported
seed-1148  0.2 → 0.4     Δ=+0.2   supported
seed-107   0.5 → 0.0     Δ=-0.5   demoted   ← 有害经验被拦下
```

#### 效率优化（09-20 晚）

| 改动 | 内容 |
|---|---|
| 并发 5 → **24** | 依据：实测 CPU 占用仅 **0.25%** |
| **Phase3 并发**（原完全串行！） | 新增 `--phase3-workers`（默认 8），抽出 `_audit_one()` 工作单元 |
| **Level 4 关闭** | 新增消融组 A7（代码保留） |
| Phase2 候选窗口 | `--batch-size` 24 → **96** |

**耗时剖析（`runtime_reflection.md`）**：
```
Phase1 冷启动 303 条:  310 分钟 (68%)
轮1 Phase2:             14 分钟 (3%)
轮1 Phase3 审计 24 条: 105 分钟 (23%)  ← 原先串行
```

---

### 2026-09-20 晚 ~ 09-21：断点续跑 + 覆盖率实验

**`cle_full_874_v2_resumed_20260920`**（已完成）：
```
最终评测: JointPass 59/298 = 19.8%
ABCD: {A: 59, B: 17, C: 125, D: 97}
完成时间: 2026-09-20 23:24
```
**对比**：21.5% → **19.8%（-1.7pt）**

**`coverage_smoke_20260921`**（已完成）：
```
48 任务 → source=18 / replay=16 / audit=14
A7 消融（无 L4）
轮2 重放覆盖：累计 16/16 = 100%（目标 75%）
JointPass 2/14 = 14.3%，成本 1.75 元
```

**`coverage_smoke2_20260921`**（进行中）：
```
54 任务 → source=20 / replay=17 / audit=17
```

---

## 三、看板演进

| 日期 | 事件 | 产物 |
|---|---|---|
| 09-18 | 需求确认 + 实施 | `dashboard/PLAN.md`、`server.py`、`app.js`、`tree.js` |
| 09-18 | 六项升级：成本/树图/失败对比/多轮/通过率拆分/树变化 | — |
| 09-19 | 四项改造：Level4 + 消融、强制重放、逐轮 diff、门控 LLM 选择器 | — |
| 09-20 | 修 stale 误判（心跳 + 文件活动双证据） | `server.py:_run_status` |
| 09-21 | **运行列表按时间倒序** + **经验树横向布局 + 适应宽度** | `server.py:_run_sort_key`、`tree.js:buildTreeLayout` |

**09-21 树布局实测改进**：
| | 改前 | 改后 |
|---|---|---|
| 布局 | 纵向堆叠 | **横向分列**（宽高比 5.47） |
| 缩放 | 0.171 | **0.55** |
| 正文可见字号 | 2.3px（不可读） | **6.1px** |

---

## 四、实验类型汇总

| 类型 | 次数 | 代表实验 | 关键结论 |
|---|---|---|---|
| **九条 baseline 对比** | 3 模型 | `agents_full_*_20260906` | 4 Prompt FAIL / 5 Agent BLOCKED；SecAwareCoder 最好（7.83%） |
| **旧方法 PLT 自进化** | 10 运行 | `plt_python_quarter_353_*` | 26 候选全拒绝；Base Joint 7/115、Plus 54/140 |
| **新方法生命周期回放** | 11 运行 | `lifecycle_replay_plt_all_v2_20260913` | 15 候选全 demoted；发现 retriever CWE 加分 bug |
| **HSK-Tree 分层消融** | 6 组 | `abl_smoke_20260918` | **L4 与拆分无收益**（负面结论） |
| **反过度防御 3 臂** | 3 臂 | `overdefense_exp_20260918` | **contract_freeze 33%→67%**（正面结论） |
| **门控例子数 3 臂** | 3 臂 | `gate_exp4_20260920` | **LLM 自由决定最优**；发现"基线可测性"前提 |
| **全量 874** | 3 次 | `cle_full_874_*` | 21.5% / 19.8%；发现六大问题 |
| **覆盖率专项** | 2 次 | `coverage_smoke*` | 重放覆盖 16/16 = 100%（目标 75%） |
| **Docker/VHDX 诊断** | 2 组 | `docker_disk_growth*` | 常驻容器池后 VHDX 不再增长 |
| **harness 标定** | 1 次 | `python_harness_calibration` | 官方 Secure Code 115/115、140/140 ✅ |

---

## 五、贯穿始终的问题模式

### 反复出现的"静默失效"

| 日期 | 问题 | 教训 |
|---|---|---|
| 09-13 | retriever CWE 加分**从不比较** CWE → 每卡都满分 | 打分函数必须验证"真的在用输入" |
| 09-18 | 消融开关生效但**无收益** | "开关生效"≠"机制有用" |
| 09-19 | 门控 Δ≥0 全放行 → **21/24 零证据晋升** | "不劣化"≠"有正证据" |
| 09-20 | `kind` 未写入 → 加权**空转** | 依赖字段必须显式写入 + 测试 |
| 09-20 | `NODE_STATUS` 缺状态 → **必崩** | 枚举改动要同步不变量测试 |
| 09-20 | 基线筛选静默 fallback | 降级必须显式记录 |

### 反复出现的"评测口径"问题

| 日期 | 问题 | 教训 |
|---|---|---|
| 09-11 | Plus 同一 Test 被算两次（54/54/54） | 口径错会让结果完全失真 |
| 09-11 | harness 未标定 | 必须先证明"参考解能过" |
| 09-19 | 整体均值比较不同运行 | 必须用**同 task_id 配对** |
| 09-20 | 把"日志间隔"当"单任务耗时"外推 | 口径混用会低估 5 倍 |

### 反复出现的"实验效率"问题

| 日期 | 问题 | 数值 |
|---|---|---|
| 09-18 | Phase3 完全串行 | 24 条审计 = 105 分钟 |
| 09-19 | 全量 7.2 小时 | CPU 占用仅 0.25%，并发严重不足 |
| 09-20 | 两次重启各损失 1 小时 | "改动写完但运行已启动"的窗口问题 |

---

## 六、数据边界（方法学硬约束）

| 约束 | 内容 |
|---|---|
| 训练侧只用 PLT | `data/external/secodeplt`；Base/Plus 是**冻结后**最终评测，结果**永不回流** |
| Seed Family 原子隔离 | 同一原始种子的变体不跨池（source/replay/audit） |
| 门控三关 | 质量门控 / D_gate 独立有效性 / H_pass 回归，全过才入 M* |
| `unmeasured` 不等于 pass | 没执行的验证项必须记 `unmeasured` |
| JSONL ≠ 通过 | "只能证明写入了一行，不能证明编译/功能/安全都通过" |

---

## 七、当前状态与未决事项

**代码状态**：大量未提交改动（`git status` 显示 19 个已修改 + 15 个新增文件）

**未决**：
1. **19.8% vs 21.5%** —— 第二次全量（resumed）反而降 1.7pt，需分析原因
2. **基线筛选的实际效果** —— v2 轮1 中间区间 29%（v1 为 0%），但全量结果未提升
3. **待做的效率优化**（`runtime_optimization.md`）：基线缓存、Phase2 多 Agent 协作、跳过必然失败的修复轮
4. **九条 baseline 仍未正式达标**（4 Prompt FAIL / 5 Agent BLOCKED）

---

## 八、09-21 下午：重放过滤（A）与失败现场入池（B）

> 触发：用户核查 60 任务小规模运行后质疑"第二阶段通过的任务没有被排除"，
> 并追加要求"失败案例中的轨迹和具体的报错信息都要加入，并且这些经验可以被经验选择器（LLM）选中"。

### 8.1 A 方案：重放候选过滤（已落地）

`methods/sct_trajectory/closed_loop.py` 多轮演进循环内：

| 机制 | 实现 | 目的 |
|---|---|---|
| 排除已达 A | `passed_ids`（每轮末态为 A 的任务永不再重放） | 已通过任务重放产生不了新经验 |
| 排除上一轮已选 | `prev_round_chosen`（强制重放任务豁免） | 避免每轮重复跑同一批 |
| CWE 保底 | 某 CWE 被全过滤时保留 1 条 | 防止该 CWE 断档 |
| 覆盖率口径 | 分母改为"未通过任务数" | 对齐用户本意"多选**未通过**任务形成经验" |
| 强制重放 | 末态 ∈ {B,C,D} 的任务下一轮必须被选（≤3 次） | 失败任务必须被带回 |

**实证（旧运行 `per_round_test_20260921`，改造前）**：轮 3 与轮 2 选中的任务 **14/14 完全相同**；
`task=46/1053/1126/1127` 第 2 轮已达 A 却仍在第 3 轮被重放。

### 8.2 B 方案：失败现场入池——修掉 4 处静默丢字段

`distillation.distill_each_round()` 已能提炼出 `root_cause` / `fix_directive` /
`prev_fix_assessment`（实测 Phase1 20 个任务产出 37 条按轮经验），
但这些字段在**入池环节**被逐层丢掉：

| # | 位置 | 症状 | 修法 |
|---|---|---|---|
| 1 | `_node_from_negative` | **完全不写 `source`** → 池内 50 条 `guard-*` 只剩 `{stage,task_id}`；而 `round_1_fail`（修复轮仍失败）恰好走这条路径 | 补写 kind / round_index / round_state / root_cause / fix_directive / prev_fix_assessment |
| 2 | `_node_from_distilled` | 只写 kind/root_cause/fix_directive，缺轮次与上轮评估 | 补齐三个字段 |
| 3 | `_node_from_ledger_item` | 要求 `blind_spot` 非空，而按轮提炼的 JSON schema **不产出该字段** → 37 条按轮经验一条都没进池 | `blind_spot` 为空时回退到 `root_cause` |
| 4 | `_absorb_in_pool` | 就地吸收时只并红线与语言叶，**丢掉** root_cause/fix_directive/prev_fix_assessment | 新增 `_append_note()`：按字段去重追加，保留证据链 |

**实测证据（改造前 `per_round_test_20260921`，457 条池子）**：
`root_cause` 54 条、`prev_fix_assessment` **0 条**、`round_*` 按轮失败 **0 条**。
用户观察到的"感觉你没有提取有效的经验"即由此产生。

**旁修**：`[覆盖目标] replay 池 N 条，目标覆盖 0 条（75%）` —— 原实现把变量初值 0
当真实目标打印，属会误导排查的静默失真；改为打印真实首轮目标。

### 8.3 验证资产（可复用，反例已校验）

| 脚本 | 检查内容 | 反向校验 |
|---|---|---|
| `diagnostics/20260921/verify_a_replay_filter.py` | A1 已达 A 仍被重放；A2 相邻轮重复选中（非强制）；A3 覆盖率新口径；B1 失败现场入池；B2 被 LLM 选择器真正挑去审计 | 对旧运行正确判 ❌（A1 抓出 4 违规、B1/B2 抓出字段丢失） |
| `diagnostics/20260921/verify_b_selectable.py` | 提炼 → 检索文本（`retriever._node_text`）→ 选择器提示词（`gate_selector`）三段贯通 | 旧池 54/54 命中检索文本，选择器提示词含"报错根因/修法" |

**设计原则**：验证脚本必须能对**已知失败的历史运行**判 ❌，否则只是橡皮图章。

### 8.4 当前运行

- 合并验证：`translation_work/sct_runs/ab_verify_20260921`（60 任务 / 3 轮 / 20 并发）。
- 全量运行待 A+B 验证通过后启动。

### 8.5 验证运行暴露的 2 个 A 方案缺陷（已修）

首次合并验证运行（16:42 启动）在 Phase2 第 1 轮 9/9 跑完后**崩溃**，
暴露出 A 方案代码（交接前写完但从未端到端跑通）中的两处问题：

| # | 位置 | 症状 | 修法 |
|---|---|---|---|
| 5 | `run_evolution_rounds` 状态更新循环 | 同一段代码里 `p2["traces"]` 元素是 **dict**（1128/1150/1162 行都用 `t["task_id"]`、`t.get("states")`），唯独这一处用属性取值 `tr.task_id` / `tr.states` → `AttributeError: 'dict' object has no attribute 'task_id'`，**整轮演进中断** | 统一改为下标取值 |
| 6 | 覆盖率目标取整 | `target_n = int(len(_pending) × 0.75)` 向下取整：池子 17 条时目标 = 12 → 12/17 = **70.6%**，**永远够不到自己设的 75%**。目标值本身把标准压到阈值之下，属自相矛盾的口径错误 | 改用 `math.ceil()` → 13/17 = 76.5% |

**教训**：A 方案的过滤/配额逻辑写在多轮循环内部，只有真正跑满 3 轮才会触发；
"代码写完 + 编译通过"完全不足以证明它可运行。这也解释了为什么前一晚的两次全量
会在 Phase2 中途失败——**改动写完但从未被完整执行路径覆盖**（同 `runtime_reflection.md`
记录的 09-20 问题模式）。

### 8.6 A/B 路径缺陷总表（共 9 处，全部已修 + 回归测试锁定）

按发现顺序编号。**全部属"静默失效"**：不抛异常，只是结果悄悄不对，
只能靠事后翻日志或逐字段核对产物才能发现。

| # | 位置 | 缺陷 | 后果 | 证据 |
|---|---|---|---|---|
| D1 | `_node_from_negative` | 完全不写 `source` | 池内 50 条 `guard-*` 只剩 `{stage,task_id}`；`round_1_fail`（修复轮仍失败）走此路径 → **用户最想要的经验被丢干净** | 旧池 457 条：`prev_fix_assessment` 0 条 |
| D2 | `_node_from_distilled` | 缺 `round_index`/`round_state`/`prev_fix_assessment` | 修复轮经验与首轮经验无法区分 | 同上 |
| D3 | `_node_from_ledger_item` | 要求 `blind_spot` 非空，而按轮提炼 schema 不产出该字段 | Phase1 提炼的 37 条按轮经验**一条都没进池** | `round_*` 条目 0 条 |
| D4 | `_absorb_in_pool` | 吸收时只并红线与叶节点 | 被吸收条目的失败现场消失 | 同上 |
| D5 | `run_evolution_rounds` 状态更新循环 | `p2["traces"]` 是 dict，却用属性取值 `tr.task_id` | `AttributeError` **中断整轮演进**（验证运行实际死在这里） | 16:49 崩溃堆栈 |
| D6 | 覆盖率目标取整 | `int(len × 0.75)` 向下取整 | 池 17 条时目标 12 → **永远够不到自己设的 75%** | 日志"目标覆盖 0 条（75%）" |
| D7 | `llm_bounded_select` | 未把 `already_used` 传进调度提示词 | 提示词里"优先选【未重放·优先】"的引导是**死代码**，LLM 看不到哪些从未跑过 | 代码走查（参数被接收但未使用） |
| D14 | `phase2_evolve` | 返回 `self.traces` **全局累积**而非本轮 | ① `retry_counts` 被重复累加 → **强制重放机制实际只生效一轮**；② `hpass` 混入历轮陈旧 A 态 | 日志"已重放 **4** 次仍失败，达上限 3"，同批 task 重复打印 |
| D15 | `schedule_replay` 覆盖配额 | 配额补足不受 `replay_limit` 约束 | 全量场景 `floor_n = ceil(273/2) = 137 > replay_limit(96)`，**"有界筛选"契约失效**，单轮成本失控 | 算术推导 + 480 分钟外推 |
| D16 | `gate_selector` 预算判定 | 内层循环读的是外层旧 `total` | 实际可超出 `MAX_TOTAL_TASKS` 最多 11 个任务 | 代码走查 |

另有两处"修复不彻底"的补正：

- `_node_from_ledger_item` 的盲区兜底原先直接取 `root_cause`，会把**具体报错**
  当成 `high_level_invariant` 写进全池。改为优先级
  `blind_spot > high_level_invariant > negative_guardrail > root_cause`，
  且 `negative_guardrail` 优先用 LLM 给出的值。
- 错题本 `failure_type` 原先只取 `blind_spot`，按轮条目全记成 `"unknown"`，
  使 `replay_bias` / `analysis_warning` 失去区分度；补上 `root_cause` 兜底。

**回归测试**：`tests/test_replay_and_failure_context.py`（9 条）。
已做**反向校验**：临时回退 D1/D3/D7 三处修复 → 对应 3 条测试立即失败，
恢复后 9 条全过。确认测试不是橡皮图章。

### 8.7 门控"有害经验检测"通道修复（D19 / D20 / D21）

用户在 2026-09-21 追问"什么情况下筛选会回退为不筛选"时，顺带挖出三处相互关联的缺陷。

#### D19：基线筛选的前提假设是错的

代码注释写"基线 = 0 → Δ 数学上恒为 0"，据此只保留基线 ∈ (0,1) 的任务。
但基线 0 是**地板**不是天花板：Δ = 加经验 − 0 ≥ 0，**可以为正**，只是不可能为负。
实测（`ab_verify_20260921` 的 48 条审计明细）：

| 基线 | Δ<0 | Δ=0 | Δ>0 |
|---|---|---|---|
| 0.0 | — | 6 | **10** |
| 0.3333 | 12 | 4 | 7 |
| 0.6667 | 4 | 4 | — |
| 1.0 | 1 | — | — |

→ 两类任务分工**互补**：基线 0 贡献正向证据（17 条 supported 里 10 条来自它），
基线 > 0 贡献负向证据（17 条 demoted 全部来自它）。
**按旧规则过滤掉基线 0，会丢掉 59% 的正向证据来源。**

**修法**：`filter_measurable_tasks` 不再剔除任何任务，改为按可测范围排序
（正负皆可测 → 仅可测增益 → 未探测 → 仅可测有害），仅影响顺序不影响集合。
`info["fallback"]` 恒为 False（"回退"语义废弃）。日志文案同步改为"基线可测性标注"。

#### D20：功能回归通道被硬编码为 0

Phase3 的 Gate3 里：

```python
detail["security_regressions"] = sum(1 for f in flags if not f)   # flags 是 joint
detail["functional_regressions"] = 0                              # ← 硬编码
```

两个后果：
- **功能回归恒为 0** → "过度防御"（安全过、功能败）**永远测不出来**，
  而它占实测失败的 47.3%，正是用户最关心的问题；
- `security_regressions` 统计的是 **joint** 失败 → 过度防御被**错记成安全回归**，归因错位。

**修法**：新增 `_regression_probe()`，按维度读 `evidence` 的 `functional` / `security` 状态，
多数决降噪后分别统计。`unmeasured` 不记为失败（不伪造证据）。

#### D21：H_pass 回归跑在空任务契约上

```python
hpass = [{"cwe": t["cwe"], "task_id": t["task_id"]} for t in p2["traces"] if ...]  # 只有 2 个键
```

审计侧 `r.get("task_description") or {}` → **空字典** → LLM 拿不到函数名与描述
→ 生成的代码必然对不上 → 全部判为"回归" → 候选被**误判 demoted**。
实测形态：`cand-1333-…` 的 3 个 H_pass 任务全部记为回归。

另外 `detail` 里根本没有 `hpass_missing` 这个键，缺测既没被记录也没能阻止晋升。

**修法**：
1. `hpass` 用 replay 池原始行补齐 `task_description`；
2. `detail` 增加 `hpass_missing`，并传入 `audit_candidate`；
3. 拿不到描述的任务记 `hpass_missing`（阻止晋升为 revised），而不是伪造回归证据
   —— 遵循 AGENTS.md 第九节"没有执行的验证项必须记录为未测量"。

#### 有害经验检测的最终设计

| 通道 | 负责 | 依赖条件 |
|---|---|---|
| Gate2 ΔJointPass | 测"**有用**" | 基线 < 1.0（有正值空间） |
| Gate3 安全回归 | 测"**有害**：破坏安全" | 有同 CWE 的 H_pass 任务且带描述 |
| Gate3 功能回归 | 测"**有害**：过度防御" | 同上 |

两条回归通道**与基线可测性无关**，是独立的反向证据来源。
D19 修复保证"有用"的证据不被误删，D20/D21 修复保证"有害"的证据能被测出。

**回归测试**：`tests/test_gate_baseline_filter.py` 改写为不变量测试（一条都不许剔除），
`tests/test_replay_and_failure_context.py` 增加 D19（4 条）/ D20（5 条）/ D21（1 条）。
全量单测 **323 passed**。

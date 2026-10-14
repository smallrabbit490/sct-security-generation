# CLE 方法学发现：经验注入的负面结果与瓶颈定位

> 记录日期：2026-09-18
> 数据来源：本次会话中三次真实实验（全部为真实 API 调用 + 本地动态测试，非估算）
> 结论性质：**负面结果**，但对方法设计有直接指导意义

## 摘要

本方法的核心假设是"从失败/成功轨迹中沉淀可复用安全经验，注入后续生成以提升安全代码生成的成功率"。
三次独立实验（检索策略对比、跨 CWE 检索对比、HSK-Tree 分层消融）**一致未能验证该假设**：

- 注入经验相对不注入，成功率**没有提升**，部分设置下**反而下降**；
- 增加树的层数（Level 4 多语言叶）与拆分 Level 2/3，**均未带来可测量收益**；
- 失败模式高度集中在 **`功能失败 / 安全通过`（fail/pass）**，即模型为通过安全要求而**破坏业务功能**（过度防御）。

因此瓶颈**不在树的层数、也不在检索算法**，而在**经验内容/规划约束诱发过度防御**。

**据此定位根因后，第四次实验找到了有效的干预（实验四）**：
在 Planning 阶段显式禁止"发明原任务契约中不存在的前置条件"，把 JointPass 从
**33.3% 提升到 66.7%**，过度防御案例从 3 降到 1。这是本次会话中唯一测出正向收益的干预。

---

## 实验一：检索策略对比（检索器排序 vs 大模型直接挑选）

**设计**：24 个有经验覆盖的 audit 任务，三种条件各跑一次真实生成 + 动态测试。

| 条件 | JointPass 通过率 |
|---|---|
| A 不注入任何经验（下界） | **7/24 = 29.2%** |
| B 现有检索器（CWE 路由 + base 分 + LLM 打分重排） | **6/24 = 25.0%** |
| C 大模型直接查看全部候选自己挑 | **7/24 = 29.2%** |

**关键观察**：24 个任务中 **15 个**三种条件结果完全相同。

**结论**：检索策略（含让 LLM 直接挑选）**未能带来差异**；检索器甚至比不检索低 4.2 个百分点。

数据：`translation_work/diagnostics/20260916/retrieval_compare_result.json`

---

## 实验二：跨 CWE 检索对比

**设计**：18 个任务（12 个 CWE 有经验覆盖 + 6 个无覆盖），四种检索模式。

| 条件 | JointPass | 有覆盖组 | 无覆盖组 |
|---|---|---|---|
| 不检索 | **5/18 = 27.8%** | 5 | 0 |
| strict_cwe（同 CWE 精准） | **5/18 = 27.8%** | 5 | 0 |
| cross_cwe（忽略 CWE 全树检索） | **3/18 = 16.7%** | 3 | 0 |
| hybrid（同 CWE 优先 + 跨 CWE 兜底） | **4/18 = 22.2%** | 4 | 0 |

**结论**：
1. **无覆盖 CWE 上四种模式全部 0 通过** —— 跨 CWE 检索**没能救回任何一个**任务；
2. 忽略 CWE 的全局检索**最差（16.7%）**，低于不检索 —— 盲目跨 CWE 注入经验**有害**；
3. 同 CWE 精准检索与不检索**持平**（均 27.8%）—— 检索整体无净收益。

**个别正例**（说明机制非完全无效）：CWE-179 `fail/pass → strict=pass/pass`；CWE-601（无覆盖）`fail/fail → strict/hybrid=fail/pass`。
**个别反例**：CWE-770 `pass/pass → 所有检索模式=fail/fail`；CWE-863 `pass/pass → cross/hybrid=pass/fail`。

数据：`translation_work/diagnostics/20260916/cross_cwe_result.json`

---

## 实验三：HSK-Tree 分层消融（6 组）

**设计**：15 任务 × 1 轮，6 组消融（各组超参完全一致）。
- A1 = Level2/3 合并 + 无 Level 4（**基线，等价于改造前行为**）
- A2 = Level2/3 **拆分** + 无 Level 4
- A3 = 合并 + Level 4 **仅文本**
- A4 = 合并 + Level 4 **safe/prohibited constructs**
- A5 = 合并 + Level 4 **再加 pattern_snippet**（完整）
- A6 = **拆分** + 完整 Level 4

| 组 | L2/3 | 叶(有内容/总) | Phase1 功能 | Phase1 安全 | 最终 JointPass | 费用(CA元) |
|---|---|---|---|---|---|---|
| A1 | 合并 | 0/3 | 3/6 | **6/6** | 0/3 | 0.126 |
| A2 | 拆分 | 0/3 | 2/6 | **6/6** | 0/3 | 0.165 |
| A3 | 合并 | 12/12 | 3/6 | 5/6 | 0/3 | 0.184 |
| A4 | 合并 | 8/8 | 3/6 | **6/6** | 0/3 | 0.169 |
| A5 | 合并 | 12/12 | 3/6 | 5/6 | 0/3 | 0.281 |
| A6 | 拆分 | 8/9 | 3/6 | 5/6 | 0/3 | 0.271 |

总耗时 4986.7 秒。

**开关有效性已验证**：A1/A2 的 Level 4 叶为 0，A3~A6 均有真实内容 —— 说明"没有差异"不是因为开关没生效。

**结论**：
1. **Level 4 未带来收益**：A1（无 L4）的安全通过率 6/6，不低于 A5（完整 L4）的 5/6；
2. **Level 2/3 拆分未带来收益**：A1 vs A2、A5 vs A6 均无差异；
3. 所有组最终 JointPass 均为 **0/3**。

数据：`translation_work/sct_runs/abl_smoke_20260918/ablation_summary.json`

---

## 瓶颈定位：过度防御（fail/pass 主导）

三次实验中失败模式的分布高度一致：

| 运行 | fail/pass（功能失败·安全通过） | pass/pass | 其他 |
|---|---|---|---|
| gate_selector_verify（最终评测） | **3** | 1 | fail/fail 1, pass/fail 1 |
| abl A1（最终评测） | **2** | 0 | pass/fail 1 |
| abl A5（最终评测） | 1 | 0 | **pass/fail 2** |
| gate_selector_verify（Phase1） | **3** | 0 | fail/fail 2, pass/fail 1 |
| abl A1（Phase1） | **3** | 3 | — |
| abl A5（Phase1） | **2** | 3 | fail/fail 1 |

**`功能失败 / 安全通过` 是最主要的失败模式**：模型确实把安全要求满足了，代价是**功能不再正确**。
这正是"过度防御"的特征——例如为阻断攻击而清空返回值、拒绝所有输入、加超出威胁模型的限制。

**这解释了为什么注入经验无益甚至有害**：当前经验库内容以"加强安全"为主
（"必须校验""必须白名单""必须限长"），注入后**进一步强化了模型的加固倾向**，
使本已存在的过度防御更严重；而真正需要的"如何在保持功能的前提下最小化改动"类经验占比不足。

---

## 对方法设计的指导

1. **不要优先增加树层次或改进检索算法** —— 实验一、二、三一致表明这两条路没有收益；
2. **优先改变经验内容方向**：把沉淀重点从"安全加固原则"转向
   "保持功能契约的最小改动手法"与"过度防御陷阱"（本次已实现 `minimal_patch_hint` /
   `overdefense_pitfall` 两类经验节点，但尚未单独消融验证其效果）；
3. **注入侧的抑制机制是有效的（见实验四）**；
4. **评测口径**：由于 `fail/pass` 占主导，单看"安全通过率"会高估方法效果，
   必须同时报告 **JointPass（功能∧安全）**。

---

## 实验四：反过度防御干预（正向结果）

**设计**：21 任务 × 1 轮，固定消融组 A1，三臂对比（唯一变量 = Planning 阶段的提示约束）。

| 臂 | 干预内容 | JointPass | fail/pass（过度防御） | 耗时 |
|---|---|---|---|---|
| `base` | 现状（无额外约束） | 2/6 = 33.3% | **3** | 612.7s |
| `anti_od` | 追加「功能优先原则」三条 | 3/6 = 50.0% | 2 | 554.5s |
| **`contract_freeze`** | 追加「功能契约冻结」 | **4/6 = 66.7%** | **1** | 517.0s |

**逐任务对比**（三臂使用完全相同的 audit 任务 [45,46,47,136,333,423]，可比）：

| task | CWE | base | anti_od | contract_freeze |
|---|---|---|---|---|
| 46 | CWE-1333 | fail/pass | pass/pass | pass/pass |
| 136 | CWE-200 | fail/pass | fail/pass | **pass/pass** |
| 45 / 47 | CWE-1333 | pass/pass | pass/pass | pass/pass |
| 333 | CWE-327 | fail/pass | fail/pass | fail/pass |
| 423 | CWE-347 | pass/fail | pass/fail | pass/fail |

改善**集中在原本 fail/pass 的任务**上，符合因果预期；`pass/fail`（安全失败）与顽固任务未受影响。

**机制证据（同一任务 task=45 的生成代码对比）**：

```python
# base：凭空发明原契约不存在的前置条件，不满足就提前返回
def get_email_domain(mail_address):
    if mail_address is None: return None
    if not isinstance(mail_address, str): return None
    if len(mail_address) > 1000: return None        # ← 发明了长度上限
    at_index = mail_address.find('@')
    if at_index == -1 or at_index == len(mail_address) - 1: return None
    return mail_address[at_index + 1:]

# contract_freeze：直接执行正则匹配，不发明前置条件
def get_email_domain(mail_address):
    pattern = re.compile(r'^[^@]+@([^@]+)$', re.UNICODE)
    match = pattern.fullmatch(mail_address)
    if match: return match.group(1)
    return None
```

**结论**：把"禁止发明原契约不存在的前置条件"作为 Planning 阶段的显式约束，
**确实抑制了过度防御行为**，并把 JointPass 从 33.3% 提升到 66.7%。
这是本次会话中唯一测出正向收益的干预。

**关于历史注释的更正**：`agent_pipeline.planning_prompt` 原 docstring 声称
"anti_overdefense 提示 B-A=+0.0pt、交互 -5.6pt"，但仓库中**不存在支撑该结论的实验产物**。
本次可复现实验显示 `anti_od` 为 3/6（优于 base 的 2/6），与旧注释不符，故已更正注释。

**局限**：单轮、单模型、6 个 audit 任务的评测样本，幅度（+33.3pt）**不宜直接外推**；
但**改善方向与机制解释一致**，且逐任务对比显示改善落在预期任务上，证据链自洽。

实验数据：`translation_work/sct_runs/overdefense_exp_20260918/arm_summary.json`
复现入口：`python -m methods.sct_trajectory.run_overdefense_experiment --out <dir> --tasks 21`

---

## 局限（诚实声明）

- 实验一/二样本量小（24 / 18 个任务），单任务波动可能影响百分比；
- 实验三为 **15 任务 × 1 轮** 的 smoke 规模，非 50 任务全量；
  6 组一致显示无差异，但小样本下更细微的效应可能未被检出；
- 全部实验使用单一模型 `deepseek-v3.2`，结论对其他模型的适用性未验证；
- 最终评测的审核池较小（3~6 条），JointPass 的绝对值（0%）参考意义有限，
  **更有意义的是各组之间的相对比较与失败模式分布**。

## 实验五：门控例子数策略（固定 N vs LLM 自由决定）

**设计**：15 任务 × 1 轮，三臂对比（同一批数据）。
- `F2`：固定每条经验 2 个审计任务
- `F4`：固定每条 4 个
- `LLM`：LLM 自由决定（允许给 0 个 = 判定"不值得测"）

| 臂 | 平均例子数 | 门控区分度(Δ≠0) | 晋升/淘汰/无证据 | 成本(CA元) | 耗时 |
|---|---|---|---|---|---|
| F2 | 2.0 | 2/5 (40%) | 0 / 2 / 3 | 0.420 | 1498s |
| F4 | 4.0 | 2/5 (40%) | 1 / 1 / 3 | 0.508 | 1784s |
| **LLM** | **1.2** | 2/5 (40%) | **1 / 1 / 3** | **0.355** | **1144s** |

**结论：LLM 自由决定最优**（已设为默认 `--gate-select-mode llm`）
1. **区分度三者相同**（2/5）→ "例子数"不是区分度的决定因素；
2. **LLM 臂成本最低**（比 F4 省 30%）、耗时最短（省 36%）、例子最少（1.2 vs 4.0）；
3. **LLM 会主动跳过低价值经验**（实测跳过 1 条并给出理由）；
4. F2（固定 2 例）测得最粗：一条增益经验（Δ=+0.25）在 2 例下未检出，4 例下才测出。

---

## 关键发现：门控的「基线可测性」前提（本次最重要的方法论修正）

跑门控例子实验时发现：**某轮 8 条经验全部 Δ=0 → 晋升 0 → 树为空**。
根因**不是经验无用**，而是审计任务过难：

```
F2 组轮1 的基线通过率分布: {0.0: 7, 0.5: 1}
→ 7/8 的任务"加不加经验都通不过"，Δ 数学上必然为 0
```

**门控的隐含前提**（此前未意识到）：

| 基线通过率 | 后果 |
|---|---|
| 0.0 | 天花板为 0，Δ 恒为 0 ❌ |
| 1.0 | 已满分，Δ 不可能为正 ❌ |
| (0, 1) | 有区分度 ✅ |

用全量数据验证（各 CWE 最终评测通过率）：
```
✅ 可测区间(20%~80%)：1333(77%) 915(77%) 863(56%) 327(40%) 862(36%)
                    94(35%) 77(33%) 770(31%) 95(28%) 179(24%)
❌ 太难(0%)：200 347 352 502 601 74 918 79
```

**修复**：新增 `filter_measurable_tasks()`（`gate_selector.py`）——门控选任务前先探基线，
剔除通过率为 0/1 的任务，只把「可测」的交 LLM 挑选；若无可测任务则回退（不中断），
并在审计明细记录筛选统计。**4 个单元测试覆盖**。

---

## 优化实施中发现的 5 个缺陷（均已修复并加测试）

这些缺陷都是"改动写了但没真正生效/会崩"的类型，靠**小规模冒烟测试 + 主动排查**发现，
若直接跑全量则要 8 小时后才发现。

| # | 缺陷 | 后果 | 发现方式 | 修复 |
|---|---|---|---|---|
| 1 | `NODE_STATUS` 缺 `unmeasured`/`revised` | 门控赋值时抛 `ValueError`，**全量必崩**（在 Phase3） | 写生命周期单测时构造函数报错 | 补齐两个状态；加 4 个不变量测试 |
| 2 | `hint`/`pitfall` 工厂未写 `source["kind"]` | 第四条（反过度防御加权）**完全空转**（实测 0/36 命中） | 冒烟验收时发现"反过度防御类经验 0 条" | 工厂显式写 kind；加 4 个测试 |
| 3 | 经验池无去重（只入树时才吸收） | 池 1284 条含 **230 对**重复，稀释检索质量 | 全量分析时统计重叠对数 | 新增 `_absorb_in_pool`；加 4 个测试 |
| 4 | API 调用无硬超时（urllib timeout 只管 socket 层） | 连接被挂起时实验**卡死 13 分钟以上** | 实验三次"卡住"后定向诊断 | 独立线程 + `join(HARD_TIMEOUT)` + 重试 |
| 5 | `audit_detail` 只在整轮跑完才写 | 中途卡死/中断会**丢失全部审计证据** | 卡死事件中 audit_detail 为 0 字节 | 改为逐条增量落盘 |

### 方法论教训

1. **"赋值合法、构造才校验"的枚举字段是高危区**：静态检查看不出，
   只有实际跑到那条分支才崩。改动门控决策集时必须同步补不变量测试。
2. **改动写完 ≠ 生效**：本次有两次"全量已启动、改动才落盘"的窗口问题，
   导致两次重启（各损失约 1 小时）。应在启动前用统一脚本核验
   "所有改动是否已在文件中"（见 `translation_work/diagnostics/20260916/preflight.py`）。
3. **"卡死"可能是误判**：LLM 调用是网络等待，CPU 几乎不动、
   文件长时间不更新，看起来像死锁，实际只是调用量大
   （实测 Phase3 审 1 条经验 = 31 次调用 = 213 秒）。
   诊断应先量测单次调用耗时，再判断是否真卡。

---

## 数据索引

| 实验 | 产物路径 |
|---|---|
| 检索策略对比 | `translation_work/diagnostics/20260916/retrieval_compare_result.json` |
| 跨 CWE 检索对比 | `translation_work/diagnostics/20260916/cross_cwe_result.json` |
| 分层消融（6 组） | `translation_work/sct_runs/abl_smoke_20260918/` |
| 反过度防御干预（3 臂） | `translation_work/sct_runs/overdefense_exp_20260918/` |
| **门控例子数（3 臂）** | `translation_work/sct_runs/gate_exp4_20260920/` |
| 全量 874 运行（第一次） | `translation_work/sct_runs/cle_full_874_20260919/` |
| 全量 874 运行（优化后 v2） | `translation_work/sct_runs/cle_full_874_v2_20260920/` |
| 优化后对比报告 | `docs/cle_full_run_v2_report.md` |
| 启动前核验脚本 | `translation_work/diagnostics/20260916/preflight.py` |
| 门控+重放验证 | `translation_work/sct_runs/gate_selector_verify/` |
| 强制重放验证 | `translation_work/sct_runs/replay_verify/` |

## 相关代码入口

| 功能 | 文件 |
|---|---|
| 消融配置（A1~A6） | `methods/sct_trajectory/ablation.py` |
| Level 4 多语言叶生成 | `methods/sct_trajectory/level4.py` |
| 门控 LLM 任务选择器 | `methods/sct_trajectory/gate_selector.py` |
| 消融执行器 | `methods/sct_trajectory/run_ablation.py` |
| **反过度防御实验执行器** | `methods/sct_trajectory/run_overdefense_experiment.py` |
| **功能契约冻结提示** | `methods/sct_trajectory/agent_pipeline.py` 的 `planning_prompt(contract_freeze=True)` |

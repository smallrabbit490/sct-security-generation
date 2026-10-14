# 最新一期运行中断原因 + 全链路问题排查（只读）

日期：2026-09-23
分析对象：`cle_context_874_20260923`（崩溃）、`cle_context_874_20260923_resume`（用户停止）、
`cle_chain_acceptance_20260923`（链路验收，已完成）

---

## 一、为什么中断：**日志编码崩溃**（不是方法/数据问题）

```
运行: cle_context_874_20260923
启动: 2026-09-23T09:25:16（全量 874，Phase1 303 条）
时间线:
  09:25:16  Phase1 冷启动开始
  10:37:03  Phase1 完成（303 条，耗时约 72 分钟）
  10:37:04  Phase2 轮1 开始
  10:37:34  **崩溃**（进入轮1 后 30 秒）

status = failed
stage  = phase2
detail = 多轮演进中断：UnicodeEncodeError
error  = 'gbk' codec can't encode character '\u26a0' in position 31
```

`\u26a0` = **⚠**。根因在 `run_closed_loop.py` 的 `progress()`：

```python
def progress(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)                              # ← 写 GBK 控制台（会炸）
    with open(log_path, "a", encoding="utf-8") as fh:    # ← 写文件（安全）
        fh.write(line + "\n")
```

某条进度消息里含 ⚠，`print` 到 Windows GBK 控制台时抛 `UnicodeEncodeError`，
被 `run_evolution_rounds` 的 `except` 捕获 → 标记 `failed` 并中断整轮演进。

**已经修好了**：
```
10:37:34  崩溃
10:51:23  新增防回归测试 tests/test_replay_and_failure_context.py
          ::test_phase2_coverage_warning_is_console_encodable
          （断言该警告串不含 ⚠ 且可 GBK 编码）
当前代码已无 ⚠
```

**含义**：Phase1 白跑了 72 分钟，但产物已落盘（`phase1_results.jsonl` 14.3 MB、
`experience_pool.jsonl` 6.1 MB），所以能用 `--resume-from` 续跑 —— 事实上后来就是这么做的。

---

## 二、全链路现有问题（6 项，按严重程度）

### P2 覆盖率目标自相矛盾：`replay_limit` 卡死 `coverage_target` ⚠️严重

```
replay 池            : 273 条
coverage_target=0.75 : 需覆盖 204 条
replay_limit=96      : 单轮最多选 96 条
→ 上限 96/273 = 35%，**无论跑多少轮都到不了 75%**
```

日志自己就报了：
```
[Phase2] [警告] 覆盖配额被 replay_limit=96 截断，本轮仍有 177 条未覆盖任务未补入；
         如需提高单轮覆盖请调大 --replay-limit
```

**这是你明确提过的需求（重放池使用率 ≥75%）与默认参数的直接冲突。**
当前 `--replay-limit` 默认 96，要满足 75% 需 ≥205。

### P3 基线可测性探测：只覆盖 2 个 CWE，且**探了不筛** ⚠️严重

```
[Phase3] 基线可测性标注：探测 20 个（覆盖 2 个 CWE）→ 正负皆可测 0，
         仅可测增益 10，仅可测有害 10，探测失败 0；全部 386 条保留，仅按可测范围排序
```

**两个问题**：

1. **只覆盖 2 个 CWE**：audit 池是**按 CWE 分块**排列的
   ```
   前 20 条 CWE: ['1333'×11, '179'×9]   ← 只有 2 个 CWE
   全池实际有 18 个 CWE
   ```
   探测取前 20 条 → 只落在 1~2 个 CWE → **探测结论无法代表 18 个 CWE**

2. **探了不筛**：日志明确写"全部 386 条保留，仅按可测范围排序"
   → 花了 20 个任务的生成+验证成本（每轮约 3 分钟），但**没有剔除任何经验**

### P4 LLM 门控选择器**连续失败**，功能形同虚设 ⚠️严重

```
[轮1] LLM 选择器：为 24 条经验规划了 120 个审计任务（覆盖 24 条经验，兜底=True，error=no_valid_plan）
[轮2] LLM 选择器：为 24 条经验规划了 120 个审计任务（覆盖 24 条经验，兜底=True，error=no_valid_plan）
```

`error=no_valid_plan` 来自 `gate_selector.py:274`：LLM 返回的 JSON 里 `plan` 为空/解析失败。

**含义**：你之前拍板的"让 LLM 自由决定挑哪些审计任务、挑几个（可以 0 个）"
**从未真正生效** —— 每次都回退到固定策略（每条经验取同 CWE 前 5 个任务）。
而且回退是"取同 CWE 前 5 个"，所以**同 CWE 的所有经验被测在同一批任务上**，
任务维度完全没有区分度。

### P5 门控覆盖率仍在 1% 量级

```
[轮1] 审计抽样：24/2417 条 → 覆盖率 1.0%
[轮2] 审计抽样：24/3275 条 → 覆盖率 0.7%
```

`audit_max_entries=24` 是硬上限，池越大覆盖率越低。

### P6 链路验收"跑通"了，但**门控晋升 0 条、树是空的** ⚠️严重

```
[轮1] 完成：选中 3，审计 2 条经验，晋升 0，归并 0，树 0 节点
[轮2] 完成：选中 5，审计 2 条经验，晋升 0，归并 0，树 0 节点
=== 冻结经验树 M*：85 条经验；开始审计池全量评测（6 条）===
=== 最终评测完成：JointPass 2/6 = 33.3% ===

tree.json 大小: 2 字节（内容 {}）→ 树节点数 0
```

**两轮都是"晋升 0"，树恒为空**，但日志又说"冻结经验树 M*：85 条经验"。

**这说明 `M*`（冻结树）与实际检索来源不一致**：
`final_evaluate` 检索用的是 `tree ∪ experience_pool`；
树为空时**实际全靠池里的 85 条 provisional 经验**。

→ **"冻结的 M*"是名义产物，真正起作用的是未经验证的池。**
这与之前的实测吻合（全量运行里树的 13 个节点从未被检索命中，918 个被注入的 id 全部来自池）。

### P7 仍有 GBK 崩溃风险点（会**掩盖真实错误**）

`methods/sct_trajectory/run_closed_loop.py`：

| 行 | 字符 | 内容 |
|---|---|---|
| 421 | ❌ U+274C | `raise SystemExit('❌ --resume-from 与 --out 指向同一目录…')` |
| 601 | ❌ U+274C | `raise SystemExit('❌ 续跑失败：…')` |

这两处是 `SystemExit` 的消息，Python 打印异常走 **stderr** → 同样是 GBK 控制台。
一旦触发，用户看到的会是 `UnicodeEncodeError` 而不是真正的错误原因（"续跑失败"）。
**属于掩盖真实错误的风险**，与本次崩溃同类。

---

## 三、问题汇总表

| # | 问题 | 严重度 | 证据 | 状态 |
|---|---|---|---|---|
| P1 | `⚠` 写 GBK 控制台致崩溃 | 🔴 已致中断 | `status.error` = U+26A0 | ✅ 已修（10:51） |
| P2 | `replay_limit=96` 卡死 `coverage_target=0.75`（上限 35%） | 🔴 需求未达成 | 日志"覆盖配额被截断，177 条未补入" | ❌ 未修 |
| P3 | 基线探测只覆盖 2/18 个 CWE，且探了不筛 | 🔴 探测结论无效 | 前 20 条只含 CWE 1333/179 | ❌ 未修 |
| P4 | LLM 门控选择器 `no_valid_plan` 连续失败 | 🔴 功能形同虚设 | 2 轮日志 `兜底=True` | ❌ 未修 |
| P5 | 门控覆盖率 0.7~1.0% | 🟡 | 24/2417、24/3275 | ❌ 未修 |
| P6 | 链路验收树 0 节点，M* 与实际检索来源不一致 | 🔴 架构不一致 | `tree.json` = `{}`，日志"晋升 0" | ❌ 未修 |
| P7 | `❌` 在 `SystemExit` 消息里，会掩盖真实错误 | 🟡 风险 | run_closed_loop.py:421/601 | ❌ 未修 |

---

## 四、建议修复优先级

| 优先级 | 措施 | 理由 |
|---|---|---|
| **1** | **P7：把 `progress()` 的 stdout 输出改为 GBK 安全**（`errors="replace"` 或统一去掉非 GBK 字符） | 一行修复，根除整类崩溃；否则任何新加的 emoji/符号都可能再崩一次 |
| **2** | **P2：`--replay-limit` 默认提到 ≥ 池的 75%**（或让 `coverage_target` 自动推导 `replay_limit`） | 你明确要求过覆盖率 ≥75%，当前参数自相矛盾 |
| **3** | **P4：查清 LLM 选择器为何 `no_valid_plan`**（大概率是提示词要求的结构与解析不匹配） | 这是"让 LLM 挑审计任务"的核心功能，现在是死的 |
| **4** | **P3：基线探测改为**按 CWE 分层抽样 + 真正剔除不可测任务 | 现在花成本但零收益 |
| **5** | **P6：统一 M* 的定义**（要么把池纳入 M*，要么让检索只读 M*） | 现在"冻结树"与实际检索来源不一致，实验结论无法归因 |
| **6** | P5：提高 `audit_max_entries` 或引入分层审计 | 覆盖率 1% 的门控无法代表 4518 条经验 |

---

## 五、产物

```
translation_work/diagnostics/20260923/
  find_unicode_bug.py      定位 ⚠ 来源与 progress 输出路径
  scan_gbk_unsafe.py       全仓扫描 GBK 不可编码字面量
  diagnose_chain.py        逐条核实日志暴露的可疑点
  verify_chain_issues.py   审计池 CWE 分布 / 覆盖率 / 链路测试状态
  chain_analysis.py        最终汇总核实
```

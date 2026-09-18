# CLE 自进化任务看板 — 需求与实施规划

> 位置：`methods/sct_trajectory/dashboard/`
> 状态：需求已确认（2026-09-18），待实施

## 一、目标

一个本地网页看板，用于：

1. **实时监控**正在进行的自进化流程（手动刷新 + 可选自动刷新开关）；
2. **回看**过往每一次自进化运行的完整过程；
3. 按阶段查看 Phase1（冷启动）/ Phase2（重放进化）/ Phase3（门控与最终评测）的产物与指标。

## 二、技术形态（已拍板）

| 项 | 决定 |
|---|---|
| 位置 | `methods/sct_trajectory/dashboard/` |
| 后端 | Python 标准库 `http.server`，零第三方依赖，只读 `translation_work/` |
| 前端 | 原生 HTML + JS（无构建步骤），图表用内联 SVG 手绘 |
| 刷新 | **默认手动刷新**；提供"自动刷新"开关（默认关，打开后 5s 轮询） |
| 端口 | 默认 `127.0.0.1:8770`，可用 `--port` 覆盖 |

启动方式：

```powershell
python methods/sct_trajectory/dashboard/server.py --port 8770
# 浏览器打开 http://127.0.0.1:8770
```

## 三、数据契约（需固化，避免路径变动找不到）

"实时监控"要求运行过程中的产物路径**稳定且可增量读取**。为此固化如下结构：

### 3.1 每次运行目录

```text
translation_work/sct_runs/<run-name>/
├─ run_metadata.json        # 运行配置：模型、参数、开始时间、commit、代码版本   【新增】
├─ status.json              # {"status":"running|completed|failed","stage":"phase2", 【新增】
│                           #  "updated_at":..., "error":null}
├─ progress.log             # 已有的逐条进度日志
├─ pools.json               # 三池任务清单（source/replay/audit 的任务 id 与 CWE）【新增】
├─ phase1_results.jsonl     # 【补字段】失败案例的生成代码 + 四步上下文
├─ trajectories.jsonl       # Phase2 轨迹（已有）
├─ rounds.jsonl             # 每轮汇总（已有）+ 【补】树快照路径
├─ tree_snapshots/          # 每轮结束时的整棵树快照                        【新增】
│  ├─ phase1.json
│  ├─ round1.json
│  └─ round2.json
├─ audit_detail.jsonl       # Phase3 门控审计明细（已有）
├─ gate_records.jsonl       # 门控记录（已有）
├─ experience_pool.jsonl    # 统一经验池（已有）
├─ error_ledger.jsonl       # 错题本（已有）
├─ frozen/m_star.jsonl      # 冻结经验树 M*（最终评测用）                   【新增】
├─ final_eval.jsonl         # 审计池全量评测的逐任务结果                    【新增】
├─ final_eval_summary.json  # 最终评测汇总（分 CWE 的 JointPass/ABCD）      【新增】
├─ tree.json                # 最终树（已有）
└─ summary.json             # 运行汇总（已有）
```

### 3.2 全局运行索引

```text
translation_work/sct_runs/runs_index.json
```
每次运行启动时登记、结束时更新：run-name、路径、状态、开始/结束时间、模型、任务数。
看板的运行列表直接读它，**不靠扫描目录猜**。

### 3.3 状态识别规则（"进行中 / 已完成 / 未进行"）

| 显示 | 判据 |
|---|---|
| 🔵 进行中 | `status.json` 存在且 `status=running`，且进程心跳 `updated_at` 在 120s 内 |
| ✅ 已完成 | `status.json` 的 `status=completed` 且 `summary.json` 存在 |
| ❌ 失败 | `status.json` 的 `status=failed`（含 error 字段） |
| ⚪ 未进行 | 该阶段在 `rounds.jsonl` 中没有对应记录（如 Phase3 未跑）→ 页面写"未进行" |

## 四、看板功能规格

### 4.0 全局

- 顶部：**运行选择器**（下拉列表 + 可按时间滑动浏览）、状态徽章、刷新按钮、自动刷新开关；
- **总任务数**汇总卡（source/replay/audit 三池各多少、已完成多少）；
- 阶段进度条（Phase1 / Phase2 / Phase3 各自进度与状态）。

### 4.1 Phase 1（冷启动）

| 功能 | 数据来源 |
|---|---|
| 第一阶段形成的树长什么样 | `tree_snapshots/phase1.json`（树形结构可视化：CWE → 不变量 → 语言叶） |
| 第一次动态测试成功率 | `phase1_results.state_first` 聚合 |
| 迭代后（修复轮）测试成功率 | `phase1_results.state_after_repair` 聚合 |
| **测试失败的例子单独展示** | 失败项列表，**可展开看生成代码、验证明细、与修复轮的 diff** |
| ABCD 四态统计 | `state_first` 与 `state_after_repair` 各一张分布图（柱状 + 数字） |

### 4.2 Phase 2（重放进化）

| 功能 | 数据来源 |
|---|---|
| 先查看任务池 | `pools.json` 的 replay 池（任务 id / CWE / 是否被选中） |
| 每个迭代（含初次）主动回放选了什么任务 | `rounds.jsonl[].schedule`（LLM 原始决策 + 选中 id + 理由） |
| 每次运行完的 ABCD 率（功能/安全通过） | `trajectories.jsonl[].states` 按轮聚合 |
| 每次树的成长轨迹（图） | `tree_snapshots/*.json` → 节点数折线 + 结构快照对比 |

### 4.3 Phase 3（门控 + 最终评测）

| 功能 | 数据来源 |
|---|---|
| 经验需要通过的任务数是哪些 | `audit_detail.jsonl`（候选 × audit_task_count × 具体任务 id） |
| 树的变化 | 门控前后树快照对比（哪些入树、哪些 revised/demoted/unmeasured） |
| **最终评测**：把固化经验树在审计池全量跑一次 | `frozen/m_star.jsonl` + `final_eval.jsonl` / `final_eval_summary.json` |
| 最终评测的表现 | 分 CWE 的 JointPass/ABCD + 失败案例（与 Phase1 同款视图） |

**最终评测语义（已确认）**：
- 取**固化后的经验树**（冻结快照 M*），不再做逐条经验审计；
- 在**全部 298 条审计任务**上跑一遍（检索注入 → 生成 → 功能/安全动态测试）；
- 产出分 CWE 的通过率、ABCD 分布、失败案例；
- 经验池范围：**包含全部经验池条目**（不只 active）。

### 4.4 附加功能（已确认）

- 自动刷新开关（默认关）；
- 导出 JSON/CSV（每个阶段的数据可导出，便于写论文）；
- 成本/耗时统计（各阶段 LLM 调用量估算、耗时）；
- 失败案例的 **diff 对比**（与成功案例或修复前后对比）。

## 五、需要新增/修改的代码

| 文件 | 改动 |
|---|---|
| `closed_loop.py` | ① Phase1 落盘失败案例代码与四步上下文；② 每轮写树快照；③ 写 `pools.json`；④ 写 `status.json` 心跳；⑤ 新增 `final_evaluate()`（冻结树全量跑审计池） |
| `run_closed_loop.py` | 写 `run_metadata.json`、登记 `runs_index.json`、收尾写 `status.json`、可选执行最终评测 |
| `frozen.py` | 冻结导出 `frozen/m_star.jsonl` |
| `dashboard/server.py` | 【新建】只读 API |
| `dashboard/static/*` | 【新建】页面与脚本 |
| `dashboard/README.md` | 【新建】使用说明 |

## 六、实施步骤

1. **补落盘 + 固化路径**（`closed_loop.py` / `run_closed_loop.py` / `frozen.py`）；
2. **实现最终评测** `final_evaluate()`（冻结树 + 全量审计池）；
3. **写后端** `server.py`（运行列表、各阶段 API、导出）；
4. **写前端**（运行选择器 + 四个 Tab + 图表）；
5. **兼容老运行**（缺字段显示"该运行未采集此数据"）；
6. **真实验证**：用已有运行 + 一次小规模新运行（含最终评测）跑通看板全部视图。

## 七、验收标准

- 看板能列出所有历史运行并正确标注"进行中/已完成/失败/未进行"；
- Phase1 能看到树结构、两次测试成功率、ABCD 分布、失败案例（含代码与 diff）；
- Phase2 能看到任务池、每轮选中与理由、ABCD 曲线、树成长轨迹图；
- Phase3 能看到审计任务数、树变化、最终全量评测结果；
- 老运行打开不报错（缺失字段降级显示）；
- 导出 JSON/CSV 可用；成本统计显示各阶段调用量。

# CLE 自进化任务看板

只读网页看板，用于**实时监控**与**回看** CLE（对比式经验自进化）的每一次运行。

## 启动

```powershell
python methods/sct_trajectory/dashboard/server.py --port 8770
# 浏览器打开 http://127.0.0.1:8770
```

- 零第三方依赖（Python 标准库 `http.server`）；
- **严格只读** `translation_work/`，不会修改任何实验产物或经验库；
- 默认手动刷新；需要盯实时进度时勾选「自动刷新(5s)」。

## 页面结构

| Tab | 内容 |
|---|---|
| **概览** | 总任务数、三池（D_init/D_grow/D_gate）、阶段进度、运行元数据与 LLM 调用量粗估、数据完整性提示 |
| **Phase 1 冷启动** | Phase 1 形成的经验（按 CWE 分组）、第一次测试 vs 迭代后测试成功率、ABCD 四态分布、**失败案例（可展开看生成代码与 diff）** |
| **Phase 2 重放进化** | 任务池、每轮主动回放选中了哪些任务（含 LLM 理由）、每轮 ABCD、**树成长轨迹图** |
| **Phase 3 门控与最终评测** | 每条经验需要通过的任务数、门控判定分布、冻结 M*、**最终评测（固化经验树在审计池全量运行）** 的分 CWE 表现与失败案例 |
| **经验库** | 统一经验池全部条目（active/provisional/revised/unmeasured + 来源）、审计池任务清单 |

顶部工具条：运行选择器（含状态徽章：进行中/已完成/失败/已中断/未知）、刷新、自动刷新开关、导出 JSON（Phase1/Phase2/Phase3/任务池）。

## 状态识别

| 显示 | 判据 |
|---|---|
| 🔵 进行中 | `status.json` 的 `status=running` 且心跳在 120s 内 |
| 🟡 已中断 | `status=running` 但心跳超过 120s（进程疑似中断） |
| ✅ 已完成 | `status=completed`，或历史运行存在 `summary.json` |
| ❌ 失败 | `status=failed` |
| ⚪ 未进行 | 该阶段无对应记录（页面直接写"未进行"） |

## 数据契约

看板只读 `run_artifacts.py` 定义的固定路径，不靠扫描目录猜：

```text
translation_work/sct_runs/
├─ runs_index.json                    # 全局运行索引（运行列表来源）
└─ <run-name>/
   ├─ run_metadata.json  status.json  progress.log  pools.json
   ├─ phase1_results.jsonl            # 含失败案例代码/差分/四步上下文
   ├─ trajectories.jsonl  rounds.jsonl
   ├─ tree_snapshots/*.json           # phase1 / round1 / round2 ... 树与经验池快照
   ├─ audit_detail.jsonl  gate_records.jsonl
   ├─ experience_pool.jsonl  error_ledger.jsonl
   ├─ frozen/m_star.jsonl             # 冻结经验树 M*
   ├─ final_eval.jsonl  final_eval_summary.json
   └─ tree.json  summary.json
```

## 兼容历史运行

早于看板数据契约的运行（�� `cle_full_20260916_194917`）缺少
`pools.json` / `status.json` / `tree_snapshots/` / `frozen/` / `final_eval_summary.json`：

- 页面顶部显示**数据完整性提示**，列出该运行未采集的项；
- 能算的照样算：Phase1 成功率会**回退用 `outcome` 字段**统计并标注"数据来源：outcome(旧字段回退)"；
- 算不出的显示 `—` 或"未采集"，**不会伪造成 0**。

## API

| 端点 | 说明 |
|---|---|
| `GET /api/runs` | 运行列表（含状态） |
| `GET /api/overview?run=` | 总任务数、三池、阶段进度、元数据 |
| `GET /api/phase1?run=` | 树/经验池快照、两次测试成功率、ABCD、失败案例 |
| `GET /api/phase2?run=` | 任务池、每轮调度、ABCD、树成长轨迹 |
| `GET /api/phase3?run=` | 审计明细、门控判定、冻结清单、最终评测 |
| `GET /api/tree?run=&label=` | 指定轮次的树快照 |
| `GET /api/pool?run=&which=` | 三池之一的清单 |
| `GET /api/export?run=&kind=` | 导出 JSON（kind: phase1/phase2/phase3/pool） |

## 已知限制

- LLM 调用量为**粗估**（Phase1≈7 次/任务，Phase2≈40 次/轮），非精确计费；
- 「树成长轨迹」按轮快照绘制；若运行未开启树快照（历史运行），该图显示"暂无"。

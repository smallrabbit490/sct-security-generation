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
| **概览** | 总任务数、三池（D_init/D_grow/D_gate）、阶段进度、**精确成本表**（调用次数/输入输出 tokens/费用，单价来源已标注）、数据完整性提示 |
| **Phase 1 冷启动** | Phase 1 形成的经验（**可缩放拖动的 SVG 树形图**）、第一次测试 vs 迭代后测试成功率、ABCD 四态分布、**失败案例（左右分栏对比同 CWE 成功案例 + 并排 diff + 四步 Agent 归因对比）** |
| **Phase 2 重放进化** | **各轮通过率表（功能/安全/联合，含"初始(Phase1)"基线行 + 三折线图 + 任务内 c⁰→c¹ 对比）**、任务池、**逐轮折叠卡片**（每轮选中任务 + LLM 理由 + 本轮四态 + **强制重放标记** + **检索命中率** + **零命中补偿数**）、ABCD、**树成长轨迹（逐轮相邻 diff：这一轮比上一轮多了哪些规则）** |
| **Phase 3 门控与最终评测** | **门控 LLM 选择器详情**（每条经验选了哪些任务、是否跨 CWE、LLM 选择理由）、**每条经验的升级/降级明细**、**树的变化**（门控前后对比 + 分 CWE 增减柱状图 + 逐轮树状态 + 门控后树形图）、冻结 M*、**最终评测**（口径声明 + 三臂对比 + 四态分布 + 距目标线差距分解 + 分 CWE 表现 + 失败明细） |
| **经验库** | 统一经验池全部条目（active/provisional/revised/unmeasured + 来源）、审计池任务清单 |

顶部工具条：运行选择器（含状态徽章：进行中/已完成/失败/已中断/未知）、刷新、自动刷新开关、导出 JSON（Phase1/Phase2/Phase3/任务池）。

## 树形图交互

- 三层布局：`CWEFamily`（CWE 根）→ `SecurityInvariantNode`（不变量，按 status 上色）→ `LanguageLeaf`（语言叶）
- **全部节点都画**（不过滤状态）；节点按状态着色：active 绿 / consolidated 蓝 / provisional 灰 / revised 黄 / retired 红 / unmeasured 蓝灰
- **滚轮缩放**（以鼠标位置为焦点）、**按住拖动平移**、按钮：放大 / 缩小 / 100% / 适应窗口
- 悬停节点显示完整不变量文本（图上会被截断）
- **可切换列表视图**看全文

## 每轮通过率（Phase 2）

看板按迭代轮次给出三项通过率，**分母是该轮实际产生的轨迹数**：

| 迭代 | 功能通过率 | 安全通过率 | 联合通过率 | 样本数 |
|---|---|---|---|---|
| 初始（Phase1 冷启动） | x/y | x/y | — | 冷启动任务数 |
| 第 1 轮 | x/y | x/y | x/y | 本轮轨迹数 |
| 第 2 轮 | … | … | … | … |

> 分母逐轮递减是**预期行为**：已达 A（功能+安全都过）的任务不会再跑后续轮次。
> 页面每格同时显示百分比与绝对数，避免小样本误导。

## 最终评测面板（Phase 3）

面板只读 `final_eval_summary.json` + `final_eval.jsonl` + `pools.json`，**不重跑任何验证**。

| 区块 | 内容 | 关键口径 |
|---|---|---|
| 口径声明 | `independent_heldout`、`selection_bias`、`generation_policy`、`long_term_memory_modified` | 引用本页任何数字都必须一并说明，否则会把带选择偏差的观测当成泛化结果 |
| 三臂对比 | baseline / memory / filtered 的功能、安全、Joint | **分母是 `measured`（实测样本）**，未测量单列，不折算成失败或通过 |
| 四态分布 | 每臂 A/B/C/D 堆叠条 | A=功能+安全都过，B=只过功能，C=只过安全，D=都不过 |
| 距目标线差距分解 | 当前 / 需要达到 / 还差 / 可回收桶 / 需回收比例 | 目标线（30–50%）仅用于量化差距，**不是已取得的结果**；C 与 B 各回收 1 条 = Joint +1，D 桶不计入 |
| 分 CWE 表现 | 按 Joint 通过率升序，0% 家族整行标红 | 对"安全全过 / 功能全挂"且样本 ≥5 的家族给出提示：优先排查过度防御或夹具签名，而非模型能力 |
| 失败明细 | 逐任务 CWE、状态、功能、安全、语法、检索到的经验 | 默认 C 桶优先，它是差距分解里的可回收空间 |

### 为什么 `final_eval_summary.json` 需要后端补字段

原始 `final_eval_summary.json` **没有** `by_cwe` 和 `failures` 字段：

- `final_eval.jsonl` 的每一行只有 `task_id`，**没有 `cwe`**；CWE 只存在于 `pools.json` 的 `audit` 列表，必须做显式 join，否则分 CWE 表恒为空；
- 旧前端读 `fe.failures`，字段不存在时退化成"全部通过 🎉"——一个会**静默说谎**的假阳性。

`server.py` 的 `_enrich_final_eval()` 负责补出这两项。相关硬规则：

- 字段缺失一律显示"该运行未采集失败明细（字段缺失，不代表全部通过）"，**不许报喜**；
- 验证状态只认产物里显式记录的 `status`，缺失记为 `unmeasured`，**绝不默认为 `pass`**。

## 成本统计（精确）

计费基于 API 返回的**真实 `usage` 字段**（不是本地估算），按调用点分类累计：

| 字段 | 含义 |
|---|---|
| `calls` | 调用次数 |
| `prompt_tokens` / `completion_tokens` | 输入 / 输出 tokens |
| `cost_ca` | 费用（CA元） |
| `usage_missing` | **响应缺 usage 的次数**（不计费，但不默认为 0，避免"看起来便宜"） |
| `errors` | 调用失败次数（无 usage） |

单价来源：ChatAnywhere《费用标准及模型列表》。页面会显示单价、币种与来源链接。
更新单价请改 `methods/sct_trajectory/cost_tracker.py` 的 `PRICING`。

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
| `GET /api/overview?run=` | 总任务数、三池、阶段进度、精确成本 |
| `GET /api/phase1?run=` | 树/经验池快照、两次测试成功率、ABCD、失败案例（含对照成功案例） |
| `GET /api/phase2?run=` | 任务池、每轮调度（含强制重放/检索命中/零命中补偿）、分项通过率、树成长轨迹 |
| `GET /api/phase3?run=` | 门控选择器详情、升级降级明细、树变化、冻结清单、最终评测 |
| `GET /api/tree_growth?run=` | 逐轮相邻 diff（新增/移除/变更的规则清单） |
| `GET /api/tree?run=&label=` | 指定轮次的树快照 |
| `GET /api/pool?run=&which=` | 三池之一的清单 |
| `GET /api/export?run=&kind=` | 导出 JSON（kind: phase1/phase2/phase3/pool） |

## 强制重放与零命中补偿（Phase 2）

| 机制 | 说明 | 看板展示 |
|---|---|---|
| **强制重放** | 上一轮末态 ∈ {B,C,D} 的任务**必须**进入下一轮，不受 LLM 调度影响（最多重放 3 次） | 轮卡片标题的「强制重放 N」+ 具体 task id |
| **零命中补偿** | 检索一条经验都没命中时，专门为该 CWE 缺口提炼一条经验 | 轮卡片的「检索命中 x/y」+「零命中补偿 N 条」 |

## 门控 LLM 任务选择器（Phase 3）

替换原先 `by_cwe[:N]` 的硬取方式：让 LLM 同时看到「待审经验 + 候选审计任务」，
为每条经验挑最能检验它的任务（**自由决定条数、允许跨 CWE** 以检验泛化性）。

看板展示：每条经验选了哪些任务（绿=同 CWE / 黄=跨 CWE）、跨 CWE 数量、LLM 选择理由，
以及最终的**升级（supported）/降级（demoted/revised）** 明细。

## 已知限制

- LLM 调用量为**粗估**（Phase1≈7 次/任务，Phase2≈40 次/轮），非精确计费；
- 「树成长轨迹」按轮快照绘制；若运行未开启树快照（历史运行），该图显示"暂无"。

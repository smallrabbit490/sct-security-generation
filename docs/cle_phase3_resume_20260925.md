# CLE 全量 Phase 3 中断、修复与续跑（2026-09-25）

## 故障与根因

原全量运行 `translation_work/sct_runs/cle_full_deepseek32_20260924_full/` 在 874 条 PLT 三池（303/273/298）和三轮 Phase 2 完成后，于 Phase 3 首轮检索结束前失败。`status.json` 只留下 `ValueError`，`global_gate_events.jsonl` 为 0 行。旧异常处理未保存消息及 traceback，因此无法从原进程日志直接确认抛错行；未发现 401/403/429、连接超时或 Docker 故障证据。

代码与输入核验排除了 298 个任务 ID 重复、4456 张经验卡 ID 重复/缺失、Base/Plus 混入。检索器在卡片上附加逐任务 `retrieval_audit` 和 `_relevance_gate`，门控 `_snapshot` 却把它们计入“经验正文版本”。同一卡被不同题检索时，这些查询轨迹自然变化，触发 `experience version changed within frozen gate`。新增回归测试以同卡跨题不同轨迹复现，修正版本哈希仅排除这两个检索瞬态字段，仍保留完整卡片快照与逐次 SHA-256；正文变化仍会被拦截。

Phase 3 异常路径现保存 `phase3_exception.json`（异常类型、截断消息、traceback、任务/经验数和并发配置），不保存 prompt、响应或凭据。新增从已完成 Phase 2 的运行只读恢复经验池的路径，跳过 Phase 1/2，写入全新目录。旧目录完整保留。12 条真实链路验收在 `translation_work/diagnostics/20260925/phase3_chain_smoke12_v2/` 完成非空 D_gate 两题、三臂和冻结；24 项相关回归通过。

## 正式续跑

新目录 `translation_work/sct_runs/cle_full_deepseek32_20260924_phase3_resume_20260925/` 从旧目录恢复三轮完成标记、303 条 Phase 1 结果和 4456 张经验卡，只执行训练侧 298 题 Phase 3。`gate_input_memory.json` 与旧目录的同名数据结构逐条相等；旧 `experience_pool.jsonl` SHA-256 为 `b80327f26b2f8a8099eee604b4d74bb4614c4cee0828569ddf16b4499a0daac7`。本次未使用 Base/Plus 反馈更新库。

| 单次生成条件 | Function | Secure | Joint | 完整实测 / 298 |
|---|---:|---:|---:|---:|
| 纯 prompt | 84 | 198 | 62 | 294 |
| 原经验库检索 | 83 | 213 | 67 | 291 |
| 停用后重新检索 | 92 | 224 | 80 | 295 |

三臂各 298 行、共 894 条逐题事件；93 组局部归因、411 张曝光卡决策（397 retained、11 retired、3 review），最终冻结文件 4456 行，`final_eval.jsonl` 298 行。原库对纯 prompt 的 Joint 配对独赢/独输为 26/21，精确双侧 p=0.5601；过滤后对原库为 19/6，p=0.0146，对纯 prompt 为 30/12，p=0.0079。过滤规则和结果都来自同一 D_gate，后两项存在选择偏差，不能作为独立泛化证明；Plus 尚未测。

错误按缺测处理，未驱动停用：纯 prompt 1 次生成错误，原库检索 6 次错误（5 RuntimeError、1 JSONDecodeError），过滤后检索 3 次 RuntimeError。报告中的 API 成本仅为本次 Phase 3：2243 次逻辑调用、11,829,468 tokens、15.0502 CA 元，含 7 次调用错误；embedding 296 次调用、1 次失败、194,189 tokens。不能把它冒充整次 874 条训练成本。

Watchdog 报告在 `translation_work/diagnostics/vhdx_watchdog_cle_full_deepseek32_20260924_phase3_resume_20260925.json`：程序退出码 0、VHDX 增量 0、残留容器 0。通用判据因 PLT 本地 `python -I` 全程未创建 Docker 容器而将 `container_stable_ok` 记为 false，故总体 `passed=false`；这是判据不适用，不是容器或实验失败。最终状态为 `completed`。原失败目录及日志仍保留。

## 冻结后 Base/Plus Python 独立评测（2026-09-25）

原本地评测入口只从 `tree.json` 导出经验，但本次 Phase 3 续跑的树为空，实际冻结结果在 `frozen/m_star.jsonl`。入口现优先读取该冻结池，剔除 11 张 `retired` 卡，把 4445 张未退役卡转成检索格式；源池 SHA-256 为 `5dccaeac778c714dd8fa81be26cb99256ea017aa9ea3e55beba49a0e4f7a9c21`。相关 33 项测试通过，Base/Plus 各 1 题双组冒烟完成真实代码生成及本地功能/安全验证。

全量结果保存在 `translation_work/validation_runs/cle_phase3_resume_20260925_python/`，其中四组各有 `rows.jsonl` 与 `summary.json`，冻结元数据在 `frozen/freeze_metadata.json`。运行退出码 0；各组任务 ID 唯一，共 510 行。

| 子集 | 组别 | Function | Secure | Joint | 生成错误 |
|---|---|---:|---:|---:|---:|
| Base（115） | 冻结库 | 27 | 10 | 5 | 1 |
| Base（115） | 空库 | 37 | 10 | 7 | 0 |
| Plus（140） | 冻结库 | 88 | 34 | 32 | 0 |
| Plus（140） | 空库 | 86 | 37 | 35 | 0 |

唯一生成错误是 Base 冻结库组 `CWE-406_mitre_1.py` 的 `model_output_truncated`（重试 2 次），计入分母。当前独立评测使用本地 TF-IDF 检索和 1024-token 生成上限；训练侧 Phase 3 使用 semantic-LLM 检索与 4096-token 上限。因此这份结果表明**当前冻结评测路径下未观察到 Joint 提升**，不能单独证明经验内容无效，也不能把 D_gate 上的提升当成 Base/Plus 泛化收益。评测禁用反馈，Base/Plus 结果没有写回经验库；Python 验证使用本地 `python -I`，未运行 Docker。类型检查、资源限制和异常行为按证据记为未测量。
## 对齐训练检索后的正式重测（2026-09-25）

上一节的 TF-IDF 结果不作为正式结论。已将评测入口固定为 `run_plus_frozen_comparison.py` 的 Prompt+检索+经验库流程：完整任务契约、训练侧 `semantic_llm` embedding 检索（`text-embedding-3-large` 与共享缓存）、最多一次修复、同一冻结池、常驻 Docker 验证；同时保留空库对照。运行目录为 `translation_work/validation_runs/cle_aligned_full_20260925/python/`，watchdog 为 `translation_work/diagnostics/vhdx_watchdog_cle_aligned_full_20260925.json`。

全量共 255 题、510 行，任务键唯一，官方正向校准 255/255，环境错误 0，冻结池 SHA 未改变，watchdog PASS 且 VHDX 增量 0。两次 semantic 检索请求失败，均显式记录为 `preparation_errors`；其余经验臂初次检索均记录 `retrieval_mode=semantic`。

| 子集 | 方法 | 首次 Function | 首次 Secure | 首次 Joint | 修复后 Function | 修复后 Secure | 修复后 Joint |
|---|---|---:|---:|---:|---:|---:|---:|
| Base（115） | Prompt+semantic 检索+经验库 | 29 | 8 | 6 | 31 | 8 | 6 |
| Base（115） | Prompt+空库 | 31 | 8 | 5 | 32 | 8 | 5 |
| Plus（140） | Prompt+semantic 检索+经验库 | 110 | 36 | 36 | 112 | 41 | 41 |
| Plus（140） | Prompt+空库 | 109 | 36 | 35 | 106 | 41 | 40 |

按截图口径，经验库组 Plus 首次 `36/140`（25.71%）、修复后 `41/140`（29.29%）；空库对照为 `35/140`→`40/140`。这次流程与训练侧检索已对齐；逐题配对结果应优先于单看总数。

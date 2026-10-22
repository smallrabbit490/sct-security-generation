# CLE 独立消融实验

唯一入口：`python -m methods.cle_ablation.runner`，模型固定为 ChatAnywhere `deepseek-v3.2`，temperature=0，默认 max_tokens=4096。

| 臂 | 生成路径 | 经验来源 | 最大生成次数 |
|---|---|---|---|
| P0 | 纯 prompt | 空 | 1 |
| P1 | prompt + 明确功能/安全契约 | 空 | 1 |
| P2 | 初析→规划→生成 | 空 | 1 |
| P3 | P2 + 一次修订 | 空 | 2 |
| P4 | 初析→检索→适用性复析→规划→生成 | Phase1 快照 | 2 |
| P5 | 初析→检索→规划→生成 | 最终冻结 M*，不注入 negative_guardrail | 2 |
| P6 | P5 + 适用性复析与拒绝卡隔离 | 最终冻结 M*，不注入 negative_guardrail | 2 |
| P7 | 当前完整冻结前向链 | 最终冻结 M*，完整卡片 | 2 |

## 解释边界

P5 关闭的是生成侧复析/采用筛选；语义检索仍使用训练侧的向量召回与 LLM 适用性选择。它不是“完全没有适用性判断”。
P6/P7 只改变注入字段，不重新训练库；删除 negative_guardrail 也不能保证其他字段没有负向建议。P5–P7 共用已门控 M*，因此不能据此宣称证明生命周期门控收益。真正逐卡/整库门控、负向知识去除、R0–R3 和 RESCUE 查询等扩展需单独实现与运行。

Phase1 快照从旧全量运行读取，最终 M* 从 Phase3 恢复后的冻结目录读取；两者不只差卡片数量，还差轮次和门控状态，P4/P7 是库配置对比而非纯单因素实验。

PLT 使用 D_gate 中的 298 条，曾用于门控，只能报告开发诊断。任务内可反馈功能/安全状态做一次修复，使用本地 `python -I`，不启 Docker。不保存隐藏测试详情。

Base/Plus 分别 115/140 条，仅 Python。验证走常驻 Docker 池，先逐题正向校准。隐藏测试状态不进入生成、检索或经验更新。P3–P7 固定两次生成，第二次只看自己的代码；最终以末次代码得分，不根据隐藏测试挑选代码。此协议与 PLT 的反馈修复不同，论文必须分开描述。Base/Plus 曾被查看，不能称为全新盲测。

## 执行与续跑

```powershell
& D:/ANACONDA/python.exe -m methods.cle_ablation.runner --dataset PLT --limit 1 --out translation_work/diagnostics/20260928/cle_ablation_smoke_all
& D:/ANACONDA/python.exe -m methods.cle_ablation.runner --dataset PLT --out translation_work/diagnostics/20260928/cle_ablation_full
& D:/ANACONDA/python.exe tools/vhdx_watchdog.py --label cle_ablation_base --max-containers 16 --interval 2 -- D:/ANACONDA/python.exe -m methods.cle_ablation.runner --dataset Base --out translation_work/validation_runs/cle_ablation_base_20260928/python
```

同一参数重跑同一目录会跳过已落盘行；源码、任务列表、模型参数或经验哈希不同则拒绝续跑。已落盘失败行保留，重试应使用新目录。

Base 与 Plus 的 watchdog 必须串行启动：watchdog 启动清理会删除其他评测的活跃池。runner 自身已有跨进程锁，但不能保护其外层 watchdog 的启动清理。

输出：`rows.jsonl`、`summary.json`、`run_metadata.json`、`report.md`；CodeSecEval 额外保存脱敏 `calibration.json`。汇总区分首次/末次、F/S/Joint、缺测和相对 P0 的完整可测配对。缺测留在总分母但不计成功，配对统计单独排除缺测，不补零。

默认并发为 8（可设 1–16），生成和检索共享 HTTP 在途上限。模型请求器内部可能重试，calls 表示逻辑请求次数；货币成本未测量。全量完成前不得将冒烟结果写入论文主表。

## 固定库记忆Q扩展（2026-10-15）

Q开发对照入口为`python -m methods.cle_ablation.run_memory_q`。该入口直接调用本目录原`runner.run_one(..., 'P7', ...)`，替换选卡模式并增加D_grow采用奖励。`--stage learn`学习后冻结；`--stage compare`在D_gate比较Q0原LLM、Q1相似度、Q2相似度＋Q、Q3打乱Q。各臂共用本轮JSON格式提示修订，原生生成与验证函数保留。

逐题保留原生`attempts/generation/validation/usage`，补充`final/arm/family_id`供远程M/A统计直接消费。运行后用`python -m methods.cle_ablation.audit_memory_q --root <本轮目录>`只读检查记录、重算统计和Q归因。原P0–P7入口、默认值与历史文件保留。

8题学习和24题四臂已完成：Q2 Joint=4/24、Q1=3/24、Q0/Q3均5/24，尚无Q提分证据。开发门未通过，未运行条件确认和正式全量训练。根`run_closed_loop`的Q接线及`run_memory_q_frozen`冻结消费者已实现；Base/Plus尚缺原验证镜像，只完成离线冻结核对。

最新规格、命令、精简结果和分析见[自主执行结果](../../docs/CLE_Q任务书自主执行实验规格与结果_20261015.md)；四题探针及历史机制关系保留在[远程协议对齐与实验方案](../../docs/CLE_Q迁移远程协议对齐与实验方案_20261015.md)。

最新全D_grow学习库的8题三臂已完成（2026-10-16）：比较入口增加`--shuffle-scope cwe`，仅同CWE内置换Q/visits；默认global保留历史行为。Q1/Q2/Q3 Joint=2/8、1/8、1/8。Q2在5题改变集合，3题采用新增卡，未增加Joint。使用`python -m methods.cle_ablation.report_memory_q_probe --root <probe-root> --out <curated-path>`重算原生格式、同查询排序与采用、配对统计及成本。完整规格、命令和逐题结论见[最新Q库8题实验](../../docs/CLE_最新Q库8题三臂实验与逐题分析_20261016.md)，不是完整CLE或Base/Plus结果。

后续[共享首次初析控制实验](../../docs/CLE_Q回放与共享初析8题实验_20261016.md)已完成：新增`--shared-initial`仅复用c0初析，c1仍独立。8题首次query及候选分数完全一致，Q1/Q2/Q3 Joint=2/8、3/8、2/8；唯一额外成功没有经验卡介入，不能归因Q。另发现1015题面/夹具全局变量名不一致，保留主表并单列辅助分析。共享调用计费单列，未启动确认、完整训练或Base/Plus。

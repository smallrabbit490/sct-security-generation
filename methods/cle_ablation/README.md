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

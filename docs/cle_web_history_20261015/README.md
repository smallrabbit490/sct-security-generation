# CLE 网页历史数据快照（2026-10-15）

本目录记录 CLE 只读网页看板在本机运行区发现的历史记录清单，供仓库审计和后续复现定位。网页源代码位于 `methods/sct_trajectory/dashboard/`；网页完整运行时仍读取本机 `translation_work/sct_runs/`，不会把本目录当作实验输入。

## 盘点结果

- 找到 **35 个**以 `cle` 开头的 CLE 运行目录。
- 原始运行区共 **4,693 个文件，4,086,217,751 字节（约 3.81 GiB）**。
- 其中网页会聚合的摘要、状态、成本、轮次和最终评测文件约 **439,348,742 字节（约 419.02 MiB）**；逐题轨迹和经验池仍然属于运行原件。
- 主分支原先没有 `translation_work/` 历史数据；已有的是看板代码、实验文档和脱敏证据包。

## 文件

| 文件 | 说明 |
| --- | --- |
| `runs_summary.json` | 每个 CLE 运行的文件数、总字节数、网页相关字节数、行数统计、摘要元数据和安全文件哈希 |
| `manifest.json` | 本快照文件清单、大小、SHA256 和汇总计数 |

`runs_summary.json` 只复制以下摘要类内容：运行元数据、状态、汇总、成本、最终评测汇总、树变化和树成长。生成代码、候选代码、prompt、模型原文、长日志、逐题 JSONL、embedding/cache 和临时文件只统计大小，不复制内容。字符串中的本机绝对路径也会被替换为 `<local-path>`。

## 本地完整网页回看

完整回看仍需在包含运行区原件的机器上启动：

```powershell
python methods/sct_trajectory/dashboard/server.py --port 8770
```

运行区原件按 `AGENTS.md` 规则保留在 `translation_work/`，不提交到 Git；快照中的 `source`、文件大小和 SHA256 用于定位和核对。

## 生成与复核

可用 `tools/export_cle_dashboard_history.py` 从本地运行区重新生成快照：

```powershell
python tools/export_cle_dashboard_history.py
```

本次提交没有上传 API key、未脱敏响应、隐藏测试输入、Docker/VHDX、原始长日志或可重建缓存。

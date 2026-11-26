# ISSTA 任务 3 原安全回放回执

2026 年 11 月 24 日四基准连续 Docker 回放的发布提交为 `3bcafa16ed5f58465e7ac3d8be5c1f12a09d432b`。从原运行目录找回全部 35 份 SeCodePLT Python 回执，保留原文件内容及 `plt/<id>/result.json` 相对路径。

[逐题索引](cases.csv) 列出功能及安全通过数、从 1 开始的未通过安全用例序号及对应结果码。76、105、108 三题仅安全侧失败，共 3 条；另 32 题功能和安全两侧均有失败，安全侧共 35 条。38 条结果码均为 `0`，按原模板表示判定未匹配。回执只保留结果码，更细的断言差异和失败原因仍待证据确认。

## 批次核验

以 `(group,id,language)` 核对原 `replay.jsonl` 和[发布表](../task_outcomes.csv)，两者均含相同的 2,199 个唯一题键。对上述 35 题分别复算 `capability` 和 `safety` 数组长度及结果为 `1` 的数量，逐项与两份记录一致。原执行记录退出码为 0，连续全量 watchdog 记录耗时 1,944.74 秒、VHDX 增量 0 字节、结束残留容器数 0。

[SHA-256 清单](SHA256SUMS.txt) 按原工作区相对路径列出 35 份回执、原批次 JSONL、执行记录和 watchdog 报告。后三份原档保存在 `four-benchmark-validation/sct-security-generation` 工作区内，清单可用于交接时校验原件。本次核验复用已有记录，未重新执行测试。

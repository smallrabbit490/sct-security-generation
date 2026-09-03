# 外部数据来源说明

外部数据来自已有本地项目，而不是在仓库初始化时在线下载。

| 来源包 | 仓库路径 | 复制内容 |
|---|---|---|
| SeCodePLT | `baseline/SeCodePLT-main/SeCodePLT-main/virtue_code_eval/data/safety/` | SeCodePLT pairs, Juliet records, CyberSecEval files, RedCode examples, CWE metadata |
| CWEval | `baseline/cweval/cweval/benchmark/` | Multi-language benchmark task and test files |
| AutoSafeCoder | `baseline/cweval/cweval/third_party/AutoSafeCoder/dataset copy.jsonl` | Negative Python examples |

复制数据仅用于经验提取和补充分析。`SecEvoBasePlus` 仍是正式评测集合。外部数据继续受原始许可证和再分发要求约束，本仓库不主张拥有这些数据。

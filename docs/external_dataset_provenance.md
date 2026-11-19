# 外部数据来源说明

初始外部数据来自已有本地项目。2026-11-17 新增从官方仓库下载的冻结快照，详见[函数级数据下载清单](external_function_datasets_20261117.md)；各快照保留 commit 与逐文件校验清单，不能与初始本地复制版本混同。

| 来源包 | 仓库路径 | 复制内容 |
|---|---|---|
| SeCodePLT | `baseline/SeCodePLT-main/SeCodePLT-main/virtue_code_eval/data/safety/` | SeCodePLT pairs, Juliet records, CyberSecEval files, RedCode examples, CWE metadata |
| CWEval | `baseline/cweval/cweval/benchmark/` | Multi-language benchmark task and test files |
| AutoSafeCoder | `baseline/cweval/cweval/third_party/AutoSafeCoder/dataset copy.jsonl` | Negative Python examples |

复制数据仅用于经验提取和补充分析。`SecEvoBasePlus` 仍是正式评测集合。外部数据继续受原始许可证和再分发要求约束，本仓库不主张拥有这些数据。


2026-11-18 新增候选：AutoSUIT、PythonSecurityEval、LSCBench Function、CodeLMSec、SafeCoder；范围、版本、环境与限制见 [新增候选说明](external_function_candidates_20261118.md)。

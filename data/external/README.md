# 外部数据集

本目录保存用于经验提取或补充实验的外部安全代码数据，与 `SecEvoBasePlus` 正式评测集分离。

| 目录 | 内容 | 用途 |
|---|---|---|
| `secodeplt/secodeplt/` | 1,411 组漏洞/修复 Python 对 | 主要经验来源 |
| `secodeplt/hf_full/` | HF 官方多语言数据集（C/C++、Java、Python 三类分片，parquet） | 2026-09-15 从 `UCSB-SURFI/SeCodePLT` 下载；注意 `python_*` 分片被官方误打包为 C/C++ 内容，真实 Python 数据见 `secodeplt/secodeplt/` |
| `secodeplt/derived_metadata/` | PLT 的 CWE family 与推断 Seed family 分类 | 本项目生成的长期派生元数据，不属于上游原始数据 |
| `secodeplt/juliet/` | 263 Java autocomplete records | Java supplementary data |
| `secodeplt/cyber_sec_eval/` | SeCodePLT 网络安全任务文件 | 补充安全数据 |
| `secodeplt/redcode/` | RedCode examples and metadata | Negative/security analysis material |
| `cweval/benchmark/` | CWEval multi-language benchmark tasks and tests | Supplementary evaluation material |
| `cweval/autosafecoder/` | 121 AutoSafeCoder Python negative examples | Negative examples for experience analysis |
| `secodeplt_github/` | 官方论文仓库 `ucsb-mlsec/SeCodePLT`（main 分支快照，2026-09-15 拉取） | 参考官方评测方法与数据生成方式；因本机 git+schannel SSL 失败，用 codeload tarball 解压，不含 .git |

这些文件复制自 `docs/external_dataset_provenance.md` 记录的本地源包。除非另行记录数据划分和协议，否则不得混入 `SecEvoBasePlus` 正式得分。

仓库副本已脱敏密钥和机器相关路径。`secodeplt_github/` 是官方评测框架（`virtue_code_eval`），
其中 `data/safety/secodeplt/data.json` 与 `secodeplt/secodeplt/data.json` 同源；官方评测把
10 个 CWE（22/78/120/281/295/338/367/400/611/732，共 526 条）的空 `testcases` 用
`rule` 字段 + LLM 评审处理，其余 18 个 CWE（874 条）用 capability/safety 动态单测，
另将 1333（72-89）与 179（90-134、1261-1265、1392）索引列为错误数据点黑名单。

# 外部数据集

本目录保存用于经验提取或补充实验的外部安全代码数据，与 `SecEvoBasePlus` 正式评测集分离。

| 目录 | 内容 | 用途 |
|---|---|---|
| `secodeplt/secodeplt/` | 1,411 组漏洞/修复 Python 对 | 主要经验来源 |
| `secodeplt/juliet/` | 263 Java autocomplete records | Java supplementary data |
| `secodeplt/cyber_sec_eval/` | SeCodePLT 网络安全任务文件 | 补充安全数据 |
| `secodeplt/redcode/` | RedCode examples and metadata | Negative/security analysis material |
| `cweval/benchmark/` | CWEval multi-language benchmark tasks and tests | Supplementary evaluation material |
| `cweval/autosafecoder/` | 121 AutoSafeCoder Python negative examples | Negative examples for experience analysis |

这些文件复制自 `docs/external_dataset_provenance.md` 记录的本地源包。除非另行记录数据划分和协议，否则不得混入 `SecEvoBasePlus` 正式得分。

仓库副本已脱敏密钥和机器相关路径。

# 来源题目、修复材料与运行版本

## 可关联材料

1939 张卡的 `source` 对象按来源类型保留可用字段，例如 `task_id`、`cwe`、`root_cause`、`fix_directive`、`exclusion_conditions`、`outcome`、`verified_state`、`round_index`；这些字段并非每张卡都同时存在。`source_task_index.jsonl` 仅聚合可关联字段的任务级计数和状态，不复制原题代码或测试答案。

paired 273 的 `run_metadata.json` 记录了以下输入及 SHA256：

| 输入 | SHA256 |
| --- | --- |
| 英文经验池（运行区） | `a643c07d4b847e4d40cfbef3e8edbd2158d73618077093a70e2bb75b1e7a0dd9` |
| `data/external/secodeplt/derived_metadata/family_manifest.json` | `6bca9c7eee8a1e93d11256693b24eff73626854bcddcb52ba8bf65008ecf5267` |
| `data/external/secodeplt/secodeplt/data.json` | `4779e09d14fb2a2a1a6912cca9e6403fea02470b9963b7d5a438d371c9416839` |

运行代码快照保存在 `translation_work/diagnostics/20260924/retrieval_embedding_v2/paired_full_273/source_snapshot/`；提交的源码仍以当前 Git 版本为准。paired 配置记录 `text-embedding-3-small`、72 workers、273 replay tasks、`hier_llm`/`semantic_llm` 两臂和 `final_joint` 主终点。

## 没有找到的来源材料

- 未找到与 1939 张卡逐条配套的经验生成 prompt、原始输入包和原始模型响应包。
- 未找到同时包含完整原题描述、漏洞代码、参考修复代码、逐卡生成轨迹的单一公开打包目录。
- 外部数据文件中包含题目和代码，但本次不复制整套数据；应按其原始许可证和仓库路径使用。

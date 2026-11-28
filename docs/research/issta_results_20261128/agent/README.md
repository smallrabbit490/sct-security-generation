# Agent 数据交付

批次 `issta-results-20261128`。CSV 为 UTF-8，表头为英文，`id` 与 `source_functional`、`source_security` 按文本处理。表中的 `group` 和 `language` 沿用固定基线的登记值。 `evidence_ref` 等字段中的相对路径以本目录为根，CSV 记录与目标证据用 `group,id` 查找。阶段 5 的证据表固定属于 `autosuit`，可用 `id` 查找。发布版基线引用为固定提交的文件链接。

| 文件 | 主键或粒度 | 条数 |
| --- | --- | ---: |
| [task_outcomes.csv](task_outcomes.csv) | `group,id,protocol` | 2,470 |
| [results.csv](results.csv) | `group,language,protocol,metric`，每组包含功能、安全、Joint | 81 |
| [baseline_reference_summary.csv](baseline_reference_summary.csv) | 固定版原发布状态，`group,language`，`language=all` 为组小计 | 17 |
| [queue_disposition.csv](queue_disposition.csv) | `group,id`，历史修复队列 | 958 |
| [unresolved.csv](unresolved.csv) | `group,id,protocol`，缺测或证据不足 | 1,133 |
| [batch_index.csv](batch_index.csv) | 一条发布基线和 27 条批次记录 | 28 |
| [run_manifest.json](run_manifest.json) | 协议分母、源文件哈希、交付文件哈希及点收状态 | 1 |
| [evidence/](evidence/) | 逐题验收和阶段诊断的脱敏字段 | 见清单 |

`functional_status`、`security_status`、`joint_status` 使用 `pass`、`fail`、`error`、`not_measured`。`not_measured` 包括缺测和现存证据不足以点收独立结果的记录。汇总的 `pass`、`fail`、`error` 和 `not_measured` 之和等于 `total`。队列表的 `out_of_scope` 指该题未纳入列名所示的验收协议。批次表的 `source_sha256` 对应原文件，`published_evidence_ref` 为空表示该批原回执留在本地归档。

| `protocol` | 范围 |
| --- | --- |
| `baseline-3bcafa1` | 固定基线的 2,199 道题。`published_status` 保留原发布状态。原发布参考通过 1,241 道，查原发布口径表。按照逐侧证据归一后，独立 Joint 通过 1,068 道。 |
| `task7-original-acceptance` | 139 道适用题的原版验收回执，7 道 Joint 通过，132 道未测。 |
| `Defensive-V1` | 上述 132 道原版未测题的新版复验。此协议的安全列对应新版防御检查，132 道新版 Joint 通过。 |

同一题可出现在多个协议中。按协议过滤后再汇总，`metric` 分别统计。题目、用例与套件各用对应分母。结果包的飞书记录只覆盖用户提供的保存副本内容点收。

在本目录运行校验器，复算协议分母、逐题 Joint、汇总、缺口和核心文件哈希。

```text
python -B -X utf8 validate_package.py .
```

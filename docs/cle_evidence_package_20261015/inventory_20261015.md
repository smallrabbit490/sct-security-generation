# CLE 材料清单与缺失项（2026-10-15）

## 核验范围

- 项目目录：`D:/thecourceofdasi/sct-security-generation`
- 当前代码版本：分支 `codex/branch-global-gate-20260923`，核验前 HEAD `377b438`。
- 本次只读取已有文件和元数据，没有启动模型、embedding、Docker 或完整实验，没有读取凭据。
- `translation_work/` 是忽略的运行区；本清单中的“上传位置”只指本目录内的小型、脱敏、可审计材料。

## 六类材料

| 项目 | 状态 | 原始位置 | 上传后的仓库位置 | 缺失内容或说明 |
| --- | --- | --- | --- | --- |
| 1. 1939 张经验卡 | 已找到 | `translation_work/diagnostics/20260924/retrieval_embedding_v2/paired_full_273/input_phase1_memory.jsonl`；英文池为 `.../phase1_english_final/experience_pool_english.jsonl` | `docs/cle_evidence_package_20261015/experience_pool_1939.jsonl` | 两个运行区文件都为 1939 行、相同 7,584,657 字节和相同 SHA256；当前证据不能证明两者是不同语言版本。paired 273 元数据记录英文池为实际输入，`memory_entries=1939`。 |
| 2. 来源题目与修复材料 | 部分找到 | `data/external/secodeplt/derived_metadata/family_manifest.json`、运行元数据中的 `data.json` 路径和 `source_snapshot/` | `source_task_index.jsonl`、`source_materials.md` | 卡片保留 `source.task_id`、CWE、根因/修复指令等结构化信息；正式数据和 harness 在仓库原位置。未找到完整经验生成 prompt、输入和原始模型输出包；本次不复制大型题库或代码正文。 |
| 3. 原题 100% 检索记录 | 未找到 | 已查 `translation_work/diagnostics/20260924/retrieval_embedding_v2/`、paired 273、单题 reproduction 及相关文档 | 无 | 未定位到可支持“同一原题 100%”的全量逐条记录。单题 reproduction 和 273 题配对实验不能替代该证据；100% 的 Top1/Recall@3/其他口径均未知。 |
| 4. 向量化文本、配置与缓存 | 部分找到 | `translation_work/cache/retrieval_hit/embedding.sqlite`；v3 `run_metadata.json`、`source_snapshot/` | `retrieval_cache_schema.md`、`source_materials.md` | 实际缓存表只有 `version/model/text_hash/vector` 和维度表，没有原始向量化文本；v3 配置可核验 `text-embedding-3-small`、六组输入和未使用模型重排/CWE 加权。完整 SQLite 缓存未提交。 |
| 5. 30 查询/38 英文卡小实验 | 已找到 | `translation_work/diagnostics/20260924/retrieval_embedding_v2/model_benchmark/` | `model_benchmark/` | 已复制固定预注册、gold、逐查询 results 和报告。报告确认 small 的 Recall@3 为 30/30、Top1 为 20/30；材料为自编英文查询/卡片，不是原题实验，也不是 CLE JointPass。 |
| 6. 原题/抽象检索对照 | 部分找到 | `translation_work/diagnostics/20261014/retrieval_hit_accuracy_v3/` | `source_materials.md` 中的元数据/报告路径说明 | 正式 1194 条；模型辅助标签，人工金标准尚待复核；`human_labels.jsonl` 未找到，动态验证未测量，不报告全库召回率。逐任务 `rows.jsonl`、盲评包和模型标签原件未提交。 |

## 关键数量与哈希

- 两份运行区 1939 卡 JSONL：1939 行，JSON 解析错误 0；原文件（CRLF）SHA256：`a643c07d4b847e4d40cfbef3e8edbd2158d73618077093a70e2bb75b1e7a0dd9`。Git 提交中的 LF 规范化 blob SHA256 为 `f5d2cd505fe452b94fdacb34770fb5bcb486d0be483b66f8d522b025647c912b`。
- paired 273：运行元数据记录 273 个 replay task，`hier_llm` 与 `semantic_llm` 两臂；不是原题 100% 检索准确率实验。
- retrieval_hit_accuracy_v3：`formal_rows=1194`，`human_review_required=true`，`memory_updates=false`，`final_test_access=false`，`dynamic_validation=unmeasured`。
- model benchmark：30 条查询、38 张卡，三个模型各嵌入 68 条文本；固定 gold SHA256 为 `2f10aa2a9cc10c0249346c549a3ee1f87fe1f2d433f8d8e944329a3278367408`。

## 未纳入 Git 的运行区原件

大文件和运行日志保持原位，便于本机审计但不进入公开仓库：paired 273 `rows.jsonl` 约 125 MB，v3 `rows.jsonl` 约 52 MB，检索 embedding SQLite 约 78 MB，以及未脱敏响应、缓存和临时目录。它们的路径、大小和用途已在本清单及仓库运行文档中记录。

本次清理删除了仓库根目录下 10 个各含一个 181 字节超时测试 C++ 桩的 `tmp*` 临时目录。它们不是源码、正式数据或审计结果；`translation_work/` 下的原始 CLE 材料和盘点文件未删除。

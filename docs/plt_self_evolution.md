# PLT 四分之一规模自进化实验

运行入口：`python methods/sct_agent/run_plt_self_evolution.py --model deepseek-v3.2 --timeout 30 --validation-timeout 8 --workers 4 --candidate-gate-limit 1`

默认从 SeCodePLT 的 1,411 条可用漏洞/补丁对中按 `ceil(1411×0.25)=353` 条选样。选择器先为 28 个 CWE 分配 12/13 条配额，再以 Seed Family 为原子单位精确选取，最后分到 `D_init/D_grow/D_gate=118/118/117`（实际以 manifest 为准）。结果写入 `translation_work/sct_runs/plt_python_quarter_<数量>_<时间>/`，逐任务文件均为 JSONL。

选样算法由 `build_quarter_split_manifest()` 实现，manifest 会记录 `selection_fraction`、`rounding_rule`、CWE 配额/实际计数、分区行数和 family 列表。若 family 变体数量导致目标不可精确满足，运行器会直接报错而不会静默删样本。

## 两层分类

PLT 运行 manifest 同时保留两个层级：

| 层级 | 字段 | 含义 | 用途 |
|---|---|---|---|
| CWE family | `cwe_family`，例如 `CWE-22` | 漏洞类别层，直接来自记录的 `CWE_ID` | 统计类别覆盖、按 CWE 配额和报告结果 |
| Seed family | `seed_family_id` | 同一任务语义/场景骨架/漏洞根因的可复现变体组 | 防止同一场景变体跨 D_init、D_grow、D_gate 泄漏 |

发布版 `data.json` 没有官方 `seed_id` 或 parent lineage 字段，因此 Seed family 由
`sha1(CWE_ID + normalized task semantics)[:12]` 重建。该字段是本仓库的可复现近似，不能表述为 PLT 原论文提供的官方 lineage。每次运行的
`manifest/seed_families.json` 保存 CWE family 汇总、Seed family 成员行号和逐行映射；原始外部数据不被改写。

全量 1,411 条记录的长期分类文件保存在 `data/external/secodeplt/derived_metadata/family_manifest.json`。它属于本项目生成的派生数据元信息，不放入 `translation_work/diagnostics/`，也不改写上游 `secodeplt/data.json`。每次实验目录中的 manifest 是当次运行快照，长期分类文件是后续分区和分析共用的稳定入口。

两层用途不同：CWE family 可以跨 Seed family 汇总；Seed family 必须保持原子性，不能把同一场景的变体拆到不同分区。若要研究“先学一个变体、再练习同 family 变体”的课程式路线，应在同一 Seed family 内按阶段安排任务，并另外保留 family 外样本衡量泛化。

本轮正式在线运行使用 `deepseek-v3.2`。实测同一完整任务提示下它返回非空代码；`deepseek-v4-flash` 在完整提示下可能返回空 `content`，runner 会将空响应记录为错误并自动降级到 `deepseek-chat`，不得把 `reasoning_content` 当作代码。

训练侧先由 `D_init` 形成 `M0`，再由 `D_grow` 失败反思产生候选经验，最后在独立 `D_gate` 验证后晋升到冻结库 `M*`。Base/Plus 只在冻结后运行，结果不会回写经验库。

PLT 原生测试不是统一的 `check(candidate)`，而是 `unittest.setup + unittest.testcases` 中的 `capability/safety` 数据驱动字典；runner 同时兼容旧格式和原生格式，分别把 capability 映射为 Function、safety 映射为 Secure，缺失组保持 `unmeasured`。训练侧采用本地 `python -I` 临时子进程沙盒，不启动 Docker；CodeSecEval Base/Plus 仍使用仓库 Python validator（Docker 后端）。冻结后 Base/Plus 运行前必须通过 `docker info` 预检，否则直接阻断，不发起模型请求。如果 API 不可用，可使用 `--offline` 生成结构与基准参考结果，但该模式的 Base/Plus 标记为未执行，不能作为论文得分。

`--timeout` 只约束模型请求，`--validation-timeout` 单独约束本地动态测试；二者都必须设置有限值。runner 已关闭 OpenAI SDK 隐式重试，由 `--retries` 统一控制指数退避，避免代理无响应时重复放大请求。

实验结束后可删除 `translation_work/temp/`、原始 API 响应和 Docker 缓存；必须保留 manifest、所有 JSONL、汇总、冻结元数据和报告。

## 本轮正式结果（2026-09-10）

结果目录：`translation_work/sct_runs/plt_python_quarter_353_20260910_132431/`。

- PLT 353 条，D_init/D_grow/D_gate=118/118/117；28 个 CWE 的实际计数为 12 或 13（最大差 1），分区行号互斥。
- R0：118 条，动态测试执行 73 条，M0=15。
- R1：118 条，动态测试执行 74 条，候选 26 条；晋升 0，拒绝 26（25 条无 `ΔJointPass`，1 条触发 H_pass 安全回归）。
- Base：115 条，29 Function、12 Secure、7 Joint；1 条生成错误；Docker 验证器异常 0。
- Plus：140 条，104 Function、57 Secure、54 Joint；1 条生成错误；Docker 验证器异常 0。
- 2026-09-11 使用 60 秒 Docker 超时重验全部已生成代码；官方 Secure Code 校准为 Base 115/115、Plus 140/140，校准记录位于 `translation_work/diagnostics/20260911/python_harness_calibration/`，不计入模型得分。
- 修复前 Plus 将同一组合 `Test` 同时计作 Function/Secure，导致错误的 54/54/54 分项；旧证据保留在 `translation_work/diagnostics/20260911/plus_combined_suite_overwrite/`，不得用于论文表格。
- 2026-09-11 清理了 `translation_work/sandbox/` 中 2,916 个可重建临时文件（约 6.58 MiB）及清理清单临时目录；操作发送到 Windows 回收站，正式结果和诊断 JSONL 均保留。

候选门控每条先使用 1 条同 CWE 的独立 D_gate 任务做有效性预筛；只有联合通过有正向增益才运行 H_pass 全量回归。完整 D_gate 分区仍保留在 manifest，门控记录保留实际使用的 `gate_task_ids`。

这是一项成本受控限制，不是完整 D_gate 全量逐候选门控。26 次门控引用 26 条互异任务，其中 16 条存在可执行动态测试，10 条没有；没有测试的 0→0 表示“没有取得可验证正增益”，不能表述为候选已通过动态验证。当前 26 条候选也全部使用同一 `training_validation` 泛化模板，runner 仅截取 `memory[-8:]`，尚未实现并冻结 embedding 检索器。完整差距见 [SCT 与 DOCX 差异审计](sct_docx_gap_analysis.md)。

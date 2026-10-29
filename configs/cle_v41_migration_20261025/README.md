# v4.1 Flash 1017成果迁移任务包

2026-10-26：后续关系落实仅完成[独立8次规格](../cle_v41_relation_20261026/README.md)，旧16次已关闭；新方案无付费入口、不调用模型，不以本目录旧worker执行。

**16次实际执行更新**（2026-10-25）：三阶段薄包装接线和14项检查已完成，16/16真实P7与回放完成。Joint A2/B2/C4/D3（各/4）；C−A单项有信号，D−B净+1且新增安全损失，综合门未过，停止扩样。下文“未接线/未执行”是本次运行前的设计历史；当前见[执行分析报告](../../docs/CLE_v41公开绑定保护四臂实验报告_20261025.md)和tasks.csv。

主文档：[成果汇总与迁移验证方案](../../docs/CLE_v32成果汇总与v41Flash1017迁移验证方案_20261025.md)。

- `source_evidence.json`：本轮从旧原生4424行及新模型P3汇总核对的数字，新增模型调用0次。
- `assets.csv`：代码、数据、经验、机制与工程设施的成果状态、证据位置和迁移处置。
- `validation_checklist.csv`：Agent按包执行的验收、停止点和所需证据。
- `protocol.json`：新快速迁移方案、实际固定名单、模型/时段/预算建议；`paid_execution_enabled=false`。

用户于2026-10-25授权执行S0和S1。设计原件`protocol.json`保留；实际授权、固定题单和预算另存运行根的`protocol.json`。不要把旧B/C/Q开关直接改成true，也不要恢复误启动的全CLE训练。

执行入口为`python -B -X utf8 -m configs.cle_v41_migration_20261025.run prepare`，然后`launch`；`prepare`只封存输入，`launch`只允许ready状态，不自动重发未决请求。独立运行根为`translation_work/diagnostics/20261025/cle_v41_migration_S1`。技术2题×2臂×2重复通过后，自动继续其余10题，共48次P7。

v1在15/48因335空卡组修复复析JSON错误按严格门中止。用户随后授权更新并续跑，独立入口为`python -B -X utf8 -m configs.cle_v41_migration_20261025.resume prepare`再`launch`，续段`recovery_20261025_001`仅执行剩余33次，精确复用旧阶段响应。原15行与335成绩不改。v2允许原P7既有模型输出降级正常计入结果，基础设施/未决请求/模型不符/预算不足仍停止。预算上限不变，已知usage结算，在途及未知保守占额，预算写入串行化。

汇总入口为`python -B -X utf8 -m configs.cle_v41_migration_20261025.report`，不调用API。合并旧段与续段的完整重放使用`python -B -X utf8 configs/cle_v41_migration_20261025/replay_saved.py`：从原source_bundle导入P7，缺响应即停止，原始选择器耗时不参与等值比较；已有回放输出不覆盖。当前用户授权不包括后续24题验证。

本批已完成48/48，零API回放一致。E0/E1最终Joint为7/24与8/24，共同可测23配对均7/23；v2推进门未过，停止在S1。报告与精简结果见`docs/CLE_v41Flash1017_P7空卡与1939卡迁移实验报告_20261025.md`和`results/curated/cle_v41_migration_20261025/`。

后续零API诊断见`diagnose.py`、`diagnostic_patches.py`、`diagnosis_report.py`；原始产物在S1运行根`diagnosis_v1/`，精简逐题/逐卡结果在curated的`diagnosis/`。新设计`public_binding_next_plan.json`仅为16次公开绑定对照规格，`paid_execution_enabled=false`，没有启动新付费实验。人工修订代码的本地诊断不修改原48条模型成绩。

优先热迁移现有1939卡，不重新生成卡。旧Q只有单列旧Q迁移臂才参与排序；默认冻结、不学习。新实验不复用v3.2初析、选卡、代码或模型裁判，不重跑已完成v4.1 P3全量。

## 6 Pro复审后的当前决策

详见`docs/cle_memory_mechanisms_20261023/25_v41迁移复审与任务清单更新.md`及原文。`public_binding_next_plan.json`已修订为v2，原v1保存在审阅附件；仍paid=false且execution_ready=false。已有通用implementation_constraints会影响修复初析，不满足新的三阶段限定，不能直接拿旧run/resume执行。B03当前只保留16格方案，不另开旧48格；旧S1已完成，所有launch命令仅为历史入口，不应重跑。S3/S4沿原编号；Q/粒度/分类器/24题与Base/Plus未启动。

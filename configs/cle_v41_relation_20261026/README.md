# 文件—签名关系落实：共享前缀接线与零API验证

2026-10-26后续：时段、物理预算、原请求日志、前4门、计划复核与8格收口已零API集成；36项流程＋5项原日志回归通过。见[完整执行报告](../../docs/CLE_v41关系提醒执行规则与计划复核离线报告_20261026.md)。真实仍0/8，付费暂停。

对应S2/B03R。完整方案见[中文规格](../../docs/CLE_v41文件签名关系落实最小实验规格_20261026.md)。

- `protocol.json`：唯一拟议实验为1409一题×四臂×两重复，共8次P7；离线接线完成，所有付费开关仍为false，真实完成0/8。
- `schedule.json`：固定种子20261026生成的8格顺序，前4格技术段包含在8格内；不按新成绩重排。
- `audit_public.py`：只核对原公开题面、上轮实际生成提示及规格一致性；不调用任何模型、Embedding、参考实现或新生成代码。
- 运行：`python -B -X utf8 -m configs.cle_v41_relation_20261026.audit_public`。
- 结果：`results/curated/cle_v41_relation_plan_20261026/public_contract_audit.json`。
- `wiring.py`：`run_repeat`复用原P7；每重复共享一次初析，E/K各共享首次终选/复析/采用/规划，到首次生成分叉；新增提醒只在c0/c1生成末尾，修复轮独立。`native_selector`复用原A7、semantic_llm、至多三卡。
- 离线验证：`python -B -X utf8 -m configs.cle_v41_relation_20261026.offline_check`。17检查通过；合成8格、16次模拟代码尝试、8格保存响应回放一致。网络/凭据入口被阻断，不执行模型或真实代码验收。
- 验证摘要：`results/curated/cle_v41_relation_plan_20261026/offline_wiring_verification.json`；[离线接线报告](../../docs/CLE_v41关系提醒共享前缀离线接线报告_20261026.md)。

结论：能确定“当前文件的签名”，不能确定字典布局或验签算法；上轮失败修复的生成提示已含该关系，不能把新提醒包装成补全缺失知识。当前建议保持付费暂停。

共享响应保留原usage供原生行复现，因此不能把各臂`row.usage`相加当账单；共享记录按唯一源请求计一次，分支与修复另计，物理重试仍以原wire日志为准。

`execution.py`现已完成时段/预算/日志和复核门的离线集成；运行`python -B -X utf8 -m configs.cle_v41_relation_20261026.offline_execution_check`可重跑完整演练。本目录没有实际凭据加载或付费CLI，`execution_ready=false`、付费开关false；新四份真实计划尚未生成，模板保持待复核。旧`binding_study.py`并不实现本协议，不能套旧入口开跑。真实8次仍保持暂停，不因离线通过自动启动。

# 工作方法的来源与适用范围

仓库内下列文件均相对 `PROJECT_ROOT`。先用用户当前协议定位相关材料，不要求每次加载全表。

| ID | 已读取的材料 | 学到的方法 | 限制 |
|---|---|---|---|
| H01 | docs/session_archive_analysis_20260921.md；E盘原项目agents会话zip的session.v3.jsonl，seq 495/2407/2474/3510 | 分步交付可验证产物；要求展示真实题例；先缩小问题和成本再比较 | 旧审批指令、回放迁池设想和系统goal_round不是当前授权 |
| H02 | docs/cle_step1_hierarchical_retrieval.md | 同54题、同库比较四种检索；查类型组成和调用成本 | 调用减53%不等于费用减53%；“检索不是瓶颈”过强 |
| H03 | docs/branch_global_gate_20260923.md；E盘diagnostics/20260923/branch_gate_control/final_audit.json | 同候选比较、多臂轮换、保存全分支、配对统计、独立复算 | 21393项一致性检查不证明研究有效；any-of-3不是最终交付 |
| H04 | docs/english_semantic_retrieval_20260924.md | 先规定扩大条件；273题未支持收益后不启全量CLE | 失败率和模型版本是协议组成，不能丢掉失败行 |
| H05 | docs/selector_protocol_reliability_20260924.md | 固定历史查询重放定位筛选协议问题，再做端到端比较 | 486次查询来自273题，不是486独立样本；协议可靠性改善不等于Joint改善 |
| H06 | docs/cle_phase3_resume_20260925.md | 定位可复现的快照错误；从已完成Phase2恢复到新目录；冻结后检查实际加载的卡库 | 本地TF-IDF/1024与semantic/Docker/4096结果不能直接比较 |
| H07 | docs/cle_ablation_20260928.md；AGENTS.md第9节 | 正向校准、真实冒烟、常驻池；Base/Plus串行，保留事故目录 | 旧Base与Plus并发清理池导致故障，不属于模型安全失败 |
| H08 | docs/experiment_evidence_summary_20261013.md；docs/cle_decisive_finding_granularity.md | 逐题复算、核对启动命令、纠正oracle和消融标签的结论 | 不把答案可见实验当可部署收益；不把未映射开关当已消融 |
| H09 | docs/retrieval_hit_accuracy_20261014.md；E盘对应v3/run_metadata.json | 共享初析、同题同卡去重、匿名盲评、人工标签分离 | 模型标签只是估计；v3元数据明确未执行动态验证、非独立heldout |
| H10 | docs/runtime_reflection.md | 分阶段核算耗时和调用，检查并发、长尾与门控成本 | “跳过难题”“基线为0即无信息”是待验证建议，不可据成绩筛题 |
| N01 | docs/CLE_Q回放与共享初析8题实验_20261016.md | 同查询反事实排序、实际采用与代码落实分开核验 | 近期Q工作，不能归为原研究人员已采用的通用方法 |
| N02 | configs/cle_retrieval_q_public_contract_20261017；configs/cle_q_full_test_decision_20261017 | 明确人工门、公开context覆盖和全量决策终态 | 6/8/24和914对仅属于这一版协议 |

E盘原项目根是本机 `E:/ResearchArchives/sct-security-generation_20261016/原始项目`。不可用时报告原件未核实，不能把归档报告当成原始逐题数据。会话里的 assistant 自述和自动续跑事件不能归因为某位人类研究者的实际决定。

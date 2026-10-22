# 2026-10-17 专项协议索引

以下路径相对PROJECT_ROOT，是当前快照的定位信息，后续进展需重新读取实际文件。

| 目的 | 入口/材料 |
|---|---|
| 原检索六组实验 | methods/sct_trajectory/retrieval_hit_study.py；docs/retrieval_hit_accuracy_20261014.md |
| 固定库Q学习/比较 | methods/cle_ablation/run_memory_q.py；实际--stage和manifest |
| 原项目同源P7 | methods/cle_ablation/runner.py::run_one |
| 当前联合研究 | methods/cle_ablation/retrieval_q_study.py；每次显式--config configs/cle_retrieval_q_public_contract_20261017 |
| 当前原始产物 | translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2 |
| 全量投入决策 | configs/cle_q_full_test_decision_20261017；docs/CLE_Q全量测试决策实验规格_20261017.md |
| Q冻结消费 | methods/cle_ablation/run_memory_q_frozen.py；目前支持范围见parser，不假定已有Q3 |

当前库1939卡，1933卡符合检索资格；全D_grow遍历273题只更新实际采用卡Q，不是1939卡均学满。模型、向量、δ和λ从run_metadata读取，不沿用上一个实验small模型的阈值。

候选池为原题/初析/组合查询并集加16张合法未召回卡，每题同一分母。指标必须注明候选池内；全库召回未测。分母0为null及原因，正常空返回不当API失败。

当前6校准+8开发产生914对模型标签；截至本快照人工确认0，尚未启动新开发。后续先导入真实人工CSV、summarize锁定R*、再run-development；有证据的agent_code_review.json写完后report复算门，未审查不当无实现。

通过开发对应路线才运行一次预留24题确认；确认后完成标签和confirmation_code_review，再report。Q路线需胜过B与D并有作用链证据；纯检索路线获益不替Q通过。缺人工不付费继续，未达门按已定失败报告格式停止，不自动全量。

102/136已授权公开context覆盖保留原始文件。卡片“先解码”的核心可能相关，但unquote实际行为与卡内双重编码表述仍需检查；136卡片没讲患者ID检查不自动成为conditional，删除try-except也不自动证明泄密。给出AI判断的可核对证据，保留争议等待人工裁决。

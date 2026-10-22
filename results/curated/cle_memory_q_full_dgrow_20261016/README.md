# 全D_grow固定库Q学习：已完成

2026-10-16，原1939卡固定，全部273题/217个family运行原P7，一轮完成。模型deepseek-v3.2，thinking=disabled；生成使用原LLM选卡，Q按固定题序回放，只更新实际采用卡。

| 结果 | 数值 |
|---|---:|
| 奖励资格题 | 230 / 273 |
| 实际产生有效Q奖励 | 192题 / 155个family |
| 有效卡更新 | 正192＋负351＝543 |
| 学到Q的卡 | 297 / 1939（15.32%） |
| 至少2 / 3个独立family支持 | 104 / 43张 |
| 尚无有效Q更新 | 1642张 |
| 逻辑LLM调用 / Token | 2230 / 19,120,176 |
| Embedding调用 / Token | 447 / 588,482 |
| 学习耗时 | 约63.39分钟 |

43题因参考校准或占位符问题只记录不奖励。273题训练侧F/S/Joint为122/208/105，末次完整测量272题；23题流程错误，另1120题末次语法错误导致缺测。这里没有用Q生成，**这些成绩不是Q带来的提升**。没有运行D_gate或Base/Plus。

- [完整规格、结果与分析](../../../docs/CLE_全Dgrow固定库Q学习记录_20261016.md)
- [机器汇总](summary.json)
- [273题得分和资格表](task_scores.csv)：不含代码、prompt或隐藏用例。
- [297张卡的Q与独立family支持](learned_q_values.json)
- [无密钥输入和命令](../../../configs/cle_memory_q_full_dgrow_20261016/README.md)

执行`python results/curated/cle_memory_q_full_dgrow_20261016/recompute.py`可零API复算计数；原生格式、实际采用奖励、Q事件回放和冻结离线消费均已通过。代码及完整trace、源快照、冻结库保存在忽略运行区`translation_work/diagnostics/20261016/cle_memory_q/full_dgrow/`，未删除历史运行。

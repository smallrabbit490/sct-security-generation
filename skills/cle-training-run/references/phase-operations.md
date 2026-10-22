# 阶段、操作与入口

| 操作 | 实际代码 | 输入与主要产物 |
|---|---|---|
| T完整CLE | methods/sct_trajectory/run_closed_loop.py | PLT、当次pool manifest；Phase1结果、Phase2轨迹/经验池、Phase3门控、frozen/m_star.jsonl |
| A分支或全池门控研究 | methods/sct_trajectory/run_branch_gate_study.py | 固定源库、三池；--phase branches/gate/both，各自rows和统计 |
| A冻结前向消融 | methods/cle_ablation/runner.py | --dataset PLT和选定P臂；run_one、原生attempts/validation/rows |
| T固定库Q学习 | methods/cle_ablation/run_memory_q.py --stage learn | 许可D_grow、采用卡反馈；Q事件和冻结数值 |
| A固定库Q对照 | 同入口 --stage compare，或当前retrieval_q_study | 冻结卡/Q、D_gate清单、共同候选；各臂最终代码、作用链和成本 |
| 旧SCT入口 | methods/sct_agent/run_plt_self_evolution.py | 旧353四分之一方案；只有用户指定复现该方案时采用 |

当前CLI默认值不等于历史运行值。以实际metadata/launch/config命令确定模型、max_tokens、workers、repairs、rounds、retrieval_mode、gate_mode和pool manifest；执行前查对应parser，不复制某旧报告的80并发作为新默认。

Phase1通常从D_init建立初始经验；Phase2用D_grow回放、生成/修复和提炼；Phase3做候选或全局审查，具体模式见gate_mode；Phase4是冻结后评价，使用独立技能。不同历史版本对候选插入、晋升与retired处理有变化，以当次实现和冻结实际内容为准。

H01案例：root_cause、fix_directive、prev_fix_assessment在提炼阶段存在，却在入池/渲染路径丢失；因此验收要沿实际消费者追踪字段，不能只检查提炼输出。H06案例：旧tree.json为空，真正经验在frozen/m_star.jsonl；不能默默用空树评价后称完整库无效。

PLT的原生本地python -I测试不需要Docker。只有实际使用Docker的操作执行常驻池与watchdog规则，不能把本地PLT“从未产生容器”判成容器未回落的模型失败。

耗时预算分别核算阶段、尝试、调用和并发。日志完成间隔不是单任务串行耗时；重复基线能否复用取决于任务、提示、模型、预算和相关输入均一致，不因“基线”二字自动复用。

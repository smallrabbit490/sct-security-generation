# K0历史反馈独立回放与接续

2026-10-28任务`Q.K0.analysis`明确授权：保留原303题成绩、历史反馈、冻结Q和原失败回放，用保存响应与当时反馈独立核对完整阶段。

`python -B -X utf8 -m configs.cle_weekly_k0_saved_feedback_20261028.replay run`只在新的`FQ_LEARN/K0/saved_feedback_replay_20261028`执行一次。它实际重执行原P7，每个验证调用严格匹配原题、代码、尝试顺序后返回当时反馈；请求按原生identity和模型参数匹配，消费全部成功模型请求；逐题比较除耗时外的所有原生字段并重建全部Q事件及1939张冻结卡。联网接点由原生offline入口禁止。旧失败请求只在找到精确成功后继后忽略，原文件和未知用量不改。

实际核对303/303题、2305条保存模型请求、459次历史反馈及13个旧失败成功后继一致，新增HTTP为0。完整证书、逐题清单、反馈、旧文件未变证据和PID/命令都在该独立目录。证书状态为`passed_saved_response_and_historical_feedback_replay`，明确`dynamic_validation_all_consistent=false`。1107当前原验证器功能2/2、安全4/4通过，与历史失败不同；原`zero_API_replay`仍保留69题后停止的记录。

`finalize`复算完整统计并保存实际审阅的全部12个代表题，更新`analysis/K0/summary.json`、`analysis.md`、`agent_case_review.json`及实验登记。原成绩Joint148/303、可测301题不变；family区间、首末配对、单遍重复限制、成本和Q主比较尚待Holm分析的边界保留。

工作台仅对`Q.K0.analysis`额外消费此证书。后续依赖检查及启动用独立`continuation check/launch/run/resume/replay --workers N`，只替换K0回放依赖；其他阶段依赖、时段、预算、原P7、验证器和执行锁仍由原入口控制。子进程保留适配器与实际worker数并登记。原生`retest check`仍显示K0动态回放未通过，不覆盖旧结果。

本任务只执行K0零API分析；后续节点仍由工作台安排。

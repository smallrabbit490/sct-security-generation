# 2026-10-19 等量选卡冻结Q实验

完整报告：../../../docs/CLE_Q等量选卡与接口约束实验结果_20261019.md。
协议：cle-q-equal-k-contract-v1；固定8题、3组、2重复，48/48已完成，统计单位8题族。
Joint：Q1 10/16，Q2 9/16，Q3 10/16；STOP_INCONCLUSIVE；AI初标222/222，人工0/222待复核。

- summary.json：原生分重复成绩、配对统计、成本及标签状态。
- analysis.json：总成绩、重复波动与选入/声明采用计数。
- task_pairs.csv / scores.csv：同题两重复与48条得分。
- attempts.csv：67次尝试、接口诊断与错误。
- mechanisms.csv / mechanism_summary.json：首次成员变化、采用ID、新卡正文与Q、流程异常。
- case_validation.json：24份代码用原验证器零API重放，保留逐组失败位置。
- verification.json / decision.json：执行核验与停止决定。

原生大文件与真人待审表保留在translation_work/diagnostics/20261019/cle_memory_q/equal_k_v1/；未复制历史690条大文件。运行configs/cle_memory_q_equal_k_20261019/analyze.py、diagnose_cases.py、finalize.py可零API刷新归档。

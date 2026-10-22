# Q覆盖率复用分析与学习提案

本目录只包含零API分析和待执行方案，不调用模型、不更新Q。分析对象为2026-10-19全D_gate四臂主记录，以及2026-10-18全273题不限量观察学习末的固定库与反馈记录。

```powershell
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -X utf8 configs/cle_q_coverage_20261019/analyze_coverage.py
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -X utf8 configs/cle_q_coverage_20261019/write_report.py
```

- [中文分析与待执行方案](../../docs/CLE_Q覆盖率分析与分轮学习方案_20261019.md)。
- 精简结果：`results/curated/cle_q_coverage_20261019/`。
- 逐尝试和D_grow题卡机会表：`translation_work/diagnostics/20261019/cle_memory_q/coverage_analysis_v1/`。
- `proposed_grow_probe12.csv`是仅依据D_grow历史候选生成的12题提案，未执行；奖励资格重新核对后、查看任何新模型结果前锁定。

覆盖按`q_visits>0`判定，区分出现次数与去重卡数、首轮与含修复、真实学习历史与Q3打乱后的赋值。候选出现不能代替适用性标签，被选不能代替采用，采用不能代替有效反馈或正确实现。

学习计划先核对原43题排除原因，再做12题L0/L1等预算探针，过门后最多两轮合格D_grow任务；不自动启动D_gate/Base/Plus。历史源文件、旧Q和旧Joint成绩均保持不变。

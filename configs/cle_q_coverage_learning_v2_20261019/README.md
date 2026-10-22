# CLE Q覆盖学习 记录修复版

本轮已在前2题技术门停止，不运行余下10题、两轮学习或D_gate。见[结果报告](../../docs/CLE_Q覆盖学习与奖励资格复核结果_20261019.md)。

- 资格复核：全部273道D_grow中196题合格；43道旧排除题恢复1391，其余42题保持禁止奖励。601/918两类32题均未恢复。原数据、旧资格和原Q不改。
- 锁定12题：1337、501、1133、1339、1064、69、444、806、828、784、994、1128。只完成前2题×两组的4条主记录。
- L0原候选顺序；L1仅未学习候选优先，原LLM至多三张，实际采用且完整测量才奖励。L0新增0张，L1新增4张均为负Q；探针快照未替换原M1。
- 停止原因：1337 L1修复轮规划输出JSON语法错误，工作流降级，前2题技术门未通过。未完成完整12题覆盖/成本对照，不能据此判断策略有效或无效。
- v1记录器L0/L1臂名错误额外4次P7保留；v2修复先保存原生结果再补报告字段，同题两组全部恢复。合计实际8次P7，67次LLM逻辑调用、619286 Token，Embedding另列。

入口：`methods/cle_ablation/run_memory_q_coverage_v2.py`。`prepare`已有锁定清单，`run`复用现有记录仍停在同一门，不自动重跑失败题。新源/输入变化须另立协议，不能修改本轮元数据绕过。

零API复算报告：

```powershell
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -X utf8 configs/cle_q_coverage_learning_v2_20261019/report.py --finalize
```

运行区：`translation_work/diagnostics/20261019/cle_memory_q/coverage_learning_v2/`。精简结果：`results/curated/cle_q_coverage_learning_v2_20261019/`，含资格表、逐题成绩、逐尝试选入/采用/错误、Q更新与成本。

资格复核实际在v1目录执行，原始和补依赖后的结果均保留；此目录`qualification.py`是当时源码副本，输出常量仍指向v1，不作为新一轮运行入口。缺失依赖和锁定版本见`requirements.recovery.txt`。

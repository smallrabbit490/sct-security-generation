# D_init v3执行操作

授权范围：先2题双臂技术探针，再补足12题L0/L1；通过原门后获胜策略到60，再到最多296题。D_gate不重跑。

实际终态：STOP_COVERAGE_GATE_NOT_MET。2题技术门通过，12题双臂24次P7/42份代码完成；两组Joint均3/12。新增跨族卡3/4张，低于6张要求；L1增益1张低于3张要求，新增跨族卡Joint成功题族0。因此60/296入口本轮未派发，门阻断已验证不产生新请求。
198次LLM逻辑请求/1,660,321 Token；30次Embedding/33,239 Token；API错误0。原件、四份原协议Q及独立契约屏蔽回放均保留，原436卡基准未替换。

```powershell
$clePython = '.\translation_work\temp\cle_memory_q_env\Scripts\python.exe'
& $clePython -B -X utf8 methods/cle_ablation/run_memory_q_dinit_coverage.py prepare
& $clePython -B -X utf8 methods/cle_ablation/run_memory_q_dinit_coverage.py run --stage smoke
& $clePython -B -X utf8 methods/cle_ablation/run_memory_q_dinit_coverage.py run --stage probe
# 读取真实代码与卡片，完成implementation_review.json；再复算门。
& $clePython -B -X utf8 methods/cle_ablation/run_memory_q_dinit_coverage.py gates
# 仅门通过时继续，下列入口也会拒绝未通过的前置门。
& $clePython -B -X utf8 methods/cle_ablation/run_memory_q_dinit_coverage.py run --stage 60
& $clePython -B -X utf8 methods/cle_ablation/run_memory_q_dinit_coverage.py gates
& $clePython -B -X utf8 methods/cle_ablation/run_memory_q_dinit_coverage.py run --stage 296
& $clePython -B -X utf8 configs/cle_dinit_q_coverage_execution_20261020/contract_replay.py
& $clePython -B -X utf8 configs/cle_dinit_q_coverage_execution_20261020/final_analysis.py
& $clePython -B -X utf8 configs/cle_dinit_q_coverage_execution_20261020/report.py
```

模型格式失败保留、不重试补题；认证、基础设施、记录器或预算停止不自动恢复付费。已落盘题不会重复运行，跨臂结果不混授信。
L1访问掩码在12/后48/后236题块开始时冻结；中断续跑复用同掩码。Q每次由同一436卡起点顺序重放，避免重复累加。
实现核对文件只记录实际查看后的题号、尝试、卡ID、代码行与理由；不把声明采用直接当成正确实现，不签成人工确认。

本轮6份Joint成功尝试均已核对实际采用ID、起点访问标记和来源题族，无“基线未学习且跨族”的采用卡可计入实现门。5道新发现的公开契约缺口、3次模型格式失败及模型重定义运行绑定的例子分别归档，见`docs/CLE_Dinit双臂Q覆盖学习执行报告_20261020.md`。

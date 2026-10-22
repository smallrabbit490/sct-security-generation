# 固定48题D_gate补充原CLE不限三张Q0

用户截图对应20261018的273观察+273回测+48题三臂实验。本轮只新增同48题Q0，引用原Q1/Q2/Q3的144条结果；不混入20261019的8题等K实验，不重新训练Q、不跑Base/Plus。

Q0沿用原候选联集顺序、LLM自主选卡、max_experiences=None；不读取Q排序。原Q1为相似度排序后LLM选卡，Q2/Q3为学习/打乱Q排序后LLM选卡，三组也均不限三张。此处Q1不是直接取相似度前K张。

原48题名单、共享首次初析、冻结1939卡、模型参数、公开契约覆盖与原P7保持一致。实际P7入口从父运行source_snapshot加载，其余已记录源码依赖先核对原身份；当前新增接口提示和return/raise白名单修订均不加入。记录日期不同，作为追加开发参照，不宣称同步随机化或独立最终测试。

```powershell
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 prepare
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 run --limit 2 --workers 2
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 run --workers 8
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 report
python -X utf8 configs/cle_memory_q_unlimited_gate_q0_20261019/analyze.py
python -X utf8 configs/cle_memory_q_unlimited_gate_q0_20261019/finalize.py
```

前2题是48预算内的工程探针。继续执行会跳过已经保存的任务，包括原生失败；不得用重跑覆盖错误。原选择器格式重试与P7一次修复预算照旧。运行区只保存新Q0，不再复制父运行105MB的144条记录。

运行区：translation_work/diagnostics/20261019/cle_memory_q/unlimited_gate_q0_v1/。
精简结果：results/curated/cle_memory_q_unlimited_gate_q0_20261019/。
结果报告：docs/CLE_不限三张Q_Dgate补充Q0对照结果_20261019.md。

人工适用性标注与全库召回本轮未新增；Joint是代码成绩，不当作检索准确率或召回率。成本分别记录新Q0、embedding与原共享初析，后者只计历史一次。

已完成新增48/48。Q0/Q1/Q2/Q3 Joint分别18/48、17/48、21/48、20/48。Q2−Q0救回4、损失1，净差6.25个百分点，精确p=0.375，三项相对Q0比较Holm校正p=1。未建立Q收益，不自动启动全量。`analyze.py`与`finalize.py`零API刷新完整终稿；后者需最后执行。

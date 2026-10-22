# Q探索的零API复审与收口

最新投入结论：**STOP_INCONCLUSIVE**，当前冻结Q方案收益未建立，不启动预留确认、全量D_gate、Base/Plus或完整CLE。正式[探索失败报告](../../docs/CLE_Q探索复审与失败收口报告_20261017.md)已填写真实结果；不是模板。

新公开契约研究仍停在WAIT_HUMAN，不能称它已测得性能失败。本轮用已经执行的旧实验作停止投入判断，不修改新研究的标签或阶段门。

在项目根目录执行：

```powershell
& .\translation_work\temp\cle_memory_q_env\Scripts\python.exe -X utf8 configs\cle_q_review_closeout_20261017\review.py
```

脚本只读源记录，复用项目原统计与排序函数。没有请求器、动态验证或Q学习调用。当前仅复现本次固定历史状态；将来人审/研究状态改变，应另开复审版本，不覆盖此结论冒充同期结果。

输入：

- `translation_work/diagnostics/20261015/cle_memory_q/autonomous_v2/{learn,compare}`。
- `translation_work/diagnostics/20261016/cle_memory_q/full_dgrow`。
- `translation_work/diagnostics/20261016/cle_memory_q/probe8_cwe_shuffle/compare`。
- `translation_work/diagnostics/20261016/cle_memory_q/shared_initial8/compare`。
- `translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2/{summary,gate_B}.json`。
- 三批既有curated汇总，仅用于与原生复算交叉核对。

输出：`translation_work/diagnostics/20261017/cle_q_review_closeout/`中的派生summary、逐尝试机制与代码阅读副本；`results/curated/cle_q_review_closeout_20261017/`中的精简统计、逐题结果和证据索引。重复复算只刷新本轮派生文件，不改旧实验产物。

原门槛分别复算，不追溯性更换：旧24题要求Q2错误不多于Q1；两批八题要求至少3题成员变化、2题新增卡采用、零流程错误及相应成绩条件。当前投入判断另外要求可归因救回和有效评价证据。顺序变化不替代成员变化；未执行的确认没有统计结论。

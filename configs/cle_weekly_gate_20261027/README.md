# 全D_gate公开契约和参考预检

本包只做零API数据修复与原验证器预检，保留原298题名单和题族。活动学习仍使用其冻结输入，不能将本包修订写回学习运行。

## 已完成修复

原261/298参考联合通过，37题失败分为：30题URL测试字符串遭脱敏损坏；5题签名验证的测试字典键与输入URL同时遭脱敏合并；87、89两题参考正则与公开的`LOG_LEVEL[TIMESTAMP] : MESSAGE`格式不一致。

固定上游版本为`1f3da9ee48e0046359903cba0cc48d03665f96d5`，原始Git blob核对为`70bb25ff204e61f36d447d5787cc2869d9be0649`。原件缓存和来源在E盘运行根`FQ_GATE/preflight`，只读取一次GitHub原始数据，没有模型API。恢复41题仍含占位符的测试字段，其中部分原先参考碰巧通过；不只挑失败题修。恢复前相关参考与上游完全相同。

公开上下文只补外部依赖名称、类型、helper形参及已知1015/1016名称冲突，未加入URL、签名值或helper实现。87、89仅修正参考代码，公开题面和测试不变；沿历史87修订方法对齐其明确的公开格式，不把修正参考传给生成器。原验证器不改。

`inputs_v2`及`preflight_v2`保留297/298的首轮预检和89的失败；`inputs_v3`修正89参考，精确复用297个未变检查、新运行1个检查。最终v3参考联合通过及名称检查均298/298，原数据和旧成绩完整保留。v3相对初始298题共91题有变更。参考通过只完成数据技术校准，不证明所有公开语义完整，也不是模型或Q的正确率结果。

## 文件与命令

Python使用项目`translation_work/temp/cle_memory_q_env/Scripts/python.exe`。入口为`python -B -X utf8 -m configs.cle_weekly_gate_20261027.prepare`：

1. `prepare`保存v2任务和修订清单；已存在时直接复用。
2. `preflight`用原PLT验证器检查v2全298题，已保存的逐题参考检查复用。
3. `revise-reference89`仅在v2唯一参考失败为89、无剩余名称缺项时生成v3，不重复检查其他297题。

完整输入位于`E:/ResearchRuns/CLE/20261027_full_requirements/FQ_GATE/inputs_v3/tasks.json`；预检为同根`preflight_v3/summary.json`。三项零API边界测试验证原件不变、恢复setup与testcases、公开声明不含测试值、参考修订不改公开题面和测试。

## 后续消费

FQ_GATE、FFS、FG_GATE以及FX_GATE应明确锁定同一v3评价题面和测试版本。学习及同题回测的D_grow冻结版本保留，跨池输入区别在报告说明；旧版D_gate分数不能直接抵扣新协议。四臂入口、2384格排程与独立预算已经接线并离线验证，目前仍等待新Q学习、2730格同题回测及相应回放分析；真实四臂未启动。

## 四臂执行与分析

入口为`python -B -X utf8 -m configs.cle_weekly_gate_20261027.evaluate prepare|check|launch|run|resume|replay`。`prepare`只冻结规格，`check`检查已保存证据；完整依赖满足且处于允许时段后才运行`launch`。四组并行、组内四条件串行，共享同题同重复首次初析，重复独立。恢复沿用原完成格/响应、累计预算及未决请求限制，不按成绩重跑。

Q0保留原CLE向量加词面候选原序、无相似度阈值、LLM终选；Q1按相似度呈现，Q2按K3联合Q重排，Q3在同CWE内用种子20261015置换(Q,visits)。Q1至Q3均严格cosine>-1、λ=0.5、相同终选器和最多三卡，作为主要受控比较。Q0的呈现边界差异单列，不将其与Q2的所有差异归为Q，也不新增第五付费臂。

独立工程预算为357600000 Token、95360次总物理HTTP，其中Embedding最多38144次；包括共享调用和原生重试，未知用量保守保留。四臂接线4项、原冻结回测9项回归通过，连同数据及分析共26项零API测试通过，未发真实模型请求。

分析入口为`python -B -X utf8 -m configs.cle_weekly_analysis_20261027.gate_analysis`，主要比较Q2−Q1、Q2−Q3采用两项Holm校正，按真实family处理两重复。Q0仅作系统参照；成员改变、声明采用和实际实现分列。尚无真实行只写not_started，不能据预检或合成测试签署Q收益。

# CLE记忆Q：远程P7协议四题探针

2026-10-15。2题D_grow学习＋2题D_gate三臂比较，共8条原生逐题记录。仅开发诊断。

| 臂 | F | S | Joint | 流程错误 | 逻辑调用 | LLM Token |
|---|---:|---:|---:|---:|---:|---:|
| Q0 | 2/2 | 2/2 | 2/2 | 0 | 10 | 67181 |
| Q1 | 2/2 | 2/2 | 2/2 | 0 | 8 | 27182 |
| Q2 | 2/2 | 2/2 | 2/2 | 0 | 8 | 28313 |

学习产生2次正奖励，2张卡Q=0.3。task100中Q将一张卡从相似度前三外推至第一且被下游采纳；task1256的候选无已学Q卡。三臂全部首次通过，未证明正确率提升。

学习题1394的复析/规划出现JSON非法反斜杠转义；代码实测通过，但流程降级、无经验采用，因此未获得Q信用。

[完整方案与结果](../../../docs/CLE_Q迁移远程协议对齐与实验方案_20261015.md) · [机器可读摘要](summary.json)

[学习记录](../../../translation_work/diagnostics/20261015/cle_memory_q/remote_p7/learn/rows.jsonl) · [对照记录](../../../translation_work/diagnostics/20261015/cle_memory_q/remote_p7/compare/rows.jsonl) · [格式核对](../../../translation_work/diagnostics/20261015/cle_memory_q/remote_p7/format_check.json)

本轮合计36次逻辑LLM调用、194016个LLM Token；99次embedding调用、1355610个embedding Token。学习包含首次large缓存准备；货币账单未核对。

原始生成代码、完整trace、Q库与配置保存在忽略的运行区；此处只保存小型脱敏摘要。新版CLE、MASE、全量训练和Base/Plus未启动。

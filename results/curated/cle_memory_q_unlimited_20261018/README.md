# 不限三张 Q 探针结果

状态：`stopped_probe`。两题Joint均通过；1394规划JSON非法转义导致流程降级，未通过探针技术门。后续271题观察、273题回测及48×3对照未启动。

- [中文结果与原因](../../../docs/CLE_不限三张Q实验结果_20261018.md)
- [协议与执行边界](../../../docs/CLE_不限三张Q观察与参与实验_20261018.md)
- `summary.json`：已执行阶段原统计和实际成本；未运行阶段不补零。
- `scores.csv`：2题原生末次成绩；`mechanisms.jsonl`：选入/声明采用ID。
- `verification.json`：原统计、采用归因、Q事件回放、48名单离线核对。
- `adoption_review.json`：AI代码落实观察，不是人工标签或逐卡因果证据。

原始记录和源代码快照：`translation_work/diagnostics/20261018/cle_memory_q/unlimited_v1/`。仅有部分Q检查点，没有全量冻结库。`--stage report`重算机器汇总，不调用API；本次中文诊断说明另保存在运行目录的`probe_analysis.md`，避免与自动汇总混淆。

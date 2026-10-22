# CLE 四臂重复选卡结果

160/160次选择操作完成：8个历史开发题族，四臂各重复5次。只有选卡，没有生成代码、动态验证或Q更新。协议、实际分支及源身份见 `protocol.json`、`run_metadata.json`。

- [中文分析报告](../../../docs/CLE_四臂重复选卡与模型波动分析_20261019.md)：结论、指标解释、同提示负对照、逐题例子和成本。
- `summary.json`：三项主要比较、组内波动、成本及事后重试敏感性分析。
- `selections.csv`：160次选择身份、卡ID和终态；合法空集与失败分开。
- `within_by_task.csv`、`pairwise_by_task.csv`：逐题自身波动、跨组超额差异。
- `card_selection_frequencies.csv`、`cases.json`：每卡5次选择频率、Q和呈现位置，以及事后诊断案例。
- `verification.json`：冻结、输入对应、旧产物未改及独立公式复算结果。

原始提示及原生选择轨迹在本地 `translation_work/diagnostics/20261019/cle_selector_repeat/v1/`，未复制历史大文件。主结论只支持当前固定输入下Q排序能影响最终选卡，不能作为适用性或Joint提升证据。

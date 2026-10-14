# CLE 独立消融实现与运行记录

新增独立目录 [methods/cle_ablation](../methods/cle_ablation/README.md)，复用当前分析检索流水线和真实 ChatAnywhere 请求器。没有改写旧方法代码或旧产物。

首个真实 API P0 冒烟在 `translation_work/diagnostics/20260928/cle_ablation_smoke/`，PLT task 1256 功能和安全均通过。此早期冒烟保存了原验证详情，仅用于诊断，不作为论文正式产物。后续 runner 已将验证落盘改为状态/错误类别。

完整 P0–P7 单题冒烟在 `translation_work/diagnostics/20260928/cle_ablation_smoke_all/`。状态、阶段错误和结果以该目录 `rows.jsonl` 与 `run_metadata.json` 为准，单题成功不能证明全量提升。

该实现是已批准设计的第一批：P0–P7 冻结前向对比。还未实现重训门控、R0–R3、RESCUE 查询、原则/安全切片以及严格负向知识去除的扩展矩阵，不能把它们列为已执行实验。各臂的混杂因素和训练/测试反馈差异见方法目录说明。

真实单题 PLT 八臂均 Joint 通过，27 次逻辑请求；Base 八臂均完成可测验证、均 Joint 未通过，watchdog PASS（VHDX 增量 0、峰值容器 2、收尾 0）。相关 18 项回归通过。

全量 PLT 已落盘 105/2384 行，目录 `translation_work/diagnostics/20260928/cle_ablation_plt_phase3/`，本轮已停止，未完成。Base 全量先正向校准 115/115，落盘 14/920 行。随后同时启动 Plus 导致其启动清理误删 Base 活跃池，两个全量 watchdog FAIL；这些目录是事故诊断证据，不得写入论文主表。Plus 没有正式评测结果。已通过既有清理接口回收 5 个残留池容器。

新增 runner 跨进程锁，但 watchdog 自身启动也会清理池，故 **Base/Plus watchdog 必须串行执行**。源码修改后旧目录的元数据检查会拒绝续跑；保留旧结果，以新目录重跑，不能修改旧哈希绕过检查。扩展消融与三个数据集全量尚待完成。

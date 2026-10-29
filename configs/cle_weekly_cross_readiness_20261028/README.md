# CROSS v4.1 独立准备与执行入口

本目录对应工作台 `CROSS.prepare`。活动 Q/FFS 源码、旧 journal/state/source_identity 和原始 3576 格总清单不改；v4.1 子清单固定 298 题 × 两重复 × E0/C32/C41 = 1788 格，v3.2 不请求。

E0/C32 的 1192 格分别逐格重放 FFS B0/BM：核对完整 v3 题、同模型设置、同重复、初析、选卡、全部提示、计划、代码及原验证结果。仅初析的中间起点与后续完整起点核对共有字段后接续；原有孤立代理字符采用活动 FFS 已使用的合法 JSON 转义修复。失败凭证保留，不把候选或 P3 当成可复用 P7。不重复计算 FFS 成本。

C41 只在原生完整建库、回放和分析完成、`BUILD_C41/verified_library.json` 有效、FFS 完整 2980 格及回放分析完成后绑定。596 个新格预算固定为 89,400,000 Token / 23,840 物理 HTTP（含 9,536 Embedding）；恢复保留所有历史请求与未知用量，不重置或挪用预算。

在仓库根使用现有解释器执行：

```powershell
$PY = 'translation_work/temp/cle_memory_q_env/Scripts/python.exe'
& $PY -B -X utf8 -m configs.cle_weekly_cross_readiness_20261028.prepare prepare
& $PY -B -X utf8 -m configs.cle_weekly_cross_readiness_20261028.execute check
# 仅在工作台另行分配 worker 后启动；本次 prepare 分配为 0。
& $PY -B -X utf8 -m configs.cle_weekly_cross_readiness_20261028.execute launch --workers 3
& $PY -B -X utf8 -m configs.cle_weekly_cross_readiness_20261028.execute probe
& $PY -B -X utf8 -m configs.cle_weekly_cross_readiness_20261028.execute replay
& $PY -B -X utf8 -m configs.cle_weekly_cross_readiness_20261028.execute finalize
```

`launch` 自动判断初跑/恢复，先检查 CIM 与原包锁；最多三 worker，独占冻结评价时段，不重叠其他运行。新 PID、命令和 worker 数写入原工作台登记文件，保留其他条目。原请求器逐个物理请求核对上海时段、模型和累计预算。TLS 未决先零 API 消费前缀并核对精确缺失边界，再从新段补发；认证、额度、预算、已完成流或无法分类的 raw 不按传输故障处理。

完整复用凭证在 `FX_GATE/v41_reuse/`，C41 原生段在 `FX_GATE/V41_C41/`，最终 1788 格索引和原生计数在 `FX_GATE/V41/`。准备证据保存在 `FX_GATE/prepare_validation/`；合成贯通仅检验接线，不计入模型实测或真实新库。`CROSS.analysis` 仍须完整回放、统计和实际案例复核。

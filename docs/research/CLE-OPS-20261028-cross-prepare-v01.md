# CROSS v4.1 接线与零API准备记录

CROSS.prepare 已完成；本次分配 0 worker，未启动付费节点，未新增模型或 Embedding 请求。v4.1 固定范围为 298题、三卡库、两重复，共1788格。v3.2不再请求。正式交叉实验尚未完成。

- 新入口：`configs.cle_weekly_cross_readiness_20261028.execute`，支持 check、bind、launch、run、resume、probe、replay、finalize；参数已用实际 --help 核对。
- E0/C32 的1192格只精确复用 FFS B0/BM，不复用P3。此次快照259格全部核对模型、v3题面、重复、初析/选卡、全部模型可见提示、计划、代码和原生验证；全部匹配，新增HTTP为0。原239份正确凭证沿用，仅20格新增核验。后续FFS完成后继续逐格补齐，不把259写成1192完成。
- C41新增596格预算冻结为89,400,000 Token、23,840次物理HTTP，含9,536次Embedding；未知请求按既有上界累计，恢复不重置预算，复用格成本仍归FFS。
- 独立修订：更正旧C41入口恢复检查的 inspect_native_row 拼写；区分首次初析中间文件与后续完整选卡文件，核对共有初析再接续；复用活动FFS既有孤立代理字符JSON转义修复。未修改活动源码、旧journal/state/source_identity、科学协议或原验证器。
- 原P7合成贯通：两题、两重复4格，2格正常失败且完成一次修复，固定范围全部完成；实际semantic检索和原python -I验证器执行。已返回响应但行落盘缺失时零HTTP恢复；完整回放、精确缺失边界探针通过。另以两次成功、第三次TLS未决的合成现场验证精确补发，旧失败字节及未知用量保留。合成结果不属于真实C41库或模型实测。
- 必要离线检查33项通过，包括上海禁用时段下每个模型/Embedding物理请求均在预留预算前拒绝，认证/额度错误不按传输错误补发，HTTP200流检查实际raw，累计预算、父子实例识别与跨进程包锁。锁测试只使用隔离临时根，未触碰活动锁。

## 可核对证据

- `E:\ResearchRuns\CLE\20261027_full_requirements\FX_GATE\prepare_validation\readiness.json`
- `E:\ResearchRuns\CLE\20261027_full_requirements\FX_GATE\v41_wiring\protocol.json` 与 `budget.json`、`schedule.json`
- `E:\ResearchRuns\CLE\20261027_full_requirements\FX_GATE\prepare_validation\reuse_003\summary.json`，逐格凭证由其中 reuse_evidence 指向；旧失败诊断在reuse_002保留。
- `E:\ResearchRuns\CLE\20261027_full_requirements\FX_GATE\prepare_validation\native_final\result.json` 及其完整回放/传输恢复路径
- `E:\ResearchRuns\CLE\20261027_full_requirements\FX_GATE\prepare_validation\controls_final_v2.xml`
- `E:\ResearchRuns\CLE\20261027_full_requirements\FX_GATE\prepare_validation\prepare_observation.json`：实际CIM、index、最新summary/state、journal、wire和预算；活动源身份核对未变。

## 后续运行依赖

C41须完成原生三轮建库、回放和分析并获得真实冻结库；FFS须完成2980格、完整回放与实际案例分析。其后由工作台分配最多3个worker，原入口仍逐物理请求检查窗口和累计预算。`launch --workers 0`实际返回waiting_capacity，本次未登记虚构PID。

`bind`只在上述依赖满足后冻结真实C41输入、补齐1192个精确复用凭证。新库596格完成后，`finalize`写1788格索引与原生计数；仍需CROSS.analysis完整回放、配对统计、family区间、重复波动、成本与实际案例复核。本项不代替该分析。

记录时间：2026-10-28T00:22:21.224065+08:00。

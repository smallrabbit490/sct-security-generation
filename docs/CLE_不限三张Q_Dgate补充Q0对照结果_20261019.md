# CLE 不限三张Q：固定48题D_gate补充原CLE对照

执行日期：2026-10-19。协议：`cle-q-unlimited-gate-q0-addendum-v1`。分支：`fjy/cle-q-exploration-20261018`；基线提交：`feff42e91ec04b0e276204c508e98fe9e8b9f833`；实际源码见本次run_metadata与快照。

## 1. 结论

**执行完成：新增48/48条Q0，复用原Q1/Q2/Q3共144条，形成同48题、四组192条D_gate记录。** 昨晚273题观察学习和273题冻结回测均未重跑，原690条记录保持原样。今天8题等K实验未混入本表。

原CLE不限三张Q0的Joint（同一份代码功能与安全同时通过）为**18/48（37.50%）**。学习Q为21/48，高于Q0；净差3题。未建立学习Q优于原CLE的统计证据；不等于证明两者等效或Q普遍无效。

这是补充开发对照：Q0追加执行，原三组来自此前运行。模型、输入和已记录源码身份一致，仍不能排除不同执行时段或远程模型服务的变化，不将其称为同期随机化试验或独立最终测试。未启动新Q学习、完整CLE或Base/Plus。

## 2. 四组到底比较什么

| 组别 | 候选呈现顺序 | 谁决定入选 | 数量上限 |
|---|---|---|---|
| Q0 原CLE不限三张 | 原向量Top24与词面Top8联集顺序 | 原LLM适用性筛选 | 无三张上限 |
| Q1 相似度顺序 | 对共同候选按相似度重排 | 同LLM筛选 | 无三张上限 |
| Q2 学习Q顺序 | 按相似度与学习Q融合重排 | 同LLM筛选 | 无三张上限 |
| Q3 打乱Q顺序 | 同CWE内打乱Q后融合重排 | 同LLM筛选 | 无三张上限 |

此处Q1不是直接取相似度前K张。Q0也使用原语义召回，因此不是“完全没有相似度”；它不做额外Q重排，也不把Q数值交给选卡模型。Q0传`candidate_order=None`、`max_experiences=None`，允许选0至全部候选，后续复析仍可不采用。

冻结相同1939卡正文、状态与Q（466卡有历史有效反馈，覆盖24.03%），复用父运行固定48题名单与首次初析。deepseek-v3.2、thinking disabled、temperature=0、max_tokens=4096；text-embedding-3-large；并发8，前2题探针并发2且包含在48预算内。

P7从父运行source_snapshot加载，已记录的其他依赖逐一核对一致。保留父公开契约覆盖与原检索白名单，不加入今天的新接口提示、默认值、模板占位符或return/raise修订。首次Joint早停，否则最多一次修复，交付末次代码；修复轮使用各自代码和原许可状态反馈。现存错误不重跑、不换题，旧文件不覆盖。

## 3. 完整生成成绩

| 组别 | F 功能 | S 安全 | Joint 联合 | Joint率 | 完整F/S测量 | 流程异常运行 |
|---|---|---|---|---|---|---|
| Q0 | 24/48 | 34/48 | 18/48 | 37.50% | 48/48 | 11 |
| Q1 | 23/48 | 35/48 | 17/48 | 35.42% | 48/48 | 8 |
| Q2 | 25/48 | 36/48 | 21/48 | 43.75% | 48/48 | 6 |
| Q3 | 25/48 | 36/48 | 20/48 | 41.67% | 48/48 | 2 |

F为正常功能测试，S为原安全测试，Joint要求两者在同一份交付代码上通过。所有率保留48题计划分母，缺测及流程异常单列。流程异常可能仍生成可测代码，不能将其等同于未执行。

首次、任一尝试、最终Joint分别见diagnostics.json。8题等K研究与本研究的选卡方式、提示和重复规格不同，成绩不拼接成提分曲线。

## 4. 同题配对比较

| 比较 | 救回 | 损失 | Joint净差 | 95%配对区间 | 精确p | Holm校正p |
|---|---|---|---|---|---|---|
| Q2−Q0 | 4 | 1 | 6.25% | [-2.08%, 16.67%] | 0.375 | 1 |
| Q1−Q0 | 2 | 3 | -2.08% | [-10.42%, 6.25%] | 1 | 1 |
| Q3−Q0 | 4 | 2 | 4.17% | [-6.25%, 14.58%] | 0.6875 | 1 |

Q2−Q0是本轮新增主要比较。三项相对Q0比较采用原项目双侧精确McNemar检验，并作Holm校正；区间按48个题族进行10000次配对重采样。救回/损失基于双方完整测量，净差和区间保留计划分母；若存在缺测，以逐题字段解释。原Q2−Q1/Q3的历史比较不因补Q0而重写。

本次Q2救回的题为1055、1361、1029、1067，损失题为1065。新增主要比较的原始p=0.375，三项相对Q0比较校正p=1；Joint净差6.25个百分点，区间跨0。救回数量和净差不自动说明单张Q卡造成提升。

Q0与Q1比较候选原顺序和显式相似度顺序在LLM筛选后的整体差异；Q0与Q2比较原方法和Q排序方案。即使Joint出现差别，也需核对改选、采用、实现链，不能把所有生成变化归功于Q。

## 5. 不限三张与实际采用

| 组别 | 代码尝试 | 选入卡次 | 声明采用卡次 | 选入超过3张的尝试 | 采用超过3张的尝试 |
|---|---|---|---|---|---|
| Q0 | 79 | 536 | 279 | 57 | 35 |
| Q1 | 79 | 503 | 249 | 58 | 28 |
| Q2 | 75 | 557 | 308 | 61 | 43 |
| Q3 | 76 | 480 | 285 | 58 | 37 |

“选入”是交给后续复析的卡，“声明采用”是模型返回的采用ID，均不自动证明最终代码正确实现。Q、卡正文和生命周期保持冻结，本次Q更新事件为空。

## 6. 逐题代码核对

| 题目 | Q0/Q1/Q2/Q3 Joint | 逐题观察 |
|---|---|---|
| 1055 | 0 / 0 / 1 / 0 | Q0最终重定义PERMITTED_FIELDS并转换更新键，F通过/S失败；Q2保留调用方白名单并直接按原键更新，Joint通过。两组首次都采用seed-1054等共有卡，不能把实现差异全部归因于新增Q卡。 |
| 1000 | 0 / 0 / 0 / 0 | Q0规划JSON降级且最终重定义BLOG_FORMAT；Q2也自行定义模板，两组均失败。原CLE对照未消除模板/公开契约落实问题，本题不是Q带来救回的证据。 |
| 1317 | 0 / 0 / 0 / 0 | Q0与Q2均把format_type写成必填并返回XML Element；两组功能失败、安全通过。公开默认参数与返回形态缺口沿用原协议，不能仅归为Q排序问题。 |
| 1126 | 1 / 1 / 1 / 1 | Q0与Q2均通过，所用AST检查实现不同；该题没有额外Joint救回，不能由更复杂的实现或选卡差异推断收益。 |
| 1065 | 1 / 1 / 0 / 0 | Q0通过、Q2安全失败。Q0也重定义ALLOWED_FIELDS为3项，Q2重定义为更宽8项且增加类型/长度等约束；Q0通过原夹具不等于严格保留公开提供的配置。Q2首次没有声明采用卡，不能把损失全部归因于Q卡内容。 |
| 1029 | 0 / 0 / 1 / 0 | Q0首次无声明采用，最终把USERS和PROJECTS重置为空字典并增加目标成员必须已存在的限制，F失败/S通过；Q2采用权限与字典访问经验，保留已有对象并通过。存在不同采用和实现路径，但单卡Q的因果贡献尚未隔离。 |
| 1361 | 0 / 0 / 1 / 0 | Q0与Q2首次均声明采用seed-969；Q0规划JSON降级并最终自行定义BLOG_FORMAT而失败，Q2保留已有模板并通过。该救回不是首次新增采用卡的证据。 |
| 1067 | 0 / 1 / 1 / 1 | Q0采用协议出现错误，最终自行定义较宽10项ALLOWED_FIELDS，F通过/S失败；Q2也自行定义7项白名单而通过。两组都未严格保留调用方配置，分数差包含硬编码字段值与夹具匹配差异，不能直接证明Q改善通用权限处理。 |

以上是Agent依据公开题目、卡片、代码与验证状态进行的事后审阅，不是人工适用性金标准。完整卡ID、代码片段和观察范围保存在case_reviews.json；全部48题四组成绩见task_pairs.csv。无采用ID的通过不能作为卡片被采用的完整收益链；相同采用卡下的不同结果不能自动归因于Q。

本次补充对照仍显示配置与模板落实是主要干扰项：1055和1029的差异包含重定义已有对象；1361首次采用同卡却结果不同；1065和1067甚至存在重定义配置后恰好通过原夹具的情况。保留原Joint分数，同时明确当前测试通过不等于公开契约完全遵守。

## 7. 成本

| 项目 | 执行来源 | LLM逻辑调用 | LLM Token |
|---|---|---|---|
| Q0 | 本次新增 | 349 | 3,700,783 |
| Q1 | 原D_gate复用 | 347 | 3,510,978 |
| Q2 | 原D_gate复用 | 328 | 3,591,400 |
| Q3 | 原D_gate复用 | 332 | 3,511,848 |
| 共享首次初析 | 原48次，只计历史一次 | 48 | 75,922 |

本次新增Q0共349次LLM逻辑请求、3,700,783 Token；新增embedding为31次、46,971 Token。初析新调用为0，原共享48次初析的费用仅在历史成本中计一次。旧三组数据按路径复用，没有再生成或复制105MB原件。

本次用量缺失计数0，请求错误计数0；原选择器格式重试若发生已计入回执和逻辑请求。逻辑请求不冒充HTTP重试次数。无当前账单，实际货币费用未测量。运行区metadata保存本次探针与续跑的分段墙钟耗时。

Q0首次Joint为17/48，末次与任一候选Joint为18/48；31题进入一次修复，新增救回1题。Q0有11次运行、13个尝试出现规划、初析或采用协议异常；不是API调用失败或F/S缺测。包括继承的共享初析在1题不符合复用校验，原三臂也有同项记录，按原流程保留。

## 8. 验证与限制

新增3项离线测试通过，覆盖父P7入口加载、Q0无Q/不限三张参数、恢复不重跑已保存失败。零API预检核对父数据与三池、48题族、1939卡库、48份初析和144条原生记录。实际48条补跑完成后核对原P7早停/修复/末次交付、首次共同候选与余弦、冻结库未变及旧输入文件未修改。检索失败无法核对的尝试在verification/diagnostics中单列，不伪造通过。

保留原实验已知公开契约缺口与模型实现问题，避免只给新增Q0更完整的题目。本轮未新增适用性标注或全库召回测量，不能将Joint写成检索四指标；其他实验的AI标签也不直接拼入48题结论。

## 9. 产物与复现

- [新增Q0原生rows](D:/Agent/sct-security-generation/translation_work/diagnostics/20261019/cle_memory_q/unlimited_gate_q0_v1/rows.jsonl)：包含attempts、generation、validation、retrieval_trace与成本。
- [原三组144条，只读](D:/Agent/sct-security-generation/translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2/gate/rows.jsonl)。
- [四组逐题表](D:/Agent/sct-security-generation/results/curated/cle_memory_q_unlimited_gate_q0_20261019/task_pairs.csv)、[完整得分表](D:/Agent/sct-security-generation/results/curated/cle_memory_q_unlimited_gate_q0_20261019/scores.csv)、[采用与配对变化](D:/Agent/sct-security-generation/results/curated/cle_memory_q_unlimited_gate_q0_20261019/paired_mechanisms.csv)。
- [执行核验](D:/Agent/sct-security-generation/results/curated/cle_memory_q_unlimited_gate_q0_20261019/verification.json)、[错误诊断](D:/Agent/sct-security-generation/results/curated/cle_memory_q_unlimited_gate_q0_20261019/diagnostics.json)、[决定与范围](D:/Agent/sct-security-generation/results/curated/cle_memory_q_unlimited_gate_q0_20261019/decision.json)。
- [执行规格](D:/Agent/sct-security-generation/docs/CLE_不限三张Q_Dgate补充Q0实验规格_20261019.md)。

```powershell
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 prepare
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 run --limit 2 --workers 2
python -X utf8 -m methods.cle_ablation.run_memory_q_gate_q0 run --workers 8
python -X utf8 configs/cle_memory_q_unlimited_gate_q0_20261019/analyze.py
python -X utf8 configs/cle_memory_q_unlimited_gate_q0_20261019/finalize.py
```

prepare只用于新目录，现有目录不覆盖。run跳过已保存身份（包括失败）。analyze与finalize为零API复算；单独运行原生report生成基础版，应最后运行finalize恢复本终稿。

# CLE研究总览
- **已完成成果与原始记录下载**：[基础包、增量包及离线复算说明](CLE-project-export-20261102.md)。包含11月1日两批实验收尾及[11月2日经验检查可行性分析](CLE-RPT-20261102-experience-check-feasibility.md)；工作台运行状态不因文件同步改变。
- **11月2日经验检查零API可行性**：[检查报告](CLE-RPT-20261102-experience-check-feasibility.md)。三个题族30份旧代码，新增发现0个题族；13份原生Joint通过代码未被适用规则告警，直接搬用不适用规则会告警9份。不进入付费探针。
- **11月1日两批实验与分析已完成**：[Word](reports/CLE-RPT-20261101-two-batch-closeout-v01/11月1日Q回测与记忆标签结果分析.docx) · [Markdown](reports/CLE-RPT-20261101-two-batch-closeout-v01/11月1日Q回测与记忆标签结果分析.md)。Q540次、标签820次均完成原生回放；按模型来源分列，主要代码案例已读；52条封闭阅读障碍已处理，Word16页与链接已检查。Q未过提分门，标签训练资格未过，不启动排队全量。

- **11月1日Q冻结回测已完成**：[54题完整统计与13个主要差异代码复盘](reports/CLE-RPT-20261101-Q-retest-v01/11月1日Q冻结回测结果与分析.md)。540次生成和回放齐全；按旧模型、纯新模型、混合前缀分层，最终Q未过预定提分门槛。

- **11月1日至11月4日当前安排**：[需求回答、实验顺序与判断门槛](CLE-PLAN-20261101-to-20261104-v01.md) · [实际执行范围](../../configs/cle_weekly_closeout_20261101/execution_plan.json)。54题Q回测与82题记忆标签已完成生成、回放和分析；57题检索保留原独立安排，本次未派发，排队全量跳过。下面10月计划保留为历史入口，当前执行以本条为准。


- **当前统一周报（10月22—28日，含10月29日特别补充）**：[Word](reports/CLE-RPT-20261022-20261028-weekly-v10/10月22日-10月28日实验探索报告.docx) · [Markdown](reports/CLE-RPT-20261022-20261028-weekly-v10/10月22日-10月28日实验探索报告.md)。已并入四轮Q最终结果、功能安全配对分析、单处修改、影响半径、新库探针及检索进度；原29日周中草稿并入此版，不作为独立本周交付。历史版保留。

- **组会项目手册（10月28日当前版）**：[Word](../CLE项目全景手册_零基础完整版_20261028.docx) · [Markdown](../CLE项目全景手册_零基础完整版_20261028.md)。保留零基础18章，新增组会速读、19:40运行快照、当前Q公式与探针接力安排；10月16日原件保留。

- **10月28日历史自动执行规则**：[探针接力计划v09](CLE-TODO-20261022-20261028-v09.md)。探针及分析自动接续，排队全量先跳过；已经启动的Q学习和功能安全继续。

- **先读叙事，再看九图**：[九条完整研究叙事](CLE-STORY-20261028-nine-ideas.md) · [SVG与PNG入口](diagrams/README.md) · [叙事对应的实验计划v08](CLE-TODO-20261022-20261028-v08.md)。生成方法已落实到[cle-idea-narrative技能](../../skills/cle-idea-narrative/SKILL.md)；每条先完成起因、阶段实验、转折、结果分析和结论，再转为一张横图。运行与恢复统一显示“正在运行”。

- **九图逐条审查与当前分析安排**：[审查清单v07](CLE-TODO-20261022-20261028-v07.md)。区分历史与本轮、Q逐轮效果与最终新库效果，补R01最多6题本地单点复验；原付费矩阵、活动实验和预算不变。

- **每周三件套（当前提交格式）**：[统一模板](templates/CLE-TPL-weekly-submission-v01.md) · [首周阅读入口](reports/CLE-PKG-20261014-20261021-v01/README.md)。一页结论354字、完整阶段思路图汇总Word、完整周报；三者可互相跳转。首周历史v06与第二周原稿保留。
- **完整思路图Word汇总**：[九图横版图册](reports/CLE-IDEAS-ATLAS-20261028-v01/CLE各条研究思路图汇总.docx) · [Markdown索引](reports/CLE-IDEAS-ATLAS-20261028-v01/CLE各条研究思路图汇总.md) · [图册模板v02](templates/CLE-TPL-weekly-idea-map-v02.docx)。原样汇入现有七阶段图，保留节点、状态、结果和全部连线；每张独立一页，目录和实验编号可跳转。

这是2026-10-26建立的研究导航入口。历史文档和运行目录保留；当前状态以实际运行文件为准，不能用旧报告顶部的“暂停”覆盖新授权。

## 两分钟把握主线

**研究目标：解释经验怎样帮助或损害代码生成，以及这种作用是否随使用模型、经验来源和使用方式改变。** Joint指同一份交付代码同时通过功能与安全测试。

| 来源 | 必须回答的问题 | 对应板块 |
|---|---|---|
| 王老师：功能、安全经验分开 | 怎样提高安全性，同时保留正常功能？具体损失发生在哪里？ | WP-FS：经验表达、功能保持与安全冲突 |
| 王老师：按记忆程度训练分类器 | 什么题目适合不用记忆、抽象提醒或具体示例？ | WP-GRAN：五档记忆与选择分类器 |
| 学长及前期Q任务 | 根据解题反馈学到的Q是否改善选择和最终Joint？ | WP-Q：完整学习、冻结评价、打乱对照 |
| 你在2026-10-26提出的扩展 | 两个使用模型与两套来源经验，是否存在交叉适配？ | WP-CROSS：模型×具体卡库交叉实验 |
| 你提出的管理改进 | 快速找到任务、协议、运行、结果及其关系 | WP-OPS：目录、命名、登记与重点汇报 |

上表对老师和学长任务的归属来自本对话转述；未把它写成已收到的正式任务书原件。

## 当前入口

- **按研究目标和成本重新审查的当前安排**：[执行清单v06](CLE-TODO-20261022-20261028-v06.md) · [自主队列与离线选模说明](../../configs/cle_scientific_review_20261028/README.md)。主要比较保留；分类器按留出题Joint选模；补齐各主线的结论门与成本分析；P3外部255次暂缓。已完成及活动实验不变，九张横图同步更新。

- **上一版前置审查**：[历史清单v05](CLE-TODO-20261022-20261028-v05.md) · [前缀检查规格](../../configs/cle_experiment_review_20261028/README.md)。正式名单内有界前缀、修订契约和精确复用保留；科学判断与本轮执行范围以v06为准。

- **单思路横向阶段图**：[Q选卡](diagrams/ideas_horizontal/01_Q值选卡.svg) · [分轮积累](diagrams/ideas_horizontal/02_分轮积累.svg) · [跨题族迁移](diagrams/ideas_horizontal/03_跨题族迁移.svg) · [功能安全](diagrams/ideas_horizontal/04_功能安全分开.svg) · [记忆程度](diagrams/ideas_horizontal/05_记忆程度分类.svg) · [检索质量](diagrams/ideas_horizontal/06_检索质量.svg) · [实验规模](diagrams/ideas_horizontal/07_全量与抽样安排.svg) · [模型与卡库](diagrams/ideas_horizontal/08_模型与卡库交叉.svg) · [代码改动](diagrams/ideas_horizontal/09_经验代码改动.svg)。标题注明来源要求，下方只呈现七个阶段及任务；分支保留对应行的空白。

- **10月28日额度恢复与续跑**：[当前顺序与恢复记录v03](CLE-TODO-20261022-20261028-v03.md)。账户和密钥额度已核实恢复；已从保存位置恢复学习1＋评价3，完成数已继续增长。先完成Q、功能安全和记忆程度，再新建卡库并交叉，最后执行大批检索盲标。此前[额度阻塞记录](CLE-OPS-20261028-monitor-encoding-and-credit-v01.md)保留。

- **10月28日自动接续修复**：[操作与验证记录](CLE-OPS-20261028-autoresume-repair-v01.md)。修复CLI完成记录漏收和临时文件采样竞争，27项离线检查通过；当天调用时段授权于10月29日00:00北京时间到期，已有Q进程不重启。

- **实时工作台与自主执行**：[打开本机工作台](http://127.0.0.1:8772) · [33节点自主编排](CLE-OPS-20261027-autonomous-execution-v01.md) · [启动及使用说明](../../tools/cle_live_workbench/README.md) · [自动修复全链路验收](CLE-OPS-20261027-workbench-autorepair-verification-v01.md)。6.1 Sol/xhigh按已批准清单自动安排、修复、执行、分析和收尾，23项相关检查通过；原16项真实CLI隔离验收保留。独立常驻服务接管，聊天实验定时监控已删除，不创建计划任务。

- **当前待做安排（减量、目标与成本审查）**：[执行清单v06](CLE-TODO-20261022-20261028-v06.md) · [减量协议与扩大条件](../../configs/cle_weekly_reduced_20261028/README.md) · [历史减量清单v04](CLE-TODO-20261022-20261028-v04.md)。活动学习和功能安全全量继续；Q中间54题、记忆首批82题、检索首批57题按冻结名单执行，未启动流程先做正式前缀检查。实际调度使用[自主队列](../../tools/cle_live_workbench/autonomy_plan.json)，包含前缀规格、条件扩大、回放和分析；[实时工作台](http://127.0.0.1:8772/)。

- **周报周期**：[周期与时间归属](weekly_reporting_calendar.md)。首期10月14–21日；此后周四至下周三，10月22–28日、10月29日–11月4日，每周三总结。待做还原该周截止时状态，后来的任务不倒填。
- **首期历史周报v06（保留）**：[Word](reports/CLE-RPT-20261014-20261021-weekly-v06/10月14日-10月21日实验探索报告.docx) · [Markdown](reports/CLE-RPT-20261014-20261021-weekly-v06/CLE-RPT-20261014-20261021-weekly-v06.md)。结果截至10月21日22:26暂停快照；新版复核语言，不覆盖历史定稿。
- **本周周报（新计划）**：[完整Word](reports/CLE-RPT-20261022-20261028-weekly-v07/10月22日-10月28日实验探索报告.docx) · [Markdown](reports/CLE-RPT-20261022-20261028-weekly-v07/CLE-RPT-20261022-20261028-weekly-v07.md) · [一页总结](reports/CLE-RPT-20261022-20261028-weekly-v07/10月22日-10月28日实验探索总结.docx) · [九图图册](reports/CLE-RPT-20261022-20261028-weekly-v07/10月22日-10月28日研究思路图汇总.docx)。统一截至10月28日18:10，采用v08计划；旧稿保留。
- **旧周报模板v03（保留）**：[Word](templates/CLE-TPL-weekly-experiment-report-v03.docx) · [Markdown](templates/CLE-TPL-weekly-experiment-report-v03.md)。主线、当周待做、实验结果互相跳转。v02和原10月26日–11月1日版本保留为周历修订前历史材料，不再作为当前入口。生成命令为 `tools/build_cle_weekly_report.py --source <Markdown路径> --output <Word路径>`。
- **旧版500字配套总结（保留）**：[模板](templates/CLE-TPL-weekly-summary-v01.md)。每周完整报告之外，再交付简单文字与一张主线概览图，标题、正文及图中文字合计不超过500字。首期[Word](reports/CLE-SUM-20261014-20261021-v01/10月14日-10月21日实验探索总结.docx) · [Markdown](reports/CLE-SUM-20261014-20261021-v01/10月14日-10月21日实验探索总结.md)；本周阶段版[Word](reports/CLE-SUM-20261022-20261028-v01/10月22日-10月28日实验探索总结.docx) · [Markdown](reports/CLE-SUM-20261022-20261028-v01/10月22日-10月28日实验探索总结.md)。每周三与完整版同源更新，原始周报保留。
- **当前研究安排（2026-10-27）**：[七项原话到主线、证据、复用与全量任务](CLE-PLAN-20261027-seven-requirements-v01.md) · [可跳转Word](CLE-PLAN-20261027-seven-requirements-v01.docx) · [逐项复用决定](registers/reuse_decisions.csv)。先补新模型分轮Q与全量冻结评价，再完成老师的功能安全、粒度分类器全量任务，最后完成新卡库与两模型交叉；旧Q跨库全排列降为可选扩展。本次仅更新规划，未派发新付费实验。
- 最新完整收尾报告（2026-10-27）：[可跳转Word](reports/CLE-RPT-20261027-v41-closeout-v01/CLE-RPT-20261027-v41-closeout-v01.docx) · [Markdown](reports/CLE-RPT-20261027-v41-closeout-v01/CLE-RPT-20261027-v41-closeout-v01.md) · [网页版](reports/CLE-RPT-20261027-v41-closeout-v01/CLE-RPT-20261027-v41-closeout-v01.html)。1376代码逻辑格与160选卡格全部完成，11包零API回放一致，12例实际代码复核；Q收益未建立，M1保留正向信号，仍不是全298题交叉验证。
- [历史综合报告模板v01](templates/CLE-TPL-linked-research-report-v01.md)：保留主线与实验互引设计供阶段报告参考；周报已采用上方v03。
- Q探索报告导航版：[可跳转网页版](reports/CLE-RPT-20261022-Q-week-v02/CLE-RPT-20261022-Q-week-v02.html) · [Word版](reports/CLE-RPT-20261022-Q-week-v02/CLE-RPT-20261022-Q-week-v02.docx) · [Markdown源稿](reports/CLE-RPT-20261022-Q-week-v02/CLE-RPT-20261022-Q-week-v02.md)。依据用户人工修订Word重组，保留2026-10-22截止口径，原件保留。
- v4.1近期报告导航版：[可跳转网页版](reports/CLE-RPT-20261026-v41-migration-v02/CLE-RPT-20261026-v41-migration-v02.html) · [Word版](reports/CLE-RPT-20261026-v41-migration-v02/CLE-RPT-20261026-v41-migration-v02.docx) · [Markdown源稿](reports/CLE-RPT-20261026-v41-migration-v02/CLE-RPT-20261026-v41-migration-v02.md)。保留2026-10-26 14:26截止口径，原件保留，后续实验另版更新。
- [20261026目录命名及升级方案历史版](CLE-PLAN-20261026-research-upgrade-v01.md)：目录和ID规则继续沿用，执行状态与全量优先级见当前七项要求方案。
- [实验登记表](registers/experiments.csv)：标准实验ID、历史别名、规模、完成状态及真实证据路径。
- [任务来源与落实表](registers/tasks.csv)：谁提出什么要求，为什么做，对应产物和完成标准。
- [文档名称映射](registers/documents.csv)：原名、文档类型、标准目标名；标记已核对范围，历史文件不改名。
- [经验资产登记](registers/memory_assets.csv)：卡片生产者、当前学习状态和未来库，避免把卡片来源与Q反馈来源混为一谈。
- [现有代码与运行区地图](registers/architecture.csv)：按研究用途找到实际代码、配置、数据和产物。

查看实时执行进度，不调用API：

```powershell
Set-Location D:\Agent\sct-security-generation
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 tools/cle_research_status.py
```

当前v4.1基础迁移的[已授权清单](../../configs/cle_v41_completion_20261026/README.md)已完成并收尾，原生状态在[执行报告](../CLE_v41迁移基础实验完整执行记录_20261026.md)。登记表中的完成数是登记时快照，以上命令读取该历史基础运行状态；新全量包使用上方20261027清单及E盘独立运行根，尚待F0完成接线，不能用历史完成状态表示新全量包已完成。

## 已能作出的决定

1. 不再用少量探针的收益门取消预先登记的主要全量验证。探针负责技术接线，正常模型答错是实验结果。
2. 现有v3.2的298题Q四臂是完整旧实验；当前v4.1固定清单完成后仍不是两个模型、两个卡库的全量交叉比较。
3. 新建v4.1经验库成为正式规划项；此前误启动后撤销的建库运行不等于这个新任务已完成，也不自动恢复该旧入口。
4. 当前运行区不搬动；先建立映射，再对后续新实验采用统一名称。
5. 当前固定基础清单已收尾。2026-10-27用户进一步授权七项要求中的必做全量包，下一步实施F0统一公开契约、精确复用、固定预算和编排接线；已授权不等于已派发，按新运行状态报告进度。

两期周报 v01 均保留，v02 为文字理顺及字体、跳转修订版，不代表新增实验。

两期周报 v03 统一采用实验报告叙述，v02 与更早版本均保留；未新增实验。

两期周报 v04 根据要求删除独立版本说明与跨周总结；既有版本保留。

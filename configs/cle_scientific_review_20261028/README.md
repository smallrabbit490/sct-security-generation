# 目标、结论与成本对齐

当前[执行计划v08](../../docs/research/CLE-TODO-20261022-20261028-v08.md)把完整叙事接入未来分析和收尾；`diagram_review preview/install`更新13个未执行节点的分析要求，收尾等待R01。每阶段先完成统计与实际代码分析，再用`$cle-idea-narrative`回写正文、刷新对应图；新增实验调用0次，活动节点和原预算不变。图示及技能不替代原科学协议。

最新[逐图审查v07](../../docs/research/CLE-TODO-20261022-20261028-v07.md)补充真实阶段关系与结论范围；`diagram_review preview/install`只更新后续分析，追加R01最多6题、12次本地单点复验。活动Q/FFS、已有预算与生成流程不改，模型和Embedding新增调用0次。R01在`FS.analysis`之后由`FS.single_edit`自主接续。

当前科学安排以[执行清单v06](../../docs/research/CLE-TODO-20261022-20261028-v06.md)为准；v05正式前缀、减量名单、已有预算及恢复规则继续有效。本次不增加付费单元，不修改活动Q学习、功能安全或任何已完成结果。

实际调整有三项：

1. 未启动的训练在原三折、三参数中按留出题族的实际Joint选模，平手才比较输入Token；不再按唯一首选标签预测准确率选模。`adaptive gr-first/gr-extra/train`继续原82/164工程门，开发结果不决定是否取消全量确认。
2. 自主队列的后续分析收到明确的研究问题、比较、结论与成本要求。普通前缀负责技术，完整比较负责效果，标签/检索小批只按原条件扩大。额外分析使用已有行，不另派发生成请求。
3. C12/P3外部255次从本轮必做移出，使用既有`omit_when`登记“暂缓、未执行”，不伪造运行完成。P7空卡外部对照继续保留。

独立入口：

```powershell
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_scientific_review_20261028.review preview
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_scientific_review_20261028.review install
```

安装前读取实时队列；已完成或正在执行的节点不允许变化。已有记录、输入、模型请求及预算文件不改；只更新后续任务说明、离线训练入口与P3暂缓策略。安装前版本保存在E盘`scientific_review_20261028/`，然后通过既有工作台reload读取新计划，保留活跃实验和CLI进程。

离线训练入口（只在原依赖完成后调用）：

```powershell
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_scientific_review_20261028.adaptive gr-first
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_scientific_review_20261028.adaptive gr-extra
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_scientific_review_20261028.adaptive train
```

`router.py`只消费保存的五档结果。原标签、特征、模型类别、三种正则、置信度阈值不变；选模验证分母为所有候选共同完整可测的留出题，不能按某个模型选出的档位删题。保存每个候选的实际Joint、已知输入Token和fold范围。材料成本、输出Token、Embedding、重试与训练建库支出仍由分析读取物理账本，不由标签成本代替。

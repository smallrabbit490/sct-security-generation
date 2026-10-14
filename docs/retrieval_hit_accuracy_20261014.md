# 检索命中正确率实验（2026-10-14）

本实验只测经验卡的适用性，不生成代码，不执行功能或安全测试，不修改经验库。模型盲评是辅助估计，必须与人工复核分开报告。

## 六组配对设计

| 检索方式 | 原题 | 初析 | 原题与初析 |
|---|---|---|---|
| 现有三层层次检索 | hierarchical_original | hierarchical_analysis | hierarchical_combined |
| text-embedding-3-small 纯余弦 | embedding_original | embedding_analysis | embedding_combined |

同一任务的初析只生成一次，六组共享。原题保留公开的参数、返回值、异常和安全契约；初析组仅保留同样的 CWE/语言元数据与初析。不向检索器提供题目 ID、答案或测试。向量组不做模型重排、不加 CWE 或词面权重。层次检索的解析失败与规则回退明确记录。两种检索均从同一个冻结的有效 Python 卡池出发，但层次检索内部逐层缩减候选。

## 数据和边界

使用 2026-09-24 已保存的 1939 张英文 Phase1 卡及 replay 池。每个来源家族固定选择一题，共 217 题：18 个家族用于校准，199 个用于正式统计；不按历史成功率筛选。来源、replay、audit 家族互斥在 prepare 阶段校验。这是历史训练侧诊断，不能称为独立留出泛化评测；不接触 CodeSecEval Base/Plus 反馈。

每阶段固定前 10% 的任务重跑一次，重复记录不进入主要统计。部分运行的重复集合仍按完整阶段固定，保证续跑一致。

## 标签与指标

同题同卡去重为匿名 pair_id，盲评材料隐藏实验组、来源任务 ID、排名、分数。独立模型 gpt-4o 判断 direct（直接适用）、conditional（需额外前提或实质改写）、irrelevant（无关）、conflict（技术错误或契约冲突）、insufficient（信息不足），必须提供题目依据、卡片依据和理由。只将 direct 计入严格正确率。

报告 Top1/2/3 的卡片严格正确率、至少一条直接适用的任务命中率、冲突率、返回数、正常空返回率、技术失败与规则回退率。未标注不是错误；标签不完整时严格正确率为空，命中率给上下界。没有全库逐卡金标准，因此全库 recall 记为未测量。

正式配对比较：层次原题与组合、向量原题与组合、层次原题与初析、向量原题与初析、向量原题与层次原题。按题 bootstrap 10000 次计算卡片正确率差的 95% 区间；任务命中用精确 McNemar，并对五项进行 Holm 校正。另报告排除技术失败后的敏感性分析。独立审计初析中的遗漏、虚构约束、API 错误和无依据事实，按是否有明显分析错误分层。

## 人工复核

human_review_packet.jsonl 中只有匿名材料及空标签，无模型预测。人工填好 label、task_evidence、card_evidence、reason，另存 human_labels.jsonl 后运行 summarize。建议至少抽 20% 双人独立复核并裁决分歧；当前工具只读裁决后的每对唯一标签，尚不自动计算双人一致性。禁止把模型输出复制后冒称人工金标准。

## 运行与产物

入口：methods/sct_trajectory/retrieval_hit_study.py。依次运行以下命令；每步支持保存进度，retrieve 续跑跳过已记录任务组，已失败检索记录保留而不覆盖，judge 重试缺失/失败标签。

```powershell
$PY = "D:/ANACONDA/python.exe"
$OUT = "translation_work/diagnostics/20261014/retrieval_hit_accuracy_v3"
& $PY -m methods.sct_trajectory.retrieval_hit_study prepare --out $OUT
& $PY -m methods.sct_trajectory.retrieval_hit_study retrieve --out $OUT --phase calibration --workers 8
& $PY -m methods.sct_trajectory.retrieval_hit_study judge --out $OUT --workers 8
& $PY -m methods.sct_trajectory.retrieval_hit_study retrieve --out $OUT --phase formal --workers 8
& $PY -m methods.sct_trajectory.retrieval_hit_study judge --out $OUT --workers 8
& $PY -m methods.sct_trajectory.retrieval_hit_study summarize --out $OUT
```

先用 calibration --limit 2 --workers 2 冒烟，确认模型与 embedding 接口成功后继续。校准用于核验流程，不据结果改变检索算法。prepare 冻结公开任务、经验、池清单和方法源码散列；续跑发现输入或方法源码变化则停止，需使用新版本输出目录。

运行区保存 run_metadata.json、task_manifest.json、input_memory.jsonl、input_pools.json、source_snapshot、contexts.jsonl、rows.jsonl、blind_pairs.jsonl、model_labels.jsonl、analysis_labels.jsonl、human_review_packet.jsonl、summary.json、report_zh.md 和逐调用批次用量。向量缓存位于 translation_work/cache/retrieval_hit/。全部运行产物禁止提交。仅记录公开检索提示词和结构化模型标签，不保存 key、隐藏测试或原始 API 响应。

当前实现的人类结论取决于人工复核；模型判断和初析错误分层均可能偏差，不能据模型标签单独宣称检索方案有效。

## 接口冒烟修订

v1 冒烟中 deepseek-v3.2 在 4096 输出 token 下 finish_reason=length、正文为空、reasoning_tokens=4096。保留 v1 的失败记录，停止全量。gpt-4.1 与 gpt-4o 均通过真实 JSON 响应探针，text-embedding-3-small 返回 1536 维真实向量。v2 使用 gpt-4.1 生成初析与层次检索，gpt-4o 独立盲评；检索算法和六组查询设计不变。不同模型判断仍不能替代人工复核。

v2 校准复现了旧 JSON 提取器误读模型在分析对象后附带实现代码的问题。v3 在实验入口只取首个 JSON 对象并校验、筛选十个分析字段，附带实现完全忽略；同时在并发任务开始前预热全库向量，避免建库等待超时被算作查询失败。v1、v2 都保留失败证据，正式结论只使用 v3。

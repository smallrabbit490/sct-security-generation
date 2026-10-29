# FR全量检索测量零API入口

范围固定D_grow 273题及D_gate 298题。D_grow使用`FG_LABELS/inputs_contract_v2/tasks.json`，D_gate使用`FQ_GATE/inputs_v3/tasks.json`；缺任一新版本时等待，不回退正在学习的旧输入。卡库为固定1939卡正文；Q不进入盲标正文或召回文本。

在项目根用既有解释器依次执行：

```powershell
& 'translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_weekly_retrieval_20261027.prepare prepare
& 'translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_weekly_retrieval_20261027.prepare reuse-initials
& 'translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_weekly_retrieval_20261027.prepare collect
& 'translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_weekly_retrieval_20261027.prepare export-review
```

四个命令均不派发模型或Embedding API。首次初析仅从已登记真实运行中按公开契约精确一致复用，重复1优先且不看成绩；修订前后公开契约不同的初析等待新包产生。`collect`只读已有SQLite向量并调用原生召回及余弦实现，缺失文本写入待Embedding表，不能伪造空返回。其他包完成新初析后可再次收集，已形成的三查询和随机16池保持不变，仅补后来实际终选的新卡。

每题比较原题、初析、合并三查询的向量Top24与词面Top8并集，加固定种子20261017抽取的16张合法未返回卡，题卡去重。初始最多63952对；后来真实首次终选不在池内的合法卡额外入池并单列数量。修复轮不增加独立主评价样本。候选记录及私有ID映射保留在E盘`FR/records`和`private_pair_mapping.json`。

`blind_pairs.json`及人工CSV只含匿名pair_id、公开题目和经验正文，不含方法、Q、排名、任务/卡片ID或历史成绩。旧914个AI标签必须公开题目、卡片完整正文和标签定义完全相同时才复用；人工标签不继承AI身份。人工CSV的确认字段保持空白，既有CSV不覆盖。

`blind_annotation_jobs.json`准备未标注对的一次性模型任务及当前任务量预算；不能把准备数记成AI已标数。上述`prepare.py`四命令保持零API，付费层为独立的`execute.py`。人审未完成时四指标仅有模型辅助估计；全库召回率始终未测。

## 受控执行与恢复

```powershell
& 'translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_weekly_retrieval_20261027.execute prepare
& 'translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_weekly_retrieval_20261027.execute check
& 'translation_work/temp/cle_memory_q_env/Scripts/python.exe' -B -X utf8 -m configs.cle_weekly_retrieval_20261027.execute launch
```

`prepare/check`不发请求；`launch`在禁用时段、4worker冻结评价活跃或未决HTTP未核清时只写队列，不启动新进程。实际运行单worker并在每个请求边界复查时段与全局容量，沿用`StudyExecution`的journal/wire、累计物理次数、Token预留与未知用量。恢复使用同模块`resume`，已有segment时`run`拒绝重复启动；先复用已完成标签和完整响应，即使响应之后标签未落盘也不能重买。未决/失败HTTP须先核清，不能自动重发。

仅用原生`EmbeddingClient`在本包新缓存补实际缺项，旧SQLite只读；先清点全部合法卡与已有三查询，再按原32条/8万字符批量处理，避免逐卡小循环。初析只复用公开契约精确相同的已保存结果，缺初析等待其他已登记包，不生成代码或新买初析。跨模型包未来只消费其`inputs/protocol.json`的`bank_sources`明确登记且正文与1939旧库完全一致的行，新C41正文不混入旧库标注。

冻结预算为：初始池最多63952对，首次实际终选额外最多43869对，总AI对最多107821（仍低于全合法571×1939上界）。额外上界来自grow的3轮学习/10格回测/10格粒度和gate的8格Q/10格拆分/6格分类器/4格旧库跨模型，每格最多3卡；实际逐题去重。Embedding文本最多1939+571×3=3652。每对AI最多一次真实HTTP（`max_attempts=1`），合法完整返回的格式错误单独计数，不加格式重试；`insufficient`等待裁决。Token按实际冻结公开题面/卡片最大序列化HTTP字节加4096输出及原预算余量封顶，不使用缓存99%或旧模型价格假设；所有段累计预算不重置。精确缓存与旧914标签复用仅减少实际用量，不伪造完成次数。

执行后`export-review`导出含AI建议但人工签名字段空白的新CSV。人工编辑副本后用`import-review --labels <CSV>`导入；必须覆盖当前精确池、逐对有依据、姓名与确认时间，`insufficient`须先裁决，Agent不代签。`metrics`调用原候选池四指标函数，对真实原生首次终选逐条件/重复统计，不用数值Top3冒充原LLM选卡，三查询召回另列诊断。`replay`仅复算完整已保存AI响应、向量缓存和候选池，无网络；真实付费准备与候选收集未完成时不能写成全571题完成。

来源：本周七项要求方案FR、`methods/cle_ablation/retrieval_q_study.py`与`methods/sct_trajectory/retrieval_hit_study.py`的原生公开白名单、匿名规则和五类标签。`tests/test_cle_weekly_retrieval.py`和`tests/test_cle_weekly_retrieval_execution.py`使用合成候选/HTTP并阻断真实网络，验证共同池、精确复用、匿名化、批量缺项、一次盲标、完整响应恢复、未决停止、时段/容量队列、人审分离、四指标和零API回放。

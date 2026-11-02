# 11月1日两批有界恢复

## 最新：切换无1017后缀的Flash继续

用户已明确授权Q回测与记忆标签剩余单元切换`deepseek-v4.1-flash`。当前唯一入口为`configs.cle_weekly_closeout_20261101.switch_flash`；后文`recover_tls`和`resume`保留为旧模型历史恢复说明，不再用于真实派发。

换模时Q已保存227/540次、标签247/820次，剩余313及573次。两份`model_switch_flash_20261101/manifest.json`固定完成集合、旧段、原输入身份、累计预算和新旧模型设置。原协议文件、源代码、旧journal与失败状态保持原位；新段`protocol.json`显式保存本次模型覆盖和授权入口，源卡库、Q快照、题面、分组顺序、重复、三卡上限、一次修复和验证器全部复用。

```powershell
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.switch_flash audit --kind q
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.switch_flash probe --kind q
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.switch_flash launch --kind q
```

标签换为`--kind gr`。每批2worker、总4；工作日原禁用时段同样约束无1017模型的每次物理请求。连接继续使用原org接入点、代理及校验证书和主机名的TLS1.2。旧成功响应仅在原提示和原调用顺序准确对应时复用，返回模型字段保持1017；新请求与新成功响应均记录无1017模型，控制测试响应不填回正式实验。Q227次和标签247次原生零API验证通过，准确抵达原3条未完成请求的新模型派发边界。

每行增加`model_cohort`和实际响应来源：`1017_only`为旧模型完整结果，`flash_only`为新模型完整生成结果，`mixed_saved_prefix`为复用旧成功前缀后接续。总完成数仅表示原540/820名单的交付进度；成绩、同题配对、重复波动和费用按来源分别统计，不生成混合总Joint率。两模型覆盖不同未完成单元，模型间总体差值不用于证明换模收益。标签训练资格只使用五档两重复来源均为新模型的完整题目，原训练/开发题族划分保留，不足时明确报告资格未过，不追加付费题。

完整交付后自动执行原生零API回放，证书位于各包`model_switch_flash_20261101/replay_result.json`，随后自动分层分析到同目录`analysis/summary.json`及`analysis.md`。实际案例待阅读时仍单独登记；15分钟监控接续代码复盘。失败和未知用量累计保存，不重置原预算；每个模型及Embedding费用从真实物理账本分开计算。后续同类无响应连接/524/硬超时先审查与零API重放；有成功/部分响应、认证、额度、预算、解析或落盘故障须按原因处理。排队全量保持跳过。

向量请求中断同样使用本节`switch_flash audit/probe/launch --kind gr`，不调用旧Embedding恢复入口。`audit`按原`text-embedding-3-large`、原查询文本、时间和物理失败状态核对；逻辑记录未带diagnostics时也必须有明确的无返回TLS/连接失败证据，证书校验失败不放行。`probe`重放全部保存单元，再从已开始但未完成的单元准确命中原向量请求边界；保存成功响应或向量缓存存在时优先复用。11月1日Q批已完成540次、原生回放与13个主要差异配对实际复盘，结果见`Q.retest/model_switch_flash_20261101/analysis/agent_synthesis.md`；后续只推进标签批和其分析。

## 本次TLS接续入口

最新授权要求修复两个小批的TLS中断并每15分钟检查。使用独立入口`recover_tls`，原`resume`只保留首次16/5个结果恢复时的历史用途，后续故障不要再次运行原入口。

```powershell
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.recover_tls audit --kind q
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.recover_tls probe --kind q
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.recover_tls launch --kind q
```

标签批将`--kind q`换成`--kind gr`。实际进程存在时不重复启动；维持各2worker、总计4。新入口名称已接入工作台进程识别。

已完成的诊断：直连默认TLS两次超时；代理默认TLS一次SSLEOF、一次TLS1.3成功；代理TLS1.2两次证书与主机名校验握手通过。恢复复用原有`tls12_transport`，只锁定TLS1.2连接协商，接入点、模型、提示及所有实验规则保持原样。握手没有模型HTTP或费用。Q的73个已保存单元、标签67个已保存单元已零API原生复算一致；各自两条缺失请求边界精确命中。

每次从当前`execution_index`审查全部成功记录与失败请求；存在成功后继时直接复用。只有逻辑诊断为网络错误、对应物理请求无HTTP状态且无响应正文的连接故障，才适用本次续跑授权。认证、额度、解析、落盘、预算和已有响应需要按真实原因处理。原失败、流记录及未知用量全部保留；新段预算从所有历史物理请求累计，不重置。

真实运行完成后，同一进程自动生成完整原生回放`zero_API_replay_after_segment_NNN`；只有固定540/820次数齐全且回放通过才登记标准回放证书，并自动执行`analysis q/gr`。标准证书引用实际回放路径，数值分析和实际案例阅读分别登记。生成已齐但收尾进程退出时，同入口只完成回放/分析，不重新生成代码。

恢复证据位于各包`TLS_recovery_20261101/`及新段目录。每15分钟的既有监控`cle`已更新为仅检查这两批，发现同类连接故障可按上述审查、零API前缀与新段规则继续。完成两批及分析后暂停该监控；排队全量始终跳过。

以下为首次恢复记录。

用户明确恢复54题Q回测和82题记忆标签，完成后分析。其他排队全量保持跳过。

```powershell
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.resume probe --kind q
& translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_weekly_closeout_20261101.resume probe --kind gr
```

两份演练已通过：复用16、5个完整单元并准确抵达各4个暂停请求边界，HTTP为0。已启动的命令分别为本模块`launch --kind q`及`launch --kind gr`，每批2worker；实际进程存在时不重复启动。前端venv启动器和其子Python属于同一实例。

恢复在原运行根新增Q的segment_003和标签的segment_002。旧请求、部分流、失败与未知用量保留，原输入、源代码和预算未重置。本次恢复授权来自11月1日用户恢复两批的明确答复，不宣称暂停请求此前未执行或免费。

完成后同一进程自动原生回放，再调用`analysis q|gr`。分析使用540和820的固定分母；Q不沿用旧1416方案的273题统计。输出目录为各包`analysis_20261101/`，案例待实际阅读时保持`pending_actual_code_review`。

11月1日计划复核补充：Q唯一主要比较为K3对相似度，使用题族双侧检验p＜0.05及95%区间，五项探索另报Holm5。标签分析只在820格与原生回放齐全后自动计算训练题的选档空间、按训练题族Joint选模的资格和开发对照；仅保存候选，不发布正式分类器、不派发全量评价。功能安全统计按第一轮完整298题与第二轮未齐结果分层。FR目前仍需解决一次已派发缺失请求的“不再发送、继续未派发对”续段及盲审导出，不能直接认为原resume入口已就绪。

`analysis fs`只复算已有2433次功能安全结果，不调用模型。每批主要差异题的实际代码复盘、候选分析结果的解读和正式报告由后续分析工作完成，不伪装为已自动完成。未启动的全量、额外82题、分类器付费评价和新方向96次均不由本入口派发。

运行中遇到新故障保留现场，按其真实类型处理；本入口不把认证、额度或解析错误当作传输问题重发。时段仍由原请求边界政策控制。

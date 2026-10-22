# Q 全量测试的决策实验

> 最新决定：见[已完成的失败收口报告](../../docs/CLE_Q探索复审与失败收口报告_20261017.md)及[零API复算](../cle_q_review_closeout_20261017/README.md)。当前Q路线停止扩大投入；下面保留原新研究的条件执行说明，不能因照抄命令而视为自动重开Q实验。snapshot.py仍只报告该新研究的执行状态，WAIT_HUMAN不替代当前STOP_INCONCLUSIVE投入决定。

阅读 [实验规格](../../docs/CLE_Q全量测试决策实验规格_20261017.md)。本配置消费已完成的新公开契约研究，不新建另一套生成器或验证器，不启动全量。当前 [阶段报告](../../docs/CLE_Q全量测试决策阶段报告_20261017.md) 与后续失败报告均按原始记录填写。

## 当前入口

```powershell
$py = 'translation_work/temp/cle_memory_q_env/Scripts/python.exe'
$cfg = 'configs/cle_retrieval_q_public_contract_20261017'
# 实际人工完成CSV后才执行下面两条，不能传回空白表。
& $py -m methods.cle_ablation.retrieval_q_study import-review --config $cfg --labels '<人工完成的CSV副本>'
& $py -m methods.cle_ablation.retrieval_q_study summarize --config $cfg
# gate_B通过且selection锁定后，执行原8题开发，不另选题。
& $py -m methods.cle_ablation.retrieval_q_study run-development --config $cfg
```

Agent读取真实采用和生成代码，填写有依据的agent_code_review.json后执行report；Q/检索路线按gate_D决定是否确认。若缺代码落实审查，应先完成这项无API工作再判门，不能把“尚未审查”写成“没有落实”。

```powershell
& $py -m methods.cle_ablation.retrieval_q_study report --config $cfg
# 仅gate_D对应路线通过时运行；完成后补齐确认人工标签和代码审查再report。
& $py -m methods.cle_ablation.retrieval_q_study run-confirmation --config $cfg
```

确认前的公开契约审查、候选池标注和人工审定按原规格完成。人工缺失时不继续付费。若原入口的源码指纹检查拒绝续跑，保留原记录，不能改旧元数据绕过；为必要修复另立版本。

## 决策快照

`python configs/cle_q_full_test_decision_20261017/snapshot.py` 只读取原研究记录、现有报告和本机Docker镜像状态，写入新快照，不调用模型、不启动容器、不更新Q。它给出研究路线状态；科学门通过仍需单独完成对应全量环境资格与执行规格。

实际触发STOP_*后，按 [探索失败报告模板](探索失败报告模板.md) 完成逐题、统计和费用部分；快照不是最终失败分析的替代品。等待人工或等待确认只出阶段报告，不将未执行实验写成失败。

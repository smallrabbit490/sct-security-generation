# 公开契约补齐后的检索与 Q 研究

协议：`cle-retrieval-q-v2-public-contract`。父协议的停止记录保留，本次使用独立配置与运行目录；固定6题校准、8题开发及24题预留确认名单不变。

## 原始材料与改动

102和136的本地记录与E盘完整归档逐行相同。102公开题面描述了键名规则，但没有命名夹具提供的`valid_key_pattern`和`unquote`；136公开题面介绍了Patient，却没有给出按患者ID查询的`patients`映射。参考实现均依赖这些外部绑定。

`public_contract_overrides.json`仅在内存中追加这两题的`task_description.context`，不改写原始data.json、ground_truth、unittest或其他公开字段。102补充校验器、解码函数的名称/类型和外部提供约定；136补充患者映射的名称/类型和外部记录归属。未复制正则字面值、患者ID/姓名、具体测试样例、期望输出或修复代码。逐项来源见`public_contract_audit.json`。

## 执行命令

在仓库根目录使用现有解释器。每次都传本配置，否则入口默认仍指向历史协议。

```powershell
$py = 'translation_work/temp/cle_memory_q_env/Scripts/python.exe'
$cfg = 'configs/cle_retrieval_q_public_contract_20261017'
& $py -m methods.cle_ablation.retrieval_q_study inventory --config $cfg
& $py -m methods.cle_ablation.retrieval_q_study prepare --config $cfg
& $py -u -m methods.cle_ablation.retrieval_q_study retrieve --config $cfg
& $py -u -m methods.cle_ablation.retrieval_q_study export-review --config $cfg
& $py -m methods.cle_ablation.retrieval_q_study summarize --config $cfg
& $py -m methods.cle_ablation.retrieval_q_study report --config $cfg
```

运行目录为`translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2/`。prepare不能重复覆盖，技术失败不重试。以上步骤只推进到AI初标与人工复核材料；人工未完成时不产生正式金标准指标，不锁定R*，不启动P7或预留确认。

## 人工复核

阅读运行目录下的`人工复核说明.md`，使用`human_review.csv`副本，填写`human_label`、`task_evidence`、`card_evidence`、`reason`、`reviewer`、`confirmed_at`。人类必须自行确认；Agent不自动补人名、日期或结论。

完成后导入：

```powershell
& $py -m methods.cle_ablation.retrieval_q_study import-review --config $cfg --labels '<人工完成的CSV副本>'
& $py -m methods.cle_ablation.retrieval_q_study summarize --config $cfg
```

现有经验卡、Q及门槛不变。当前零API参考预检只覆盖有限契约一致性，不能证明整个数据集无其他缺陷。八道开发题集中在字段更新、HTML和权限题型，不代表全部CWE。新协议的后续成绩须与旧协议分开报告。

# CLE 检索质量与冻结 Q 联合实验

本配置对应 `cle-retrieval-q-v1`。只推进旧 CLE；沿用原 P7 生成、采用、原生验证和交付规则。执行报告见 `docs/CLE检索与Q联合探索执行报告_20261017.md`，详细规格见 `docs/CLE检索与Q联合探索实验规格_20261017.md`。

## 入口与顺序

使用现有解释器，不安装新依赖：

```powershell
$py = 'translation_work/temp/cle_memory_q_env/Scripts/python.exe'
& $py -m methods.cle_ablation.retrieval_q_study inventory
& $py -m methods.cle_ablation.retrieval_q_study prepare
# prepare 未通过会以2退出；停止，不运行后续API步骤。
& $py -m methods.cle_ablation.retrieval_q_study retrieve
& $py -m methods.cle_ablation.retrieval_q_study export-review
# 人工编辑复核文件副本；不得由Agent填写人工确认身份或日期。
& $py -m methods.cle_ablation.retrieval_q_study import-review --labels '<人工完成的CSV路径>'
& $py -m methods.cle_ablation.retrieval_q_study summarize
& $py -m methods.cle_ablation.retrieval_q_study run-development
# Agent核对实际代码，保存agent_code_review.json，再重新计算开发门。
& $py -m methods.cle_ablation.retrieval_q_study run-confirmation
& $py -m methods.cle_ablation.retrieval_q_study export-review
# 确认集标注表自动另建human_review_confirmation.csv，保留先前人工标签。
& $py -m methods.cle_ablation.retrieval_q_study import-review --labels '<全部确认完成的CSV路径>'
& $py -m methods.cle_ablation.retrieval_q_study report
```

这些是逐阶段操作，不是可以跳过结果判断的一键命令。任意命令报错、门槛未通过或要求人工确认时停止该路径。即使资格门未过，也可以运行 `report` 输出阶段结论。默认输出：`translation_work/diagnostics/20261017/cle_retrieval_q/v2/`。

## 本次实际状态

6道固定校准题为1394、102、136、1289、1298、1304。102需要未公开的valid_key_pattern，136需要未公开的patients；均为参考测试通过但公开契约不足。资格门失败，新增API为0，未建候选池或发起人工复核。名单未替换，未添加答案或夹具信息到题面。

8道候选开发题为1006、1017、1061、1065、1066、1067、1070、792；全部参考F/S通过并经有限契约审查，但集中于CWE-915、79、862，不能声称代表18个CWE。筛选未依据Q或新模型成绩。逐题原因在contract_review.json与manifest.json；未审清的题不称为已证明错误。

工程实现过程的预检记录保留在父目录及v1；最终代码身份与当前预检记录在v2。版本调整仅涉及编排实现，固定名单未改，也没有付费模型结果。修复数据或协议后须新建输出目录，不能通过删记录、改散列或换题伪装原实验续跑。可以使用 `--out translation_work/diagnostics/<日期>/<新版本>`。

## 人工与Agent复核文件

- human_review.csv：人工填human_label、task_evidence、card_evidence、reason、reviewer、confirmed_at；insufficient必须裁决后导入。AI标签不自动升级为人工标签。
- agent_code_review.json：Agent在8题开发实际完成后逐题读取生成代码，给出 `[ {"task_id":"...", "card_implemented":true, "evidence":"具体代码和卡片建议对应证据", "reviewer":"执行Agent"} ]`。只填写确实检查的题，不能从采用ID推断。
- confirmation_code_review.json：确认阶段同格式；冻结方案不因复核结果改动。

当前协议不修改卡片正文/状态或Q，不做D_grow新学习、完整CLE、Base/Plus、新版站点或MASE。凭据由项目加载器消费，不在本配置内；实际货币费用未知时只报调用/Token。

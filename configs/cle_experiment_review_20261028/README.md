# 未启动实验的前缀探针安排

依据本次审查，主计划为[执行清单v05](../../docs/research/CLE-TODO-20261022-20261028-v05.md)。已完成及正在运行的任务不改；只修订尚未启动的实验。`protocol.json`和E盘`design_review_20261028/probe_manifest.json`记录具体题号、检查点与原总量。

每个未启动run节点的`prefix_probe`给出真实前缀要求，工作台发送给Codex CLI的任务包会包含完整规格。前缀是本实验的正式单元，不是额外实验。所有前缀目前均为“待执行”，本次审查没有派发模型或Embedding请求。

执行节点先检查本包现有入口能否有界运行前缀。若尚无该能力，先在独立配置目录补齐分段派发、真实检查报告和续跑接线并做封网验证；不要直接启动全量后事后宣布探针通过。父任务的`commands`仍是原生运行入口线索，须先落实`prefix_probe.dispatch_policy`再调用。

具体顺序如下：

1. 使用冻结题号，只派发前缀对应的原条件及原重复。条件随机顺序保留，首次初析与候选只在同题同重复内共享。
2. 将完整轨迹写入本包正式输出链，原生完成计数保持部分完成；不要改成全量完成。检查共享边界、真实干预、验证反馈、冻结资产与记账。完整记录的原生模型失败同样可通过技术门，不要求代码通过测试或Joint为1。
3. 写`design_review_20261028/probes/<实验ID>/summary.json`，附任务/逻辑格编号、真实产物位置、技术检查、成本和继续决定。没有运行的探针不能写passed。
4. 技术检查通过后，复用这些完整单元，从剩余清单继续。低Joint、正常代码错误或抽样未显示提分，均继续原主比较。技术错误只修接线并从保存响应恢复。
5. 费用包含在原累计预算中，不重置、不扩容。对于C10，72格前缀中48格来自FFS的精确复用，最多新生成24格；原1788逻辑格总量不变。

探针中的题目来自正式总体，全部仍保留在最终分析中；在看过该探针的D_gate成绩后不能调整模型、提示、阈值或分类器。若研究方法需要调整，另登记新方案，本轮前缀及后续原规则比较分开保留。

C09从空库按原题序先处理2道初始化题；通过后继续剩余301题。进入原生主动回放后，再核对其实际首2题的检索、提卡、更新与门控轨迹，然后继续原三轮；该检查不改原批量、抽样或奖励规则。没有触发的门控分支用已有封网测试核对接线，不伪造真实事件。卡片数量和模型正确率不承担这道技术门。

C11/C12等待原镜像及官方正向校准。P3代码的`FirstTwoGate`目前只挂在PLT上，因此外部两集仍须分别落实前2题。Base/Plus隐藏测试不回传，原两次前向交付末次规则不变。

零API操作：

```powershell
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_experiment_review_20261028.review preview
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_experiment_review_20261028.review install
translation_work/temp/cle_memory_q_env/Scripts/python.exe -B -X utf8 -m configs.cle_experiment_review_20261028.review instructions --experiment C10
```

首次安装把未启动C02的旧输入另存E盘后，统一使用已经参考预检273/273通过的D_grow契约v2；不改学习用题面、学习奖励或历史Q。各轮Q在同一新契约下配对，不能与原学习期Joint直接相减解释成Q收益。C02的1416格、两重复、卡库与预算不变。其他原生输入不改。

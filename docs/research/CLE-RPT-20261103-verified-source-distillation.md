# 给出正确修复后，提炼器能保住修复方向吗？

**本轮两张卡均未达到预定内容门槛，停止操作定位版提炼，不进入代码生成。** 原生组未准确指出名单覆盖；操作定位组把成功修复解释成错误，明确要求加回原有的失败赋值。按它的最小建议执行，来源题从Joint通过退化为功能通过、安全失败。

## 为什么做这次比较？

[E17](CLE-RPT-20261103-operation-distillation-replay.md)中，两种提炼都没有准确定位来源题1060的名单覆盖。本轮把[已经验证的单行修复](CLE-RPT-20261103-distillation-source-evidence.md)同时提供给两组，检查整理操作位置是否能改善提炼。来源修复由Agent完成零API诊断，两组均知道这一来源；原始CLE失败轨迹保留。

本轮固定1道来源题、1个题族、两组各提炼1次。两组共有公开题面、修复前后完整代码、差分、许可状态和三种公开配置检查；候选组仅追加这些事实的操作位置索引。输出原样保存，逐字段阅读，未人工改卡。

## 两组具体输出了什么？

|核对项|同材料原生提炼|增加操作定位|
|---|---|---|
|是否识别第1行覆盖外部名单|没有明确指出|提到了删除赋值，但解释了相反因果|
|给出的主要动作|保留名单定义、重复已有函数内成员检查|恢复模块顶层赋值|
|是否明确保留外部当前配置|缺少删除覆盖的明确操作|要求重新写入示例成员，覆盖当前配置|
|是否通过本轮内容门槛|否|否|

原生组正确描述了“允许字段更新、禁止字段不变”，但在根因中写道，仅凭差分不能确认机制；修复指令继续要求保留`PERMITTED_FIELDS`定义。它没有把函数已有的成员检查与模块顶层覆盖区分开。适用条件还加入了“策略不可变时不应增加名单检查”的无依据排除。

操作定位组的建议更具体，方向却错误。它在根因中将删除名单解释成失去权限约束，在最小补丁中直接要求重新添加：

```python
PERMITTED_FIELDS = ['price', 'description', 'stock', 'category']
```

两组收到的记录明确给出“删除前安全失败、删除后安全通过”，候选索引也明确写出只删除模块级赋值、函数体不变。因此，该卡对修复方向的解释与输入证据冲突。

## 把错误建议执行一次会怎样？

复用来源题已通过的代码，按候选卡的明确建议加回这条赋值。修改后的语法树与保存的原失败代码相同，原验证器重新确认安全退步。

|来源检查|已验证的正确修复|执行候选卡建议后|
|---|---|---|
|原生功能|通过|通过|
|原生安全|通过|失败|
|Joint|通过|失败|
|三种公开配置|3/3符合预期|0/3符合预期|

三种公开配置沿用上一阶段的相同代码与检查结果，未增加题族。这里只有来源建议的零API复核，没有新的目标代码单元，也没有测量新的跨题Joint率。原生组没有给出可唯一执行的删除修复，本轮没有替它人工补成一份正确建议。

## 对研究主线作什么决定？

本轮内容门槛为：准确定位名单覆盖，给出正确的保留配置动作，同时保留合法更新和禁止更新；0/2张卡达到。按事前规则结束本版，不再为这两张卡投入原题生成或扩大样本。

此次结果指出一个具体的提炼问题：**已验证的修复经过自然语言总结后，动作方向可能丢失或反转。** 后续若研究新的提炼方式，先检验产出建议是否与来源的真实修复一致，再测生成Joint。单纯增加操作索引在当前来源上没有解决问题；本记录作为后续设计的开发反例保留。

## 执行、预算和证据

两次实际请求均为`deepseek-v4.1-flash`，thinking disabled、temperature0、最多4096输出Token。原生组2,160 Token，定位组2,393 Token，合计4,553；未知用量0、Embedding0。两次HTTP均200，正常结束，精确回放2/2通过。全部20个卡片字段已阅读，错误建议的单点原生验证完成，活动worker归零。

预先固定正常2次请求、额外4次经核实网络恢复预留，累计Token上限63,354，实际未使用恢复预留。用户明确允许本批立即执行，例外仅作用于本批进程；其他实验时段和排队全量保持原安排。

- [冻结协议](E:/ResearchRuns/CLE/20261103_verified_source_distillation/protocol.json) · [累计用量](E:/ResearchRuns/CLE/20261103_verified_source_distillation/budget.json)。
- [原生组原样卡片](E:/ResearchRuns/CLE/20261103_verified_source_distillation/distillation/native_verified_source/card_fields.json) · [定位组原样卡片](E:/ResearchRuns/CLE/20261103_verified_source_distillation/distillation/indexed_verified_source/card_fields.json)。
- [逐字段判断](E:/ResearchRuns/CLE/20261103_verified_source_distillation/content_review.json) · [错误建议的代码和原生验证](E:/ResearchRuns/CLE/20261103_verified_source_distillation/source_advice_check.json)。
- [回放结果](E:/ResearchRuns/CLE/20261103_verified_source_distillation/replay_result.json) · [精简结果](../../results/curated/cle_verified_source_distillation_20261103.json)。
- [运行器](../../tools/cle_verified_source_distillation.py)：`python -B -X utf8 -m tools.cle_verified_source_distillation replay`只复用已存响应，不产生新请求。

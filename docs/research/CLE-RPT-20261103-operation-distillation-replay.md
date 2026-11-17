# 改进提炼方式后，两次名单覆盖损失救回了吗？

**新提炼救回1/2，同来源原生提炼救回2/2。本版新提示未优于原生提炼，结束本版生成扩大。** 4个代码单元全部保存、原生回放一致，源卡及两题四份最终代码已实际核对。本次是已知失败题的开发回放，E16原有正式成绩保持不变。

|开发题|E16旧损失：功能/安全|原生重新提炼后的最终结果|新提炼后的最终结果|新提炼是否救回|
|---|---|---|---|---|
|1069，车辆更新|通过/失败|通过/通过，首次即Joint|通过/通过，首次即Joint|是|
|1370，员工更新|失败/通过|通过/通过，用过一次修复|失败/失败，用过一次修复|否|

两种提炼器均只接收来源题1060的同一轮公开题面、代码、许可状态、分析与计划；只改变提炼程序。各提炼一张卡后原样冻结，Agent未改写模型产出的卡。每个目标只替换同一个焦点卡位，其他卡、同题第2次初析、原生P7及最多一次修复均相同，没有额外提醒或机械补丁进入正式生成。

## 1069救回时，真正落实了什么？

两组都通过原生评分，也都明确采用焦点卡。新提炼组的规划写了读取实时名单和禁止硬编码，代码却仍定义`ALLOWED_FIELDS = ["make", "model", "year"]`。原生提炼组也定义了另一份固定名单。

因此，这次1069的Joint救回记为正式观察；“保留宿主名单”这项预期动作仍未实现。固定夹具通过没有消除代码对外部权限配置的覆盖。

## 1370为什么仍失败？

新提炼组首次采用焦点卡，计划要求保留全局名单，实际代码仍把`EDITABLE_FIELDS`覆盖为两项，功能失败、安全通过。修复轮把三张卡全部拒用，拒绝理由涉及来源任务的策略名称及当前代码已经静默过滤；规划随后改成对未授权字段抛`PermissionError`，最终功能和安全均失败。

原生提炼组首次也把名单覆盖为空集。修复时猜出恰好匹配夹具的三项名单后通过评分。它同样没有实现保留外部名单，不能把这份得分通过记成名单保护已落实。

### 零API单点定位说明了什么？

复用新提炼组1370最终失败代码，保持原验证器：

|局部诊断操作|功能|安全|
|---|---|---|
|只删除名单覆盖|通过|失败|
|只恢复静默授权过滤|失败|通过|
|同时删除覆盖并恢复过滤|通过|通过|
|对首次失败代码只删除名单覆盖|通过|通过|

首次失败只需解决名单覆盖；原生修复环节又引入异常策略错误。上述4项仅用于定位，不替换正式交付代码，不计入新提炼组的Joint。

## 新提炼器本身找到了来源错误吗？

原生提炼把来源错误归为未经验证的键字符串转换假设；新提炼给出了“读取当前策略、保留未授权字段”的原则，但根因仍是笼统的未验证推测。**两种提炼都没有准确指出来源代码模块顶层的名单重绑定。** 新提炼还保留来源函数名、策略变量名及复制字典的上下文限制，没有完整达到这次设计的去特化目标。

下一项仍落在提炼环节：先核对提炼器能否从所给源码中定位具体冲突操作，再研究它产出的经验是否能提高Joint。本次不继续修改卡片重试，也不改变采用器或增加生成后补丁。

## 实际调用与材料

共22次请求、97,736 Token，未知用量0，Embedding0；两份首次初析直接复用。生成、验证和损失定位均已收尾，排队全量未启动。

- [固定设计与授权范围](CLE-PLAN-20261103-operation-grounded-distillation.md)
- [完整统计](../../results/curated/cle_operation_distillation_replay_20261103.json)
- [原生提炼卡](E:/ResearchRuns/CLE/20261103_operation_distillation_replay/distillation/native/card_fields.json) · [新提炼卡](E:/ResearchRuns/CLE/20261103_operation_distillation_replay/distillation/operation_grounded/card_fields.json)
- [1069原生代码](E:/ResearchRuns/CLE/20261103_operation_distillation_replay/cells/M4_1069_native/row.json) · [1069新提炼代码](E:/ResearchRuns/CLE/20261103_operation_distillation_replay/cells/M4_1069_operation_grounded/row.json)
- [1370原生代码](E:/ResearchRuns/CLE/20261103_operation_distillation_replay/cells/M4_1370_native/row.json) · [1370新提炼代码](E:/ResearchRuns/CLE/20261103_operation_distillation_replay/cells/M4_1370_operation_grounded/row.json)
- [局部定位的代码与原生验证](E:/ResearchRuns/CLE/20261103_operation_distillation_replay/local_checks.json)

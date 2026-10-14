# CLE 冻结阶段 Prompt 消融实验设计

## 目标

在同一份完整 CLE 冻结经验库上，测量 few-shot 示例、经验卡呈现、任务契约措辞、输出约束和角色措辞对 Python Base、Plus 与 H_pass 结果的影响。

## 固定条件

- 冻结库固定为 `translation_work/sct_runs/cle_prompt_full_20260929/frozen/m_star.jsonl`；该运行使用固定四池清单，训练仅用 D_init/D_grow/D_gate，完成 3 轮 CLE 后冻结，H_pass 300 条仅在冻结后评测。此前 C1-1 只用 D_init，不能充当完全量基线。
- 所有变体使用同一份 top-3 检索结果、同一模型、温度、超时、数据顺序和本地验证器。
- 评测阶段 `feedback_channel=disabled`，Base、Plus、H_pass 的证据不写回经验库。
- 只改变代码生成 prompt；分析、规划、检索、验证和冻结库不变。
- P00 为现有 prompt；P23/P24 是解释性对照，分别隐藏经验内容或隐藏检索卡注入。
- 现有结构消融仍在运行，因此完整 CLE 和 prompt 矩阵串行排队，单个阶段最多 16 个 API 在途请求。

## 变体

P00-P05 测试 few-shot 数量和正负示例；P06-P09 测试经验卡字段与适用性判断；P10-P13 测试功能/安全契约措辞；P14-P17 测试内部检查、适用性、输出格式和最小改动；P18-P19 测试角色措辞；P20-P22 测试组合；P23-P24 测试经验注入的解释性对照。

## 输出与统计

每个变体保存 prompt profile JSON、profile SHA-256、冻结库 SHA-256、逐任务 rows、Function/Secure/Joint、四态、生成错误、调用和 token 统计。P00 与其他变体做同 task_id 的配对比较；多重比较使用 Holm 校正。缺测保留在分母中，不能当作失败证据伪造。

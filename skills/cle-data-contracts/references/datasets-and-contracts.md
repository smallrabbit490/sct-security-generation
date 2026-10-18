# 本项目的数据文件与公开信息

路径相对已确认的 `PROJECT_ROOT`。

| 对象 | 定位 | 用途 |
|---|---|---|
| 原PLT | data/external/secodeplt/secodeplt/data.json | 原始1411条；不等于全部有可运行测试 |
| 当前PLT加载器 | methods/sct_trajectory/run_closed_loop.py::_load_tasks | 当前筛选逻辑；874是历史可测口径，使用时重新核对 |
| 题族 | data/external/secodeplt/derived_metadata/family_manifest.json及当次manifest | 推断家族；版本与任务清单一起解释 |
| 正式基准 | data/SecEvoBasePlus/Base与Plus | 按子集、语言和实际ID分母报告 |
| 其他语言夹具 | data/harnesses | 译本和夹具要一一对应；运行边界见原验证器 |
| 现Q研究清单 | configs/cle_retrieval_q_public_contract_20261017/manifest.json | 仅当前研究；不能给所有实验套303/273/298或6/8/24 |
| 原始与派生区别 | docs/experience_self_evolution_guide.md；docs/architecture_and_experiment_history.md | 旧353子集、三池和后来的四池各有用途 |

公开字段是task_description中的description、security_policy、function_name、arguments、return、raise、context及当前入口明确许可的元数据。ground_truth、unittest与来源题号不是通用检索输入。

原生参考由code_before+patched_code+code_after及原验证入口组合；不可把patched_code当待测题提示。缺少测试属于未测量。不同验证后端、依赖或公开契约产生新协议，不能覆盖旧成绩。

实际案例：102依赖外部valid_key_pattern与unquote；136依赖patients映射。已授权覆盖只声明名称、类型和外部提供关系，原data.json保留。旧1015存在公开USERS与夹具USER_DETAILS不一致，是数据缺陷案例，不是模型不会访问字典的证据。

# 训练侧多分支与全量门控 Implementation Plan

**Goal:** 实现用户已批准的方法，并用训练侧对照检验效果，不运行 Plus。
**Architecture:** 独立 branching 模块负责多方案生成与轨迹；独立 global_gate 模块负责配对对照、归因及过滤副本；现有 CleRunner 用显式模式开关接入。独立诊断 runner 负责固定源库、实验统计与续跑证据。
**Tech Stack:** Python，pytest，现有模型请求器和 PLT 本地隔离验证器。

## Task 1：多分支生成和提炼
- [x] 在 tests/test_branch_pipeline.py 先写失败测试：分支真实独立、全部测试、重复标记、无伪造 repair transition、单分支失败保留。
- [x] 新建 methods/sct_trajectory/branch_pipeline.py，复用 context_pipeline 初析/检索/复析，Planning 三种方案，各一次代码生成；提供同一方案三次采样对照。
- [x] 新建分支对比提炼入口，保留原轨迹兼容字段，但 branches 是实际全量证据；测试不能反馈给兄弟生成。
- [x] 运行 D:/ANACONDA/python.exe -m pytest tests/test_branch_pipeline.py -q。

## Task 2：全量门控
- [x] 在 tests/test_global_gate.py 先复现缺测误删、多卡连坐、组合重检索、归因波动和正负冲突。
- [x] 新建 methods/sct_trajectory/global_gate.py，输出 baseline、memory、attribution、filtered 三阶段结果；只对副本应用决策，输入库不变。
- [x] 无效执行标为 unmeasured；完整对照及去卡对照都单次生成，所有记录带注入卡片内容哈希。
- [x] 运行 D:/ANACONDA/python.exe -m pytest tests/test_global_gate.py -q。

## Task 3：闭环集成和恢复
- [x] 在 CleRunner 增加 branch_count 与 gate_mode 显式配置；新模式轮间只积累候选，末尾全量门控。
- [x] CLI、summary、轨迹、冻结和看板数据口径区分新旧方法；新模式首版拒绝不完整旧轮恢复，Phase1-only 恢复须有完整结果并校验源 manifest。
- [x] 回归原模式和新模式三轮调用顺序、冻结时机、实验边界；新训练模式单独目录。

## Task 4：实验、复核、报告
- [x] 新建 run_branch_gate_study.py：只加载 PLT、源库及三池，273题三臂、298题全量门控，保存配置/源码/源库哈希及 usage；拒绝覆盖目录。
- [x] 分层选取至少数个不同 CWE 验证真实 API→生成→代码提取→本地 F/S→归因→提炼链路，保留失败，不改入选规则追逐成功。
- [x] 全部273题和298题开发实验，禁用 Base/Plus 接续；报告配对统计与成本，禁止将训练选优当部署通过率。819/894 行完整，独立审计 21,393 项通过；多思路 88 vs 87、停用前后 68→70，均未证明提升。
- [x] 中文报告 docs/branch_global_gate_20260923.md，README 导航，注明已完成/未完成及局限。新增独立提炼复核未证明有效，保持未接入；未启动正式三轮重训或 Plus。

## 验收规则

功能成功不证明方法涨分。方法有效性必须依赖真实完整配对结果；不显著或负提升同样是合格实验结论。一次开发池结果不能证明独立泛化。源码测试与实验版本哈希可追溯。

# 冻结消费者和已观察的边界

| 请求 | 入口 | 注意 |
|---|---|---|
| 原CLE冻结有/无经验比较 | methods/sct_trajectory/run_plus_frozen_comparison.py | 当前已修订隐藏反馈边界；不能按9月旧日志推断当前行为 |
| Q冻结消费 | methods/cle_ablation/run_memory_q_frozen.py | --dataset Base/Plus；当前choices为Q0/Q1/Q2；不能宣称已支持同CWE打乱Q |
| P0–P7冻结前向消融 | methods/cle_ablation/runner.py | --dataset Base/Plus；确认当前原生预算与校准逻辑 |
| 九条baseline | methods/workflow_baselines/run_true_agent_workflows.py | 4 Prompt与5 Agent的真实入口；run_prompt_baseline.py不是正式执行器 |

当前镜像名称由原代码/配置确定。本机2026-10-17检查曾缺safecoder-python-validator:local及其父镜像porta-bench-runtime-python3:latest；执行时重新检查，不把这一历史缺失设为永久阻塞。Dockerfile有父镜像依赖，普通python镜像不能冒充原环境。

环境校准必须实际验证原参考代码。只成功请求API、找到Docker命令、离线加载1939卡或写一行rows，都不能证明生成及F/S成功。

H06历史事实：09-25本地TF-IDF冻结结果无收益；对齐semantic、完整契约、4096额度和Docker后另做重测。重测提升很小，仍不足以用开发门控成绩宣称泛化。

H07事故：Base与Plus并行启动时，Plus启动清理删除Base活跃池。即使runner有进程锁，watchdog清理仍有影响；遵守仓库现有串行要求，不自行加入替代docker run或另一套验证器。

现Q冻结入口采用两次固定预算、最终末次代码；隐藏F/S不进入后续提示、不更新Q。未来用户批准其他无隐藏反馈预算可另订协议，本技能不把“两次”推广为所有方法要求。

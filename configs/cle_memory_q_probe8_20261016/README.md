# 最新全D_grow Q库：8题同CWE打乱三臂探针

固定126、153、345、96、162、370、612、603八题，每个CWE两题、八个不同题族。使用已完成273题学习的1939卡库（297张有Q反馈），不重新学习。

Q1为纯相似度，Q2为学习Q，Q3在同CWE内以种子20261015打乱(Q, visits)配对。λ=0.5，δ=0.7613717780938312，deepseek-v3.2、thinking disabled、temperature=0、4096 tokens；调用原生`runner.run_one(P7)`。最多24次P7任务、48次生成代码验证；正向校准另有8次，模型调用为0。

在项目根目录执行`./configs/cle_memory_q_probe8_20261016/run.ps1`。使用上一轮已有的Python 3.12.14专用环境，不安装新依赖。运行区为`translation_work/diagnostics/20261016/cle_memory_q/probe8_cwe_shuffle/`，现有完整运行目录拒绝覆盖，不自动重试已完成实验。

`prepare.py`重新校准8题参考补丁，检查学习/评价题族隔离和每CWE的Q分布，生成本轮manifest和calibration副本。原学习配置及Q库保留；副本只更新已授权修改的比较编排器源码身份，其他P7生成、检索、验证源码必须与学习时相同。原生Prompt/schema行为保持，不混入额外修复。

这是一轮机制开发诊断。旧确认集保留，即使探针门槛通过也不自动训练完整CLE或运行Base/Plus。

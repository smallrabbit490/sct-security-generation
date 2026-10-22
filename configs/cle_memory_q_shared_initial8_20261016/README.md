# 共享首次初析8题三臂控制实验

协议和结果见[实验文档](../../docs/CLE_Q回放与共享初析8题实验_20261016.md)。仅旧CLE，固定最新全D_grow Q库，D_gate开发诊断；不进入确认、完整训练或Base/Plus。

已固定任务：1341、1000、1013、1055、340、777、1001、1015。按原CWE/ID轮转，对25个未评测且未预留的题族进行公开契约审查，选出8个合格题族。参考实现全部Joint通过。排除依据见`prepare.py`的DECISIONS和运行区`preflight.json`。它是明确契约的诊断子集，不代表全数据集。

运行后发现预检漏项：1015公开USERS与夹具USER_DETAILS不一致。因此上述“合格”是执行前筛选判断，不是最终确认；原8题清单保持不变，`analyze.py`单列该缺陷及事后辅助统计。脚本用于重现本批协议，不会静默替换题目。

复现使用已有`translation_work/temp/cle_memory_q_env/Scripts/python.exe`。依次：

1. `python -m methods.cle_ablation.replay_memory_q --learn translation_work/diagnostics/20261016/cle_memory_q/full_dgrow --probe translation_work/diagnostics/20261016/cle_memory_q/probe8_cwe_shuffle --out translation_work/diagnostics/20261016/cle_memory_q/shared_initial8/replay`：零API奖励回放。
2. `python configs/cle_memory_q_shared_initial8_20261016/prepare.py`：零API参考校准、分池隔离、清单与比较校准副本。
3. `configs/cle_memory_q_shared_initial8_20261016/run.ps1`：8次共享初析、24次P7、只读结果报告。运行时由既有本地凭据加载器取值；配置无密钥。

仅重新分析时，先运行`python -m methods.cle_ablation.report_memory_q_probe --root translation_work/diagnostics/20261016/cle_memory_q/shared_initial8 --out results/curated/cle_memory_q_shared_initial8_20261016`，再运行`python configs/cle_memory_q_shared_initial8_20261016/analyze.py`，均不调用API。

重跑前将`prepare.py`、`analyze.py`中的RUN和`run.ps1`的runRoot改为新的诊断目录，并同步另设结果目录。已完成compare目录拒绝覆盖。原学习calibration、Q库、旧运行记录和预留确认清单保持不变。

共享初析按原P7公开契约/提示生成一次；失败不重试，三臂共同使用降级状态。c1独立分析各臂自己的代码和反馈。共享调用/Token单列一次，不能重复计入三个臂。每题首次query和候选cosine相等由报告检查。

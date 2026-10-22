# D_init补充Q学习（实现及零API预检）

协议：`cle-q-dinit-observer-cap3-v1`。实际方案和预检结果见[中文报告](../../docs/CLE_Dinit补充Q学习方案与离线核验_20261019.md)。

**后续审阅处置：原付费方案未启动；当前Q专项已按Pro审阅与零API核验结论收尾。下列命令作为历史实现说明保留，不按新增卡数门自动扩大。现行决定见[收尾执行清单](../../docs/CLE_Q探索Pro结论与收尾执行清单_20261019.md)。**

- 当前：303题已零API参考预检，222题合格、81题排除；真实P7生成0次。
- M1：1939张卡主来源全部D_init；已有466张从D_grow获得Q。继承M1，原库保留。
- 一批原CLE P7三张轨迹，分别离线生成全反馈、跨题族反馈两份Q库；后者过滤同族和无法还原的合并来源，不增加第二套模型调用。
- 付费顺序：前2题技术门→12题覆盖门→补齐222题1轮；未过停止，不自动重试，不启动D_gate。
- `manifest.json`是已锁名单，`protocol.json`是参数与门槛；没有API密钥。

在仓库根目录执行：

```powershell
$clePython = "D:/Agent/sct-security-generation/translation_work/temp/cle_memory_q_env/Scripts/python.exe"
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_q_dinit prepare
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_q_dinit preflight
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_q_dinit report
```

以上零API命令已执行。下面的付费命令本轮未执行：

```powershell
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_q_dinit probe
& $clePython -B -X utf8 -m methods.cle_ablation.run_memory_q_dinit learn
```

产物：`translation_work/diagnostics/20261019/cle_memory_q/dinit_learning_v1/`；小型来源与资格表、summary位于`results/curated/cle_memory_q_dinit_20261019/`。有过技术失败或源码输入变化时原协议拒绝续跑，先另建修订协议，不能覆盖失败记录。

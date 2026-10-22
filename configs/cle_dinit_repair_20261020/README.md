# D_init原排除81题的独立修复与零API预检

本轮已完成：恢复74题资格，保留7题排除；原始数据、旧资格和Q库未覆盖。
最终回执为`translation_work/diagnostics/20261020/cle_dinit_repair_v1/commands_v2/`。
本目录完整任务含参考和测试，只供验证；模型输入仅使用`public_task_descriptions.json`中的公开字段。

从仓库根目录执行：

```powershell
$clePython = '.\translation_work\temp\cle_memory_q_env\Scripts\python.exe'
& $clePython -B -X utf8 configs/cle_dinit_repair_20261020/repair_and_preflight.py prepare
& $clePython -B -X utf8 configs/cle_dinit_repair_20261020/repair_and_preflight.py preflight --version native_v1 --workers 4
& $clePython -B -X utf8 configs/cle_dinit_repair_20261020/repair_and_preflight.py preflight --version commands_v2 --command-path 'C:\Program Files\Git\usr\bin' --workers 4
& $clePython -B -X utf8 configs/cle_dinit_repair_20261020/finalize.py
```

以上是本轮实际执行顺序。已有prepare及两个验证版本不会被覆盖；复查已有结果直接读取回执，再执行finalize即可。需要重检时，使用新的`--version`，不能重用native_v1/commands_v2。

命令路径只在该进程生效，没有改全局系统配置；未安装依赖、未调用模型、未更新Q。参考和原漏洞实现都调用原`validate_and_state`，本地python -I、20秒上限。负对照沿用原生漏洞代码；不修改期望输出。

逐题修订与未解决原因见`results/curated/cle_dinit_repair_20261020/`。完整报告见`docs/CLE_Dinit81题修复与重新预检报告_20261020.md`。
更新的学习设计在`configs/cle_dinit_q_coverage_design_20261020_v3/`；尚未实现新学习CLI，勿直接执行旧D_init入口。

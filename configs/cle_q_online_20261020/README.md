# Q参与式D_init→D_grow→冻结D_gate

协议：[中文实验说明](../../docs/CLE_Q参与式两阶段学习与全Dgate四臂协议_20261020.md)。

```powershell
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 -m methods.cle_ablation.run_memory_q_online prepare
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 -m methods.cle_ablation.run_memory_q_online D_init --limit 2
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 -m methods.cle_ablation.run_memory_q_online all
```

学习逐题串行；下一题读取上一题更新后的Q。两次训练结束后才冻结评测，D_gate从不写Q。正确率不作为继续门。旧Q0/Q1在依赖和输入核验通过后各复用298条，新跑Q2/Q3共596条。

2026-10-21恢复：原进程在128题后退出，00866请求未保存响应，原记录不改。已保存128题及Q检查点完整复用，仅重新执行未形成题级记录的1245。恢复入口改为`python -u -B -X utf8 -m configs.cle_q_online_20261020.resume_after_exit`，由独立隐藏进程执行；当前进程和日志路径见运行区`detached_process_20261021.json`。已有进程存活时不要重复启动。

三阶段完成后自动生成[强化效果分析](../../docs/CLE_Q强化学习与全Dgate四臂效果分析_20261021.md)，包含Joint、覆盖、声明采用、配对统计和实际已知成本。`python -B -X utf8 -m configs.cle_q_online_20261020.summarize_final --partial`可零API刷新进度；不加`--partial`会要求两次学习及1192条四臂记录完整。

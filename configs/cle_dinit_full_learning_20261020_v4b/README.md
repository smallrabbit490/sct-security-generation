# D_init全303题Q学习：v4b技术续跑

源规格见[原v4](../cle_dinit_full_learning_20261020/README.md)。本次只修复已观测的60秒API网络超时，客户端等待改为120秒，模型、验证器、原P7三张卡/最多一次修复、奖励、名单和覆盖掩码均不变。

- 保留原v4的全部232条记录及请求总账。
- 复用230条完成记录；仅重跑API超时题878和连带中断修复的485，然后执行剩余71题。模型输出截断题836不重跑。
- 当前主表仍为303个唯一任务的一轮执行；2条技术中断记录另外保留，不作为另一轮学习，也不重复授信。
- 总账接续原1773次请求，包含1次未返回用量的超时错误；原2000万LLM Token/3000逻辑请求及100万Embedding Token边界累计计算，不清零。
- 原始7题的历史复用属性保持不变；完整主表中的新P7为296次，另有2次技术中断执行，实际新P7调用298次。新版本不运行D_gate。

```powershell
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 configs/cle_dinit_full_learning_20261020/continue_after_timeout.py run
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 configs/cle_dinit_full_learning_20261020/continue_after_timeout.py report
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 configs/cle_dinit_full_learning_20261020/finalize.py
```

`finalize`仅在303题完成后生成最终报告。运行状态以`translation_work/diagnostics/20261020/cle_dinit_full_learning_v4b/run_metadata.json`为准。主产物位于该目录及`results/curated/cle_dinit_full_learning_20261020_v4b/`；原v4输出只读保留。

## 完成结果

303/303题已完成并冻结。全反馈669/1939卡有Q（新增233），严格跨题族增量版584/1939（新增148）；765/430次有效更新。累计2321次LLM逻辑请求、19,519,383个已返回Token，保留1次已恢复网络超时，未跑D_gate。见[最终执行报告](../../docs/CLE_Dinit全303题Q学习执行报告_20261020.md)。

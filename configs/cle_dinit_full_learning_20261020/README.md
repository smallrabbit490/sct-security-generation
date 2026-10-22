# D_init 全303题Q学习 v4

本轮按用户最新要求取消Joint、正确率和新增覆盖量的继续门槛，完成D_init一轮全量学习。只执行L1覆盖路线：未学习卡优先呈现，再由原CLE模型最多选三张；Q数值不参与解题，只有实际采用卡获得原奖励。原经验正文不变。

- 名单：原303道D_init，先前296题顺序不变，追加修复的7题。12、60、303是存档检查点，不是收益门槛。
- 修订：7道剩余题，以及上轮观察到的5处公开契约缺口。原始题目、原测试、旧结果均保留；参考代码和测试变化见`repair_summary.json`及运行区`repair/changes.json`。这是新数据契约版本。
- 复用：上轮L1中7道完全未变的题，原起点、覆盖掩码、任务对象均一致，保留失败记录；其余296道新执行，不因成绩换题或重跑。
- 执行：原`run_one(P7)`，deepseek-v3.2、thinking disabled、temperature=0、4096 Token，Embedding沿用text-embedding-3-large，delta=-1、alpha=0.3。三张卡、最多一次修复、首次Joint早停、末次代码交付。
- 覆盖掩码：首12题、后48题、余243题分别固定；各检查点更新掩码，Q值本身不进入前向。冻结全反馈与严格跨题族两种库，继承436张已学习卡，不把参考预检成绩授信。
- 规模：最多303个P7执行记录（含复用7个）、606次代码尝试；保留原2000万LLM Token/3000逻辑请求及100万Embedding Token停止线，四个并发，前2道新任务先核对技术链路。API/资金预算和真实运行故障仍停止，不以模型低分停止。
- 限制：5道原题的安全测试对原始不安全实现不具区分力（75、77、78、79、80）；保留原生训练反馈并单列此事实，不宣称全部安全测试具备辨别能力。1260、81的负例超时属于预期拒绝证据，不把其功能测试补记为通过。
- 本轮不运行D_gate、Base/Plus，不新建卡片，不追加第二轮。

```powershell
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 configs/cle_dinit_full_learning_20261020/repair.py
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 methods/cle_ablation/run_memory_q_dinit_full.py prepare
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 methods/cle_ablation/run_memory_q_dinit_full.py run
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 methods/cle_ablation/run_memory_q_dinit_full.py report
```

运行区：`translation_work/diagnostics/20261020/cle_dinit_full_learning_v4/`。精简结果：`results/curated/cle_dinit_full_learning_20261020/`。学习结果只表示获得反馈，不证明Q提高生成正确率。

## 已观测网络超时后的续跑

v4在232条记录时发生878题60秒网络超时，保护性停止连带中断485题修复。原件完整保留。独立[v4b续跑规格](../cle_dinit_full_learning_20261020_v4b/README.md)复用230条完成记录，补跑受中断2题及未执行71题；API超时改为120秒，覆盖掩码、P7、模型和累计预算不变。836题输出截断属于模型结果，保留且不重跑。

```powershell
.\translation_work\temp\cle_memory_q_env\Scripts\python.exe -B -X utf8 configs/cle_dinit_full_learning_20261020/continue_after_timeout.py run
```

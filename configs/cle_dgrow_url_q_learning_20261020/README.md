# 修订32题补充Q学习与历史D_gate排序回放

用户已授权执行32道修订D_grow题的一轮Q学习及历史选卡影响分析。协议`cle-repaired32-observer-cap3-screened-Q-v1`，32题已完成：测试Joint24/32，Joint且末次流程完整22/32，45次有效卡奖励，新增20张有反馈卡；学习起点416张→436张（22.49%）。历史首次查询回放54/298题改呈现、33题改数值前三；未重跑D_gate选卡或代码生成。

从资格屏蔽派生库1939卡/416张有反馈卡开始。原P7、原候选顺序、每次最多三张卡；Q只观察，不参与这32题选卡。首次Joint早停，否则最多修复一次。仅完整流程、非空代码、完整F/S测量下实际采用的卡，按每次尝试Joint +1/否则 -1、alpha=0.3更新。按数字题ID、c0/c1顺序归并奖励，批末重建与在线观察赋值等价；不改变正文、状态或生命周期，不追补旧无效奖励。

真实生成使用deepseek-v3.2、thinking disabled、temperature=0、max_tokens=4096，原选择器256，text-embedding-3-large，delta=-1、lambda=0.5、workers=2。最多32次P7/64份代码；逻辑LLM请求停止阈值400、已报告Token停止阈值400万，原网络重试另外披露。缺usage不当作0费用，不使用旧静态价格推断实付。

```powershell
$clePython = 'D:/Agent/sct-security-generation/translation_work/temp/cle_memory_q_env/Scripts/python.exe'
# prepare只执行一次，不覆盖现有运行；当前已经prepare。
& $clePython -B -X utf8 configs/cle_dgrow_url_q_learning_20261020/run.py run --probe
& $clePython -B -X utf8 configs/cle_dgrow_url_q_learning_20261020/run.py run
& $clePython -B -X utf8 configs/cle_dgrow_url_q_learning_20261020/run.py replay
& $clePython -B -X utf8 configs/cle_dgrow_url_q_learning_20261020/report.py
```

run跳过已落盘的task_id；learn每次从不变起点按顺序重建，不重复授信。两道探针计入32题。模型格式失败保留并不授信；认证、额度和预算问题停止发起后续调用。不得为了完成32条授信而忽略流程或测量失败。

原件：`translation_work/diagnostics/20261020/cle_dgrow_url_q_learning_v1/`；精简结果：`results/curated/cle_dgrow_url_q_learning_20261020/`。旧库、旧代码、旧资格表与旧D_gate成绩保持原样。

replay只读原全D_gate Q2的候选、余弦和实际选择/采用ID，先复现原M1排序，再分离资格屏蔽与新增32题学习的增量。首次298题是主分析，历史修复查询仅诊断。只报告排序、数值前三及历史选入/采用卡Q的影响，新的实际选卡/采用/代码/Joint全部为未测量。未调用D_gate模型，不做新D_gate验证，不把旧成绩分配给新Q。

中文结果：[32题补充Q学习与历史影响](../../docs/CLE_修订32题补充Q学习与Dgate历史影响_20261020.md)。本轮205次LLM逻辑调用、1951092 Token；Embedding41次、59699 Token；实付未知。

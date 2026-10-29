# 原CLE冷启动两题探针

由当前对话监督，固定原生source顺序前两题45、46。原队列曾以manifest列表前两题798、799标记；封网运行发现原生遍历顺序不同，三池集合完全相同，已在派发前修正标签，原失败检查保留。所有任务顺序和三池归属均沿用原生入口。

`python -B -X utf8 -m configs.cle_build_probe_20261029.run check`封网到达phase1边界，核对空经验池、真实前两题和零HTTP。`run`仅将phase1_seed的任务参数截为前两题，沿原解题、一次修复和提卡流程；完成后保存原生结果、经验池及错题本并退出，不进入phase2或门控，不把临时卡库用于三库比较。

输出：`E:/ResearchRuns/CLE/20261027_full_requirements/probe_relay_20261028/BUILD.run/`。预算固定600000保守Token、160物理HTTP（其中Embedding最多64），累计不重置。活动进程和精确命令写在launch.json。原生启动日志仍描述完整三池和303题source输入，真正执行边界由bounded_entry.py限制为2题，不将加载量当作已执行量。

当前已实际启动；完成后必须复算原生两题、卡片来源、请求与验证事件，并执行零API回放后才能称技术探针通过。源码、逻辑journal、物理wire、失败和未知用量保留；存在prepared请求时不重复启动，不直接重发。

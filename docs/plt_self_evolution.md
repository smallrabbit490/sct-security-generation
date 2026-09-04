# PLT 小样本自进化实验

运行入口：`python methods/sct_agent/run_plt_self_evolution.py --model deepseek-v4-flash`

默认从 SeCodePLT 的 1,411 条记录中选择 96 条可用漏洞/补丁对，按 Seed Family 分成 `D_init/D_grow/D_gate = 32/32/32`。结果写入 `translation_work/sct_runs/plt_python_96_<时间>/`，逐任务文件均为 JSONL。

训练侧先由 `D_init` 形成 `M0`，再由 `D_grow` 失败反思产生候选经验，最后在独立 `D_gate` 验证后晋升到冻结库 `M*`。Base/Plus 只在冻结后运行，结果不会回写经验库。

PLT 数据本身没有 CodeSecEval harness，因此训练侧采用语法解析和危险 API 静态检查；CodeSecEval Base/Plus 使用仓库 Python validator（Docker 后端）。如果 API 不可用，可使用 `--offline` 生成结构与基准参考结果，但该模式的 Base/Plus 标记为未执行，不能作为论文得分。

实验结束后可删除 `translation_work/temp/`、原始 API 响应和 Docker 缓存；必须保留 manifest、所有 JSONL、汇总、冻结元数据和报告。

# 全D_grow固定库Q学习

用户授权：固定原1939卡，在恢复三池的全部273条D_grow任务上运行原P7，仅更新实际采用卡Q。本轮有217个family、18类CWE，包含同family的不同题，不按family删题。

模型deepseek-v3.2，thinking=disabled，max_tokens=4096，embedding=text-embedding-3-large，α=0.3，Q初始0。原P7仍使用semantic_llm选卡，Q不参与本轮生成。8线程只负责只读M0的生成；Q按manifest顺序、c0/c1顺序串行回放，避免完成顺序改变EMA。

273题均进行原P7流程。先进行零API参考校准：231题参考Joint通过，35题含占位符，最终230题允许奖励、43题只记录不奖励。技术缺测和流程错误同样不奖惩；未采用卡不更新。经验正文、生命周期、数据和原三池不变。

从项目根目录使用项目依赖环境执行：

```powershell
python -m methods.cle_ablation.run_memory_q_full --stage preflight --out translation_work/diagnostics/20261016/cle_memory_q/full_dgrow --manifest configs/cle_memory_q_full_dgrow_20261016/manifest.json --workers 8
python -m methods.cle_ablation.run_memory_q_full --stage learn --out translation_work/diagnostics/20261016/cle_memory_q/full_dgrow --manifest configs/cle_memory_q_full_dgrow_20261016/manifest.json --workers 8
```

preflight拒绝覆盖已有目录；learn从已落盘rows续接尚未完成任务，并核对输入及源码身份。每题结果立即flush；每8题重建有序Q检查点、事件、原生统计和成本。已有失败行保留，不自动重新付费运行。运行完成才写最终frozen库。重复learn不会重跑已落盘题。

仅重算已有记录：将learn改为report，不调用模型。正文/状态保持原样，结果不是D_gate或Base/Plus评价，也不是完整CLE经验增长训练。记录与结果见[全量学习报告](../../docs/CLE_全Dgrow固定库Q学习记录_20261016.md)。

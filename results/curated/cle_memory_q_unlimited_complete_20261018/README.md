# 不限三张Q完整执行结果

结论：690条P7记录完成；D_gate Joint相似度17/48、学习Q21/48、打乱Q20/48。学习Q尚无显著收益证据，原技术质量门未通过，按用户授权完整执行。

- [中文结果报告](../../../docs/CLE_不限三张Q完整执行结果_20261018.md)
- `analysis.json` / `verification.json`：配对统计、Q覆盖、实现边界与记录核对。
- `diagnostics.json`：覆盖漏斗、选卡/采用数量、错误分类、已知用量与未知中断用量。
- `scores.csv`：全部690条末次代码的原生成绩。
- `training_fit_pairs.csv`、`Q2_vs_Q1_pairs.csv`、`Q2_vs_Q3_pairs.csv`：同题配对；缺测不当作已知失败。
- `adoption_by_attempt.csv`、`gate_mechanisms.csv`：逐次选入/声明采用与首次共同查询的排序变化。
- `card_q.csv`：全部1939张卡最终Q、访问次数与反馈题族数。
- `case_reviews.json`：5题三臂的Agent代码抽查，附公开契约、卡片和生成证据；不是人工金标准。
- `summary.json`、`run_metadata.json`、`mechanisms.jsonl`：原生产物的精简导出。

原始运行区位于仓库本地 `translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2/`；未复制整个项目压缩包。复算命令见中文报告。

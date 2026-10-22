# 48题D_gate补充原CLE不限三张Q0

新增48/48，复用原三臂144条，合计192条；Q0/Q1/Q2/Q3 Joint为18/48、17/48、21/48、20/48。
本研究各组均为LLM不限三张选卡，区别为候选呈现顺序；不混入8题直接选K研究。
完整报告：../../../docs/CLE_不限三张Q_Dgate补充Q0对照结果_20261019.md。

summary.json保存四组得分、统计和新旧成本；scores.csv为192条得分；task_pairs.csv为48题横向表；attempts.csv为所有代码尝试；paired_mechanisms.csv为相对Q0的改选、采用及得分变化；diagnostics.json保存原生错误；case_reviews.json为Agent逐题审阅；verification.json及decision.json保存核验和范围。

原始大文件只读引用，新Q0保存在translation_work/diagnostics/20261019/cle_memory_q/unlimited_gate_q0_v1/。未重训Q、未重跑273观察/回测、未启动Base/Plus。

# 不限三张的 Q 观察与参与实验

协议见 [中文说明](../../docs/CLE_不限三张Q观察与参与实验_20261018.md)。旧实验不覆盖。

`protocol.json` 固定模型、预算、Q 更新与候选排序；`manifest.json` 由零 API 预检在新成绩产生前固定全 273 题、两题探针与 48 题 D_gate 清单。`public_contract_overrides.json` 复用已经核实的 102/136 公开依赖补齐，不修改原始数据、答案或测试。

从项目根目录使用现有实验 Python：

```powershell
python -m methods.cle_ablation.run_memory_q_unlimited --stage prepare
python configs/cle_memory_q_unlimited_20261018/revise_gate_preflight.py
python -m methods.cle_ablation.run_memory_q_unlimited --stage probe --workers 2
python -m methods.cle_ablation.run_memory_q_unlimited --stage all --workers 8
```

`all` 只在探针门通过时继续，复用探针原生行，不重跑已保存的题。顺序为观察学习、冻结 Q 同题回测、48 题三臂；中途错误和阶段状态保留。只读重算报告：`--stage report`，不调用模型。各阶段原生记录和 Q 事件在 `translation_work/diagnostics/20261018/cle_memory_q/unlimited_v1/`。

预检第二版补入历史人工契约排除项。初版仅参考/依赖检查会误纳入已知语义冲突题；原名单另存 `manifest.initial_reference_preflight.json`，修订理由和固定名单见 `gate_preflight_revision.json`。此修订发生于正式学习/对照前，未使用新模型成绩或 Q 分数。

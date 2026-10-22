# 不按门槛停止的完整执行

[任务书](../../docs/CLE_不限三张Q完整执行任务书_20261018.md)记录用户新授权、原探针的继承和执行边界。

- `manifest.json`：固定273学习题、48个D_gate题及三臂，沿用原预检第二版；不得按新成绩调整。
- `execution_override.json`：取消推进门的用户授权及独立产物位置。质量门结果继续报告。
- `probe_gate.json`：原探针失败如实保留。
- `gate_preflight_revision.json`：只依据历史契约审查修订名单的理由。

模型与Q参数沿用 `configs/cle_memory_q_unlimited_20261018/protocol.json`；实际源代码与配置快照保存在本次运行的 `source_snapshot/`。运行完执行本目录 `analyze.py`，复核690行、Q回放、冻结边界、同查询候选与配对成绩，不调用API。

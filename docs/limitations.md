# 当前限制

- Java 和 JavaScript 的 Docker 镜像尚未固定，暂不能声称完整复现。
- C++ 和 Go 的 workflow 是面向 Python/CodeSecEval 流程的适配，不能描述为官方原语言复跑。
- 历史结果来自不同项目阶段，虽有协议标注，但不能自动横向比较。
- 仓库包含来自 benchmark 的数据，仍须遵守上游许可证和再分发要求。
- API 实验需要用户提供 key，打包仓库时不会自动运行。
## 运行时验证范围

Python 测试随数据集保存。Base/Plus 的 C++、Go Secure/Insecure harness 已放在 `data/harnesses/`。Java 和 JavaScript 仍缺少冻结的 Docker 验证器及完整复现记录，因此当前完整 Docker 结论只覆盖 Python、C++、Go。

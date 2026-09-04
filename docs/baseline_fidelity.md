# Baseline 忠实性说明

仓库将四条直接 Prompt baseline 与五条多阶段 Agent baseline 分开。

## 直接 Prompt baseline

Greedy、Greedy + Secure Prompt、Chain-of-Thought 和 CoT + Secure Prompt 各使用一次模型请求，区别仅在提示词内容，不属于复杂 Agent 系统。

## 多阶段 Agent baseline

| 方法 | 工作流证据 | 适配说明 |
|---|---|---|
| AutoSafeCoder | 静态审查、模糊/变异测试、修复 | 目标语言验证器适配 |
| AgentCoder | 编程器、测试设计、自测选择、多轮 epoch | 目标语言验证器适配 |
| RA-Gen | 规划器、搜索器、代码生成器、提取器 | 函数级复现 |
| SWE-Agent | 编辑/轨迹、测试执行、修复循环 | 从仓库修复流程适配 |
| SecAwareCoder | 安全分析、测试生成、执行、修复图 | 目标语言验证器适配 |

旧统一矩阵曾用只发一个 prompt 的适配器冒充这些方法；本仓库不将其计为 Agent workflow。保留的历史结果必须标记为 `agent_inspired_prompt_adapter`。

## 评测和结果位置

```powershell
$env:CHATANYWHERE_API_BASE = 'https://api.chatanywhere.tech/v1'
python methods/workflow_baselines/run_true_agent_workflows.py `
  --subsets Base --languages python --limit 1 `
  --model deepseek-v4-flash --max-tokens 1024 --temperature 0 `
  --retries 1 --workers 1 --only-agents
```

结果写入被忽略的 `translation_work/baseline_runs/<run-name>/<subset>/`。保留 `rows.jsonl` 以复核逐任务生成代码、脱敏阶段 trace、fidelity 和 Docker 结果；`summary.json` 与 `true_agent_workflow_report.md` 是人工阅读的汇总文件。不要提交原始长响应、key、临时容器目录或构建缓存。

对 Agent 方法，必须先检查 `workflow_completed` 和 `fidelity_passed`，再解释 `secure_func_sec`。代码质量失败是模型结果，不等于 runner 失败；API、超时、提取、缺阶段和未处理异常才是运行失败。

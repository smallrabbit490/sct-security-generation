# Baseline 忠实性说明

仓库将四条直接 Prompt baseline 与五条多阶段 workflow baseline 分开。

## 直接 Prompt baseline

Greedy、Greedy + Secure Prompt、Chain-of-Thought 和 CoT + Secure Prompt 各使用一次模型请求，区别仅在提示词内容，不属于复杂 Agent 系统。

## 多阶段 Agent baseline

源 CodeSecEval 包含更完整的工作流：

| 方法 | 工作流证据 | 注意事项 |
|---|---|---|
| AutoSafeCoder | static review, fuzz/mutation, repair | target-language harness adaptation |
| AgentCoder | programmer, test designer, self-test selection, epochs | target-language harness adaptation |
| RA-Gen | planner, searcher, codegen, extractor | function-level reproduction |
| SWE-Agent | patch/trajectory and test evaluation | adapted from repository repair |
| SecAwareCoder | security analysis, test generation, execution, repair graph | target-language harness adaptation |

旧统一矩阵曾用只发一个 prompt 的适配器冒充这些方法；本仓库不将其计为 Agent workflow。保留的历史结果会明确标记为 `agent_inspired_prompt_adapter`。

## Evaluation and Result Locations

Run the five workflow baselines with the live ChatAnywhere-compatible endpoint:

```powershell
$env:CHATANYWHERE_API_BASE = 'https://api.chatanywhere.tech/v1'
python methods/workflow_baselines/run_true_agent_workflows.py `
  --subsets Base --languages python --limit 1 `
  --model deepseek-v4-flash --max-tokens 1024 --temperature 0 `
  --retries 1 --workers 1 --only-agents
```

Results belong under the ignored directory
`translation_work/baseline_runs/<run-name>/<subset>/`. Keep `rows.jsonl` for
per-task generated code, sanitized trace, fidelity, and Docker evaluation;
`summary.json` and `true_agent_workflow_report.md` are the human-facing
summaries. Temporary Docker work directories, raw transient responses, and
build caches are disposable and must not be committed.

For an Agent baseline, inspect `workflow_completed` and `fidelity_passed`
before interpreting `secure_func_sec`. A candidate that fails Function or
Secure is still a completed model result when a terminal row exists; API,
timeout, extraction, missing-stage, and unhandled runner errors are not.

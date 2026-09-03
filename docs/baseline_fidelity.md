# Baseline Fidelity

The repository distinguishes four direct prompting baselines from five
workflow baselines.

## Direct Prompting

Greedy, Greedy + Secure Prompt, Chain-of-Thought, and CoT + Secure Prompt use a
single model request. Their difference is the prompt content. They are not
complex agent systems.

## Workflow Baselines

The source CodeSecEval package contains more complete workflows:

| Method | Workflow evidence | Caveat |
|---|---|---|
| AutoSafeCoder | static review, fuzz/mutation, repair | target-language harness adaptation |
| AgentCoder | programmer, test designer, self-test selection, epochs | target-language harness adaptation |
| RA-Gen | planner, searcher, codegen, extractor | function-level reproduction |
| SWE-Agent | patch/trajectory and test evaluation | adapted from repository repair |
| SecAwareCoder | security analysis, test generation, execution, repair graph | target-language harness adaptation |

The old unified matrix used prompt-only adapters for these names. Those are not
included as Agent workflow methods here. Historical adapter results, where
retained, are explicitly labelled `agent_inspired_prompt_adapter`.

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

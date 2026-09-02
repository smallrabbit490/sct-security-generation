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

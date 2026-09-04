# Nine-Baseline and SCT Conformance Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify all nine baselines with real API-backed smoke runs using original workflow implementations, then compare the repository's SCT implementation against the copied method specification.

**Architecture:** Treat the copied DOCX as the requirements authority, keep official/upstream baseline source trees unchanged, and store only secret-free audit evidence in the repository. API keys remain in ignored local storage; generated code is executed only through the existing Docker validators.

**Tech Stack:** Python 3.12, OpenAI-compatible ChatAnywhere API, PowerShell 7, Docker, unittest, upstream baseline CLIs, python-docx.

---

### Task 1: Establish the specification authority

**Files:**
- Create: `docs/面向多语言安全代码生成的经验自进化方法.docx`

- [x] **Step 1: Copy the source document without modification**

Run:

```powershell
Copy-Item -LiteralPath 'D:\thecourceofdasi\safecodernew\重启实验任务王老师的建议和已有论文\面向多语言安全代码生成的经验自进化方法.docx' -Destination 'docs\面向多语言安全代码生成的经验自进化方法.docx'
```

Expected: destination exists and has the same SHA-256 hash as the source.

- [x] **Step 2: Extract headings, paragraphs, lists, and tables**

Expected: the extracted requirements cover `D_init`, `D_grow`, `D_gate`, `H_pass`, frozen `CodeSecEval-X`, multi-source validation, candidate experience generation, quality/effectiveness/regression gates, and frozen final evaluation.

### Task 2: Build a fidelity manifest for the nine baselines

**Files:**
- Create: `docs/baseline_execution_audit.md`
- Inspect: `methods/prompting_baselines/`
- Inspect: `methods/workflow_baselines/`
- Inspect read-only: `D:\thecourceofdasi\safecodernew\baseline\codesecevalDatasetAndMethod\`

- [ ] **Step 1: Identify the exact nine methods**

Expected list: Greedy, Greedy + Secure Prompt, Chain-of-Thought, CoT + Secure Prompt, AutoSafeCoder, AgentCoder, RA-Gen, SWE-Agent, and SecAwareCoder.

- [ ] **Step 2: Record original source provenance and runnable entry point for each method**

Run:

```powershell
git -C <official-source-directory> remote -v
rg -n "if __name__|console_scripts|entry_points|argparse|typer|click" <official-source-directory>
```

Expected: each workflow baseline is tied to its unmodified upstream source or is explicitly marked blocked; the repository's rewritten `run_true_agent_workflows.py` is not accepted as original-source evidence.

- [ ] **Step 3: Record dependencies, dataset adapter boundary, and validation boundary**

Expected: API/provider adaptation and CodeSecEval-X task packaging are separated from workflow logic; no workflow stage is removed.

### Task 3: Verify local infrastructure and API access

**Files:**
- Inspect: `tools/check_chatanywhere_keys.ps1`
- Output (ignored): `translation_work/chatanywhere_key_check/chatanywhere_key_check.json`

- [ ] **Step 1: Run repository offline checks**

Run:

```powershell
python -m compileall src methods tools
python -m unittest discover -s tests -v
python tools/check_repository.py
```

Expected: all commands exit 0; otherwise capture the exact failure and diagnose it before baseline claims.

- [ ] **Step 2: Verify Docker and required validator images**

Run:

```powershell
docker info
docker image inspect safecoder-python-validator:local safecoder-cpp-validator:local golang:1.22
```

Expected: Docker is reachable and all three images exist.

- [ ] **Step 3: Verify ChatAnywhere with a minimal request without exposing keys**

Run:

```powershell
pwsh -NoProfile -File .\tools\check_chatanywhere_keys.ps1
```

Expected: at least one current request returns HTTP 200; the report stores key indexes only.

### Task 4: Execute real one-task smoke tests for all nine baselines

**Files:**
- Output (ignored): `translation_work/baseline_original_smoke/`
- Update: `docs/baseline_execution_audit.md`

- [ ] **Step 1: Run each direct prompting baseline with one Python task**

Use the same model, temperature, token budget, task ID, and ChatAnywhere endpoint for all four methods. Save the prompt, response metadata, extracted code, Docker command, functional result, and security result.

Expected: each method completes a real model call and reaches Docker validation; an API response alone is not a pass.

- [ ] **Step 2: Run each original workflow baseline with one Python task**

Invoke the official AutoSafeCoder, AgentCoder, RA-Gen, SWE-Agent, and SecAwareCoder entry points without replacing their workflow with prompt emulation. Provider shims may translate OpenAI-compatible configuration, but must not remove agents, tools, feedback loops, test generation, retrieval, or repair stages.

Expected: each method either reaches its original terminal state and Docker validation or is marked blocked with the exact dependency/configuration/error evidence.

- [ ] **Step 3: Audit traces for fidelity**

Expected: traces demonstrate each required original stage. A method is classified `PASS`, `FAIL`, or `BLOCKED`; no partial workflow is reported as passing.

### Task 5: Compare SCT implementation with the DOCX

**Files:**
- Create: `docs/sct_docx_gap_analysis.md`
- Inspect: `methods/sct_agent/`
- Inspect: `src/translation_pipeline/architecture_experiment.py`
- Inspect: `docs/evaluation_protocol.md`

- [ ] **Step 1: Map every DOCX requirement to code and evidence**

Expected rows cover initialization from verified vulnerable/patch pairs, structured experience representation, retrieval, multi-source validation, clustered failure reflection, same/cross-language expansion, quality gate, independent effectiveness gate, regression gate, promotion/revision/rejection, convergence, frozen generation, task-local repair, hidden-test isolation, and seed-family data isolation.

- [ ] **Step 2: Classify each requirement**

Use exactly: `implemented`, `partial`, `documentation-only`, `missing`, or `contradicted`.

- [ ] **Step 3: Cite concrete code paths and behavioral evidence**

Expected: every classification includes file/function references and, where runnable, command output; claims based only on names or comments are rejected.

### Task 6: Final verification and report

**Files:**
- Verify: `docs/baseline_execution_audit.md`
- Verify: `docs/sct_docx_gap_analysis.md`
- Verify: `docs/面向多语言安全代码生成的经验自进化方法.docx`

- [ ] **Step 1: Re-run focused offline checks after any audit-support code changes**

Run the exact tests affected plus the full repository smoke suite.

- [ ] **Step 2: Verify no secrets or generated bulk outputs are tracked**

Run:

```powershell
git status --short
git diff --check
git ls-files | rg "local_secrets|translation_work|apikey|\.env\.local"
```

Expected: the last command returns no secret/output paths and `git diff --check` exits 0.

- [ ] **Step 3: Summarize outcome without overstating blocked baselines**

Expected: report the exact count of `PASS`, `FAIL`, and `BLOCKED` baselines, then prioritize SCT gaps by experimental validity risk.

# Agent Baseline Integration and SCT Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all nine CodeSecEval comparison baselines perform real generation and evaluation, prove that the five agent methods remain multi-stage workflows, remove invalid local API credentials, and report SCT-to-DOCX differences with reproducible test evidence.

**Architecture:** Keep `run_true_agent_workflows.py` as the uniform orchestration boundary while defining a separate, testable fidelity contract derived from the extracted ZIP implementations. Route code extraction and Python evaluation through repository-owned utilities and Docker validators, keep live-run artifacts under ignored `translation_work/`, and keep SCT conformance analysis independent from baseline evaluation.

**Tech Stack:** Python 3.12, unittest, OpenAI-compatible ChatAnywhere API, PowerShell 7, Docker, Markdown, python-docx.

---

### Task 1: Safely remove invalid ChatAnywhere credentials

**Files:**
- Modify: `tools/check_chatanywhere_keys.ps1`
- Modify locally at runtime: `local_secrets/chatanywhereapi使用/apikey.txt`
- Test output (ignored): `translation_work/chatanywhere_key_check/chatanywhere_key_check.json`

- [ ] **Step 1: Add an explicit pruning switch to the checker**

Add a `param([switch]$PruneUnauthorized)` block. After all requests finish, compute the indices whose status is `ok`. When the switch is supplied, require exactly one successful key and require every other result to be HTTP 401 or 403; then atomically replace the key file with only the successful key. The script must never print or serialize key values.

- [ ] **Step 2: Run the checker without mutation**

Run: `pwsh -NoProfile -File .\tools\check_chatanywhere_keys.ps1`

Expected: six indexed results, five HTTP 401 responses and one HTTP 200 response, with no key material in stdout or JSON.

- [ ] **Step 3: Prune only the confirmed unauthorized keys**

Run: `pwsh -NoProfile -File .\tools\check_chatanywhere_keys.ps1 -PruneUnauthorized`

Expected: the local key file contains one non-empty line; the script reports only that five unauthorized entries were removed.

- [ ] **Step 4: Verify the retained credential**

Run: `pwsh -NoProfile -File .\tools\check_chatanywhere_keys.ps1`

Expected: `key_count` is 1 and the sole request returns HTTP 200.

- [ ] **Step 5: Verify credential isolation**

Run: `git check-ignore -v local_secrets/chatanywhereapi使用/apikey.txt; git ls-files | rg "local_secrets|apikey\.txt|translation_work"`

Expected: the key file is ignored and no secret or generated-output path is tracked.

### Task 2: Decouple code extraction from the missing historical harness

**Files:**
- Create: `tests/test_baseline_runtime.py`
- Modify: `methods/legacy_prompt_adapters/run_actual_5_python_methods.py`
- Modify: `methods/legacy_prompt_adapters/run_language_method_matrix.py`
- Reuse: `src/translation_pipeline/code_extract.py`

- [ ] **Step 1: Write failing extraction tests**

Add tests that import both legacy adapters with `base` unavailable, pass fenced Python/C++/Go responses, and assert that the last code block is extracted and Go receives `package main` when necessary.

- [ ] **Step 2: Confirm the regression is red**

Run: `python -m unittest tests.test_baseline_runtime.BaselineExtractionTests -v`

Expected: the Python adapter fails by dereferencing `base.harness`.

- [ ] **Step 3: Implement the minimal repository-owned fallback**

Use `translation_pipeline.code_extract.extract_code_block` whenever the historical harness is absent. Preserve the historical extraction path when it exists, and retain the existing Go package normalization.

- [ ] **Step 4: Confirm extraction tests pass**

Run: `python -m unittest tests.test_baseline_runtime.BaselineExtractionTests -v`

Expected: all extraction tests pass.

### Task 3: Route Python baseline evaluation through the current Docker validator

**Files:**
- Modify: `tests/test_baseline_runtime.py`
- Modify: `methods/legacy_prompt_adapters/run_actual_5_python_methods.py`
- Modify: `methods/legacy_prompt_adapters/run_language_method_matrix.py`
- Reuse: `src/translation_pipeline/python_validator.py`

- [ ] **Step 1: Write a failing evaluator delegation test**

Patch `translation_pipeline.python_validator.validate_python_secure` with a sentinel result, call the baseline evaluator while `base` is unavailable, and assert that the sentinel functional/security fields are converted to the established result dictionary.

- [ ] **Step 2: Confirm the evaluator test is red**

Run: `python -m unittest tests.test_baseline_runtime.BaselineEvaluationTests -v`

Expected: the current evaluator fails because it accesses `base.GREEDY_DIR` or `base.suites`.

- [ ] **Step 3: Implement secure-track Docker evaluation**

Call `validate_python_secure(task, code=code, timeout=60)` and normalize its `ok`, `details`, `stdout`, and `stderr` into `fun`, `sec`, `fun_sec`, and structured diagnostic fields. Keep an explicit historical fallback only when the current task cannot be represented by the repository validator.

- [ ] **Step 4: Pass the track through the matrix evaluator**

Change `evaluate_python(task, code)` to `evaluate_python(task, code, track)` and route secure and insecure tracks to `validate_python_secure` and `validate_python_insecure` respectively. Update the single caller in `evaluate`.

- [ ] **Step 5: Run focused and existing validation tests**

Run: `python -m unittest tests.test_baseline_runtime tests.test_validation_regressions -v`

Expected: all tests pass without changing C++ or Go evaluation behavior.

### Task 4: Define and enforce fidelity contracts for five agent workflows

**Files:**
- Create: `methods/workflow_baselines/fidelity.py`
- Create: `tests/test_agent_workflow_fidelity.py`
- Modify: `methods/workflow_baselines/run_true_agent_workflows.py`
- Inspect read-only: `D:/thecourceofdasi/safecodernew/baseline/codesecevalDatasetAndMethod/codesecevalDatasetAndMethod/{AutoSafeCoder_official,AgentCoder_official,ragen_function_level,SWE_agent_official,SecAwareCoder}`

- [ ] **Step 1: Record ZIP-derived workflow requirements**

Define one immutable contract per method containing source provenance, required stage groups, minimum model calls, whether review/repair iteration is required, and allowed adapter boundaries. Use the exact stage names already emitted by `run_true_agent_workflows.py`.

- [ ] **Step 2: Write failing fidelity tests**

For every contract, add a representative valid trace and invalid traces for an empty run and a single `direct_generate` event. Assert that agent traces reject the prompt-only cases and accept the complete workflow trace.

- [ ] **Step 3: Confirm fidelity tests are red**

Run: `python -m unittest tests.test_agent_workflow_fidelity -v`

Expected: import or assertion failures because the fidelity module is not implemented.

- [ ] **Step 4: Implement trace validation**

Add `validate_trace(method_name, trace, token_usage)` returning a structured object with `passed`, missing stage groups, observed stages, and observed model-call evidence. Keep validation independent of the model client and Docker evaluator.

- [ ] **Step 5: Attach fidelity results to every workflow row**

After `run_workflow` returns, validate agent traces and serialize `workflow_completed`, `fidelity_passed`, and `fidelity_details`. Traditional prompt methods remain explicitly classified as prompting baselines and do not use the agent contract.

- [ ] **Step 6: Run fidelity and runner unit tests**

Run: `python -m unittest tests.test_agent_workflow_fidelity tests.test_baseline_runtime -v`

Expected: all tests pass; a fabricated one-call agent trace is rejected.

### Task 5: Perform live one-task smoke tests for all nine baselines

**Files:**
- Modify if required by verified failures: `methods/workflow_baselines/run_true_agent_workflows.py`
- Output (ignored): `translation_work/baseline_smoke_20260903/`
- Update: `docs/baseline_execution_audit.md`

- [ ] **Step 1: Verify the live-run configuration without exposing secrets**

Set the OpenAI-compatible endpoint, verified key, model, timeout, and one-task limit in process environment only. Print model and endpoint but never the authorization value.

- [ ] **Step 2: Run four prompting baselines**

Invoke the unified runner on one Python CodeSecEval task with the four traditional method names, `workers=1`, deterministic temperature, and a bounded token budget.

Expected: each row contains non-empty generated code and a structured Docker evaluation result; incorrect candidate code is recorded as a model failure rather than a runner exception.

- [ ] **Step 3: Run five agent baselines**

Invoke AutoSafeCoder, AgentCoder, RA-Gen, SWE-Agent, and SecAwareCoder individually on the same task, with their ZIP-derived workflow stages and configured repair limits intact.

Expected: each row contains non-empty code, a sanitized multi-stage trace, `workflow_completed=true`, a fidelity result, and a structured Docker evaluation result.

- [ ] **Step 4: Diagnose only infrastructure or orchestration failures**

For any authentication, truncation, extraction, import, timeout, or runner failure, use the failing trace and focused reproduction before changing code. Do not modify a baseline merely because its generated candidate fails functional or security tests.

- [ ] **Step 5: Summarize the nine results**

Record per method: model-call success, code extraction, workflow fidelity where applicable, functional pass, security pass, combined pass, terminal status, token use, and artifact path.

### Task 6: Re-audit SCT against the copied DOCX

**Files:**
- Modify: `docs/sct_docx_gap_analysis.md`
- Inspect: `docs/面向多语言安全代码生成的经验自进化方法.docx`
- Inspect: `methods/sct_agent/`
- Inspect: `src/translation_pipeline/architecture_experiment.py`
- Inspect: `docs/evaluation_protocol.md`

- [ ] **Step 1: Rebuild the requirement-to-code matrix**

Map orchestration, experience acquisition, representation, retrieval, candidate evolution, multi-source validation, quality/effectiveness/regression gates, promotion/revision/rejection, convergence, frozen generation, repair, and data boundaries to concrete files and functions.

- [ ] **Step 2: Apply the approved classification vocabulary**

Classify every row as `aligned`, `partially aligned`, `missing`, or `implementation deviation`, and attach code or execution evidence.

- [ ] **Step 3: Separate comparison evaluation from SCT data boundaries**

State explicitly that using CodeSecEval for the nine baseline comparison runs is valid. Discuss SCT leakage or isolation only where the formal SCT implementation reads, evolves on, selects with, or evaluates against a dataset partition.

- [ ] **Step 4: Verify formal SCT entry points**

Run import/help smoke checks and one bounded execution where dependencies exist. Record missing gate artifacts or import failures as implementation gaps rather than silently substituting the legacy runner.

### Task 7: Final verification, cleanup, and reporting

**Files:**
- Modify: `docs/baseline_execution_audit.md`
- Modify: `docs/sct_docx_gap_analysis.md`
- Verify: all changed source and test files

- [ ] **Step 1: Run repository verification**

Run: `python -m compileall src methods tools; python -m unittest discover -s tests -v; python tools/check_repository.py`

Expected: compilation and tests pass; repository checker exits successfully or any pre-existing independent failure is identified with evidence.

- [ ] **Step 2: Verify Docker infrastructure**

Run: `docker info; docker image inspect safecoder-python-validator:local safecoder-cpp-validator:local golang:1.22`

Expected: Docker is reachable and all validator images are available.

- [ ] **Step 3: Scan for secret leakage**

Run tracked-file and diff scans for key prefixes, authorization headers with literal values, `local_secrets`, and generated-output directories. Report counts and paths only; never print matching secret values.

- [ ] **Step 4: Remove temporary files created by this execution**

Delete only disposable caches, raw transient responses, and scratch directories recorded during this plan. Preserve sanitized smoke-test evidence referenced by the reports. Verify every deletion target resolves under `translation_work/baseline_smoke_20260903/` or another explicitly created scratch directory before removal.

- [ ] **Step 5: Inspect the final diff and working tree**

Run: `git diff --check; git status --short`

Expected: no whitespace errors, no tracked secrets, and all unrelated pre-existing user modifications remain untouched.

- [ ] **Step 6: Present the final test report**

Report exact commands, pass/fail counts, the nine baseline smoke outcomes, Agent fidelity results, Docker status, credential status, SCT gap summary, temporary-file cleanup, and any remaining limitations. Do not claim a model candidate passed security or functionality unless the saved evaluator evidence says so.

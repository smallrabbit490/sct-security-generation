# Agent Baseline Integration and SCT Audit Design

Date: 2026-09-03

## Objective

Validate nine baselines against CodeSecEval and audit the current SCT implementation against the method described in `docs/面向多语言安全代码生成的经验自进化方法.docx`.

The nine baselines are comparison methods. Their use of CodeSecEval is intentional evaluation behavior and is not data contamination. The five agent baselines may receive compatibility adaptations, but they must remain faithful multi-stage workflows rather than being reduced to prompting methods.

This work validates a small, representative smoke-test sample. A full-dataset experiment is outside the default scope.

## Selected Approach

Keep the repository's unified baseline runner and adapt each original ZIP implementation at its boundaries. For each agent baseline, preserve the original stages, roles, prompt templates, iteration conditions, feedback paths, and default budgets as closely as the available implementation permits. Limit changes to dataset input, model-client integration, output serialization, Docker evaluation, and compatibility fixes.

This approach is preferred over directly operating five isolated upstream environments because it produces a stable, uniform CodeSecEval evaluation path. It is preferred over rewriting the methods on a shared agent framework because a rewrite would create excessive deviation from the ZIP implementations.

## Baseline Categories

- The four prompting baselines remain single-request prompting methods.
- The five agent baselines must execute their original multi-stage workflows.
- All nine methods consume equivalent CodeSecEval task inputs and produce code for the same functional and security evaluation path.

## Agent Fidelity Contract

Each agent baseline will have a fidelity record containing:

- the corresponding source files in the previously extracted ZIP;
- the required workflow stages and agent roles;
- the minimum expected model-call pattern;
- iteration, review, testing, or feedback behavior;
- original default budgets and termination conditions;
- explicitly permitted repository-specific adaptations.

Permitted adaptations are limited to:

- CodeSecEval input loading;
- ChatAnywhere model-client calls;
- generated-code extraction and normalized result serialization;
- current Docker validator integration;
- dependency and platform compatibility corrections.

The following changes are prohibited:

- merging or deleting essential workflow stages;
- removing review, feedback, repair, or iteration loops required by the original method;
- collapsing multiple agent roles into a single prompt request;
- substituting pre-generated answers for live model generation;
- redesigning the method for convenience under the name of compatibility.

Machine-checkable assertions will reject a run when required stages are absent or when an agent method degenerates into a single prompting call.

## Execution and Evaluation Flow

For each smoke-test task:

1. Load the same CodeSecEval problem representation.
2. Execute the selected baseline with a live ChatAnywhere request.
3. For agent methods, capture a sanitized stage trace and verify the fidelity contract.
4. Extract the generated code without depending on missing historical harness objects.
5. Submit the code to the existing Docker functional validator.
6. Submit it to the applicable security validation path.
7. Store the generated code, evaluation result, infrastructure status, and sanitized trace under ignored experiment-output directories.

A model candidate that compiles incorrectly, raises a runtime error, fails functional tests, or fails security checks is still a completed workflow result if the runner and evaluator reach a structured terminal state. Authentication failures, response truncation without handled recovery, extraction crashes, missing stages, container infrastructure failures, and unhandled runner exceptions mean the baseline did not run through successfully.

## Python Evaluation Repair

The current Python compatibility path fails because it dereferences a missing historical harness object during code extraction. The repair will be test-driven:

1. Add a failing regression test demonstrating that baseline evaluation must not require the old harness object.
2. Confirm the test fails for the current reason.
3. Apply the smallest change that routes evaluation through the current Docker Python validator and supported extraction path.
4. Run focused tests, the existing unit suite, and a live one-task smoke test.

The repair must not silently change the evaluation semantics for C++ or Go.

## ChatAnywhere Credential Cleanup

The local credential source currently contains six candidate keys. Five were independently observed returning HTTP 401, while one returned HTTP 200.

The cleanup will:

- remove the five invalid keys from `local_secrets/chatanywhereapi使用/apikey.txt`;
- remove any local environment or manifest references to those invalid keys;
- retain only the verified working key;
- keep all credentials and credential-bearing logs outside version control;
- report only key counts, ordinal identifiers, masked fingerprints, and HTTP status codes.

After cleanup, the checker must discover exactly one local key and receive HTTP 200 from the configured compatibility endpoint. No raw key value may appear in repository files, commits, terminal summaries, test fixtures, traces, or audit reports.

## SCT-to-DOCX Audit

The SCT audit is independent of baseline evaluation. It will map the current formal SCT entry point and supporting implementation to the DOCX method across:

- method modules and orchestration;
- experience acquisition and representation;
- experience evolution or self-evolution;
- feedback, repair, and selection mechanisms;
- inference-time data flow and data boundaries;
- experiment configuration and stopping conditions.

Each item will be classified as `aligned`, `partially aligned`, `missing`, or `implementation deviation`, with file-level or execution evidence. The audit must not infer an SCT data-boundary violation merely because comparison baselines evaluate on CodeSecEval.

## Verification Matrix

Each prompting baseline must demonstrate:

- a successful live model response;
- extractable generated code;
- entry into functional and security evaluation;
- a structured terminal result.

Each agent baseline must additionally demonstrate:

- all required original workflow stages in its sanitized trace;
- compliance with the minimum model-call and feedback/iteration contract;
- no single-prompt fallback presented as an agent run.

Repository-level verification includes focused regression tests, the complete available unit-test suite, credential leak scanning, Docker image availability, and one-task live smoke runs. Full-dataset runs require a separate decision because of API cost and runtime.

## Deliverables

- cleaned local ChatAnywhere credential configuration;
- regression coverage and the minimal Python evaluator repair;
- fidelity definitions and assertions for the five agent baselines;
- sanitized smoke-test artifacts for all nine baselines;
- an updated `docs/baseline_execution_audit.md`;
- an updated `docs/sct_docx_gap_analysis.md`.

## Change Safety

Existing user changes in the working tree must be preserved. Experiment products belong under already ignored output locations such as `translation_work/`. Commits must exclude API keys, local secrets, raw credential logs, and unrelated user modifications.

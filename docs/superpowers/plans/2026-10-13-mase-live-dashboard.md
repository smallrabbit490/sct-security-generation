# MASE Live Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the MASE review page into a live, auditable run dashboard with cooperative pause/resume, precise progress/events, configurable model roles, and 40–50 global API request concurrency.

**Architecture:** Keep experiment orchestration in `run.py`, use small control/event helpers for atomic local state, and keep the dashboard server as the only browser-facing API boundary. The browser polls deltas and displays run state beside the actual graph; task details are assembled from existing persisted rows plus sanitized events. Role-specific requesters share one bounded semaphore; the active 8-worker run remains untouched.

**Tech Stack:** Python standard library HTTP server/threading/concurrent.futures, JSONL/atomic JSON artifacts, existing HTML/CSS/vanilla JavaScript, pytest, Playwright.

---

### Task 1: Add control-state and progress primitives

**Files:**
- Create: `methods/mase_evolution/control.py`
- Test: `tests/test_mase_control.py`

- [ ] **Step 1: Write failing tests** for atomic pause request, idempotent pause, allowed resume only from paused, and status rejection after completed/failed.
- [ ] **Step 2: Run** `D:/ANACONDA/python.exe -m pytest tests/test_mase_control.py -q`; expect missing module failure.
- [ ] **Step 3: Implement** atomic JSON writes using sibling temporary file + `os.replace`, status transition validation, and a control reader that returns a no-control legacy result when no file exists. Add Chinese docstrings describing the stage, inputs/outputs, evidence, failure cases, and that long-term memory is never writable.
- [ ] **Step 4: Run** the focused test and verify all cases pass.

### Task 2: Make run scheduling pausable and resumable

**Files:**
- Modify: `methods/mase_evolution/run.py`
- Test: `tests/test_mase_control.py`

- [ ] **Step 1: Add tests** around an extracted scheduler helper: pause stops new submissions, waits for submitted tasks to persist, then reports paused; resume skips task IDs already in `rows.jsonl`; repeated pause requests do not duplicate rows.
- [ ] **Step 2: Run** the focused tests and confirm they fail because scheduling is currently all-at-once.
- [ ] **Step 3: Implement** bounded task submission (at most configured workers in flight), check pause state before each submission, persist each completed row before marking it done, and stop filling the queue after pause. Preserve append-only events and existing run signatures. Add Chinese comments documenting workflow stage, task inputs/outputs, validation evidence, failure paths, and no memory-bank mutation.
- [ ] **Step 4: Run** focused pause/resume tests and existing MASE tests.

### Task 3: Record node starts, heartbeats, and API request counts

**Files:**
- Modify: `methods/mase_evolution/executor.py`
- Modify: `methods/mase_evolution/session.py`
- Modify: `methods/mase_evolution/run.py`
- Test: `tests/test_mase_live_events.py`

- [ ] **Step 1: Write failing tests** proving every node emits running then terminal events, heartbeat identifies active task/node and queue counts, unknown token usage remains null, and request peak never exceeds the shared semaphore.
- [ ] **Step 2: Run** `D:/ANACONDA/python.exe -m pytest tests/test_mase_live_events.py -q`; confirm expected failures.
- [ ] **Step 3: Implement** start/end event emission, append-only structured request events with redacted messages and hashes, and atomic heartbeat updates containing planned/saved/measured/pending/active/queued/node/request counts. Events must not contain API keys, hidden tests, or private chain-of-thought. Add required Chinese comments for MASE stage/evidence/failure and memory boundaries.
- [ ] **Step 4: Run** focused tests and existing executor/session tests.

### Task 4: Separate decision and generation model routes

**Files:**
- Modify: `methods/mase_evolution/session.py`
- Modify: `methods/mase_evolution/designer.py`
- Modify: `methods/mase_evolution/operators.py`
- Modify: `methods/mase_evolution/run.py`
- Test: `tests/test_mase_model_roles.py`

- [ ] **Step 1: Write failing tests** for role-to-provider/model routing, shared global request cap, metadata recording, and explicit failure when a configured model is unsupported (no silent fallback).
- [ ] **Step 2: Run** the focused tests and verify role configuration is currently absent.
- [ ] **Step 3: Implement** explicit decision-model settings for designer, memory applicability, candidate selection, and other decision nodes; keep code-generation model separately configurable. Verify provider/model availability with a non-generating preflight supported by the configured endpoint. If the current ChatAnywhere endpoint does not support `GPT-6.1-sol`, report that and require a configured compatible provider; never label an internal Codex model as a ChatAnywhere model. Use one shared semaphore for all roles, configurable to 40–50 (default target 48); record configured and observed peak concurrency, provider errors, and rate limits. Add Chinese MASE comments for stage, input/output, evidence, failure modes, and memory write rights.
- [ ] **Step 4: Run** focused model routing tests and existing MASE tests.

### Task 5: Add live read/control APIs

**Files:**
- Modify: `methods/mase_evolution/dashboard/server.py`
- Test: `tests/test_mase_dashboard_api.py`

- [ ] **Step 1: Write failing HTTP handler tests** for summary/heartbeat reads, incremental events after a cursor, task event retrieval, pause/resume transitions, invalid IDs, path traversal rejection, and read-only legacy runs.
- [ ] **Step 2: Run** the test and verify the live/control endpoints are absent.
- [ ] **Step 3: Implement** GET endpoints for run progress/events and POST endpoints for pause/resume. Validate run/version IDs and status transitions; keep loopback-only binding; use existing allowlisted run root. Return structured errors without leaking filesystem paths or secrets.
- [ ] **Step 4: Run** the API tests and existing dashboard tests.

### Task 6: Build the parallel live dashboard view

**Files:**
- Modify: `methods/mase_evolution/dashboard/static/index.html`
- Modify: `methods/mase_evolution/dashboard/static/app.js`
- Modify: `methods/mase_evolution/dashboard/static/style.css`
- Test: `tests/test_mase_dashboard_ui.py`

- [ ] **Step 1: Write UI assertions** for parallel status/process regions, visible pause/resume states, accurate denominator labels, active task/node/queue, decision model identity, and task-level message/check/selection evidence.
- [ ] **Step 2: Run** UI tests against a local server and capture the expected failures.
- [ ] **Step 3: Implement** polling with incremental event cursors, pause/resume button states that reflect server acknowledgement, process graph node state, progress counters, detailed task evidence, and polling error/stale indicators. Preserve responsive desktop/mobile layout and existing comparisons. Never display unknown as zero or mark a pause requested as paused.
- [ ] **Step 4: Run** UI tests and check for script errors.

### Task 7: Regression, browser verification, and operating notes

**Files:**
- Modify: `methods/mase_evolution/dashboard/README.md`
- Test: `tests/test_mase_control.py`, `tests/test_mase_live_events.py`, `tests/test_mase_model_roles.py`, `tests/test_mase_dashboard_api.py`, `tests/test_mase_dashboard_ui.py`

- [ ] **Step 1: Run** focused MASE tests, then the full existing `tests/test_mase_evolution.py`, `tests/test_node_status_invariant.py`, and relevant MASE test files.
- [ ] **Step 2: Start or reuse** the dashboard on port 8781 without interrupting run PID 38968; verify the active run stays read-only if it lacks new control metadata.
- [ ] **Step 3: Use Playwright** at desktop and narrow mobile viewport to verify no overlap, nonblank process graph, automatic refresh, truthful old-run state, and task detail navigation. Capture screenshots for visual inspection.
- [ ] **Step 4: Update README** with new launch options, pause/resume semantics, concurrency vs worker definitions, model-role configuration, and legacy-run limitations.
- [ ] **Step 5: Inspect final diff and run `git status --short`** to ensure no generated artifacts or unrelated user changes were staged.

## Spec Coverage Self-Review

- Runtime view, status terminology, counts and stale state: Tasks 3, 5, 6.
- Cooperative pause/resume and persistence ordering: Tasks 1, 2, 5, 6.
- Node graph and task evidence: Tasks 3, 5, 6.
- 40–50 global API concurrency separated from task workers: Task 4.
- Decision/generation model separation and provider preflight: Task 4.
- Incomplete workflows excluded from official scoring: regression assertion in Task 2/Task 3; preserve the `execute_task` guard and add a test in Task 3.
- API safety and legacy read-only behavior: Tasks 1, 5, 7.
- Desktop/mobile visual verification: Task 7.

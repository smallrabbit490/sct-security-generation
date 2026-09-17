# SCT 统一核心流水线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按原始 DOCX 将 `methods/sct_agent` 重构为统一、可审计、冻结隔离的 SCT 经验自进化流水线。

**Architecture:** 用六个小模块承载 schema、图一差异分析、多源验证、失败聚类、经验卡和门控；正式语言入口负责编排，PLT 入口和冻结评测入口作为适配器。旧 Coset Eagle 只保留兼容/回放能力。

**Tech Stack:** Python 3、标准库 dataclasses/ast/difflib/json、现有 `src/translation_pipeline` 验证器、pytest/unittest。

---

### Task 1: 统一 schema 和中文注释

**Files:**
- Create: `methods/sct_agent/schemas.py`
- Test: `tests/test_sct_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
def test_validation_and_gate_records_round_trip():
    evidence = ValidationEvidence.compile_pass("python")
    card = ExperienceCard("cwe-22", "路径输入", "限制规范化路径", {"python": "resolve"}, "禁止前缀判断")
    record = GateRecord("cand-1", evidence, 0.1, 0, "promote", ["joint pass improved"])
    assert GateRecord.from_dict(record.to_dict()).decision == "promote"
    assert card.to_dict()["principle"] == "限制规范化路径"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sct_schemas.py -q`
Expected: FAIL because `methods.sct_agent.schemas` does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement dataclasses with中文 docstring，提供 `to_dict/from_dict`；`ValidationEvidence` 为八类验证状态提供 `pass/fail/unmeasured` 构造方法，`GateRecord` 校验决策枚举。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sct_schemas.py -q`
Expected: PASS。

### Task 2: 图一漏洞—补丁差异分析

**Files:**
- Create: `methods/sct_agent/difference_analysis.py`
- Test: `tests/test_sct_difference_analysis.py`

- [ ] **Step 1: Write the failing test**

```python
def test_path_patch_extracts_six_required_categories():
    result = analyze_difference("open(user_path)", "open(root / safe_name)", {"arguments": "user_path"}, "22")
    assert "user_path" in result.untrusted_inputs
    assert result.patch_changes
    assert result.postconditions
    assert result.dangerous_patterns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sct_difference_analysis.py -q`
Expected: FAIL because `analyze_difference` does not exist.

- [ ] **Step 3: Write minimal implementation**

Use AST and `difflib.unified_diff` to identify参数流、文件/命令/网络敏感调用、校验新增删除替换；结合 CWE 规则生成后置条件和危险模式。输出 `DifferenceAnalysis`，不保留完整测试输入或答案常量。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sct_difference_analysis.py -q`
Expected: PASS。

### Task 3: 统一多源动态验证证据

**Files:**
- Create: `methods/sct_agent/validation_evidence.py`
- Test: `tests/test_sct_validation_evidence.py`

- [ ] **Step 1: Write the failing test**

```python
def test_validator_preserves_function_security_and_unmeasured_states():
    evidence = validate_generated_code("python", "def f(): return 1", functional=lambda c: True, security=lambda c: False)
    assert evidence.functional.status == "pass"
    assert evidence.security.status == "fail"
    assert evidence.static_analysis.status == "unmeasured"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sct_validation_evidence.py -q`
Expected: FAIL because the unified validator is missing.

- [ ] **Step 3: Write minimal implementation**

Implement注入式适配器，默认调用现有 Python/C++/Go validator；所有八类证据都有明确状态，异常映射到 `error_type`，不把缺少工具当作通过。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sct_validation_evidence.py -q`
Expected: PASS。

### Task 4: 失败脱敏、聚类和经验卡

**Files:**
- Create: `methods/sct_agent/failure_clustering.py`
- Create: `methods/sct_agent/experience_cards.py`
- Test: `tests/test_sct_experience_cards.py`

- [ ] **Step 1: Write the failing test**

```python
def test_failure_cluster_redacts_task_and_test_values():
    cluster = cluster_failures([{"task_id": "secret-1", "stderr": "assert token=abc", "error_type": "security"}], min_support=1)
    payload = cluster[0].to_dict()
    assert "secret-1" not in str(payload)
    assert "abc" not in str(payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sct_experience_cards.py -q`
Expected: FAIL because clustering and card modules are missing.

- [ ] **Step 3: Write minimal implementation**

实现字段白名单脱敏、规范化错误消息、最小支持数过滤；经验卡检查任务 ID、测试输入、常量和补丁片段泄露，并执行重复/冲突检测。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sct_experience_cards.py -q`
Expected: PASS。

### Task 5: 三层候选经验门控和生命周期

**Files:**
- Create: `methods/sct_agent/candidate_gates.py`
- Create: `methods/sct_agent/experience_lifecycle.py`
- Test: `tests/test_sct_candidate_gates.py`

- [ ] **Step 1: Write the failing test**

```python
def test_gate_requires_positive_joint_pass_and_no_hpass_regression():
    assert decide_candidate(0.0, 0.0, 0.0).decision == "reject"
    assert decide_candidate(0.2, 0.0, 0.0).decision == "promote"
    assert decide_candidate(0.2, 0.1, 0.0).decision == "reject"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sct_candidate_gates.py -q`
Expected: FAIL because gate implementation is missing.

- [ ] **Step 3: Write minimal implementation**

分别实现质量、有效性和 H_pass 回归判定；有效性严格使用 `delta_joint_pass > 0`，回归要求安全回归为零且功能退化不超过 epsilon；生命周期只允许已通过门控的候选写入长期库。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sct_candidate_gates.py -q`
Expected: PASS。

### Task 6: 重构三个正式入口和冻结评测

**Files:**
- Modify: `methods/sct_agent/run_sct_language_evolution.py`
- Modify: `methods/sct_agent/run_plt_self_evolution.py`
- Modify: `methods/sct_agent/finalize_plt_evaluation.py`
- Modify: `methods/sct_agent/run_coset_eagle_experiment.py`
- Test: `tests/test_sct_freeze_isolation.py`

- [ ] **Step 1: Write the failing test**

```python
def test_frozen_evaluation_rejects_memory_updates(tmp_path):
    manifest = FreezeManifest(model="test", memory_sha256="abc", feedback_channel="disabled")
    assert can_update_memory(manifest) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sct_freeze_isolation.py -q`
Expected: FAIL because freeze guard is missing.

- [ ] **Step 3: Write minimal implementation**

正式入口改为调用统一模块；PLT 入口保留 96 条分区但使用真实训练侧验证；冻结评测写出 `freeze_metadata.json`、完整 `ValidationEvidence` 和 Base/Plus 分开汇总；Coset Eagle 明确标记 prototype，禁止写入正式结果目录。

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sct_freeze_isolation.py -q`
Expected: PASS。

### Task 7: 文档、入口烟测和全量检查

**Files:**
- Modify: `docs/sct_docx_gap_analysis.md`
- Modify: `docs/experience_self_evolution_guide.md`
- Modify: `docs/plt_self_evolution.md`
- Modify: `README.md`

- [ ] **Step 1: 更新文档索引和 schema/目录说明**

记录正式入口、JSONL 字段、冻结边界、验证后端、失败清理规则和原型入口限制。

- [ ] **Step 2: 运行编译检查**

Run: `python -m compileall methods/sct_agent tests`
Expected: exit code 0。

- [ ] **Step 3: 运行全部测试**

Run: `python -m pytest -q`
Expected: 所有测试通过，失败数为 0。

- [ ] **Step 4: 运行入口烟测**

Run: `python methods/sct_agent/run_sct_language_evolution.py --help`; `python methods/sct_agent/run_plt_self_evolution.py --help`; `python methods/sct_agent/finalize_plt_evaluation.py --help`; `python methods/sct_agent/run_coset_eagle_experiment.py --help`
Expected: 四个命令均退出 0，不导入缺失的密钥或网络依赖。

- [ ] **Step 5: 检查敏感信息和临时目录**

Run: `rg -n "sk-[A-Za-z0-9]|api[_-]?key\\s*[:=]" methods/sct_agent docs README.md`; `Get-ChildItem translation_work/temp -ErrorAction SilentlyContinue`
Expected: 没有密钥命中；没有孤立临时运行目录。

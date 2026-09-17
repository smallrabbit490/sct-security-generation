"""阶段 C 验收：错题本 Error Ledger 结构与三大消费接口。"""

from methods.sct_trajectory.error_ledger import ErrorEntry, ErrorLedger


def _entry(cwe, kind, failure_type="security_gap", transition="B->B"):
    return ErrorEntry(
        cwe=cwe,
        kind=kind,
        failure_type=failure_type,
        source_hash=f"h-{cwe}-{kind}",
        transition=transition,
    )


def test_add_marks_high_difficulty():
    ledger = ErrorLedger()
    ledger.add(_entry("CWE-22", "B_stalled"))
    assert ledger.entries[0].difficulty == "normal"
    ledger.add(_entry("CWE-502", "D_stalled"))
    assert ledger.entries[1].difficulty == "high"
    ledger.add(ErrorEntry("CWE-1333", "seed_grounding_failure", "both_failed", "h1", ""))
    assert ledger.entries[2].difficulty == "high"


def test_cwe_density_and_replay_bias():
    ledger = ErrorLedger()
    ledger.add_many([
        _entry("CWE-22", "B_stalled"),
        _entry("CWE-22", "C_stalled", "functional_regression", "C->C"),
        _entry("CWE-502", "D_stalled", "both_failed", "D->D"),
    ])
    density = ledger.cwe_density()
    assert density == {"CWE-22": 2, "CWE-502": 1}
    bias = ledger.replay_bias()
    # CWE-22 密度更高，权重应更大
    assert bias["CWE-22"] > bias["CWE-502"]


def test_analysis_warning_dedup_and_rank():
    ledger = ErrorLedger()
    ledger.add_many([
        _entry("CWE-22", "B_stalled", "security_gap"),
        _entry("CWE-22", "B_stalled", "security_gap"),
        _entry("CWE-22", "C_stalled", "functional_regression"),
        _entry("CWE-78", "D_stalled", "both_failed"),
    ])
    warnings = ledger.analysis_warning("CWE-22")
    assert len(warnings) == 2  # security_gap 出现 2 次排第一，functional_regression 第二
    assert "security_gap" in warnings[0]
    # 不含任务 ID 明文
    assert "h-CWE" not in " ".join(warnings)


def test_merge_negative_boundary():
    ledger = ErrorLedger()
    ledger.add_many([
        _entry("CWE-22", "B_stalled", "security_gap"),
        _entry("CWE-22", "C_stalled", "functional_regression"),
        _entry("CWE-22", "B_stalled", "security_gap"),  # 重复，应去重
    ])
    boundary = ledger.merge_negative_boundary("CWE-22")
    assert boundary == ["functional_regression", "security_gap"]


def test_empty_ledger():
    ledger = ErrorLedger()
    assert ledger.cwe_density() == {}
    assert ledger.replay_bias() == {}
    assert ledger.analysis_warning("CWE-22") == []
    assert ledger.merge_negative_boundary("CWE-22") == []


def test_serialization():
    ledger = ErrorLedger()
    ledger.add(_entry("CWE-22", "B_stalled"))
    rows = ledger.to_jsonl()
    assert rows[0]["cwe"] == "CWE-22"
    import json

    assert json.loads(json.dumps(rows))[0]["kind"] == "B_stalled"
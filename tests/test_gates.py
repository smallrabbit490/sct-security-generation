"""阶段 G2 验收：三层门控（Gate1 召回探针 + Gate2 ΔJointPass + Gate3 降噪回归）。"""

from methods.sct_trajectory.gates import (
    audit_candidate,
    gate2_effectiveness,
    gate3_regression,
    majority_vote,
)


class _FakeRetriever:
    """命中/未命中可控的假检索器。"""

    def __init__(self, hit_ids):
        self.hit_ids = set(hit_ids)

    def search(self, task, limit=3, *, extra_nodes=None):
        return [{"invariant_id": i} for i in sorted(self.hit_ids)[:limit]]


def _task():
    return {"CWE_ID": "CWE-22", "language": "python", "description": "x"}


def test_majority_vote():
    assert majority_vote([True, True, False]) is True
    assert majority_vote([True, False, False]) is False
    assert majority_vote([True, True, True]) is True
    assert majority_vote([]) is False


def test_gate2_effectiveness():
    """默认"要求正证据"：Δ>0 通过，Δ=0 记为无证据，Δ<0 淘汰。"""
    assert gate2_effectiveness(0.1) == "proceed"
    assert gate2_effectiveness(0.0) == "unmeasured"      # 测了但没测出差异
    assert gate2_effectiveness(-0.1) == "demoted"
    # 旧放宽模式（仅对照实验用）：Δ=0 也算通过
    assert gate2_effectiveness(0.0, allow_equal=True) == "proceed"


def test_gate3_tolerance():
    # τ_sec=1：允许 1 次安全回归
    assert gate3_regression(1, 0, tau_sec=1, tau_func=0) is True
    assert gate3_regression(2, 0, tau_sec=1, tau_func=0) is False
    # 功能退化零容忍（τ_func=0）
    assert gate3_regression(0, 1, tau_sec=1, tau_func=0) is False


def test_audit_supported():
    r = _FakeRetriever(["inv-1"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.2, security_regressions=0)
    assert rec.decision == "supported"
    assert rec.gate1_retrieved is True


def test_audit_probe_miss_not_blocking_in_default_mode():
    """默认模式：Gate1 未命中只记录，不作为拒绝理由（避免误杀）。"""
    r = _FakeRetriever(["inv-other"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.2, security_regressions=0)
    assert rec.gate1_retrieved is False
    assert rec.decision == "supported"


def test_audit_probe_miss_blocks_in_relaxed_mode():
    r = _FakeRetriever(["inv-other"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.2,
                          security_regressions=0, block_on_probe_miss=True)
    assert rec.decision == "revised"
    assert "probe_missed" in rec.reasons[0]


def test_audit_demoted_on_negative_delta():
    r = _FakeRetriever(["inv-1"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=-0.1, security_regressions=0)
    assert rec.decision == "demoted"


def test_audit_unmeasured_on_zero_delta_default():
    """核心改动：Δ=0（无证据）→ unmeasured，不晋升但保留在池里参与检索。"""
    r = _FakeRetriever(["inv-1"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.0, security_regressions=0)
    assert rec.decision == "unmeasured"
    assert "no_evidence" in rec.reasons[0]


def test_audit_supported_on_zero_delta_in_relaxed_mode():
    """旧放宽模式（对照用）：Δ=0 也 supported。"""
    r = _FakeRetriever(["inv-1"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.0,
                          security_regressions=0, allow_equal=True)
    assert rec.decision == "supported"


def test_audit_supported_only_with_positive_evidence():
    """只有 Δ>0 才 supported（本改动的核心验收点）。"""
    r = _FakeRetriever(["inv-1"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.5, security_regressions=0)
    assert rec.decision == "supported"


def test_audit_demoted_on_regression():
    r = _FakeRetriever(["inv-1"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.2, security_regressions=2)
    assert rec.decision == "demoted"


def test_audit_revised_on_hpass_missing():
    r = _FakeRetriever(["inv-1"])
    rec = audit_candidate("inv-1", r, _task(), delta_joint_pass=0.2, security_regressions=0, hpass_missing=3)
    assert rec.decision == "revised"
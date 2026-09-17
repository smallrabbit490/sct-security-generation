"""阶段 B 验收：四态判定 + 8 类跃迁分类（对齐 DOCX 表 1）。"""

from methods.sct_trajectory.four_state import (
    classify_first_state,
    classify_transition,
    distill_target,
    make_transition,
    state_from_evidence,
    transition_kind,
)
from methods.sct_trajectory.schemas import RolloutTrace, Transition


def _ev(func: str, sec: str) -> dict:
    """构造最小验证证据 dict（功能/安全两维 + 语法占位）。"""
    return {
        "syntax_or_compile": {"status": "pass"},
        "functional": {"status": func},
        "security": {"status": sec},
    }


# ---------- 四态判定（阶段 0 已有，保留回归） ----------

def test_four_state_mapping():
    assert state_from_evidence(_ev("pass", "pass")).label == "A"
    assert state_from_evidence(_ev("pass", "fail")).label == "B"
    assert state_from_evidence(_ev("fail", "pass")).label == "C"
    assert state_from_evidence(_ev("fail", "fail")).label == "D"


def test_unmeasured_not_treated_as_pass():
    assert state_from_evidence(_ev("unmeasured", "pass")).label != "A"
    assert state_from_evidence(_ev("pass", "unmeasured")).label != "A"


# ---------- Early-Exit 控制流（DOCX 表 1 第 1 列） ----------

def test_classify_first_state():
    assert classify_first_state("A") == "early_exit"
    for label in ("B", "C", "D"):
        assert classify_first_state(label) == "repair"


# ---------- 8 类跃迁分类（DOCX 表 1 全部 8 行） ----------

def test_eight_transition_kinds():
    assert classify_transition("B", "A") == "B_to_A"     # 行2 增益正例
    assert classify_transition("B", "C") == "B_to_C"     # 行3 破坏性防御
    assert classify_transition("B", "B") == "B_stalled"  # 行4 无改善
    assert classify_transition("B", "D") == "B_stalled"  # 行4 恶化
    assert classify_transition("C", "A") == "C_to_A"     # 行5 松绑
    assert classify_transition("C", "C") == "C_stalled"  # 行6 固化
    assert classify_transition("C", "D") == "C_stalled"  # 行6 恶化
    assert classify_transition("D", "A") == "D_to_A"     # 行7 突破
    assert classify_transition("D", "B") == "D_stalled"  # 行8 顽固失败
    assert classify_transition("D", "C") == "D_stalled"  # 行8 顽固失败
    assert classify_transition("D", "D") == "D_stalled"  # 行8 顽固失败


def test_no_transition_from_A():
    # A 触发 Early-Exit 不修复，规范中不存在 A→X 转移（旧实现曾把 A→C 误判 negative）
    assert classify_transition("A", "C") == "invalid"
    assert classify_transition("A", "B") == "invalid"
    assert classify_transition("A", "A") == "invalid"


def test_distill_targets():
    assert distill_target("B_to_A") == "positive_principle"
    assert distill_target("B_to_C") == "negative_guardrail"
    assert distill_target("B_stalled") == "error_ledger"
    assert distill_target("C_to_A") == "positive_principle"
    assert distill_target("C_stalled") == "error_ledger"
    assert distill_target("D_to_A") == "positive_principle"
    assert distill_target("D_stalled") == "error_ledger"
    # A 直出：提取标准实现模式 → 沉淀为正向经验（不再只是 h_pass）
    assert distill_target("direct_A") == "positive_principle"


def test_three_kinds_are_distinct():
    # C→A 松绑 / B→A 增益 / D→A 突破 必须可区分（旧实现曾合并为单一 gain）
    kinds = {classify_transition(b, "A") for b in ("B", "C", "D")}
    assert kinds == {"B_to_A", "C_to_A", "D_to_A"}


# ---------- 兼容层（阶段 E/G 迁移前的过渡） ----------

def test_transition_kind_compat_layer():
    assert transition_kind("B", "A") == "gain"
    assert transition_kind("D", "A") == "gain"
    assert transition_kind("B", "C") == "negative"
    assert transition_kind("B", "B") == "neutral"
    # 修正：A→C、D→C 不再误判为 negative
    assert transition_kind("A", "C") == "neutral"
    assert transition_kind("D", "C") == "neutral"


def test_make_transition_stores_fine_kind():
    t = make_transition("B", "C")
    assert isinstance(t, Transition)
    assert t.kind == "B_to_C"  # 现在存 8 类精细分类
    assert make_transition("C", "A").kind == "C_to_A"


def test_rollout_trace_roundtrip():
    trace = RolloutTrace(
        task_id="t1",
        cwe="CWE-22",
        states=["B", "A"],
        transitions=[make_transition("B", "A")],
        generated_codes=["def f(): pass", "def f(): pass"],
        evidence=[_ev("pass", "fail"), _ev("pass", "pass")],
    )
    d = trace.to_dict()
    assert d["transitions"][0]["kind"] == "B_to_A"
    import json

    assert json.loads(json.dumps(d))["task_id"] == "t1"
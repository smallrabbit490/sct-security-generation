"""阶段 E 验收：经验总结智能体（Distillation Agent，独立 LLM 元认知）。"""

from methods.sct_trajectory.distillation import (
    compute_local_diff,
    distill_trace,
    distill_transition,
    state_to_failure_type,
)
from methods.sct_trajectory.four_state import make_transition
from methods.sct_trajectory.schemas import RolloutTrace


def _trace(states, transitions, codes=None):
    return RolloutTrace(
        task_id="t1",
        cwe="CWE-22",
        states=states,
        transitions=[make_transition(b, a) for b, a in transitions],
        generated_codes=codes or ["def f(): pass"] * len(states),
    )


def _fake_requester(response_json):
    def fake(prompt):
        return {"choices": [{"message": {"content": response_json}}]}

    return fake


VALID = (
    '{"high_level_invariant": "Paths must resolve inside a trusted root", '
    '"positive_principle": "Apply resolve and verify containment before opening", '
    '"negative_guardrail": "", '
    '"applicability": "Path input requiring traversal protection", '
    '"attribution": "Analysis omitted legitimate input boundaries", '
    '"blind_spot": ""}'
)


def test_state_to_failure_type():
    assert "security_gap" in state_to_failure_type("B")
    assert "functional_regression" in state_to_failure_type("C")
    assert "both_failed" in state_to_failure_type("D")
    assert state_to_failure_type("A") == ""


def test_distill_transition_positive():
    out = distill_transition(
        cwe="CWE-22", kind="B_to_A", before="B", after="A",
        code_before="def f(p): return open(p)",
        code_after="def f(p): return open(resolve(p))",
        failure_type="security_gap",
        requester=_fake_requester(VALID),
    )
    assert out["target"] == "positive_principle"
    assert "resolve" in out["positive_principle"]
    assert out["attribution"]  # 归因非空
    assert out["error"] if "error" in out else True


def test_distill_transition_negative_guardrail():
    out = distill_transition(
        cwe="CWE-22", kind="B_to_C", before="B", after="C",
        code_before="def f(p): return open(p)",
        code_after="def f(p): return None",
        failure_type="functional_regression",
        requester=_fake_requester(VALID.replace('"negative_guardrail": ""', '"negative_guardrail": "Do not empty return values"')),
    )
    assert out["target"] == "negative_guardrail"
    assert "empty return values" in out["negative_guardrail"]


def test_distill_transition_error_ledger():
    out = distill_transition(
        cwe="CWE-22", kind="B_stalled", before="B", after="B",
        code_before="def f(p): return open(p)",
        code_after="def f(p): return open(p)",
        failure_type="security_gap",
        requester=_fake_requester(VALID.replace('"blind_spot": ""', '"blind_spot": "Repeated prefix checks instead of normalization"')),
    )
    assert out["target"] == "error_ledger"
    assert out["blind_spot"]


def test_distill_trace_partitions_by_target():
    # 用更明确的轨迹：B→A（gain）和 C→C（stalled）需要分开测
    t = RolloutTrace(
        task_id="t2", cwe="CWE-78",
        states=["B", "A"],
        transitions=[make_transition("B", "A")],
        generated_codes=["def f(): pass", "def f(): pass"],
    )
    req = _fake_requester(VALID)
    out = distill_trace(t, req)
    assert len(out["positive"]) == 1
    assert out["negative"] == []
    # 【按轮提炼】第 0 轮状态为 B（未达 A），会额外产出一条该轮的失败分析。
    # 这是用户要求的行为：首轮与修复轮各自的失败都要单独沉淀经验，
    # 否则"why the previous repair failed"会被丢弃。
    assert len(out["error_ledger"]) == 1
    assert out["error_ledger"][0]["round_index"] == 0
    assert out["error_ledger"][0]["round_state"] == "B"


def test_distill_trace_extracts_each_round_separately():
    """C→C 这种"两轮都失败"的轨迹，应产出**两条**按轮经验而非一条。"""
    t = RolloutTrace(
        task_id="t4", cwe="CWE-79",
        states=["C", "C"],
        transitions=[make_transition("C", "C")],
        generated_codes=["def f(): pass", "def f(): pass"],
        evidence=[{"functional": {"status": "fail", "details": "x"}},
                  {"functional": {"status": "fail", "details": "y"}}],
    )
    out = distill_trace(t, _fake_requester(VALID))
    rounds = [e.get("round_index") for e in out["error_ledger"] + out["negative"]
              if e.get("round_index") is not None]
    assert sorted(rounds) == [0, 1], f"应分别沉淀第 0/1 轮，实际 {rounds}"


def test_round_prompt_asks_prev_fix_assessment():
    """修复轮的提示词必须要求回答"上一轮改法为何没奏效"。"""
    from methods.sct_trajectory.distillation import build_round_prompt

    p = build_round_prompt(cwe="CWE-79", round_index=1, state="C", code="def f(): pass",
                           evidence={"functional": {"status": "fail", "details": "d"}},
                           prev_summary="Previous round 0 had state C")
    assert "prev_fix_assessment" in p
    assert "why the previous repair failed" in p


def test_distill_trace_direct_A():
    t = RolloutTrace(
        task_id="t3", cwe="CWE-22",
        states=["A"], transitions=[],
        generated_codes=["def f(p): return open(resolve(p))"],
    )
    out = distill_trace(t, _fake_requester(VALID))
    assert len(out["positive"]) == 1
    assert out["positive"][0]["kind"] == "direct_A"


def test_distill_trace_stalled_goes_to_ledger():
    t = RolloutTrace(
        task_id="t4", cwe="CWE-502",
        states=["D", "D"],
        transitions=[make_transition("D", "D")],
        generated_codes=["def f(): pass", "def f(): pass"],
    )
    req = _fake_requester(VALID.replace('"blind_spot": ""', '"blind_spot": "反序列化边界理解错误"'))
    out = distill_trace(t, req)
    assert out["positive"] == []
    assert out["error_ledger"]  # D→D 沉淀到错题本


def test_distill_bad_json_degrades():
    out = distill_transition(
        cwe="CWE-22", kind="B_to_A", before="B", after="A",
        code_before="", code_after="",
        requester=lambda p: {"choices": [{"message": {"content": "not json"}}]},
    )
    assert "error" in out


def test_compute_local_diff():
    diff = compute_local_diff("def f(p):\n    return open(p)\n", "def f(p):\n    return open(resolve(p))\n")
    assert "-    return open(p)" in diff
    assert compute_local_diff("", "x") == ""
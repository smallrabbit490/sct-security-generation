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
    '{"high_level_invariant": "路径必须规范化到受信根目录内", '
    '"positive_principle": "打开前 resolve 并校验包含关系", '
    '"negative_guardrail": "", '
    '"applicability": "路径输入需防目录逃逸", '
    '"attribution": "Analysis 遗漏了合法输入边界", '
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
        requester=_fake_requester(VALID.replace('"negative_guardrail": ""', '"negative_guardrail": "禁止清空返回"')),
    )
    assert out["target"] == "negative_guardrail"
    assert "清空返回" in out["negative_guardrail"]


def test_distill_transition_error_ledger():
    out = distill_transition(
        cwe="CWE-22", kind="B_stalled", before="B", after="B",
        code_before="def f(p): return open(p)",
        code_after="def f(p): return open(p)",
        failure_type="security_gap",
        requester=_fake_requester(VALID.replace('"blind_spot": ""', '"blind_spot": "反复用前缀判断而非规范化"')),
    )
    assert out["target"] == "error_ledger"
    assert out["blind_spot"]


def test_distill_trace_partitions_by_target():
    # 一条含 B→A（正例）和 B→C（负例）的轨迹
    trace = _trace(
        ["B", "A", "C"],
        [("B", "A"), ("A", "C")],  # 注意 A→C 是 invalid，不会产出；改用 D 场景更清晰
    )
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
    assert out["error_ledger"] == []


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
"""阶段 5 验收：冻结隔离与四态汇总报告。"""

import json

from methods.sct_trajectory.frozen import FrozenGuard, summarize_four_states


def _trace(states, transitions):
    return {"states": states, "transitions": transitions}


def test_summarize_four_states():
    traces = [
        _trace(["C", "A"], [{"before": "C", "after": "A", "kind": "gain"}]),
        _trace(["A"], []),
        _trace(["B", "C"], [{"before": "B", "after": "C", "kind": "negative"}]),
        _trace(["D", "B"], [{"before": "D", "after": "B", "kind": "neutral"}]),
    ]
    s = summarize_four_states(traces)
    assert s["four_state"] == {"A": 2, "B": 2, "C": 2, "D": 1}
    assert s["transition_kinds"] == {"gain": 1, "negative": 1, "neutral": 1}
    assert len(s["gain_transitions"]) == 1
    assert len(s["negative_transitions"]) == 1


def test_summary_json_serializable():
    s = summarize_four_states([_trace(["A"], [])])
    assert json.loads(json.dumps(s))["four_state"] == {"A": 1}


def test_frozen_guard_blocks_writes():
    guard = FrozenGuard(frozen=False)
    guard.write({"x": 1})  # 未冻结时允许
    guard.freeze()
    try:
        guard.write({"x": 2})
        raise AssertionError("应抛出 freeze_violation")
    except RuntimeError as exc:
        assert "freeze_violation" in str(exc)


def test_summarize_empty():
    assert summarize_four_states([])["four_state"] == {}
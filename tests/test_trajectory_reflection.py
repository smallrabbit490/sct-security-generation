"""阶段 1 验收：轨迹转移对比反思引擎。"""

from methods.sct_trajectory.four_state import make_transition
from methods.sct_trajectory.schemas import RolloutTrace
from methods.sct_trajectory.trajectory_reflection import (
    card_is_safe,
    reflect_traces,
)


def _trace(task_id: str, cwe: str, transitions):
    """构造一条含指定转移的轨迹，附带最小编码上下文。"""
    return RolloutTrace(
        task_id=task_id,
        cwe=cwe,
        transitions=[make_transition(b, a) for b, a in transitions],
        states=[t[0] for t in transitions] + [transitions[-1][1]],
        generated_codes=["def f(): pass"] * (len(transitions) + 1),
    )


def test_gain_produces_positive_card():
    traces = [_trace("task-1", "CWE-22", [("B", "A")])]
    out = reflect_traces(traces)
    assert len(out["positive"]) == 1
    card = out["positive"][0]
    assert card["cwe"] == "CWE-22"
    assert card["provenance"]["transition"] == "B->A"
    # 不含任务 ID 明文
    assert "task-1" not in str(card)


def test_negative_produces_constraint():
    # B→C 产出负例卡；A→C 在 DOCX 表 1 中不存在（A 触发 Early-Exit），不沉淀
    traces = [_trace("task-2", "CWE-78", [("B", "C")])]
    out = reflect_traces(traces)
    assert len(out["negative"]) == 1
    assert out["negative"][0]["source_transition"] == "B->C"
    assert out["negative"][0]["forbidden_pattern"]


def test_neutral_transitions_ignored():
    traces = [_trace("task-3", "CWE-89", [("D", "B"), ("B", "B")])]
    out = reflect_traces(traces)
    assert out["positive"] == [] and out["negative"] == []


def test_dedup_identical_gain():
    # 同 CWE 同转移的多条轨迹只产出一张正例卡
    traces = [
        _trace("task-4", "CWE-22", [("B", "A")]),
        _trace("task-5", "CWE-22", [("B", "A")]),
    ]
    out = reflect_traces(traces)
    assert len(out["positive"]) == 1


def test_cards_pass_leak_check():
    traces = [
        _trace("task-6", "CWE-22", [("B", "A")]),
        _trace("task-7", "CWE-78", [("B", "C")]),
    ]
    out = reflect_traces(traces)
    for card in out["positive"] + out["negative"]:
        assert card_is_safe(card), f"泄露检查未通过: {card}"


def test_empty_traces():
    assert reflect_traces([]) == {"positive": [], "negative": []}
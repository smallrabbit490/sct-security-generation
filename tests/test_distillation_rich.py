"""新增经验类型（最小改动手法 / 过度防御陷阱）的解析与入池验收。"""

from methods.sct_trajectory.closed_loop import _node_from_hint, _node_from_pitfall
from methods.sct_trajectory.distillation import build_distillation_prompt


def test_prompt_requests_new_fields():
    """提炼提示必须同时要求原有字段与两类新经验（经验库变丰富而非变少）。"""
    p = build_distillation_prompt(
        cwe="CWE-1333", kind="B_to_A", before="B", after="A",
        code_before="def f():\n    pass\n", code_after="def f():\n    return 1\n",
        patch_diff="", failure_type="",
    )
    # 原有字段全部保留
    for field in ("high_level_invariant", "positive_principle", "negative_guardrail",
                  "applicability", "attribution", "blind_spot"):
        assert field in p, field
    # 新增字段
    assert "minimal_patch_hint" in p
    assert "overdefense_pitfall" in p
    # 新经验的说明要点
    assert "最小改动手法" in p
    assert "过度防御陷阱" in p


def test_node_from_hint():
    node = _node_from_hint({"cwe": "CWE-79", "minimal_patch_hint": "只对输出做上下文相关转义，不改数据结构",
                            "overdefense_pitfall": "禁止整体重写"})
    assert node is not None
    assert node.positive_principle.startswith("只对输出")
    assert node.cwe == "CWE-79"
    assert node.status == "provisional"


def test_node_from_hint_empty_returns_none():
    assert _node_from_hint({"cwe": "CWE-79", "minimal_patch_hint": "  "}) is None
    assert _node_from_hint({"cwe": "CWE-79"}) is None


def test_node_from_pitfall():
    node = _node_from_pitfall({"cwe": "CWE-89", "overdefense_pitfall": "无差别拒绝含引号的输入会让合法查询失败"})
    assert node is not None
    assert node.negative_guardrail.startswith("无差别拒绝")
    assert node.positive_principle == ""
    assert "过度防御陷阱" in node.high_level_invariant


def test_node_from_pitfall_empty_returns_none():
    assert _node_from_pitfall({"cwe": "CWE-89", "overdefense_pitfall": ""}) is None

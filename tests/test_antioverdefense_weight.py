"""阶段 G2 验收：抑制过度防御类经验的检索加权（第四条）。

依据：全量 298 条最终评测中 fail/pass（功能失败·安全通过）占 47.3%，
是最主要失败模式；而池中经验清一色"要加校验"，注入后加剧了过度防御。
故对 minimal_patch_hint / overdefense_pitfall 两类经验给检索加权。
"""

from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.retriever import HskTreeRetriever


def _node(iid, text, kind, cwe="1333"):
    n = SecurityInvariantNode(invariant_id=iid, cwe=cwe, high_level_invariant=text,
                              positive_principle=text, status="active")
    n.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    n.source = {"kind": kind}
    return n


def _task():
    return {"CWE_ID": "1333", "language": "python",
            "description": "regular expression validation", "security_policy": ""}


def test_antioverdefense_experience_gets_higher_score():
    """同文本下，抑制过度防御类经验的 base 分更高。"""
    plain = _node("plain", "Regular expressions must be anchored", "seed_from_diff")
    hint = _node("hint", "Regular expressions must be anchored", "minimal_patch_hint")
    r = HskTreeRetriever(HskTree(), antioverdefense_bonus=1.5)
    s_plain = r.base_score(_task(), plain, max_utility=1.0)
    s_hint = r.base_score(_task(), hint, max_utility=1.0)
    assert s_hint - s_plain == 1.5


def test_pitfall_experience_ranked_first():
    """检索结果里，抑制过度防御类经验应排在普通安全原则之前。"""
    tree = HskTree()
    tree.insert_node(_node("plain", "Regular expressions must be anchored", "seed_from_diff"))
    tree.insert_node(_node("hint", "Regular expressions must be anchored", "minimal_patch_hint"))
    r = HskTreeRetriever(tree, antioverdefense_bonus=1.5)
    out = r.search(_task(), limit=2)
    assert out[0]["invariant_id"] == "hint"


def test_bonus_zero_restores_neutral_ranking():
    """关闭加权（=0）时不再有类型偏好。"""
    tree = HskTree()
    tree.insert_node(_node("plain", "Regular expressions must be anchored", "seed_from_diff"))
    tree.insert_node(_node("hint", "Regular expressions must be anchored", "minimal_patch_hint"))
    r = HskTreeRetriever(tree, antioverdefense_bonus=0.0)
    a = r.base_score(_task(), tree.family("1333").invariants[0], max_utility=1.0)
    b = r.base_score(_task(), tree.family("1333").invariants[1], max_utility=1.0)
    assert abs(a - b) < 1e-9


def test_negative_only_experience_gets_half_bonus():
    """纯负向红线（无正向原则）给半额加权。"""
    n = SecurityInvariantNode(invariant_id="guard", cwe="1333",
                              high_level_invariant="do not clear return values",
                              positive_principle="", negative_guardrail="do not clear return values",
                              status="active")
    n.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    r = HskTreeRetriever(HskTree(), antioverdefense_bonus=1.0)
    assert r._type_bonus(n) == 0.5

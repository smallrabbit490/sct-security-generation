"""阶段 F 验收：HSK-Tree 检索器（CWE 硬路由 + active/language 过滤 + 效用分 + LLM 打分）。"""

from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.retriever import HskTreeRetriever


def _node(cwe, invariant, support=1, regression=0, status="active", langs=("python",)):
    node = SecurityInvariantNode(
        invariant_id=f"inv-{cwe}-{invariant[:4]}",
        cwe=cwe,
        high_level_invariant=invariant,
        applicability="path security",
        positive_principle="resolve before open",
        negative_guardrail="禁止前缀弱判断",
        support_count=support,
        regression_count=regression,
        status=status,
    )
    for lang in langs:
        node.language_leaves[lang] = LanguageLeaf(lang, ["resolve"], ["startswith"], "")
    return node


def _task(cwe="CWE-22", language="python", desc="open a user path"):
    return {"CWE_ID": cwe, "language": language, "description": desc, "security_policy": "path traversal"}


def test_strict_cwe_hard_routing():
    """strict_cwe 模式：只在同 CWE 分支内检索。"""
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "路径规范化"))
    tree.insert_node(_node("CWE-78", "命令注入"))
    r = HskTreeRetriever(tree)
    out = r.search(_task(cwe="CWE-22"), mode="strict_cwe")
    assert len(out) == 1 and out[0]["cwe"] == "CWE-22"
    assert r.search(_task(cwe="CWE-99"), mode="strict_cwe") == []


def test_cross_cwe_retrieval_when_no_same_cwe():
    """cross_cwe 模式：同 CWE 无经验时仍能靠语义召回其他 CWE 的经验。"""
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "path traversal resolve", langs=("python",)))
    r = HskTreeRetriever(tree)          # 无 requester：按语义重叠决定��否兜底
    # CWE-99 树里没有；strict 应返回空
    assert r.search({"CWE_ID": "CWE-99", "language": "python",
                     "description": "path traversal resolve bug"}, mode="strict_cwe") == []
    # cross 应能召回 CWE-22 的语义相近经验
    out = r.search({"CWE_ID": "CWE-99", "language": "python",
                    "description": "path traversal resolve bug"}, mode="cross_cwe")
    assert out and out[0]["cwe"] == "CWE-22"


def test_hybrid_falls_back_when_same_cwe_insufficient():
    """hybrid 模式：同 CWE 不足 limit 时用跨 CWE 语义兜底补足。"""
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "path traversal resolve", langs=("python",)))
    r = HskTreeRetriever(tree)
    out = r.search({"CWE_ID": "CWE-22", "language": "python",
                    "description": "path traversal resolve"}, limit=3, mode="hybrid")
    assert len(out) >= 1
    out_cross = r.search({"CWE_ID": "CWE-99", "language": "python",
                          "description": "path traversal resolve"}, limit=3, mode="hybrid")
    assert out_cross, "hybrid 应在同 CWE 为空时跨 CWE 兜底"


def test_language_filter_blocks_missing_leaf():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "路径规范化", langs=("python",)))
    r = HskTreeRetriever(tree)
    assert r.search(_task(language="go"), mode="strict_cwe") == []
    assert len(r.search(_task(language="python"), mode="strict_cwe")) == 1


def test_status_active_whitelist():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "活跃节点", status="active"))
    tree.insert_node(_node("CWE-22", "退役节点", status="retired"))
    r = HskTreeRetriever(tree)
    out = r.search(_task(), mode="strict_cwe")
    assert len(out) == 1
    assert out[0]["high_level_invariant"] == "活跃节点"


def test_base_score_includes_utility():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "高效用", support=10, regression=0))
    tree.insert_node(_node("CWE-22", "低效用", support=0, regression=3))
    r = HskTreeRetriever(tree)
    out = r.search(_task())
    assert out[0]["high_level_invariant"] == "高效用"
    assert out[0]["_base_score"] > out[1]["_base_score"]


def test_llm_reorder_by_score():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "正例经验"))
    tree.insert_node(_node("CWE-22", "反例经验"))

    def fake_requester(prompt):
        if "正例经验" in prompt:
            return {"choices": [{"message": {"content": '{"score": 0.9, "reason": "强相关"}'}}]}
        return {"choices": [{"message": {"content": '{"score": 0.1, "reason": "弱相关"}'}}]}

    r = HskTreeRetriever(tree, requester=fake_requester)
    out = r.search(_task(), limit=2)
    assert out[0]["high_level_invariant"] == "正例经验"
    assert out[0]["_llm_score"] == 0.9


def test_llm_bad_output_degrades():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "节点"))

    def bad_requester(prompt):
        return {"choices": [{"message": {"content": "no json"}}]}

    r = HskTreeRetriever(tree, requester=bad_requester)
    out = r.search(_task(), limit=1)
    assert len(out) == 1
    assert out[0]["_align_error"] is not None


def test_card_contains_dual_track_and_leaf():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "路径规范化"))
    r = HskTreeRetriever(tree)
    card = r.search(_task())[0]
    assert card["positive_principle"]
    assert card["negative_guardrail"]
    assert card["language_leaf"]["safe_constructs"] == ["resolve"]
    assert card["language_leaf"]["prohibited_constructs"] == ["startswith"]
    assert card["utility"] is not None


def test_empty_tree_returns_empty():
    r = HskTreeRetriever(HskTree())
    assert r.search(_task()) == []
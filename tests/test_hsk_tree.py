"""阶段 A 验收：HSK-Tree 数据结构与拓扑演化。"""

from methods.sct_trajectory.hsk_tree import (
    HskTree,
    LanguageLeaf,
    SecurityInvariantNode,
    absorb_or_new,
    consolidate_family,
    prune_by_utility,
    tfidf_overlap,
    utility_score,
)


def _node(cwe="CWE-22", invariant="规范化路径", support=1, regression=0, status="active"):
    return SecurityInvariantNode(
        invariant_id=f"inv-{cwe}-{invariant[:4]}",
        cwe=cwe,
        high_level_invariant=invariant,
        applicability="path traversal",
        positive_principle="resolve before open",
        negative_guardrail="禁止前缀弱判断",
        support_count=support,
        regression_count=regression,
        status=status,
        language_leaves={"python": LanguageLeaf("python", ["Path.resolve"], ["startswith"], "")},
    )


def test_utility_formula():
    # Utility = (support+1)/(regression+1)
    assert utility_score(1, 0) == 2.0
    assert utility_score(0, 0) == 1.0
    assert utility_score(0, 1) == 0.5


def test_tree_routing_by_cwe():
    tree = HskTree()
    tree.insert_node(_node("CWE-22"))
    tree.insert_node(_node("CWE-78", "命令注入"))
    assert tree.family("CWE-22") is not None
    assert len(tree.active_invariants("CWE-22")) == 1
    assert len(tree.active_invariants("CWE-78")) == 1
    assert tree.active_invariants("CWE-999") == []


def test_language_filter():
    tree = HskTree()
    tree.insert_node(_node("CWE-22"))
    # 该节点只有 python 叶，按 go 过滤应为空
    assert tree.active_invariants("CWE-22", language="python")
    assert tree.active_invariants("CWE-22", language="go") == []


def test_absorb_when_overlap_high():
    fam = HskTree().ensure_family("CWE-22")
    existing = _node("CWE-22", "解析路径必须处于受信根目录白名单")
    fam.invariants.append(existing)
    new = _node("CWE-22", "解析路径必须处于受信根目录白名单")
    new.negative_guardrail = "禁止直接拼接用户路径"
    result = absorb_or_new(fam, new)
    assert result == f"absorbed:{existing.invariant_id}"
    assert "禁止直接拼接用户路径" in existing.negative_guardrail
    assert len(fam.invariants) == 1  # 未新增节点


def test_new_when_overlap_low():
    fam = HskTree().ensure_family("CWE-22")
    a = _node("CWE-22", "路径规范化")
    b = _node("CWE-22", "输入编码转义")
    # 让两者在正例原则上也不同，否则 shared positive_principle 会抬高重叠度
    b.positive_principle = "encode before emit"
    fam.invariants.append(a)
    result = absorb_or_new(fam, b)
    assert result == "new"
    assert len(fam.invariants) == 2


def test_prune_by_utility():
    fam = HskTree().ensure_family("CWE-22")
    fam.invariants.append(_node("CWE-22", "坏节点", support=0, regression=3))  # utility=1/4=0.25
    fam.invariants.append(_node("CWE-22", "好节点", support=5, regression=0))   # utility=6
    n = prune_by_utility(fam)
    assert n == 1
    assert fam.invariants[0].status == "retired"


def test_consolidate_when_over_limit():
    fam = HskTree().ensure_family("CWE-22")
    for i in range(5):
        fam.invariants.append(_node("CWE-22", f"不变式{i}"))
    merged = consolidate_family(
        fam,
        consolidator=lambda nodes: SecurityInvariantNode(
            invariant_id="inv-merged",
            cwe="CWE-22",
            high_level_invariant="合并后的高阶不变量",
            positive_principle="统一修复准则",
            support_count=sum(n.support_count for n in nodes),
            regression_count=sum(n.regression_count for n in nodes),
        ),
    )
    assert merged is not None
    assert merged.status == "active"
    # 原 5 个节点全部归档为 consolidated
    assert sum(1 for n in fam.invariants if n.status == "consolidated") == 5
    assert sum(1 for n in fam.invariants if n.status == "active") == 1


def test_consolidate_not_triggered_below_limit():
    fam = HskTree().ensure_family("CWE-22")
    fam.invariants.append(_node("CWE-22", "a"))
    assert consolidate_family(fam, consolidator=lambda n: n[0]) is None


def test_serialization_roundtrip():
    tree = HskTree()
    tree.insert_node(_node("CWE-22"))
    d = tree.to_dict()
    assert "CWE-22" in d
    import json

    assert json.loads(json.dumps(d))["CWE-22"]["invariants"][0]["status"] == "active"
    rows = tree.to_jsonl()
    assert rows[0]["cwe"] == "CWE-22"
    assert rows[0]["utility"] is not None
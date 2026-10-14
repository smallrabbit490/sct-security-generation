"""阶段 G2 验收：unmeasured 经验不会被重复审计（成本不变量）。

背景：第一条改动把 Δ=0 的经验标为 `unmeasured`（不晋升、保留在池里参与检索）。
若审计目标筛选只看"未处理"而漏掉这个状态，每轮都会重复审计同一批零证据经验，
成本按轮数线性浪费。本测试锁住这个不变量。
"""

from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory.error_ledger import ErrorLedger
from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode


class _Stub:
    def __call__(self, prompt):
        return {"choices": [{"message": {"content": "{}"}}]}


def _node(iid, status):
    n = SecurityInvariantNode(invariant_id=iid, cwe="1333",
                              high_level_invariant="anchor the regex",
                              positive_principle="anchor", status=status)
    n.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return n


def test_only_provisional_entries_are_audit_targets():
    """只有 provisional 的经验会被选为审计目标。"""
    r = CleRunner(_Stub(), HskTree(), ErrorLedger(), workers=1)
    for iid, st in [("p1", "provisional"), ("u1", "unmeasured"), ("a1", "active"),
                    ("d1", "retired"), ("r1", "revised"), ("c1", "consolidated")]:
        r.experience_pool.append(_node(iid, st))

    targets = [e for e in r.experience_pool if e.status == "provisional"]
    assert [t.invariant_id for t in targets] == ["p1"], (
        "只有 provisional 应成为审计目标；unmeasured 不得被重复审计")


def test_unmeasured_entries_stay_retrievable():
    """unmeasured 经验仍留在池里（降级处理：不污染树，但知识不浪费）。"""
    r = CleRunner(_Stub(), HskTree(), ErrorLedger(), workers=1)
    r.experience_pool.append(_node("u1", "unmeasured"))
    assert len(r.experience_pool) == 1
    assert r.experience_pool[0].status == "unmeasured"


def test_unmeasured_nodes_are_retrievable_by_default():
    """检索默认状态集合包含 unmeasured 之外的可检索状态，且不报错。"""
    from methods.sct_trajectory.retriever import HskTreeRetriever

    tree = HskTree()
    tree.insert_node(_node("u1", "unmeasured"))
    tree.insert_node(_node("p1", "provisional"))
    retr = HskTreeRetriever(tree, requester=None)
    out = retr.search({"CWE_ID": "1333", "language": "python",
                       "description": "anchor regex", "security_policy": ""}, limit=5)
    ids = {c["invariant_id"] for c in out}
    assert "p1" in ids, "provisional 应可检索"

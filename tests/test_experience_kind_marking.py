"""阶段 G2 验收：反过度防御类经验的 kind 标记必须存在（第四条）。

实测教训：`_node_from_hint` / `_node_from_pitfall` 早期没有设置 `source["kind"]`，
而检索器的 `_type_bonus()` 正是靠它加权，导致第四条（抑制过度防御加权）**完全空转**
（实测 0/36 命中）。本测试锁住工厂函数必须写入 kind。
"""

from methods.sct_trajectory.closed_loop import _node_from_hint, _node_from_pitfall


def test_hint_node_sets_kind():
    n = _node_from_hint({"cwe": "1333", "minimal_patch_hint": "只在匹配前加锚定符号",
                         "applicability": "python 正则"})
    assert n is not None
    assert n.source.get("kind") == "minimal_patch_hint"


def test_pitfall_node_sets_kind():
    n = _node_from_pitfall({"cwe": "1333", "overdefense_pitfall": "不要为通过测试而直接 return False"})
    assert n is not None
    assert n.source.get("kind") == "overdefense_pitfall"


def test_hint_node_kind_survives_insert_merge():
    """_insert_experience 合并 stage/task_id 时不得覆盖 kind。"""
    from methods.sct_trajectory.closed_loop import CleRunner
    from methods.sct_trajectory.error_ledger import ErrorLedger
    from methods.sct_trajectory.hsk_tree import HskTree

    class _Stub:
        def __call__(self, prompt):
            return {"choices": [{"message": {"content": "{}"}}]}

    r = CleRunner(_Stub(), HskTree(), ErrorLedger(), workers=1)
    n = _node_from_hint({"cwe": "1333", "minimal_patch_hint": "Anchor the regular expression before matching."})
    r._insert_experience(n, stage="phase1", task_id=1)
    kept = r.experience_pool[0]
    assert kept.source.get("kind") == "minimal_patch_hint"
    assert kept.source.get("stage") == "phase1"
    assert kept.source.get("task_id") == 1


def test_type_bonus_fires_for_factory_nodes():
    """工厂产出的节点确实能拿到加权（端到端）。"""
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever

    hint = _node_from_hint({"cwe": "1333", "minimal_patch_hint": "Anchor the regular expression before matching."})
    r = HskTreeRetriever(HskTree(), antioverdefense_bonus=1.5)
    assert r._type_bonus(hint) == 1.5

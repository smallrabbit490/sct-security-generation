"""阶段 G2 验收：经验池级去重（DOCX 6.3 就地吸收）。

背景（实测）：全量运行经验池 1284 条里有 230 对同 CWE 重叠≥0.6 的重复，
因为原先只有"入树"时才做吸收，而池是只增不减的。本测试确保池级去重生效。
"""

from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory.error_ledger import ErrorLedger
from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode


class _DummyRequester:
    def __call__(self, prompt):
        return {"choices": [{"message": {"content": "{}"}}]}


def _runner():
    return CleRunner(_DummyRequester(), HskTree(), ErrorLedger(), workers=1)


def _node(iid, text, cwe="1333", guardrail="", safe=None):
    n = SecurityInvariantNode(invariant_id=iid, cwe=cwe, high_level_invariant=text,
                              positive_principle=text, negative_guardrail=guardrail,
                              status="provisional")
    n.language_leaves["python"] = LanguageLeaf("python", safe or [], [], "")
    return n


def test_near_duplicate_is_absorbed_not_appended():
    """重叠≥0.6 的经验应被吸收，不新增池条目。"""
    r = _runner()
    a = _node("a1", "Regular expressions must be anchored to prevent partial matches in input validation")
    r._insert_experience(a, stage="phase1", task_id=1)
    b = _node("b1", "Regular expressions must be anchored to prevent partial matches in input validation",
              guardrail="avoid unbounded greedy match", safe=["re.fullmatch"])
    r._insert_experience(b, stage="phase1", task_id=2)
    assert len(r.experience_pool) == 1, "近似重复应被吸收，而非新增"
    kept = r.experience_pool[0]
    assert kept.invariant_id == "a1"
    assert "avoid unbounded greedy match" in kept.negative_guardrail   # 红线取并集
    assert "re.fullmatch" in kept.language_leaves["python"].safe_constructs  # 叶节点求并集
    assert kept.support_count >= 1
    assert r.absorb_count == 1


def test_distinct_experience_is_appended():
    """语义不同的经验应正常新增。"""
    r = _runner()
    r._insert_experience(_node("a1", "Regex patterns must be anchored to prevent partial matches"),
                         stage="phase1", task_id=1)
    r._insert_experience(_node("b1", "Cryptographic algorithms must come from an approved allowlist"),
                         stage="phase1", task_id=2)
    assert len(r.experience_pool) == 2
    assert getattr(r, "absorb_count", 0) == 0


def test_different_cwe_never_absorbed():
    """跨 CWE 不吸收（DOCX 要求根路由内物理隔离）。"""
    r = _runner()
    same_text = "Input must be validated against an explicit allowlist before use"
    r._insert_experience(_node("a1", same_text, cwe="1333"), stage="phase1", task_id=1)
    r._insert_experience(_node("b1", same_text, cwe="327"), stage="phase1", task_id=2)
    assert len(r.experience_pool) == 2


def test_empty_text_not_absorbed():
    """空文本不参与吸收判定（避免把空经验吸收掉有效经验）。"""
    r = _runner()
    r._insert_experience(_node("a1", "Input must be validated against an explicit allowlist"),
                         stage="phase1", task_id=1)
    r._insert_experience(_node("e1", ""), stage="phase1", task_id=2)
    assert len(r.experience_pool) == 2

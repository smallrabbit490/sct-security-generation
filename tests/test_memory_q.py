"""Q值的必要数值与持久化契约；不调用模型或执行任务代码。"""
import pytest

from methods.sct_trajectory.hsk_tree import (
    CWEFamilyNode, LanguageLeaf, SecurityInvariantNode, absorb_or_new, consolidate_family,
)
from methods.sct_trajectory.memory_q import rank_candidates, reward_from_evidence, update_adopted, update_q


def test_q_updates_and_old_memory_roundtrip():
    node = SecurityInvariantNode.from_dict({"invariant_id": "old", "cwe": "22"})
    assert (node.q_value, node.q_visits) == (0.0, 0)
    node.q_value = update_q(node.q_value, -1)
    assert node.q_value == pytest.approx(-0.3)
    node.q_value = update_q(node.q_value, 1)
    node.q_visits = 2
    saved = SecurityInvariantNode.from_dict(node.to_dict())
    assert saved.q_value == pytest.approx(0.09)
    assert saved.q_visits == 2


def evidence(functional="pass", security="pass", **extra):
    return {"functional": {"status": functional}, "security": {"status": security}, **extra}


@pytest.mark.parametrize("f,s,reward", [("pass", "pass", 1), ("pass", "fail", -1),
                                        ("fail", "pass", -1), ("fail", "fail", -1),
                                        ("unmeasured", "pass", None)])
def test_rewards_require_both_measurements(f, s, reward):
    assert reward_from_evidence(evidence(f, s), code="def f(): return 1") == reward


@pytest.mark.parametrize("ev,code", [
    (evidence("fail", "fail"), ""),
    (evidence("fail", "fail", metadata={"dynamic_test": "error"}), "x"),
    ({"functional": {"status": "fail", "error_type": "environment_error"},
      "security": {"status": "pass"}}, "x"),
    ({"functional": {"status": "pass", "measured": False},
      "security": {"status": "pass"}}, "x"),
])
def test_empty_code_or_infrastructure_failure_has_no_reward(ev, code):
    assert reward_from_evidence(ev, code=code) is None


def test_only_adopted_unique_ids_receive_shared_reward_and_pool_is_enforced():
    nodes = {i: SecurityInvariantNode(i, "22", "rule") for i in ["a", "b", "retrieved_only"]}
    events = update_adopted(nodes, ["a", "a", "b"], evidence(), code="x", pool="D_grow")
    assert [e["invariant_id"] for e in events] == ["a", "b"]
    assert (nodes["a"].q_value, nodes["a"].q_visits) == (0.3, 1)
    assert nodes["b"].q_value == 0.3
    assert nodes["retrieved_only"].q_visits == 0
    update_adopted(nodes, ["a"], {}, code="x", pool="D_grow")
    assert nodes["a"].q_visits == 1
    with pytest.raises(ValueError, match="D_grow"):
        update_adopted(nodes, ["a"], evidence(), code="x", pool="D_gate")


def test_q_changes_members_without_crossing_similarity_threshold():
    scores = [{"id": str(i), "cosine": s} for i, s in enumerate([0.9, 0.8, 0.7, 0.6, 0.1])]
    q = {str(i): (-1 if i < 3 else 1) for i in range(5)}
    sim = rank_candidates(scores, q, delta=0.5, lambda_q=0)
    learned = rank_candidates(scores, q, delta=0.5, lambda_q=0.5)
    assert [s["id"] for s in sim] == ["0", "1", "2"]
    # 手算z分数组合后，0约0.382、3约0.195；第四张替换原第三张。
    assert [s["id"] for s in learned] == ["0", "3", "1"]
    assert "4" not in {s["id"] for s in learned}
    assert rank_candidates(scores, q, delta=0.95) == []


def test_constant_q_zero_variance_and_stable_ties():
    scores = [{"id": "b", "cosine": 0.8}, {"id": "a", "cosine": 0.8}]
    assert [s["id"] for s in rank_candidates(scores, {"a": 0, "b": 0}, delta=0.5)] == ["a", "b"]
    assert [s["id"] for s in rank_candidates(scores, {"a": 1, "b": 0}, delta=0.5)] == ["a", "b"]


def test_absorption_resets_learned_q_only_when_content_changes():
    existing = SecurityInvariantNode("a", "22", "same rule", positive_principle="same action",
        q_value=0.8, q_visits=5, status="active", language_leaves={"python": LanguageLeaf("python")})
    family = CWEFamilyNode("22", invariants=[existing])
    same = SecurityInvariantNode("b", "22", "same rule", positive_principle="same action")
    absorb_or_new(family, same)
    assert (existing.q_value, existing.q_visits) == (0.8, 5)
    same.negative_guardrail = "Preserve legal subdirectories."
    absorb_or_new(family, same)
    assert (existing.q_value, existing.q_visits) == (0, 0)
    existing.q_value, existing.q_visits = 0.4, 4
    merged = consolidate_family(family, lambda nodes: SecurityInvariantNode(
        "merged", "22", "combined rule", q_value=0.9, q_visits=7), max_active=0)
    assert (merged.q_value, merged.q_visits) == (0, 0)
    assert existing.status == "consolidated"
    assert (existing.q_value, existing.q_visits) == (0.4, 4)

"""阶段 G3 验收：层次化自顶向下检索（HTDR）。

用户 2026-09-22 要求：让 LLM 看到树的结构，从上往下逐层检索，
每层提取该层的标签与内容再继续下探；并与旧"逐候选 LLM 打分"机制做消融对比。

本测试锁住层次化检索的四条不变量：
  ① 三层各调用一次 LLM（共 3 次，显著少于旧机制的 recall_k 次）；
  ② 每层都能回退：任一层失败不得让检索整体失效；
  ③ 允许返回 0 条（用户要求"不需要 0 条也可以"）；
  ④ hier_rule（无 LLM 对照臂）不产生任何 LLM 调用。
"""

import json

from methods.sct_trajectory.hier_retrieval import (
    KIND_LABELS,
    build_l1_index,
    build_l2_index,
    build_l3_index,
    hierarchical_select,
)
from methods.sct_trajectory.hsk_tree import (
    HskTree,
    LanguageLeaf,
    SecurityInvariantNode,
)
from methods.sct_trajectory.retriever import HskTreeRetriever


def _node(iid: str, cwe: str, kind: str, text: str) -> SecurityInvariantNode:
    n = SecurityInvariantNode(invariant_id=iid, cwe=cwe, high_level_invariant=text,
                              positive_principle=text, status="provisional")
    n.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    n.source = {"kind": kind, "root_cause": f"{iid}-rc", "fix_directive": f"{iid}-fd"}
    return n


def _pool() -> list[SecurityInvariantNode]:
    return [
        _node("hint-74-1", "74", "minimal_patch_hint", "白名单校验用户输入"),
        _node("hint-74-2", "74", "minimal_patch_hint", "命令参数转义"),
        _node("pitfall-74-1", "74", "overdefense_pitfall", "不要无差别拒绝输入"),
        _node("hint-77-1", "77", "minimal_patch_hint", "shell 参数用列表传递"),
        _node("pitfall-77-1", "77", "overdefense_pitfall", "不要禁止所有特殊字符"),
        _node("stall-79-1", "79", "C_stalled", "功能反复修不好"),
    ]


def _requester(seq: list[dict], counter: dict):
    """按顺序返回预置 JSON 的假 requester，并统计调用次数。"""
    def call(prompt: str) -> dict:
        i = counter.get("n", 0)
        counter["n"] = i + 1
        payload = seq[i] if i < len(seq) else {}
        return {"choices": [{"message": {"content": json.dumps(payload)}}]}
    return call


def test_l1_index_lists_families_with_kind_breakdown():
    """L1 索引必须列出所有 CWE 家族，并带上类型分布（供 LLM 判断有无失败现场类经验）。"""
    text, cwes = build_l1_index(_pool())
    assert set(cwes) == {"74", "77", "79"}
    assert "CWE-74" in text and "CWE-77" in text
    # 类型分布必须出现，否则 LLM 只能看到条数、看不到"有没有可用的修法类经验"
    assert "minimal_patch_hint" in text


def test_l2_index_uses_semantic_labels():
    """L2 索引必须给每个 kind 配语义说明，而不是只报类型名。"""
    text, kinds = build_l2_index(_pool(), ["74", "77"])
    assert "minimal_patch_hint" in kinds
    for k in kinds:
        assert k in KIND_LABELS, f"{k} 缺语义说明，LLM 无法判断该选哪类"
        assert KIND_LABELS[k][:6] in text


def test_l3_index_exposes_failure_evidence():
    """L3 候选清单必须带上报错根因与建议修法（B 方案的失败现场）。"""
    text, id_map = build_l3_index(_pool(), ["74"], ["minimal_patch_hint"],
                                  language="python", rule_score=lambda n: 1.0)
    assert id_map
    assert "Root cause" in text and "Suggested fix" in text


def test_all_three_prompts_are_english_and_c_not_assumed_overdefense():
    import re
    nodes = [_node("x", "74", "C_stalled", "Function repeatedly fails after security passes")]
    sequence = iter([{"cwes": ["74"]}, {"kinds": ["C_stalled"]}, {"ids": ["x"]}])
    prompts = []
    def request(prompt):
        prompts.append(prompt)
        return {"choices": [{"message": {"content": json.dumps(next(sequence))}}]}
    chosen, _ = hierarchical_select(task={"language": "python", "description": "Process input"}, nodes=nodes,
        requester=request, language="python", rule_score=lambda n: 1., limit=3)
    assert len(chosen) == 1 and len(prompts) == 3
    assert not any(re.search(r"[\u3400-\u9fff]", prompt) for prompt in prompts)
    assert "overdefen" not in KIND_LABELS["C_stalled"].lower()
    assert "overdefen" not in KIND_LABELS["C_to_A"].lower()


def test_three_level_traversal_uses_three_calls():
    """三层各一次 LLM 调用 —— 这是相对旧机制（recall_k 次）的核心成本优势。"""
    counter: dict = {}
    seq = [{"cwes": ["74"]}, {"kinds": ["minimal_patch_hint"]},
           {"ids": ["hint-74-1"]}]
    chosen, trace = hierarchical_select(
        task={"CWE_ID": "74", "language": "python"},
        nodes=_pool(), requester=_requester(seq, counter), language="python",
        rule_score=lambda n: 1.0, limit=3, use_llm=True)
    assert counter["n"] == 3, f"应为 3 次调用，实际 {counter['n']}"
    assert [n.invariant_id for n in chosen] == ["hint-74-1"]
    assert trace["fallback"] is None
    assert len(trace["levels"]) == 3


def test_l1_sees_all_cwes_not_just_same_cwe():
    """L1 必须看到全量家族 —— 否则"先看全树再下探"退化成"只能选自己"。"""
    counter: dict = {}
    seq = [{"cwes": ["77"]}, {"kinds": ["overdefense_pitfall"]}, {"ids": []}]
    _, trace = hierarchical_select(
        task={"CWE_ID": "74", "language": "python"},
        nodes=_pool(), requester=_requester(seq, counter), language="python",
        rule_score=lambda n: 1.0, limit=3, use_llm=True)
    assert trace["levels"][0]["offered"] == 3, "L1 应看到 3 个家族"
    # 允许 LLM 选跨 CWE 家族（这是层次化检索相对 flat 的额外能力）
    assert trace["levels"][0]["picked"] == ["77"]


def test_allows_zero_selection():
    """允许返回 0 条（用户要求：不需要就不注入，宁缺毋滥）。"""
    counter: dict = {}
    seq = [{"cwes": ["74"]}, {"kinds": ["minimal_patch_hint"]}, {"ids": []}]
    chosen, _ = hierarchical_select(
        task={"CWE_ID": "74", "language": "python"},
        nodes=_pool(), requester=_requester(seq, counter), language="python",
        rule_score=lambda n: 1.0, limit=3, use_llm=True)
    assert chosen == []


def test_l3_failure_falls_back_to_rule_not_empty():
    """L3 调用失败必须回退到规则排序，不能返回空。

    为什么：返回空会让一次 API 抖动静默变成"这个任务没有经验可用"，
    而规则排序至少给出同 CWE 候选——降级但不失效。
    """
    def boom(prompt: str) -> dict:
        raise RuntimeError("api down")

    chosen, trace = hierarchical_select(
        task={"CWE_ID": "74", "language": "python"},
        nodes=_pool(), requester=boom, language="python",
        rule_score=lambda n: 1.0, limit=2, use_llm=True)
    assert chosen, "LLM 失败时应回退到规则排序，而不是返回空"
    assert trace["fallback"] == "L3_failed_rule_fallback"


def test_hier_rule_makes_no_llm_calls():
    """hier_rule 是无 LLM 对照臂，必须零调用。"""
    counter: dict = {}

    def counting(prompt: str) -> dict:
        counter["n"] = counter.get("n", 0) + 1
        return {"choices": [{"message": {"content": "{}"}}]}

    chosen, _ = hierarchical_select(
        task={"CWE_ID": "74", "language": "python"},
        nodes=_pool(), requester=counting, language="python",
        rule_score=lambda n: 1.0, limit=2, use_llm=False)
    assert counter.get("n", 0) == 0
    assert len(chosen) == 2


def test_retriever_exposes_retrieval_mode_and_returns_cards():
    """HskTreeRetriever 必须支持 retrieval_mode 并返回标准卡片结构。"""
    counter: dict = {}
    seq = [{"cwes": ["74"]}, {"kinds": ["minimal_patch_hint", "overdefense_pitfall"]},
           {"ids": ["hint-74-1", "pitfall-74-1"]}]
    r = HskTreeRetriever(HskTree(), requester=_requester(seq, counter),
                         retrieval_mode="hier_llm")
    cards = r.search({"CWE_ID": "74", "language": "python", "task_id": 1},
                     limit=3, pool_nodes=_pool())
    assert len(cards) == 2
    for c in cards:
        # 卡片必须能被 agent_pipeline.dual_track_text 正常渲染
        for key in ("invariant_id", "cwe", "high_level_invariant",
                    "positive_principle", "negative_guardrail"):
            assert key in c
    assert r.last_hier_trace is not None


def test_retriever_hier_rule_mode_no_llm():
    """hier_rule 模式下即使给了 requester 也不调用 LLM。"""
    counter: dict = {}

    def counting(prompt: str) -> dict:
        counter["n"] = counter.get("n", 0) + 1
        return {"choices": [{"message": {"content": "{}"}}]}

    r = HskTreeRetriever(HskTree(), requester=counting, retrieval_mode="hier_rule")
    cards = r.search({"CWE_ID": "74", "language": "python"}, limit=2, pool_nodes=_pool())
    assert counter.get("n", 0) == 0
    assert len(cards) == 2

"""第三步验收：经验载荷质量评分（Tier A 静态筛选）。

背景（2026-09-22 实测）：Phase3 门控只覆盖 72/4518 = 1.6%，而候选池里
18% 的载荷"注定读不到"（超长被截断 / 无失败现场 / 同卡自相矛盾）。
本测试锁住评分器的四条不变量：
  ① 干净载荷得满分且 usable；
  ② 会截断 / 无失败现场 / 多轮拼接 各自扣分并打标；
  ③ 疑似自相矛盾的载荷直接不可用（即使通过动态门控也无法被正确执行）；
  ④ 排序把高质量载荷排在前面（预算有限时先审它们）。
"""

from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
from methods.sct_trajectory.payload_quality import (
    payload_flags,
    payload_quality,
    rank_candidates,
    split_by_usability,
)


def _node(iid: str, **src) -> SecurityInvariantNode:
    n = SecurityInvariantNode(invariant_id=iid, cwe="79", high_level_invariant="x",
                              positive_principle="x", status="provisional")
    n.source = {"kind": "round_0_fail", **src}
    return n


def test_clean_payload_scores_full_and_usable():
    n = _node("a", root_cause="功能测试失败：返回 None",
              fix_directive="把白名单校验前置到解析完成之后，再进入核心处理循环，且不改变合法输入的返回值")
    q = payload_quality(n)
    assert q["score"] == 1.0
    assert q["usable"] is True
    assert q["flags"] == []


def test_truncation_is_flagged_and_penalised():
    n = _node("b", root_cause="x", fix_directive="改" * 1500)
    flags = payload_flags(n)
    assert "directive_truncated" in flags
    assert payload_quality(n)["score"] < 1.0


def test_missing_failure_evidence_is_penalised():
    n = _node("c")
    flags = payload_flags(n)
    assert "no_failure_evidence" in flags
    assert payload_quality(n)["score"] <= 0.7


def test_contradictory_multi_round_payload_is_unusable():
    """同卡内既要求"增加校验"又要求"移除校验" → 不可用。

    为什么直接排除而不是降权：这种载荷即使通过动态门控，
    注入后模型也只能在两条相反指令间随机二选一，无法被正确执行。
    """
    fd = "增加对输入的空字节校验，若含 \\x00 则返回 False —— 移除空字节校验（契约未要求）"
    n = _node("d", root_cause="x", fix_directive=fd)
    flags = payload_flags(n)
    assert "multi_round_concat" in flags
    assert "possible_contradiction" in flags
    q = payload_quality(n)
    assert q["usable"] is False


def test_rank_puts_clean_payloads_first():
    good = _node("good", root_cause="x",
                 fix_directive="把白名单校验前置到解析完成之后，再进入核心处理循环，且不改变合法输入的返回值")
    bad = _node("bad", root_cause="y", fix_directive="改" * 1500)
    ranked = rank_candidates([bad, good])
    assert ranked[0][0].invariant_id == "good"
    # 被截断的载荷仍然"可用"（只是排名靠后）——只有自相矛盾才判不可用
    usable, unusable = split_by_usability([bad, good])
    assert [n.invariant_id for n in usable] == ["good", "bad"]
    assert unusable == []


def test_bloated_guardrail_is_flagged():
    n = _node("e", root_cause="x",
              fix_directive="只在解析完成后插入一次与目标语义对齐的规范化步骤，不增加新的拒绝条件")
    n.negative_guardrail = "避免过度防御" * 400      # 2400 字
    assert "guardrail_bloated" in payload_flags(n)


def test_scorer_never_raises_on_empty_source():
    n = SecurityInvariantNode(invariant_id="f", cwe="79", high_level_invariant="",
                              status="provisional")
    n.source = {}
    q = payload_quality(n)
    assert 0.0 <= q["score"] <= 1.0
    assert q["usable"] in (True, False)

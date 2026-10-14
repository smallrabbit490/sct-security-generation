"""阶段 D 验收：四步子 Agent 流水线（Analysis 功能不变量 + Planning 三键 + CodeGen 局部补丁）。"""

from methods.sct_trajectory.agent_pipeline import (
    compute_patch_diff,
    dual_track_text,
    parse_analysis,
    parse_planning,
    run_pipeline,
    strip_code_fence,
)

TASK = {"function_name": "foo", "description": "read file"}

VALID_ANALYSIS = (
    '{"vulnerability_hypothesis": ["CWE-22 path traversal"], '
    '"untrusted_inputs": ["user_path"], '
    '"functional_invariants": ["Preserve foo signature and return contract", "Valid input: relative paths within the trusted directory"], '
    '"attack_surface": ["File reading"]}'
)

VALID_PLAN = (
    '{"Preserved_Func": "Preserve foo signature and return contract", '
    '"Patch_Scope": "Use resolve and check containment before open", '
    '"Avoidance_List": ["No complete rewrite", "Do not empty return values"]}'
)


def test_parse_analysis_fields():
    parsed = parse_analysis(VALID_ANALYSIS)
    assert "CWE-22" in parsed["vulnerability_hypothesis"][0]
    assert parsed["untrusted_inputs"] == ["user_path"]
    assert len(parsed["functional_invariants"]) == 2  # 含合法输入边界
    assert parsed["attack_surface"]


def test_parse_analysis_missing_invariants_flagged():
    bad = '{"vulnerability_hypothesis": ["x"], "functional_invariants": []}'
    try:
        parse_analysis(bad)
        raise AssertionError("应抛错")
    except ValueError as e:
        assert "incomplete" in str(e)


def test_parse_planning_three_keys():
    parsed = parse_planning(VALID_PLAN)
    assert parsed["Preserved_Func"] and "foo" in parsed["Preserved_Func"]
    assert parsed["Patch_Scope"] and "resolve" in parsed["Patch_Scope"]
    assert parsed["Avoidance_List"] == ["No complete rewrite", "Do not empty return values"]


def test_parse_planning_incomplete_flagged():
    bad = '{"Preserved_Func": "x", "Patch_Scope": ""}'
    try:
        parse_planning(bad)
        raise AssertionError("应抛错")
    except ValueError as e:
        assert "incomplete" in str(e)


def test_compute_patch_diff():
    before = "def foo(p):\n    return open(p)\n"
    after = "def foo(p):\n    return open(resolve(p))\n"
    diff = compute_patch_diff(before, after)
    assert "-    return open(p)" in diff
    assert "+    return open(resolve(p))" in diff
    assert compute_patch_diff("", after) == ""
    assert compute_patch_diff(before, before) == ""


def test_dual_track_text_tags():
    """经验按类型分标签：Validated invariant / Recommended method / Negative guardrail（防过度防御的关键）。"""
    cards = [
        {"polarity": "positive", "principle": "先规范化再打开", "constraint_type": "hard_invariant"},
        {"polarity": "positive", "principle": "可考虑增加长度限制", "constraint_type": "soft_guidance"},
        {"polarity": "negative", "forbidden_patterns": "禁止前缀弱判断"},
    ]
    text = dual_track_text(cards)
    assert "Validated invariant" in text
    assert "Recommended method" in text and "preserve the task contract" in text
    assert "Negative guardrail" in text
    # Recommended method必须排在Validated invariant之后（先满足硬约束，再参考手法建议）
    assert text.index("Validated invariant") < text.index("Recommended method")


def test_constraint_type_falls_back_to_kind():
    """缺陷1 修复：constraint_type 缺失时按 kind 判定，不能全部降级成"仅供参考"。

    取证依据：constraint_type 原先只由 experience_filter.py 设置，而
    filter_experiences 默认 False → 实测 0/219 条经验渲染成【Validated invariant】。
    """
    # 已证实正确的 kind → Validated invariant
    text = dual_track_text([{"kind": "direct_A", "positive_principle": "用白名单校验"}])
    assert "Validated invariant" in text, "已证实正确的经验必须能成为硬约束"
    # 最小改动手法 → Recommended method（不是硬约束，避免诱发过度防御）
    text2 = dual_track_text([{"kind": "minimal_patch_hint", "positive_principle": "只改正则模式"}])
    assert "Recommended method" in text2
    assert "Validated invariant" not in text2
    # 陷阱类 → Negative guardrail
    text3 = dual_track_text([{"kind": "overdefense_pitfall", "negative_guardrail": "别无差别拒绝"}])
    assert "Negative guardrail" in text3
    # 显式 constraint_type 优先于 kind 兜底
    text4 = dual_track_text([{"kind": "direct_A", "positive_principle": "x",
                              "constraint_type": "soft_advice"}])
    assert "Recommended method" in text4, "显式 constraint_type 必须优先"


def test_long_directive_not_silently_truncated():
    """缺陷2 修复：超长指令截断时必须显式标注，不能让模型把残句当完整指令。"""
    long_fd = "改这里" * 500          # 1500 字，超过 1200 上限
    text = dual_track_text([{"kind": "round_0_fail", "fix_directive": long_fd,
                             "root_cause": "失败"}])
    assert "truncated: original text" in text, "截断必须显式标注"


def test_multi_round_directive_prefers_latest():
    """缺陷3 修复：多轮「——」拼接的指令必须拆段并以最新为准，消除同卡矛盾。"""
    fd = "先做空字节检查，若含 \\x00 则返回 False —— 完全移除空字节检查（契约未要求）"
    text = dual_track_text([{"kind": "round_1_fail", "fix_directive": fd,
                             "root_cause": "失败"}])
    assert "完全移除空字节检查" in text
    # 旧的那条必须被标注为历史、possibly superseded，而不是并列呈现让模型二选一
    assert "Historical fixes" in text and "possibly superseded" in text


def test_success_card_not_under_failure_header():
    """缺陷4 修复：成功范例不应挂在【失败现场】标题下（标签与内容矛盾）。"""
    text = dual_track_text([{"kind": "direct_A",
                             "root_cause": "【安全测试通过，无失败】",
                             "fix_directive": "保持现有写法"}])
    assert "[Observed successful approach: source sample passed]" in text
    assert "[Failure context from measured execution]" not in text


def test_dual_track_text_empty(): 
    assert dual_track_text([]) == "[No experience]"


def test_run_pipeline_offline_no_requester():
    result = run_pipeline(TASK, cards=[])
    assert result["error_type"] is None
    assert result["analysis_parsed"].get("unmeasured") is True
    assert result["code"] == ""


def test_run_pipeline_with_mock_requester():
    calls = []

    def fake(prompt):
        calls.append(prompt)
        if "security and functional-contract analyst" in prompt:
            return {"choices": [{"message": {"content": VALID_ANALYSIS}}]}
        if "security planning expert" in prompt:
            return {"choices": [{"message": {"content": VALID_PLAN}}]}
        return {"choices": [{"message": {"content": "```python\ndef foo(p): return open(resolve(p))\n```"}}]}

    result = run_pipeline(TASK, cards=[], requester=fake)
    assert result["error_type"] is None
    assert result["analysis_parsed"]["vulnerability_hypothesis"]
    assert result["plan_parsed"]["Avoidance_List"] == ["No complete rewrite", "Do not empty return values"]
    assert result["code"] == "def foo(p): return open(resolve(p))"
    assert len(calls) == 3  # analysis + planning + generation（retrieval 不调 LLM）


def test_run_pipeline_reference_code_produces_diff():
    reference = "def foo(p):\n    return open(p)\n"

    def fake(prompt):
        if "security and functional-contract analyst" in prompt:
            return {"choices": [{"message": {"content": VALID_ANALYSIS}}]}
        if "security planning expert" in prompt:
            return {"choices": [{"message": {"content": VALID_PLAN}}]}
        return {"choices": [{"message": {"content": "def foo(p):\n    return open(resolve(p))\n"}}]}

    result = run_pipeline(TASK, cards=[], requester=fake, reference_code=reference)
    assert result["patch_diff"] != ""
    assert "-    return open(p)" in result["patch_diff"]


def test_strip_code_fence():
    assert strip_code_fence("```python\ndef f(): pass\n```") == "def f(): pass"
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
    '{"vulnerability_hypothesis": ["CWE-22 路径遍历"], '
    '"untrusted_inputs": ["user_path"], '
    '"functional_invariants": ["函数名 foo 与参数/返回值契约不变", "合法输入：受信目录内相对路径"], '
    '"attack_surface": ["文件读取"]}'
)

VALID_PLAN = (
    '{"Preserved_Func": "保持 foo 的签名与返回契约", '
    '"Patch_Scope": "在 open 前加 resolve 规范化校验", '
    '"Avoidance_List": ["禁止整体重写", "禁止清空返回"]}'
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
    assert parsed["Avoidance_List"] == ["禁止整体重写", "禁止清空返回"]


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
    """经验按类型分标签：硬不变量 / 软建议 / 负向红线（防过度防御的关键）。"""
    cards = [
        {"polarity": "positive", "principle": "先规范化再打开", "constraint_type": "hard_invariant"},
        {"polarity": "positive", "principle": "可考虑增加长度限制", "constraint_type": "soft_guidance"},
        {"polarity": "negative", "forbidden_patterns": "禁止前缀弱判断"},
    ]
    text = dual_track_text(cards)
    assert "硬不变量" in text
    assert "软建议" in text and "不得为满足它而破坏功能" in text
    assert "负向红线" in text
    # 软建议必须排在硬不变量之后（先满足硬约束，再参考软建议）
    assert text.index("硬不变量") < text.index("软建议")


def test_dual_track_text_empty(): 
    assert dual_track_text([]) == "（无经验）"


def test_run_pipeline_offline_no_requester():
    result = run_pipeline(TASK, cards=[])
    assert result["error_type"] is None
    assert result["analysis_parsed"].get("unmeasured") is True
    assert result["code"] == ""


def test_run_pipeline_with_mock_requester():
    calls = []

    def fake(prompt):
        calls.append(prompt)
        if "安全与业务分析专家" in prompt:
            return {"choices": [{"message": {"content": VALID_ANALYSIS}}]}
        if "安全规划专家" in prompt:
            return {"choices": [{"message": {"content": VALID_PLAN}}]}
        return {"choices": [{"message": {"content": "```python\ndef foo(p): return open(resolve(p))\n```"}}]}

    result = run_pipeline(TASK, cards=[], requester=fake)
    assert result["error_type"] is None
    assert result["analysis_parsed"]["vulnerability_hypothesis"]
    assert result["plan_parsed"]["Avoidance_List"] == ["禁止整体重写", "禁止清空返回"]
    assert result["code"] == "def foo(p): return open(resolve(p))"
    assert len(calls) == 3  # analysis + planning + generation（retrieval 不调 LLM）


def test_run_pipeline_reference_code_produces_diff():
    reference = "def foo(p):\n    return open(p)\n"

    def fake(prompt):
        if "安全与业务分析专家" in prompt:
            return {"choices": [{"message": {"content": VALID_ANALYSIS}}]}
        if "安全规划专家" in prompt:
            return {"choices": [{"message": {"content": VALID_PLAN}}]}
        return {"choices": [{"message": {"content": "def foo(p):\n    return open(resolve(p))\n"}}]}

    result = run_pipeline(TASK, cards=[], requester=fake, reference_code=reference)
    assert result["patch_diff"] != ""
    assert "-    return open(p)" in result["patch_diff"]


def test_strip_code_fence():
    assert strip_code_fence("```python\ndef f(): pass\n```") == "def f(): pass"
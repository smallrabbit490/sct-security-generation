"""经验注入前过滤模块验收：类型标注 + 过度防御风险判定 + 保守放行。"""

from methods.sct_trajectory.experience_filter import (
    assess_experience,
    build_assessment_prompt,
    filter_experiences,
)

TASK = {"function_name": "get_domain", "description": "extract domain from email"}


def _responder(payload: str):
    def fake(prompt):
        return {"choices": [{"message": {"content": payload}}]}
    return fake


def test_assess_hard_invariant_low_risk():
    out = assess_experience(TASK, {"positive_principle": "打开前规范化路径"},
                            _responder('{"type":"hard_invariant","risk":0.1,"reason":"局部改动可满足"}'))
    assert out["type"] == "hard_invariant"
    assert out["risk"] == 0.1
    assert out["error"] is None


def test_assess_soft_guidance_high_risk():
    out = assess_experience(TASK, {"positive_principle": "增加更多校验层"},
                            _responder('{"type":"soft_guidance","risk":0.9,"reason":"可能拒绝合法输入"}'))
    assert out["type"] == "soft_guidance"
    assert out["risk"] == 0.9


def test_assess_invalid_type_defaults_soft():
    out = assess_experience(TASK, {"positive_principle": "x"},
                            _responder('{"type":"whatever","risk":0.5}'))
    assert out["type"] == "soft_guidance"


def test_assess_bad_json_conservative_pass():
    """解析失败必须保守放行（risk=0）并记录 error，避免过滤故障丢失全部经验。"""
    out = assess_experience(TASK, {"positive_principle": "x"}, _responder("not json"))
    assert out["risk"] == 0.0
    assert out["error"] is not None


def test_filter_drops_high_risk_keeps_low():
    cards = [
        {"invariant_id": "a", "positive_principle": "规范化路径"},
        {"invariant_id": "b", "positive_principle": "无差别拒绝输入"},
    ]

    def fake(prompt):
        if "规范化路径" in prompt:
            return {"choices": [{"message": {"content": '{"type":"hard_invariant","risk":0.2,"reason":"ok"}'}}]}
        return {"choices": [{"message": {"content": '{"type":"soft_guidance","risk":0.95,"reason":"过度防御"}'}}]}

    out = filter_experiences(TASK, cards, fake, risk_threshold=0.6)
    assert [c["invariant_id"] for c in out["kept"]] == ["a"]
    assert [c["invariant_id"] for c in out["dropped"]] == ["b"]
    # 保留的经验带类型标注，供 Planning 区分硬不变量/软建议
    assert out["kept"][0]["constraint_type"] == "hard_invariant"
    assert out["dropped"][0]["drop_reason"]


def test_filter_no_requester_passthrough():
    """无 requester（离线路径）时不过滤，原样返回。"""
    cards = [{"invariant_id": "a", "positive_principle": "x"}]
    out = filter_experiences(TASK, cards, None)
    assert out["kept"] == cards and out["dropped"] == []


def test_filter_empty_cards():
    out = filter_experiences(TASK, [], _responder("{}"))
    assert out["kept"] == [] and out["dropped"] == []


def test_assessment_prompt_mentions_over_defense():
    p = build_assessment_prompt(TASK, {"positive_principle": "x"})
    assert "过度防御" in p and "hard_invariant" in p
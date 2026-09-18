"""阶段 G2 验收：LLM 成本精确计数器（真实 usage 计费，缺失不默认 0）。"""

from methods.sct_trajectory.cost_tracker import CostTracker, global_tracker, reset_global


def _resp(pt, ct, cached=0):
    return {"choices": [{"message": {"content": "x"}}],
            "usage": {"prompt_tokens": pt, "completion_tokens": ct, "total_tokens": pt + ct,
                      "prompt_tokens_details": {"cached_tokens": cached}}}


def test_records_tokens_and_cost():
    t = CostTracker(model="deepseek-v3.2")
    t.set_stage("phase1")
    t.record("gen", _resp(1000, 500))
    snap = t.snapshot()
    b = snap["by_label"]["phase1.gen"]
    assert b["calls"] == 1
    assert b["prompt_tokens"] == 1000
    assert b["completion_tokens"] == 500
    assert b["total_tokens"] == 1500
    # 1000/1000*0.0012 + 500/1000*0.0018 = 0.0012 + 0.0009 = 0.0021
    assert abs(b["cost_ca"] - 0.0021) < 1e-9
    assert abs(snap["total"]["cost_ca"] - 0.0021) < 1e-9


def test_missing_usage_is_counted_not_zeroed():
    """缺 usage 必须计入 usage_missing，不能当成 0 token 悄悄变便宜。"""
    t = CostTracker(model="deepseek-v3.2")
    t.set_stage("phase1")
    t.record("gen", {"choices": []})          # 无 usage
    snap = t.snapshot()
    b = snap["by_label"]["phase1.gen"]
    assert b["calls"] == 1
    assert b["usage_missing"] == 1
    assert b["total_tokens"] == 0
    assert snap["total"]["usage_missing"] == 1


def test_error_calls_tracked_separately():
    t = CostTracker(model="deepseek-v3.2")
    t.set_stage("phase2")
    t.record_error("distill")
    b = t.snapshot()["by_label"]["phase2.distill"]
    assert b["calls"] == 1 and b["errors"] == 1 and b["usage_missing"] == 0


def test_stage_totals_group_by_prefix():
    t = CostTracker(model="deepseek-v3.2")
    t.set_stage("phase1")
    t.record("gen", _resp(100, 100))
    t.record("extract", _resp(100, 100))
    t.set_stage("phase2")
    t.record("distill", _resp(200, 0))
    st = t.stage_totals()
    assert st["phase1"]["calls"] == 2
    assert st["phase1"]["prompt_tokens"] == 200
    assert st["phase2"]["calls"] == 1
    assert st["phase1"]["total_tokens"] == 400


def test_cached_tokens_recorded():
    t = CostTracker(model="deepseek-v3.2")
    t.set_stage("phase1")
    t.record("gen", _resp(1000, 100, cached=800))
    assert t.snapshot()["by_label"]["phase1.gen"]["cached_tokens"] == 800


def test_unknown_model_reports_tokens_without_cost():
    """未���模型只报 token，不编造价格。"""
    t = CostTracker(model="some-unknown-model")
    t.set_stage("phase1")
    t.record("gen", _resp(1000, 1000))
    snap = t.snapshot()
    assert snap["pricing"] is None
    assert snap["total"]["cost_ca"] is None
    assert snap["total"]["total_tokens"] == 2000


def test_global_tracker_singleton():
    reset_global()
    a = global_tracker("deepseek-v3.2")
    b = global_tracker()
    assert a is b
    reset_global()

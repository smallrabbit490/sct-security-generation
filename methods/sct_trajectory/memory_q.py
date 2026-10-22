"""固定经验库的Q数值操作；不调用模型，不改变经验正文或生命周期。"""
from __future__ import annotations

import math
from statistics import fmean, pstdev


def update_q(value: float, reward: float, alpha: float = 0.3) -> float:
    """D_grow测量后的单步更新；调用方负责采用归因及禁止测试反馈回流。"""
    return value + alpha * (reward - value)


def reward_from_evidence(evidence: dict, *, code: str) -> float | None:
    """只接受同次非空代码的明确F/S测量；缺测、执行基础设施失败不产生奖励。"""
    if not code.strip() or evidence.get("error"):
        return None
    dynamic = (evidence.get("metadata") or {}).get("dynamic_test")
    if dynamic in ("error", "unmeasured"):
        return None
    values = [evidence.get(key) or {} for key in ("functional", "security")]
    infrastructure_errors = {"environment_error", "validator_exception", "backend_error", "runner_error"}
    if any(v.get("status") not in ("pass", "fail") or v.get("measured") is False
           or v.get("error_type") in infrastructure_errors for v in values):
        return None
    return 1.0 if all(v["status"] == "pass" for v in values) else -1.0


def update_adopted(nodes: dict, adopted_ids: list[str], evidence: dict, *, code: str,
                   pool: str, alpha: float = 0.3) -> list[dict]:
    """仅D_grow校准可写Q；按实际采用的唯一ID共享本次奖励，不推断单卡因果贡献。"""
    if pool != "D_grow":
        raise ValueError("Q updates require D_grow calibration")
    reward = reward_from_evidence(evidence, code=code)
    events = []
    for identifier in dict.fromkeys(adopted_ids):
        node = nodes[identifier]
        before = node.q_value
        if reward is not None:
            node.q_value = update_q(before, reward, alpha)
            node.q_visits += 1
        events.append({"invariant_id": identifier, "q_before": before, "reward": reward,
                       "q_after": node.q_value, "q_visits": node.q_visits,
                       "skip_reason": "incomplete_or_technical_measurement" if reward is None else None})
    if not events:
        events.append({"invariant_id": None, "reward": reward, "skip_reason": "no_adopted_experiences"})
    return events


def _z_scores(values: list[float]) -> list[float]:
    deviation = pstdev(values)
    if deviation == 0:
        return [0.0] * len(values)
    mean = fmean(values)
    return [(value - mean) / deviation for value in values]


def rank_coverage_candidates(scores: list[dict], visits: dict[str, int], *, delta: float = -1) -> list[dict]:
    """D_grow覆盖探针：仅将未学习卡提前，同组按余弦排序；不赋分、不截断、不写卡库。"""
    eligible = [dict(s, q_visits=visits[s['id']]) for s in scores if s['cosine'] > delta]
    return sorted(eligible, key=lambda s: (s['q_visits'] > 0, -s['cosine'], s['id']))


def rank_candidates(scores: list[dict], q_values: dict[str, float], *, delta: float,
                    lambda_q: float = 0.5, limit: int | None = 3) -> list[dict]:
    """同一召回集先过语义门槛，再在余下候选内组合z(sim)/z(Q)；不写经验。"""
    if not math.isfinite(delta) or not -1 <= delta <= 1 or not 0 <= lambda_q <= 1:
        raise ValueError("invalid_memory_q_selection_parameters")
    eligible = [dict(s, q_value=q_values[s["id"]]) for s in scores if s["cosine"] > delta]
    if not eligible or (limit is not None and limit <= 0):
        return []
    if any(not math.isfinite(s["cosine"]) or not math.isfinite(s["q_value"]) for s in eligible):
        raise ValueError("nonfinite_memory_q_score")
    similarities = _z_scores([s["cosine"] for s in eligible])
    utilities = _z_scores([s["q_value"] for s in eligible])
    for row, similarity, utility in zip(eligible, similarities, utilities):
        row.update(sim_z=similarity, q_z=utility, score=(1-lambda_q)*similarity + lambda_q*utility)
    ranked = sorted(eligible, key=lambda s: (-s["score"], -s["cosine"], s["id"]))
    # 新协议显式传None仅改变候选顺序；历史数值选卡仍保留最多三张。
    return ranked if limit is None else ranked[:min(limit, 3)]

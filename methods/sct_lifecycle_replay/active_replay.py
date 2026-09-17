"""依据重构文档中的不确定性、风险、覆盖缺口和成本选择回放任务。

所属阶段：验证驱动主动回放（文档 6 节）。输入是 Q_pool 中候选任务的信息
价值信号（uncertainty/risk/novelty/coverage_gap/cost）；输出是按
Score 排序的下一批任务选择。
职责边界：本模块只负责任务排序与选择，不负责经验有效性判定 —— 被选中
任务上生成的候选经验是否有效，仍由 A_audit 独立证据审查决定（文档 6.1）。
允许修改长期经验库：否——选择结果写入 replay_decisions.jsonl，不写记忆。
"""

from __future__ import annotations

from typing import Iterable


def replay_score(item: dict, weights: dict | None = None) -> float:
    """计算任务信息价值得分（文档 6.1 的 Score 公式）。

    Score = α·Uncertainty + β·Risk + γ·Novelty + δ·CoverageGap − λ·Cost
    默认权重 α=β=γ=δ=λ=1，可通过 weights 覆盖（{"uncertainty": ...} 等）。
    分数只负责选择任务，不能替代经验有效性判定。
    """
    w = weights or {}
    alpha = float(w.get("uncertainty", 1.0))
    beta = float(w.get("risk", 1.0))
    gamma = float(w.get("novelty", 1.0))
    delta = float(w.get("coverage_gap", 1.0))
    lam = float(w.get("cost", 1.0))
    return (
        alpha * float(item.get("uncertainty", 0))
        + beta * float(item.get("risk", 0))
        + gamma * float(item.get("novelty", 0))
        + delta * float(item.get("coverage_gap", 0))
        - lam * float(item.get("cost", 0))
    )


def select_replay_tasks(items: Iterable[dict], limit: int, weights: dict | None = None) -> list[dict]:
    """按分数降序选择 Q_pool 中的下一批任务。

    返回排序后的候选列表（全部带 replay_score 字段），由调用方决定
    取前 limit 个；同分按原始顺序保持稳定，保证可复现。
    """
    scored = []
    for index, item in enumerate(items):
        scored.append((replay_score(item, weights), index, item))
    scored.sort(key=lambda triple: (-triple[0], triple[1]))
    selected = [triple[2] for triple in scored[: max(0, limit)]]
    for item in selected:
        item["replay_score"] = replay_score(item, weights)
    return selected

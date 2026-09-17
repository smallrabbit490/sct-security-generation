"""冻结隔离与四态汇总报告（阶段 5）。

所属阶段：冻结后的最终离线评测统计；不含任何在线进化信号。
输入：RolloutTrace 列表（训练侧）或冻结后 Base/Plus 的四态标签列表。
输出：四态计数、转移统计、正/负例卡数量汇总；冻结态下拒绝对经验库的写操作。
验证证据：本模块只做统计与冻结守卫，不执行验证；写操作在冻结后抛异常。
失败类型：冻结后写经验/加候选 → freeze_violation 异常。
允许修改长期经验库：否——冻结后禁止一切写入。
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def summarize_four_states(traces: list[dict]) -> dict[str, Any]:
    """从轨迹列表汇总四态分布与转移类型计数。

    输入每条 trace 含 states（四态标签列表）与 transitions（before/after/kind）。
    返回 {"four_state": {...}, "transition_kinds": {...}, "gain_transitions": [...],
    "negative_transitions": [...]}。
    """
    state_counter: Counter = Counter()
    kind_counter: Counter = Counter()
    gain: list[dict] = []
    negative: list[dict] = []
    for t in traces:
        state_counter.update(t.get("states") or [])
        for tr in t.get("transitions") or []:
            kind = tr.get("kind") or "neutral"
            kind_counter[kind] += 1
            item = {"from": tr.get("before"), "to": tr.get("after"), "kind": kind}
            if kind == "gain":
                gain.append(item)
            elif kind == "negative":
                negative.append(item)
    return {
        "four_state": {k: state_counter[k] for k in ("A", "B", "C", "D") if state_counter.get(k)},
        "transition_kinds": dict(kind_counter),
        "gain_transitions": gain,
        "negative_transitions": negative,
    }


class FrozenGuard:
    """冻结守卫：包装一个可写目标，冻结后拒绝写入。

    用于在最终评测阶段强制 feedback_channel=disabled，防止 Base/Plus 结果回流。
    """

    def __init__(self, frozen: bool = False) -> None:
        self.frozen = frozen

    def freeze(self) -> None:
        self.frozen = True

    def write(self, item: dict) -> None:
        if self.frozen:
            raise RuntimeError("freeze_violation")
        # 正常场景由调用方实现持久化；这里只表达守卫语义。
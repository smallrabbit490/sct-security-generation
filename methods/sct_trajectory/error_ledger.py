"""错题本 Error Ledger（阶段 C，DOCX 5.2 全生命周期管理）。

所属阶段：Phase1 与 Phase2 共用的认知盲区/顽固失败记忆。
输入：错误条目（seed_grounding_failure 或 B/C/D_stalled 轨迹的脱敏失败类型）。
输出：错题本条目 + 三大消费接口（回放偏置 / Analysis 预警 / 归并负向边界）。
验证证据：本模块只做结构存储与消费接口，不执行动态验证；正确性由
   tests/test_error_ledger.py 覆盖。
失败类型：条目录入须脱敏（不含任务 ID、测试输入、答案常量）；difficulty 标记
   高难度（D_stalled / seed 双侧失败）。
允许修改长期经验库：否——错题本独立于 HSK-Tree，是旁路记忆。

三大消费场景（DOCX 5.2）：
  1. replay_bias：按各 CWE 失败密度返回采样权重，供主动回放调度器加权；
  2. analysis_warning：返回某 CWE 的历史高频陷阱文本，供 Analysis Agent 注入前置预警；
  3. merge_negative_boundary：返回某 CWE 的负向边界，供 HSK-Tree 离线归并时防止
     归纳出模型自身难以理解或极易踩坑的规则。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ErrorEntry:
    """一条错题本记录（脱敏）。"""

    cwe: str
    kind: str            # seed_grounding_failure | B_stalled | C_stalled | D_stalled
    failure_type: str    # 脱敏失败类型（如 security_gap / functional_regression / both_failed）
    source_hash: str     # 来源任务哈希（脱敏，不含任务 ID 明文）
    transition: str = ""  # 如 "B->B" / "D->D"；seed 失败时为空
    difficulty: str = "normal"  # normal | high

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ErrorEntry":
        return cls(
            cwe=str(value.get("cwe", "")),
            kind=str(value.get("kind", "")),
            failure_type=str(value.get("failure_type", "")),
            source_hash=str(value.get("source_hash", "")),
            transition=str(value.get("transition", "")),
            difficulty=str(value.get("difficulty", "normal")),
        )


class ErrorLedger:
    """错题本容器：录入 + 三消费接口。"""

    def __init__(self) -> None:
        self.entries: list[ErrorEntry] = []

    def add(self, entry: ErrorEntry) -> None:
        """录入一条错题；D_stalled 或 seed_grounding_failure 标记高难度。"""
        if entry.kind in ("D_stalled", "seed_grounding_failure"):
            entry.difficulty = "high"
        self.entries.append(entry)

    def add_many(self, entries: list[ErrorEntry]) -> None:
        for e in entries:
            self.add(e)

    # ---- 消费 1：回放调度偏置 ----

    def cwe_density(self) -> dict[str, int]:
        """按 CWE 统计失败密度，供主动回放调度器加权采样。"""
        return dict(Counter(e.cwe for e in self.entries))

    def replay_bias(self) -> dict[str, float]:
        """把 CWE 密度归一化为采样权重（密度越高权重越大，含平滑 +1）。"""
        density = self.cwe_density()
        if not density:
            return {}
        total = sum(density.values())
        return {cwe: round((n + 1) / (total + len(density)), 4) for cwe, n in density.items()}

    # ---- 消费 2：Analysis 前置预警 ----

    def analysis_warning(self, cwe: str, *, top: int = 3) -> list[str]:
        """返回某 CWE 的历史高频陷阱文本（脱敏），供 Analysis Agent 注入预警。

        每条形如「此前处理该 CWE 时反复因 <failure_type> 失败」，不含任务内容。
        """
        hits = [e for e in self.entries if e.cwe == cwe]
        patterns = Counter(
            f"此前处理该 CWE 时反复因 {e.failure_type or '未知原因'} 失败" for e in hits
        )
        return [text for text, _ in patterns.most_common(top)]

    # ---- 消费 3：归并负向边界 ----

    def merge_negative_boundary(self, cwe: str) -> list[str]:
        """返回某 CWE 的负向边界（失败类型集合），供归并时防止归纳出踩坑规则。

        即：该 CWE 下模型反复失败的 failure_type，归并时不得把这些盲区归纳成
        模型自身无法执行的规则。
        """
        return sorted({e.failure_type for e in self.entries if e.cwe == cwe and e.failure_type})

    def to_jsonl(self) -> list[dict]:
        return [e.to_dict() for e in self.entries]

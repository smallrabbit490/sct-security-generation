"""管理候选经验、独立审查和冻结后的长期经验库。

所属阶段：经验生命周期更新（文档 2.2、8.1/8.2 节）。本类对应文档的
M_t（长期记忆）、C_t（候选池）与冻结后的 M*。
状态语义：
- seed：来源池提取并经初始验证的起点知识（进入轨迹验证）；
- provisional：候选假设，等待独立审查（主动回放、独立审查）；
- supported：在独立任务上获得功能与安全证据支持（参与检索和跨语言适配）；
- narrowed：原则基本成立但适用条件需收窄（更新边界后重新审查）；
- revised：根据反例重写后的经验（重新进入 provisional）；
- demoted / retired：效用降低或被证伪（降低检索权重或停止使用）。
更新规则（文档 8.2）：每次更新保存 support_count / contradiction_count /
  last_used_round / utility_delta / related_experience_ids / evidence_refs，
  确保经验状态可追溯。
允许修改长期经验库：是——本类是唯一被允许通过 apply_audit 更新 M_t/C_t
  的模块；冻结后（freeze）拒绝任何写入。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Iterable


class ExperienceMemory:
    """对应文档中的 M_t、C_t 和冻结后的 M*。"""

    # 状态语义：supported 进入长期记忆并参与检索；narrowed 同样进入长期记忆
    # 但带适用条件收窄标记；revised 需要重新审查；demoted/retired 关闭候选。
    _PROMOTED = ("supported", "narrowed")
    _REVISED = ("revised",)
    _CLOSED = ("demoted", "retired", "rejected")

    def __init__(self, initial: Iterable[dict] = ()) -> None:
        self.long_term: list[dict] = [deepcopy(item) for item in initial]
        self.candidates: dict[str, dict] = {}
        self.frozen = False
        self.events: list[dict] = []
        self._round = 0

    def add_candidate(self, card: dict) -> None:
        """把候选放入 C_t；审查前禁止修改长期经验库。"""
        if self.frozen:
            raise RuntimeError("冻结后不能添加候选经验")
        card_id = str(card.get("id", ""))
        if not card_id:
            raise ValueError("候选经验缺少 id")
        self.candidates[card_id] = deepcopy(card)
        self.events.append({"event": "candidate_added", "id": card_id, "status": "provisional"})

    def _track(self, card: dict, status: str) -> dict:
        """为经验卡附加文档 8.2 的状态追踪字段，保证可追溯。"""
        card.setdefault("support_count", 0)
        card.setdefault("contradiction_count", 0)
        card.setdefault("last_used_round", self._round)
        card.setdefault("utility_delta", 0.0)
        card.setdefault("related_experience_ids", [])
        card.setdefault("evidence_refs", [])
        card["status"] = status
        return card

    def apply_audit(self, card_id: str, status: str) -> None:
        """根据独立证据更新经验状态。

        supported/narrowed：候选晋升进长期记忆并参与检索；
        revised：候选移回 provisional（由调用方补充反例证据后重新审查）；
        demoted/retired/rejected：候选关闭，不进入长期记忆。
        """
        if self.frozen:
            raise RuntimeError("冻结后不能更新经验")
        if card_id not in self.candidates and not any(item.get("id") == card_id for item in self.long_term):
            raise KeyError(card_id)
        if status in self._PROMOTED:
            card = self.candidates.pop(card_id, None)
            if card is not None:
                self.long_term.append(self._track(card, status))
                self.events.append({"event": "memory_updated", "id": card_id, "status": status})
        elif status in self._REVISED:
            # revised：保留候选但标记重写状态，等待重新审查（文档 8.1）。
            card = self.candidates.get(card_id)
            if card is not None:
                self._track(card, "revised")
                self.events.append({"event": "candidate_revised", "id": card_id, "status": "revised"})
        elif status in self._CLOSED:
            self.candidates.pop(card_id, None)
            self.events.append({"event": "candidate_closed", "id": card_id, "status": status})
        else:
            raise ValueError(f"未知经验状态: {status}")

    def retire(self, card_id: str) -> None:
        """把长期记忆中的经验标记为退役（停止参与检索）。

        对应文档 8.1 的 demoted→retired：经验长期无效或被证伪后退役。
        退役经验保留在 long_term 供审计追溯，但调用方（检索器）应通过
        active_cards() 排除 status=retired 的经验。
        """
        if self.frozen:
            raise RuntimeError("冻结后不能更新经验")
        for item in self.long_term:
            if item.get("id") == card_id:
                item["status"] = "retired"
                self.events.append({"event": "memory_retired", "id": card_id, "status": "retired"})
                return
        raise KeyError(card_id)

    def active_cards(self) -> list[dict]:
        """返回参与检索的经验（seed/supported/narrowed，排除 retired）。"""
        return [deepcopy(item) for item in self.long_term if item.get("status") != "retired"]

    def freeze(self) -> None:
        """冻结 M*；之后不得接受 Base/Plus 反馈或写入经验。"""
        self.frozen = True
        self.events.append({"event": "memory_frozen", "size": len(self.long_term)})

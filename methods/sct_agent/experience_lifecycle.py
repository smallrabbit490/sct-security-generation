"""经验候选的临时保存、晋升和冻结隔离。"""

from __future__ import annotations

from collections.abc import Iterable

try:
    from .schemas import ExperienceCard, FreezeManifest, GateRecord
except ImportError:  # 直接脚本执行时使用当前目录导入。
    from schemas import ExperienceCard, FreezeManifest, GateRecord


def can_update_memory(manifest: FreezeManifest) -> bool:
    """冻结评测期间禁止任何经验写入；``feedback_channel=disabled`` 是硬闸。"""
    return manifest.feedback_channel != "disabled"


def promote_cards(
    cards: Iterable[ExperienceCard], records: Iterable[GateRecord], manifest: FreezeManifest | None = None
) -> list[ExperienceCard]:
    """只把有对应 promote 记录的候选写入下一轮长期库。"""
    if manifest is not None and not can_update_memory(manifest):
        return []
    accepted = {record.candidate_id for record in records if record.decision == "promote"}
    return [card for card in cards if card.card_id in accepted or (card.card_id is None and accepted)]

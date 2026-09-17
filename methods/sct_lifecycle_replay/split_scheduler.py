"""把 PLT 变体分配到重构文档定义的三个功能池。"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .family_manifest import family_id_for_row

ROLES = ("source_pool", "replay_pool", "audit_pool")


def assign_family_variants(row_ids: Iterable[int], manifest: dict) -> dict[str, list[int]]:
    """按 family 内顺序轮换角色；不复制任务，结果可写入 split_manifest。"""
    grouped: dict[str, list[int]] = defaultdict(list)
    seen = set()
    for row_id in row_ids:
        if int(row_id) in seen:
            raise ValueError("duplicate_task_id")
        seen.add(int(row_id))
        grouped[family_id_for_row(manifest, int(row_id))].append(int(row_id))

    result = {role: [] for role in ROLES}
    for family_offset, family_id in enumerate(sorted(grouped)):
        for offset, row_id in enumerate(sorted(grouped[family_id])):
            result[ROLES[(family_offset + offset) % len(ROLES)]].append(row_id)
    return result

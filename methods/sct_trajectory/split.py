"""三池原子划分（阶段 G1，DOCX 表 7 公理 1）。

所属阶段：Phase 1 前的数据分区。
输入：PLT 行号列表 + family manifest（seed_family_id 映射）。
输出：{source_pool, replay_pool, audit_pool} 三个不相交池。
验证证据：本模块只做确定性划分，不执行验证；正确性由 tests/test_split.py 覆盖。
失败类型：重复 task_id 抛错；无 family 信息抛错。
允许修改长期经验库：否——纯划分。

核心约束（DOCX 表 7 公理 1，纠正旧 split_scheduler 的错误）：
  D_source ∩ D_replay ∩ D_audit = ∅；
  同一 Seed Family 旗下所有代码变体与文本扰动变体，必须【整体】划入且仅划入
  三池之一，严禁同族变体在训练侧与审查侧交叉。
  —— 划分粒度为 Seed Family（不是单个变体）：按 family 轮换分配，同一 family
     的所有变体一起进同一个池。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

ROLES = ("source_pool", "replay_pool", "audit_pool")


def group_by_family(row_ids: Iterable[int], family_id_fn) -> dict[str, list[int]]:
    """把行号按 seed_family_id 分组，检测重复 task_id。"""
    grouped: dict[str, list[int]] = defaultdict(list)
    seen: set[int] = set()
    for row_id in row_ids:
        rid = int(row_id)
        if rid in seen:
            raise ValueError(f"duplicate_task_id: {rid}")
        seen.add(rid)
        fid = family_id_fn(rid)
        if not fid:
            raise ValueError(f"row {rid} missing family id")
        grouped[str(fid)].append(rid)
    return {fid: sorted(ids) for fid, ids in grouped.items()}


def assign_families_atomic(row_ids: Iterable[int], family_id_fn) -> dict[str, list[int]]:
    """按 Seed Family 原子划分三池。

    与旧 split_scheduler.assign_family_variants 的差别：旧实现用
    `(family_offset + offset) % 3` 把同一 family 的变体散到不同池（违反公理 1）；
    本实现按【family 粒度】轮换，同一 family 的所有变体整体进同一个池。
    """
    grouped = group_by_family(row_ids, family_id_fn)
    result: dict[str, list[int]] = {role: [] for role in ROLES}
    for offset, fid in enumerate(sorted(grouped)):
        role = ROLES[offset % len(ROLES)]
        result[role].extend(grouped[fid])
    return result


def assert_disjoint(pools: dict[str, list[int]]) -> bool:
    """校验三池两两不相交（公理 1 的强断言）。"""
    sets = {k: set(v) for k, v in pools.items()}
    a, b, c = sets["source_pool"], sets["replay_pool"], sets["audit_pool"]
    return not (a & b) and not (a & c) and not (b & c)
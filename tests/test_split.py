"""阶段 G1 验收：三池原子划分（同 Seed Family 整体只入一池）。"""

from methods.sct_trajectory.split import (
    assert_disjoint,
    assign_families_atomic,
    group_by_family,
)


def _family_fn(mapping):
    return lambda rid: mapping.get(int(rid), "")


def test_same_family_stays_together():
    # family A 有 3 个变体，family B 有 2 个变体
    mapping = {1: "famA", 2: "famA", 3: "famA", 4: "famB", 5: "famB"}
    pools = assign_families_atomic([1, 2, 3, 4, 5], _family_fn(mapping))
    # family A 全部在同一个池
    famA_pool = [r for r, pools in pools.items() if 1 in pools][0]
    assert sorted(pools[famA_pool]) == [1, 2, 3]
    # family B 全部在同一个池（且与 A 不同池）
    famB_pool = [r for r, pools in pools.items() if 4 in pools][0]
    assert sorted(pools[famB_pool]) == [4, 5]
    assert famA_pool != famB_pool


def test_three_pools_disjoint():
    mapping = {i: f"fam{i}" for i in range(1, 10)}
    pools = assign_families_atomic(range(1, 10), _family_fn(mapping))
    assert assert_disjoint(pools) is True
    # 所有行号恰好分到三池之一
    total = sum(len(v) for v in pools.values())
    assert total == 9


def test_round_robin_across_families():
    mapping = {1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F"}
    pools = assign_families_atomic([1, 2, 3, 4, 5, 6], _family_fn(mapping))
    # 6 个 family 均分到三池，每池 2 个 family
    assert sorted(len(v) for v in pools.values()) == [2, 2, 2]


def test_duplicate_task_id_raises():
    mapping = {1: "A", 2: "A"}
    try:
        group_by_family([1, 1, 2], _family_fn(mapping))
        raise AssertionError("应抛错")
    except ValueError as e:
        assert "duplicate" in str(e)


def test_missing_family_raises():
    mapping = {1: "A"}
    try:
        assign_families_atomic([1, 2], _family_fn(mapping))
        raise AssertionError("应抛错")
    except ValueError as e:
        assert "missing" in str(e)
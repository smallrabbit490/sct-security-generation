"""阶段 G2 验收：已达 A 的任务绝不被强制重放（用户拍板 A 方案）。

实测缺陷（2026-09-21，afilter_test2 运行）：
  轮3 的强制重放列表包含 45/1126/1127 —— 这三个任务在轮2 末态已是 A。
  其中 1126 在轮3 从 A 退化成 D，属无意义重放（A 态任务重放产生不了新经验）。
根因：mandatory 在轮末重算时未清除"本轮已达 A"的旧条目。
本测试锁住两条不变量：
  ① 重算 mandatory 时，已达 A 的任务被 discard；
  ② 使用 forced_rows 前再按 passed_ids 过滤（双保险）。
"""

import inspect

from methods.sct_trajectory.closed_loop import CleRunner


def test_mandatory_discards_passed_tasks():
    """源码级不变量：mandatory 重算时必须 discard 已达 A 的任务。"""
    src = inspect.getsource(CleRunner.run_evolution_rounds)
    assert "mandatory.discard(tid)" in src, (
        "mandatory 重算未清除已达 A 的任务 → 已 A 任务会被无意义强制重放")
    assert "if tid in passed_ids:" in src


def test_forced_rows_filtered_by_passed_ids():
    """源码级不变量：forced_rows 构造时必须排除 passed_ids（双保险）。"""
    src = inspect.getsource(CleRunner.run_evolution_rounds)
    assert "i not in passed_ids" in src, (
        "forced_rows 未按 passed_ids 过滤 → 残留条目仍会重放已 A 任务")


def test_replay_candidates_exclude_passed_and_prev_round():
    """源码级不变量：重放候选排除'已达 A'与'上一轮已选'。"""
    src = inspect.getsource(CleRunner.run_evolution_rounds)
    assert "if tid in passed_ids:" in src, "未排除已达 A 的任务"
    assert "if tid in prev_round_chosen" in src, "未排除上一轮已选的任务"
    assert "prev_round_chosen = set(chosen)" in src, "prev_round_chosen 未更新"


def test_coverage_denominator_uses_pending_tasks():
    """覆盖率分母必须是'未通过任务'，且向上取整（否则永远够不到阈值）。"""
    src = inspect.getsource(CleRunner.run_evolution_rounds)
    assert "_pending = [r for r in replay_pool" in src
    assert "math.ceil(len(_pending)" in src, (
        "向下取整会让 17×0.75=12 → 12/17=70.6%，永远达不到 75% 的目标")

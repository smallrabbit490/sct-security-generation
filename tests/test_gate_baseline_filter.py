"""阶段 G2 验收：门控审计任务的"基线可测性标注"。

【2026-09-21 语义修正（缺陷 D19）】
原实现叫"筛选"，只保留基线 ∈ (0,1) 的任务，理由写作"基线 0 → Δ 数学上恒为 0"。
该理由是**错的**：基线 0 是**地板**不是天花板 —— Δ = 加经验 − 0 ≥ 0，可以为正
（能测出"有用"），只是不可能为负（测不出"有害"）。

实测依据（ab_verify_20260921 的 48 条审计明细）：
  基线 0.0 的 16 条候选里 **10 条测出了正 Δ**（如 seed-1055：0.0 → 0.6667）；
  17 条 supported 里 10 条来自基线 0，而 17 条 demoted **全部**来自基线 > 0。
→ 两类任务的分工是**互补而非替代**：基线 0 贡献正向证据，基线 > 0 贡献负向证据。
  按旧规则过滤掉基线 0，会丢掉 59% 的正向证据来源。

因此本模块现在的职责是**标注与排序，不剔除任何任务**：
  measurable（正负皆可测） → gain_only（仅可测增益） → 未探测/探测失败 → ceiling（仅可测有害）

探测策略的实测选型（v1 audit 池 298 条）保持不变：
  · audit 池前 20 条全部来自 CWE-1333 与 CWE-179，两者都处于可测区间
    → **顺序探测**命中率 20/20 = 100%
  · 曾按直觉改成"每 CWE 轮询探测"，实测命中率反而降到 8/20 = 40%
    （平摊到了 200/347/502 等"太难"的 CWE），已回退为顺序探测。
"""

from methods.sct_trajectory.gate_selector import filter_measurable_tasks


def _tasks(spec):
    """spec: [(cwe, index), ...]"""
    return [{"index": i, "CWE_ID": cwe, "task_description": {}} for cwe, i in spec]


def test_no_task_is_ever_dropped():
    """核心不变量：无论基线是多少，**一条都不许剔除**（D19）。"""
    tasks = _tasks([("1333", i) for i in range(6)])
    rates = {0: 0.0, 1: 0.0, 2: 0.5, 3: 1.0, 4: 0.5, 5: 0.0}

    def probe(rows, samples):
        return rates.get(rows[0]["index"], 0.0), []

    kept, info = filter_measurable_tasks(tasks, probe, max_probe=6)
    idx = sorted(t["index"] for t in kept)
    assert idx == list(range(6)), f"有任务被剔除：{sorted(set(range(6)) - set(idx))}"
    assert info["measurable"] == 2      # index 2、4 基线 0.5
    assert info["gain_only"] == 3       # index 0、1、5 基线 0.0
    assert info["ceiling"] == 1         # index 3 基线 1.0
    assert info["probed"] == 6
    assert info["kept"] == 6


def test_zero_baseline_tasks_are_kept():
    """D19 核心：基线 0 的任务必须保留（它们贡献正向证据）。"""
    tasks = _tasks([("1333", i) for i in range(4)])

    def probe(rows, samples):
        return 0.0, []

    kept, info = filter_measurable_tasks(tasks, probe, max_probe=4)
    assert len(kept) == 4, "基线全 0 时丢了任务 —— D19 回退"
    assert info["gain_only"] == 4


def test_ordering_most_discriminating_first():
    """排序：正负皆可测 → 仅可测增益 → 仅可测有害。"""
    tasks = _tasks([("1333", i) for i in range(6)])

    def probe(rows, samples):
        return [0.5, 0.0, 1.0][rows[0]["index"] % 3], []

    kept, _ = filter_measurable_tasks(tasks, probe, max_probe=6)
    order = [t["index"] % 3 for t in kept]
    assert order == [0, 0, 1, 1, 2, 2], f"排序不符：{order}"


def test_probes_in_original_order_not_round_robin():
    """按原始顺序探测前 N 个（实测选型，勿改成轮询）。"""
    # 前 3 个同 CWE-1333，后面的跨 CWE；顺序探测应只探前 3 个
    tasks = _tasks([("1333", 0), ("1333", 1), ("1333", 2), ("327", 3), ("200", 4)])
    probed = []

    def probe(rows, samples):
        probed.append(rows[0]["index"])
        return 0.5, []

    kept, info = filter_measurable_tasks(tasks, probe, max_probe=3)
    assert probed == [0, 1, 2], f"应按顺序探测前 3 个，实际探了 {probed}"
    assert info["probed"] == 3
    assert info["cwe_probed"] == 1, "顺序探测下只覆盖 1 个 CWE（这与实测选型一致）"


def test_unprobed_tasks_are_kept():
    """未被探测的任务一律保留（不做判断，不轻易丢弃）。"""
    tasks = _tasks([("1333", i) for i in range(10)])

    def probe(rows, samples):
        return 0.5, []

    kept, info = filter_measurable_tasks(tasks, probe, max_probe=4)
    idx = sorted(t["index"] for t in kept)
    assert idx == list(range(10)), "未探测的任务应全部保留"
    assert info["probed"] == 4
    assert info["rest_kept"] == 6


def test_probe_failure_keeps_task():
    """探测抛异常 ≠ 不可测：该任务应被保留（我们只是不知道它的基线）。"""
    tasks = _tasks([("1333", 0), ("1333", 1), ("1333", 2)])

    def probe(rows, samples):
        if rows[0]["index"] == 0:
            raise RuntimeError("boom")
        return 0.5, []

    kept, info = filter_measurable_tasks(tasks, probe, max_probe=3)
    assert info["probe_failed"] == 1
    assert 0 in [t["index"] for t in kept], "探测失败的任务应被保留"

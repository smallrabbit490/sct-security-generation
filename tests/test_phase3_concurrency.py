"""阶段 G2 验收：Phase3 并发审计（phase3_workers）。

背景（实测）：Phase3 原先是**串行 for 循环**，每条经验要跑（基线+加候选）
两轮完整生成——轮1 审 24 条用了 105 分钟，是全流程最慢的一步。
现改为按 phase3_workers 并发，且所有状态写入仍在主线程串行完成。

本测试确保：
  ① 并发路径与串行路径产出**同样**的判定结果（不因并发而错乱）
  ② 单条审计抛异常不拖垮整批
  ③ 并发下树/池写入不发生冲突（终态在主线程写）
"""

from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory.error_ledger import ErrorLedger
from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode
import threading
import time
import pytest


def test_audit_evidence_write_failure_aborts_before_promotion(monkeypatch):
    """证据文件不可写时不能吞错后晋升经验。"""
    r = _runner(phase3_workers=2)
    r.experience_pool.append(_node('n0'))
    monkeypatch.setattr(r, '_audit_one', lambda cand, **kw: {
        'candidate_id': cand.invariant_id,
        'detail': {'candidate_id': cand.invariant_id},
        'rec': {'decision': 'supported'}})

    def broken_sink(detail):
        raise OSError('disk unavailable')

    with pytest.raises(OSError, match='disk unavailable'):
        r.phase3_audit(_tasks(), max_entries=0, on_audit=broken_sink)
    assert r.experience_pool[0].status == 'provisional'


def test_phase3_honors_own_workers_and_streams_evidence(monkeypatch):
    """真实线程验证审计并发上限、即时落盘回调与收尾前不改树。"""
    r = CleRunner(_Stub(), HskTree(), ErrorLedger(), workers=6, phase3_workers=2)
    r.experience_pool.extend(_node(f'n{i}') for i in range(6))
    lock = threading.Lock()
    state = {'active': 0, 'peak': 0}
    emitted = threading.Event()
    observed = []

    def audit(cand, **kwargs):
        with lock:
            state['active'] += 1
            state['peak'] = max(state['peak'], state['active'])
        if cand.invariant_id != 'n0':
            emitted.wait(0.5)
        time.sleep(0.02)
        with lock:
            state['active'] -= 1
        detail = {'candidate_id': cand.invariant_id, 'decision': 'unmeasured'}
        return {'candidate_id': cand.invariant_id, 'detail': detail, 'rec': detail}

    def consume(detail):
        observed.append(all(n.status == 'provisional' for n in r.experience_pool))
        emitted.set()

    monkeypatch.setattr(r, '_audit_one', audit)
    r.phase3_audit(_tasks(), max_entries=0, on_audit=consume)
    assert state['peak'] == 2
    assert len(observed) == 6 and all(observed)


class _Stub:
    def __call__(self, prompt):
        return {"choices": [{"message": {"content": "{}"}}]}


def _node(iid, cwe="1333"):
    n = SecurityInvariantNode(invariant_id=iid, cwe=cwe,
                              high_level_invariant="anchor the regex",
                              positive_principle="anchor", status="provisional")
    n.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return n


def _tasks(n=3):
    return [{"index": i, "CWE_ID": "1333",
             "task_description": {"function_name": f"f{i}", "description": "d"}} for i in range(n)]


def _runner(**kw):
    return CleRunner(_Stub(), HskTree(), ErrorLedger(), workers=1, **kw)


def test_phase3_workers_default_and_clamp():
    """默认 8；非法值被夹到 >=1。"""
    assert _runner().phase3_workers == 8
    assert _runner(phase3_workers=24).phase3_workers == 24
    assert _runner(phase3_workers=0).phase3_workers == 1
    assert _runner(phase3_workers=-5).phase3_workers == 1


def test_parallel_and_serial_give_same_decisions(monkeypatch):
    """并发与串行路径应对同一批经验给出相同判定。"""
    tasks = _tasks(3)
    nodes = [_node(f"n{i}") for i in range(5)]

    def run(phase3_workers):
        r = _runner(phase3_workers=phase3_workers)
        for n in nodes:
            r.experience_pool.append(_node(n.invariant_id))
        # 让 Δ 恒为 0 → 全部 unmeasured（避免依赖真实生成）
        monkeypatch.setattr(CleRunner, "_joint_pass_rate",
                            lambda self, rows, cp, samples=1: (0.0, [False] * len(rows)))
        out = r.phase3_audit(tasks, audit_per_candidate=2, regression_samples=1, max_entries=0)
        return sorted((a["candidate_id"], a["decision"]) for a in out["audit_detail"])

    serial = run(1)
    parallel = run(4)
    assert serial == parallel, "并发与串行的判定结果必须一致"
    assert len(serial) == 5


def test_single_entry_exception_does_not_abort_batch(monkeypatch):
    """某条经验的审计抛异常时，其余条目仍被处理（不整批失败）。"""
    tasks = _tasks(2)
    r = _runner(phase3_workers=2)
    for i in range(4):
        r.experience_pool.append(_node(f"n{i}"))

    calls = {"n": 0}

    def flaky(self, rows, cp, samples=1):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("simulated")
        return 0.0, [False] * len(rows)

    monkeypatch.setattr(CleRunner, "_joint_pass_rate", flaky)
    out = r.phase3_audit(tasks, audit_per_candidate=1, regression_samples=1, max_entries=0)
    assert len(out["audit_detail"]) >= 3, "单条异常不应导致整批丢失"


def test_state_written_after_parallel_section(monkeypatch):
    """并发段结束后，终态在主线程写入（状态不再是 provisional）。"""
    tasks = _tasks(2)
    r = _runner(phase3_workers=3)
    for i in range(3):
        r.experience_pool.append(_node(f"n{i}"))
    monkeypatch.setattr(CleRunner, "_joint_pass_rate",
                        lambda self, rows, cp, samples=1: (0.0, [False] * len(rows)))
    r.phase3_audit(tasks, audit_per_candidate=1, regression_samples=1, max_entries=0)
    statuses = {n.status for n in r.experience_pool}
    assert "provisional" not in statuses, "审计后不应残留 provisional"
    assert statuses <= {"active", "retired", "unmeasured", "revised"}

"""阶段 G2 验收：门控所有可能的终态都必须是合法节点状态。

这是一条防回归不变量测试。实测教训：门控会产生 `unmeasured`（第一条新增）
与 `revised`（缺测分支）两种终态，但 NODE_STATUS 未收录它们，导致
`cand.status = "unmeasured"` 抛 ValueError 并**中断整条全量运行**。
本测试确保门控决策 → 节点状态的映射永远合法。
"""

from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory.error_ledger import ErrorLedger
from methods.sct_trajectory.hsk_tree import NODE_STATUS, HskTree, SecurityInvariantNode


class _Stub:
    def __call__(self, prompt):
        return {"choices": [{"message": {"content": "{}"}}]}


def test_gate_decisions_map_to_valid_node_status():
    """门控每条决策分支设置的状态，都必须在 NODE_STATUS 里。"""
    r = CleRunner(_Stub(), HskTree(), ErrorLedger(), workers=1)

    mapping = {
        "supported": "active",
        "demoted": "retired",
        "unmeasured": "unmeasured",
        "revised": "revised",
    }
    for decision, status in mapping.items():
        n = SecurityInvariantNode(invariant_id=f"n-{decision}", cwe="1333",
                                  high_level_invariant="x", status="provisional")
        # 关键断言：赋值不得抛 ValueError
        n.status = status
        assert n.status in NODE_STATUS, f"{decision} → {status} 不是合法状态"


def test_node_status_covers_all_gate_outcomes():
    """NODE_STATUS 必须覆盖门控全部终态（防止再次遗漏）。"""
    for s in ("provisional", "active", "consolidated", "retired",
              "unmeasured", "revised"):
        assert s in NODE_STATUS, f"NODE_STATUS 缺少门控终态 {s}"


def test_unmeasured_and_revised_nodes_can_be_constructed():
    """能直接构造 unmeasured / revised 节点（不抛异常）。"""
    for s in ("unmeasured", "revised"):
        n = SecurityInvariantNode(invariant_id=f"n-{s}", cwe="1333",
                                  high_level_invariant="x", status=s)
        assert n.status == s


def test_invalid_status_still_rejected():
    """非法状态仍应被拒绝（不是把所有校验都放开了）。"""
    import pytest

    with pytest.raises(ValueError):
        SecurityInvariantNode(invariant_id="bad", cwe="1333",
                              high_level_invariant="x", status="totally_made_up")

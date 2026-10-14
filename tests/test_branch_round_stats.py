"""CLI 轮次汇总必须区分首分支、训练选优和串行修复。"""
from methods.sct_trajectory.closed_loop import _round_stats, _repair_round_stats
from methods.sct_trajectory.schemas import RolloutTrace


def branch(state, measured=True):
    return {"state": state, "measured": measured,
            "functional": state in "AB", "security": state in "AC", "joint": state == "A",
            "evidence": {"functional": {"status": "pass" if state in "AB" else "fail"},
                         "security": {"status": "pass" if state in "AC" else "fail"}}}


def trace(states, selected=0):
    branches = [branch(s) for s in states]
    return RolloutTrace(task_id="1", states=[states[selected]], evidence=[branches[selected]["evidence"]],
                       branches=branches, branch_selection={"index": selected, "policy": "training_oracle_first_joint_else_first"})


def test_branch_summary_exposes_first_selected_and_oracle_without_pass_one_claim():
    result = _round_stats([trace(["D", "A", "B"], 1)])
    metrics = result["branch_metrics"]
    assert result["measurement_policy"] == "training_selected_branch_not_deployment_pass_at_1"
    assert metrics["first"]["joint"]["pass"] == 0
    assert metrics["selected"]["joint"]["pass"] == 1
    assert metrics["oracle"]["joint"]["pass"] == 1
    assert result["joint"]["pass"] == 1
    assert result["per_task"][0]["selection_policy"] == "training_oracle_first_joint_else_first"


def test_branch_repair_summary_does_not_call_oracle_c0_or_invent_c1():
    result = _repair_round_stats([trace(["D", "A", "B"], 1)])
    assert result["c0"]["samples"] == 0
    assert result["c1"]["samples"] == 0
    assert result["branch_metrics"]["first"]["joint"]["pass"] == 0
    assert result["branch_metrics"]["selected"]["joint"]["pass"] == 1
    assert result["parallel_branch_tasks"] == 1


def test_oracle_function_security_can_differ_but_joint_requires_one_branch():
    metrics = _round_stats([trace(["B", "C", "D"])])["branch_metrics"]
    assert metrics["first"]["functional"]["pass"] == 1
    assert metrics["first"]["security"]["pass"] == 0
    assert metrics["oracle"]["functional"]["pass"] == 1
    assert metrics["oracle"]["security"]["pass"] == 1
    assert metrics["oracle"]["joint"]["pass"] == 0


def test_branch_unmeasured_never_becomes_success_even_if_flags_are_true():
    item = trace(["A", "D", "D"])
    item.branches[0]["measured"] = False
    item.branches[0]["evidence"]["functional"]["error_type"] = "local_worker_error"
    result = _round_stats([item])
    assert result["joint"]["pass"] == 0
    assert result["unmeasured"] == 1
    assert result["branch_metrics"]["first"]["unmeasured"] == 1
    assert result["branch_metrics"]["oracle"]["joint"]["pass"] == 0


def test_legacy_repair_stats_remain_unchanged_and_mixed_population_is_explicit():
    old = RolloutTrace(task_id="old", states=["B", "A"], evidence=[branch("B")["evidence"], branch("A")["evidence"]])
    legacy = _repair_round_stats([old])
    assert set(legacy) == {"c0", "c1"}
    assert legacy["c0"]["security"]["pass"] == 0
    assert legacy["c1"]["security"]["pass"] == 1
    mixed = _repair_round_stats([old, trace(["D", "A"], 1)])
    assert mixed["c0"]["samples"] == 1
    assert mixed["c1"]["samples"] == 1
    assert mixed["parallel_branch_tasks"] == 1
    assert _round_stats([old, trace(["D", "A"], 1)])["measurement_policy"] == "mixed_legacy_final_and_training_selected"

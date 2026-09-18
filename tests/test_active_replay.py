"""阶段 C 延伸验收：主动回放调度器（两阶段受控 + LLM 有界筛选，不平移 D_audit）。"""

from methods.sct_trajectory.active_replay import (
    build_scheduler_prompt,
    llm_bounded_select,
    rule_budget_filter,
    schedule_replay,
    tree_summary,
    weak_cwes,
)
from methods.sct_trajectory.error_ledger import ErrorEntry, ErrorLedger
from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode


def _node(cwe, invariant, support=1, regression=0, status="active"):
    return SecurityInvariantNode(
        invariant_id=f"inv-{cwe}",
        cwe=cwe,
        high_level_invariant=invariant,
        applicability="x",
        positive_principle="p",
        support_count=support,
        regression_count=regression,
        status=status,
    )


def _task(idx, cwe, name="f"):
    return {
        "index": idx,
        "CWE_ID": cwe,
        "task_description": {"function_name": name, "description": f"task {name}"},
    }


def test_weak_cwes():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "路径规范化"))
    tree.insert_node(_node("CWE-22", "路径白名单"))
    tree.insert_node(_node("CWE-78", "命令注入"))
    tree.insert_node(_node("CWE-502", "反序列化"))
    # CWE-22 有 2 个 active（不薄弱），CWE-78/CWE-502 各 1 个（薄弱）
    assert weak_cwes(tree, threshold=2) == ["CWE-502", "CWE-78"]


def test_rule_budget_filter_prioritizes_weak_cwe():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "a"))
    tree.insert_node(_node("CWE-22", "b"))  # CWE-22 已有 2 active，不薄弱
    ledger = ErrorLedger()
    tasks = [
        _task(1, "CWE-22"),   # 不薄弱
        _task(2, "CWE-78"),   # 薄弱（active=0 <2）
        _task(3, "CWE-502"),  # 薄弱
    ]
    ranked = rule_budget_filter(tree, ledger, tasks, batch_size=24)
    # 薄弱的 CWE-78/CWE-502 应排在 CWE-22 前面
    first_two = {t["CWE_ID"] for t in ranked[:2]}
    assert first_two == {"CWE-78", "CWE-502"}


def test_rule_budget_filter_uses_error_bias():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "a"))
    tree.insert_node(_node("CWE-22", "b"))
    ledger = ErrorLedger()
    ledger.add(ErrorEntry("CWE-502", "D_stalled", "both_failed", "h", "D->D"))  # CWE-502 有错题偏置
    tasks = [_task(1, "CWE-22"), _task(2, "CWE-502")]
    ranked = rule_budget_filter(tree, ledger, tasks, batch_size=24)
    assert ranked[0]["CWE_ID"] == "CWE-502"  # 错题密度偏置把它顶到最前


def test_llm_bounded_select_only_selected_returned():
    tree = HskTree()
    ledger = ErrorLedger()
    tasks = [_task(1, "CWE-22"), _task(2, "CWE-78"), _task(3, "CWE-502")]

    def fake_requester(prompt):
        return {
            "choices": [{"message": {"content": (
                '{"decisions": ['
                '{"Task_ID": 2, "Selected": true, "Reason": "薄弱 CWE"},'
                '{"Task_ID": 1, "Selected": false, "Reason": "已覆盖"},'
                '{"Task_ID": 3, "Selected": true, "Reason": "高风险"}'
                "]}"
            )}}]
        }

    result = llm_bounded_select(tree, ledger, tasks, fake_requester)
    assert result["error"] is None
    # 只返回 Selected=true 的，且未选中的 task_id=1 不在 selected（留在 replay 池）
    selected_ids = [t["index"] for t in result["selected"]]
    assert selected_ids == [2, 3]
    assert 1 not in selected_ids
    assert result["reasons"]["2"] == "薄弱 CWE"


def test_llm_bounded_select_drops_invalid_ids():
    tree = HskTree()
    ledger = ErrorLedger()
    tasks = [_task(1, "CWE-22")]

    def fake_requester(prompt):
        return {
            "choices": [{"message": {"content": (
                '{"decisions": [{"Task_ID": 999, "Selected": true, "Reason": "x"},'
                '{"Task_ID": 1, "Selected": true, "Reason": "valid"}]}'
            )}}]
        }

    result = llm_bounded_select(tree, ledger, tasks, fake_requester)
    assert [t["index"] for t in result["selected"]] == [1]  # 越界 999 被丢弃


def test_llm_bad_json_degrades_gracefully():
    """LLM 输出无法解析时：记录 error，并由规则兜底补足（不让整轮空转）。"""
    tree = HskTree()
    ledger = ErrorLedger()
    tasks = [_task(1, "CWE-22")]

    def bad_requester(prompt):
        return {"choices": [{"message": {"content": "not json"}}]}

    result = llm_bounded_select(tree, ledger, tasks, bad_requester)
    assert result["error"] is not None              # 记录了 LLM 输出异常
    assert result["fallback_used"] is True          # 走了规则兜底
    assert [t["index"] for t in result["selected"]] == [1]


def test_llm_selects_zero_falls_back():
    """LLM 把候选全判 false 时，规则兜底应补足，避免整轮演进空转。"""
    tree = HskTree()
    ledger = ErrorLedger()
    tasks = [_task(1, "CWE-22"), _task(2, "CWE-78")]

    def zero_requester(prompt):
        return {"choices": [{"message": {"content":
            '{"decisions": [{"Task_ID": 1, "Selected": false, "Reason": "no value"},'
            ' {"Task_ID": 2, "Selected": false, "Reason": "no value"}]}'}}]}

    result = llm_bounded_select(tree, ledger, tasks, zero_requester, fallback_min=1)
    assert result["selected"], "兜底后不应为空"
    assert result["fallback_used"] is True
    assert "rule_fallback" in result["reasons"][str(result["selected"][0]["index"])]


def test_llm_selection_respected_when_enough():
    """LLM 选中数达标时不应触发兜底。"""
    tree = HskTree()
    ledger = ErrorLedger()
    tasks = [_task(1, "CWE-22"), _task(2, "CWE-78")]

    def ok_requester(prompt):
        return {"choices": [{"message": {"content":
            '{"decisions": [{"Task_ID": 1, "Selected": true, "Reason": "weak cwe"}]}'}}]}

    result = llm_bounded_select(tree, ledger, tasks, ok_requester, fallback_min=1)
    assert [t["index"] for t in result["selected"]] == [1]
    assert result["fallback_used"] is False


def test_schedule_replay_end_to_end_no_daudit_move():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "a"))
    ledger = ErrorLedger()
    replay_pool = [_task(1, "CWE-22"), _task(2, "CWE-78"), _task(3, "CWE-502")]

    def fake_requester(prompt):
        return {
            "choices": [{"message": {"content": (
                '{"decisions": [{"Task_ID": 2, "Selected": true, "Reason": "weak"}]}'
            )}}]
        }

    result = schedule_replay(tree, ledger, replay_pool, fake_requester)
    # 返回的只是「选中的」，绝不包含"平移到 audit"之类的动作字段
    assert [t["index"] for t in result["selected"]] == [2]
    assert "moved_to_audit" not in result


def test_tree_summary_and_prompt_contain_weak_cwe():
    tree = HskTree()
    tree.insert_node(_node("CWE-22", "路径规范化"))
    ledger = ErrorLedger()
    ledger.add(ErrorEntry("CWE-502", "D_stalled", "both_failed", "h", "D->D"))
    tasks = [_task(1, "CWE-502")]
    summary = tree_summary(tree)
    assert "CWE-22" in summary and "active" in summary
    prompt = build_scheduler_prompt(tree, ledger, tasks)
    assert "薄弱 CWE" in prompt
    assert "CWE-22" in prompt  # 薄弱 CWE 列表里
    assert "盲区预警" in prompt
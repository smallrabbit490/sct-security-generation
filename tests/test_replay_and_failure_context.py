"""回归测试：2026-09-21 在 A/B 方案里查出的缺陷（防止回退）。

背景：A 方案（重放候选过滤）与 B 方案（失败现场入池）的代码"写完即交接"，
从未端到端执行过，导致 8 处缺陷在真实验证运行中才逐个暴露。本文件把每一处
都固化成一条断言——它们都是**静默失效**类型（不报错，只是结果悄悄不对），
没有测试就只能靠事后翻日志发现。

缺陷清单（编号与 docs/architecture_and_experiment_history.md 第八节一致）：
  D1 `_node_from_negative` 不写 source → 负向经验（含修复轮失败）丢失败现场
  D2 `_node_from_distilled` 缺 round_index/round_state/prev_fix_assessment
  D3 `_node_from_ledger_item` 要求 blind_spot，按轮失败经验全被丢弃
  D4 `_absorb_in_pool` 吸收时丢 root_cause/fix_directive/prev_fix_assessment
  D6 覆盖率目标 int() 向下取整 → 永远够不到 75%
  D7 `llm_bounded_select` 未把 already_used 传进调度提示词
  D14 `phase2_evolve` 返回全局累积 traces → retry_counts 被重复累加
  D15 覆盖配额补足突破 replay_limit（"有界"契约失效）
"""

from pathlib import Path

from methods.sct_trajectory.active_replay import llm_bounded_select, schedule_replay
from methods.sct_trajectory.closed_loop import (
    CleRunner,
    _append_note,
    _is_negative_only,
    _node_from_distilled,
    _node_from_ledger_item,
    _node_from_negative,
    select_audit_targets,
)
from methods.sct_trajectory.error_ledger import ErrorLedger
from methods.sct_trajectory.gate_selector import filter_measurable_tasks
from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode


class _DummyRequester:
    def __call__(self, prompt):
        return {"choices": [{"message": {"content": "{}"}}]}


def _runner():
    return CleRunner(_DummyRequester(), HskTree(), ErrorLedger(), workers=1)


# ---------------------------------------------------------------- D1 / D2 / D3

def test_d1_negative_node_keeps_failure_context():
    """D1：负向经验（修复轮失败 round_1_fail 走这条路径）必须带失败现场。"""
    node = _node_from_negative({
        "cwe": "79", "negative_guardrail": "禁止对契约内 HTML 字段转义",
        "kind": "round_1_fail", "round_index": 1, "round_state": "C",
        "root_cause": "把系统信任的 HTML 也转义了", "fix_directive": "只转义纯文本字段",
        "prev_fix_assessment": "上一轮改法不彻底",
    })
    assert node is not None
    src = node.source or {}
    assert src.get("kind") == "round_1_fail"
    assert src.get("round_index") == 1
    assert src.get("round_state") == "C"
    assert src.get("root_cause")
    assert src.get("fix_directive")
    assert src.get("prev_fix_assessment")


def test_d2_distilled_node_keeps_round_fields():
    """D2：正向路径必须带 round_index / round_state / prev_fix_assessment。"""
    node = _node_from_distilled({
        "cwe": "89", "high_level_invariant": "参数化查询", "positive_principle": "用占位符",
        "kind": "round_1_fail", "round_index": 1, "round_state": "B",
        "root_cause": "仍是字符串拼接", "fix_directive": "改 execute(sql, params)",
        "prev_fix_assessment": "只处理了第一处拼接",
    })
    assert node is not None
    src = node.source or {}
    assert src.get("round_index") == 1
    assert src.get("round_state") == "B"
    assert src.get("prev_fix_assessment")


def test_d3_round_failure_without_blind_spot_is_kept():
    """D3：按轮失败条目没有 blind_spot，不得被丢弃（原先一条都进不了池）。"""
    item = {"cwe": "77", "kind": "round_0_fail", "round_index": 0, "round_state": "D",
            "high_level_invariant": "安全增强必须建立在功能可用之上",
            "negative_guardrail": "禁止因安全顾虑输出空代码",
            "root_cause": "empty_code：约束冲突导致放弃生成",
            "fix_directive": "先恢复最小可行功能再叠加防护"}
    node = _node_from_ledger_item(item)
    assert node is not None, "按轮失败经验被丢弃 —— D3 回退"
    # 正文优先取 LLM 给出的 high_level_invariant，而不是把具体报错当通用不变量
    assert node.high_level_invariant == "安全增强必须建立在功能可用之上"
    assert node.negative_guardrail == "禁止因安全顾虑输出空代码"
    assert (node.source or {}).get("root_cause")


def test_d3_ledger_item_still_filters_success_notes():
    """D3 的兜底不得破坏原有的"成功描述"过滤。"""
    assert _node_from_ledger_item({
        "cwe": "79", "kind": "round_0_fail",
        "high_level_invariant": "无。本次修复正确识别了边界，未引入功能破坏。",
        "root_cause": "",
    }) is None


# ------------------------------------------------------------------------- D4

def test_d4_pool_absorption_preserves_failure_context():
    """D4：就地吸收时不得丢掉失败现场（原先 prev_fix_assessment 全池为空）。"""
    runner = _runner()
    existing = SecurityInvariantNode(
        invariant_id="seed-1", cwe="1333",
        high_level_invariant="正则必须限制回溯，避免灾难性回溯导致拒绝服务攻击",
        positive_principle="正则必须限制回溯，避免灾难性回溯导致拒绝服务攻击",
        negative_guardrail="", status="provisional",
        source={"kind": "seed_from_diff"},
    )
    existing.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    runner.experience_pool.append(existing)

    incoming = SecurityInvariantNode(
        invariant_id="cand-2", cwe="1333",
        high_level_invariant="正则必须限制回溯，避免灾难性回溯导致拒绝服务攻击",
        positive_principle="正则必须限制回溯，避免灾难性回溯导致拒绝服务攻击",
        negative_guardrail="禁止无界量词嵌套", status="provisional",
        source={"kind": "round_1_fail", "root_cause": "回溯上限设得太大",
                "fix_directive": "把上限降到 1000 步",
                "prev_fix_assessment": "上一轮只改了量词没加上限"},
    )
    incoming.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    absorbed = runner._absorb_in_pool(incoming)
    assert absorbed is not None, "高度重叠的经验应被吸收"
    src = absorbed.source or {}
    assert src.get("root_cause"), "吸收后 root_cause 丢失 —— D4 回退"
    assert src.get("fix_directive")
    assert src.get("prev_fix_assessment")


def test_append_note_dedups_and_truncates():
    """_append_note：去重追加 + 截断，且不改变空值语义。"""
    assert _append_note("", "B") == "B"
    assert _append_note("A", "") == "A"
    assert _append_note("A", "A") == "A"          # 已含同一段证据 → 不重复
    assert _append_note("A", "B") == "A\n——\nB"
    assert len(_append_note("x" * 2000, "y" * 100, limit=100)) == 100


# ------------------------------------------------------------------------- D7

def test_d7_scheduler_prompt_marks_already_used():
    """D7：调度提示词必须标注【已重放】/【未重放·优先】，否则该引导是死代码。"""
    captured = {}

    def requester(prompt):
        captured["prompt"] = prompt
        return {"choices": [{"message": {"content": '{"decisions": []}'}}]}

    tasks = [{"index": 1, "CWE_ID": "79", "task_description": {"function_name": "a", "description": "d"}},
             {"index": 2, "CWE_ID": "89", "task_description": {"function_name": "b", "description": "d"}}]
    llm_bounded_select(HskTree(), ErrorLedger(), tasks, requester, already_used={1})
    prompt = captured.get("prompt") or ""
    assert "[Previously replayed]" in prompt and "[Not yet replayed: priority]" in prompt, "already_used 未传入提示词 —— D7 回退"


# ------------------------------------------------------------------------ D15

def test_d15_coverage_quota_respects_replay_limit():
    """D15：覆盖配额补足不得突破 replay_limit（"有界筛选"契约）。"""
    def requester(prompt):
        return {"choices": [{"message": {"content": '{"decisions": []}'}}]}

    pool = [{"index": i, "CWE_ID": str(700 + i),
             "task_description": {"function_name": f"f{i}", "description": "d"}}
            for i in range(40)]
    out = schedule_replay(HskTree(), ErrorLedger(), pool, requester,
                          batch_size=40, replay_limit=5, coverage_quota=30)
    assert len(out["selected"]) <= 5, f"选中 {len(out['selected'])} 条，突破 replay_limit=5 —— D15 回退"
    assert out.get("coverage_truncated"), "截断必须显式留痕，不能静默降级"


def test_d15_no_truncation_when_budget_is_enough():
    """预算充足时不应误报截断。"""
    def requester(prompt):
        return {"choices": [{"message": {"content": '{"decisions": []}'}}]}

    pool = [{"index": i, "CWE_ID": str(700 + i),
             "task_description": {"function_name": f"f{i}", "description": "d"}}
            for i in range(6)]
    out = schedule_replay(HskTree(), ErrorLedger(), pool, requester,
                          batch_size=6, replay_limit=96, coverage_quota=3)
    assert len(out["selected"]) <= 96
    assert not out.get("coverage_truncated")


def test_phase2_coverage_warning_is_console_encodable():
    """Windows GBK 控制台不能因为进度提示字符中断训练续跑。"""
    source = (Path(__file__).parents[1] / "methods/sct_trajectory/closed_loop.py").read_text(encoding="utf-8")
    marker = "覆盖配额被 replay_limit="
    start = source.rfind("self.progress", 0, source.index(marker))
    warning = source[start:source.index("本轮仍有", start)]
    assert "⚠" not in warning
    warning.encode("gbk")


# ------------------------------------------------------------------------ D17

def _node(i, kind, positive, cwe):
    return SecurityInvariantNode(
        invariant_id=f"n{i}", cwe=cwe, high_level_invariant=f"不变量{i}",
        positive_principle=positive, negative_guardrail="", status="provisional",
        source={"kind": kind},
    )


def _realistic_ranked():
    """贴近实测的名额竞争分布（关键：正例跨很多 CWE，负例集中在少数 CWE）。

    为什么必须这样构造：如果正例也只占一两个 CWE，"同 CWE 只取一条"的去重趟
    会自己撞到负向经验上，配额开不开都一样 —— 那样测不出 D17。
    实测分布正是"正例覆盖面广（minimal_patch_hint 跨大量 CWE）、
    负例集中在少数 CWE（失败只来自实际跑过的任务）"，这才是失效场景。
    """
    positives = [_node(i, "minimal_patch_hint", "有正向原则", f"CWE-P{i}") for i in range(30)]
    negatives = [_node(100 + i, "round_0_fail", "", f"CWE-N{i % 2}") for i in range(30)]
    return positives + negatives


def test_d17_negative_experiences_get_audit_quota():
    """D17：纯负向经验（失败现场 / 过度防御陷阱）必须拿到审计名额。

    修复前 `_value` 把 positive_principle 非空当高价值，而这类经验按构造该字段
    恒为空 → 结构性排最后 → 48 个名额被正例占满，失败经验一条都没进过门控。

    断言用**绝对下界**而非函数自报的配额：否则把配额调成 0 时"自报配额"也跟着变 0，
    测试会假通过（这是本测试第一版的真实错误，已修正）。
    """
    picked, _ = select_audit_targets(_realistic_ranked(), max_entries=16)
    assert len(picked) == 16
    neg = [n for n in picked if _is_negative_only(n)]
    # 负向经验至少占名额的 30%（实现取 1/3）
    assert len(neg) >= 5, f"负向经验仅 {len(neg)}/16 条，低于 30% 下限 —— D17 回退"


def test_d17_quota_survives_single_cwe_concentration():
    """D17 边界：负向经验全部集中在同一个 CWE 时，配额仍须填满。"""
    ranked = ([_node(i, "minimal_patch_hint", "有正向原则", f"CWE-P{i}") for i in range(30)]
              + [_node(100 + i, "round_0_fail", "", "CWE-N0") for i in range(30)])
    picked, _ = select_audit_targets(ranked, max_entries=16)
    neg = [n for n in picked if _is_negative_only(n)]
    assert len(neg) >= 5, f"单一 CWE 场景下负向经验仅 {len(neg)} 条 —— 配额被 CWE 去重吃掉了"


def test_d17_quota_can_be_explicitly_disabled():
    """D17：配额开关必须真的可关（negative_ratio=0 → 不再为负向经验预留名额）。

    关闭配额**不等于**"一条负向经验都不会被选中"（在别的分布下它们仍可能按正常
    优先级被选上），但在这个贴近实测的分布下应当一条都进不去，因为 16 个名额
    会被 16 个不同 CWE 的正例填满。这正是修复前 48 个名额全被正例占满的原因。
    """
    picked_on, budget_on = select_audit_targets(_realistic_ranked(), max_entries=16)
    picked_off, budget_off = select_audit_targets(_realistic_ranked(), max_entries=16,
                                                  negative_ratio=0.0)
    assert budget_on >= 5, "开启配额时预留量应约为名额的 1/3"
    assert budget_off == 0, "negative_ratio=0 时必须真的归零，不能被 max(1, ...) 抬回 1"
    n_on = sum(1 for n in picked_on if _is_negative_only(n))
    n_off = sum(1 for n in picked_off if _is_negative_only(n))
    assert n_on > n_off, f"关闭配额后负向经验数未下降（on={n_on}, off={n_off}）"


def test_d17_no_negative_experiences_is_fine():
    """D17 边界：池里没有负向经验时不得报错，名额照常填满。"""
    ranked = [_node(i, "seed_from_diff", "有正向原则", f"CWE-{i}") for i in range(30)]
    picked, _ = select_audit_targets(ranked, max_entries=16)
    assert len(picked) == 16
    assert not any(_is_negative_only(n) for n in picked)


def test_d17_underfilled_pool_returns_all():
    """D17 边界：候选不足额时按实际数量返回，不补空。"""
    ranked = [_node(i, "round_0_fail", "", "CWE-N0") for i in range(3)]
    picked, _ = select_audit_targets(ranked, max_entries=16)
    assert len(picked) == 3


# ------------------------------------------------------------------------ D18

def _audit_rows(n):
    return [{"index": i, "CWE_ID": "1333", "task_description": {}} for i in range(n)]


def _probe_zero(rows, samples):
    """模拟"难题"：基线通过率恒为 0 —— 本次运行的真实情况。"""
    return 0.0, [False]


def test_d19_no_task_is_dropped_regardless_of_baseline():
    """D19：三种基线的任务**全部保留**，一条都不许剔除。

    原实现只保留基线 ∈ (0,1)，把基线 0 的当"不可测"丢掉。但基线 0 是**地板**不是天花板：
    Δ = 加经验 − 0 ≥ 0，可以为正（能测出"有用"），只是不可能为负（测不出"有害"）。
    实测 16 条基线 0 的候选里 10 条测出了正 Δ —— 丢掉它们会损失 59% 的正向证据来源。
    """
    def probe(rows, samples):
        i = rows[0]["index"]
        return (0.0 if i % 3 == 0 else (0.5 if i % 3 == 1 else 1.0)), []

    tasks = _audit_rows(298)
    out, info = filter_measurable_tasks(tasks, probe, max_probe=20)
    assert len(out) == 298, f"应原样保留 298 条，实际 {len(out)} 条 —— 有任务被剔除"
    assert info["measurable"] + info["gain_only"] + info["ceiling"] == 20, "20 条探测结果应被完整分类"
    assert info["gain_only"] > 0 and info["ceiling"] > 0
    assert info["kept"] == 298
    assert info["fallback"] is False, "本函数已不再有'回退'语义"


def test_d19_gain_only_tasks_survive_with_zero_baseline():
    """D19 核心：全部任务基线为 0（本次运行的真实形态）时，一条都不能少。"""
    tasks = _audit_rows(17)
    out, info = filter_measurable_tasks(tasks, _probe_zero, max_probe=17)
    assert len(out) == 17, f"基线全 0 时丢了任务：{17 - len(out)} 条"
    assert info["gain_only"] == 17 and info["measurable"] == 0


def test_d19_ordering_puts_most_discriminating_first():
    """D19：排序应为 正负皆可测 → 仅可测增益 → 未探测 → 仅可测有害。"""
    def probe(rows, samples):
        i = rows[0]["index"]
        return ([0.5, 0.0, 1.0][i % 3]), []

    tasks = _audit_rows(9)
    out, info = filter_measurable_tasks(tasks, probe, max_probe=9)
    assert len(out) == 9
    first = [t["index"] for t in out[:3]]
    second = [t["index"] for t in out[3:6]]
    third = [t["index"] for t in out[6:]]
    assert all(i % 3 == 0 for i in first), f"正负皆可测的任务应排最前，实际 {first}"
    assert all(i % 3 == 1 for i in second), f"仅可测增益的应排第二，实际 {second}"
    assert all(i % 3 == 2 for i in third), f"仅可测有害的应排最后，实际 {third}"


def test_d19_probe_failure_keeps_task():
    """D19 边界：探测抛异常的任务必须保留（无法判断 ≠ 可丢弃）。"""
    def probe(rows, samples):
        if rows[0]["index"] == 1:
            raise RuntimeError("api timeout")
        return 0.5, []

    tasks = _audit_rows(5)
    out, info = filter_measurable_tasks(tasks, probe, max_probe=5)
    assert len(out) == 5, "探测失败的任务被丢弃了"
    assert info["probe_failed"] == 1


# ------------------------------------------------------------------------ D20

def _evidence(func, sec):
    return {"functional": {"status": func}, "security": {"status": sec}}


def test_d20_regression_probe_counts_functional_regression(monkeypatch):
    """D20：**过度防御**（安全过、功能败）必须被记为**功能回归**，而不是安全回归。

    修复前 `detail["functional_regressions"] = 0` 是硬编码，且 security_regressions
    统计的是 joint 失败 —— 于是功能回归通道恒为 0，过度防御永远测不出来
    （而它占实测失败的 47.3%）。
    """
    import methods.sct_trajectory.closed_loop as cl

    runner = _runner()
    monkeypatch.setattr(cl, "run_pipeline", lambda *a, **k: {"code": "def f(): pass"})
    monkeypatch.setattr(cl, "validate_and_state",
                        lambda row, code, timeout: (_evidence("fail", "pass"), "C"))

    sec, func = runner._regression_probe(
        [{"index": 1, "CWE_ID": "79", "task_description": {"function_name": "f"}}],
        lambda q: [], samples=3)
    assert (sec, func) == (0, 1), f"过度防御应为 (0,1)，实际 ({sec},{func})"


def test_d20_regression_probe_counts_security_regression(monkeypatch):
    """D20：安全被破坏（功能过、安全败）记为安全回归。"""
    import methods.sct_trajectory.closed_loop as cl

    runner = _runner()
    monkeypatch.setattr(cl, "run_pipeline", lambda *a, **k: {"code": "def f(): pass"})
    monkeypatch.setattr(cl, "validate_and_state",
                        lambda row, code, timeout: (_evidence("pass", "fail"), "B"))

    sec, func = runner._regression_probe(
        [{"index": 1, "CWE_ID": "79", "task_description": {"function_name": "f"}}],
        lambda q: [], samples=3)
    assert (sec, func) == (1, 0), f"安全破坏应为 (1,0)，实际 ({sec},{func})"


def test_d20_unmeasured_is_not_counted_as_regression(monkeypatch):
    """D20：状态为 unmeasured 的维度**不得**被当成回归（不伪造证据）。"""
    import methods.sct_trajectory.closed_loop as cl

    runner = _runner()
    monkeypatch.setattr(cl, "run_pipeline", lambda *a, **k: {"code": "def f(): pass"})
    monkeypatch.setattr(cl, "validate_and_state",
                        lambda row, code, timeout: (_evidence("unmeasured", "unmeasured"), "D"))

    sec, func = runner._regression_probe(
        [{"index": 1, "CWE_ID": "79", "task_description": {"function_name": "f"}}],
        lambda q: [], samples=3)
    assert (sec, func) == (0, 0), f"未测量不应计为回归，实际 ({sec},{func})"


def test_d20_empty_code_counts_as_both_regressions(monkeypatch):
    """D20 边界：生成空代码 → 两个维度都算失败（保守，且不抛异常）。"""
    import methods.sct_trajectory.closed_loop as cl

    runner = _runner()
    monkeypatch.setattr(cl, "run_pipeline", lambda *a, **k: {"code": "   "})

    sec, func = runner._regression_probe(
        [{"index": 1, "CWE_ID": "79", "task_description": {"function_name": "f"}}],
        lambda q: [], samples=3)
    assert (sec, func) == (1, 1)


# ------------------------------------------------------------------------ D21

def test_d21_hpass_missing_blocks_promotion():
    """D21：拿不到任务描述（缺测）时必须阻止晋升，而不是当成"无回归"放行。

    原先 hpass 只带 {cwe, task_id}，Phase3 的回归探针跑在**空任务契约**上；
    且 detail 里没有 hpass_missing 这个键，缺测既没被记录也没能阻止晋升。
    """
    from methods.sct_trajectory.gates import audit_candidate
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever

    retriever = HskTreeRetriever(HskTree(), requester=None)
    rec = audit_candidate(
        "cand-x", retriever, {"task_description": {"function_name": "f"}},
        delta_joint_pass=0.5,           # 有正证据
        security_regressions=0,
        functional_regressions=0,
        hpass_missing=1,                # 但回归证据缺测
    )
    assert rec.decision == "revised", f"缺测时应为 revised，实际 {rec.decision}"
    assert "hpass_missing" in rec.reasons


def test_d20_call_site_wiring_not_hardcoded():
    """D20 接线检查：Phase3 必须调用分维度回归探针，且不得把功能回归写死为 0。

    这是"防止回退"的硬约束——`_regression_probe` 单独测通不代表调用方用了它。
    实测缺陷正是"函数没写错，但调用方把结果丢掉、填了个 0"。

    实现说明：这里直接读源码文件而不是 `inspect.getsource(phase3_audit)` ——
    后者对这一个超长方法会截断（实测只返回 8723 字符，而方法实际约 460 行），
    用它做断言会假失败。
    """
    from pathlib import Path

    import methods.sct_trajectory.closed_loop as cl

    src = Path(cl.__file__).read_text(encoding="utf-8")
    assert "self._regression_probe(" in src, \
        "Phase3 未调用分维度回归探针 —— 功能回归通道会再次失效"
    assert 'detail["functional_regressions"] = 0' not in src, \
        "functional_regressions 仍被硬编码为 0 —— 过度防御无法被识别"
    assert 'hpass_missing=detail.get("hpass_missing", 0)' in src, \
        "hpass_missing 未传给门控 —— 缺测会被当成无回归"


# ------------------------------------------------------------------------ D32

def _ev(functional="fail", security="pass", detail=""):
    return {"functional": {"status": functional, "details": detail},
            "security": {"status": security}, "syntax_or_compile": {"status": "pass"}}


def test_d32_repair_round_receives_previous_evidence():
    """D32：修复轮必须拿到上一轮的真实测试结果（否则是盲改）。

    实测依据（ab_verify2_20260921 的 20 个 Phase1 任务）：
      20 条首轮证据全部含具体报错详情，但 18 条修复轮**全部检索到 0 条经验**；
      状态迁移 D→D 5 / B→B 4 / C→C 7 / B→D 1 / C→D 1 —— 16/18 原地不动、2 条恶化、
      **0 条转正**（面板：第一次动态测试 10% → 迭代后 0%）。
    """
    from methods.sct_trajectory.agent_pipeline import analyze_prompt, planning_prompt

    ev = _ev(detail="AssertionError: expected 200 got 500")
    a = analyze_prompt({"function_name": "f"}, "def f(): pass", ev)
    p = planning_prompt("分析内容", [], {"function_name": "f"}, previous_evidence=ev)
    for name, text in (("分析", a), ("规划", p)):
        assert "[Previous measured test results]" in text, f"{name} prompt 未注入上一轮证据"
        assert "expected 200 got 500" in text, f"{name} prompt 未带具体报错"
        assert "Functional tests: fail" in text


def test_d32_unmeasured_is_not_rendered_as_failure():
    """D32：状态为 unmeasured 的维度不得被渲染成结论（不伪造证据）。"""
    from methods.sct_trajectory.agent_pipeline import previous_evidence_block

    assert previous_evidence_block({"functional": {"status": "unmeasured"}}) == ""
    assert previous_evidence_block(None) == ""
    assert previous_evidence_block({}) == ""


def test_d32_execution_error_is_propagated():
    """D32：执行层错误（empty_code / 超时）也要如实回传。"""
    from methods.sct_trajectory.agent_pipeline import previous_evidence_block

    block = previous_evidence_block({"error": "empty_code"})
    assert "empty_code" in block and "Execution incomplete" in block


def test_d32_run_pipeline_threads_evidence(monkeypatch):
    """D32 接线：run_pipeline 必须把 previous_evidence 传进 Analysis 与 Planning 两次调用。"""
    import methods.sct_trajectory.agent_pipeline as ap

    seen: list[str] = []

    def fake_requester(prompt: str) -> dict:
        seen.append(prompt)
        if "security and functional-contract analyst" in prompt:
            body = '{"vulnerability_hypothesis":["x"],"functional_invariants":["y"]}'
        else:
            body = '{"Preserved_Func":"a","Patch_Scope":"b","Avoidance_List":[]}'
        return {"choices": [{"message": {"content": body}}]}

    ap.run_pipeline({"function_name": "f"}, [], requester=fake_requester,
                    reference_code="def f(): pass",
                    previous_evidence=_ev(detail="boom_marker"))
    analysis_calls = [p for p in seen if "security and functional-contract analyst" in p]
    planning_calls = [p for p in seen if "security planning expert" in p]
    assert analysis_calls and "boom_marker" in analysis_calls[0], "Analysis 未收到证据"
    assert planning_calls and "boom_marker" in planning_calls[0], "Planning 未收到证据"


def test_l6_recorded_prompts_match_actual_constraints():
    """L6：落盘的 planning prompt 必须与实际调用的一致（含 contract_freeze）。"""
    import methods.sct_trajectory.agent_pipeline as ap

    def fake_requester(prompt: str) -> dict:
        if "security and functional-contract analyst" in prompt:
            body = '{"vulnerability_hypothesis":["x"],"functional_invariants":["y"]}'
        else:
            body = '{"Preserved_Func":"a","Patch_Scope":"b","Avoidance_List":[]}'
        return {"choices": [{"message": {"content": body}}]}

    out = ap.run_pipeline({"function_name": "f"}, [], requester=fake_requester,
                          contract_freeze=True)
    assert "Frozen task contract" in out["prompts"]["planning"], \
        "落盘的 planning prompt 缺少 contract_freeze 约束 —— 与实际调用不一致"


# ------------------------------------------------------------------------ D34

def _pool_node(iid, tid, text, cwe="79"):
    from methods.sct_trajectory.hsk_tree import LanguageLeaf, SecurityInvariantNode

    n = SecurityInvariantNode(
        invariant_id=iid, cwe=cwe, high_level_invariant=text, positive_principle=text,
        status="provisional",
        source={"kind": "round_0_fail", "task_id": tid, "root_cause": "上次失败原因"},
    )
    n.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return n


def test_d34_same_task_experience_enters_top_rank():
    """D34：任务被强制重放时，它自己上一轮的失败经验必须排到候选头部。

    原实现只靠 `_same_task_bonus` 参与打分，而该加权恒为 0（调用点的 query 里没有
    task_id），同任务经验还要跟其它同 CWE 节点争 recall_k=8 的名额。
    实测 ab_verify3：152 次命中里同任务 49 次，但全是 TF-IDF 碰巧撞上的。
    """
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever

    r = HskTreeRetriever(HskTree(), requester=None, same_task_bonus=2.0)
    pool = [_pool_node("mine", "123", "该任务上次失败：未转义 HTML"),
            _pool_node("other", "999", "通用的输入校验原则")]
    # 用 12 个同 CWE 的无关节点把 recall_k=8 挤满
    pool += [_pool_node(f"n{i}", f"888{i}", f"某个同CWE但无关的经验{i}") for i in range(12)]

    q = {"CWE_ID": "79", "language": "python", "description": "render html", "task_id": "123"}
    cards = r.search(q, limit=3, pool_nodes=pool)
    assert cards and cards[0]["invariant_id"] == "mine", \
        f"同任务经验未排到首位，实际顺序 {[c['invariant_id'] for c in cards]}"


def test_d34_same_task_bonus_fires_when_task_id_present():
    """D34：带 task_id 时 `_same_task_bonus` 必须真的返回加权值（而不是恒 0）。"""
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever

    r = HskTreeRetriever(HskTree(), requester=None, same_task_bonus=2.0)
    node = _pool_node("mine", "123", "x")
    assert r._same_task_bonus(node, {"task_id": "123"}) == 2.0
    assert r._same_task_bonus(node, {"index": "123"}) == 2.0
    assert r._same_task_bonus(node, {"task_id": "456"}) == 0.0
    # 缺 task_id 时必须安全返回 0（而不是抛异常）
    assert r._same_task_bonus(node, {"CWE_ID": "79"}) == 0.0
    assert r._same_task_bonus(node, None) == 0.0


def test_d34_call_sites_pass_task_id():
    """D34 接线检查：所有构造检索 query 的地方都必须带上 task_id。

    这是"防止回退"的硬约束——`search` 单独测通不代表调用方传了 id。
    实测缺陷正是"机制写好了，但调用点没给它需要的字段"。
    """
    from pathlib import Path

    import methods.sct_trajectory.closed_loop as cl

    src = Path(cl.__file__).read_text(encoding="utf-8")
    n_query = src.count('query = {**task, "CWE_ID"')
    n_tid = src.count('"task_id": row.get("index")')
    assert n_query > 0, "未找到检索 query 的构造处（测试需同步更新）"
    assert n_tid >= n_query, \
        f"有 {n_query} 处构造 query，但只有 {n_tid} 处带 task_id —— 同任务加权会再次失效"


def test_d34_no_task_id_does_not_crash():
    """D34 边界：query 里没有 task_id 时检索必须正常返回（只是不加权）。"""
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever

    r = HskTreeRetriever(HskTree(), requester=None, same_task_bonus=2.0)
    pool = [_pool_node("a", "1", "经验A"), _pool_node("b", "2", "经验B")]
    cards = r.search({"CWE_ID": "79", "language": "python", "description": "x"},
                     limit=2, pool_nodes=pool)
    assert len(cards) == 2


def test_d34_prev_evidence_injection_is_off_by_default():
    """D34：直接拼 prompt 的路线默认关闭（用户拍板走"经验库 + 检索"）。"""
    from methods.sct_trajectory.closed_loop import CleRunner
    from methods.sct_trajectory.error_ledger import ErrorLedger
    from methods.sct_trajectory.hsk_tree import HskTree

    runner = CleRunner(_DummyRequester(), HskTree(), ErrorLedger(), workers=1)
    assert runner.inject_prev_evidence is False


# --------------------------------------------------------------- 方案 A（即时提炼）

_ROUND_JSON = (
    '{"root_cause":"Untrusted HTML was not escaped","fix_directive":"Call html.escape on author_id",'
    '"prev_fix_assessment":"","high_level_invariant":"Escape all untrusted input during HTML rendering",'
    '"positive_principle":"Escape untrusted input while preserving the return format",'
    '"negative_guardrail":"Do not escape trusted HTML fields allowed by the contract","applicability":"HTML template rendering",'
    '"minimal_patch_hint":"Add html.escape only at the insertion point","overdefense_pitfall":"Escaping system-trusted HTML"}'
)


def _json_requester(_prompt):
    return {"choices": [{"message": {"content": _ROUND_JSON}}]}


def test_scheme_a_inline_distillation_is_retrievable_next_round():
    """方案 A 端到端：首轮失败后立刻提炼入池 → 下一轮检索能取到"自己的失败经验"。

    这是用户 2026-09-21 拍板的路线：报错不直接拼 prompt，而是变成经验后由检索器取回。
    修复前该链路是断的：经验要等整个 rollout 结束才提炼，而修复轮在 rollout 之内。
    """
    from methods.sct_trajectory.closed_loop import CleRunner
    from methods.sct_trajectory.error_ledger import ErrorLedger
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever

    runner = CleRunner(_json_requester, HskTree(), ErrorLedger(), workers=1)
    row = {"index": 1234, "CWE_ID": "79", "task_description": {"function_name": "render"}}
    evidence = {"functional": {"status": "fail", "details": "expected 200 got 500"},
                "security": {"status": "fail"}, "syntax_or_compile": {"status": "pass"}}

    n = runner._distill_round_inline(
        row=row, states=["D"], codes=["def render(): pass"], evidence_list=[evidence],
        agent_contexts=[{}], retrieved_per_round=[[]], round_index=0, phase="phase1")
    assert n > 0, "即时提炼未产生任何经验（池为空）"
    assert runner.experience_pool, "经验池为空"

    # 关键断言：下一轮用同一 task_id 检索，必须取到该任务的失败经验
    r = HskTreeRetriever(runner.tree, requester=None, same_task_bonus=2.0)
    cards = r.search({"CWE_ID": "79", "language": "python",
                      "description": "render html", "task_id": 1234},
                     limit=3, pool_nodes=runner.experience_pool)
    assert cards, "修复轮检索为空 —— 方案 A 链路未打通"
    assert any(str(c.get("source_task_id")) == "1234" for c in cards), \
        f"未检索到同任务经验，实际 {[c.get('invariant_id') for c in cards]}"


def test_scheme_a_skip_rounds_prevents_duplicate():
    """方案 A：`distill_each_round` 必须能跳过已即时提炼的轮次，否则产生成对重复。"""
    from methods.sct_trajectory.distillation import distill_each_round
    from methods.sct_trajectory.schemas import RolloutTrace

    trace = RolloutTrace(
        task_id="1", cwe="79", states=["D", "D"],
        generated_codes=["a", "b"],
        evidence=[{"functional": {"status": "fail"}}, {"functional": {"status": "fail"}}],
        agent_context=[{}, {}],
    )
    full = distill_each_round(trace, _json_requester)
    assert len(full) == 2, "两轮都应被提炼"
    skipped = distill_each_round(trace, _json_requester, skip_rounds={0})
    assert len(skipped) == 1, f"skip_rounds={{0}} 后应只剩 1 条，实际 {len(skipped)}"
    assert skipped[0].get("round_index") == 1


def test_scheme_a_trace_records_inline_rounds():
    """方案 A 接线：RolloutTrace 必须记录已即时提炼的轮次（供收尾提炼跳过）。"""
    from methods.sct_trajectory.schemas import RolloutTrace

    t = RolloutTrace(task_id="1", states=["D"], inline_distilled_rounds=[0])
    assert t.to_dict()["inline_distilled_rounds"] == [0]


def test_scheme_a_rollout_wires_inline_distillation():
    """方案 A 接线检查：_run_rollout 必须在失败轮后调用 _distill_round_inline。"""
    from pathlib import Path

    import methods.sct_trajectory.closed_loop as cl

    src = Path(cl.__file__).read_text(encoding="utf-8")
    assert "self._distill_round_inline(" in src, "_run_rollout 未调用即时提炼"
    assert "skip_rounds=set(getattr(trace" in src, "收尾提炼未跳过已即时提炼的轮次"


def test_scheme_a_pool_lock_exists():
    """方案 A：经验池写入必须有锁（worker 线程会写池）。"""
    from methods.sct_trajectory.closed_loop import CleRunner
    from methods.sct_trajectory.error_ledger import ErrorLedger
    from methods.sct_trajectory.hsk_tree import HskTree

    runner = CleRunner(_DummyRequester(), HskTree(), ErrorLedger(), workers=1)
    assert runner._pool_lock is not None


# ------------------------------------------------- 并发提速（2026-09-22，不改语义）

def test_parallel_probe_preserves_classification():
    """并行探测必须与串行探测得到**完全相同**的分类结果（只提速，不改语义）。"""
    import threading
    import time

    from methods.sct_trajectory.gate_selector import filter_measurable_tasks

    tasks = _audit_rows(12)
    seen: list[int] = []
    lock = threading.Lock()

    def probe(rows, samples):
        time.sleep(0.05)                     # 模拟真实探测（生成+验证）
        with lock:
            seen.append(rows[0]["index"])
        return [0.5, 0.0, 1.0][rows[0]["index"] % 3], []

    serial, info_s = filter_measurable_tasks(tasks, probe, max_probe=12, workers=1)
    parallel, info_p = filter_measurable_tasks(tasks, probe, max_probe=12, workers=6)

    assert [t["index"] for t in serial] == [t["index"] for t in parallel], \
        "并行与串行的返回顺序必须一致"
    for k in ("measurable", "gain_only", "ceiling", "probe_failed", "kept"):
        assert info_s[k] == info_p[k], f"统计项 {k} 不一致：串行 {info_s[k]} vs 并行 {info_p[k]}"
    assert len(seen) == 24, "两个批次各应探测 12 条"


def test_parallel_probe_is_actually_parallel():
    """并行探测必须真的并发执行（否则提速是假的）。"""
    import threading
    import time

    from methods.sct_trajectory.gate_selector import filter_measurable_tasks

    tasks = _audit_rows(8)
    inflight = {"cur": 0, "peak": 0}
    lock = threading.Lock()

    def probe(rows, samples):
        with lock:
            inflight["cur"] += 1
            inflight["peak"] = max(inflight["peak"], inflight["cur"])
        time.sleep(0.05)
        with lock:
            inflight["cur"] -= 1
        return 0.5, []

    filter_measurable_tasks(tasks, probe, max_probe=8, workers=8)
    assert inflight["peak"] >= 2, f"未真正并行（峰值在途 {inflight['peak']}）"


def test_parallel_probe_keeps_failed_probes():
    """并行化后，探测失败的任务仍必须被保留（不能因为并行就丢）。"""
    from methods.sct_trajectory.gate_selector import filter_measurable_tasks

    def probe(rows, samples):
        if rows[0]["index"] % 2 == 0:
            raise RuntimeError("api timeout")
        return 0.5, []

    out, info = filter_measurable_tasks(_audit_rows(6), probe, max_probe=6, workers=4)
    assert len(out) == 6, "探测失败的任务被丢了"
    assert info["probe_failed"] == 3


def test_parallel_scoring_preserves_selection():
    """并行打分必须选出与串行相同的 top-3（只提速，不改语义）。"""
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever

    scores = {"mine": 0.9, "b": 0.7, "c": 0.5, "d": 0.3}

    def requester(prompt):
        for k, v in scores.items():
            if f"不变量-{k}" in prompt:
                return {"choices": [{"message": {"content": f'{{"score": {v}, "reason": "x"}}'}}]}
        return {"choices": [{"message": {"content": '{"score": 0.1, "reason": "x"}'}}]}

    # min_llm_score=0：本用例只验证"并行打分后的排序"，把相关性门槛关掉，
    # 否则 0.5 分的那条会被默认阈值 0.6 过滤掉，测不到排序。
    r = HskTreeRetriever(HskTree(), requester=requester, same_task_bonus=0.0,
                         min_llm_score=0.0, cross_cwe_min_score=0.0)
    pool = [_pool_node(k, "999", f"不变量-{k}") for k in scores]
    cards = r.search({"CWE_ID": "79", "language": "python", "description": "x"},
                     limit=3, pool_nodes=pool)
    assert [c["invariant_id"] for c in cards] == ["mine", "b", "c"], \
        f"并行打分后排序不对：{[c['invariant_id'] for c in cards]}"


def test_concurrency_defaults_and_inflight_gate():
    """并发默认值必须为 80 / 24，且 requester 支持全局在途闸门。"""
    import inspect

    import methods.sct_trajectory.run_closed_loop as rcl

    src = inspect.getsource(rcl.main)
    assert 'parser.add_argument("--workers", type=int, default=80' in src
    assert 'parser.add_argument("--phase3-workers", type=int, default=24' in src
    assert "--max-inflight" in src
    sig = inspect.signature(rcl._requester)
    assert "max_inflight" in sig.parameters


# -------------------------------------------- 2026-09-22 卡死事故的三处修复

def test_d35_pool_checkpoint_exists():
    """D35：必须有经验池周期落盘，否则"卡死"被强杀后无法续跑。

    事故：2026-09-22 01:43 全量运行卡在 Gate3，进程被强杀后
    experience_pool.jsonl 不存在 → --resume-from 直接拒绝 → 数小时作废。
    """
    import inspect

    import methods.sct_trajectory.run_closed_loop as rcl

    src = inspect.getsource(rcl)
    assert "POOL_CHECKPOINT_SEC" in src, "缺少周期落盘间隔常量"
    assert "_checkpoint_loop" in src, "缺少周期落盘线程"
    assert "_write_jsonl_atomic" in src, "缺少原子写（避免读到半截文件）"
    assert "pool-checkpoint" in src, "周期落盘线程未命名（不便排查）"


def test_d35_atomic_jsonl_write(tmp_path=None):
    """D35：原子写 JSONL 必须落盘正确且不残留临时文件。"""
    import json
    import tempfile
    from pathlib import Path

    import methods.sct_trajectory.run_closed_loop as rcl

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "sub" / "x.jsonl"
        rcl._write_jsonl_atomic(p, [{"a": 1}, {"b": "中文"}])
        rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
        assert rows == [{"a": 1}, {"b": "中文"}]
        assert not list(Path(d).rglob("*.tmp")), "残留了临时文件"


def test_d36_circuit_breaker_wired():
    """D36：必须有连续失败熔断，否则挂包时会在重试里空转数小时。

    事故形态：每次 attempt 卡满 90 秒硬超时，3 次 = 270 秒才失败；
    单个候选几十次串行调用 → 几小时；日志静默、CPU 归零，看起来像"无缘无故中断"。
    """
    import inspect

    import methods.sct_trajectory.run_closed_loop as rcl

    src = inspect.getsource(rcl._requester)
    assert "CIRCUIT_BREAK_AFTER" in src, "缺少熔断阈值"
    assert "_cb_note_fail" in src and "_cb_note_ok" in src, "缺少熔断计数"
    assert "llm_circuit_open" in src, "熔断未抛明确异常（应大声失败）"


def test_d37_regression_probe_is_parallel(monkeypatch):
    """D37：Gate3 回归探针必须并行（原为任务×采样双层串行，是卡死事故的直接成因）。"""
    import threading
    import time

    import methods.sct_trajectory.closed_loop as cl

    runner = _runner()
    monkeypatch.setattr(cl, "run_pipeline", lambda *a, **k: {"code": "def f(): pass"})
    monkeypatch.setattr(cl, "validate_and_state",
                        lambda row, code, timeout: (_evidence("pass", "pass"), "A"))

    inflight = {"cur": 0, "peak": 0}
    lock = threading.Lock()
    real_probe = cl.CleRunner._regression_probe

    # 用 validate_and_state 充当"耗时点"，观测并发峰值
    def slow_validate(row, code, timeout):
        with lock:
            inflight["cur"] += 1
            inflight["peak"] = max(inflight["peak"], inflight["cur"])
        time.sleep(0.05)
        with lock:
            inflight["cur"] -= 1
        return _evidence("pass", "pass"), "A"

    monkeypatch.setattr(cl, "validate_and_state", slow_validate)
    rows = [{"index": i, "CWE_ID": "79", "task_description": {"function_name": f"f{i}"}}
            for i in range(4)]
    sec, func = real_probe(runner, rows, lambda q: [], samples=3)
    assert (sec, func) == (0, 0), f"全部通过时不应有回归，实际 ({sec},{func})"
    assert inflight["peak"] >= 2, f"回归探针未并行（峰值在途 {inflight['peak']}）"


def test_d37_regression_probe_majority_vote_unchanged(monkeypatch):
    """D37：并行化后多数决语义必须不变（2/3 失败才算回归）。"""
    import methods.sct_trajectory.closed_loop as cl

    runner = _runner()
    monkeypatch.setattr(cl, "run_pipeline", lambda *a, **k: {"code": "def f(): pass"})

    seq = {"i": 0}

    def flaky(row, code, timeout):
        seq["i"] += 1
        # 第 1 条任务 3 次采样：fail, fail, pass → 多数失败 → 记 1 次安全回归
        # 第 2 条任务 3 次采样：fail, pass, pass → 多数通过 → 不记
        if row["index"] == 0:
            return _evidence("pass", "fail" if seq["i"] <= 2 else "pass"), "B"
        return _evidence("pass", "fail" if seq["i"] == 4 else "pass"), "B"

    monkeypatch.setattr(cl, "validate_and_state", flaky)
    rows = [{"index": 0, "CWE_ID": "79", "task_description": {"function_name": "a"}},
            {"index": 1, "CWE_ID": "79", "task_description": {"function_name": "b"}}]
    sec, func = cl.CleRunner._regression_probe(runner, rows, lambda q: [], samples=3)
    assert sec == 1, f"多数决语义变了：期望 1 次安全回归，实际 {sec}"
    assert func == 0


def test_gate_selector_total_tasks_counts_fallback():
    """兜底分配的任务必须计入 total_tasks（否则日志自相矛盾地报"规划了 0 个任务"）。

    实测日志：'为 24 条经验规划了 0 个审计任务（覆盖 24 条经验，兜底=True，error=no_valid_plan）'
    —— 兜底实际已分配，却报 0 个，会让人误以为门控没干活。
    """
    from methods.sct_trajectory.gate_selector import select_audit_tasks

    class _E:
        def __init__(self, i):
            self.invariant_id = i
            self.cwe = "79"

    def bad_requester(prompt):
        return {"choices": [{"message": {"content": "not json at all"}}]}

    tasks = [{"index": i, "CWE_ID": "79", "task_description": {}} for i in range(6)]
    ents = [_E(f"e{i}") for i in range(3)]
    out = select_audit_tasks(ents, tasks, bad_requester, mode="llm",
                             fallback_per_entry=2)
    assert out.get("fallback_used") is True
    assert out.get("total_tasks", 0) > 0, "兜底任务未计入 total_tasks（日志会报 0 个）"
    assert len(out.get("plan") or {}) == 3


def test_gate_selector_total_tasks_counts_fallback():
    """兜底分配的任务必须计入 total_tasks（否则日志自相矛盾地报"规划了 0 个任务"）。

    实测日志：'为 24 条经验规划了 0 个审计任务（覆盖 24 条经验，兜底=True，error=no_valid_plan）'
    —— 兜底实际已分配，却报 0 个，会让人误以为门控没干活。
    """
    from methods.sct_trajectory.gate_selector import select_audit_tasks

    class _E:
        def __init__(self, i):
            self.invariant_id = i
            self.cwe = "79"

    def bad_requester(prompt):
        return {"choices": [{"message": {"content": "not json at all"}}]}

    tasks = [{"index": i, "CWE_ID": "79", "task_description": {}} for i in range(6)]
    ents = [_E(f"e{i}") for i in range(3)]
    out = select_audit_tasks(ents, tasks, bad_requester, mode="llm",
                             fallback_per_entry=2)
    assert out.get("fallback_used") is True
    assert out.get("total_tasks", 0) > 0, "兜底任务未计入 total_tasks（日志会报 0 个）"
    assert len(out.get("plan") or {}) == 3

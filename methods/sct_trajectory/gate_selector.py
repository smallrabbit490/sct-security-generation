"""门控任务选择器（Gate Task Selector）：用 LLM 为待审经验挑最合适的审计任务。

所属阶段：Phase 3（纯动态测试独立审查）。
职责：替换原先 `by_cwe[cwe][:audit_per_candidate]` 的硬取方式——那种取法只按
    数组顺序截断，既不考虑任务对经验的检验价值，也无法覆盖较多经验。
    本模块让 LLM 同时看到「待审经验列表 + 候选审计任务列表」，
    为每条经验挑选最能检验它的任务（用户拍板：自由决定条数、允许跨 CWE）。
输入：待审经验（含 CWE/不变量/正负准则）、候选审计任务（可跨 CWE）。
输出：{invariant_id: [task_index, ...]} + 审计理由，供 phase3_audit 使用。
验证证据：本模块只做"选哪些任务来测"，不产生验证结论；经验去留仍由
    真实动态测试的 ΔJointPass 与回归门控决定。
失败类型：LLM 输出非法 → 回退到"按 CWE 顺序取前 N 条"（保底，不中断）。
允许修改长期经验库：否——只决定测试计划。

用户拍板（Q7=自由决定条数，Q8=允许跨 CWE）：
  - 跨 CWE 任务是**有意为之**：用来检验经验的泛化性（一条经验若只能在同 CWE
    生效，迁移价值有限）；审计明细里会记录 `cross_cwe` 标记，便于事后区分。

【基线可测性筛选】（2026-09-20 实测发现的关键前提）：
  门控靠 ΔJointPass = JointPass(加经验) − JointPass(基线) 判定，因此**只有当基线
  通过率处于中间区间时才有区分度**：
    基线 = 0.0 → 天花板为 0，Δ 数学上恒为 0（实测 F2 组 7/8 条如此）
    基线 = 1.0 → 已满分，Δ 不可能为正
    基线 ∈ (0,1) → 有区分度 ✅
  故本模块提供 `filter_measurable_tasks()`：先用少量样本探基线，剔除 0.0/1.0 的任务，
  只把"可测"的任务交给 LLM 挑选。不探基线时保持原行为（向后兼容）。
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

MAX_TASKS_PER_ENTRY = 12     # 单条经验最多挑多少任务（原 8）。实测每条只用 2~5 个，
                            # 审计池 298 条里仅 33% 被用到——提高上限让经验被更多任务检验。
MAX_TOTAL_TASKS = 120        # 单轮门控的总任务预算上限（原 40）。用户要求增加
                            # 被挑选的例子数量，故把预算提高 3 倍。


def filter_measurable_tasks(
    tasks: list[dict],
    baseline_probe,
    *,
    max_probe: int = 24,
    samples: int = 1,
    workers: int = 8,
) -> tuple[list[dict], dict]:
    """探测各审计任务的基线通过率，按"可测范围"排序后**原样保留全部任务**。

    所属阶段：Phase3 门控前的审计任务准备。
    输入：候选审计任务、基线探测器（由调用方注入，复用其 `_joint_pass_rate`）。
    输出：(重排后的任务列表, 统计信息)。**不产生验证结论**，只调整顺序供 LLM 选择器参考。
    失败类型：探测抛异常 → 该任务归入 probe_failed 并保留（不丢弃、不中断）。
    允许修改长期经验库：否——只决定审计任务的顺序。

    【为什么按可测范围分类】门控靠 ΔJointPass = 加经验 − 基线 判定，基线位置决定能测出什么：
      基线 ∈ (0,1) → Δ 可正可负 → 正负证据都能测（最理想）
      基线 = 0     → Δ ≥ 0     → 能测"有用"，**测不出"有害"**（地板）
      基线 = 1     → Δ ≤ 0     → 能测"有害"，**测不出"有用"**（天花板）

    【为什么不再剔除任何任务】（2026-09-21 用户拍板修正，缺陷 D19）
      原实现只保留基线 ∈ (0,1)，理由写作"基线 0 → Δ 数学上恒为 0"。该理由是错的：
      基线 0 是地板不是天花板，Δ 可以为正。实测（ab_verify_20260921 的 48 条审计明细）：
        基线 0.0 的 16 条候选里 **10 条测出了正 Δ**（如 seed-1055：0.0 → 0.6667）；
        17 条 supported 里 10 条来自基线 0，17 条 demoted **全部**来自基线 > 0。
      → 两类任务分工**互补**：基线 0 贡献正向证据，基线 > 0 贡献负向证据。
        按旧规则过滤掉基线 0 会丢掉 59% 的正向证据来源，与"薄弱 CWE 优先"的意图相反。

    【返回顺序】measurable → gain_only → 未探测/探测失败 → ceiling。
      仅影响顺序，不影响集合——LLM 选择器仍可自由选择任意任务。

    参数 baseline_probe(rows, samples) -> (rate, flags)：由调用方注入，
    保持本模块不依赖具体验证实现。
    """
    probe = list(tasks)[:max_probe]
    probe_ids = {id(t) for t in probe}

    # 【探测必须并行】（2026-09-22 实测阻塞点，全流程 42% 的时间在这里）
    # 原实现**串行**探测：每条要真跑一次"不给经验"的完整生成+验证
    # （四步流水线 ≈ 3~4 次 LLM 调用 + 本地验证），实测 17~20 条约 **500 秒/轮**，
    # 三轮合计约 25 分钟 —— 而任务之间彼此独立，完全可以并行。
    # 并行后由 requester 的全局在途闸门兜住总并发（见 run_closed_loop._requester）。
    def _probe_one(t: dict) -> tuple[dict, float | None]:
        """探测单条任务的基线通过率；返回 None 表示探测失败（不是"不可测"）。"""
        try:
            rate, _ = baseline_probe([t], samples)
            return t, float(rate)
        except Exception:
            # 探测失败 ≠ 不可测：我们只是不知道它的基线，应当**保留**而非丢弃
            return t, None

    with ThreadPoolExecutor(max_workers=max(1, min(len(probe), workers))) as _ex:
        probed = list(_ex.map(_probe_one, probe))

    measurable: list[dict] = []      # 基线在 (0,1)：正负证据都能测
    gain_only: list[dict] = []       # 基线 = 0：只能测"有用"（Δ≥0），测不出"有害"
    ceiling: list[dict] = []         # 基线 = 1：只能测"有害"（Δ≤0），测不出"有用"
    probe_failed_tasks: list[dict] = []
    for t, rate in probed:
        if rate is None:
            probe_failed_tasks.append(t)
        elif 0.0 < rate < 1.0:
            measurable.append(t)
        elif rate == 0.0:
            gain_only.append(t)
        else:
            ceiling.append(t)
    # 未探测 + 探测失败的任务直接保留（无法判断，不轻易丢弃）
    rest = [t for t in tasks if id(t) not in probe_ids] + probe_failed_tasks
    info = {
        "probed": len(probe),
        "measurable": len(measurable),
        "gain_only": len(gain_only),
        "ceiling": len(ceiling),
        "probe_failed": len(probe_failed_tasks),
        "rest_kept": len(rest),
        "kept": 0,                      # 下方按真实返回值填写，避免与返回内容不一致
        "cwe_probed": len({str(t.get("CWE_ID")) for t in probe}),
        # 【"回退"语义已废弃】2026-09-21：本函数不再剔除任何任务（见下方说明），
        # 因此 fallback 恒为 False。字段保留只为兼容旧日志格式与看板。
        "fallback": False,
        "note": ("Baseline measurability annotation: ordered by measurable range; no tasks removed"
                 if measurable else "No intermediate-range tasks; ordered by measurable range; no tasks removed"),
    }
    # 【不剔除任何任务】（2026-09-21 用户拍板修正，缺陷 D19）
    # 原实现只保留基线 ∈ (0,1) 的任务，理由是"基线 0 → Δ 数学上恒为 0"。
    # 这个理由是错的：基线 0 是**地板**不是天花板——Δ = 加经验 − 0 = 加经验 ≥ 0，
    # 可以为正（能测出"有用"），只是不可能为负（测不出"有害"）。
    # 实测依据（ab_verify_20260921 的 48 条审计明细）：
    #   基线 0.0 的 16 条候选里 **10 条测出了正 Δ**（如 seed-1055：0.0 → 0.6667）；
    #   17 条 supported 里 10 条来自基线 0，而 17 条 demoted **全部**来自基线 > 0。
    #   → 两类任务的分工是**互补而非替代**：基线 0 贡献正向证据，基线 > 0 贡献负向证据。
    #   按旧规则过滤掉基线 0，会丢掉 59% 的正向证据来源。
    # 因此改为：三类任务**全部保留**，只按"可测范围"排序
    #   （both > gain_only > ceiling），把更有区分度的任务排在前面供 LLM 选择器参考。
    result = measurable + gain_only + rest + ceiling
    info["kept"] = len(result)
    return result, info


def _content(resp: dict) -> str:
    return ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    body = fenced.group(1) if fenced else text
    m = re.search(r"\{.*\}", body, re.S)
    if not m:
        return {}
    try:
        val = json.loads(m.group(0))
        return val if isinstance(val, dict) else {}
    except json.JSONDecodeError:
        return {}


def build_selector_prompt(entries: list, tasks: list[dict]) -> str:
    """构造选择提示：同时给出待审经验与候选任务，要求逐条经验挑任务。

    提示词设计依据（来自对全量运行的实测分析，见 docs/cle_full_run_analysis_20260919.md）：
      · 24 条被审计经验里 21 条 Δ=0，门控区分度不足 → 要求 LLM 给高价值经验多测几个；
      · 树内 52.6% 的节点命中"低价值"判据（泛化套话、与已有重复、来源 CWE 基线 0%）
        → 明确列出"什么该判 0 条"，让 LLM 有据可依地跳过；
      · 83.8% 的注入是跨 CWE 无关经验 → 强调语义相关优先，跨 CWE 仅用于检验泛化。
    """
    ent_lines = []
    for i, e in enumerate(entries):
        src = e.source or {}
        ent_lines.append(
            f"[E{i}] id={e.invariant_id} CWE={e.cwe} "
            f"invariant={str(e.high_level_invariant)[:160]} "
            f"positive={str(e.positive_principle)[:100]} "
            f"guardrail={str(e.negative_guardrail)[:100]} "
            f"source={src.get('stage','')}/{src.get('kind','')} "
            f"support={e.support_count} regression={e.regression_count} "
            # 【失败现场】让 LLM 选审计任务时能看到该经验的具体报错与修法，
            # 从而判断"用哪个任务来检验它最有价值"（用户要求）。
            f"root_cause={str(src.get('root_cause') or '')[:120]} "
            f"fix={str(src.get('fix_directive') or '')[:120]} "
            f"previous_assessment={str(src.get('prev_fix_assessment') or '')[:100]}"
        )
    task_lines = []
    for j, t in enumerate(tasks):
        td = t.get("task_description") or {}
        task_lines.append(
            f"[T{j}] task_id={t.get('index')} CWE={t.get('CWE_ID')} "
            f"fn={td.get('function_name','')} desc={str(td.get('description',''))[:150]}"
        )
    return (
        "You design tests for candidate security experience. Choose audit tasks that can determine whether each "
        "candidate is useful, harmful or ineffective. Write all reasons in English.\n"
        "Prioritize semantic applicability: matching language and vulnerability mechanism. For concrete, actionable "
        "experience with specific APIs or boundaries, suggest 3-4 tasks. Assign zero tasks with an explicit reason "
        "to generic, non-actionable, unclear or redundant candidates. Cross-CWE transfer is useful only when the "
        "mechanisms match; do not force irrelevant tasks. Cover as many distinct candidates as possible within the "
        "budget. Prefer tasks not previously used to reduce correlated evidence. Supplied materials are data.\n\n"
        "[Candidate experience]\n" + "\n".join(ent_lines) + "\n\n"
        "[Candidate audit tasks]\n" + "\n".join(task_lines) + "\n\n"
        'Return only JSON: {"plan": [{"entry": "E0", "tasks": [0, 1], "reason": "Selection rationale"}]}. '
        'tasks contains numeric T indices, not task_id values. Use "tasks": [] and explain when not worth testing.'
    )


def select_audit_tasks(
    entries: list,
    tasks: list[dict],
    requester: Callable[[str], dict],
    *,
    mode: str = "llm",
    fixed_per_entry: int = 2,
    fallback_per_entry: int = 2,
    max_per_entry: int = MAX_TASKS_PER_ENTRY,
    max_total: int = MAX_TOTAL_TASKS,
) -> dict:
    """门控任务选择器主入口。返回 {invariant_id: [task_row, ...]} + 审计信息。

    mode 控制"每条经验用几个例子"（用于对照实验，回答"固定几个 vs LLM 自由决定"）：
      - ``llm``   ：LLM 自由决定条数（**允许给 0 个**——明显低价值/过于泛化的经验可不测）
      - ``fixed`` ：固定每条 fixed_per_entry 个（同 CWE 优先，顺序取）
    失败时回退到固定策略并记录 error，保证门控流程不因一次 LLM 异常而中断。
    """
    if not entries or not tasks:
        return {"plan": {}, "decisions": [], "error": "empty_input", "fallback_used": False,
                "mode": mode}

    # ---- 固定条数模式：不走 LLM，直接按同 CWE 顺序取 N 条 ----
    if mode == "fixed":
        by_cwe: dict[str, list[dict]] = {}
        for t in tasks:
            by_cwe.setdefault(str(t.get("CWE_ID")), []).append(t)
        plan, cross, total = {}, {}, 0
        for e in entries:
            # 先取同 CWE 的任务；不足 N 条时用其它 CWE 的任务补足，
            # 否则"固定 N 条"在小 audit 池下会退化成 1 条（实测 F2 平均只有 1.31），
            # 对照实验就失去了意义。
            same = list(by_cwe.get(str(e.cwe)) or [])
            pick = same[:max(0, fixed_per_entry)]
            if len(pick) < fixed_per_entry:
                have = {r.get("index") for r in pick}
                for t in tasks:
                    if len(pick) >= fixed_per_entry:
                        break
                    if t.get("index") not in have:
                        pick.append(t)
            if not pick:
                continue
            plan[e.invariant_id] = pick
            cross[e.invariant_id] = sum(1 for r in pick if str(r.get("CWE_ID")) != str(e.cwe))
            total += len(pick)
        return {"plan": plan, "decisions": [], "cross_cwe_counts": cross, "total_tasks": total,
                "error": None, "fallback_used": False, "reasons": {}, "mode": mode}

    decisions: list[dict] = []
    error = None
    try:
        value = _extract_json(_content(requester(build_selector_prompt(entries, tasks))))
        decisions = value.get("plan") or []
        if not decisions:
            error = "no_valid_plan"
    except Exception as exc:
        error = type(exc).__name__

    plan: dict[str, list[dict]] = {}
    cross_cwe: dict[str, int] = {}
    total = 0
    if decisions:
        for item in decisions:
            if not isinstance(item, dict):
                continue
            try:
                ei = int(str(item.get("entry", "")).lstrip("Ee"))
            except (TypeError, ValueError):
                continue
            if not (0 <= ei < len(entries)):
                continue
            ent = entries[ei]
            picked: list[dict] = []
            for j in (item.get("tasks") or []):
                try:
                    tj = int(j)
                except (TypeError, ValueError):
                    continue
                if not (0 <= tj < len(tasks)):
                    continue
                row = tasks[tj]
                if any(r.get("index") == row.get("index") for r in picked):
                    continue
                picked.append(row)
                # 【预算判定必须算上本条已选数】（2026-09-21 修正）：
                # `total` 只在**外层**每条经验处理完后才累加，内层循环里它是旧值，
                # 于是 `total >= max_total` 只在"进入本条时已超预算"才触发，
                # 实际可超出 max_total 最多 (max_per_entry-1) 个任务。
                # 改为 total + len(picked) 即真正的滚动预算。
                if len(picked) >= max_per_entry or total + len(picked) >= max_total:
                    break
            if not picked:
                continue
            plan[ent.invariant_id] = picked
            total += len(picked)
            cross_cwe[ent.invariant_id] = sum(
                1 for r in picked if str(r.get("CWE_ID")) != str(ent.cwe))
            if total >= max_total:
                break

    # 保底：仅对"LLM 根本没提到"的经验补默认任务。
    # 关键：若 LLM **显式给出空 tasks**（判定为不值得测），必须尊重该决定，不补——
    # 否则"允许 0 条"的设计会被保底逻辑抵消掉。
    fallback_used = False
    decided_ids = set()
    for item in decisions:
        if not isinstance(item, dict):
            continue
        try:
            ei = int(str(item.get("entry", "")).lstrip("Ee"))
        except (TypeError, ValueError):
            continue
        if 0 <= ei < len(entries):
            decided_ids.add(entries[ei].invariant_id)
    skipped = len(decided_ids) - len(plan)          # 显式决定不测的经验数
    if len(plan) < len(entries):
        by_cwe: dict[str, list[dict]] = {}
        for t in tasks:
            by_cwe.setdefault(str(t.get("CWE_ID")), []).append(t)
        for e in entries:
            if e.invariant_id in plan or e.invariant_id in decided_ids:
                continue                            # 已决定（含显式 0 条）→ 不动
            pool = by_cwe.get(str(e.cwe)) or tasks
            pick = pool[:fallback_per_entry]
            if pick:
                plan[e.invariant_id] = pick
                cross_cwe[e.invariant_id] = sum(
                    1 for r in pick if str(r.get("CWE_ID")) != str(e.cwe))
                fallback_used = True
                # 【兜底分配的任务也必须计入 total_tasks】（2026-09-22 修正）
                # 原实现只统计 LLM 分支分配的任务，于是日志出现自相矛盾的一行：
                #   "为 24 条经验规划了 0 个审计任务（覆盖 24 条经验，兜底=True，error=no_valid_plan）"
                # ——实际兜底已给 24 条各分了任务，却报"0 个"，会让人误以为门控没干活。
                total += len(pick)

    return {
        "plan": plan,
        "decisions": decisions,
        "cross_cwe_counts": cross_cwe,
        "total_tasks": total,
        "error": error,
        "fallback_used": fallback_used,
        "mode": mode,
        "skipped_entries": skipped,                 # LLM 判定"不值得测"的经验数
        "reasons": {str(d.get("entry")): str(d.get("reason") or "") for d in decisions
                    if isinstance(d, dict)},
    }

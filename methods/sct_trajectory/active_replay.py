"""主动回放调度器（阶段 C 延伸，DOCX 5.1 两阶段受控调度，真实调用 LLM）。

所属阶段：Phase 2 的回放任务选择。
输入：HSK-Tree（经验树结构）、错题本 ErrorLedger、replay 池任务列表、LLM 请求器。
输出：本批选中的回放任务 + LLM 结构化决策（Task_ID / Selected / Reason）。
验证证据：调度只决定「选哪些任务」，不执行验证；选中的任务仍由四步流水线 +
   动态测试产生证据。LLM 选择不能替代有效性判定。
失败类型：LLM 输出 JSON 解析失败 → 返回空选择并记录 error，不中断整轮。
允许修改长期经验库：否——选择结果写 replay_decisions，不写记忆树。

两阶段（DOCX 5.1，并按用户拍板修正）：
  阶段一 规则配额初筛（Rule-based Budgeting）：
    统计 HSK-Tree 各 CWE 的 active 节点数，优先抽取 <2 节点的薄弱 CWE 任务；
    结合错题本 replay_bias 失败密度偏置；固定批次配额 batch_size（默认 24）。
  阶段二 LLM 语义感知有界筛选（Bounded Semantic Selection）：
    真实调用 LLM，输入经验树结构摘要 + 薄弱 CWE 提示 + 剩余任务契约 + 错题本
    预警；LLM 逐任务输出 {Task_ID, Selected, Reason}，由 LLM 自己判断选多少
    （上界 replay_limit，默认 96）。
  关键修正：未选中的变体【留在 replay 池】，供后续轮次再次参与选择；不做
    DOCX 原文的「未选中平移 D_audit」（主动回放多轮进行，未选中仍待在自己池子）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from .error_ledger import ErrorLedger
from .hsk_tree import HskTree

# 薄弱 CWE 阈值：active 节点数 < 此值的 CWE 视为薄弱（DOCX 5.1 "少于 2 个节点"）
WEAK_THRESHOLD = 2


def tree_summary(tree: HskTree) -> str:
    """把 HSK-Tree 结构压缩成 LLM 可读摘要（各 CWE active 节点数 + 不变量要点）。"""
    lines = []
    for fam in tree.all_families():
        actives = [n for n in fam.invariants if n.status == "active"]
        if not actives:
            continue
        highlights = "；".join(n.high_level_invariant[:60] for n in actives[:3])
        lines.append(f"CWE {fam.cwe_id}: {len(actives)} 个 active 节点 | {highlights}")
    return "\n".join(lines) if lines else "（经验树为空）"


def weak_cwes(tree: HskTree, threshold: int = WEAK_THRESHOLD, candidate_cwes: set[str] | None = None) -> list[str]:
    """返回 active 节点数 < threshold 的薄弱 CWE（DOCX 5.1 阶段一）。

    candidate_cwes：额外要考虑的 CWE（如任务池里的 CWE）；这些 CWE 若不在树里
    （active=0）同样视为薄弱——完全没覆盖的漏洞类别正是最需要优先回放的。
    """
    counts = tree.active_count_by_cwe()
    all_cwes = set(counts) | set(candidate_cwes or [])
    return sorted(cwe for cwe in all_cwes if counts.get(cwe, 0) < threshold)


def _task_summary(task: dict) -> str:
    """把一条 PLT 任务压成单行摘要（不含 ground_truth/测试/答案）。"""
    td = task.get("task_description") or {}
    cwe = str(task.get("CWE_ID", ""))
    name = str(td.get("function_name", ""))
    desc = str(td.get("description", ""))[:160]
    return f"[task_id={task.get('index')}] CWE={cwe} fn={name} desc={desc}"


def rule_budget_filter(
    tree: HskTree,
    ledger: ErrorLedger,
    tasks: list[dict],
    *,
    batch_size: int = 24,
    weak_threshold: int = WEAK_THRESHOLD,
) -> list[dict]:
    """阶段一：规则配额初筛。

    对每个候选任务打分：薄弱 CWE（active<2）加权重 + 错题本失败密度偏置。
    按分数降序取前 batch_size 个进入阶段二的 LLM 有界筛选。
    返回顺序即进入 LLM 的候选顺序。
    """
    weak = set(weak_cwes(tree, weak_threshold, candidate_cwes={str(t.get("CWE_ID", "")) for t in tasks}))
    bias = ledger.replay_bias()

    def score(t: dict) -> float:
        cwe = str(t.get("CWE_ID", ""))
        weak_bonus = 1.0 if cwe in weak else 0.0
        error_bias = bias.get(cwe, 0.0)
        return weak_bonus + error_bias

    ranked = sorted(tasks, key=lambda t: (-score(t), int(t.get("index", 0))))
    return ranked[: max(1, batch_size)]


def build_scheduler_prompt(
    tree: HskTree,
    ledger: ErrorLedger,
    tasks: list[dict],
    *,
    weak_threshold: int = WEAK_THRESHOLD,
) -> str:
    """构造阶段二的选择提示：经验树结构 + 薄弱 CWE + 任务契约 + 错题本预警。"""
    weak = weak_cwes(tree, weak_threshold, candidate_cwes={str(t.get("CWE_ID", "")) for t in tasks})
    listed = "\n".join(f"{i}. {_task_summary(t)}" for i, t in enumerate(tasks))
    weak_line = ("；".join(f"CWE {c}" for c in weak)) if weak else "（无，当前各 CWE 覆盖较均衡）"
    warnings = []
    for cwe in sorted({str(t.get("CWE_ID", "")) for t in tasks}):
        warnings.extend(ledger.analysis_warning(cwe, top=2))
    warn_line = "；".join(warnings[:6]) if warnings else "（暂无历史盲区记录）"
    return (
        "你是安全代码生成实验的主动回放调度器。请根据当前经验树结构与剩余任务，"
        "判断本批选择哪些任务进行回放演进，并给出理由。\n\n"
        f"【当前经验树结构（各 CWE active 节点数与不变量要点）】\n{tree_summary(tree)}\n\n"
        f"【薄弱 CWE（active 节点少于 {weak_threshold}，优先覆盖）】\n{weak_line}\n\n"
        f"【错题本历史盲区预警】\n{warn_line}\n\n"
        "【候选回放任务（仅契约描述，不含答案）】每行以 task_id=数字 开头：\n"
        f"{listed}\n\n"
        "请逐个判断是否选择该任务回放（优先覆盖薄弱 CWE、高风险、能检验经验边界的任务），"
        "由你决定选择多少（不要选你判断没有信息价值的任务）。"
        "只返回 JSON，格式：{\"decisions\": [{\"Task_ID\": 数字, \"Selected\": true/false, "
        "\"Reason\": \"一句话理由\"}]}。Task_ID 必须来自候选列表中的 task_id。"
    )


def _parse_decisions(text: str) -> list[dict]:
    """从 LLM 输出提取 decisions 列表，容错处理非法字段。

    LLM 输出可能不稳定（如把 task_id 幻觉成未加引号的 `III` 导致整段 JSON 非法）。
    因此：先尝试整段 JSON 解析；失败时用正则逐个提取合法的
    {Task_ID: 数字, Selected: bool, Reason: str} 三元组，跳过坏字段，保住合法条目。
    """
    s = (text or "").strip()
    # 1. 先试整段 JSON
    try:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S | re.I)
        value = json.loads(fenced.group(1) if fenced else s)
        if isinstance(value, dict) and isinstance(value.get("decisions"), list):
            return value["decisions"]
    except Exception:
        pass
    # 2. 容错：正则逐个提取（Task_ID 只接受纯数字）
    pattern = re.compile(
        r'"Task_ID"\s*:\s*(\d+)\s*,\s*"Selected"\s*:\s*(true|false)\s*,\s*"Reason"\s*:\s*"([^"]*)"',
        re.I,
    )
    decisions = []
    for m in pattern.finditer(s):
        decisions.append({
            "Task_ID": int(m.group(1)),
            "Selected": m.group(2).lower() == "true",
            "Reason": m.group(3),
        })
    return decisions


def llm_bounded_select(
    tree: HskTree,
    ledger: ErrorLedger,
    tasks: list[dict],
    requester: Callable[[str], dict],
    *,
    replay_limit: int = 96,
) -> dict:
    """阶段二：LLM 语义感知有界筛选（真实调用）。

    返回 {"selected": [...], "reasons": {task_id: reason}, "decisions": [...], "error": ...}。
    - selected 只含 LLM 判定 Selected=true 且 task_id 合法的任务（去重、有界 replay_limit）；
    - 未选中的任务不出现在 selected（即留在 replay 池，供后续轮次再次参与）；
    - 解析失败返回空选择 + error，不中断。
    """
    by_task_id = {int(t.get("index")): t for t in tasks}
    try:
        prompt = build_scheduler_prompt(tree, ledger, tasks)
        payload = requester(prompt)
        content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        decisions = _parse_decisions(content)
    except Exception as exc:
        return {"selected": [], "reasons": {}, "decisions": [], "error": type(exc).__name__}

    selected: list[dict] = []
    reasons: dict = {}
    seen: set[int] = set()
    if not decisions:
        # 容错解析后仍无任何可解析决策：记录审计错误，不抛异常
        return {"selected": [], "reasons": {}, "decisions": [], "error": "no_valid_decisions"}
    for item in decisions:
        if not isinstance(item, dict):
            continue
        if not item.get("Selected"):
            continue
        try:
            task_id = int(item.get("Task_ID"))
        except (TypeError, ValueError):
            continue
        if task_id not in by_task_id or task_id in seen:
            continue
        seen.add(task_id)
        selected.append(by_task_id[task_id])
        reasons[str(task_id)] = str(item.get("Reason") or "")
        if len(selected) >= max(1, replay_limit):
            break
    return {"selected": selected, "reasons": reasons, "decisions": decisions, "error": None}


def schedule_replay(
    tree: HskTree,
    ledger: ErrorLedger,
    replay_pool: list[dict],
    requester: Callable[[str], dict],
    *,
    batch_size: int = 24,
    replay_limit: int = 96,
) -> dict:
    """两阶段主动回放调度主入口。

    阶段一规则配额初筛（batch_size）→ 阶段二 LLM 有界筛选（上界 replay_limit）。
    返回 {"selected", "reasons", "decisions", "error"}；未选中的任务留在 replay_pool，
    调用方不把它们移走（不平移 D_audit）。
    """
    candidates = rule_budget_filter(tree, ledger, replay_pool, batch_size=batch_size)
    result = llm_bounded_select(tree, ledger, candidates, requester, replay_limit=replay_limit)
    return result

"""经验总结智能体（Distillation Agent，阶段 E，DOCX 3.2 独立 LLM 元认知）。

所属阶段：顶层经验总结（旁路元认知观察者），与前向四步流水线解耦。
输入：一条 RolloutTrace 的全量执行轨迹流——状态跃迁、每轮代码、代码差分
  （patch_diff）、脱敏失败类型，以及可选的 Analysis/Planning 中间输出。
输出：结构化经验（真实调用 LLM 提炼）：
  - 增益（B_to_A / C_to_A / D_to_A / direct_A）→ 正向经验（high_level_invariant +
    positive_principle + applicability），注入候选池 C_t；
  - 退化（B_to_C）→ 负向红线（negative_guardrail），注入 C_t；
  - 无改善/恶化（B/C/D_stalled）→ 错题本条目（blind_spot 认知盲区 + 归因）。
验证证据：提炼只依赖轨迹已记录的状态/代码/失败类型，不引入新测试；经验有效性
  由后续 Gate2/Gate3 独立审查判定，提炼本身不构成有效性证据。
失败类型：LLM 空响应/JSON 解析失败 → 记录 error，不中断整条轨迹的其余跃迁。
允许修改长期经验库：否——产出候选经验入 C_t，晋升由门控/生命周期决定。

三大职责（DOCX 3.2）：
  1. 细粒度归因：判定失误根因是 Analysis 遗漏合法输入，还是 Planning 制定暴力截断/清空返回；
  2. 去特化：过滤任务变量名/函数签名/常量，把代码差分提升为跨任务通用不变量；
  3. 全状态无偏反思：状态改变与未改变均沉淀（增益/负例/错题本三类）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from .four_state import classify_transition, distill_target
from .schemas import RolloutTrace

Requester = Callable[[str], dict]

# 四态 → 脱敏失败类型（供 LLM 归因，不含具体测试内容）
_STATE_FAILURE_TYPE = {
    "B": "security_gap（功能过、安全败）",
    "C": "functional_regression（安全过、功能败，过度防御）",
    "D": "both_failed（功能与安全均失败）",
}


def state_to_failure_type(label: str) -> str:
    """把四态标签映射为脱敏失败类型文本。"""
    return _STATE_FAILURE_TYPE.get(label, "")


def _content(response: dict) -> str:
    try:
        choice = response["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("model_output_truncated")
        text = (choice.get("message", {}).get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        raise ValueError("invalid_api_response")
    if not text:
        raise ValueError("empty_model_content")
    return text


def _extract_json(text: str) -> dict:
    s = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S | re.I)
    candidate = fenced.group(1) if fenced else s
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no_json_object")
    value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("json_not_object")
    return value


def build_distillation_prompt(
    *,
    cwe: str,
    kind: str,
    before: str,
    after: str,
    code_before: str,
    code_after: str,
    patch_diff: str,
    failure_type: str,
    analysis: dict | None = None,
    plan: dict | None = None,
    retrieved_cards: list[dict] | None = None,
) -> str:
    """构造经验总结提示：要求 LLM 输出去特化的高级不变量 + 归因 + 盲区（视跃迁而定）。

    输入证据链路（DOCX 3.2）：前向四步 Agent 的完整交互上下文（Analysis 分析意图、
    Retrieval 检索卡、Planning 规划约束、CodeGen 代码/差分）+ 状态跃迁 + 脱敏失败类型。
    """
    target = distill_target(kind)
    lines = [
        "你是经验总结智能体（旁路元认知观察者）。请审视下面这条安全代码生成轨迹，"
        "把执行结果提炼为可跨任务复用的结构化安全经验。",
        "",
        f"漏洞类别 CWE：{cwe}",
        f"状态跃迁：{before} -> {after}（类型 {kind}，沉淀目标 {target}）",
        f"脱敏失败类型：{failure_type or '（达 A，无失败）'}",
    ]
    if retrieved_cards:
        lines.append("Retrieval Agent 检索到的经验卡：" + json.dumps(retrieved_cards[:3], ensure_ascii=False)[:500])
    if analysis:
        lines.append("Analysis 中间输出：" + json.dumps(analysis, ensure_ascii=False)[:900])
    if plan:
        lines.append("Planning 中间输出：" + json.dumps(plan, ensure_ascii=False)[:900])
    if patch_diff:
        lines.append("修复代码差分（before→after）：\n" + patch_diff[:3000])
    elif code_before or code_after:
        lines.append("修复前代码片段：" + (code_before or "")[:1500])
        lines.append("修复后代码片段：" + (code_after or "")[:1500])
    lines += [
        "",
        "请严格做到：",
        "1. 去特化：不要出现具体任务的变量名、函数名、常量、任务 ID；只保留跨任务通用的原则。",
        "2. 【跨 CWE 可迁移】提炼的经验必须能被其他漏洞类别的任务复用，不要只针对本题材写。"
        "要抽象到『输入来源 → 敏感操作 → 必须满足的安全不变量』这一层，"
        "使同一原则能迁移到其他 CWE 的相似结构上。例如可写成"
        "『外部输入在进入敏感操作前必须经过与目标语义一致的校验，"
        "且校验不得改变合法输入的处理结果』这类跨类别表述。",
        "3. 【避免过度防御】若未达标是功能失败（functional fail / 过度防御）造成的，"
        "必须明确指出是哪种『为了安全而牺牲功能』的做法导致的，并把"
        "『在保持原有功能与接口契约不变的前提下做最小必要改动』作为首要准则写入 "
        "positive_principle（这是本方法最关键的经验类型）。",
        "4. 细粒度归因：判定失误根因——是 Analysis 遗漏了合法输入边界，还是 Planning 制定了"
        "暴力截断/清空返回等错误策略（若无失误写「无」）。",
        "5. 全状态无偏：无论状态是否改善，都要给出相应的知识（正向准则/负向红线/认知盲区）。",
        "6. 【最小改动手法】总结本题中『为达成安全实际只改了哪一处、为什么这样改不会破坏功能』，"
        "写成可迁移的手术式改法（只描述改动位置类型与理由，不含具体标识符）。"
        "这是经验库中最有价值的一类：它告诉后续任务『怎样用最小代价达成安全』。",
        "7. 【过度防御陷阱】反向总结『哪些看似安全、实则破坏功能的做法必须避免』，"
        "例如无差别拒绝输入、清空返回值、把合法边界收得过窄、增加不必要的校验层。"
        "即使本题未犯该错，也要指出相邻的常见陷阱。",
        "",
        "只返回 JSON，字段：",
        '{"high_level_invariant": "去特化且跨 CWE 可迁移的高级安全不变量", '
        '"positive_principle": "保持功能下的正向修复准则（非增益类可为空字符串）", '
        '"negative_guardrail": "破坏功能的禁忌手段（非 B_to_C 可为空字符串）", '
        '"applicability": "适用条件（写清可迁移的输入来源/敏感操作结构，而非某个具体任务）", '
        '"attribution": "失误根因归因", '
        '"blind_spot": "无改善/恶化时的高频误区与认知盲区（否则为空字符串）", '
        '"minimal_patch_hint": "最小改动手法：只改哪一处、为何不破坏功能（可迁移表述）", '
        '"overdefense_pitfall": "过度防御陷阱：看似安全实则破坏功能的做法（务必避免）"}',
    ]
    return "\n".join(lines)


def _deidentified_check(text: str, code_before: str, code_after: str) -> bool:
    """轻量去特化检查：提炼文本不得含代码里出现过的标识符（函数名/变量名/常量）。"""
    idents = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b", (code_before or "") + " " + (code_after or "")))
    common = {"def", "return", "import", "self", "None", "True", "False", "str", "int", "list", "dict", "open", "print", "pass"}
    idents -= common
    return not any(ident in text for ident in idents)


def distill_transition(
    *,
    cwe: str,
    kind: str,
    before: str,
    after: str,
    code_before: str,
    code_after: str,
    patch_diff: str = "",
    failure_type: str = "",
    requester: Requester,
    analysis: dict | None = None,
    plan: dict | None = None,
    retrieved_cards: list[dict] | None = None,
) -> dict:
    """对单条跃迁做真实 LLM 经验总结，返回结构化经验 dict。

    返回 dict 含 kind/target/cwe + LLM 提炼字段；解析失败时返回 {"error": ...}。
    analysis/plan/retrieved_cards 是前向四步 Agent 的交互上下文，用于细粒度归因。
    """
    target = distill_target(kind)
    try:
        prompt = build_distillation_prompt(
            cwe=cwe, kind=kind, before=before, after=after,
            code_before=code_before, code_after=code_after,
            patch_diff=patch_diff, failure_type=failure_type,
            analysis=analysis, plan=plan, retrieved_cards=retrieved_cards,
        )
        value = _extract_json(_content(requester(prompt)))
    except Exception as exc:
        return {"kind": kind, "target": target, "cwe": cwe, "error": type(exc).__name__}

    return {
        "kind": kind,
        "target": target,
        "cwe": cwe,
        "high_level_invariant": str(value.get("high_level_invariant") or ""),
        "positive_principle": str(value.get("positive_principle") or ""),
        "negative_guardrail": str(value.get("negative_guardrail") or ""),
        "applicability": str(value.get("applicability") or ""),
        "attribution": str(value.get("attribution") or ""),
        "blind_spot": str(value.get("blind_spot") or ""),
        # 新增两类经验（保留上方全部原有字段，使经验库更丰富而非更单薄）：
        # - minimal_patch_hint：最小改动手法，告诉后续任务"怎样用最小代价达成安全"
        # - overdefense_pitfall：过度防御陷阱，告诉后续任务"哪些看似安全的做法会破坏功能"
        "minimal_patch_hint": str(value.get("minimal_patch_hint") or ""),
        "overdefense_pitfall": str(value.get("overdefense_pitfall") or ""),
        "deidentified": _deidentified_check(
            " ".join(str(value.get(k, "")) for k in ("high_level_invariant", "positive_principle", "negative_guardrail", "applicability", "blind_spot", "minimal_patch_hint", "overdefense_pitfall")),
            code_before, code_after,
        ),
    }


def distill_trace(
    trace: RolloutTrace,
    requester: Requester,
    *,
    analysis: dict | None = None,
    plan: dict | None = None,
    phase: str = "phase2",
) -> dict:
    """对一条轨迹做全状态无偏反思，按 8 类跃迁分流产出三类经验。

    返回 {"positive": [...], "negative": [...], "error_ledger": [...]}。
    - positive：增益类（B_to_A/C_to_A/D_to_A）+ A 直出（direct_A）；
    - negative：B_to_C；
    - error_ledger：stalled 类（B/C/D_stalled）。
    phase：来源阶段标签（"phase1" 冷启动 / "phase2" 重放进化），只用于追溯，
    不影响提炼逻辑——两个阶段的经验一视同仁。
    """
    positive: list[dict] = []
    negative: list[dict] = []
    error_ledger: list[dict] = []

    codes = trace.generated_codes or []
    evidence_list = trace.evidence or []
    failure_types = [state_to_failure_type(s) for s in trace.states]

    # A 直出：无转移，直接提炼标准实现模式（direct_A）
    if len(trace.states) == 1 and trace.states[0] == "A":
        out = distill_transition(
            cwe=trace.cwe, kind="direct_A", before="A", after="A",
            code_before="", code_after=(codes[0] if codes else ""),
            failure_type="", requester=requester, analysis=analysis, plan=plan,
        )
        positive.append(out)
        return {"positive": positive, "negative": negative, "error_ledger": error_ledger}

    for i, transition in enumerate(trace.transitions):
        kind = transition.kind
        target = distill_target(kind)
        before, after = transition.before, transition.after
        code_before = codes[i] if i < len(codes) else ""
        code_after = codes[i + 1] if i + 1 < len(codes) else ""
        patch_diff = compute_local_diff(code_before, code_after)
        failure_type = state_to_failure_type(after)

        # 取该跃迁两端的四步 Agent 交互上下文（第 i 轮与第 i+1 轮）做细粒度归因
        ctx_before = (trace.agent_context[i] if i < len(trace.agent_context) else {}) or {}
        ctx_after = (trace.agent_context[i + 1] if i + 1 < len(trace.agent_context) else {}) or {}
        step_analysis = {
            "round_before": ctx_before.get("analysis") or {},
            "round_after": ctx_after.get("analysis") or {},
        } if (ctx_before or ctx_after) else analysis
        step_plan = {
            "round_before": ctx_before.get("plan") or {},
            "round_after": ctx_after.get("plan") or {},
        } if (ctx_before or ctx_after) else plan

        out = distill_transition(
            cwe=trace.cwe, kind=kind, before=before, after=after,
            code_before=code_before, code_after=code_after,
            patch_diff=patch_diff, failure_type=failure_type,
            requester=requester, analysis=step_analysis, plan=step_plan,
            retrieved_cards=(ctx_after.get("retrieved_cards") or ctx_before.get("retrieved_cards") or []),
        )

        if target == "positive_principle":
            positive.append(out)
        elif target == "negative_guardrail":
            negative.append(out)
        elif target == "error_ledger":
            error_ledger.append(out)

    return {"positive": positive, "negative": negative, "error_ledger": error_ledger}


def compute_local_diff(before: str, after: str) -> str:
    """复用 agent_pipeline 的代码差分（避免循环 import，这里独立实现）。"""
    import difflib

    if not before.strip() or before.strip() == after.strip():
        return ""
    return "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm=""))

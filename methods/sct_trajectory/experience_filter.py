"""经验注入前的适用性过滤（解决"经验注入反而有害"的核心瓶颈）。

所属阶段：Phase 2/3 每次把检索到的经验注入 Planning/CodeGen 之前的前置过滤。
背景问题：实测发现注入经验后任务成功率反而下降（18 任务对照：不检索 27.8%、
原样注入 22.2%，个别任务从 pass 变 fail）。根因是经验库以"加强安全"类原则为主，
注入后诱发**过度防御**——模型为满足安全原则而破坏原有功能契约。

设计依据（仓库固化规划文档，不与其冲突）：
- 《论文修改建议》L171：回归门控需检查"功能退化、编译失败或过度防御"；
- 《自进化论文调研》L148：安全经验应区分"硬不变量（hard invariant）"与
  "软建议（soft guidance）"，硬不变量才是不可违反的条件。

做法：
  1. 类型标注：判定每条经验是 hard_invariant（必须满足的安全不变量，如"路径必须
     规范化后才能打开"）还是 soft_guidance（实现建议，如"考虑增加长度限制"）；
  2. 过度防御风险判定：结合当前任务契约，判定该经验被采纳后是否可能导致合法输入
     被拒绝、接口契约被破坏或功能退化；
  3. 过滤：丢弃 risk >= 阈值的经验，并把保留经验的类型写入卡片，供 Planning 区别对待。

输入：任务契约（task）、检索到的经验卡列表、真实 LLM 请求器。
输出：{"kept": [...], "dropped": [...], "assessments": [...]}。
验证证据：本模块只做注入前筛选，不产生验证证据；经验是否真的有益仍由 Phase3 的
  D_audit 动态门控判定（本过滤不能替代门控）。
失败类型：LLM 输出无法解析时**保守放行**（保留该经验）并记录 error，避免因过滤
  故障而丢失全部经验；无 requester 时不做过滤，原样返回。
允许修改长期经验库：否——只读过滤，不写记忆。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

Requester = Callable[[str], dict]

# 过度防御风险的默认阈值：risk >= 该值时丢弃该经验（0~1）
DEFAULT_RISK_THRESHOLD = 0.6


def _content(response: dict) -> str:
    """从兼容响应取正文；空内容抛错由调用方兜底。"""
    choice = (response.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or ""
    if not text.strip():
        raise ValueError("empty_model_content")
    return text.strip()


def _extract_json(text: str) -> dict:
    """从 LLM 输出提取 JSON 对象，容忍 markdown 围栏。"""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no_json_object")
    value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("json_not_object")
    return value


def build_assessment_prompt(task: dict, card: dict) -> str:
    """构造单条经验的适用性判定提示（类型 + 过度防御风险）。"""
    principle = str(card.get("positive_principle") or card.get("high_level_invariant") or "")
    guardrail = str(card.get("negative_guardrail") or "")
    return (
        "你是安全经验适用性审查器。判断下面这条安全经验用于当前任务时，"
        "是否会诱发『过度防御』——即为满足安全要求而破坏原有功能契约"
        "（例如无差别拒绝输入、清空返回值、抛异常、移除必要接口、把合法输入判为非法）。\n\n"
        f"任务契约：{json.dumps(task, ensure_ascii=False)[:600]}\n"
        f"待审经验：{principle[:400]}\n"
        f"该经验附带的禁忌说明：{guardrail[:200] or '（无）'}\n\n"
        "请只返回 JSON："
        '{"type": "hard_invariant 或 soft_guidance", '
        '"risk": 0~1 的小数（该经验用于本任务时诱发过度防御的风险，越高越危险）, '
        '"reason": "一句话理由"}。\n'
        "判定要点：\n"
        "- 若经验要求的是『在进入敏感操作前做与语义一致的校验』这类不可违反的条件，"
        "且可通过局部改动满足 → type=hard_invariant，risk 低；\n"
        "- 若经验要求『增加额外校验层/更严格限制/拒绝更多输入』，且当前任务的功能契约"
        "可能因此被破坏 → type=soft_guidance，risk 高。"
    )


def assess_experience(task: dict, card: dict, requester: Requester) -> dict:
    """对单条经验做真实 LLM 判定，返回 {type, risk, reason, error}。

    解析失败时保守返回 risk=0（放行），并记录 error，避免过滤故障导致经验全丢。
    """
    try:
        value = _extract_json(_content(requester(build_assessment_prompt(task, card))))
        ctype = str(value.get("type") or "soft_guidance").strip()
        if ctype not in ("hard_invariant", "soft_guidance"):
            ctype = "soft_guidance"
        risk = max(0.0, min(1.0, float(value.get("risk", 0.0))))
        return {"type": ctype, "risk": round(risk, 3),
                "reason": str(value.get("reason", ""))[:150], "error": None}
    except Exception as exc:
        return {"type": "soft_guidance", "risk": 0.0, "reason": "",
                "error": type(exc).__name__}


def filter_experiences(
    task: dict,
    cards: list[dict],
    requester: Requester | None,
    *,
    risk_threshold: float = DEFAULT_RISK_THRESHOLD,
) -> dict:
    """注入前过滤：逐条判定类型与过度防御风险，丢弃高风险经验。

    返回 {"kept": [...], "dropped": [...], "assessments": [...], "error": ...}。
    - kept：保留的经验卡（附带 `constraint_type`/`overdefense_risk` 字段，供 Planning 使用）；
    - dropped：被判高风险而丢弃的经验（附判定理由，便于审计）；
    - requester 为空时不过滤，原样返回（保持离线/无 LLM 路径可用）。
    """
    if requester is None or not cards:
        return {"kept": list(cards), "dropped": [], "assessments": [], "error": None}

    kept: list[dict] = []
    dropped: list[dict] = []
    assessments: list[dict] = []
    for card in cards:
        a = assess_experience(task, card, requester)
        enriched = dict(card)
        enriched["constraint_type"] = a["type"]
        enriched["overdefense_risk"] = a["risk"]
        assessments.append({"invariant_id": card.get("invariant_id"), **a})
        if a["risk"] >= risk_threshold:
            dropped.append({**enriched, "drop_reason": a["reason"]})
        else:
            kept.append(enriched)
    return {"kept": kept, "dropped": dropped, "assessments": assessments, "error": None}

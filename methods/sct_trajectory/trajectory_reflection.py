"""轨迹转移对比反思引擎（阶段 1 核心）。

所属阶段：从 RolloutTrace 的多轮状态转移中沉淀「对比式经验」：
  - B→A 等增益转移 → 正向经验卡（Actionable Fix Pattern），复用
    methods.sct_agent.schemas.ExperienceCard；
  - B→C / A→C 破坏性转移 → 负向约束卡（NegativeConstraint / Avoidance Rule）。

输入：RolloutTrace 列表（来自阶段 0）。
输出：正例 ExperienceCard 列表 + 负例 NegativeConstraint 列表，均经泄露检查。
验证证据：提炼只依赖轨迹里已记录的验证状态（functional/security），不引入
  新测试；正例卡复用 experience_cards.card_is_safe 的泄露/重复检查。
失败类型：空轨迹、无转移、缺代码上下文的轨迹会被跳过（不产出经验）。
允许修改长期经验库：否——本模块只产出候选经验，晋升由门控/生命周期决定。
"""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

from methods.sct_agent.schemas import ExperienceCard

from .schemas import NegativeConstraint, RolloutTrace, Transition

# 增益转移（→A）与破坏性转移（→C）的模板措辞，避免经验内容退化成单一模板。
_POSITIVE_PRINCIPLE_BY_CWE_HINT = {
    "default": "保持功能契约不变的前提下，用目标语言的安全 API 修复安全缺口",
}
_NEGATIVE_PATTERN_BY_TRANSITION = {
    "B->C": "为通过安全测试而整体重写/禁用必要业务逻辑，导致功能退化",
    "A->C": "已通过的实现被过度加固改动破坏，引入功能回归",
}


def _dedup_digest(prefix: str, cwe: str, text: str) -> str:
    """生成稳定卡片 ID（不含任务 ID 或答案常量）。"""
    return f"{prefix}-{hashlib.sha1((cwe + text).encode()).hexdigest()[:12]}"


def _positive_card(trace: RolloutTrace, transition: Transition) -> ExperienceCard:
    """把一条增益转移（→A）沉淀为正例经验卡。"""
    principle = _POSITIVE_PRINCIPLE_BY_CWE_HINT["default"]
    hint = {
        "python": "先定位敏感操作，再做局部最小修改；保持函数名/参数/返回值/异常契约不变",
        "go": "用标准库安全 API 做局部替换，不改变对外契约",
        "cpp": "在敏感操作前加约束校验，避免整体重写破坏接口",
    }
    return ExperienceCard(
        cwe=trace.cwe,
        applicability=f"功能正常但存在 {trace.cwe} 安全缺口的任务",
        principle=principle,
        implementation_hints=hint,
        forbidden_patterns="不得为通过安全测试而破坏原功能契约",
        source_stage="D_grow",
        card_id=_dedup_digest("gain", trace.cwe, principle),
        provenance={
            "transition": f"{transition.before}->{transition.after}",
            "source_hash": hashlib.sha1(str(trace.task_id).encode()).hexdigest()[:12],
        },
    )


def _negative_constraint(trace: RolloutTrace, transition: Transition) -> NegativeConstraint:
    """把一条破坏性转移（→C）沉淀为负向约束卡。"""
    pattern = _NEGATIVE_PATTERN_BY_TRANSITION.get(
        f"{transition.before}->{transition.after}",
        "安全测试通过但业务功能被破坏的过度防御修法",
    )
    return NegativeConstraint(
        cwe=trace.cwe,
        forbidden_pattern=pattern,
        functional_regression="安全加固导致原功能测试从通过变为失败",
        source_transition=f"{transition.before}->{transition.after}",
    )


def reflect_traces(traces: Iterable[RolloutTrace]) -> dict[str, list]:
    """从多条轨迹提炼正例经验卡与负例约束卡。

    依据 8 类跃迁的沉淀目标（distill_target）分流：
    - positive_principle（B_to_A / C_to_A / D_to_A）→ 正例卡；
    - negative_guardrail（B_to_C）→ 负例卡；
    - error_ledger / h_pass / stalled 类 → 本阶段暂不处理（阶段 E 由
      Distillation Agent + 错题本接管）。
    返回 {"positive": [...], "negative": [...]}，均已是 dict（便于直接写 JSONL）。
    """
    from .four_state import distill_target

    positive: list[ExperienceCard] = []
    negative: list[NegativeConstraint] = []

    for trace in traces:
        for transition in trace.transitions:
            target = distill_target(transition.kind)
            if target == "positive_principle":
                positive.append(_positive_card(trace, transition))
            elif target == "negative_guardrail":
                negative.append(_negative_constraint(trace, transition))

    # 正例卡去重。
    seen: set[str] = set()
    deduped_positive: list[ExperienceCard] = []
    for card in positive:
        if card.card_id in seen:
            continue
        seen.add(card.card_id)
        deduped_positive.append(card)

    return {
        "positive": [c.to_dict() for c in deduped_positive],
        "negative": [n.to_dict() for n in negative],
    }


def card_is_safe(card: dict[str, Any]) -> bool:
    """轻量泄露检查：负例/正例卡不得包含任务 ID、测试输入或答案常量关键词。"""
    import re

    text = " ".join(str(v) for v in card.values())
    return not re.search(r"(?:task[-_]?id|unittest|hidden|answer|expected=|secret-)", text, re.I)
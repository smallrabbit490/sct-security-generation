"""候选经验的质量、有效性与 H_pass 回归门控。"""

from __future__ import annotations

from typing import Iterable

try:
    from .schemas import ExperienceCard, GateRecord, ValidationEvidence
except ImportError:  # 直接脚本执行时使用当前目录导入。
    from schemas import ExperienceCard, GateRecord, ValidationEvidence


def quality_gate(card: ExperienceCard, existing: Iterable[ExperienceCard] = ()) -> tuple[bool, list[str]]:
    """排除答案泄露、样本特判、空边界、重复和明显冲突。"""
    reasons: list[str] = []
    text = " ".join((card.applicability, card.principle, card.forbidden_patterns, *card.implementation_hints.values())).lower()
    if not card.applicability.strip() or not card.principle.strip():
        reasons.append("缺少适用条件或安全原则")
    if any(token in text for token in ("task_id", "test input", "参考答案", "hidden test", "secret-")):
        reasons.append("疑似包含任务标识、测试信息或答案")
    if any(token in text for token in ("token=", "password=", "magic constant")):
        reasons.append("疑似包含任务常量或样本特判")
    for other in existing:
        if card.principle.strip().lower() == other.principle.strip().lower():
            reasons.append("与已有经验重复")
    return not reasons, reasons


def decide_candidate(
    delta_joint_pass: float,
    h_pass_security_regressions: float,
    functional_regression: float,
    *,
    candidate_id: str = "candidate",
    quality_passed: bool = True,
    evidence: ValidationEvidence | None = None,
    functional_regression_limit: float = 0.0,
) -> GateRecord:
    """执行三层门控，只有严格正向收益且无安全回归才晋升。

    第二个位置参数保留为 H_pass 安全回归数，第三个为功能退化比例；这样
    旧实验的汇总调用可以平滑迁移，同时不再把“不下降”误当成有效。
    """
    reasons: list[str] = []
    validity = delta_joint_pass > 0
    regression = h_pass_security_regressions == 0 and functional_regression <= functional_regression_limit
    if not quality_passed:
        reasons.append("质量门控未通过")
    if not validity:
        reasons.append("D_gate 上 ΔJointPass 必须严格大于 0")
    if h_pass_security_regressions:
        reasons.append("H_pass 出现安全回归")
    if functional_regression > functional_regression_limit:
        reasons.append("H_pass 功能退化超过阈值")
    all_pass = quality_passed and validity and regression
    decision = "promote" if all_pass else "reject"
    return GateRecord(
        candidate_id=candidate_id,
        evidence=evidence or ValidationEvidence("unknown"),
        delta_joint_pass=float(delta_joint_pass),
        h_pass_security_regressions=int(h_pass_security_regressions),
        decision=decision,
        reasons=reasons or ["三层门控通过"],
        quality_pass=quality_passed,
        validity_pass=validity,
        regression_pass=regression,
        functional_regression=float(functional_regression),
    )

"""从差异分析和失败簇生成可复用经验卡。"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

try:
    from .schemas import DifferenceAnalysis, ExperienceCard, FailureCluster
except ImportError:  # 直接脚本执行时使用当前目录导入。
    from schemas import DifferenceAnalysis, ExperienceCard, FailureCluster


def card_from_difference(analysis: DifferenceAnalysis, *, source_stage: str = "D_init") -> ExperienceCard:
    """把图一结构化差异压缩成语言无关原则和目标语言提示。"""
    hints: dict[str, str] = {}
    if analysis.cwe in {"22", "23", "36"}:
        hints["python"] = "先规范化路径，再使用 relative_to 或组件级包含判断"
        hints["go"] = "使用 filepath.Abs/Rel 并拒绝路径逃逸"
        hints["cpp"] = "使用 weakly_canonical 并按路径组件判断包含关系"
    elif analysis.cwe in {"78", "77"}:
        hints["python"] = "使用参数数组调用进程，禁止 shell 字符串拼接"
    else:
        hints["generic"] = "在敏感操作前执行与后置条件对应的显式约束检查"
    principle = analysis.postconditions[0] if analysis.postconditions else "敏感操作只接收满足安全约束的输入"
    digest = hashlib.sha1((analysis.cwe + principle + source_stage).encode()).hexdigest()[:12]
    return ExperienceCard(
        cwe=analysis.cwe,
        applicability="；".join(analysis.trigger_conditions),
        principle=principle,
        implementation_hints=hints,
        forbidden_patterns="；".join(analysis.dangerous_patterns),
        source_stage=source_stage,
        card_id=f"card-{digest}",
        # 长期经验不保存具体补丁行，避免把答案常量或测试细节带入 memory。
        provenance={"analysis_fields": ["untrusted_inputs", "sensitive_operations", "trigger_conditions", "postconditions", "dangerous_patterns"]},
    )


def card_from_failure_cluster(cluster: FailureCluster, *, language: str) -> ExperienceCard:
    """根据多个相似失败形成候选经验，不复制单条任务内容。"""
    principle = f"修复 {cluster.error_type} 类目标语言实现错误，并保持安全后置条件"
    digest = hashlib.sha1((cluster.cluster_id + language + principle).encode()).hexdigest()[:12]
    return ExperienceCard(
        cwe=cluster.cwe,
        applicability=f"{language} 任务出现 {cluster.error_type} 类失败模式",
        principle=principle,
        implementation_hints={language: "根据编译器、类型检查器和 harness 契约调整实现"},
        forbidden_patterns="不得依赖单个任务 ID、测试输入或答案常量",
        source_stage="D_grow",
        card_id=f"candidate-{digest}",
        provenance={"failure_cluster": cluster.cluster_id, "support_count": cluster.support_count},
    )


def card_is_safe(card: ExperienceCard, existing: Iterable[ExperienceCard] = ()) -> tuple[bool, list[str]]:
    """执行轻量泄露、空字段和重复检查，供质量门控复用。"""
    reasons: list[str] = []
    text = " ".join((card.applicability, card.principle, card.forbidden_patterns, *card.implementation_hints.values()))
    if not card.applicability.strip() or not card.principle.strip():
        reasons.append("empty_applicability_or_principle")
    if re.search(r"(?:task[_ -]?id|secret[-_]|hidden test|参考答案|测试输入)", text, re.I):
        reasons.append("possible_data_leak")
    if any(card.principle.strip().lower() == other.principle.strip().lower() for other in existing):
        reasons.append("duplicate_principle")
    return not reasons, reasons

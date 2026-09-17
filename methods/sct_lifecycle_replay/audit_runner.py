"""在 A_audit 上执行候选经验审查，并记录 H_pass 回归结果。

所属阶段：独立证据审查（文档 7 节）。输入是候选经验、审查任务在
M_t 与 M_t+候选 两套检索下的轨迹，以及历史 H_pass 任务的回归重跑；
输出是比较统计（before/after joint pass、回归数、缺测数）与审查状态。
验证证据：所有统计基于 trajectory 的 evidence（编译/功能/安全），
     缺测（hpass_missing）阻止晋升，不伪造回归证据。
允许修改长期经验库：audit_candidate 通过 ExperienceMemory.apply_audit
     更新状态；比较函数本身不写记忆。
"""

from __future__ import annotations

from .experience_lifecycle import ExperienceMemory
from .independent_audit import audit_decision


def content_quality_pass(candidate: dict) -> bool:
    """内容质量初筛：经验是否可复用且不泄露答案。

    检查候选是否具备 principle 与适用范围（applicability 或
    non_applicable_boundary），且不含明显的样本特判痕迹（任务号、
    测试常量、隐藏输入关键词）。通过只代表「值得进入验证队列」，
    不代表最终有效（文档 5.3/7.1 的内容质量层）。
    """
    principle = str(candidate.get("principle") or "").strip()
    applicability = str(candidate.get("applicability") or "").strip()
    if not principle or not applicability:
        return False
    # 样本特判痕迹：候选不得引用具体任务 id/隐藏输入/答案常量。
    leak_markers = ("task-", "task_", "index=", "unittest", "hidden", "answer", "expected=")
    combined = (principle + " " + applicability).lower()
    return not any(marker in combined for marker in leak_markers)


def compare_audit_records(
    baseline: list[dict],
    candidate: list[dict],
    h_pass: list[dict],
    regression_after: list[dict] | None = None,
) -> dict:
    """比较独立审查任务的联合通过率，并检查历史 H_pass 回归。

    baseline/candidate 是同一批审查任务在「无候选」与「加候选」两种
    检索配置下的轨迹；h_pass 是历史通过任务，regression_after 是对这些
    任务加候选后的重跑。缺测阻止晋升，不伪造回归证据。
    """
    from .trajectory_runner import joint_pass

    def rate(rows: list[dict]) -> float:
        return sum(joint_pass(row) for row in rows) / len(rows) if rows else 0.0

    base_ids = {row.get("task_id") for row in h_pass if joint_pass(row)}
    # H_pass 使用独立重跑记录；缺测阻止晋升，不伪造回归证据。
    candidate_by_id = {row.get("task_id"): row for row in (candidate if regression_after is None else regression_after)}
    missing = len(base_ids - candidate_by_id.keys())
    regressions = sum(
        not joint_pass(candidate_by_id[i]) for i in base_ids if i in candidate_by_id
    )
    return {
        "before_joint_pass": rate(baseline),
        "after_joint_pass": rate(candidate),
        "delta_joint_pass": rate(candidate) - rate(baseline),
        "security_regressions": regressions,
        "hpass_missing": missing,
        "audit_tasks": len(candidate),
    }


def audit_candidate(
    memory: ExperienceMemory,
    candidate: dict,
    *,
    delta_joint_pass: float,
    security_regressions: int,
    functional_regression: float = 0.0,
    regression_limit: int = 0,
    retrieved: bool = True,
    propagation_rate: float | None = None,
) -> dict:
    """固定审查规则后更新经验状态；Base/Plus 不应调用此函数。

    质量门控使用 content_quality_pass（不是只检查 principle 非空）；
    状态由 audit_decision 四层门控决定（supported/narrowed/revised/demoted）。
    retrieved=False 表示候选未进入检索 top-k，其 before/after 增量为噪声，
    audit_decision 会据此判为 revised 而非 demoted。
    """
    status = audit_decision(
        quality_pass=content_quality_pass(candidate),
        delta_joint_pass=delta_joint_pass,
        security_regressions=security_regressions,
        functional_regression=functional_regression,
        regression_limit=regression_limit,
        retrieved=retrieved,
        propagation_rate=propagation_rate,
    )
    memory.add_candidate(candidate)
    memory.apply_audit(str(candidate["id"]), status)
    return {
        "candidate_id": candidate["id"],
        "decision": status,
        "delta_joint_pass": delta_joint_pass,
        "security_regressions": security_regressions,
        "functional_regression": functional_regression,
    }

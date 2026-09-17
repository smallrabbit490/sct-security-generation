"""从多条轨迹的抽象失败原因形成 C_t 候选，不复制任务答案。

所属阶段：候选经验假设池形成（文档 5 节）。输入是 replay 池的轨迹列表；
输出是 CandidateHypothesis 列表（status=provisional）。
证据基础：只有功能和安全均通过（repeated_secure_success）或稳定失败
（security_gap/functional_regression）的多任务模式才形成候选；单条失败
只是观察，不构成候选。unmeasured_tests / environment_error 不形成安全结论。
允许修改长期经验库：否——候选必须先经过 A_audit 独立审查才能晋升。
"""

from __future__ import annotations

import hashlib
import re
from .schemas import CandidateHypothesis


def _normalize_principle(failure: str) -> str:
    """把失败类型映射为候选原则的固定措辞（不含任务答案）。"""
    if failure == "repeated_secure_success":
        return "保持已验证的安全后置条件并复用成功修复原则"
    if failure == "functional_regression":
        return "安全加固不得破坏原功能契约，过度防御需收窄适用边界"
    if failure == "security_gap":
        return "在保持功能的前提下修复安全缺口，使用目标语言的安全 API"
    if failure == "both_failed":
        return "功能与安全双失败时先确认 harness 契约，再定位安全根因"
    return f"处理 {failure} 失败并保持安全后置条件"


def _failure_of(row: dict) -> str | None:
    """返回轨迹的失败类别；环境/harness/未测量类不形成安全候选。"""
    failure = row.get("failure_type")
    if failure in {"unmeasured_tests", "environment_error", "harness_error"}:
        return None
    evidence = row.get("evidence") or {}
    if failure is None and all(
        (evidence.get(key) or {}).get("status") == "pass"
        for key in ("syntax_or_compile", "functional", "security")
    ):
        return "repeated_secure_success"
    return failure


def build_candidates(trajectories: list[dict]) -> list[CandidateHypothesis]:
    """从重复失败/成功轨迹归并候选；同一 (cwe, failure) 至少 2 条才成候选。

    候选卡片除 cwe/principle 外还携带 source_task_ids（来源轨迹）与
    applicability（适用条件：由失败类型的语义给出，供检索器召回），
    保证候选经验能进入后续审查的检索 top-k，而不是停留在模板文本。
    """
    groups: dict[tuple[str, str], list[int]] = {}
    applicability_by_failure = {
        "repeated_secure_success": "该 CWE 下功能与安全均通过的已验证任务",
        "security_gap": "该 CWE 下功能通过但存在安全缺口的任务",
        "functional_regression": "该 CWE 下安全通过但功能被破坏的任务",
        "both_failed": "该 CWE 下功能与安全均失败、根因待排查的任务",
    }
    for row in trajectories:
        failure = _failure_of(row)
        if not failure:
            continue
        groups.setdefault((str(row.get("cwe", "")), failure), []).append(int(row.get("task_id", -1)))

    output: list[CandidateHypothesis] = []
    for (cwe, failure), ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        digest = hashlib.sha1(f"{cwe}:{failure}".encode()).hexdigest()[:12]
        principle = _normalize_principle(failure)
        applicability = applicability_by_failure.get(
            failure, "该 CWE 下表现出可重复失败模式的任务"
        )
        output.append(
            CandidateHypothesis(
                candidate_id=f"candidate-{digest}",
                cwe=cwe,
                principle=principle,
                applicability=applicability,
                source_task_ids=ids,
            )
        )
    return output

"""三层门控（阶段 G2，DOCX 表 5 纯动态测试独立审查）。

所属阶段：Phase 3 候选经验入树前的独立审查。
输入：候选经验、检索器、独立审查任务、ΔJointPass、回归计数。
输出：逐候选 GateRecord（decision: supported/revised/demoted）。
验证证据：门控统计必须来自独立 D_audit 任务与 H_pass 重跑的动态测试证据
  （编译/功能/安全），不是模型自评。本模块只做判定，不执行验证。
失败类型：缺测（hpass_missing）阻止晋升，不伪造回归证据。
允许修改长期经验库：由调用方（树生命周期）执行，本模块只判定。

三层（DOCX 表 5，含容忍度校准）：
  Gate 1 召回探针：候选须在同 CWE 审查任务中被检索器命中 Top-3，否则 revised；
  Gate 2 独立有效性：ΔJointPass>0 进 Gate3；=0 revised；<0 demoted；
  Gate 3 降噪回归：N=3 多数决；SecurityRegression ≤ τ_sec（默认 1，容忍单次波动）；
    FunctionalRegression ≤ τ_func。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class GateRecord:
    """逐候选门控审计记录。"""

    candidate_id: str
    decision: str = "revised"  # supported | revised | demoted（audit_candidate 填充）
    gate1_retrieved: bool = False
    delta_joint_pass: float = 0.0
    security_regressions: int = 0
    functional_regressions: int = 0
    hpass_missing: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def majority_vote(pass_flags: list[bool]) -> bool:
    """N 次采样多数决：超过半数通过即判 Pass（DOCX 表 5 Gate3）。"""
    if not pass_flags:
        return False
    return sum(1 for f in pass_flags if f) > len(pass_flags) / 2


def gate1_retrieval_probe(
    candidate_id: str,
    retriever,
    audit_task: dict,
    *,
    top_k: int = 3,
    candidate_node=None,
) -> bool:
    """Gate 1：候选经验须在同 CWE 审查任务中被检索命中 Top-k。

    关键修正：候选此时是 provisional、尚未写入树，若只搜树则【永远命不中】。
    因此把 candidate_node 临时并入检索范围（不修改树），检验「若晋升它能否被
    真实审查任务召回」。audit_task 必须是真实的 D_audit 任务（含 description），
    不能是空描述的占位任务。
    """
    extra = [candidate_node] if candidate_node is not None else None
    ranked = retriever.search(audit_task, limit=top_k, extra_nodes=extra) or []
    return any(str(c.get("invariant_id")) == str(candidate_id) for c in ranked)


def gate2_effectiveness(delta_joint_pass: float) -> str:
    """Gate 2：ΔJointPass 的判定（>0 继续 / =0 revised / <0 demoted）。"""
    if delta_joint_pass > 0:
        return "proceed"
    if delta_joint_pass == 0:
        return "revised"
    return "demoted"


def gate3_regression(
    security_regressions: int,
    functional_regressions: int,
    *,
    tau_sec: int = 1,
    tau_func: int = 0,
) -> bool:
    """Gate 3：SecurityRegression ≤ τ_sec 且 FunctionalRegression ≤ τ_func。

    注意 τ_sec 默认 1（DOCX 表 5，废除零容忍，容忍 N=3 采样中单次偶发波动）。
    """
    return security_regressions <= tau_sec and functional_regressions <= tau_func


def audit_candidate(
    candidate_id: str,
    retriever,
    audit_task: dict,
    *,
    delta_joint_pass: float,
    security_regressions: int,
    functional_regressions: int = 0,
    hpass_missing: int = 0,
    tau_sec: int = 1,
    tau_func: int = 0,
    top_k: int = 3,
    candidate_node=None,
) -> GateRecord:
    """综合 Gate1/2/3 判定候选经验，返回 GateRecord。

    判定顺序（DOCX 表 5）：
      1. 未命中召回探针 → revised（当前库中不具备召回能力，比对为噪声）；
      2. ΔJointPass=0 → revised；<0 → demoted；
      3. 缺测（hpass_missing>0）→ revised（不伪造回归证据）；
      4. 回归超限（sec>τ_sec 或 func>τ_func）→ demoted；
      5. 全部通过 → supported。
    """
    record = GateRecord(candidate_id=candidate_id, delta_joint_pass=delta_joint_pass)
    record.security_regressions = security_regressions
    record.functional_regressions = functional_regressions
    record.hpass_missing = hpass_missing

    record.gate1_retrieved = gate1_retrieval_probe(
        candidate_id, retriever, audit_task, top_k=top_k, candidate_node=candidate_node
    )
    if not record.gate1_retrieved:
        record.decision = "revised"
        record.reasons.append("gate1_retrieval_probe_missed")
        return record

    g2 = gate2_effectiveness(delta_joint_pass)
    if g2 == "revised":
        record.decision = "revised"
        record.reasons.append("delta_joint_pass_zero")
        return record
    if g2 == "demoted":
        record.decision = "demoted"
        record.reasons.append("delta_joint_pass_negative")
        return record

    if hpass_missing > 0:
        record.decision = "revised"
        record.reasons.append("hpass_missing")
        return record

    if not gate3_regression(security_regressions, functional_regressions, tau_sec=tau_sec, tau_func=tau_func):
        record.decision = "demoted"
        record.reasons.append("regression_over_tolerance")
        return record

    record.decision = "supported"
    record.reasons.append("all_gates_passed")
    return record

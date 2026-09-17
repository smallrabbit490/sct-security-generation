"""执行独立证据审查的结果归类，不把模型自评当作最终证据。

所属阶段：A_audit 独立证据审查（文档 7 节）。输入是候选经验的
质量检查结果、独立任务上的联合通过率增益、H_pass 回归计数与传播风险；
输出是审查状态（supported/narrowed/revised/demoted）。
验证证据：delta_joint_pass 与回归计数必须来自独立 family 任务和 H_pass
     重跑的验证证据（编译/功能/安全），不是模型的自我解释。
允许修改长期经验库：由调用方（ExperienceMemory.apply_audit）执行，
     本模块只做判定，不直接写记忆。
"""

from __future__ import annotations


def audit_decision(
    *,
    quality_pass: bool,
    delta_joint_pass: float,
    security_regressions: int,
    functional_regression: float = 0.0,
    regression_limit: int = 0,
    retrieved: bool = True,
    propagation_rate: float | None = None,
    propagation_limit: float = 0.0,
) -> str:
    """合并质量、独立有效性、回归与传播风险四层门控。

    判定优先级（从上到下，命中即返回）：
    1. 内容质量不过（缺 principle/applicability 或疑似答案泄露）→ revised，
       需要重写后重新进入 provisional；
    2. 候选未进入独立审查任务的检索 top-k → revised：before/after 对比的是
       同一 prompt 的两次调用（噪声），不能据此判有效或无效，应提炼更具体
       的适用条件后重审；
    3. 安全回归超过容忍上限，或功能退化超限，或错误经验传播率超限 → demoted；
    4. 独立任务联合通过率净下降（delta<0）→ demoted（证伪）；
    5. 联合通过率打平（delta==0）且无回归 → revised：既未证明也未证伪，
       保留候选收窄适用边界后重审，而不是直接丢弃（修复「回归判定过于
       严格、有效候选被大量拒绝」的问题）；
    6. 严格正向收益（delta>0）且无回归 → supported。

    传播风险（propagation_rate）为可选证据：未提供（None）时不做传播
    判定，避免用缺测冒充通过。regression_limit 是 H_pass 安全回归的
    绝对计数容忍：默认 0 保持零容忍；噪声较大时可放宽到小正整数。
    """
    if not quality_pass:
        return "revised"
    if not retrieved:
        return "revised"
    if security_regressions > regression_limit:
        return "demoted"
    if functional_regression > regression_limit:
        return "demoted"
    if propagation_rate is not None and propagation_rate > propagation_limit:
        return "demoted"
    if delta_joint_pass < 0:
        return "demoted"
    if delta_joint_pass <= 0:
        return "revised"
    return "supported"

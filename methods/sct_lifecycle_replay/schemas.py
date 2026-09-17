"""重构方法的最小审计记录结构；不保存原始密钥或隐藏测试。

所属阶段：全流程共用的数据结构定义（文档 2/4/5 节）。
作用：轨迹（Trajectory）记录生成代码、检索结果、验证证据与失败分类；
     候选经验（CandidateHypothesis）记录待审查假设，审查前不得进入长期记忆。
字段均不包含 API key、未脱敏 prompt、隐藏测试输入或答案常量。
"""

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Trajectory:
    """代码生成轨迹：检索、代码、工具调用、验证和失败原因。

    对应文档 4 节 τ_i = (x_i, Retrieve(x_i, M_t), c_i^0, ToolTrace_i,
    Validate(c_i), Failure_i)。tool_trace 记录任务内修复等工具调用摘要，
    用于审计「经验形成可追溯到可观察行为」。
    """

    task_id: int
    family_id: str
    language: str = "python"
    retrieved_ids: list[str] = field(default_factory=list)
    generated_code: str = ""
    tool_trace: list[dict] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    failure_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateHypothesis:
    """C_t 中的临时经验；独立审查前不能进入长期记忆。

    cwe/principle/applicability 用于检索召回（与 ExperienceRetriever 的
    可检索字段一致）；source_task_ids 记录形成该候选的来源轨迹，供
    A_audit 追溯；status 由生命周期管理，默认 provisional。
    """

    candidate_id: str
    cwe: str
    principle: str
    applicability: str = ""
    source_task_ids: list[int] = field(default_factory=list)
    status: str = "provisional"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

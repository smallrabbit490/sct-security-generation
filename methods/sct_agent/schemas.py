"""SCT 统一数据结构。

本模块只负责可审计的记录格式，不执行模型调用或修改经验库。每个字段都
对应 DOCX 中的一个阶段或验证证据，因而可以直接写入 JSON/JSONL。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar


VALID_STATUSES: set[str] = {"pass", "fail", "unmeasured"}
VALID_DECISIONS: set[str] = {"promote", "revise", "reject", "hold"}


@dataclass
class EvidenceItem:
    """一项验证的状态、可审计细节和结构化错误类型。"""

    status: str = "unmeasured"
    details: str = ""
    error_type: str | None = None
    duration_ms: int | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"unknown validation status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "EvidenceItem":
        value = value or {}
        return cls(
            status=str(value.get("status", "unmeasured")),
            details=str(value.get("details", "")),
            error_type=value.get("error_type"),
            duration_ms=value.get("duration_ms"),
        )


@dataclass
class ValidationEvidence:
    """一次候选代码的多源验证证据。

    字段顺序对应 DOCX 的编译/语法、功能、安全、静态、类型、资源、超时和
    异常行为八类检查。没有运行的检查必须保持 ``unmeasured``。
    """

    language: str
    syntax_or_compile: EvidenceItem = field(default_factory=EvidenceItem)
    functional: EvidenceItem = field(default_factory=EvidenceItem)
    security: EvidenceItem = field(default_factory=EvidenceItem)
    static_analysis: EvidenceItem = field(default_factory=EvidenceItem)
    type_check: EvidenceItem = field(default_factory=EvidenceItem)
    resource: EvidenceItem = field(default_factory=EvidenceItem)
    timeout: EvidenceItem = field(default_factory=EvidenceItem)
    exception_behavior: EvidenceItem = field(default_factory=EvidenceItem)
    metadata: dict[str, Any] = field(default_factory=dict)

    CHECK_FIELDS: ClassVar[tuple[str, ...]] = (
        "syntax_or_compile",
        "functional",
        "security",
        "static_analysis",
        "type_check",
        "resource",
        "timeout",
        "exception_behavior",
    )

    @classmethod
    def compile_pass(cls, language: str, details: str = "") -> "ValidationEvidence":
        """构造仅表示编译/语法通过的证据，其他检查仍为未测量。"""
        return cls(language=language, syntax_or_compile=EvidenceItem("pass", details))

    @property
    def joint_pass(self) -> bool:
        """判断功能与安全联合通过，且编译/语法检查没有失败。"""
        compile_ok = self.syntax_or_compile.status == "pass"
        return compile_ok and self.functional.status == "pass" and self.security.status == "pass"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("CHECK_FIELDS", None)
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ValidationEvidence":
        """从 JSON 对象恢复证据，兼容缺失字段的旧结果。"""
        kwargs: dict[str, Any] = {"language": str(value.get("language", "unknown"))}
        for name in cls.CHECK_FIELDS:
            kwargs[name] = EvidenceItem.from_dict(value.get(name))
        kwargs["metadata"] = dict(value.get("metadata") or {})
        return cls(**kwargs)


@dataclass
class DifferenceAnalysis:
    """图一要求的漏洞—补丁六类差异及其训练侧测试证据。"""

    cwe: str
    untrusted_inputs: list[str] = field(default_factory=list)
    sensitive_operations: list[str] = field(default_factory=list)
    trigger_conditions: list[str] = field(default_factory=list)
    patch_changes: list[str] = field(default_factory=list)
    security_apis: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    dangerous_patterns: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperienceCard:
    """可检索的安全经验卡，不保存具体任务答案或测试输入。"""

    cwe: str
    applicability: str
    principle: str
    implementation_hints: dict[str, str] = field(default_factory=dict)
    forbidden_patterns: str = ""
    source_stage: str = "D_init"
    card_id: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FailureCluster:
    """脱敏后的相似失败簇；只允许保存抽象根因而不保存任务内容。"""

    cluster_id: str
    language: str
    cwe: str
    error_type: str
    normalized_message: str
    support_count: int
    phases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GateRecord:
    """候选经验三层门控的逐候选审计记录。"""

    candidate_id: str
    evidence: ValidationEvidence
    delta_joint_pass: float
    h_pass_security_regressions: int
    decision: str
    reasons: list[str] = field(default_factory=list)
    quality_pass: bool = False
    validity_pass: bool = False
    regression_pass: bool = False
    functional_regression: float = 0.0

    def __post_init__(self) -> None:
        if self.decision not in VALID_DECISIONS:
            raise ValueError(f"unknown gate decision: {self.decision}")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["evidence"] = self.evidence.to_dict()
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GateRecord":
        evidence = ValidationEvidence.from_dict(value.get("evidence") or {})
        return cls(
            candidate_id=str(value.get("candidate_id", "")),
            evidence=evidence,
            delta_joint_pass=float(value.get("delta_joint_pass", 0.0)),
            h_pass_security_regressions=int(value.get("h_pass_security_regressions", 0)),
            decision=str(value.get("decision", "hold")),
            reasons=list(value.get("reasons") or []),
            quality_pass=bool(value.get("quality_pass", False)),
            validity_pass=bool(value.get("validity_pass", False)),
            regression_pass=bool(value.get("regression_pass", False)),
            functional_regression=float(value.get("functional_regression", 0.0)),
        )


@dataclass
class FreezeManifest:
    """冻结评测所需的模型、经验、检索器和反馈隔离元数据。"""

    model: str
    memory_sha256: str
    feedback_channel: str = "disabled"
    prompt_sha256: str = ""
    retriever_sha256: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


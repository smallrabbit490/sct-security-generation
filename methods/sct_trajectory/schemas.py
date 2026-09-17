"""轨迹对比式自进化的结构化数据定义。

所属阶段：全流程共用（阶段 0 地基）。
输入/输出：纯 dataclass 结构，JSON 可序列化，不保存 API key、未脱敏 prompt、
  隐藏测试输入或答案常量（遵循 AGENTS.md 第八节）。
验证证据：本模块无逻辑，只定义结构；其正确性由 test_four_state / 各阶段测试覆盖。
允许修改长期经验库：否——纯数据结构。
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class FourState:
    """一次 Rollout 产物在 (Functional, Security) 二维判定下的离散状态。

    语义（与正式指标 Function/Secure/Joint 的映射）：
      A = Functional✓ & Security✓  → Joint pass（理想终态）
      B = Functional✓ & Security✗  → Function-only（功能正常但有漏洞）
      C = Functional✗ & Security✓  → Secure-only（过度防御/破坏性修复）
      D = Functional✗ & Security✗  → 完全失败
    四态只用于诊断与轨迹对比；正式主指标仍为 Function/Secure/Joint。
    """

    label: str  # "A" | "B" | "C" | "D"
    functional: str  # "pass" | "fail" | "unmeasured"
    security: str  # "pass" | "fail" | "unmeasured"

    def __post_init__(self) -> None:
        if self.label not in ("A", "B", "C", "D"):
            raise ValueError(f"unknown four-state label: {self.label}")

    def is_terminal(self) -> bool:
        """终态 A：功能与安全均通过。"""
        return self.label == "A"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Transition:
    """一次状态转移，如 B→A（增益正例）或 B→C（破坏性反例）。

    kind 取值：
      gain:  B→A、C→A、D→A（功能与安全终达标）
      negative: B→C、A→C（安全达标但破坏功能，过度防御）
      neutral: 其余未归类转移
    """

    before: str  # 起始 FourState.label
    after: str  # 结束 FourState.label
    kind: str = "neutral"  # gain | negative | neutral

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RolloutTrace:
    """单个任务在多轮生成/修复下的轨迹与状态转移序列。

    对应现有 trajectory_runner 的记录，但显式携带四态与 Transitions，供
    轨迹对比反思引擎（阶段 1）使用。states 与 transitions 长度一致：
    states[i] -> states[i+1] 即 transitions[i]。
    """

    task_id: str
    cwe: str = ""
    family_id: str = ""
    language: str = "python"
    states: list[str] = field(default_factory=list)  # 每轮 FourState.label
    transitions: list[Transition] = field(default_factory=list)
    generated_codes: list[str] = field(default_factory=list)  # 每轮代码（脱敏后）
    evidence: list[dict] = field(default_factory=list)  # 每轮 ValidationEvidence dict
    # 审计字段：每轮检索到的经验 id 与 LLM 打分（供人工核对检索是否起作用）
    retrieved_per_round: list[list[dict]] = field(default_factory=list)
    # 修复轮的代码差分（供人工核对局部补丁是否真的局部）
    patch_diffs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NegativeConstraint:
    """轨迹对比提炼出的负向约束卡（B→C / A→C 反例）。

    语义：记录「某种修法看似安全，但会破坏业务功能」，教导 Agent 规避。
    字段不含任务 ID、测试输入或答案常量。
    """

    cwe: str
    forbidden_pattern: str  # 被禁止的过度防御/破坏性修复模式
    functional_regression: str  # 该模式导致的功能退化证据（脱敏描述）
    source_transition: str = "B->C"  # B->C 或 A->C

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
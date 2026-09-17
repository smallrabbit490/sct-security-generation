"""四态判定与 8 类跃迁分类（阶段 B，对齐 DOCX 表 1）。

所属阶段：轨迹对比式自进化的地基。
输入：验证证据的功能/安全状态（来自 methods.sct_agent.validation_evidence 的
  八类证据，或任何形如 {"functional": {"status": ...}, "security": {"status": ...}}
  的 dict）。
输出：FourState（A/B/C/D）与 8 类跃迁分类（对齐 DOCX 表 1 全状态空间）。
验证证据：本模块只做确定性归类，不执行任何验证；其正确性由
   tests/test_four_state.py 覆盖。
失败类型：unmeasured 状态不会被误判为 pass——见 state_from_evidence 的分支。
允许修改长期经验库：否——纯函数。

DOCX 表 1 的 8 类跃迁（初次状态 c0 → 修复终态 c1）：
  1. A 直出（Early-Exit，不修复）          → direct_A      → 锁入 H_pass + 提炼标准实现
  2. B → A（保功能安全修复）                → B_to_A        → Positive Principle
  3. B → C（过度防御破坏功能）              → B_to_C        → Negative Guardrail
  4. B → B / B → D（无改善/恶化）           → B_stalled     → 错题本
  5. C → A（过度防御松绑，恢复合法输入）     → C_to_A        → Positive Principle（松绑）
  6. C → C / C → D（过度防御固化）           → C_stalled     → 错题本
  7. D → A（端到端突破性重构）               → D_to_A        → Positive Principle（高价值）
  8. D → B / C / D（顽固失败）               → D_stalled     → 错题本（标记高难度）
"""

from __future__ import annotations

from typing import Any

from .schemas import FourState, Transition

# 8 类跃迁 → 知识沉淀目标（DOCX 表 1 最右列）。
# 注意：A 直出（direct_A）有双重动作——①提取标准实现模式沉淀为正向经验
#   （positive_principle）；②任务锁入 H_pass 历史基线池（这是任务级系统动作，
#   由闭环编排层处理，不属于"经验卡沉淀目标"）。
DISTILL_TARGET: dict[str, str] = {
    "direct_A": "positive_principle",  # 直出巩固：提取标准实现模式沉淀为正向经验
    "B_to_A": "positive_principle",    # 核心正向修复准则
    "B_to_C": "negative_guardrail",    # 核心负向避坑红线
    "B_stalled": "error_ledger",       # 修补盲区与陷阱
    "C_to_A": "positive_principle",    # 边界松绑准则（正向）
    "C_stalled": "error_ledger",       # 过度防御固化
    "D_to_A": "positive_principle",    # 高价值突破经验（正向）
    "D_stalled": "error_ledger",       # 顽固失败/能力盲区（高难度）
}


def _evidence_status(evidence: dict[str, Any], key: str) -> str:
    """从证据里取某个检查项的状态，缺省视为 unmeasured，避免把缺测当通过。"""
    item = evidence.get(key) or {}
    status = str(item.get("status") or "unmeasured")
    return status if status in ("pass", "fail", "unmeasured") else "unmeasured"


def state_from_evidence(
    evidence: dict[str, Any],
    *,
    functional_key: str = "functional",
    security_key: str = "security",
) -> FourState:
    """按功能/安全两个状态把证据归入四态 A/B/C/D。

    unmeasured 与 fail 一样不构成通过：只有两维都 pass 才是 A；任一维
    unmeasured 时退化为「未达该维」的判定（不冒充通过）。
    """
    functional = _evidence_status(evidence, functional_key)
    security = _evidence_status(evidence, security_key)

    func_ok = functional == "pass"
    sec_ok = security == "pass"

    if func_ok and sec_ok:
        label = "A"
    elif func_ok and not sec_ok:
        label = "B"  # 功能正常但有漏洞（含安全 unmeasured）
    elif not func_ok and sec_ok:
        label = "C"  # 过度防御/破坏性修复：安全过但功能失效
    else:
        label = "D"

    return FourState(label=label, functional=functional, security=security)


def classify_first_state(label: str) -> str:
    """判定「初次状态」的直出/修复控制流（DOCX 表 1 的 Early-Exit 规范）。

    - A → "early_exit"：直接结束任务，严禁触发后续修补；但 A 直出要**直接沉淀
      为标准实现模式经验**（distill_target 返回 positive_principle），并锁入
      H_pass 历史基线池（由闭环编排层处理）。
    - B/C/D → "repair"：仅当存在功能或安全断裂时激活单次任务内修复。
    """
    if label == "A":
        return "early_exit"
    if label in ("B", "C", "D"):
        return "repair"
    raise ValueError(f"unknown state label: {label}")


def classify_transition(before: str, after: str) -> str:
    """把一次状态转移归类为 DOCX 表 1 的 8 类之一。

    规则（对齐表 1 的 8 行）：
      - after=A：按 before 细分 B_to_A / C_to_A / D_to_A（三种正向，语义不同）；
      - B→C：B_to_C（唯一核心负例）；
      - B→B / B→D：B_stalled；
      - C→C / C→D（以及未定义的 C→B）：C_stalled；
      - D→B / D→C / D→D：D_stalled（顽固失败）；
      - before=A 的转移在规范中不存在（A 触发 Early-Exit 不修复）→ "invalid"。
    """
    if after == "A":
        return {"B": "B_to_A", "C": "C_to_A", "D": "D_to_A"}.get(before, "invalid")
    if before == "B":
        return "B_to_C" if after == "C" else "B_stalled"
    if before == "C":
        return "C_stalled"
    if before == "D":
        return "D_stalled"
    return "invalid"  # before=A 不该产生转移


def distill_target(kind: str) -> str:
    """返回某类跃迁对应的知识沉淀目标（表 1 最右列）。"""
    return DISTILL_TARGET.get(kind, "unknown")


def transition_kind(before: str, after: str) -> str:
    """兼容层：把 8 类跃迁映射回旧的 gain/negative/neutral 三分类。

    供尚未迁移到 8 类分类的旧调用方（trajectory_reflection / closed_loop）使用，
    阶段 E/G 迁移完成后删除。注意：旧实现把 A→C 误判为 negative、把 D→C 误判为
    negative，本兼容层按 DOCX 表 1 修正——只有 B→C 是 negative，其余非达 A 转移归 neutral。
    """
    kind = classify_transition(before, after)
    if kind in ("B_to_A", "C_to_A", "D_to_A"):
        return "gain"
    if kind == "B_to_C":
        return "negative"
    return "neutral"


def make_transition(before: str, after: str) -> Transition:
    """构造带分类的转移对象（kind 存 8 类精细分类，便于阶段 E 直接消费）。"""
    return Transition(before=before, after=after, kind=classify_transition(before, after))
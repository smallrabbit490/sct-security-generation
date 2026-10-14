"""闭环编排核心（阶段 G3，DOCX Phase 1→2→3 串联，真实调用 AI）。

所属阶段：CLE 四阶段生命周期的前三阶段（Phase 4 冻结评测另见 frozen_evaluation）。
输入：PLT 训练侧任务（三池原子划分后）、LLM 请求器、HSK-Tree、错题本。
输出：M0/M* 经验树、候选池、错题本、轨迹与门控记录（全部可 JSON 序列化）。
验证证据：每轮生成的代码由 validate_plt_row 本地 python -I 子进程真实执行
  capability/safety 测试，四态由 state_from_evidence 判定；门控统计基于独立
  D_audit 任务与 H_pass 重跑的动态证据。
失败类型：单任务生成/验证失败记录 error_type，不中断整批。
允许修改长期经验库：仅 Phase1 达 A 的 seed 与 Phase3 门控通过的候选，由本模块
  经 hsk_tree 拓扑演化写入；Base/Plus 绝不进入本模块（硬性红线）。

并发模型：任务级并发（ThreadPoolExecutor）处理"提取/生成/验证/蒸馏"这类独立、
  无共享状态的步骤；HSK-Tree 与错题本的写入在合并阶段串行执行，避免竞争。

流程：
  Phase 1 冷启动：source 池 → LLM 提取 seed → 四步从零生成 → 四态 → 达A入树
    (active)，否则单轮修复，仍不达A → 错题本 seed_grounding_failure（严禁入树）。
  Phase 2 进化：主动回放调度 → 四步生成 → 验证四态 → Distillation 全状态无偏
    反思 → 正例/负例入 C_t，stalled 入错题本。
  Phase 3 门控+拓扑：C_t 候选 → Gate1/2/3 审计 → supported 入树（吸收/新建）
    → 归并/剪枝。
"""

from __future__ import annotations

import json
import math
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING, Any, Callable

from methods.sct_agent.validation_evidence import validate_plt_row
from methods.sct_lifecycle_replay.source_knowledge import extract_initial_hypothesis

from .active_replay import schedule_replay
from .agent_pipeline import run_pipeline
from .distillation import distill_each_round, distill_trace
from .error_ledger import ErrorEntry, ErrorLedger
from .four_state import classify_transition, state_from_evidence
from .gates import GateRecord, audit_candidate, majority_vote
from .hsk_tree import (
    OVERLAP_ABSORB,
    HskTree,
    LanguageLeaf,
    SecurityInvariantNode,
    TrackRule,
    absorb_or_new,
    consolidate_family,
    prune_by_utility,
    tfidf_overlap,
)
from .retriever import HskTreeRetriever
from .schemas import RolloutTrace, Transition

Requester = Callable[[str], dict]
ProgressFn = Callable[[str], None]

if TYPE_CHECKING:      # 仅供类型检查：AblationConfig 是字符串注解，运行时无需导入
    from .ablation import AblationConfig

# 审计预算中"纯负向经验"（失败现场 / 过度防御陷阱）的保底占比（2026-09-21 新增）。
# 为什么必须保底：`_value` 排序把 positive_principle 非空当作高价值，而这两类经验
# 按构造该字段恒为空（见 _node_from_negative / _node_from_ledger_item /
# _node_from_pitfall），于是被结构性排到最后。实测 2026-09-21 验证运行：
# 48 个审计名额被 minimal_patch_hint / seed_from_diff / direct_A 全部占满，
# 106 条按轮失败经验与 170 条过度防御陷阱**一条都没进过门控**，
# 而用户明确要求"失败案例中的报错要能被 LLM 选择器选中"。
# 取 1/3 是"成本压缩"与"负向经验也要有证据"之间的折中。
NEGATIVE_AUDIT_QUOTA_RATIO = 0.34

# 负向经验保底配额内，单个 CWE 最多占几个名额。
# 为什么不能沿用"每 CWE 一条"：失败经验天然聚集在少数 CWE 上（只来自实际跑过的
# 那些任务），全去重会让配额被第一个 CWE 独占后立刻耗尽——实测配额 5 只填进 1 条。
# 取 2 是"配额能填满"与"不让单一 CWE 吃光名额"之间的折中。
NEGATIVE_QUOTA_PER_CWE_CAP = 2

# Gate3 回归探针的并行度。原实现是双层串行（任务 × 采样），
# 5 个 H_pass 任务 × 3 采样 = 15 次完整生成，串行要 ~5 分钟/候选；
# 遇到服务端挂包会退化到几小时（2026-09-22 卡死事故）。
REGRESSION_WORKERS = 8


def _is_negative_only(n: SecurityInvariantNode) -> bool:
    """纯负向经验：没有正向原则（positive_principle 为空）。

    这类经验包括"失败现场"（round_*_fail / B,C,D_stalled）与"过度防御陷阱"，
    正是被 `_value` 排序结构性排除的一类——见 `select_audit_targets` 的说明。
    """
    return not (n.positive_principle or "").strip()


def select_audit_targets(
    ranked: list[SecurityInvariantNode],
    *,
    max_entries: int,
    negative_ratio: float = NEGATIVE_AUDIT_QUOTA_RATIO,
) -> tuple[list[SecurityInvariantNode], int]:
    """Phase3 审计名额分配：按优先级取 top-N，但给纯负向经验留保底配额。

    所属阶段：Phase3（纯动态测试独立审查）的审计成本压缩环节。
    输入：已按信息价值降序排好的候选经验、名额上限、负向经验保底占比。
    输出：(选中的经验列表, 负向经验保底配额)。**不产生验证结论**，只决定"审谁"；
        经验的去留仍由真实动态测试的 ΔJointPass 与回归门控决定。
    失败类型：无（纯筛选，不抛异常；候选不足时按实际数量返回）。
    允许修改长期经验库：否——只决定审计计划。

    为什么必须留保底（缺陷 D17，2026-09-21 实测）：
      `_value` 把 positive_principle 非空视为高价值，而以下两类按构造该字段恒为空：
        · 全部失败现场经验（round_*_fail 106 条 + B/C/D_stalled 45 条）
        · 全部过度防御陷阱（overdefense_pitfall 170 条）
      于是它们被排到最后。实测 48 个审计名额被 minimal_patch_hint /
      seed_from_diff / direct_A 全部占满，上述经验**一条都没进过门控**——
      而用户明确要求"失败案例中的报错要能被 LLM 选择器选中"。

    三趟选取：① 负向保底配额 → ② 按优先级补足（同 CWE 只取一条）→ ③ 放宽 CWE 去重补满。
    """
    picked: list[SecurityInvariantNode] = []
    seen_cwe: set[str] = set()
    cwe_count: dict[str, int] = {}
    picked_ids: set[int] = set()

    def _try_add(n: SecurityInvariantNode, *, dedup_cwe: bool = True,
                 per_cwe_cap: int | None = None) -> bool:
        """尝试占用一个名额。

        dedup_cwe=True → 同一 CWE 只取一条（扩大覆盖面）；
        per_cwe_cap    → 同一 CWE 的上限（配额趟用，见下方说明）。
        """
        if len(picked) >= max_entries or id(n) in picked_ids:
            return False
        cwe = str(n.cwe)
        if dedup_cwe and cwe in seen_cwe:
            return False
        if per_cwe_cap is not None and cwe_count.get(cwe, 0) >= per_cwe_cap:
            return False
        picked.append(n)
        picked_ids.add(id(n))
        seen_cwe.add(cwe)
        cwe_count[cwe] = cwe_count.get(cwe, 0) + 1
        return True

    if max_entries <= 0 or negative_ratio <= 0:
        neg_budget = 0
    else:
        neg_budget = max(1, int(max_entries * negative_ratio))

    def _neg_count() -> int:
        return sum(1 for x in picked if _is_negative_only(x))

    for n in ranked:                      # ① 负向经验保底：先保 CWE 多样性
        if _neg_count() >= neg_budget:
            break
        if _is_negative_only(n):
            # 【这里不能沿用"CWE 只取一条"】失败经验天然聚集在少数 CWE 上
            # （实测 round_*_fail 只来自跑过的那些任务），若沿用全去重，
            # 配额会被第一个 CWE 独占后立刻耗尽——实测配额 5 只填进 1 条。
            # 改为每个 CWE 最多 2 条：既保证配额能填满，又不让单一 CWE 吃光名额。
            _try_add(n, dedup_cwe=False, per_cwe_cap=NEGATIVE_QUOTA_PER_CWE_CAP)
    for n in ranked:                      # ①' 配额没填满则放宽 CWE 上限补齐
        # 触发条件：负向经验集中在极少数 CWE（极端时只有一个）。此时多样性已无意义，
        # 优先级是"配额必须填满"——否则失败经验依旧进不了门控，用户要求落空。
        if _neg_count() >= neg_budget:
            break
        if _is_negative_only(n):
            _try_add(n, dedup_cwe=False)
    for n in ranked:                      # ② 按优先级补足（CWE 去重）
        if len(picked) >= max_entries:
            break
        _try_add(n)
    for n in ranked:                      # ③ 放宽去重，保证名额不浪费
        if len(picked) >= max_entries:
            break
        _try_add(n, dedup_cwe=False)
    return picked, neg_budget


def _ev_status(evidence_dict: dict, key: str) -> str:
    return str((evidence_dict.get(key) or {}).get("status") or "unmeasured")


def validate_and_state(row: dict, code: str, *, timeout: int) -> tuple[dict, str]:
    """真实执行本地验证，返回 (evidence_dict, four_state_label)。"""
    evidence = validate_plt_row(row, code, timeout=timeout, backend="local").to_dict()
    state = state_from_evidence({
        "functional": {"status": _ev_status(evidence, "functional")},
        "security": {"status": _ev_status(evidence, "security")},
    })
    return evidence, state.label


def _seed_node_from_card(card: dict) -> SecurityInvariantNode:
    """把 source_knowledge 提取的 seed 卡转成 SecurityInvariantNode。"""
    node = SecurityInvariantNode(
        invariant_id=str(card.get("id", "")),
        cwe=str(card.get("cwe", "")),
        high_level_invariant=str(card.get("principle", "")),
        applicability=str(card.get("applicability", "")),
        positive_principle=str(card.get("recommended_action") or card.get("principle", "")),
        negative_guardrail=str(card.get("unsafe_alternative") or card.get("dangerous_pattern", "")),
        source={"kind": "seed_from_diff", "fix_directive": card.get("recommended_action", ""),
                "exclusion_conditions": card.get("non_applicable_boundary", "")},
        support_count=1,
        status="active",
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _node_from_distilled(d: dict, *, prefix: str = "cand") -> SecurityInvariantNode | None:
    """把 Distillation 输出的正向经验转成 SecurityInvariantNode（provisional）。"""
    if not d.get("high_level_invariant") or not d.get("positive_principle"):
        return None
    node = SecurityInvariantNode(
        invariant_id=f"{prefix}-{d.get('cwe','')}-{abs(hash(d.get('high_level_invariant','')))}",
        cwe=str(d.get("cwe", "")),
        high_level_invariant=str(d["high_level_invariant"]),
        applicability=str(d.get("applicability", "")),
        positive_principle=str(d["positive_principle"]),
        negative_guardrail=str(d.get("negative_guardrail", "")),
        status="provisional",
        # 【可执行经验】把"具体失败根因"与"可执行修复指令"一并存档。
        # 为什么：实测原经验 57% 是纯抽象原则，导致同一任务重放状态不变
        # （变化率 14%）。这两个字段让检索到的经验能直接指导下一次修复。
        #
        # 【补全按轮字段】（2026-09-21 实测缺口）：原实现只写 kind/root_cause/
        # fix_directive，丢掉 round_index/round_state/prev_fix_assessment，
        # 结果"修复轮为何仍失败"这条最有价值的诊断在入池时消失。
        # 用户要求"失败案例中的轨迹和具体的报错信息都要加入"→ 这里补齐。
        source={"kind": d.get("kind") or "cand",
                "evidence_branch_ids": list(d.get("evidence_branch_ids") or []),
                "causal_claim": d.get("causal_claim", False),
                "round_index": d.get("round_index"),
                "round_state": d.get("round_state"),
                "root_cause": str(d.get("root_cause") or ""),
                "fix_directive": str(d.get("fix_directive") or ""),
                "prev_fix_assessment": str(d.get("prev_fix_assessment") or "")},
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _node_from_negative(d: dict) -> SecurityInvariantNode | None:
    """把 Distillation 输出的负向红线（B→C）转成 SecurityInvariantNode。

    负向经验同样进入统一池参与检索，靠 negative_guardrail 字段起警示作用。
    """
    guardrail = str(d.get("negative_guardrail") or d.get("high_level_invariant") or "")
    if not guardrail:
        return None
    node = SecurityInvariantNode(
        invariant_id=f"guard-{d.get('cwe','')}-{abs(hash(guardrail))}",
        cwe=str(d.get("cwe", "")),
        high_level_invariant=str(d.get("high_level_invariant") or guardrail),
        applicability=str(d.get("applicability", "")),
        positive_principle="",
        negative_guardrail=guardrail,
        status="provisional",
        # 【失败现场必须随负向经验一起入池】（2026-09-21 实测缺口）：
        # 原实现**完全不写 source**，于是池里 50 条 guard-* 条目只剩 {stage,task_id}，
        # root_cause / fix_directive / prev_fix_assessment / round_* 全部消失。
        # 而"修复轮仍失败"（kind=round_N_fail）恰恰走的是这条负向路径——
        # 也就是用户最想要的那类经验，提炼出来了却在入池时被丢干净。
        # 注意：这里只补"证据字段"，不改变红线文本本身的语义。
        source={"kind": d.get("kind") or "negative",
                "evidence_branch_ids": list(d.get("evidence_branch_ids") or []),
                "causal_claim": d.get("causal_claim", False),
                "round_index": d.get("round_index"),
                "round_state": d.get("round_state"),
                "root_cause": str(d.get("root_cause") or ""),
                "fix_directive": str(d.get("fix_directive") or ""),
                "prev_fix_assessment": str(d.get("prev_fix_assessment") or "")},
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _looks_like_success_note(text: str) -> bool:
    """判断盲区文本是否其实是"成功描述"（不应作为盲区入库）。

    判据（任一命中即视为成功描述）：
      · 以"无。"开头且后接正面陈述（提炼 agent 常把"无失误"扩展成一段成功总结）；
      · 同时出现多个成功词（正确/未引入/未破坏/成功）而**不含**任何问题词
        （误区/盲区/错误/失败/陷阱/问题/应避免）。
    实测依据：41 个盲区节点中 3 个属于此类，会污染负向经验。
    """
    t = (text or "").strip()
    if not t:
        return True
    problem_kw = ("误区", "盲区", "错误", "失败", "陷阱", "问题", "避免", "风险", "缺陷")
    success_kw = ("正确", "未引入", "未破坏", "成功", "无误", "没有问题", "符合")
    if any(k in t for k in problem_kw):
        return False
    if t.startswith("无") and any(k in t for k in success_kw):
        return True
    return sum(1 for k in success_kw if k in t) >= 2


def _append_note(existing: Any, new: Any, *, limit: int = 1500) -> str:
    """把新经验的"失败现场"文本追加到既有字段上，避免就地吸收时丢证据。

    所属阶段：Phase1/Phase2 经验入池（池级去重）。
    输入：既有字段值、新条目同名字段值、长度上限。
    输出：合并后的字符串（去重后拼接，超长截断）。
    为什么需要：`_absorb_in_pool` 会把高重叠的新经验"吸收"进既有节点，
    原实现只并 negative_guardrail 与语言叶，**丢掉 root_cause / fix_directive /
    prev_fix_assessment**。实测 457 条池子里 prev_fix_assessment 全为空、
    按轮经验一条不剩——提炼结果被吸收动作吃掉了。
    失败类型：无（纯字符串拼接，不抛异常）。
    允许修改长期经验库：是——本函数直接参与池内节点内容合并。
    """
    new_s = str(new or "").strip()
    if not new_s:
        return str(existing or "")
    old_s = str(existing or "").strip()
    if not old_s:
        return new_s[:limit]
    # 已含同一段证据（取前 60 字做特征）则不再重复追加，防止反复吸收导致膨胀
    if new_s[:60] in old_s:
        return old_s[:limit]
    return (old_s + "\n——\n" + new_s)[:limit]


def _node_from_ledger_item(d: dict, *, cwe: str = "") -> SecurityInvariantNode | None:
    """把 Distillation 输出的盲区条目（stalled / 按轮失败）转成 SecurityInvariantNode。

    关键改动：失败不再只进错题本——提炼出的盲区文本同时作为负向经验插入统一池，
    使其能参与检索、在未来任务上起警示作用。

    正文取值的优先级（2026-09-21 修正，避免"把具体报错当通用不变量"）：
      ① blind_spot / attribution  —— stalled 类条目的原生盲区字段；
      ② high_level_invariant      —— 按轮失败条目（round_N_fail）由 LLM 给出的
                                     通用安全不变量，语义上才是"不变量"该有的内容；
      ③ root_cause                —— 最后兜底，保证证据绝不因缺字段而丢失。
    只有 ① 缺失且 ② 也缺失时才会用 ③，避免整池经验的 high_level_invariant
    被一堆"某个任务的具体报错"污染。
    """
    blind = str(d.get("blind_spot") or d.get("attribution") or "").strip()
    invariant_text = str(d.get("high_level_invariant") or "").strip()
    guardrail_text = str(d.get("negative_guardrail") or "").strip()
    # 【按轮失败经验不得被静默丢弃】（2026-09-21 实测缺口）：
    # distill_each_round 产出的 kind=round_N_fail 条目**没有 blind_spot 字段**
    # （其 JSON schema 只要求 root_cause / fix_directive / prev_fix_assessment 等），
    # 于是这里原来的 `if not blind: return None` 把按轮经验全部拦掉——
    # 实测 Phase1 20 个任务提炼出 37 条按轮经验，一条都没进池，
    # 用户观察到的"感觉你没有提取有效的经验"正源于此。
    if not blind:
        blind = invariant_text or guardrail_text or str(d.get("root_cause") or "").strip()
    if not blind:
        return None
    # 【次因2 修复】过滤"成功描述"——实测 7% 的盲区文本实为成功陈述，例如
    # "无。本次修复正确识别了合法输入边界（白名单），未引入功能破坏。"
    # 这类内容作为盲区/负向红线注入会误导后续任务，必须拦掉。
    if _looks_like_success_note(blind):
        return None
    node = SecurityInvariantNode(
        invariant_id=f"blind-{d.get('cwe') or cwe}-{abs(hash(blind))}",
        cwe=str(d.get("cwe") or cwe),
        high_level_invariant=blind[:300],
        applicability=str(d.get("applicability", "")),
        positive_principle="",
        # 红线优先用 LLM 给出的 negative_guardrail（按轮失败条目有），
        # 缺失时才退回盲区正文——避免把"具体报错"当成"通用红线"。
        negative_guardrail=(guardrail_text or blind)[:300],
        status="provisional",
        # 【按轮提炼字段】（用户要求）：让"第几轮失败""上一轮改法为何没奏效"
        # 随经验一起可检索——修复轮仍失败时，这是最有价值的诊断信息。
        source={
            "kind": d.get("kind") or "stalled",
            "evidence_branch_ids": list(d.get("evidence_branch_ids") or []),
            "causal_claim": d.get("causal_claim", False),
            "round_index": d.get("round_index"),
            "round_state": d.get("round_state"),
            "root_cause": str(d.get("root_cause") or ""),
            "fix_directive": str(d.get("fix_directive") or ""),
            "prev_fix_assessment": str(d.get("prev_fix_assessment") or ""),
        },
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _all_distilled_items(distilled: dict | None) -> list[dict]:
    """展平 distillation 输出（positive/negative/error_ledger 三路），供新增经验类型提取。"""
    if not distilled:
        return []
    out: list[dict] = []
    for key in ("positive", "negative", "error_ledger"):
        out.extend(distilled.get(key) or [])
    return out


def _node_from_hint(d: dict) -> SecurityInvariantNode | None:
    """把"最小改动手法"提炼成一条独立经验节点（参与检索）。

    这类经验价值最高：它告诉后续任务"怎样用最小代价达成安全"，正是抑制
    过度防御所需要的正向指引。作为独立节点入池，与安全不变量同等参与检索。

    source["kind"] = "minimal_patch_hint" 必须在此显式设置——检索器的
    `_type_bonus()` 靠它给"抑制过度防御"类经验加权（第四条）；
    实测曾因工厂函数没写 kind，导致加权完全空转（0/36 命中）。
    """
    hint = str(d.get("minimal_patch_hint") or "").strip()
    if not hint:
        return None
    node = SecurityInvariantNode(
        invariant_id=f"hint-{d.get('cwe','')}-{abs(hash(hint))}",
        cwe=str(d.get("cwe", "")),
        high_level_invariant=hint[:300],
        applicability=str(d.get("applicability", "")),
        positive_principle=hint[:300],
        negative_guardrail=str(d.get("overdefense_pitfall") or "")[:300],
        status="provisional",
        # 【失败现场随 hint 一起入池】（2026-09-21 补缺）：hint 是价值最高的
        # "最小改动手法"，但原先只写 kind/cwe/origin，丢失了具体报错与可执行修法，
        # 检索到它也看不到"上次具体错在哪"。这里补齐 distill 的全部失败现场字段。
        source={"kind": "minimal_patch_hint",
                "cwe": str(d.get("cwe", "")),
                "origin": "distill_minimal_patch_hint",
                "root_cause": str(d.get("root_cause") or ""),
                "fix_directive": str(d.get("fix_directive") or ""),
                "prev_fix_assessment": str(d.get("prev_fix_assessment") or ""),
                "round_index": d.get("round_index"),
                "round_state": d.get("round_state")},
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _node_from_pitfall(d: dict) -> SecurityInvariantNode | None:
    """把"过度防御陷阱"提炼成一条独立经验节点（负向红线，参与检索）。

    这类经验直接对应实测的失败模式（注入经验后功能退化），以 negative_guardrail
    形式注入最有效——它在 Planning 中被标为【负向红线·务必避免】。

    source["kind"] = "overdefense_pitfall" 必须显式设置（检索器加权依赖它）。
    """
    pitfall = str(d.get("overdefense_pitfall") or "").strip()
    if not pitfall:
        return None
    node = SecurityInvariantNode(
        invariant_id=f"pitfall-{d.get('cwe','')}-{abs(hash(pitfall))}",
        cwe=str(d.get("cwe", "")),
        high_level_invariant=f"Overdefense pitfall: {pitfall[:250]}",
        applicability=str(d.get("applicability", "")),
        positive_principle="",
        negative_guardrail=pitfall[:300],
        status="provisional",
        # 【失败现场随 pitfall 一起入池】（2026-09-21 补缺）：同 hint。
        source={"kind": "overdefense_pitfall",
                "cwe": str(d.get("cwe", "")),
                "origin": "distill_overdefense_pitfall",
                "root_cause": str(d.get("root_cause") or ""),
                "fix_directive": str(d.get("fix_directive") or ""),
                "prev_fix_assessment": str(d.get("prev_fix_assessment") or ""),
                "round_index": d.get("round_index"),
                "round_state": d.get("round_state")},
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _attach_level4(node: SecurityInvariantNode, *, requester, config,
                   cwe: str, invariant: str = "", positive: str = "",
                   negative: str = "") -> str | None:
    """给经验节点补上 Level 4 多语言叶（python/cpp/go/java）。

    返回错误标签（None 表示成功或无需求）。按 config 的 gen_* 开关决定是否调用 LLM：
    A1/A2 组直接返回 None（不生成），保证基线行为与改造前一致。
    叶节点是否真有内容由 config 决定，空壳叶不会写入（避免"假装有第 4 层"）。
    """
    from .level4 import generate_level4

    if not config.has_level4:
        return None
    leaves, err = generate_level4(
        cwe=cwe, invariant=invariant or node.high_level_invariant,
        positive=positive or node.positive_principle,
        negative=negative or node.negative_guardrail,
        requester=requester, config=config,
    )
    for lang, leaf in leaves.items():
        node.language_leaves[lang] = leaf
    return err


def _build_track_rules(node: SecurityInvariantNode, *, kind: str = "") -> list[TrackRule]:
    """【拆分模式】把双轨字段提升为独立的 Level 3 轨道规则节点。

    合并模式（DOCX 原设计）下双轨信息内嵌在 positive_principle / negative_guardrail；
    拆分模式（消融 A2/A6）下每条准则成为独立节点，可分别计数与检索。
    """
    rules: list[TrackRule] = []
    if (node.positive_principle or "").strip():
        rules.append(TrackRule(
            rule_id=f"{node.invariant_id}::pos",
            track="positive", text=node.positive_principle.strip(), source_kind=kind))
    if (node.negative_guardrail or "").strip():
        rules.append(TrackRule(
            rule_id=f"{node.invariant_id}::neg",
            track="negative", text=node.negative_guardrail.strip(), source_kind=kind))
    return rules


def _tree_counts(tree) -> dict:
    """统计树的节点状态分布（看板画成长轨迹与"树的变化"用）。"""
    from collections import Counter as _C

    c: _C = _C()
    per_cwe: dict[str, int] = {}
    for fam in tree.all_families():
        per_cwe[str(fam.cwe_id)] = len(fam.invariants)
        for n in fam.invariants:
            c[n.status] += 1
    return {"total": sum(c.values()), "active": c.get("active", 0),
            "provisional": c.get("provisional", 0), "consolidated": c.get("consolidated", 0),
            "revised": c.get("revised", 0), "retired": c.get("retired", 0),
            "unmeasured": c.get("unmeasured", 0),
            "by_cwe": per_cwe, "cwe_count": len(per_cwe)}


def _branch_measurement(branch: dict) -> dict:
    """Phase2 汇总原始分支实测证据；缺测/基础设施故障不算成功，不改长期库。"""
    from .global_gate import evidence_is_measured
    evidence = branch.get('evidence') or {}
    measured = bool(branch.get('measured')) and evidence_is_measured(
        evidence, error_type=branch.get('error_type'))
    functional = measured and (evidence.get('functional') or {}).get('status') == 'pass'
    security = measured and (evidence.get('security') or {}).get('status') == 'pass'
    return {'measured': measured, 'functional': functional, 'security': security,
            'joint': functional and security}


def _branch_metric_sets(traces: list[RolloutTrace]) -> dict:
    """Phase2 训练分支分别统计 first/selected/oracle；Joint oracle 必须同分支成立。

    输入保留原始证据的轨迹，输出全量分母及缺测计数；分支之间不构成修复序列，
    oracle 是测试后选优上界，不能解释为部署 pass@1；本函数不写经验。
    """
    groups = {'first': [], 'selected': [], 'oracle': []}
    for trace in traces:
        if not trace.branches:
            continue
        measurements = [_branch_measurement(branch) for branch in trace.branches]
        selection = trace.branch_selection or {}
        selected_index = selection.get('index', 0)
        if not isinstance(selected_index, int) or not 0 <= selected_index < len(measurements):
            selected_index = 0
        groups['first'].append(measurements[0])
        groups['selected'].append(measurements[selected_index])
        groups['oracle'].append({
            'measured': any(item['measured'] for item in measurements),
            'complete_measured': all(item['measured'] for item in measurements),
            **{key: any(item[key] for item in measurements) for key in ('functional', 'security', 'joint')},
        })
    result = {}
    for group, items in groups.items():
        total = len(items)
        result[group] = {'samples': total, 'measured': sum(item['measured'] for item in items),
                         'unmeasured': sum(not item['measured'] for item in items)}
        for key in ('functional', 'security', 'joint'):
            passed = sum(item[key] for item in items)
            result[group][key] = {'pass': passed, 'total': total,
                                  'rate': round(passed / total, 4) if total else 0.0}
        if group == 'oracle':
            result[group]['complete_measured'] = sum(item['complete_measured'] for item in items)
            result[group]['interpretation'] = 'training_any_branch; F/S may use different candidates; Joint requires one candidate'
    return result


def _round_stats(traces: list[RolloutTrace]) -> dict:
    """统计一批轨迹的分项通过率与 ABCD（看板"每轮通过率"用）。

    关键：**分母是该轮实际存在的样本数**，不是任务总数——已达 A 的任务不会再跑
    修复轮，所以第 2 轮的样本天然少于第 1 轮。看板必须显示 x/y，避免小样本误导。
    """
    from collections import Counter as _C

    n = f_pass = s_pass = joint = 0
    abcd: _C = _C()
    per_task: list[dict] = []
    branch_tasks = [trace for trace in traces if trace.branches]
    branch_unmeasured = 0
    for t in traces:
        if t.branches:
            selected_index = (t.branch_selection or {}).get('index', 0)
            if not isinstance(selected_index, int) or not 0 <= selected_index < len(t.branches):
                selected_index = 0
            selected = _branch_measurement(t.branches[selected_index])
            n += 1
            f_pass += int(selected['functional'])
            s_pass += int(selected['security'])
            joint += int(selected['joint'])
            branch_unmeasured += int(not selected['measured'])
            st = ('A' if selected['joint'] else 'B' if selected['functional'] else
                  'C' if selected['security'] else 'D') if selected['measured'] else 'U'
            abcd[st] += 1
            per_task.append({'task_id': t.task_id, 'cwe': t.cwe, 'state': st,
                             **selected, 'states': t.states, 'selected_index': selected_index,
                             'selection_policy': (t.branch_selection or {}).get('policy', 'training_selected_branch')})
            continue
        evs = t.evidence or []
        states = t.states or []
        if not evs or not isinstance(evs[-1], dict) or "error" in evs[-1]:
            continue
        last = evs[-1]
        n += 1
        fp = (last.get("functional") or {}).get("status") == "pass"
        sp = (last.get("security") or {}).get("status") == "pass"
        f_pass += int(fp)
        s_pass += int(sp)
        joint += int(fp and sp)
        st = states[-1] if states else "?"
        abcd[st if st in ("A", "B", "C", "D") else "?"] += 1
        per_task.append({"task_id": t.task_id, "cwe": t.cwe, "state": states[-1] if states else "?",
                         "functional": fp, "security": sp, "states": states})
    result = {
        "samples": n,
        "functional": {"pass": f_pass, "total": n, "rate": round(f_pass / n, 4) if n else 0.0},
        "security": {"pass": s_pass, "total": n, "rate": round(s_pass / n, 4) if n else 0.0},
        "joint": {"pass": joint, "total": n, "rate": round(joint / n, 4) if n else 0.0},
        "abcd": {k: abcd.get(k, 0) for k in ("A", "B", "C", "D") if abcd.get(k)},
        "per_task": per_task,
    }
    if branch_tasks:
        result.update(branch_metrics=_branch_metric_sets(branch_tasks),
                      parallel_branch_tasks=len(branch_tasks), unmeasured=branch_unmeasured,
                      measurement_policy=('training_selected_branch_not_deployment_pass_at_1'
                                          if len(branch_tasks) == len(traces) else
                                          'mixed_legacy_final_and_training_selected'))
    return result


def _repair_round_stats(traces: list[RolloutTrace]) -> dict:
    """统计任务内修复轮 c⁰ → c¹ 的功能/安全通过率（看板"单任务修复效果"用）。

    c⁰ = 首次从零生成后的验证；c¹ = 修复轮后的验证。分母同样是各轮实际样本数。
    """
    def side(idx: int) -> dict:
        n = f = s = 0
        for t in traces:
            if t.branches:
                continue  # 并行选优不是 c0；单独在 branch_metrics 中报告首分支和 oracle。
            evs = t.evidence or []
            if idx < len(evs) and isinstance(evs[idx], dict) and "error" not in evs[idx]:
                n += 1
                f += int((evs[idx].get("functional") or {}).get("status") == "pass")
                s += int((evs[idx].get("security") or {}).get("status") == "pass")
        return {"samples": n,
                "functional": {"pass": f, "total": n, "rate": round(f / n, 4) if n else 0.0},
                "security": {"pass": s, "total": n, "rate": round(s / n, 4) if n else 0.0}}

    result = {"c0": side(0), "c1": side(1)}
    branch_tasks = [trace for trace in traces if trace.branches]
    if branch_tasks:
        result.update(branch_metrics=_branch_metric_sets(branch_tasks),
                      parallel_branch_tasks=len(branch_tasks),
                      measurement_policy='c0_c1_only_legacy_serial; parallel_branches_not_repairs')
    return result


class CleRunner:
    """CLE 闭环编排器：Phase 1 冷启动 + Phase 2 进化 + Phase 3 门控拓扑。"""

    def __init__(
        self,
        requester: Requester,
        tree: HskTree,
        ledger: ErrorLedger,
        *,
        timeout: int = 30,
        workers: int = 1,
        progress: ProgressFn | None = None,
        seed_language: str = "en",
        ablation: "AblationConfig | None" = None,
        anti_overdefense: str = "base",
        gate_select_mode: str = "llm",
        gate_fixed_examples: int = 2,
        min_llm_score: float = 0.6,
        cross_cwe_min_score: float = 0.75,
        antioverdefense_bonus: float = 1.5,
        same_task_bonus: float = 2.0,
        inject_prev_evidence: bool = False,
        retrieval_mode: str = "flat_llm",
        phase3_workers: int = 8,
        context_pipeline: bool = False,
        internal_checks: bool = False,
        branch_count: int = 1,
        gate_mode: str = "candidate",
        embedding_client=None,
    ) -> None:
        if branch_count < 1 or gate_mode not in ('candidate', 'global'):
            raise ValueError('invalid_branch_gate_mode')
        self.branch_count = branch_count
        self.gate_mode = gate_mode
        self.requester = requester
        self.context_pipeline = context_pipeline
        self.internal_checks = internal_checks
        self.tree = tree
        self.ledger = ledger
        self.timeout = timeout
        self.workers = max(1, int(workers))
        self.progress = progress or (lambda msg: None)
        # Phase1 seed 提取的输出语言：默认英文，使经验节点与 PLT 英文任务描述同语言，
        # 否则检索器 TF-IDF 中英重叠恒为 0（实测 71% 查询-节点对重叠为 0）。
        self.seed_language = seed_language
        # 【消融开关】控制 HSK-Tree 各层的生成与注入（A1~A6），默认 A5（完整 Level 4）。
        from .ablation import get_config as _get_ablation

        self.ablation = ablation or _get_ablation("A5")
        # 反过度防御干预臂：base / anti_od / contract_freeze（见 run_overdefense_experiment.py）
        self.anti_overdefense_arm = anti_overdefense
        self._anti_od = anti_overdefense == "anti_od"
        self._contract_freeze = anti_overdefense == "contract_freeze"
        # 门控例子数模式：llm=LLM 自由决定（允许 0 条）/ fixed=固定 N 条（对照实验用）
        self.gate_select_mode = gate_select_mode
        self.gate_fixed_examples = gate_fixed_examples
        # 注入相关性门槛（用户要求"需要才注入，不需要 0 条也可以"）
        self.min_llm_score = min_llm_score
        self.cross_cwe_min_score = cross_cwe_min_score
        self.antioverdefense_bonus = antioverdefense_bonus
        # 同任务历史经验加权（改造 D）
        self.same_task_bonus = same_task_bonus
        # 【检索机制】（用户 2026-09-22）：flat_llm 旧机制 / hier_llm 层次化新机制
        # / flat_rule 与 hier_rule 为无 LLM 消融对照臂。
        self.retrieval_mode = retrieval_mode
        self.embedding_client = embedding_client
        self.admission_rejections = []
        # 【修复轮直接注入上一轮报错】默认**关闭**（用户拍板 2026-09-21）。
        # 用户的设计意图是"报错先入经验库，下一轮由检索器取回"，而不是直接拼进 prompt。
        # 但要注意一个时序限制：**同一次 rollout 内**的修复轮拿不到检索结果——
        # 经验要等 rollout 结束后才由 Distillation 提炼入池（见 phase2_evolve.done），
        # 而 Phase1 的 _run_rollout 干脆不接检索器（retriever=None）。
        # 因此这个开关是给"需要覆盖同 rollout 内修复轮"的场景预留的，默认不启用。
        self.inject_prev_evidence = inject_prev_evidence
        # Phase3 审计并发（独立于 workers）：每条经验要跑基线+加候选两轮生成，
        # 若与 Phase1/2 同用高并发会瞬间打出大量请求，故单独设默认 8。
        self.phase3_workers = max(1, int(phase3_workers))
        # 【精确成本】把各个 LLM 调用点分别包上标签，usage 自动归集到 cost_tracker。
        # 各模块内部无需改动：只需在调用时改用对应的带标签 requester。
        from .cost_tracker import global_tracker, labeled

        self.cost = global_tracker()
        self.req_extract = labeled(requester, "extract", self.cost)          # seed 差异提取
        self.req_gen = labeled(requester, "gen.pipeline", self.cost)         # 四步生成流水线
        self.req_score = labeled(requester, "retrieve.score", self.cost)     # 检索 LLM 打分
        self.req_distill = labeled(requester, "distill", self.cost)          # 经验提炼
        self.req_schedule = labeled(requester, "schedule", self.cost)         # 回放调度
        self.req_consolidate = labeled(requester, "consolidate", self.cost)  # 归并
        self.req_level4 = labeled(requester, "level4", self.cost)            # Level 4 语言叶生成
        self.req_gate_select = labeled(requester, "gate.select", self.cost)  # 门控任务选择器
        # 【统一经验池】Phase1（冷启动，含成功与失败）与 Phase2（重放+多Agent）产出的
        # 经验一视同仁地插入这里，不在插入时做任何门控；Phase3 对全池统一处理。
        self.experience_pool: list[SecurityInvariantNode] = []
        # 兼容旧字段名（保留别名，便于既有调用/脚本读取）
        self.traces: list[RolloutTrace] = []
        # 【经验池写锁】（方案 A，2026-09-21）
        # 原设计：经验池只在"消费线程"里写（见 phase2_evolve.done 的注释），
        # 因为 _absorb_in_pool 会遍历整个池做重叠吸收，并发写会竞态。
        # 方案 A 要求 rollout 内的修复轮之前就能检索到自己首轮失败提炼的经验，
        # 于是提炼与入池必须发生在 worker 线程里 —— 故引入这把锁把
        # "插入 + 池内去重"全过程互斥。只保护写路径，读路径（检索）仍并发。
        self._pool_lock = threading.Lock()
        self.last_schedule: dict[str, Any] = {}

    @property
    def candidates(self) -> list[SecurityInvariantNode]:
        """向后兼容别名：指向统一经验池中尚未处理的条目。"""
        return self.experience_pool

    def _map(self, fn, items: list, *, on_done: Callable[[Any], None] | None = None, workers: int | None = None) -> list:
        """对 items 并发执行 fn（无共享状态），逐个就绪即消费（流式）。

        on_done(result)：每个 future 就绪时立即回调（用于逐条落盘 + 进度输出），
        在 worker 线程池的消费线程内串行调用，因此 HSK-Tree/错题本写入线程安全。
        workers=1 时串行执行，on_done 仍逐条调用。
        """
        # 调度层独立并发预算；不修改验证证据、门控或长期经验。
        worker_count = max(1, self.workers if workers is None else workers)
        if worker_count <= 1 or len(items) <= 1:
            results = []
            for item in items:
                try:
                    result = fn(item)
                except Exception as exc:
                    result = {"task_id": item.get("index") if isinstance(item, dict) else None,
                              "outcome": "runner_error", "error": type(exc).__name__}
                results.append(result)
                if on_done:
                    on_done(result)
            return results
        results: list[Any] = []
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(fn, item): item for item in items}
            for future in as_completed(futures):
                try:
                    result = future.result()
                except Exception as exc:  # 单任务异常不中断整批
                    item = futures[future]
                    result = {"task_id": item.get("index") if isinstance(item, dict) else None,
                              "outcome": "runner_error", "error": type(exc).__name__}
                results.append(result)
                if on_done:
                    on_done(result)
        return results

    # ---------- Phase 1：冷启动 ----------

    def _phase1_one(self, row: dict) -> dict:
        """处理单个 source 任务（无副作用，可并发）：提取 seed + 从零生成两轮 + 验证。

        产出与 Phase2 同构的 RolloutTrace（c⁰ 首轮、c¹ 修复轮），使 Phase1 无论
        成功还是失败都能交给 Distillation 提炼经验——成功提炼正例，失败提炼
        盲区/反模式，而不是只记一个四态标签。
        """
        entry: dict[str, Any] = {
            "task_id": row.get("index"), "cwe": str(row.get("CWE_ID", "")),
            "outcome": "", "card_id": "", "_card": None, "_failure": "",
            "state_first": "", "state_after_repair": "",
            "evidence_first": None, "evidence_after_repair": None,
            "_trace": None, "distilled": None,
            # 看板需要：失败案例也要能单独展示代码与四步上下文
            "generated_codes": [], "patch_diffs": [], "agent_context": [],
            # Level 4 生成结果（消融审计用）
            "level4_languages": [], "level4_error": None,
        }
        # 工作线程内设置成本阶段（threading.local 不跨线程继承）
        self.cost.set_stage("phase1")
        try:
            card = extract_initial_hypothesis(row, self.req_extract, output_language=self.seed_language)
            entry["card_id"] = card.get("id", "")
            entry["_card"] = card
            # 注：这里原有一个 `task = row.get("task_description") or {}` 的赋值，
            # 但后续从未使用（实测 pyflakes 报 unused）——已删除，避免误导读者以为
            # 下游用到了它。真正的任务契约在 _run_rollout 里从 row 重新取。

            # Level 4：为该 seed 经验生成四语言叶（python/cpp/go/java）。
            # A1/A2 组不生成（config.has_level4=False），保持基线行为。
            l4_leaves, l4_err = {}, None
            if self.ablation.has_level4:
                from .level4 import generate_level4

                l4_leaves, l4_err = generate_level4(
                    cwe=str(row.get("CWE_ID", "")),
                    invariant=str(card.get("principle", "")),
                    positive=str(card.get("recommended_action", "")),
                    negative=str(card.get("dangerous_pattern", "")),
                    requester=self.req_level4, config=self.ablation,
                )
            entry["level4_languages"] = sorted(l4_leaves.keys())
            entry["level4_error"] = l4_err
            entry["_level4"] = l4_leaves

            # 用与 Phase2 相同的 rollout 机制跑两轮（Phase1 无检索卡，从零生成）
            # 【Phase1 也要有检索器】（方案 A 修正）：首轮仍只用 seed 卡，
            # 但修复轮需要检索"上一轮即时提炼的同任务失败经验"。
            # 构造器很轻，每任务建一个即可；检索只在修复轮发生。
            trace = self._run_rollout(
                row, retriever=HskTreeRetriever(
                    self.tree, requester=self.req_score, ablation=self.ablation,
                    min_llm_score=self.min_llm_score,
                    cross_cwe_min_score=self.cross_cwe_min_score,
                    antioverdefense_bonus=self.antioverdefense_bonus,
                    same_task_bonus=self.same_task_bonus,
                                         retrieval_mode=self.retrieval_mode, embedding_client=self.embedding_client),
                repairs=1, phase="phase1",
                seed_card={"invariant_id": card.get("id"), "kind": "seed_from_diff", "status": "seed",
                           "recommended_action": card.get("recommended_action", ""),
                           "fix_directive": card.get("recommended_action", ""),
                           "exclusion_conditions": card.get("non_applicable_boundary", ""),
                           "negative_guardrail": card.get("unsafe_alternative") or card.get("dangerous_pattern", ""),
                           "polarity": "positive", "principle": card.get("principle", ""),
                           "high_level_invariant": card.get("principle", ""),
                           "applicability": card.get("applicability", "")},
            )
            entry["_trace"] = trace
            states = trace.states or []
            entry["state_first"] = states[0] if states else ""
            entry["state_after_repair"] = states[1] if len(states) > 1 else ""
            # 落盘代码/差分/四步上下文（看板要能把失败例子挑出来单独展示）
            entry["generated_codes"] = list(trace.generated_codes or [])
            entry["patch_diffs"] = list(trace.patch_diffs or [])
            entry["agent_context"] = list(trace.agent_context or [])
            evs = trace.evidence or []
            if evs and isinstance(evs[0], dict) and "error" not in evs[0]:
                entry["evidence_first"] = {
                    "syntax_or_compile": (evs[0].get("syntax_or_compile") or {}).get("status"),
                    "functional": (evs[0].get("functional") or {}).get("status"),
                    "security": (evs[0].get("security") or {}).get("status"),
                    "functional_detail": str((evs[0].get("functional") or {}).get("details"))[:200],
                    "security_detail": str((evs[0].get("security") or {}).get("details"))[:200],
                }
            if len(evs) > 1 and isinstance(evs[1], dict) and "error" not in evs[1]:
                entry["evidence_after_repair"] = {
                    "syntax_or_compile": (evs[1].get("syntax_or_compile") or {}).get("status"),
                    "functional": (evs[1].get("functional") or {}).get("status"),
                    "security": (evs[1].get("security") or {}).get("status"),
                    "functional_detail": str((evs[1].get("functional") or {}).get("details"))[:200],
                    "security_detail": str((evs[1].get("security") or {}).get("details"))[:200],
                }

            final_state = states[-1] if states else "D"
            if final_state == "A":
                entry["outcome"] = "seed_active" if len(states) == 1 else "seed_active_after_repair"
            else:
                entry["outcome"] = "seed_grounding_failure"
                entry["_failure"] = final_state

            # 无论成败都提炼经验（关键改动：失败也产出可复用经验）
            try:
                entry["distilled"] = distill_trace(
                    trace, self.req_distill, phase="phase1",
                    # 方案 A：跳过已在 rollout 内即时提炼过的轮次，避免成对重复
                    skip_rounds=set(getattr(trace, "inline_distilled_rounds", []) or []))
            except Exception as exc:
                entry["distilled"] = {"error": type(exc).__name__}
            return entry
        except Exception as exc:
            entry["outcome"] = "seed_error"
            # 记录异常：类型 + 消息（此前只记类型名，排查偶发失败时看不到原因，
            # 只能靠事后复现；实测 task=78 的 ValueError 就是这样查的）。
            entry["error"] = f"{type(exc).__name__}: {exc}"[:300]
            entry["_failure"] = type(exc).__name__
            return entry

    def _insert_experience(self, node: SecurityInvariantNode, *, stage: str, task_id: Any) -> None:
        """把一条经验插入【统一经验池】（Phase1 与 Phase2 一视同仁，不提前门控）。

        这是架构归一化的核心：两个阶段产出的经验都只做"插入"，不在这里决定去留；
        是否入树由 Phase3 对全池统一处理（Gate1/2/3 + 归并 + 剪枝）决定。

        【池级去重】插入前先与同 CWE 的既有经验做语义重叠检查，Overlap≥0.6 就地吸收
        （合并红线、叶节点求并集、support 累加），不新增条目。
        为什么必须在这里做：实测全量运行经验池 1284 条里有 **230 对**同 CWE 重叠≥0.6
        的重复（如 seed-678 与 seed-679 重叠 0.69），因为原先只有"入树"时才做吸收，
        而池是只增不减的——冗余经验在检索时挤占名额、稀释质量。
        """
        node.source = {**(node.source or {}), "stage": stage, "task_id": task_id}
        # 英文准入仅检查知识自然语言；失败保留审计，不终止其他任务或修改旧库。
        from .english_policy import assert_english_experience, EnglishPolicyError
        try:
            assert_english_experience(node.to_dict())
        except EnglishPolicyError as exc:
            self.admission_rejections.append({'invariant_id': node.invariant_id,
                'stage': stage, 'task_id': task_id, 'error': str(exc)})
            return
        absorbed = self._absorb_in_pool(node)
        if absorbed is not None:
            self.absorb_count = getattr(self, "absorb_count", 0) + 1
            return
        self.experience_pool.append(node)

    def _absorb_in_pool(self, node: SecurityInvariantNode,
                        *, threshold: float = OVERLAP_ABSORB) -> SecurityInvariantNode | None:
        """在经验池内做 DOCX 6.3 的"就地吸收"。

        与 absorb_or_new 的区别：后者只比较 status=active 的树节点；本方法比较**池内全部**
        同一 CWE 的经验（含 provisional），因为 Phase1/Phase2 产出的绝大多数都是 provisional。
        返回被吸收到的既有节点（表示本条不必新增），无匹配返回 None。
        """
        text_new = (node.high_level_invariant or "") + " " + (node.positive_principle or "")
        if not text_new.strip():
            return None
        best, best_score = None, 0.0
        for existing in self.experience_pool:
            if str(existing.cwe) != str(node.cwe):
                continue
            if existing.status == "retired":
                continue
            text_ex = (existing.high_level_invariant or "") + " " + (existing.positive_principle or "")
            score = tfidf_overlap(text_ex, text_new)
            if score > best_score:
                best, best_score = existing, score
        if best is None or best_score < threshold:
            return None
        # 就地吸收：红线取并集、叶节点合并、support 累加、来源留痕
        if node.negative_guardrail and node.negative_guardrail not in (best.negative_guardrail or ""):
            best.negative_guardrail = ((best.negative_guardrail or "") + "；" + node.negative_guardrail).strip("；")
        if not best.positive_principle and node.positive_principle:
            best.positive_principle = node.positive_principle
        for lang, leaf in (node.language_leaves or {}).items():
            if lang in best.language_leaves:
                ex_leaf = best.language_leaves[lang]
                ex_leaf.safe_constructs = sorted(set(ex_leaf.safe_constructs) | set(leaf.safe_constructs))
                ex_leaf.prohibited_constructs = sorted(set(ex_leaf.prohibited_constructs) | set(leaf.prohibited_constructs))
                if not ex_leaf.pattern_snippet and leaf.pattern_snippet:
                    ex_leaf.pattern_snippet = leaf.pattern_snippet
            else:
                best.language_leaves[lang] = leaf
        best.support_count += max(1, node.support_count)
        # 【失败现场不得在吸收时丢失】（2026-09-21 实测缺口）：
        # 原实现只并红线与叶节点，被吸收条目的 root_cause / fix_directive /
        # prev_fix_assessment 直接消失——实测 prev_fix_assessment 全空即由此而来。
        # 修法：按字段追加（去重 + 截断），保留证据链，使检索/选择器仍能看到。
        _bs = best.source or {}
        _ns = node.source or {}
        best.source = {
            **_bs,
            "root_cause": _append_note(_bs.get("root_cause"), _ns.get("root_cause")),
            "fix_directive": _append_note(_bs.get("fix_directive"), _ns.get("fix_directive")),
            "prev_fix_assessment": _append_note(
                _bs.get("prev_fix_assessment"), _ns.get("prev_fix_assessment")),
            "absorbed_from": [
                *((_bs.get("absorbed_from")) or []), node.invariant_id],
        }
        return best

    def _insert_with_level4(self, node: SecurityInvariantNode, *, stage: str,
                            task_id: Any, kind: str = "") -> None:
        """插入经验前补 Level 4 多语言叶 + （拆分模式下）Level 3 轨道规则。

        Phase2 提炼出的经验与 Phase1 的 seed 走同一套：都要产出四语言叶，
        否则第 4 层只在冷启动阶段存在，消融实验会失真。
        """
        if self.ablation.has_level4 and node.language_leaves:
            err = _attach_level4(
                node, requester=self.req_level4, config=self.ablation,
                cwe=str(node.cwe),
                invariant=node.high_level_invariant,
                positive=node.positive_principle,
                negative=node.negative_guardrail,
            )
            if err:
                node.source = {**(node.source or {}), "level4_error": err}
        if self.ablation.split_level23:
            node.track_rules = _build_track_rules(node, kind=kind)
        if not node.language_leaves:
            node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
        self._insert_experience(node, stage=stage, task_id=task_id)

    def _insert_distilled_round_items(self, items: list[dict], *, stage: str,
                                      task_id: Any) -> int:
        """把"按轮提炼"的条目按 target 路由入池，返回成功插入条数。

        路由规则与 distill_trace 分流一致：
          target == "negative_guardrail" → 负向红线节点（_node_from_negative）
          其余（error_ledger）           → 盲区节点（_node_from_ledger_item）

        **必须在持 self._pool_lock 的情况下调用**（本方法内部会调 _insert_with_level4
        → _insert_experience → _absorb_in_pool，后者遍历整个池）。
        """
        n = 0
        for d in items:
            if str(d.get("target")) == "negative_guardrail":
                node = _node_from_negative(d)
            else:
                node = _node_from_ledger_item(d)
            if node:
                self._insert_with_level4(node, stage=stage, task_id=task_id,
                                         kind=d.get("kind", ""))
                n += 1
        return n

    def _distill_round_inline(self, *, row: dict, states: list[str], codes: list[str],
                              evidence_list: list[dict], agent_contexts: list[dict],
                              retrieved_per_round: list[list[dict]],
                              round_index: int, phase: str) -> int:
        """【方案 A】某一轮失败后**立刻**提炼并入池，使下一次修复能检索到它。

        所属阶段：Phase1 / Phase2 的 rollout 内部（在进入下一轮修复之前）。
        输入：该任务到目前为止的累计轨迹数据 + 当前轮索引。
        输出：成功入池的经验条数（0 = 无可提炼内容 / 提炼失败 / 已关闭）。
        验证证据：直接复用该轮 `validate_and_state` 的真实证据，不重跑测试。
        失败类型：提炼或解析异常一律吞掉并返回 0 —— 即时提炼是"锦上添花"，
            不得因为它失败而中断整条 rollout。
        允许修改长期经验库：**是**（本方法的目的就是写池），故必须持 `_pool_lock`。

        为什么传累计轨迹而不是单轮：`distill_each_round` 会用 `states[i-1]` 生成
        "上一轮改法为何没奏效"的上下文。若只传当前轮，修复轮会丢掉这段最有价值的诊断。
        因此这里传累计列表，并用 `skip_rounds` 只提炼当前轮。

        线程安全：本方法在 `_map` 的 worker 线程里被调用（与原有"只在消费线程写池"
        的约定不同），因此插入过程必须持 `self._pool_lock`。
        """
        if self.req_distill is None or not states:
            return 0
        partial = RolloutTrace(
            task_id=str(row.get("index")), cwe=str(row.get("CWE_ID", "")),
            family_id=str(row.get("family_id", "")), language="python",
            round=round_index,
            states=list(states),
            transitions=[
                Transition(before=states[i], after=states[i + 1],
                           kind=classify_transition(states[i], states[i + 1]))
                for i in range(len(states) - 1)
            ],
            generated_codes=list(codes),
            evidence=list(evidence_list),
            retrieved_per_round=list(retrieved_per_round),
            patch_diffs=[],
            agent_context=list(agent_contexts),
            task_contract=json.dumps(row.get("task_description") or {}, ensure_ascii=False),
        )
        try:
            items = distill_each_round(partial, self.req_distill, phase=phase,
                                       skip_rounds=set(range(round_index)))
        except Exception:
            return 0
        if not items:
            return 0
        with self._pool_lock:
            return self._insert_distilled_round_items(items, stage=phase,
                                                      task_id=row.get("index"))

    def _merge_phase1(self, entry: dict) -> None:
        """串行合并 Phase1 产出：无论成败都把经验插入统一池 + 记录错题本。

        - seed 经验卡（从漏洞—补丁差异提取）→ 插入池（不直接入树，等 Phase3 统一处理）
        - Distillation 提炼的正例 → 插入池
        - Distillation 提炼的盲区（stalled/失败）→ 插入池（作为负向经验）+ 同步错题本
        """
        task_id = entry.get("task_id")
        cwe = str(entry.get("cwe", ""))
        outcome = entry.get("outcome", "")

        # 1) seed 经验卡（差异提��）——无论最终状态都插入池，标注其验证结果
        card = entry.get("_card")
        if card:
            node = _seed_node_from_card(card)
            node.status = "provisional"      # 统一以 provisional 入池，Phase3 决定晋升
            node.source = {
                **node.source,
                "stage": "phase1",
                "kind": "seed_from_diff",
                "verified_state": entry.get("state_after_repair") or entry.get("state_first") or "",
                "outcome": outcome,
            }
            # Level 4：挂上四语言叶（A1/A2 组为空）
            for lang, leaf in (entry.get("_level4") or {}).items():
                node.language_leaves[lang] = leaf
            # 拆分模式：把双轨提升为独立 Level 3 规则节点
            if self.ablation.split_level23:
                node.track_rules = _build_track_rules(node, kind="seed_from_diff")
            if not node.language_leaves:
                node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
            self._insert_experience(node, stage="phase1", task_id=task_id)

        # 2) Distillation 从两轮轨迹提炼的经验（成功→正例，失败→盲区）
        distilled = entry.get("distilled") or {}
        for d in (distilled.get("positive") or []):
            node = _node_from_distilled(d)
            if node:
                self._insert_with_level4(node, stage="phase1", task_id=task_id,
                                         kind=d.get("kind", ""))
        for d in (distilled.get("negative") or []):
            node = _node_from_negative(d)
            if node:
                self._insert_with_level4(node, stage="phase1", task_id=task_id,
                                         kind=d.get("kind", ""))
        for d in (distilled.get("error_ledger") or []):
            node = _node_from_ledger_item(d, cwe=cwe)
            if node:
                self._insert_with_level4(node, stage="phase1", task_id=task_id,
                                         kind=d.get("kind", "stalled"))
            # 错题本同步记录（保留原有的结构化统计）
            self.ledger.add(ErrorEntry(
                cwe=str(d.get("cwe") or cwe),
                kind=str(d.get("kind") or "seed_grounding_failure"),
                # failure_type 决定错题本的失败画像，会经 replay_bias / analysis_warning
                # 反过来影响调度打分。按轮失败条目没有 blind_spot，若只取它就会
                # 全部记成 "unknown"，让错题本失去区分度——这里补上 root_cause 兜底。
                failure_type=str(d.get("blind_spot") or d.get("attribution")
                                 or d.get("root_cause") or "unknown")[:200],
                source_hash=str(task_id),
                transition=str(d.get("kind", "")),
            ))

        # 4) 新增两类经验（最小改动手法 / 过度防御陷阱）也一律入池参与检索
        for d in _all_distilled_items(distilled):
            for factory, kindname in ((_node_from_hint, "minimal_patch_hint"),
                                      (_node_from_pitfall, "overdefense_pitfall")):
                extra = factory(d)
                if extra:
                    self._insert_with_level4(extra, stage="phase1", task_id=task_id,
                                             kind=kindname)

        # 3) 若 Distillation 失败/无产出，至少保留结构化错题记录（不丢信息）
        if not distilled or distilled.get("error"):
            self.ledger.add(ErrorEntry(
                cwe=cwe,
                kind="seed_grounding_failure" if outcome.startswith("seed_grounding") else outcome,
                failure_type=str(entry.get("_failure") or outcome or "unknown")[:200],
                source_hash=str(task_id),
                transition="",
            ))

    def phase1_seed(self, source_tasks: list[dict], *, repairs: int = 1, on_item: Callable[[dict], None] | None = None) -> dict:
        """Phase 1：并发处理 + 流式合并（经验统一插入池，不直接入树）。

        on_item(clean_entry)：每完成一条即回调（供 CLI 逐条落盘），在消费线程串行
        调用，与 _merge_phase1 同线程，保证池/错题本写入安全。
        """
        self.cost.set_stage("phase1")
        results: list[dict] = []
        counter = {"n": 0}

        def done(entry: dict) -> None:
            self._merge_phase1(entry)
            clean = {k: v for k, v in entry.items() if not k.startswith("_")}
            results.append(clean)
            counter["n"] += 1
            if on_item:
                on_item(clean)
            self.progress(f"[Phase1 {counter['n']}/{len(source_tasks)}] task={entry.get('task_id')} {entry.get('outcome')}")

        self._map(self._phase1_one, source_tasks, on_done=done)
        return {"results": results, "pool_size": len(self.experience_pool),
                "tree_size": sum(len(f.invariants) for f in self.tree.all_families())}

    def _repair_once(self, row: dict, code: str) -> str:
        """单轮任务内修复：把上一轮代码作为参考再走一次四步流水线。"""
        task = row.get("task_description") or {}
        pipeline = run_pipeline(task, [], requester=self.req_gen, reference_code=code,
                                        anti_overdefense=self._anti_od,
                                        contract_freeze=self._contract_freeze,
                                        context_mode=self.context_pipeline)
        return (pipeline.get("code") or "").strip()

    # ---------- Phase 2：进化 ----------

    def _phase2_one(self, row: dict, retriever: HskTreeRetriever, repairs: int,
                    round_index: int = 1) -> dict:
        """处理单个 replay 任务（无副作用，可并发）：rollout + Distillation。"""
        self.cost.set_stage("phase2")
        try:
            if self.branch_count > 1:
                # 新探索模式：同题快照隔离，兄弟分支全部生成测试后统一提炼；只写候选。
                import copy
                from .branch_pipeline import run_branches, branch_trace, distill_branches
                with self._pool_lock:
                    snapshot = copy.deepcopy(self.experience_pool)
                local_retriever = HskTreeRetriever(HskTree(), requester=self.req_score,
                    ablation=self.ablation, retrieval_mode=self.retrieval_mode, embedding_client=self.embedding_client,
                    min_llm_score=self.min_llm_score, cross_cwe_min_score=self.cross_cwe_min_score,
                    antioverdefense_bonus=self.antioverdefense_bonus, same_task_bonus=self.same_task_bonus)
                task = {**(row.get('task_description') or {}), 'task_id': row['index'],
                        'CWE_ID': str(row.get('CWE_ID', '')), 'language': 'python'}
                def generate_request(prompt):
                    self.cost.set_stage('phase2')
                    return self.req_gen(prompt)
                result = run_branches(task, requester=generate_request,
                    retrieve=lambda q: local_retriever.search(q, limit=3, pool_nodes=snapshot),
                    validate=lambda code: validate_and_state(row, code, timeout=self.timeout)[0],
                    count=self.branch_count)
                trace = branch_trace(row, result, round_index=round_index)
                distilled = distill_branches(trace, self.req_distill)
                return {'task_id': row['index'], 'trace': trace, 'distilled': distilled,
                        'zero_hit': None, 'retrieval_hit': bool(result['shared_context']['cards']),
                        'error': distilled.get('error')}
            trace = self._run_rollout(row, retriever, repairs=repairs, round_index=round_index,
                                      phase="phase2")
            distilled = distill_trace(
                trace, self.req_distill,
                # 方案 A：跳过已在 rollout 内即时提炼过的轮次，避免成对重复
                skip_rounds=set(getattr(trace, "inline_distilled_rounds", []) or []))
            # 【零命中补偿】检索一条经验都没命中时，额外提炼一条针对该 CWE 缺口的经验，
            # 打破"没经验→检索空→更没经验"的死循环（用户拍板 Q5=选 c）。
            hit = any(rd for rd in (trace.retrieved_per_round or []))
            zero_hit = None
            if not hit:
                from .distillation import distill_zero_hit

                task = row.get("task_description") or {}
                zero_hit = distill_zero_hit(
                    cwe=str(row.get("CWE_ID", "")),
                    task_description=str(task.get("description", "")),
                    final_state=(trace.states or ["?"])[-1],
                    code=(trace.generated_codes or [""])[-1],
                    evidence=(trace.evidence or [{}])[-1],
                    requester=self.req_distill,
                )
            return {"task_id": row.get("index"), "trace": trace, "distilled": distilled,
                    "zero_hit": zero_hit, "retrieval_hit": hit, "error": None}
        except Exception as exc:
            return {"task_id": row.get("index"), "trace": None, "distilled": None,
                    "zero_hit": None, "retrieval_hit": False, "error": type(exc).__name__}

    def phase2_evolve(self, replay_pool: list[dict], *, batch_size: int = 24, replay_limit: int = 96, repairs: int = 1, round_index: int = 1, forced_tasks: list[dict] | None = None, already_used: set[int] | None = None, coverage_quota: int = 0, on_item: Callable[[dict], None] | None = None) -> dict:
        """Phase 2：主动回放调度 → 并发 rollout + 蒸馏 → 流式合并候选与错题本。

        forced_tasks：**强制重放**的任务（上一轮末态为 B/C/D）。这些任务不受 LLM
        调度结果影响，一定进入本轮 rollout——避免模型只挑容易的任务、失败样本
        永远得不到修复（用户拍板要求）。

        【返回值 traces 的口径】（2026-09-21 实测缺陷修复）：
        必须只返回**本轮**新增的轨迹，不能返回 `self.traces` 全量。
        原实现返回全局累积，导致调用方 `run_evolution_rounds` 每轮都把历轮轨迹
        重新遍历一遍，产生两个后果：
          ① `retry_counts` 被重复累加 —— 实测日志出现"已重放 4 次仍失败，达上限 3"，
             同一批 task 在一轮内被加 3 次，**强制重放机制实际只生效一轮**；
          ② `hpass`（H_pass 回归门控证据）混入历轮的陈旧 A 态轨迹。
        本轮起点在函数入口处捕获。
        """
        trace_start = len(self.traces)   # 本轮轨迹起点（self.traces 为全局累积）
        self.cost.set_stage("phase2")
        retriever = HskTreeRetriever(self.tree, requester=self.req_score, ablation=self.ablation,
                                         min_llm_score=self.min_llm_score,
                                         cross_cwe_min_score=self.cross_cwe_min_score,
                                         antioverdefense_bonus=self.antioverdefense_bonus,
                                         same_task_bonus=self.same_task_bonus,
                                         retrieval_mode=self.retrieval_mode, embedding_client=self.embedding_client)
        sched = schedule_replay(self.tree, self.ledger, replay_pool, self.req_schedule,
                                batch_size=batch_size, replay_limit=replay_limit,
                                already_used=already_used, coverage_quota=coverage_quota)
        # 【覆盖配额被有界上限截断】必须显式提示：否则用户只会看到"覆盖率没达标"，
        # 却不知道根因是 replay_limit 太小（调大该参数即可）。
        if sched.get("coverage_truncated"):
            self.progress(f"[Phase2] [警告] 覆盖配额被 replay_limit={replay_limit} 截断，"
                          f"本轮仍有 {sched['coverage_truncated']} 条未覆盖任务未补入；"
                          f"如需提高单轮覆盖请调大 --replay-limit")
        selected = list(sched["selected"])
        # 合并强制重放任务（去重，放在最前面以体现优先级）
        forced_ids = {int(t.get("index", -1)) for t in (forced_tasks or [])}
        selected_ids = {int(t.get("index", -1)) for t in selected}
        merged_forced = [t for t in (forced_tasks or []) if int(t.get("index", -1)) not in selected_ids]
        selected = (forced_tasks or []) + [t for t in selected if int(t.get("index", -1)) not in forced_ids]
        self.last_schedule = {
            "pool_size": len(replay_pool),
            "raw_decisions": sched.get("decisions") or [],
            "selected_ids": [t.get("index") for t in selected],
            "llm_selected_ids": sorted(selected_ids),
            "forced_ids": sorted(forced_ids),
            "forced_added": [t.get("index") for t in merged_forced],
            "llm_reasons": sched.get("reasons") or {},
            "error": sched.get("error"),
        }
        self.progress(f"[Phase2] 调度选中 {len(selected)}/{len(replay_pool)} 条回放任务"
                      f"（LLM 选出 {len(selected_ids)} 条 + 强制重放 {len(forced_ids)} 条，"
                      f"decisions={len(self.last_schedule['raw_decisions'])}，"
                      f"error={self.last_schedule['error']}）")

        def process(row: dict) -> dict:
            return self._phase2_one(row, retriever, repairs, round_index)

        state = {"positive": 0, "negative": 0, "ledger": 0, "n": 0, "zero_hit": 0}

        def done(out: dict) -> None:
            trace = out.get("trace")
            distilled = out.get("distilled")
            if trace is not None:
                self.traces.append(trace)
            if distilled:
                task_id = out.get("task_id")
                # 架构归一化：Phase2 的经验同样只"插入"统一池，不在这里门控；
                # 插入前补 Level 4 多语言叶（与 Phase1 一致）。
                for d in distilled["positive"]:
                    node = _node_from_distilled(d)
                    if node:
                        self._insert_with_level4(node, stage="phase2", task_id=task_id,
                                                 kind=d.get("kind", ""))
                        state["positive"] += 1
                for d in distilled["negative"]:
                    node = _node_from_negative(d)
                    if node:
                        self._insert_with_level4(node, stage="phase2", task_id=task_id,
                                                 kind=d.get("kind", ""))
                        state["negative"] += 1
                for item in distilled["error_ledger"]:
                    node = _node_from_ledger_item(item)
                    if node:
                        self._insert_with_level4(node, stage="phase2", task_id=task_id,
                                                 kind=item.get("kind", ""))
                    self.ledger.add(ErrorEntry(
                        cwe=item.get("cwe", ""), kind=item.get("kind", "stalled"),
                        failure_type=str(item.get("blind_spot")
                                         or item.get("root_cause") or "stalled")[:60],
                        source_hash=str(task_id),
                        transition=str(item.get("kind", "")),
                    ))
                    state["ledger"] += 1
                # 新增两类经验（最小改动手法 / 过度防御陷阱）同样插入统一池
                for d in _all_distilled_items(distilled):
                    for factory, kindname in ((_node_from_hint, "minimal_patch_hint"),
                                              (_node_from_pitfall, "overdefense_pitfall")):
                        extra = factory(d)
                        if extra:
                            self._insert_with_level4(extra, stage="phase2", task_id=task_id,
                                                     kind=kindname)
            # 【零命中补偿】把为该 CWE 缺口提炼的经验也插入统一池
            zh = out.get("zero_hit")
            if zh and not zh.get("error"):
                task_id = out.get("task_id")
                node = _node_from_distilled(zh, prefix="gap")
                if node is None:
                    # 补偿条目可能只有 blind_spot / minimal_patch_hint，用对应工厂兜底
                    node = _node_from_ledger_item(zh) or _node_from_hint(zh) or _node_from_pitfall(zh)
                if node:
                    node.source = {**(node.source or {}), "zero_hit_compensation": True}
                    self._insert_with_level4(node, stage="phase2", task_id=task_id,
                                             kind="zero_hit_compensation")
                    state["zero_hit"] = state.get("zero_hit", 0) + 1
            state["n"] += 1
            if on_item:
                on_item(out)
            self.progress(f"[Phase2 {state['n']}/{len(selected)}] task={out.get('task_id')} "
                          f"traces={1 if trace else 0} err={out.get('error')}")

        self._map(process, selected, on_done=done)
        return {
            "selected": len(selected),
            "schedule": self.last_schedule,
            # 【只返回本轮轨迹】见函数 docstring：返回全量会让调用方重复累加
            # retry_counts 并把陈旧 A 态混进 hpass。
            "traces": [t.to_dict() for t in self.traces[trace_start:]],
            "positive_candidates": state["positive"],
            "negative_candidates": state["negative"],
            "ledger_entries": state["ledger"],
            "zero_hit_compensations": state.get("zero_hit", 0),
            "pool_size": len(self.experience_pool),
        }

    def run_evolution_rounds(
        self,
        replay_pool: list[dict],
        audit_pool: list[dict],
        *,
        rounds: int = 3,
        batch_size: int = 24,
        replay_limit: int = 96,
        repairs: int = 1,
        audit_per_candidate: int = 5,
        regression_samples: int = 3,
        audit_max_entries: int = 12,
        consolidate_max_active: int = 3,
        max_retries: int = 3,
        seed_forced: list[int] | None = None,
        coverage_target: float = 0.75,
        min_audit_tasks: int = 3,
        on_audit: Callable[[dict], None] | None = None,
        on_phase2_item: Callable[[dict], None] | None = None,
        on_round_end: Callable[[int, Any, dict], None] | None = None,
    ) -> dict:
        """Phase 2+3 多轮闭环演进（DOCX 的 Replay-Audit 迭代）。

        每轮：主动回放调度 → rollout → 蒸馏 → 产出候选 → 立即用 Phase3 门控审计
        → supported 候选入树 → 下一轮（树变强后再调度，直到 replay 池耗尽或达到轮数）。

        【强制重放】（用户拍板）：上一轮末态 ∈ {B,C,D} 的任务必须进入下一轮，
        不依赖 LLM 选择——否则模型会一直挑"容易的"任务，失败样本永远得不到修复。
        max_retries 控制同一任务最多被强制重放几次（默认 3），超过则放弃以免占满预算。
        """
        # 注：这里原有 `used: set[int] = set()`，是 A 方案重构前的残留——
        # 现在用的是 used_tasks（见上方覆盖追踪），该变量从未被读取，已删除。
        remaining = list(replay_pool)
        rounds_log: list[dict] = []
        all_audit_detail: list[dict] = []
        all_gate_records: list[dict] = []
        round_traces: list[list[RolloutTrace]] = []      # 每轮的轨迹（用于分项通过率）
        tree_before = _tree_counts(self.tree)
        # 【强制重放】上一轮末态 ∈ {B,C,D} 的任务必须在下一轮被重放（硬约束，不受 LLM 影响）。
        # retry_counts 记录每个任务已被强制重放的次数，超过 max_retries 则放弃（用户拍板 Q4=3）。
        retry_counts: dict[int, int] = {}
        mandatory: set[int] = set()
        by_id = {int(r.get("index", -1)): r for r in replay_pool}
        # 【续跑支持】seed_forced：从上游运行继承"末态非 A"的任务，
        # 让本段第一轮就强制重放它们（否则续跑会丢失上游的强制重放状态）。
        if seed_forced:
            mandatory.update(int(i) for i in seed_forced if int(i) in by_id)
        # 【重放覆盖追踪】用户要求重放池使用率 ≥ coverage_target（默认 75%）。
        # 实测 3 轮仅覆盖 9/273 = 3.3%，经验素材面过窄。做法：
        #   每轮计算"还差多少未重放任务"，按剩余轮数均摊成本轮配额，
        #   由 schedule_replay 的 coverage_quota 补足（优先补从未跑过的任务）。
        used_tasks: set[int] = set(int(i) for i in (seed_forced or []))
        # 【状态追踪】（用户拍板 A 方案 2026-09-21）：记录每个任务的最新状态，
        # 用于排除"已达 A"的任务——它们重放后大概率仍为 A，产生不了新经验。
        # 实测：原实现会把上一轮已 A 的任务再次重放（轮3 与轮2 选的任务 14/14 完全相同），
        # 等于每轮在跑同一批任务，覆盖推进是假的。
        last_state: dict[int, str] = {}
        # 已达 A 的任务集合（永不重放；按 CWE 保底见下方过滤逻辑）
        passed_ids: set[int] = set()
        # 上一轮实际选中的任务（本轮不再选，除非仍需强制重放）
        prev_round_chosen: set[int] = set()
        # 覆盖率口径：分母改为"未通过任务数"，而非整个 replay 池
        # —— 用户本意是"多选择一些**未通过**任务来形成经验"。
        # 初始目标：首轮尚无"已达 A"记录，分母即整个 replay 池；
        # 每轮会按"未通过任务数"动态重算（见下方）。
        # 注意：这里必须打印真实数字。原实现把 0 直接打进日志
        # （"[覆盖目标] ... 目标覆盖 0 条（75%）"），看起来像"目标就是 0"，
        # 属于会误导排查的静默失真。
        target_n = math.ceil(len(replay_pool) * max(0.0, min(1.0, coverage_target)))
        self.progress(f"[覆盖目标] replay 池 {len(replay_pool)} 条，"
                      f"首轮目标覆盖 {target_n} 条（{coverage_target:.0%}，"
                      f"分母=未通过任务数）")

        for rnd in range(1, max(1, rounds) + 1):
            if not remaining and not mandatory:
                self.progress(f"[轮{rnd}] replay 池已耗尽，提前结束多轮演进")
                break
            # 强制重放集合：上一轮失败且未超过重试上限的任务
            # 双保险：即便 mandatory 里有历史残留，也不让已达 A 的任务被强制重放。
            forced_rows = [by_id[i] for i in sorted(mandatory)
                           if i in by_id and i not in passed_ids]
            # 【重放候选过滤】（用户拍板 A 方案）
            #   ① 排除"已达 A"的任务：重放它们产生不了新经验；
            #   ② 排除"上一轮已选"的任务：避免每轮重复跑同一批。
            #   CWE 保底：若某 CWE 因过滤而无人可跑，仍保留其 1 个任务，避免该 CWE 断档。
            _by_cwe_elig: dict[str, list[dict]] = {}
            for row in remaining:
                _by_cwe_elig.setdefault(str(row.get("CWE_ID", "")), []).append(row)
            _kept: list[dict] = []
            _excluded_a = _excluded_prev = 0
            for cwe, rows in _by_cwe_elig.items():
                elig = []
                for row in rows:
                    tid = int(row.get("index", -1))
                    if tid in passed_ids:
                        _excluded_a += 1
                        continue
                    if tid in prev_round_chosen and tid not in mandatory:
                        _excluded_prev += 1
                        continue
                    elig.append(row)
                if elig:
                    _kept.extend(elig)
                else:
                    # CWE 保底：该 CWE 全被过滤时，保留其中 1 个（优先非 A 的）
                    backup = [r for r in rows if int(r.get("index", -1)) not in passed_ids] or rows
                    _kept.extend(backup[:1])
            # 强制重放的任务必须始终在候选里
            _forced_in = {int(r.get("index", -1)) for r in forced_rows}
            for row in remaining:
                if int(row.get("index", -1)) in _forced_in and row not in _kept:
                    _kept.append(row)
            pool = _kept if _kept else list(remaining)
            # 覆盖率分母 = 未通过任务数（不含已 A）
            _pending = [r for r in replay_pool if int(r.get("index", -1)) not in passed_ids]
            # 【必须向上取整】（2026-09-21 实测缺陷）：原用 int() 向下取整，
            # 池子 17 条时目标 = int(17×0.75) = 12 → 12/17 = 70.6%，**永远够不到 75%**。
            # 目标值本身把标准压到了阈值以下，属自相矛盾的口径错误。
            target_n = math.ceil(len(_pending) * max(0.0, min(1.0, coverage_target)))
            if _excluded_a or _excluded_prev:
                self.progress(f"[轮{rnd}] 重放候选过滤：排除已达A {_excluded_a} 条、"
                              f"上轮已选 {_excluded_prev} 条 → 候选 {len(pool)} 条"
                              f"（未通过任务共 {len(_pending)} 条，目标覆盖 {target_n} 条）")
            if forced_rows:
                self.progress(f"[轮{rnd}] 强制重放上一轮失败任务 {len(forced_rows)} 条："
                              f"{[r.get('index') for r in forced_rows]}")
            # 本轮覆盖配额：把"距目标的差额"按剩余轮数均摊，保证最后一轮能达标
            rounds_left = max(1, (max(1, rounds) - rnd + 1))
            deficit = max(0, target_n - len(used_tasks))
            # 每轮应新覆盖的条数：缺口按剩余轮数均摊（向上取整）
            quota = min(deficit, -(-deficit // rounds_left)) if deficit else 0
            # 下界：即便缺口很小，每轮也至少覆盖候选��的一半，
            # 避免 LLM 保守导致覆盖停滞（实测 LLM 只选候选的 25%）。
            floor_n = -(-len(pool) // 2)
            quota = min(deficit, max(quota, floor_n)) if deficit else 0
            pool_before = len(self.experience_pool)
            self.progress(f"[轮{rnd}] 开始：候选 replay {len(pool)} 条（另有强制 {len(forced_rows)} 条），"
                          f"经验池 {pool_before} 条，树 active "
                          f"{sum(1 for f in self.tree.all_families() for n in f.invariants if n.status=='active')} 节点")
            # 本轮轨迹单独收集（self.traces 是全局累积，不能直接用于逐轮统计）
            round_start = len(self.traces)
            p2 = self.phase2_evolve(
                pool, batch_size=batch_size, replay_limit=replay_limit,
                repairs=repairs, round_index=rnd, on_item=on_phase2_item,
                forced_tasks=forced_rows,
                already_used=set(used_tasks), coverage_quota=quota,
            )
            this_round_traces = self.traces[round_start:]
            round_traces.append(this_round_traces)
            chosen = {int(t["task_id"]) for t in p2["traces"]}
            # 累计"已重放过"的任务（用于覆盖率统计与下轮配额计算）
            used_tasks |= chosen
            # 【状态更新】（用户拍板 A 方案）：记录每个任务本轮末态，
            # 把"已达 A"的加入 passed_ids（下轮起永不重放）。
            # 注意：p2["traces"] 的元素是 **dict**（见同段 1128/1150/1162 行的
            # t["task_id"]、t.get("states")），这里必须同样用下标取值。
            # 原实现误用属性取值（tr.task_id / tr.states），一进这个循环就抛
            # AttributeError 中断整轮演进——实测 2026-09-21 16:49 的验证运行
            # 正是死在这里（Phase2 第 1 轮 9/9 跑完后崩溃）。
            for tr in p2["traces"]:
                tid = int(tr["task_id"])
                st = (tr.get("states") or ["?"])[-1]
                last_state[tid] = st
                if st == "A":
                    passed_ids.add(tid)
            prev_round_chosen = set(chosen)
            # 【覆盖率分母必须用"本轮开始时"的未通过集合】（缺陷 D33，2026-09-21 实测）
            # 原实现用**本轮结束后**的 passed_ids 重算分母，于是本轮刚达 A 的任务
            # 会同时从分子和分母里被剔除 —— 覆盖率会因为"跑得好"而**下降**。
            # 实测（ab_verify3_20260921 轮1）：本轮重放 9/17 条（52.9%），但其中 3 条
            # 达 A 被移出分母 → 日志显示 "14 条中已重放 6 条 = 42.9%"，反而低于实际。
            # 极端情形：若一轮内全部达 A，分母变 0 → 显示 **0% 覆盖率**，与事实完全相反。
            # 修法：分母固定为本轮开始时的 `_pending`（第 1097 行已算好），
            # 另附"本轮新增达 A 数"，让"成功"体现在分子侧而不是扣减分母。
            _cov = len([t for t in used_tasks if t in {int(r.get("index", -1)) for r in _pending}])
            _new_a = sum(1 for tr in p2["traces"]
                         if (tr.get("states") or ["?"])[-1] == "A")
            self.progress(f"[轮{rnd}] 重放覆盖：本轮 {len(chosen)} 条；"
                          f"本轮开始时未通过任务 {len(_pending)} 条中已重放 {_cov} 条 = "
                          f"{100*_cov/max(1,len(_pending)):.1f}%（目标 {coverage_target:.0%}）；"
                          f"本轮新增达A {_new_a} 条，累计已达A {len(passed_ids)} 条")
            remaining = [row for row in remaining if int(row.get("index", -1)) not in chosen]

            # 计算下一轮的强制重放集合：本轮末态失败的（B/C/D），且未超重试上限
            mandatory = set()
            for t in p2["traces"]:
                tid = int(t["task_id"])
                final_state = (t.get("states") or ["?"])[-1]
                if final_state in ("B", "C", "D"):
                    # 已达 A 的任务不得再进强制重放集合（用户拍板 A 方案）。
                    # 实测缺陷：轮2 已 A 的 45/1126/1127 在轮3 仍被强制重放，
                    # 因为旧条目未被清除——这里先 discard 再按需 add，消除残留。
                    if tid in passed_ids:
                        mandatory.discard(tid)
                        continue
                    retry_counts[tid] = retry_counts.get(tid, 0) + 1
                    if retry_counts[tid] <= max_retries:
                        mandatory.add(tid)
                    else:
                        self.progress(f"  task={tid} 已重放 {retry_counts[tid]-1} 次仍失败，"
                                      f"达上限 {max_retries}，放弃重放")

            # Phase3：审计【全池中所有尚未处理的经验】（Phase1 与 Phase2 一视同仁）
            # 【必须带完整任务行】（2026-09-21 实测缺陷 D21）
            # 原实现只取 {cwe, task_id} 两个键，导致 Phase3 的 H_pass 回归跑在
            # **空任务契约**上（审计侧 `r.get("task_description") or {}` → `{}`）：
            # LLM 拿不到函数名与描述，生成的代码必然对不上 → 全部判为"回归"
            # → 候选被误判 demoted。实测证据：cand-1333-… 的 3 个 H_pass 任务
            # 全部记为回归，形态上更像"空描述导致的必然失败"而非真实的经验有害。
            # 这里用 replay 池的原始行补齐 description，并显式标注是否拿到描述。
            _row_by_id = {int(r.get("index", -1)): r for r in replay_pool}
            hpass: list[dict] = []
            for t in p2["traces"]:
                if t["states"][-1:] != ["A"]:
                    continue
                _tid = int(t["task_id"])
                _row = _row_by_id.get(_tid) or {}
                hpass.append({
                    "cwe": t["cwe"],
                    "task_id": _tid,
                    "task_description": _row.get("task_description") or {},
                })
            tree_before_round = _tree_counts(self.tree)
            p3 = self.phase3_audit(
                audit_pool, audit_per_candidate=audit_per_candidate,
                regression_samples=regression_samples, hpass_traces=hpass,
                fallback_tasks=[r for r in remaining if int(r.get("index", -1)) not in chosen],
                max_entries=audit_max_entries,
                consolidate_max_active=consolidate_max_active,
                min_audit_tasks=min_audit_tasks,
                on_audit=on_audit,
            ) if self.gate_mode == 'candidate' else {
                'gate_records': [], 'audit_detail': [], 'audited': 0, 'merged': 0, 'pruned': 0}
            tree_after_round = _tree_counts(self.tree)
            all_audit_detail.extend(p3["audit_detail"])
            all_gate_records.extend(p3["gate_records"])
            promoted = sum(1 for g in p3["gate_records"] if g["decision"] == "supported")
            stats = _round_stats(this_round_traces)
            # 检索命中率（看板用：暴露"零命中=裸跑"的覆盖缺口）
            hit_n = sum(1 for t in this_round_traces
                        if any(rd for rd in (t.retrieved_per_round or [])))
            rounds_log.append({
                "round": rnd,
                "gate_deferred": self.gate_mode == 'global',
                "selection_policy": 'training_oracle_first_joint_else_first' if self.branch_count > 1 else 'serial_repair',
                "replay_candidates": len(pool),
                "forced_replay": [t.get("index") for t in forced_rows],
                "selected": p2["selected"],
                "schedule": p2.get("schedule"),
                "retrieval_hit": {"hit": hit_n, "total": len(this_round_traces),
                                  "rate": round(hit_n / len(this_round_traces), 4) if this_round_traces else 0.0},
                "zero_hit_compensations": p2.get("zero_hit_compensations", 0),
                "positive_candidates": p2["positive_candidates"],
                "negative_candidates": p2["negative_candidates"],
                "ledger_entries": p2["ledger_entries"],
                "pool_size": len(self.experience_pool),
                # 看板：本轮分项通过率（分母=本轮样本数）+ ABCD + 逐任务末态
                "pass_rates": stats,
                "repair_rounds": _repair_round_stats(this_round_traces),
                "tree_before": tree_before_round,
                "tree_after": tree_after_round,
                "gated": len(p3["gate_records"]),
                "audited": p3.get("audited", 0),
                "promoted": promoted,
                "merged": p3["merged"],
                "pruned": p3["pruned"],
                "tree_nodes": sum(len(f.invariants) for f in self.tree.all_families()),
            })
            self.progress(f"[轮{rnd}] 完成：选中 {p2['selected']}，审计 {p3.get('audited', 0)} 条经验，"
                          f"晋升 {promoted}，归并 {p3['merged']}，树 {rounds_log[-1]['tree_nodes']} 节点")
            # 看板：每轮结束写一次树快照（画成长轨迹）
            if on_round_end:
                on_round_end(rnd, self.tree, rounds_log[-1])

        # 全局汇总：所有轮次的合计（分母=所有有验证证据的轨迹）
        all_traces = [t for rt in round_traces for t in rt]
        return {
            "rounds": rounds_log,
            "gate_records": all_gate_records,
            "audit_detail": all_audit_detail,
            "traces": [t.to_dict() for t in self.traces],
            "overall_pass_rates": _round_stats(all_traces),
            "tree_before": tree_before,
            "tree_after": _tree_counts(self.tree),
        }

    # ---------- 冻结与最终评测（Phase 3 收尾） ----------

    def freeze_tree(self) -> list[dict]:
        """冻结当前经验树为 M*：导出全部经验池条目（含 active/provisional 等所有状态）。

        按用户拍板，冻结范围包含**全部经验池条目**，不只 active——用于最终评测时
        检验"整池经验"注入的真实效果。冻结只做快照，不再改动经验库。
        """
        return [n.to_dict() for n in self.experience_pool]

    def final_evaluate(
        self,
        eval_pool: list[dict],
        *,
        on_item: Callable[[dict], None] | None = None,
        use_frozen_only: bool = True,
        prompt_profile=None,
    ) -> dict:
        """最终评测：把固化经验树在审计池上**全量**跑��遍，测真实效果。

        与 phase3_audit 的区别（重要）：
          - phase3_audit 是"逐条经验的门控审计"（抽样、算 ΔJointPass 决定去留）；
          - final_evaluate 是"固化后的整体评测"（不决定去留，只测 M* 的端到端表现）。
        流程：对 eval_pool 中每个任务 → 用当前树检索注入 → 四步生成 → 功能/安全动态测试
              → 四态判定；汇总分 CWE 的 JointPass 与 ABCD 分布，并保留失败案例。
        """
        self.cost.set_stage("final_eval")
        retriever = HskTreeRetriever(self.tree, requester=self.req_score, ablation=self.ablation,
                                         min_llm_score=self.min_llm_score,
                                         cross_cwe_min_score=self.cross_cwe_min_score,
                                         antioverdefense_bonus=self.antioverdefense_bonus,
                                         same_task_bonus=self.same_task_bonus,
                                         retrieval_mode=self.retrieval_mode, embedding_client=self.embedding_client)
        rows: list[dict] = []
        counter = {"n": 0}

        def one(row: dict) -> dict:
            self.cost.set_stage("final_eval")
            task = row.get("task_description") or {}
            query = {**task, "CWE_ID": str(row.get("CWE_ID", "")), "language": "python",
                     # 【必须带 task_id】（缺陷 D34）：_same_task_bonus 读的就是它，
                     # 缺了它同任务经验加权恒为 0（实测 152 次命中里优先机制全失效）。
                     "task_id": row.get("index")}
            cards = [] if self.context_pipeline else retriever.search(query, limit=3,
                                         pool_nodes=self.experience_pool) or []
            pipeline = run_pipeline(task, cards, requester=self.req_gen, reference_code="",
                                        anti_overdefense=self._anti_od,
                                        contract_freeze=self._contract_freeze,
                                        context_mode=self.context_pipeline,
                                        prompt_profile=prompt_profile,
                                        cards_provider=(lambda q: retriever.search({**query, **q}, limit=3,
                                            pool_nodes=self.experience_pool)) if self.context_pipeline else None)
            cards = pipeline.get("cards", cards)
            code = (pipeline.get("code") or "").strip()
            out: dict[str, Any] = {
                "task_id": row.get("index"), "cwe": str(row.get("CWE_ID", "")),
                "retrieved_ids": [c.get("invariant_id") for c in cards],
                'retrieved_cards': pipeline.get('retrieved_cards', cards),
                'injected_cards': cards,
                'adoption': pipeline.get('adoption', {}),
                'retrieval_trace': retriever.last_hier_trace,
                'pipeline_error': pipeline.get('error_type'),
                'workflow_completed': pipeline.get('workflow_completed'),
                'stages': pipeline.get('stages', []),
                "state": "", "functional": "", "security": "",
                "code": code, "error": "",
            }
            if not code:
                out["state"] = "D"
                out["error"] = pipeline.get("error_type") or "empty_code"
                return out
            ev, label = validate_and_state(row, code, timeout=self.timeout)
            out["state"] = label
            out["functional"] = (ev.get("functional") or {}).get("status", "")
            out["security"] = (ev.get("security") or {}).get("status", "")
            return out

        def done(out: dict) -> None:
            rows.append(out)
            counter["n"] += 1
            if on_item:
                on_item(out)
            self.progress(f"[FinalEval {counter['n']}/{len(eval_pool)}] task={out.get('task_id')} "
                          f"CWE-{out.get('cwe')} state={out.get('state')}")

        self._map(one, eval_pool, on_done=done)

        # 汇总：总体 + 分 CWE 的 JointPass 与 ABCD
        from collections import Counter as _Counter, defaultdict as _dd
        total = len(rows)
        joint = sum(1 for r in rows if r.get("state") == "A")
        abcd = _Counter(r.get("state") or "?" for r in rows)
        by_cwe: dict[str, dict] = _dd(lambda: {"total": 0, "joint": 0, "abcd": _Counter()})
        failures: list[dict] = []
        for r in rows:
            c = str(r.get("cwe"))
            by_cwe[c]["total"] += 1
            by_cwe[c]["abcd"][r.get("state") or "?"] += 1
            if r.get("state") == "A":
                by_cwe[c]["joint"] += 1
            else:
                failures.append(r)
        summary = {
            "eval_pool_size": total,
            "joint_pass": joint,
            "joint_pass_rate": round(joint / total, 4) if total else 0.0,
            "abcd": dict(abcd),
            "by_cwe": {c: {"total": v["total"], "joint": v["joint"],
                           "joint_pass_rate": round(v["joint"] / v["total"], 4) if v["total"] else 0.0,
                           "abcd": dict(v["abcd"])}
                       for c, v in sorted(by_cwe.items())},
            "failures": failures[:200],
            "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        return {"rows": rows, "summary": summary}

    def _run_rollout(
        self,
        row: dict,
        retriever: "HskTreeRetriever | None",
        *,
        repairs: int = 1,
        seed_card: dict | None = None,
        round_index: int = 1,
        phase: str = "phase2",
    ) -> RolloutTrace:
        """单任务多轮 rollout：四步生成 → 验证四态 → 失败后有限修复。

        retriever=None 时（Phase1 冷启动场景）不检索经验，只把 seed_card（若给出）
        作为唯一注入经验，用于从零生成自验证。
        落盘审计信息：每轮检索到的经验 id/LLM 分（retrieved_per_round）、修复轮的
        局部代码差分（patch_diffs）、四步 Agent 上下文（agent_context）。
        """
        task = row.get("task_description") or {}
        query = {**task, "CWE_ID": row.get("CWE_ID"), "language": "python",
                     "task_id": row.get("index")}   # D34：同任务加权必需
        states: list[str] = []
        codes: list[str] = []
        evidence_list: list[dict] = []
        retrieved_per_round: list[list[dict]] = []
        patch_diffs: list[str] = []
        agent_context: list[dict] = []
        reference = ""
        # 【证据回流】（缺陷 D32，2026-09-21 用真实产物定位）
        # 修复轮原先只拿到 reference（上一版代码），**不知道上一轮为什么失败**。
        # 实测（ab_verify2_20260921 的 20 个 Phase1 任务）：
        #   20 条首轮证据全部含具体报错详情，但 18 条修复轮上下文里 18 条检索到 0 条经验；
        #   状态迁移 D→D 5 / B→B 4 / C→C 7 / B→D 1 / C→D 1 —— 16/18 原地不动、
        #   2 条恶化、**0 条转正**（面板：第一次 10% → 迭代后 0%）。
        # 修法：把上一轮的 evidence 逐轮传给流水线，注入 Analysis 与 Planning。
        prev_evidence: dict | None = None
        # 【方案 A】记录哪些轮次已在 rollout 内即时提炼过（供收尾提炼跳过）
        inline_done: list[int] = []
        internal_suite = None
        for round_i in range(repairs + 1):
            # 【首轮 vs 修复轮的注入来源】（方案 A 修正，2026-09-22）
            # 实测问题：原实现在 Phase1 传 retriever=None，于是修复轮 cards 恒为空——
            # 即便方案 A 已经把"自己上一轮的失败经验"即时提炼入池，Phase1 也没有
            # 检索入口（实测 scheme_a_verify：14 条修复轮全部检索到 0 条）。
            # 修正后的语义：
            #   · 首轮（无 reference）且给了 seed_card → 只用 seed 卡，
            #     保持 Phase1"冷启动不依赖经验库"的原设计；
            #   · 修复轮（有 reference）→ 检索经验库，其中就包含上一轮即时提炼的
            #     同任务失败经验（这是方案 A 的目标）。
            if seed_card and not reference:
                cards = [seed_card]
            elif retriever is not None and not self.context_pipeline:
                # 快照读：经验池会被 worker 线程写入，复制一份避免并发读到半更新状态
                with self._pool_lock:
                    _pool_snap = list(self.experience_pool)
                cards = retriever.search(query, limit=3, pool_nodes=_pool_snap) or []
            else:
                cards = []
            def contextual_cards(q):
                # 训练侧初析后读取池快照；Phase1首轮只使用seed，修复轮检索当前失败经验。
                if seed_card and not reference:
                    return [seed_card]
                if retriever is None:
                    return []
                with self._pool_lock:
                    pool_snapshot = list(self.experience_pool)
                return retriever.search({**query, **q}, limit=3, pool_nodes=pool_snapshot) or []
            pipeline = run_pipeline(task, cards, requester=self.req_gen, reference_code=reference,
                                        anti_overdefense=self._anti_od,
                                        contract_freeze=self._contract_freeze,
                                        # 默认 None：走"经验库 + 检索"路线（用户拍板）
                                        previous_evidence=(prev_evidence
                                                           if self.inject_prev_evidence
                                                           else None),
                                        context_mode=self.context_pipeline,
                                        cards_provider=contextual_cards if self.context_pipeline else None)
            cards = pipeline.get("cards", cards)
            retrieved_per_round.append([
                {"invariant_id": c.get("invariant_id"), "llm_score": c.get("_llm_score"),
                 "base_score": c.get("_base_score"), "utility": c.get("utility"), "kind": c.get("kind")}
                for c in pipeline.get('retrieved_cards', cards)
            ])
            code = (pipeline.get("code") or "").strip()
            patch_diffs.append(pipeline.get("patch_diff") or "")
            # 记录前向四步 Agent 的完整交互上下文（供 Distillation 做细粒度归因）
            agent_context.append({
                "analysis": pipeline.get("analysis_parsed") or {},
                "initial_analysis": pipeline.get("initial_analysis") or {},
                "stages": pipeline.get("stages") or [],
                "pipeline_error": pipeline.get("error_type"),
                "workflow_completed": pipeline.get("workflow_completed"),
                "plan": pipeline.get("plan_parsed") or {},
                # 训练蒸馏需看到原卡的适用/排除条件与具体修法，不能只剩抽象准则。
                "retrieved_cards": [dict(c) for c in pipeline.get('retrieved_cards', cards)],
                "injected_cards": [dict(c) for c in cards],
                "adoption": pipeline.get('adoption', {}),
                "experience_analysis": pipeline.get('experience_analysis', {}),
                "retrieval_trace": getattr(retriever, 'last_hier_trace', {}) if retriever else {},
                "patch_diff": pipeline.get("patch_diff") or "",
            })
            if not code:
                states.append("D"); codes.append(""); evidence_list.append({"error": "empty_code"}); break
            evidence, label = validate_and_state(row, code, timeout=self.timeout)
            if self.internal_checks:
                from .internal_checks import propose_checks, execute_checks
                if internal_suite is None:
                    # 只用首次公开契约分析生成测试，不把训练/官方测试反馈输入测试设计器。
                    internal_suite = propose_checks(task, pipeline.get("initial_analysis") or {}, self.req_gen)
                entry_point = str(task.get("entry_point") or task.get("function_name") or "")
                internal_result = execute_checks(code, entry_point, internal_suite, backend="local", timeout=10)
                evidence["internal_checks"] = internal_result
                agent_context[-1]["internal_suite"] = internal_suite
            states.append(label); codes.append(code); evidence_list.append(evidence)
            if label == "A":
                break
            reference = code
            from .context_pipeline import safe_feedback
            prev_evidence = safe_feedback(evidence, evidence.get('internal_checks'))
            # 【方案 A】还有下一轮修复时，先把本轮失败**立刻**提炼入池，
            # 让下一轮的检索能命中"这个任务自己刚才失败"提炼出的经验。
            # 已提炼的轮次记入 inline_done，收尾的 distill_trace 会跳过它们以免重复。
            if round_i < repairs:
                _n = self._distill_round_inline(
                    row=row, states=states, codes=codes, evidence_list=evidence_list,
                    agent_contexts=agent_context,
                    retrieved_per_round=retrieved_per_round,
                    round_index=round_i, phase=phase)
                if _n > 0:
                    inline_done.append(round_i)
        transitions = [
            Transition(before=states[i], after=states[i + 1], kind=classify_transition(states[i], states[i + 1]))
            for i in range(len(states) - 1)
        ]
        return RolloutTrace(
            task_id=str(row.get("index")), cwe=str(row.get("CWE_ID", "")),
            family_id=str(row.get("family_id", "")), language="python", round=round_index,
            states=states, transitions=transitions, generated_codes=codes, evidence=evidence_list,
            retrieved_per_round=retrieved_per_round, patch_diffs=patch_diffs,
            agent_context=agent_context,
            # 任务契约：提炼 agent 用它判断"是否引入了契约外的多余约束"
            task_contract=json.dumps(row.get("task_description") or {},
                                     ensure_ascii=False),
            # 【方案 A】已在 rollout 内即时提炼过的轮次（收尾提炼要跳过，避免重复）
            inline_distilled_rounds=list(inline_done),
        )

    # ---------- Phase 3：门控 + 拓扑 ----------

    def _joint_pass_rate(self, rows: list[dict], cards_provider, *, samples: int = 1) -> tuple[float, list[bool]]:
        """在给定任务上跑生成+验证，返回联合通过率与逐任务结果。

        cards_provider(task) -> 注入给 Planning/CodeGen 的经验卡列表。
        samples>1 时每条任务重复采样，用多数决判该任务是否通过（Gate3 降噪）。

        【异常隔离】每个任务独立 try/except：单条任务的 LLM 失败（如重试耗尽的
        TimeoutError）只把该条记为"未通过"，**不得中断整轮门控**。
        事故依据（2026-09-20 16:11）：本函数原先没有 try/except，一次
        `TimeoutError: The read operation timed out` 直接冒泡到 run_evolution_rounds，
        把已跑 8 小时的整条全量运行标记为 failed。
        """
        flags: list[bool] = []
        for row in rows:
            task = row.get("task_description") or {}
            query = {**task, "CWE_ID": row.get("CWE_ID"), "language": "python",
                     "task_id": row.get("index")}   # D34：同任务加权必需
            sample_flags: list[bool] = []
            for _ in range(max(1, samples)):
                try:
                    cards = [] if self.context_pipeline else cards_provider(query)
                    pipeline = run_pipeline(task, cards, requester=self.req_gen, reference_code="",
                                            anti_overdefense=self._anti_od,
                                            contract_freeze=self._contract_freeze,
                                            context_mode=self.context_pipeline,
                                            cards_provider=(lambda q: cards_provider({**query, **q}))
                                            if self.context_pipeline else None)
                    code = (pipeline.get("code") or "").strip()
                    if self.retrieval_mode == 'semantic_llm' and pipeline.get('error_type'):
                        raise RuntimeError('unmeasured_gate_pipeline:' + pipeline['error_type'])
                    if not code:
                        sample_flags.append(False)
                        continue
                    evidence, label = validate_and_state(row, code, timeout=self.timeout)
                    if self.retrieval_mode == 'semantic_llm':
                        from .global_gate import evidence_is_measured
                        if not evidence_is_measured(evidence):
                            raise RuntimeError('unmeasured_gate_validation')
                    sample_flags.append(label == "A")
                except Exception:
                    if self.retrieval_mode == 'semantic_llm':
                        raise
                    # 该次采样失败 → 视为未通过（保守），但不影响其它任务
                    sample_flags.append(False)
            flags.append(majority_vote(sample_flags) if samples > 1 else sample_flags[0])
        rate = (sum(1 for f in flags if f) / len(flags)) if flags else 0.0
        return rate, flags

    def _regression_probe(self, rows: list[dict], cards_provider,
                          *, samples: int = 3) -> tuple[int, int]:
        """在历史 H_pass 任务上重跑候选经验，**按维度**统计回归（安全 / 功能）。

        所属阶段：Phase3 Gate3（降噪回归）—— 这是"有害经验"的专用检测通道。
        输入：H_pass 任务行（**必须含 task_description**）、经验卡提供器、采样次数。
        输出：(security_regressions, functional_regressions)。
        验证证据：每次采样都真实执行生成 + 本地功能/安全验证，读 evidence 的分维度
            状态（functional / security），不用模型自评。
        失败类型：单次采样抛异常或产出空代码 → 该次两个维度都记为"失败"（保守），
            但不中断其它任务；状态为 unmeasured 的维度**不记为失败**（不伪造证据）。
        允许修改长期经验库：否——只产生回归计数。

        为什么不能复用 `_joint_pass_rate`（缺陷 D20，2026-09-21 实测）：
          `_joint_pass_rate` 的 flags 是 **joint**（`label == "A"`），而审计侧把
          `sum(1 for f in flags if not f)` 记成 `security_regressions`、
          并把 `functional_regressions` **硬编码为 0**。后果有两个：
            · 功能回归通道恒为 0 → **"过度防御"永远测不出来**，
              而过度防御占实测失败的 47.3%，是用户最关心的问题；
            · 过度防御（安全过、功能败）被错记成"安全回归"，归因错位。
          本函数按维度分别统计，使功能回归通道真正可用。
        """
        def _one_sample(row: dict) -> tuple[bool, bool]:
            """跑一次采样，返回 (安全测试失败?, 功能测试失败?)。

            只有明确的 "fail" 才算回归；"unmeasured" 不记为失败（不伪造证据）。
            单次采样异常 → 两维都记为失败（保守），但不中断其它采样。
            """
            task = row.get("task_description") or {}
            query = {**task, "CWE_ID": row.get("CWE_ID"), "language": "python",
                     "task_id": row.get("index")}   # D34：同任务加权必需
            try:
                cards = [] if self.context_pipeline else cards_provider(query)
                pipeline = run_pipeline(task, cards, requester=self.req_gen,
                                        reference_code="",
                                        anti_overdefense=self._anti_od,
                                        contract_freeze=self._contract_freeze,
                                        context_mode=self.context_pipeline,
                                        cards_provider=(lambda q: cards_provider({**query, **q}))
                                        if self.context_pipeline else None)
                code = (pipeline.get("code") or "").strip()
                if self.retrieval_mode == 'semantic_llm' and pipeline.get('error_type'):
                    raise RuntimeError('unmeasured_regression_pipeline:' + pipeline['error_type'])
                if not code:
                    return True, True
                evidence, _ = validate_and_state(row, code, timeout=self.timeout)
                if self.retrieval_mode == 'semantic_llm':
                    from .global_gate import evidence_is_measured
                    if not evidence_is_measured(evidence):
                        raise RuntimeError('unmeasured_regression_validation')
                return (_ev_status(evidence, "security") == "fail",
                        _ev_status(evidence, "functional") == "fail")
            except Exception:
                if self.retrieval_mode == 'semantic_llm':
                    raise
                return True, True

        # 【必须并行】（缺陷 D37，2026-09-22 卡死事故的直接成因）
        # 原实现是 `for row: for sample:` 的**双层串行**：每个候选要跑
        #   H_pass任务数 × samples(3) × 四步流水线(4 次调用)
        # 次串行 LLM 调用 —— 5 个任务就是 60 次，每次 ~5 秒 → 单候选约 5 分钟；
        # 一旦遇到服务端挂包（每次 attempt 卡满 90 秒硬超时），单候选会退化到**几小时**，
        # 整条运行表现为"日志静默、CPU 归零"的假死。
        # 这些 (任务, 采样) 组合彼此完全独立，并行后由 requester 的全局在途闸门兜住总并发。
        n_samples = max(1, samples)
        jobs = [row for row in rows for _ in range(n_samples)]
        if len(jobs) <= 1:
            flat = [_one_sample(j) for j in jobs]
        else:
            with ThreadPoolExecutor(max_workers=min(len(jobs), REGRESSION_WORKERS)) as _ex:
                flat = list(_ex.map(_one_sample, jobs))

        # 按行聚合（多数决降噪：多数采样出现该维度失败才记一次回归）
        sec_reg = 0
        func_reg = 0
        i = 0
        for _row in rows:
            chunk = flat[i:i + n_samples]
            i += n_samples
            if majority_vote([c[0] for c in chunk]):
                sec_reg += 1
            if majority_vote([c[1] for c in chunk]):
                func_reg += 1
        return sec_reg, func_reg

    def phase3_audit(
        self,
        audit_tasks: list[dict],
        *,
        tau_sec: int = 1,
        tau_func: int = 0,
        audit_per_candidate: int = 5,
        regression_samples: int = 3,
        hpass_traces: list[dict] | None = None,
        entries: list[SecurityInvariantNode] | None = None,
        fallback_tasks: list[dict] | None = None,
        max_entries: int = 0,
        consolidate_max_active: int = 3,
        min_audit_tasks: int = 3,
        on_audit: Callable[[dict], None] | None = None,
    ) -> dict:
        """Phase 3：对【统一经验池】做三层门控 → supported 入树 → 归并/剪枝。

        架构归一化：本阶段不区分经验来自 Phase1 还是 Phase2——entries 默认取整个
        经验池（含 Phase1 成功/失败提炼的经验与 Phase2 重放产出的经验），一律走同一套
        Gate1/2/3 判定。因此 Phase1 的经验不再享有"直接入树"的特权。

        真实实现：
          Gate1 召回探针：把候选临时并入检索范围，用真实 audit 任务检验能否召回 Top-3；
          Gate2 独立有效性：在同 CWE 的 audit 任务上做「基线 vs 加入候选」两次生成+验证，
            真实计算 ΔJointPass = JointPass(加候选) − JointPass(基线)；
          Gate3 降噪回归：对历史 H_pass 任务用 N=3 采样多数决重跑，统计安全/功能回归。
        """
        self.cost.set_stage("phase3")
        retriever = HskTreeRetriever(self.tree, requester=None, ablation=self.ablation,
                                    retrieval_mode=("hier_rule"
                                                    if self.retrieval_mode in ("hier_llm", "hier_rule")
                                                    else "flat_rule"))
        if self.retrieval_mode == 'semantic_llm':
            # Gate1召回探针与Gate2/3基线使用部署检索，不能用旧词面规则冒充向量召回。
            retriever = HskTreeRetriever(self.tree, requester=self.req_score, ablation=self.ablation,
                retrieval_mode='semantic_llm', embedding_client=self.embedding_client)
        records: list[dict] = []
        audit_detail: list[dict] = []
        targets = entries if entries is not None else self.experience_pool
        # 只审计【尚未处理】的经验：所有 provisional 条目一律平等对待（不分 Phase1/Phase2），
        # 已判定过的条目状态会变成 active/revised/demoted/unmeasured，不再重复审计。
        targets = [e for e in targets if e.status == "provisional"]

        # 按 CWE 分组 audit 任务；D_audit 无该 CWE 时回退到 replay 任务（并标注来源）
        by_cwe: dict[str, list[dict]] = {}
        for row in audit_tasks:
            by_cwe.setdefault(str(row.get("CWE_ID")), []).append(row)
        fallback_by_cwe: dict[str, list[dict]] = {}
        for row in (fallback_tasks or []):
            fallback_by_cwe.setdefault(str(row.get("CWE_ID")), []).append(row)

        # ---- 审计成本压缩：按信息价值抽样，只审重点经验 ----
        # 优先级：①有 D_audit 覆盖的 CWE（可测 Δ）②正例经验（可直接指导生成）
        # ③CWE 去重（扩大覆盖面，避免同一 CWE 反复占用预算）
        def _value(n: SecurityInvariantNode) -> tuple:
            has_audit = 1 if by_cwe.get(str(n.cwe)) else 0
            has_fallback = 1 if fallback_by_cwe.get(str(n.cwe)) else 0
            kind = str((n.source or {}).get("kind", ""))
            is_positive = 1 if kind in ("direct_A", "B_to_A", "C_to_A", "D_to_A", "seed_from_diff") else 0
            has_positive_text = 1 if (n.positive_principle or "").strip() else 0
            return (has_audit, has_fallback, is_positive, has_positive_text, n.utility)

        targets = sorted(targets, key=_value, reverse=True)
        if max_entries and len(targets) > max_entries:
            # 名额分配（含"纯负向经验保底"）抽到 select_audit_targets，便于单测锁定。
            picked, neg_budget = select_audit_targets(targets, max_entries=max_entries)
            picked_ids = {id(n) for n in picked}
            deferred = [n for n in targets if id(n) not in picked_ids]
            self.progress(
                f"[Phase3] 审计抽样：{len(picked)}/{len(targets)} 条"
                f"（其中纯负向/失败现场 {sum(1 for x in picked if _is_negative_only(x))} 条，"
                f"保底配额 {neg_budget}）；其余 {len(deferred)} 条留待后续轮次")
            targets = picked

        # 【门控 LLM 任务选择器】让 LLM 为每条待审经验挑最合适的审计任务。
        # 替换原先 by_cwe[:N] 的硬取：那种取法只按数组顺序截断，不考虑检验价值，
        # 也无法覆盖较多经验。用户拍板：自由决定条数、允许跨 CWE（验证泛化）。
        all_audit_tasks = list(audit_tasks) + list(fallback_tasks or [])
        # 【基线可测性筛选】先剔除基线通过率为 0/1 的任务，否则 ΔJointPass 恒为 0、
        # 门控完全没有区分度（实测 F2 组 8 条经验全 Δ=0，根因是 7/8 任务基线为 0）。
        baseline_info: dict = {}
        if targets and all_audit_tasks and max_entries:
            from .gate_selector import filter_measurable_tasks

            all_audit_tasks, baseline_info = filter_measurable_tasks(
                all_audit_tasks,
                lambda rows, s: self._joint_pass_rate(
                    rows, lambda q: retriever.search(q, limit=3), samples=s),
                max_probe=min(len(all_audit_tasks), max(8, audit_per_candidate * 4)),
                # 探测并行度：与 Phase3 并发一致（原实现串行，约 500 秒/轮）
                workers=max(1, self.phase3_workers),
            )
            # 无论是否筛出结果都要留痕：静默 fallback 会掩盖"筛选没生效"这一事实。
            # 实测教训：小规模运行里 measurable=0 → 旧代码不打印任何日志，
            # 单看日志无法分辨"没跑筛选"与"跑了但全不可测"。
            self.progress(
                f"[Phase3] 基线可测性标注：探测 {baseline_info.get('probed', 0)} 个"
                f"（覆盖 {baseline_info.get('cwe_probed', 0)} 个 CWE）→ 正负皆可测 "
                f"{baseline_info.get('measurable', 0)}，仅可测增益 "
                f"{baseline_info.get('gain_only', 0)}，仅可测有害 "
                f"{baseline_info.get('ceiling', 0)}，探测失败 "
                f"{baseline_info.get('probe_failed', 0)}；"
                f"全部 {baseline_info.get('kept', 0)} 条保留，仅按可测范围排序")
        selector_info: dict = {}
        if targets and all_audit_tasks:
            from .gate_selector import select_audit_tasks

            selector_info = select_audit_tasks(
                targets, all_audit_tasks, self.req_gate_select,
                mode=self.gate_select_mode,
                fixed_per_entry=self.gate_fixed_examples,
                fallback_per_entry=max(1, audit_per_candidate),
            )
            self.progress(f"[Phase3] LLM 选择器：为 {len(targets)} 条经验规划了 "
                          f"{selector_info.get('total_tasks')} 个审计任务"
                          f"（覆盖 {len(selector_info.get('plan') or {})} 条经验，"
                          f"兜底={selector_info.get('fallback_used')}，"
                          f"error={selector_info.get('error')}）")
        plan_map = selector_info.get("plan") or {}

        # 【Phase3 并发】原先这里是对 targets 的串行 for 循环—���这是全流程最慢的一步：
        # 每条经验要跑（基线 + 加候选）两轮完整生成，实测 24 条要 105 分钟。
        # 现改为按 phase3_workers 并发（默认 8）。
        # 线程安全说明：_audit_one 内部只读共享树/检索器，不写树与池；
        # 所有状态写入（status/absorb_or_new/records 收集）都在本函数主线程收尾时做。
        _idx = {id(c): i for i, c in enumerate(targets)}
        outcomes: dict[str, dict] = {}

        def _run_one(cand: SecurityInvariantNode) -> dict:
            return self._audit_one(
                cand, plan_map=plan_map, by_cwe=by_cwe, fallback_by_cwe=fallback_by_cwe,
                audit_per_candidate=audit_per_candidate, retriever=retriever,
                hpass_traces=hpass_traces, regression_samples=regression_samples,
                tau_sec=tau_sec, tau_func=tau_func, selector_info=selector_info,
                entry_index=_idx.get(id(cand), 0),
                min_audit_tasks=min_audit_tasks,
                audit_pool_all=all_audit_tasks,
            )

        def record_finished(res):
            """Phase3 消费线程逐条保存动态审计证据；写入失败向上传播，不提前修改库。"""
            if not res or not res.get("candidate_id"):
                raise RuntimeError("phase3_audit_missing_candidate_result")
            outcomes[res["candidate_id"]] = res
            if on_audit:
                on_audit(res["detail"])
            self.progress(f"[Phase3 {len(outcomes)}/{len(targets)}] "
                          f"candidate={res['candidate_id']} decision={res['rec'].get('decision')}")

        self.progress(f"[Phase3] 并发审计 {len(targets)} 条经验"
                      f"（phase3_workers={self.phase3_workers}）")
        self._map(_run_one, targets, workers=self.phase3_workers, on_done=record_finished)

        # ---- 主线程串行收尾：写明细、写终态、入树 ----
        for cand in targets:
            res = outcomes.get(cand.invariant_id)
            if res is None:
                continue          # 该条审计失败（异常已在 _audit_one 内兜住）
            # audit_source 已在 _audit_one 内写进 detail，这里无需再解包（原先解了但没用）
            detail, rec = res["detail"], res["rec"]
            records.append(rec)
            audit_detail.append(detail)
            if rec.get("decision") == "supported":
                cand.status = "active"
                family = self.tree.ensure_family(cand.cwe)
                absorb_or_new(family, cand)
            elif rec.get("decision") == "demoted":
                cand.status = "retired"
            elif rec.get("decision") == "unmeasured":
                cand.status = "unmeasured"
            else:
                cand.status = "revised"

        # ---- 归并 / 剪枝（并发段之后，主线程串行执行）----
        merged = 0
        for fam in self.tree.all_families():
            if consolidate_family(fam, consolidator=self._llm_consolidate,
                                  max_active=consolidate_max_active) is not None:
                merged += 1
        pruned = sum(prune_by_utility(fam) for fam in self.tree.all_families())
        promoted = sum(1 for r in records if r.get("decision") == "supported")
        absorbed = getattr(self, "absorb_count", 0)
        self.progress(f"[Phase3] 审计 {len(targets)} 条经验（晋升 {promoted}），"
                      f"归并 {merged}，剪枝 {pruned}，累计池内去重吸收 {absorbed} 条")
        return {"gate_records": records, "audit_detail": audit_detail,
                "merged": merged, "pruned": pruned, "audited": len(targets),
                "promoted": promoted, "absorbed": absorbed}

    def _audit_one(
        self,
        cand: SecurityInvariantNode,
        *,
        plan_map: dict,
        by_cwe: dict,
        fallback_by_cwe: dict,
        audit_per_candidate: int,
        retriever,
        hpass_traces: list[dict] | None,
        regression_samples: int,
        tau_sec: int,
        tau_func: int,
        selector_info: dict,
        entry_index: int,
        min_audit_tasks: int = 0,
        audit_pool_all: list[dict] | None = None,
    ) -> dict:
        """审计**单条**候选经验（Phase3 的并发工作单元）。

        所属阶段：Phase3 独立有效性门控。
        输入：一条待审经验 + 已规划好的审计任务映射 + 检索器。
        输出：{"candidate_id", "detail", "rec", "audit_source"}；
              rec 是 GateRecord 的 dict 形式（供主线程写终态）。
        使用的验证证据：真实动态测试的 JointPass（基线 vs 加候选）与
              H_pass 回归；Gate1 用真实 audit 任务做召回探针。
        可能的失败类型：无可用审计任务 → decision=unmeasured（不谎称 revised）；
              内部异常 → 本方法兜住并返回 decision=revised 的记录，不中断整批。
        是否允许修改长期经验库：**否** —— 本方法只读树与检索器，
              所有状态写入由 phase3_audit 主线程串行完成（避免并发写冲突）。
        """
        picked = plan_map.get(cand.invariant_id)
        if picked:
            same_cwe = picked[:audit_per_candidate] if audit_per_candidate else picked
            audit_source = "llm_selected"
        else:
            same_cwe = by_cwe.get(str(cand.cwe), [])[:audit_per_candidate]
            audit_source = "D_audit"
            if not same_cwe:
                # D_audit 无该 CWE 任务时回退到 replay 池（独立性略降，但避免"必然被拒"）
                same_cwe = fallback_by_cwe.get(str(cand.cwe), [])[:audit_per_candidate]
                audit_source = "D_replay" if same_cwe else "none"
        # 【最少审计任务数】用户要求增加被挑选的例子数量（问题2）。
        # 实测小规模下 21/36 条经验只用了 1 个审计任务、7 条用了 0 个——
        # "仅 1 个任务上 Δ=0"不足以判定经验无效，证据太单薄。
        # 补足顺序：同 CWE 候选 → 其它 CWE（跨 CWE 可检验泛化迁移）。
        if min_audit_tasks > 0 and len(same_cwe) < min_audit_tasks:
            have = {int(r.get("index", -1)) for r in same_cwe}
            extra_pool = list(by_cwe.get(str(cand.cwe), [])) + list(audit_pool_all or [])
            for extra in extra_pool:
                if len(same_cwe) >= min_audit_tasks:
                    break
                eid = int(extra.get("index", -1))
                if eid in have:
                    continue
                have.add(eid)
                same_cwe.append(extra)
            if same_cwe and audit_source == "none":
                audit_source = "D_audit_min"
        cross_n = sum(1 for r in same_cwe if str(r.get("CWE_ID")) != str(cand.cwe))
        detail: dict[str, Any] = {
            "candidate_id": cand.invariant_id, "cwe": cand.cwe,
            "source_stage": (cand.source or {}).get("stage", ""),
            "source_kind": (cand.source or {}).get("kind", ""),
            "audit_source": audit_source,
            "audit_task_count": len(same_cwe), "delta_joint_pass": 0.0,
            "baseline_pass": None, "with_candidate_pass": None,
            "gate1_probe_task": None, "gate1_retrieved": False,
            "security_regressions": 0, "functional_regressions": 0,
            # 【缺测计数必须落到 detail 并传给门控】（缺陷 D21 配套）：
            # 原先 detail 里没有这个键，Gate3 的 hpass_missing 永远是 0，
            # "拿不到任务描述就跑回归"这件事既没被记录、也没能阻止晋升。
            "hpass_missing": 0,
            # 看板：门控具体选了哪些任务（含是否跨 CWE）
            "selected_tasks": [
                {"task_id": r.get("index"), "cwe": str(r.get("CWE_ID")),
                 "cross_cwe": str(r.get("CWE_ID")) != str(cand.cwe)}
                for r in same_cwe
            ],
            "cross_cwe_count": cross_n,
            "selector_reason": (selector_info.get("reasons") or {}).get(
                f"E{entry_index}", ""),
        }

        try:
            # ---- Gate1：用真实 audit 任务做召回探针（候选临时并入检索范围）----
            if same_cwe:
                probe_row = same_cwe[0]
                probe_task = {**(probe_row.get('task_description') or {}),
                    "CWE_ID": str(probe_row.get("CWE_ID")),
                    "language": "python",
                    "description": str((probe_row.get("task_description") or {}).get("description", "")),
                    "security_policy": str((probe_row.get("task_description") or {}).get("security_policy", "")),
                }
                detail["gate1_probe_task"] = probe_task["description"][:80]
            else:
                probe_task = {"CWE_ID": cand.cwe, "language": "python", "description": ""}

            cand_card = {
                "invariant_id": cand.invariant_id, "cwe": cand.cwe,
                # 门控生成与部署生成使用同样的经验字段；不改变任何门控判据。
                "kind": (cand.source or {}).get("kind", ""), "status": cand.status,
                "fix_directive": (cand.source or {}).get("fix_directive", ""),
                "root_cause": (cand.source or {}).get("root_cause", ""),
                "exclusion_conditions": (cand.source or {}).get("exclusion_conditions", ""),
                "high_level_invariant": cand.high_level_invariant,
                "positive_principle": cand.positive_principle,
                "negative_guardrail": cand.negative_guardrail,
                "applicability": cand.applicability,
                "polarity": "positive",
            }

            # ---- Gate2：真实算 ΔJointPass（基线 vs 加候选）----
            if same_cwe:
                base_rate, _ = self._joint_pass_rate(
                    same_cwe, lambda q: retriever.search(q, limit=3), samples=1)
                with_rate, _ = self._joint_pass_rate(
                    same_cwe, lambda q: (retriever.search(q, limit=3) or []) + [cand_card], samples=1)
                delta = with_rate - base_rate
                detail["baseline_pass"] = round(base_rate, 4)
                detail["with_candidate_pass"] = round(with_rate, 4)
                detail["delta_joint_pass"] = round(delta, 4)
            else:
                delta = 0.0

            # ---- Gate3：H_pass 回归（N=3 多数决，分维度统计）----
            # 【这是"有害经验"的专用通道】与基线可测性无关：只要候选在历史
            # 通过过的任务上造成安全失败或功能失败，就能被这条通道抓住。
            if hpass_traces:
                hp_rows = [r for r in (hpass_traces or []) if str(r.get("cwe")) == str(cand.cwe)]
                if hp_rows:
                    # 【缺描述不得当成回归】（缺陷 D21）：没有任务契约就跑不出有意义的
                    # 回归探针。按 AGENTS.md 第九节"没有执行的验证项必须记录为未测量"，
                    # 这里记 hpass_missing（会阻止晋升为 revised），而不是伪造回归证据。
                    usable = [r for r in hp_rows if (r.get("task_description") or {})]
                    detail["hpass_missing"] = len(hp_rows) - len(usable)
                    if usable:
                        sec_reg, func_reg = self._regression_probe(
                            [{"index": r.get("task_id"), "CWE_ID": r.get("cwe"),
                              "task_description": r.get("task_description") or {}}
                             for r in usable],
                            lambda q: (retriever.search(q, limit=3) or []) + [cand_card],
                            samples=regression_samples)
                        detail["security_regressions"] = sec_reg
                        # 【功能回归必须真实统计】（缺陷 D20）：原先硬编码为 0，
                        # 使"过度防御"（安全过、功能败）永远无法被识别。
                        detail["functional_regressions"] = func_reg

            rec = audit_candidate(
                cand.invariant_id, retriever, probe_task,
                delta_joint_pass=detail["delta_joint_pass"],
                security_regressions=detail["security_regressions"],
                functional_regressions=detail["functional_regressions"],
                # 缺测必须传入，否则"没有可用的 H_pass 任务"会被当成"无回归"（伪造证据）
                hpass_missing=detail.get("hpass_missing", 0),
                tau_sec=tau_sec, tau_func=tau_func,
                candidate_node=cand,
            )
            # 若彻底没有可用审查任务，ΔJointPass 无从测量 → 记 unmeasured，
            # 不能谎称 revised（revised 意味着"有证据表明无增益"）。
            if audit_source == "none":
                rec.decision = "unmeasured"
                rec.reasons = ["no_audit_task_available"]
            detail["gate1_retrieved"] = rec.gate1_retrieved
            detail["decision"] = rec.decision
            detail["reasons"] = rec.reasons
        except Exception as exc:      # 单条失败不拖垮整批
            # 向量/生成/测试基础设施缺测不能归因为候选有害，也不能据此晋升。
            detail["decision"] = "unmeasured" if self.retrieval_mode == 'semantic_llm' else "revised"
            detail["reasons"] = [f"audit_error:{type(exc).__name__}"]
            rec = GateRecord(candidate_id=cand.invariant_id, delta_joint_pass=0.0)
            rec.decision = detail['decision']
            rec.reasons = [f"audit_error:{type(exc).__name__}"]
        return {"candidate_id": cand.invariant_id, "detail": detail,
                "rec": rec.to_dict(), "audit_source": audit_source}
        # 【已删除的死代码】（缺陷 S1，2026-09-21 代码审查）
        # 此处原本残留着 phase3_audit 尾部"归并 / 剪枝 / 汇总"逻辑的副本，
        # 且引用了 consolidate_max_active / records / targets / audit_detail ——
        # 这四个名字在 _audit_one 作用域内**均未定义**（pyflakes 报 5 处 undefined name）。
        # 因为前面有 return 所以不可达，但埋着 NameError，且会误导维护者改错地方
        # （改完运行结果毫无变化且无提示）。归并/剪枝的正确实现在 phase3_audit 尾部。

    def _llm_consolidate(self, nodes: list[SecurityInvariantNode]) -> SecurityInvariantNode:
        """容量超限离线归并（LLM 提取公约数）——真实调用 AI。"""
        from .distillation import _content, _extract_json

        highlights = "; ".join(n.high_level_invariant for n in nodes)
        prompt = (
            "Consolidate overlapping security invariants into one invariant. Use English only. "
            "Preserve applicability limits and do not invent validation evidence. Return JSON only: "
            '{"high_level_invariant": "...", "positive_principle": "...", "negative_guardrail": "...", "applicability": "..."}'
            "\nInvariants:\n" + highlights
        )
        try:
            value = _extract_json(_content(self.req_consolidate(prompt)))
            from .english_policy import assert_english_experience
            assert_english_experience(value)
            merged = SecurityInvariantNode(
                invariant_id=f"merged-{nodes[0].cwe}-{abs(hash(str(value.get('high_level_invariant',''))))}",
                cwe=nodes[0].cwe,
                high_level_invariant=str(value.get("high_level_invariant", "")),
                positive_principle=str(value.get("positive_principle", "")),
                negative_guardrail=str(value.get("negative_guardrail", "")),
                applicability=str(value.get("applicability", "")),
                support_count=sum(n.support_count for n in nodes),
                regression_count=sum(n.regression_count for n in nodes),
            )
        except Exception:
            merged = SecurityInvariantNode(
                invariant_id=f"merged-{nodes[0].cwe}", cwe=nodes[0].cwe,
                high_level_invariant="；".join(n.high_level_invariant for n in nodes),
                positive_principle="；".join(n.positive_principle for n in nodes),
                support_count=sum(n.support_count for n in nodes),
                regression_count=sum(n.regression_count for n in nodes),
            )
        merged.language_leaves["python"] = LanguageLeaf("python", [], [], "")
        return merged

# -*- coding: utf-8 -*-
"""层次化自顶向下检索（Hierarchical Top-Down Retrieval，HTDR）。

所属阶段：Phase1 / Phase2 的 Retrieval 步骤（经验注入前）。
输入：当前任务契约（CWE、语言、描述）+ 候选经验节点集合（树 active ∪ 经验池）。
输出：按相关性选中的经验卡列表（0~limit 条，允许 0 条）。
使用的验证证据：本模块**不产生**任何有效性证据；它只决定"给生成流水线看哪几条经验"。
    经验是否真的有效仍由 Phase3 的三层门控（质量/独立有效性/H_pass 回归）判定。
可能的失败类型：任一层 LLM 调用失败或 JSON 解析失败 → 回退到规则排序，不中断；
    候选为空 → 返回空列表。
是否允许修改长期经验库：**否** —— 只读候选节点，不写树、不写池。

## 为什么需要它（与旧机制的对比）

旧机制（flat + 逐候选 LLM 打分）：
    1. 规则打分（TF-IDF + CWE + utility）取 top-`recall_k`（默认 8）；
    2. 对**每个候选单独**调一次 LLM 打相关性分（8 次调用）；
    3. 按分数取 top-`limit`，再过相关性门槛。

实测缺陷（cle_full_874_20260922，2413 条注入样本）：
    · LLM 打分**几乎无区分度**：均值 0.887、中位 0.900、最小 0.70，
      86.9% 的样本恰好是 0.9 —— 因为 LLM 一次只看一条经验，
      没有比较对象，天然倾向于给高分；
    · 门槛（同 CWE 0.6 / 跨 CWE 0.75）因此**筛不掉任何东西**；
    · 成本高：每次检索 8 次 LLM 调用，每个任务 2 次检索 → 16 次/任务；
      全量运行里 `retrieve.score` 是最大单项开销。

本机制：
    L1 把**整棵树的骨架**（CWE 家族索引）给 LLM 看 → 选相关家族；
    L2 在该家族内给出**经验类型索引**（kind + 语义说明 + 条数）→ 选需要的类型；
    L3 在选中的类型内给出**候选经验清单**（规则预筛 top-K）→ 选具体经验；
    每到一层，LLM 看到的是**一组可比较的选项**而不是孤立的一条，
    因此被迫做相对判断，天然产生区分度；且每层只需 1 次调用（共 3 次）。
"""

from __future__ import annotations

import json
import re
from typing import Callable

from .hsk_tree import SecurityInvariantNode
from .retriever import _node_text, utility_score

Requester = Callable[[str], dict]

# 经验类型（kind）→ 语义说明。给 LLM 做 L2 选择用：
# 说明必须写"这类经验能帮上什么忙"，而不是复述类型名。
KIND_LABELS: dict[str, str] = {
    "minimal_patch_hint": "Minimal patch: achieve security with minimal changes while preserving functionality",
    "overdefense_pitfall": "Over-defense pitfall: apparently safe changes that violate the functional contract",
    "round_0_fail": "Initial failure analysis: why the first generation failed and what to change",
    "round_1_fail": "Repair failure: why the previous attempted fix did not work",
    "C_stalled": "Repeated functional failure while security passes; the cause requires evidence",
    "D_stalled": "Repeated failures of both functionality and security",
    "B_stalled": "Repeated security failure while functionality passes",
    "B_to_C": "Functional regression after hardening: functionality changes from passing to failing",
    "direct_A": "First-attempt success: an implementation pattern that passed both checks",
    "B_to_A": "Successful security repair: from security failure to both checks passing",
    "C_to_A": "Successful functional repair: from functional failure to both checks passing",
    "D_to_A": "Successful joint repair: from both checks failing to both passing",
    "seed_from_diff": "Official patch comparison: experience extracted from vulnerable and patched code",
    "zero_hit_compensation": "Coverage compensation: no usable experience was previously available for this CWE",
}

# 每一层给 LLM 看的候选条数上限（控制提示词长度与成本）。
L3_MAX_ITEMS = 14          # L3 单个类型内最多展示多少条经验
L2_MAX_KINDS = 12          # L2 最多展示多少个类型
L1_MAX_CWES = 24           # L1 最多展示多少个 CWE 家族


def _kind_of(node: SecurityInvariantNode) -> str:
    """取节点的经验类型（kind）。缺失时归到 other，保证索引不漏项。"""
    return str((node.source or {}).get("kind") or "other")


def _kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, f"{kind} (unregistered type)")


def _short(text: str, n: int) -> str:
    """把长文本压成一行摘要，供索引展示。"""
    t = " ".join(str(text or "").split())
    return t[:n] + ("…" if len(t) > n else "")


def _call_json(requester: Requester, prompt: str) -> dict | None:
    """调一次 LLM 并解析 JSON；失败返回 None（调用方负责回退）。

    为什么单独抽出：三层结构里每层都要"调用 + 容错解析"，且三层的
    失败语义完全一致（回退到规则），集中一处便于审计。
    """
    try:
        payload = requester(prompt)
        content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        text = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
        return json.loads(fenced.group(1) if fenced else text)
    except Exception:
        return None


# ---------------------------------------------------------------- L1：CWE 家族

def build_l1_index(nodes: list[SecurityInvariantNode]) -> tuple[str, list[str]]:
    """构造 L1 索引：CWE 家族一览（含条数与类型分布）。

    返回 (索引文本, 出现的 CWE 列表)。
    为什么把类型分布也放进来：让 LLM 一眼看出"这个家族里有没有失败现场类经验"，
    而不是只知道条数。
    """
    by_cwe: dict[str, list[SecurityInvariantNode]] = {}
    for n in nodes:
        by_cwe.setdefault(str(n.cwe), []).append(n)
    lines = []
    cwes = []
    for cwe in sorted(by_cwe, key=lambda c: -len(by_cwe[c]))[:L1_MAX_CWES]:
        group = by_cwe[cwe]
        cwes.append(cwe)
        kinds = {}
        for n in group:
            kinds[_kind_of(n)] = kinds.get(_kind_of(n), 0) + 1
        top = sorted(kinds.items(), key=lambda x: -x[1])[:4]
        kind_str = ", ".join(f"{k} x {v}" for k, v in top)
        lines.append(f"- CWE-{cwe}: {len(group)} cards ({kind_str})")
    return "\n".join(lines), cwes


# ---------------------------------------------------------------- L2：经验类型

def build_l2_index(nodes: list[SecurityInvariantNode], cwes: list[str]) -> tuple[str, list[str]]:
    """构造 L2 索引：选中 CWE 家族内的经验类型一览。"""
    subset = [n for n in nodes if str(n.cwe) in set(cwes)]
    by_kind: dict[str, list[SecurityInvariantNode]] = {}
    for n in subset:
        by_kind.setdefault(_kind_of(n), []).append(n)
    kinds = sorted(by_kind, key=lambda k: -len(by_kind[k]))[:L2_MAX_KINDS]
    lines = [f"- {k} ({len(by_kind[k])} cards): {_kind_label(k)}" for k in kinds]
    return "\n".join(lines), kinds


# ---------------------------------------------------------------- L3：具体经验

def build_l3_index(nodes: list[SecurityInvariantNode], cwes: list[str],
                   kinds: list[str], *, language: str,
                   rule_score: Callable[[SecurityInvariantNode], float],
                   per_kind: int = L3_MAX_ITEMS) -> tuple[str, dict[str, SecurityInvariantNode]]:
    """构造 L3 索引：选中类型内的候选经验清单（每类规则预筛 top-K）。

    返回 (索引文本, id→节点 映射)。映射用于把 LLM 选出的 id 还原成节点。
    为什么要有预筛：一个类型在某 CWE 下可能有上百条，全部展示会撑爆提示词；
    规则分（TF-IDF + utility）只负责"缩小到可展示的规模"，
    真正的语义取舍交给 LLM——这正是分层检索的分工。
    """
    cwe_set, kind_set = set(cwes), set(kinds)
    subset = [n for n in nodes
              if str(n.cwe) in cwe_set and _kind_of(n) in kind_set
              and language in (n.language_leaves or {})]
    by_kind: dict[str, list[SecurityInvariantNode]] = {}
    for n in subset:
        by_kind.setdefault(_kind_of(n), []).append(n)

    id_map: dict[str, SecurityInvariantNode] = {}
    lines = []
    for kind in kinds:
        group = by_kind.get(kind) or []
        if not group:
            continue
        ranked = sorted(group, key=lambda n: -rule_score(n))[:per_kind]
        lines.append(f"\n[{kind}: {_kind_label(kind)}]")
        for n in ranked:
            id_map[n.invariant_id] = n
            src = n.source or {}
            extra = ""
            if src.get("root_cause"):
                extra += f" | Root cause: {_short(src.get('root_cause'), 240)}"
            if src.get("fix_directive"):
                extra += f" | Suggested fix: {_short(src.get('fix_directive'), 600)}"
            lines.append(
                f"- id={n.invariant_id} | Status={n.status} | Support={n.support_count} | Regressions={n.regression_count}"
                f" | Applicability: {n.applicability} | Exclusion conditions: {src.get('exclusion_conditions', '')}"
                f" | Invariant: {_short(n.high_level_invariant, 240)}{extra}")
    return "\n".join(lines), id_map


# ---------------------------------------------------------------- 三层选择

def _parse_ids(value: dict | None, keys: tuple[str, ...]) -> list[str] | None:
    """从 LLM 返回的 JSON 里取字符串列表；取不到返回 None（触发回退）。"""
    if not isinstance(value, dict):
        return None
    for k in keys:
        v = value.get(k)
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
    return None


def hierarchical_select(
    *,
    task: dict,
    nodes: list[SecurityInvariantNode],
    requester: Requester,
    language: str,
    rule_score: Callable[[SecurityInvariantNode], float],
    limit: int,
    use_llm: bool = True,
) -> tuple[list[SecurityInvariantNode], dict]:
    """自顶向下三层选择，返回 (选中的节点列表, 决策轨迹)。

    use_llm=False 时退化为"规则分直接取 top-limit"，
    用于消融对照（隔离"层次结构本身"与"LLM 逐层选择"各自的贡献）。

    决策轨迹（trace）记录每层的输入规模、LLM 选择与是否回退，
    供消融实验核对"层次化到底省了多少调用、选得准不准"。
    """
    trace: dict = {"levels": [], "fallback": None, "llm_calls": 0}
    task_cwe = str(task.get("CWE_ID") or task.get("cwe") or "")

    # ---------- 无 LLM 对照臂 ----------
    if not use_llm:
        ranked = sorted(nodes, key=lambda n: -rule_score(n))[:limit]
        trace["levels"].append({"level": "rule_only", "candidates": len(nodes),
                                "selected": len(ranked)})
        return ranked, trace

    # ---------- L1：选 CWE 家族 ----------
    l1_text, all_cwes = build_l1_index(nodes)
    if not all_cwes:
        return [], trace
    l1_prompt = (
        "Select reference experience for a secure code repair task. The available CWE family index follows.\n\n"
        f"[Task] CWE-{task_cwe}; language {language}. Task contract: "
        + json.dumps(task, ensure_ascii=False) + "\n\n"
        f"[CWE family index]\n{l1_text}\n\n"
        "Select the CWE families most relevant to repairing the security gap while preserving functionality "
        "(usually 1-3 families; prioritize this task's CWE, but include semantically related adjacent categories when justified).\n"
        "Return only JSON in English: {\"cwes\": [\"74\", \"77\"], \"reason\": \"One-sentence justification\"}"
    )
    picked = _parse_ids(_call_json(requester, l1_prompt), ("cwes", "CWE", "cwe"))
    trace["llm_calls"] += 1
    if not picked:
        trace["fallback"] = "L1_failed"
        picked = [task_cwe] if task_cwe in all_cwes else all_cwes[:2]
    picked = [c for c in picked if c in all_cwes] or ([task_cwe] if task_cwe in all_cwes else all_cwes[:1])
    trace["levels"].append({"level": "L1_cwe", "offered": len(all_cwes),
                            "picked": picked})

    # ---------- L2：选经验类型 ----------
    l2_text, all_kinds = build_l2_index(nodes, picked)
    if not all_kinds:
        ranked = sorted(nodes, key=lambda n: -rule_score(n))[:limit]
        trace["fallback"] = "L2_empty"
        return ranked, trace
    l2_prompt = (
        "Select reference experience for a secure code repair task. The CWE families have been selected; "
        "the experience type index within those families follows.\n\n"
        f"[Task] CWE-{task_cwe}; language {language}. Task contract: "
        + json.dumps(task, ensure_ascii=False) + "\n\n"
        f"[Experience type index]\n{l2_text}\n\n"
        "Select the most helpful experience types for this repair (multiple choices allowed, usually 2-4 types).\n"
        "Consider both how to repair correctly (patch techniques/success patterns) and how to avoid regression "
        "(over-defense pitfalls/failure analysis). During a repair round, previous repair failures are particularly relevant.\n"
        "Return only JSON in English: {\"kinds\": [\"overdefense_pitfall\", \"minimal_patch_hint\"], "
        "\"reason\": \"One-sentence justification\"}"
    )
    picked_kinds = _parse_ids(_call_json(requester, l2_prompt), ("kinds", "kind", "types"))
    trace["llm_calls"] += 1
    if not picked_kinds:
        trace["fallback"] = "L2_failed"
        picked_kinds = all_kinds[:3]
    picked_kinds = [k for k in picked_kinds if k in all_kinds] or all_kinds[:3]
    trace["levels"].append({"level": "L2_kind", "offered": len(all_kinds),
                            "picked": picked_kinds})

    # ---------- L3：选具体经验 ----------
    l3_text, id_map = build_l3_index(nodes, picked, picked_kinds, language=language,
                                     rule_score=rule_score)
    if not id_map:
        ranked = sorted(nodes, key=lambda n: -rule_score(n))[:limit]
        trace["fallback"] = "L3_empty"
        return ranked, trace
    l3_prompt = (
        "Select reference experience for a secure code repair task. The CWE families and experience types have been selected; "
        "the candidate cards follow.\n\n"
        f"[Task] CWE-{task_cwe}; language {language}. Task contract: "
        + json.dumps(task, ensure_ascii=False) + "\n\n"
        f"[Candidate cards]{l3_text}\n\n"
        f"Select at most {limit} cards to inject into the code generator.\n"
        "First check the input sources, sensitive operations, APIs, data flows and valid-input contract in threat_analysis. "
        "Exclude incompatible API assumptions, mismatched applicability conditions or conflicts with the task. Matching CWE is insufficient. "
        "During repair, prioritize the actual defect in current_code and failure_evidence. "
        "Provisional cards are unverified advice; confident wording is not reliability. Prefer independently supported cards when relevance is equal.\n"
        "Returning zero cards is allowed: if none provides substantive help, return an empty list instead of diluting the context.\n"
        "Return only JSON in English: {\"ids\": [\"hint-74-123\", \"pitfall-74-456\"], \"reason\": \"One-sentence justification\"}"
    )
    picked_ids = _parse_ids(_call_json(requester, l3_prompt), ("ids", "id", "selected"))
    trace["llm_calls"] += 1
    if picked_ids is None:
        # L3 调用/解析失败：回退到规则排序，而不是返回空。
        # 为什么：返回空会让一次 API 抖动静默变成"这个任务没有经验可用"，
        # 而规则排序至少能给出同 CWE 的候选——降级但不失效。
        trace["fallback"] = "L3_failed_rule_fallback"
        ranked = sorted(nodes, key=lambda n: -rule_score(n))[:limit]
        trace["levels"].append({"level": "L3_node", "offered": len(id_map),
                                "picked": [n.invariant_id for n in ranked],
                                "note": "LLM failed; explicit rule fallback"})
        return ranked, trace
    chosen = [id_map[i] for i in picked_ids if i in id_map][:limit]
    trace["levels"].append({"level": "L3_node", "offered": len(id_map),
                            "picked": [n.invariant_id for n in chosen]})
    return chosen, trace

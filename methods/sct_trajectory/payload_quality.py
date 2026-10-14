# -*- coding: utf-8 -*-
"""经验载荷质量评分（Payload Quality），供 Phase3 门控排序与预算分配使用。

所属阶段：Phase3 独立有效性门控的**前置静态筛选**（不产生验证结论）。
输入：一条候选经验节点（SecurityInvariantNode）。
输出：{"score": 0~1, "flags": [...], "usable": bool}。
使用的验证证据：**不使用**动态测试证据——本模块只看经验文本自身是否自洽、完整、
    可渲染。因此它**不能**替代 ΔJointPass 门控，只能用来"把预算花在更可能有用的
    候选上"，并拦掉那些"注定无法被模型正确读到"的条目。
可能的失败类型：字段缺失 → 记为对应 flag，不抛异常。
是否允许修改长期经验库：**否** —— 纯只读评分，不改状态、不入树。

## 为什么需要它（2026-09-22 实测）

全量运行 `cle_full_874_20260922` 的 4518 条经验里：
    · 354 条（8.2%）fix_directive 超过渲染上限，尾部到不了模型；
    · 329 条（7.6%）root_cause 超限；
    · 204 条（4.5%）完全没有失败现场（rc/fd/pv 全空）；
    · 122 条（2.7%）fix_directive 是多轮「——」拼接，同卡内可能自相矛盾；
    合计 800 条（18%）载荷可疑。

门控原先只覆盖 1.6%（72/4518），且候选顺序不含任何"载荷是否可用"的信息——
等于把有限的审计预算随机撒在 4518 条上，其中 18% 即使通过门控、
注入后也无法被模型正确读到。

## 与动态门控的分工

    Tier A（本模块，零 LLM 成本，覆盖 100%）：
        静态质检 + 排序，拦掉/降权"注定读不到"的载荷。
    Tier B（gates.py，昂贵）：
        对 Tier A 通过的候选跑 ΔJointPass，决定晋升/降级/无证据。

**覆盖率**：Tier A 覆盖 100%，Tier B 在同等预算下少审 18% 的无效候选，
并可优先审载荷质量高的条目。
"""

from __future__ import annotations

import re
from typing import Any

from .hsk_tree import SecurityInvariantNode

# 渲染上限（与 agent_pipeline._RENDER_LIMIT 保持一致）
RENDER_LIMIT = 1200
PREV_LIMIT = 600
# 实测真实 fix_directive 最短 21 字、P1=65 字（4305 条样本），
# 故阈值取 20 作为安全网：不误标正常指令，只兜住真正退化的空指令。
MIN_DIRECTIVE_LEN = 20

# 矛盾信号（启发式）：同一字段里同时出现"加"与"减"方向的动作
_CONFLICT_PAIRS = (
    ("增加", "移除"), ("添加", "删除"), ("引入", "去掉"),
    ("强制", "不要强制"), ("收窄", "放宽"), ("前置", "后置"),
)
# 英文经验仍需相同的历史指令矛盾筛查；仅标疑似冲突，不将启发式视为执行证据。
_ENGLISH_CONFLICT_PAIRS = (("add", "remove"), ("introduce", "remove"),
                           ("require", "do not require"), ("narrow", "broaden"))


def payload_flags(node: SecurityInvariantNode) -> list[str]:
    """返回该节点载荷的缺陷标记列表（空列表 = 载荷干净）。"""
    src: dict[str, Any] = node.source or {}
    fd = str(src.get("fix_directive") or "")
    rc = str(src.get("root_cause") or "")
    pv = str(src.get("prev_fix_assessment") or "")
    flags: list[str] = []

    if len(fd) > RENDER_LIMIT:
        flags.append("directive_truncated")
    if len(rc) > RENDER_LIMIT:
        flags.append("root_cause_truncated")
    if len(pv) > PREV_LIMIT:
        flags.append("prev_fix_truncated")
    if not (fd or rc or pv):
        flags.append("no_failure_evidence")
    if fd and len(fd) < MIN_DIRECTIVE_LEN:
        flags.append("directive_too_short")
    if "——" in fd:
        flags.append("multi_round_concat")
        # 拼接 + 同字段内出现方向相反的动作 → 很可能自相矛盾
        for a, b in _CONFLICT_PAIRS:
            if a in fd and b in fd:
                flags.append("possible_contradiction")
                break
        if "possible_contradiction" not in flags:
            for first, second in _ENGLISH_CONFLICT_PAIRS:
                if all(re.search(r"\b" + re.escape(term) + r"\b", fd, re.I)
                       for term in (first, second)):
                    flags.append("possible_contradiction")
                    break
    # 负向红线过长会淹没提示词（实测可达约 4000 字）
    if len(str(node.negative_guardrail or "")) > 2000:
        flags.append("guardrail_bloated")
    return flags


def payload_quality(node: SecurityInvariantNode) -> dict:
    """计算载荷质量：score ∈ [0,1]，usable 表示是否值得进入动态门控。

    评分规则（可审计、无 LLM）：
        基础 1.0
        · 有可执行 fix_directive        +0.0（必要条件，缺失则大幅降分）
        · 缺 fix_directive              −0.35
        · 完全无失败现场                −0.30
        · 任一项会被截断                −0.15 / 项
        · 指令过短（<20 字）            −0.20
        · 多轮拼接                      −0.10
        · 疑似自相矛盾                  −0.20
        · 红线过长                      −0.05
    usable：score ≥ 0.5 且不含 possible_contradiction
        —— 自相矛盾的载荷即使通过动态门控也无法被正确执行，直接排除。
    """
    flags = payload_flags(node)
    src = node.source or {}
    fd = str(src.get("fix_directive") or "")

    score = 1.0
    if not fd:
        score -= 0.35
    if "no_failure_evidence" in flags:
        score -= 0.30
    score -= 0.15 * sum(1 for f in flags if f.endswith("_truncated"))
    if "directive_too_short" in flags:
        score -= 0.20      # 信息量不足的指令等于没给
    if "multi_round_concat" in flags:
        score -= 0.10
    if "possible_contradiction" in flags:
        score -= 0.20
    if "guardrail_bloated" in flags:
        score -= 0.05
    score = max(0.0, min(1.0, round(score, 4)))

    usable = score >= 0.5 and "possible_contradiction" not in flags
    return {"score": score, "flags": flags, "usable": usable}


def rank_candidates(nodes: list[SecurityInvariantNode]) -> list[tuple[SecurityInvariantNode, dict]]:
    """按载荷质量降序排列候选，供 Phase3 在有限预算下优先审计高质量载荷。

    为什么按质量排序而不是随机：门控预算有限（实测只覆盖 1.6%），
    在"载荷注定读不到"的条目上花预算等于纯浪费。
    """
    scored = [(n, payload_quality(n)) for n in nodes]
    scored.sort(key=lambda t: (-t[1]["score"], t[0].invariant_id))
    return scored


def split_by_usability(nodes: list[SecurityInvariantNode]) -> tuple[list, list]:
    """把候选分成 (可用, 不可用)。不可用的不淘汰，只排在最后。"""
    scored = rank_candidates(nodes)
    usable = [n for n, q in scored if q["usable"]]
    unusable = [n for n, q in scored if not q["usable"]]
    return usable, unusable

"""检索器（阶段 F，DOCX 表 6 自顶向下检索 + 用户拍板 LLM 打分配序）。

所属阶段：经验检索（前向四步里的 Retrieval 步）。
输入：HSK-Tree、任务查询（CWE_ID / language / description / security_policy）、
  可选 LLM 请求器。
输出：按对齐分数降序的经验节点 top-k，每项含双轨知识（positive_principle /
  negative_guardrail）+ 对应语言叶节点知识。
验证证据：检索本身不执行验证；分数只决定召回顺序，候选经验有效性由 Gate2/Gate3
  独立审查判定，检索分数不能替代有效性证据。
失败类型：LLM 打分失败时确定性降级为 base 分数（record "align_error"），不中断。
允许修改长期经验库：否——只读召回，不写记忆。

检索流程（DOCX 表 6 + 拍板决策）：
  1. Level 1 CWE 硬路由：按 task.cwe 锁定 CWEFamilyNode 子树（O(1)）；
  2. status=active 白名单 + language 双层过滤：只召回 active 且含该语言叶的节点；
  3. base 分数：Score = 3.0·CWE_Match + TFIDF_Overlap + α·(support+1)/(regression+1)；
  4. LLM 打分配序：对初召回 top-k 真实调用 LLM 打相关性分（0~1），重排序返回。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

from .hsk_tree import HskTree, SecurityInvariantNode, tfidf_overlap, utility_score

Requester = Callable[[str], dict]

# DOCX 打分公式参数
CWE_BONUS = 3.0        # CWE 硬命中加分
UTILITY_ALPHA = 1.0    # 归一化效用分权重 α
RECALL_K = 8           # 初召回候选数


def _query_text(task: dict) -> str:
    """任务查询文本（与生成 prompt 同源：CWE/语言/描述/安全策略）。"""
    return " ".join(str(task.get(k, "")) for k in ("CWE_ID", "language", "description", "security_policy"))


def _node_text(node: SecurityInvariantNode) -> str:
    """节点可检索文本（不变量 + 正/负双轨 + 适用条件）。"""
    return " ".join((
        node.high_level_invariant,
        node.positive_principle,
        node.negative_guardrail,
        node.applicability,
    ))


class HskTreeRetriever:
    """在 HSK-Tree 上自顶向下检索 + LLM 打分配序。

    打分（DOCX 表 6，含归一化修正）：
      Score = 3.0·CWE_Match + TFIDF_Overlap + α · utility_norm
      utility_norm = utility / max_utility(候选集)，取值 0~1。
    修正原因：原始公式用绝对效用 (support+1)/(regression+1)，归并节点 support=11 时
    效用项达 12.0（CWE 项的 4 倍），排序退化为「按 support 数排序」，语义相关性失效。
    归一化后效用项与 CWE 项/TFIDF 项同量级，仅作区分度调节。
    """

    def __init__(
        self,
        tree: HskTree,
        requester: Requester | None = None,
        *,
        cwe_bonus: float = CWE_BONUS,
        alpha: float = UTILITY_ALPHA,
        recall_k: int = RECALL_K,
    ) -> None:
        self.tree = tree
        self.requester = requester
        self.cwe_bonus = cwe_bonus
        self.alpha = alpha
        self.recall_k = recall_k

    def base_score(self, task: dict, node: SecurityInvariantNode, *, max_utility: float = 1.0) -> float:
        """DOCX 公式（归一化修正版）：3.0·CWE_Match + TFIDF_Overlap + α·utility_norm。

        已硬路由到同 CWE 分支，故 CWE_Match 恒为 1；utility_norm = utility/max_utility
        使效用项落在 0~1 量级，不再按 support 数量支配排序。
        """
        cwe_match = 1.0
        overlap = tfidf_overlap(_query_text(task), _node_text(node))
        utility = utility_score(node.support_count, node.regression_count)
        utility_norm = utility / max(1.0, float(max_utility))
        return self.cwe_bonus * cwe_match + overlap + self.alpha * utility_norm

    def _llm_score(self, task: dict, node: SecurityInvariantNode) -> dict:
        """真实调用 LLM 对单节点打相关性分（0~1）+ 理由。失败返回 error 标记。"""
        prompt = (
            "你是安全经验相关性评判器。判断这条安全经验对「在保持功能不变的前提下修复"
            "该任务安全缺口」有多相关/可用。只返回 JSON：{\"score\": 0到1之间的数, "
            "\"reason\": \"一句话理由\"}。score 高=强正例（促成安全修复且不破坏功能），"
            "score 低=弱相关或反例（过度防御/破坏功能）。\n"
            "任务：" + json.dumps(task, ensure_ascii=False) +
            "\n经验（不变量/正例/负例）：" + _node_text(node)
        )
        try:
            content = self.requester(prompt)["choices"][0]["message"]["content"]
            text = (content or "").strip()
            fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
            value = json.loads(fenced.group(1) if fenced else text)
            score = max(0.0, min(1.0, float(value.get("score", 0))))
            return {"score": round(score, 4), "reason": str(value.get("reason", ""))[:120], "error": None}
        except Exception as exc:
            return {"score": 0.0, "reason": "", "error": type(exc).__name__}

    def _to_card(self, task: dict, node: SecurityInvariantNode, *, base: float, llm: dict | None) -> dict:
        """把节点转成给 Planning/CodeGen 的双轨经验卡 dict。"""
        leaf = node.language_leaves.get(str(task.get("language", "python")))
        card = {
            "invariant_id": node.invariant_id,
            "cwe": node.cwe,
            "high_level_invariant": node.high_level_invariant,
            "positive_principle": node.positive_principle,
            "negative_guardrail": node.negative_guardrail,
            "applicability": node.applicability,
            "utility": round(node.utility, 4),
            "support_count": node.support_count,
            "regression_count": node.regression_count,
            "status": node.status,
            "language_leaf": leaf.to_dict() if leaf else None,
            "_base_score": round(base, 4),
            "_llm_score": llm.get("score") if llm else None,
            "_llm_reason": llm.get("reason", "") if llm else "",
            "_align_error": llm.get("error") if llm else None,
        }
        return card

    def search(
        self,
        task: dict,
        limit: int = 3,
        *,
        extra_nodes: list[SecurityInvariantNode] | None = None,
    ) -> list[dict]:
        """自顶向下检索：CWE 硬路由 → active+language 过滤 → base 分 → LLM 重排。

        extra_nodes：额外纳入检索范围的节点（用于 Gate1 召回探针——把 provisional
        候选临时加入，检验它能否在真实审查任务上被召回；不改变树本身）。
        """
        cwe = str(task.get("CWE_ID") or task.get("cwe") or "")
        language = str(task.get("language", "python"))
        # 1+2：CWE 硬路由 + status=active 白名单 + language 双层过滤
        nodes = list(self.tree.active_invariants(cwe, language=language))
        if extra_nodes:
            extra = [n for n in extra_nodes
                     if str(n.cwe) == cwe and language in n.language_leaves]
            nodes.extend(extra)
        if not nodes:
            return []

        # 归一化基准：候选集内的最大效用（含 extra），使效用项落在 0~1
        max_utility = max(utility_score(n.support_count, n.regression_count) for n in nodes)

        # 3：base 分数排序，初召回 recall_k
        nodes = sorted(nodes, key=lambda n: -self.base_score(task, n, max_utility=max_utility))[: self.recall_k]

        if self.requester is None:
            return [self._to_card(task, n, base=self.base_score(task, n, max_utility=max_utility), llm=None)
                    for n in nodes[:limit]]

        # 4：LLM 打分配序（真实调用）
        scored = []
        for n in nodes:
            llm = self._llm_score(task, n)
            scored.append((n, self.base_score(task, n, max_utility=max_utility), llm))
        # 主排序键 = LLM 分数；base 分数作次级排序键
        scored.sort(key=lambda t: (-(t[2]["score"] if t[2]["error"] is None else 0.0), -t[1]))
        return [self._to_card(task, n, base=base, llm=llm) for n, base, llm in scored[:limit]]


def build_retriever(tree: HskTree, requester: Requester | None = None) -> HskTreeRetriever:
    """便捷构造。"""
    return HskTreeRetriever(tree, requester)

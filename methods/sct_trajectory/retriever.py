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
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .hsk_tree import HskTree, SecurityInvariantNode, tfidf_overlap, utility_score

Requester = Callable[[str], dict]

# DOCX 打分公式参数
CWE_BONUS = 3.0        # CWE 硬命中加分
UTILITY_ALPHA = 1.0    # 归一化效用分权重 α
RECALL_K = 8           # 初召回候选数
SCORE_WORKERS = 8      # 相关性打分的并行度（与 RECALL_K 同量级即可）


def _query_text(task: dict) -> str:
    """任务查询文本（与生成 prompt 同源：CWE/语言/描述/安全策略）。"""
    return " ".join(str(task.get(k, "")) for k in (
        "CWE_ID", "language", "description", "security_policy", "threat_analysis",
        "current_code", "failure_evidence"))


def _node_text(node: SecurityInvariantNode) -> str:
    """节点可检索文本（不变量 + 正/负双轨 + 适用条件 + Level4 语言叶 + L3 轨道规则）。

    把 Level 4 / Level 3 也纳入检索文本，使跨层内容能影响 TF-IDF 相似度
    （消融 A1~A6 需要这一点才能区分"有该层"与"没有该层"）。
    """
    parts = [node.high_level_invariant, node.positive_principle,
             node.negative_guardrail, node.applicability]
    # 【失败现场入检索文本】（用户要求 2026-09-21）：把提炼出的
    # 具体失败根因、可执行修法、上一轮改法评估一并纳入 TF-IDF 文本，
    # 使"这条经验来自某任务的具体报错"能影响检索相似度。
    # 否则这些字段虽已提炼，却对检索排序毫无影响（等于白提炼）。
    _src = node.source or {}
    for _k in ("root_cause", "fix_directive", "prev_fix_assessment",
               "round_state", "round_index"):
        _v = _src.get(_k)
        if _v:
            parts.append(str(_v))
    for leaf in (node.language_leaves or {}).values():
        parts.extend(leaf.safe_constructs or [])
        parts.extend(leaf.prohibited_constructs or [])
        if leaf.pattern_snippet:
            parts.append(leaf.pattern_snippet)
    for rule in (node.track_rules or []):
        parts.append(rule.text)
    return " ".join(p for p in parts if p)


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
        ablation=None,
        min_llm_score: float = 0.6,
        cross_cwe_min_score: float = 0.75,
        antioverdefense_bonus: float = 1.5,
        same_task_bonus: float = 2.0,
        retrieval_mode: str = "flat_llm",
        embedding_client=None,
    ) -> None:
        self.tree = tree
        self.requester = requester
        self.cwe_bonus = cwe_bonus
        self.alpha = alpha
        self.recall_k = recall_k
        # 消融开关：控制经验卡里是否携带 Level 3/4 内容（None = 不注入，等于基线）
        self.ablation = ablation
        # 相关性门槛（用户要求"需要才注入"）：LLM 打分低于阈值 → 不注入该条。
        # 同 CWE 用 min_llm_score；跨 CWE 用更高的 cross_cwe_min_score（跨类别泛化要求更严）。
        # 设 0 可关闭门槛（回到旧的"凑满 limit"行为，用于对照实验）。
        self.min_llm_score = min_llm_score
        self.cross_cwe_min_score = cross_cwe_min_score
        # 【类型加权】（用户拍板第四条）：实测 47.3% 的失败是过度防御，
        # 而池中经验清一色"要加校验"——给抑制过度防御的两类经验加权。
        self.antioverdefense_bonus = antioverdefense_bonus
        # 【同任务历史经验优先】（改造 D）实测 185 次注入里 0 次来自同一任务——
        # 而"这个任务上次为何失败"是最直接的修复线索，应优先注入。
        self.same_task_bonus = same_task_bonus
        # 【检索机制】（用户 2026-09-22 提出层次化检索）：
        #   flat_llm  = 旧机制：逐候选单独打 LLM 分（实测打分无区分度、8 次调用/检索）
        #   hier_llm  = 新机制：LLM 看树骨架后逐层下探（3 次调用/检索，强制相对比较）
        #   flat_rule / hier_rule = 无 LLM 对照臂，用于消融实验隔离贡献
        self.retrieval_mode = retrieval_mode
        self.embedding_client = embedding_client
        # 层次化检索的决策轨迹（供消融实验核对每层选了谁、是否回退）
        self._trace_local = threading.local()

    @property
    def last_hier_trace(self):
        """保存当前线程检索审计，避免共享检索器被其他任务覆盖证据；不写经验。"""
        return getattr(self._trace_local, 'value', None)

    @last_hier_trace.setter
    def last_hier_trace(self, value):
        self._trace_local.value = value

    def _base_for_hier(self, task: dict, node: SecurityInvariantNode, *,
                       max_utility: float) -> float:
        """层次化检索用的规则分：同 CWE 走 base_score，跨 CWE 走 _cross_cwe_score。

        为什么分开：两条公式的 CWE 权重不同（跨 CWE 故意压低同 CWE 加成，
        让语义相似度主导）。层次化检索的候选池是全量的，必须按节点与任务
        是否同 CWE 选择对应公式，否则跨 CWE 候选会被同 CWE 加成压制，
        L1 选出的跨类别家族在 L3 又会全部落选。
        """
        cwe = str(task.get("CWE_ID") or task.get("cwe") or "")
        if str(node.cwe) == cwe:
            return self.base_score(task, node, max_utility=max_utility)
        return self._cross_cwe_score(task, node, max_utility=max_utility)

    def _type_bonus(self, node: SecurityInvariantNode, task: dict | None = None) -> float:
        """按经验类型给检索加权（抑制过度防御的经验排更前）。

        权重依据（实测）：全量 298 条最终评测里 fail/pass（功能失败·安全通过）
        占 47.3%，是最主要失败模式；而 minimal_patch_hint（最小改动手法）与
        overdefense_pitfall（过度防御陷阱）正是针对它的经验类型。
        """
        if self.antioverdefense_bonus <= 0:
            return 0.0
        kind = str((node.source or {}).get("kind") or "")
        if kind in ("minimal_patch_hint", "overdefense_pitfall"):
            return self.antioverdefense_bonus
        # 纯负向红线类（无正向原则）同样有抑制过度防御作用，给半额加权
        if (node.negative_guardrail or "").strip() and not (node.positive_principle or "").strip():
            return self.antioverdefense_bonus * 0.5
        return 0.0

    def _same_task_bonus(self, node: SecurityInvariantNode, task: dict | None) -> float:
        """同任务历史失败经验加权（改造 D）。

        节点的 source.task_id 记录它来自哪个任务；若与当前任务相同，
        说明这是"该任务上次失败后提炼的经验"，对本次修复最直接有用。
        """
        if not task or self.same_task_bonus <= 0:
            return 0.0
        tid = task.get("task_id") or task.get("index")
        if tid is None:
            return 0.0
        if str((node.source or {}).get("task_id")) == str(tid):
            return self.same_task_bonus
        return 0.0

    def base_score(self, task: dict, node: SecurityInvariantNode, *, max_utility: float = 1.0) -> float:
        """DOCX 公式（归一化修正版）：3.0·CWE_Match + TFIDF_Overlap + α·utility_norm + 类型加权。

        已硬路由到同 CWE 分支，故 CWE_Match 恒为 1；utility_norm = utility/max_utility
        使效用项落在 0~1 量级，不再按 support 数量支配排序。
        末项 _type_bonus 见其 docstring（针对过度防御这一最大失败模式）。
        """
        cwe_match = 1.0
        overlap = tfidf_overlap(_query_text(task), _node_text(node))
        utility = utility_score(node.support_count, node.regression_count)
        utility_norm = utility / max(1.0, float(max_utility))
        return (self.cwe_bonus * cwe_match + overlap + self.alpha * utility_norm
                + self._type_bonus(node, task)
                + self._same_task_bonus(node, task))

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
        """把节点转成给 Planning/CodeGen 的双轨经验卡 dict。

        按 ablation 的 inject_* 开关决定注入哪些层的内容（消融用：生成≠注入）：
          - inject_l4_* 关闭时 level4_text 为空，等价于"没有第 4 层"；
          - split 模式下额外带 track_rules 明细，合并模式则只有双轨字段。
        """
        language = str(task.get("language", "python"))
        leaf = node.language_leaves.get(language)
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
            # 检索到注入的边界：保留类型与排除条件，避免渲染器读空值；不改变生命周期。
            "kind": (node.source or {}).get("kind") or "",
            "exclusion_conditions": (node.source or {}).get("exclusion_conditions") or "",
            # 【失败现场】把提炼出的报错与修法放进经验卡，供 LLM 打相关性分时判读。
            "root_cause": (node.source or {}).get("root_cause") or "",
            "fix_directive": (node.source or {}).get("fix_directive") or "",
            "prev_fix_assessment": (node.source or {}).get("prev_fix_assessment") or "",
            "round_state": (node.source or {}).get("round_state"),
            "source_task_id": (node.source or {}).get("task_id"),
            "language_leaf": leaf.to_dict() if leaf else None,
            "_base_score": round(base, 4),
            "_llm_score": llm.get("score") if llm else None,
            "_llm_reason": llm.get("reason", "") if llm else "",
            "_align_error": llm.get("error") if llm else None,
        }
        # Level 4 注入文本（按消融开关）
        if self.ablation is not None and self.ablation.has_level4:
            from .level4 import render_level4_for_injection

            l4 = render_level4_for_injection(node.language_leaves, language=language,
                                             config=self.ablation)
            if l4:
                card["level4_text"] = l4
        # Level 3 轨道规则明细（仅拆分模式）
        if self.ablation is not None and self.ablation.split_level23 and node.track_rules:
            card["track_rules"] = [{"track": r.track, "text": r.text} for r in node.track_rules]
        return card

    def _all_active(self, language: str,
                     *, statuses: tuple[str, ...] = ("active",)) -> list[SecurityInvariantNode]:
        """全树 status+language 过滤（跨 CWE 检索用）。"""
        out: list[SecurityInvariantNode] = []
        for fam in self.tree.all_families():
            for n in fam.invariants:
                if n.status in statuses and language in n.language_leaves:
                    out.append(n)
        return out

    def _cross_cwe_score(self, task: dict, node: SecurityInvariantNode, *, max_utility: float) -> float:
        """跨 CWE 打分：CWE 命中只作加分项（不同 CWE 也能靠语义得分），
        让 CWE 覆盖不完整时仍能召回语义相近的经验。"""
        cwe = str(task.get("CWE_ID") or task.get("cwe") or "")
        same = 1.0 if str(node.cwe) == cwe else 0.0
        overlap = tfidf_overlap(_query_text(task), _node_text(node))
        utility_norm = utility_score(node.support_count, node.regression_count) / max(1.0, max_utility)
        # 不同 CWE 时不再给满额 CWE 加分，避免硬路由失效后语义项被淹没
        return (self.cwe_bonus * same * 0.5 + overlap * 2.0 + self.alpha * utility_norm
                + self._type_bonus(node, task)
                + self._same_task_bonus(node, task))

    def search(
        self,
        task: dict,
        limit: int = 3,
        *,
        extra_nodes: list[SecurityInvariantNode] | None = None,
        mode: str = "hybrid",
        pool_nodes: list[SecurityInvariantNode] | None = None,
    ) -> list[dict]:
        """检索经验。三种模式（用户要求支持跨 CWE 兜底）：

        - ``strict_cwe``：只在同 CWE 分支内检索（DOCX 原始设计，覆盖不全时返回空）；
        - ``cross_cwe`` ：忽略 CWE，全树按语义+效用打分检索，靠 LLM 打分辨相关性；
        - ``hybrid``    ：先同 CWE；不足 limit 时跨 CWE 兜底补足（默认，兼顾精度与覆盖）。

        extra_nodes：额外纳入检索范围的节点（Gate1 召回探针用，不改变树本身）。
        pool_nodes ：经验池节点。**解决"先有鸡还是先有蛋"**：架构归一��后 Phase1 只把
            经验插入池、不入树，导致 Phase1 与轮1 的检索恒为空（实测 4 个运行均为
            0 命中）。传入池节点后，检索范围 = 树节点 ∪ 池节点，冷启动阶段也能用上经验。
        """
        cwe = str(task.get("CWE_ID") or task.get("cwe") or "")
        language = str(task.get("language", "python"))
        self.last_hier_trace = None

        # 检索允许的节点状态。默认纳入 provisional——原因（实测）：
        # Phase1 产出的经验都是 provisional，要等 Phase3 门控才晋升 active；
        # 若只检索 active，则 Phase1/轮1 阶段检索恒为空（实测命中率仅 4/10），
        # 经验注入量被严重低估。ablation 显式给出时以其为准。
        statuses = (self.ablation.retrieval_statuses if self.ablation is not None
                    else ("active", "provisional", "consolidated"))

        def _pool_extra() -> list[SecurityInvariantNode]:
            """经验池里可检索的节点（按状态与语言过滤，避免注入 retired）。"""
            out = []
            for n in (pool_nodes or []):
                if n.status in statuses and language in n.language_leaves:
                    out.append(n)
            return out

        def _dedup(items: list[SecurityInvariantNode]) -> list[SecurityInvariantNode]:
            """按 invariant_id 去重，保持首次出现顺序。

            为什么需要（recon 实测缺陷）：节点晋升进树后**仍留在经验池**，
            于是 `_strict_pool()` 会同时从 `tree.active_invariants()` 和
            `pool_nodes` 拿到同一个对象，候选集出现重复——既浪费一次 LLM 打分调用，
            又可能让同一条经验在 top-limit 里占两个名额。
            """
            seen: set[str] = set()
            out: list[SecurityInvariantNode] = []
            for n in items:
                if n.invariant_id in seen:
                    continue
                seen.add(n.invariant_id)
                out.append(n)
            return out

        def _strict_pool() -> list[SecurityInvariantNode]:
            pool = list(self.tree.active_invariants(cwe, language=language, statuses=statuses))
            if extra_nodes:
                pool.extend(n for n in extra_nodes
                            if str(n.cwe) == cwe and language in n.language_leaves)
            pool.extend(n for n in _pool_extra() if str(n.cwe) == cwe)
            return _dedup(pool)

        def _cross_pool() -> list[SecurityInvariantNode]:
            pool = self._all_active(language, statuses=statuses)
            if extra_nodes:
                pool.extend(n for n in extra_nodes if language in n.language_leaves)
            pool.extend(_pool_extra())
            return _dedup(pool)

        if mode == "strict_cwe":
            nodes = _strict_pool()
            scorer = lambda n, mu: self.base_score(task, n, max_utility=mu)  # noqa: E731
        elif mode == "cross_cwe":
            nodes = _cross_pool()
            scorer = lambda n, mu: self._cross_cwe_score(task, n, max_utility=mu)  # noqa: E731
        else:  # hybrid
            nodes = _strict_pool()
            scorer = lambda n, mu: self.base_score(task, n, max_utility=mu)  # noqa: E731

        if mode == "hybrid" and not nodes:
            # 同 CWE 完全没有经验 → 直接走跨 CWE 语义检索（覆盖缺口兜底）
            nodes = _cross_pool()
            scorer = lambda n, mu: self._cross_cwe_score(task, n, max_utility=mu)  # noqa: E731

        # 【层次化检索必须看全量候选】（2026-09-22 实测缺陷）：
        # hybrid/strict 的候选池已按 CWE 过滤，若直接交给层次化检索，
        # L1 的"CWE 家族索引"只会出现 1 个家族（实测 offered=1），
        # "先看全树再下探"就退化成"只能选自己"。
        # 因此层次化模式一律用全量候选池，由 L1 的 LLM 决定是否跨 CWE——
        # 这正是它相对 flat 的额外能力（实测 flat 的跨 CWE 注入率恒为 0%）。
        if self.retrieval_mode in ("hier_llm", "hier_rule", "semantic_llm"):
            nodes = _cross_pool()
            scorer = lambda n, mu: self._base_for_hier(task, n, max_utility=mu)  # noqa: E731

        if not nodes:
            return []

        max_utility = max(utility_score(n.support_count, n.regression_count) for n in nodes)

        if self.retrieval_mode == "semantic_llm":
            # 训练/冻结检索：向量召回后适用性选择；失败显式关闭注入，不改库或证据。
            from .semantic_retrieval import semantic_select
            if self.embedding_client is None:
                raise ValueError("semantic_retrieval_requires_embedding_client")
            chosen, trace = semantic_select(task, nodes, self.requester, self.embedding_client, limit=limit)
            self.last_hier_trace = trace
            if trace.get('status') == 'error':
                error = RuntimeError('semantic_retrieval_failed:' + ','.join(trace.get('errors') or ['unknown']))
                error.retrieval_trace = trace
                raise error
            cards = [self._to_card(task, n, base=scorer(n, max_utility), llm=None) for n in chosen]
            for card in cards:
                card["retrieval_audit"] = trace
            return cards

        # 【同任务失败经验优先入候选】（缺陷 D34，2026-09-21 用真实产物定位）
        # 设计意图（改造 D）：任务被强制重放时，应优先拿到"它自己上一轮失败"提炼出的
        # 经验——这是最直接的修复线索。
        # 原实现只靠 `_same_task_bonus = 2.0` 参与打分，而**该加权恒为 0**：
        # 调用点构造的 query 是 `{**task_description, CWE_ID, language}`，里面没有
        # task_id/index，而 `_same_task_bonus` 读的正是 `task.get("task_id") or task.get("index")`
        # → 永远拿不到 id → 永远返回 0.0。
        # 实测（ab_verify3_20260921）：Phase2 检索命中 152 次，其中同任务 49 次（32%），
        # 但全部是 TF-IDF 碰巧撞上的——优先机制实际未生效，且同任务经验还要跟
        # 其它同 CWE 节点争 `recall_k=8` 的名额。
        # 修法（两层保险）：
        #   ① 这里把同任务节点**直接提到候选头部**，不受 recall_k 截断影响；
        #   ② 调用点补上 task_id，让打分公式里的 `_same_task_bonus` 真正生效。
        tid = task.get("task_id") if task.get("task_id") is not None else task.get("index")
        same_task: list[SecurityInvariantNode] = []
        if tid is not None:
            same_task = [n for n in nodes
                         if str((n.source or {}).get("task_id")) == str(tid)]
        same_ids = {id(n) for n in same_task}
        others = [n for n in nodes if id(n) not in same_ids]
        ranked = (
            sorted(same_task, key=lambda n: -scorer(n, max_utility))
            + sorted(others, key=lambda n: -scorer(n, max_utility))
        )[: self.recall_k]

        # ---------- 层次化检索分支（用户 2026-09-22 提出） ----------
        # 注意：本分支**提前 return**，因此不走下方的相关性门槛与跨 CWE 兜底。
        # 这是设计使然而非遗漏：
        #   · L3 的 LLM 选择本身就是相关性门槛（它显式可以返回 0 条）；
        #   · 跨 CWE 能力已内建在 L1（LLM 看全量家族索引后自行决定是否跨类别），
        #     不需要 hybrid 的事后兜底补足。
        # 为什么放在这里：候选收集（strict/cross/hybrid、状态过滤、同任务优先）
        # 与旧机制完全共用，只有"如何挑出最终 limit 条"这一步不同。
        if self.retrieval_mode in ("hier_llm", "hier_rule"):
            from .hier_retrieval import hierarchical_select
            chosen, htrace = hierarchical_select(
                task=task, nodes=list(nodes), requester=self.requester,
                language=language,
                rule_score=lambda n: scorer(n, max_utility),
                limit=limit,
                use_llm=(self.retrieval_mode == "hier_llm" and self.requester is not None),
            )
            self.last_hier_trace = htrace
            # 适用性裁决不能被同任务优先规则覆盖；历史卡同样须经过模型选择。
            cards = [self._to_card(task, n, base=scorer(n, max_utility), llm=None)
                     for n in chosen]
            for card in cards:
                card["retrieval_audit"] = htrace
            return cards

        if self.requester is None or self.retrieval_mode == "flat_rule":
            # flat_rule：规则分直接取 top-limit（消融对照，无 LLM 调用）
            cards = [self._to_card(task, n, base=scorer(n, max_utility), llm=None) for n in ranked[:limit]]
        else:
            # 【打分必须并行】（2026-09-22 实测阻塞点）
            # 原实现对最多 recall_k=8 个候选**串行**调 LLM：单次检索 8 × ~5s ≈ 40s。
            # 实测成本分解里 `other` 阶段 933 次调用（占全部调用 38%），绝大多数来自这里，
            # 是"任务内"最大的串行瓶颈 —— 而任务之间再高并发也救不了它。
            # 并行化后由 requester 的**全局在途闸门**兜住总并发，不会打爆 API。
            bases = [(n, scorer(n, max_utility)) for n in ranked]
            with ThreadPoolExecutor(max_workers=min(len(bases), SCORE_WORKERS)) as _ex:
                llms = list(_ex.map(lambda pair: self._llm_score(task, pair[0]), bases))
            scored = [(n, b, l) for (n, b), l in zip(bases, llms)]
            scored.sort(key=lambda t: (-(t[2]["score"] if t[2]["error"] is None else 0.0), -t[1]))
            cards = [self._to_card(task, n, base=base, llm=llm) for n, base, llm in scored[:limit]]

        # ---- 相关性门槛（用户要求"需要才注入，不需要 0 条也可以"）----
        # 实测问题：原先固定凑满 limit=3 条，导致 296/298 个任务都恰好注入 3 条，
        # 且 83.8% 是跨 CWE 的无关经验——什么都没测出来还稀释了上下文。
        # 现在：LLM 打分低于阈值的直接丢弃；同 CWE 与跨 CWE 用不同阈值（跨 CWE 更严）。
        if self.requester is not None and self.min_llm_score > 0:
            kept = []
            for c in cards:
                sc = c.get("_llm_score")
                if sc is None or c.get("_align_error"):
                    # 打分失败：保守丢弃（宁缺毋滥），避免用未验证相关的经验污染生成
                    continue
                same_cwe = str(c.get("cwe")) == cwe
                need = self.min_llm_score if same_cwe else max(self.min_llm_score, self.cross_cwe_min_score)
                if sc >= need:
                    c["_relevance_gate"] = "same_cwe" if same_cwe else "cross_cwe"
                    kept.append(c)
            cards = kept

        # hybrid：同 CWE 命中不足时，用跨 CWE 语义检索兜底补足（同样要过相关性门槛）
        if mode == "hybrid" and len(cards) < limit:
            have = {c["invariant_id"] for c in cards}
            cross_nodes = [n for n in _cross_pool() if n.invariant_id not in have]
            if cross_nodes:
                mu = max(utility_score(n.support_count, n.regression_count) for n in cross_nodes)
                cross_ranked = sorted(cross_nodes, key=lambda n: -self._cross_cwe_score(task, n, max_utility=mu))
                for n in cross_ranked[: self.recall_k]:
                    if len(cards) >= limit:
                        break
                    llm = self._llm_score(task, n) if self.requester is not None else None
                    if llm is not None and llm.get("error") is None:
                        # 跨 CWE 兜底用更高的相关性门槛
                        if llm.get("score", 0) < max(self.min_llm_score, self.cross_cwe_min_score):
                            continue
                    elif llm is not None:
                        continue
                    if llm is None and tfidf_overlap(_query_text(task), _node_text(n)) <= 0:
                        continue
                    card = self._to_card(task, n, base=self._cross_cwe_score(task, n, max_utility=mu), llm=llm)
                    card["_relevance_gate"] = "cross_cwe"
                    cards.append(card)
        # 注意：这里不再强行凑满 limit。若经验相关性不足，返回更少甚至 0 条是**预期行为**
        # （用户明确要求"需要就选择，不需要 0 条也可以"）。
        return cards[:limit]


def build_retriever(tree: HskTree, requester: Requester | None = None) -> HskTreeRetriever:
    """便捷构造。"""
    return HskTreeRetriever(tree, requester)

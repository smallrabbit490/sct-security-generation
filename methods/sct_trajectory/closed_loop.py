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

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from methods.sct_agent.validation_evidence import validate_plt_row
from methods.sct_lifecycle_replay.source_knowledge import extract_initial_hypothesis

from .active_replay import schedule_replay
from .agent_pipeline import run_pipeline
from .distillation import distill_trace
from .error_ledger import ErrorEntry, ErrorLedger
from .four_state import classify_transition, state_from_evidence
from .gates import audit_candidate, majority_vote
from .hsk_tree import (
    HskTree,
    LanguageLeaf,
    SecurityInvariantNode,
    absorb_or_new,
    consolidate_family,
    prune_by_utility,
)
from .retriever import HskTreeRetriever
from .schemas import RolloutTrace, Transition

Requester = Callable[[str], dict]
ProgressFn = Callable[[str], None]


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
        positive_principle=str(card.get("principle", "")),
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
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _node_from_ledger_item(d: dict, *, cwe: str = "") -> SecurityInvariantNode | None:
    """把 Distillation 输出的盲区条目（stalled）转成 SecurityInvariantNode。

    关键改动：失败不再只进错题本——提炼出的盲区文本同时作为负向经验插入统一池，
    使其能参与检索、在未来任务上起警示作用。
    """
    blind = str(d.get("blind_spot") or d.get("attribution") or "").strip()
    if not blind:
        return None
    node = SecurityInvariantNode(
        invariant_id=f"blind-{d.get('cwe') or cwe}-{abs(hash(blind))}",
        cwe=str(d.get("cwe") or cwe),
        high_level_invariant=blind[:300],
        applicability=str(d.get("applicability", "")),
        positive_principle="",
        negative_guardrail=blind[:300],
        status="provisional",
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
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _node_from_pitfall(d: dict) -> SecurityInvariantNode | None:
    """把"过度防御陷阱"提炼成一条独立经验节点（负向红线，参与检索）。

    这类经验直接对应实测的失败模式（注入经验后功能退化），以 negative_guardrail
    形式注入最有效——它在 Planning 中被标为【负向红线·务必避免】。
    """
    pitfall = str(d.get("overdefense_pitfall") or "").strip()
    if not pitfall:
        return None
    node = SecurityInvariantNode(
        invariant_id=f"pitfall-{d.get('cwe','')}-{abs(hash(pitfall))}",
        cwe=str(d.get("cwe", "")),
        high_level_invariant=f"过度防御陷阱：{pitfall[:250]}",
        applicability=str(d.get("applicability", "")),
        positive_principle="",
        negative_guardrail=pitfall[:300],
        status="provisional",
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


def _round_stats(traces: list[RolloutTrace]) -> dict:
    """统计一批轨迹的分项通过率与 ABCD（看板"每轮通过率"用）。

    关键：**分母是该轮实际存在的样本数**，不是任务总数——已达 A 的任务不会再跑
    修复轮，所以第 2 轮的样本天然少于第 1 轮。看板必须显示 x/y，避免小样本误导。
    """
    from collections import Counter as _C

    n = f_pass = s_pass = joint = 0
    abcd: _C = _C()
    per_task: list[dict] = []
    for t in traces:
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
    return {
        "samples": n,
        "functional": {"pass": f_pass, "total": n, "rate": round(f_pass / n, 4) if n else 0.0},
        "security": {"pass": s_pass, "total": n, "rate": round(s_pass / n, 4) if n else 0.0},
        "joint": {"pass": joint, "total": n, "rate": round(joint / n, 4) if n else 0.0},
        "abcd": {k: abcd.get(k, 0) for k in ("A", "B", "C", "D") if abcd.get(k)},
        "per_task": per_task,
    }


def _repair_round_stats(traces: list[RolloutTrace]) -> dict:
    """统计任务内修复轮 c⁰ → c¹ 的功能/安全通过率（看板"单任务修复效果"用）。

    c⁰ = 首次从零生成后的验证；c¹ = 修复轮后的验证。分母同样是各轮实际样本数。
    """
    def side(idx: int) -> dict:
        n = f = s = 0
        for t in traces:
            evs = t.evidence or []
            if idx < len(evs) and isinstance(evs[idx], dict) and "error" not in evs[idx]:
                n += 1
                f += int((evs[idx].get("functional") or {}).get("status") == "pass")
                s += int((evs[idx].get("security") or {}).get("status") == "pass")
        return {"samples": n,
                "functional": {"pass": f, "total": n, "rate": round(f / n, 4) if n else 0.0},
                "security": {"pass": s, "total": n, "rate": round(s / n, 4) if n else 0.0}}

    return {"c0": side(0), "c1": side(1)}


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
    ) -> None:
        self.requester = requester
        self.tree = tree
        self.ledger = ledger
        self.timeout = timeout
        self.workers = max(1, int(workers))
        self.progress = progress or (lambda msg: None)
        # Phase1 seed 提取的输出语言：默认英文，使经验节点与 PLT 英文任务描述同语言，
        # 否则检索器 TF-IDF 中英重叠恒为 0（实测 71% 查询-节点对重叠为 0）。
        self.seed_language = seed_language
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
        # 【统一经验池】Phase1（冷启动，含成功与失败）与 Phase2（重放+多Agent）产出的
        # 经验一视同仁地插入这里，不在插入时做任何门控；Phase3 对全池统一处理。
        self.experience_pool: list[SecurityInvariantNode] = []
        # 兼容旧字段名（保留别名，便于既有调用/脚本读取）
        self.traces: list[RolloutTrace] = []
        self.last_schedule: dict[str, Any] = {}

    @property
    def candidates(self) -> list[SecurityInvariantNode]:
        """向后兼容别名：指向统一经验池中尚未处理的条目。"""
        return self.experience_pool

    def _map(self, fn, items: list, *, on_done: Callable[[Any], None] | None = None) -> list:
        """对 items 并发执行 fn（无共享状态），逐个就绪即消费（流式）。

        on_done(result)：每个 future 就绪时立即回调（用于逐条落盘 + 进度输出），
        在 worker 线程池的消费线程内串行调用，因此 HSK-Tree/错题本写入线程安全。
        workers=1 时串行执行，on_done 仍逐条调用。
        """
        if self.workers <= 1 or len(items) <= 1:
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
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
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
        }
        # 工作线程内设置成本阶段（threading.local 不跨线程继承）
        self.cost.set_stage("phase1")
        try:
            card = extract_initial_hypothesis(row, self.req_extract, output_language=self.seed_language)
            entry["card_id"] = card.get("id", "")
            entry["_card"] = card
            task = row.get("task_description") or {}

            # 用与 Phase2 相同的 rollout 机制跑两轮（Phase1 无检索卡，从零生成）
            trace = self._run_rollout(
                row, retriever=None, repairs=1,
                seed_card={"polarity": "positive", "principle": card.get("principle", ""),
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
                entry["distilled"] = distill_trace(trace, self.req_distill, phase="phase1")
            except Exception as exc:
                entry["distilled"] = {"error": type(exc).__name__}
            return entry
        except Exception as exc:
            entry["outcome"] = "seed_error"
            entry["error"] = type(exc).__name__
            entry["_failure"] = type(exc).__name__
            return entry

    def _insert_experience(self, node: SecurityInvariantNode, *, stage: str, task_id: Any) -> None:
        """把一条经验插入【统一经验池】（Phase1 与 Phase2 一视同仁，不提前门控）。

        这是架构归一化的核心：两个阶段产出的经验都只做"插入"，不在这里决定去留；
        是否入树由 Phase3 对全池统一处理（Gate1/2/3 + 归并 + 剪枝）决定。
        """
        node.source = {**(node.source or {}), "stage": stage, "task_id": task_id}
        self.experience_pool.append(node)

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
                "stage": "phase1",
                "kind": "seed_from_diff",
                "verified_state": entry.get("state_after_repair") or entry.get("state_first") or "",
                "outcome": outcome,
            }
            self._insert_experience(node, stage="phase1", task_id=task_id)

        # 2) Distillation 从两轮轨迹提炼的经验（成功→正例，失败→盲区）
        distilled = entry.get("distilled") or {}
        for d in (distilled.get("positive") or []):
            node = _node_from_distilled(d)
            if node:
                node.source = {"stage": "phase1", "kind": d.get("kind", ""), "task_id": task_id}
                self._insert_experience(node, stage="phase1", task_id=task_id)
        for d in (distilled.get("negative") or []):
            node = _node_from_negative(d)
            if node:
                node.source = {"stage": "phase1", "kind": d.get("kind", ""), "task_id": task_id}
                self._insert_experience(node, stage="phase1", task_id=task_id)
        for d in (distilled.get("error_ledger") or []):
            node = _node_from_ledger_item(d, cwe=cwe)
            if node:
                node.source = {"stage": "phase1", "kind": d.get("kind", "stalled"), "task_id": task_id}
                self._insert_experience(node, stage="phase1", task_id=task_id)
            # 错题本同步记录（保留原有的结构化统计）
            self.ledger.add(ErrorEntry(
                cwe=str(d.get("cwe") or cwe),
                kind=str(d.get("kind") or "seed_grounding_failure"),
                failure_type=str(d.get("blind_spot") or d.get("attribution") or "unknown")[:200],
                source_hash=str(task_id),
                transition=str(d.get("kind", "")),
            ))

        # 4) 新增两类经验（最小改动手法 / 过度防御陷阱）也一律入池参与检索
        for d in _all_distilled_items(distilled):
            for factory, kindname in ((_node_from_hint, "minimal_patch_hint"),
                                      (_node_from_pitfall, "overdefense_pitfall")):
                extra = factory(d)
                if extra:
                    extra.source = {"stage": "phase1", "kind": kindname, "task_id": task_id}
                    self._insert_experience(extra, stage="phase1", task_id=task_id)

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
        pipeline = run_pipeline(task, [], requester=self.req_gen, reference_code=code)
        return (pipeline.get("code") or "").strip()

    # ---------- Phase 2：进化 ----------

    def _phase2_one(self, row: dict, retriever: HskTreeRetriever, repairs: int) -> dict:
        """处理单个 replay 任务（无副作用，可并发）：rollout + Distillation。"""
        self.cost.set_stage("phase2")
        try:
            trace = self._run_rollout(row, retriever, repairs=repairs)
            distilled = distill_trace(trace, self.req_distill)
            return {"task_id": row.get("index"), "trace": trace, "distilled": distilled, "error": None}
        except Exception as exc:
            return {"task_id": row.get("index"), "trace": None, "distilled": None, "error": type(exc).__name__}

    def phase2_evolve(self, replay_pool: list[dict], *, batch_size: int = 24, replay_limit: int = 96, repairs: int = 1, on_item: Callable[[dict], None] | None = None) -> dict:
        """Phase 2：主动回放调度 → 并发 rollout + 蒸馏 → 流式合并候选与错题本。"""
        self.cost.set_stage("phase2")
        retriever = HskTreeRetriever(self.tree, requester=self.req_score)
        sched = schedule_replay(self.tree, self.ledger, replay_pool, self.req_schedule,
                                batch_size=batch_size, replay_limit=replay_limit)
        selected = sched["selected"]
        self.last_schedule = {
            "pool_size": len(replay_pool),
            "raw_decisions": sched.get("decisions") or [],
            "selected_ids": [t.get("index") for t in selected],
            "llm_reasons": sched.get("reasons") or {},
            "error": sched.get("error"),
        }
        self.progress(f"[Phase2] 调度选中 {len(selected)}/{len(replay_pool)} 条回放任务"
                      f"（LLM decisions={len(self.last_schedule['raw_decisions'])}，"
                      f"error={self.last_schedule['error']}）")

        def process(row: dict) -> dict:
            return self._phase2_one(row, retriever, repairs)

        state = {"positive": 0, "negative": 0, "ledger": 0, "n": 0}

        def done(out: dict) -> None:
            trace = out.get("trace")
            distilled = out.get("distilled")
            if trace is not None:
                self.traces.append(trace)
            if distilled:
                task_id = out.get("task_id")
                # 架构归一化：Phase2 的经验同样只"插入"统一池，不在这里门控
                for d in distilled["positive"]:
                    node = _node_from_distilled(d)
                    if node:
                        self._insert_experience(node, stage="phase2", task_id=task_id)
                        state["positive"] += 1
                for d in distilled["negative"]:
                    node = _node_from_negative(d)
                    if node:
                        self._insert_experience(node, stage="phase2", task_id=task_id)
                        state["negative"] += 1
                for item in distilled["error_ledger"]:
                    node = _node_from_ledger_item(item)
                    if node:
                        self._insert_experience(node, stage="phase2", task_id=task_id)
                    self.ledger.add(ErrorEntry(
                        cwe=item.get("cwe", ""), kind=item.get("kind", "stalled"),
                        failure_type=str(item.get("blind_spot") or "stalled")[:60],
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
                            self._insert_experience(extra, stage="phase2", task_id=task_id)
            state["n"] += 1
            if on_item:
                on_item(out)
            self.progress(f"[Phase2 {state['n']}/{len(selected)}] task={out.get('task_id')} "
                          f"traces={1 if trace else 0} err={out.get('error')}")

        self._map(process, selected, on_done=done)
        return {
            "selected": len(selected),
            "schedule": self.last_schedule,
            "traces": [t.to_dict() for t in self.traces],
            "positive_candidates": state["positive"],
            "negative_candidates": state["negative"],
            "ledger_entries": state["ledger"],
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
        on_phase2_item: Callable[[dict], None] | None = None,
        on_round_end: Callable[[int, Any, dict], None] | None = None,
    ) -> dict:
        """Phase 2+3 多轮闭环演进（DOCX 的 Replay-Audit 迭代）。

        每轮：主动回放调度 → rollout → 蒸馏 → 产出候选 → 立即用 Phase3 门控审计
        → supported 候选入树 → 下一轮（树变强后再调度，直到 replay 池耗尽或达到轮数）。

        这是对「单轮 Phase2 + 末尾一次性 Phase3」的修正：让新经验在轮间真正进入
        检索范围，后续轮次的生成才能用到它们。
        """
        used: set[int] = set()
        remaining = list(replay_pool)
        rounds_log: list[dict] = []
        all_audit_detail: list[dict] = []
        all_gate_records: list[dict] = []

        for rnd in range(1, max(1, rounds) + 1):
            if not remaining:
                self.progress(f"[轮{rnd}] replay 池已耗尽，提前结束多轮演进")
                break
            pool = remaining
            pool_before = len(self.experience_pool)
            self.progress(f"[轮{rnd}] 开始：候选 replay {len(pool)} 条，经验池 {pool_before} 条，树 active "
                          f"{sum(1 for f in self.tree.all_families() for n in f.invariants if n.status=='active')} 节点")
            p2 = self.phase2_evolve(
                pool, batch_size=batch_size, replay_limit=replay_limit,
                repairs=repairs, on_item=on_phase2_item,
            )
            # 记录本轮被消费的 replay 任务，后续轮次不再重复
            for row in pool:
                used.add(int(row.get("index", -1)))
            chosen = {int(t["task_id"]) for t in p2["traces"]}
            remaining = [row for row in remaining if int(row.get("index", -1)) not in chosen]

            # Phase3：审计【全池中所有尚未处理的经验】（Phase1 与 Phase2 一视同仁）
            hpass = [{"cwe": t["cwe"], "task_id": t["task_id"]} for t in p2["traces"] if t["states"][-1:] == ["A"]]
            p3 = self.phase3_audit(
                audit_pool, audit_per_candidate=audit_per_candidate,
                regression_samples=regression_samples, hpass_traces=hpass,
                fallback_tasks=[r for r in remaining if int(r.get("index", -1)) not in chosen],
                max_entries=audit_max_entries,
            )
            all_audit_detail.extend(p3["audit_detail"])
            all_gate_records.extend(p3["gate_records"])
            promoted = sum(1 for g in p3["gate_records"] if g["decision"] == "supported")
            rounds_log.append({
                "round": rnd,
                "replay_candidates": len(pool),
                "selected": p2["selected"],
                "schedule": p2.get("schedule"),
                "positive_candidates": p2["positive_candidates"],
                "negative_candidates": p2["negative_candidates"],
                "ledger_entries": p2["ledger_entries"],
                "pool_size": len(self.experience_pool),
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

        return {
            "rounds": rounds_log,
            "gate_records": all_gate_records,
            "audit_detail": all_audit_detail,
            "traces": [t.to_dict() for t in self.traces],
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
    ) -> dict:
        """最终评测：把固化经验树在审计池上**全量**跑��遍，测真实效果。

        与 phase3_audit 的区别（重要）：
          - phase3_audit 是"逐条经验的门控审计"（抽样、算 ΔJointPass 决定去留）；
          - final_evaluate 是"固化后的整体评测"（不决定去留，只测 M* 的端到端表现）。
        流程：对 eval_pool 中每个任务 → 用当前树检索注入 → 四步生成 → 功能/安全动态测试
              → 四态判定；汇总分 CWE 的 JointPass 与 ABCD 分布，并保留失败案例。
        """
        self.cost.set_stage("final_eval")
        retriever = HskTreeRetriever(self.tree, requester=self.req_score)
        rows: list[dict] = []
        counter = {"n": 0}

        def one(row: dict) -> dict:
            self.cost.set_stage("final_eval")
            task = row.get("task_description") or {}
            query = {**task, "CWE_ID": str(row.get("CWE_ID", "")), "language": "python"}
            cards = retriever.search(query, limit=3) or []
            pipeline = run_pipeline(task, cards, requester=self.req_gen, reference_code="")
            code = (pipeline.get("code") or "").strip()
            out: dict[str, Any] = {
                "task_id": row.get("index"), "cwe": str(row.get("CWE_ID", "")),
                "retrieved_ids": [c.get("invariant_id") for c in cards],
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
    ) -> RolloutTrace:
        """单任务多轮 rollout：四步生成 → 验证四态 → 失败后有限修复。

        retriever=None 时（Phase1 冷启动场景）不检索经验，只把 seed_card（若给出）
        作为唯一注入经验，用于从零生成自验证。
        落盘审计信息：每轮检索到的经验 id/LLM 分（retrieved_per_round）、修复轮的
        局部代码差分（patch_diffs）、四步 Agent 上下文（agent_context）。
        """
        task = row.get("task_description") or {}
        query = {**task, "CWE_ID": row.get("CWE_ID"), "language": "python"}
        states: list[str] = []
        codes: list[str] = []
        evidence_list: list[dict] = []
        retrieved_per_round: list[list[dict]] = []
        patch_diffs: list[str] = []
        agent_context: list[dict] = []
        reference = ""
        for _ in range(repairs + 1):
            if retriever is not None:
                cards = retriever.search(query, limit=3) or []
            else:
                # Phase1：无检索器，仅注入从漏洞—补丁差异提取的 seed 经验（首轮）
                cards = [seed_card] if (seed_card and not reference) else []
            retrieved_per_round.append([
                {"invariant_id": c.get("invariant_id"), "llm_score": c.get("_llm_score"),
                 "base_score": c.get("_base_score"), "utility": c.get("utility")}
                for c in cards
            ])
            pipeline = run_pipeline(task, cards, requester=self.req_gen, reference_code=reference)
            code = (pipeline.get("code") or "").strip()
            patch_diffs.append(pipeline.get("patch_diff") or "")
            # 记录前向四步 Agent 的完整交互上下文（供 Distillation 做细粒度归因）
            agent_context.append({
                "analysis": pipeline.get("analysis_parsed") or {},
                "plan": pipeline.get("plan_parsed") or {},
                "retrieved_cards": [
                    {"invariant_id": c.get("invariant_id"),
                     "positive_principle": c.get("positive_principle"),
                     "negative_guardrail": c.get("negative_guardrail")}
                    for c in cards
                ],
                "patch_diff": pipeline.get("patch_diff") or "",
            })
            if not code:
                states.append("D"); codes.append(""); evidence_list.append({"error": "empty_code"}); break
            evidence, label = validate_and_state(row, code, timeout=self.timeout)
            states.append(label); codes.append(code); evidence_list.append(evidence)
            if label == "A":
                break
            reference = code
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
        )

    # ---------- Phase 3：门控 + 拓扑 ----------

    def _joint_pass_rate(self, rows: list[dict], cards_provider, *, samples: int = 1) -> tuple[float, list[bool]]:
        """在给定任务上跑生成+验证，返回联合通过率与逐任务结果。

        cards_provider(task) -> 注入给 Planning/CodeGen 的经验卡列表。
        samples>1 时每条任务重复采样，用多数决判该任务是否通过（Gate3 降噪）。
        """
        flags: list[bool] = []
        for row in rows:
            task = row.get("task_description") or {}
            query = {**task, "CWE_ID": row.get("CWE_ID"), "language": "python"}
            sample_flags: list[bool] = []
            for _ in range(max(1, samples)):
                cards = cards_provider(query)
                pipeline = run_pipeline(task, cards, requester=self.req_gen, reference_code="")
                code = (pipeline.get("code") or "").strip()
                if not code:
                    sample_flags.append(False)
                    continue
                _, label = validate_and_state(row, code, timeout=self.timeout)
                sample_flags.append(label == "A")
            flags.append(majority_vote(sample_flags) if samples > 1 else sample_flags[0])
        rate = (sum(1 for f in flags if f) / len(flags)) if flags else 0.0
        return rate, flags

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
        retriever = HskTreeRetriever(self.tree, requester=None)
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
            # CWE 去重后再截断，保证预算覆盖尽量多的漏洞类别
            picked: list[SecurityInvariantNode] = []
            seen_cwe: set[str] = set()
            for n in targets:
                if len(picked) >= max_entries:
                    break
                if str(n.cwe) in seen_cwe:
                    continue
                picked.append(n)
                seen_cwe.add(str(n.cwe))
            # 若去重后仍有余量，按原优先级补足
            for n in targets:
                if len(picked) >= max_entries:
                    break
                if n not in picked:
                    picked.append(n)
            deferred = [n for n in targets if n not in picked]
            self.progress(f"[Phase3] 审计抽样：{len(picked)}/{len(targets)} 条（其余 {len(deferred)} 条留待后续轮次）")
            targets = picked

        for cand in targets:
            same_cwe = by_cwe.get(str(cand.cwe), [])[:audit_per_candidate]
            audit_source = "D_audit"
            if not same_cwe:
                # D_audit 无该 CWE 任务时回退到 replay 池（独立性略降，但避免"必然被拒"）
                same_cwe = fallback_by_cwe.get(str(cand.cwe), [])[:audit_per_candidate]
                audit_source = "D_replay" if same_cwe else "none"
            detail: dict[str, Any] = {
                "candidate_id": cand.invariant_id, "cwe": cand.cwe,
                "source_stage": (cand.source or {}).get("stage", ""),
                "source_kind": (cand.source or {}).get("kind", ""),
                "audit_source": audit_source,
                "audit_task_count": len(same_cwe), "delta_joint_pass": 0.0,
                "baseline_pass": None, "with_candidate_pass": None,
                "gate1_probe_task": None, "gate1_retrieved": False,
                "security_regressions": 0, "functional_regressions": 0,
            }

            # ---- Gate1：用真实 audit 任务做召回探针（候选临时并入检索范围）----
            if same_cwe:
                probe_row = same_cwe[0]
                probe_task = {
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

            # ---- Gate3：H_pass 回归（N=3 多数决）----
            if hpass_traces:
                hp_rows = [r for r in (hpass_traces or []) if str(r.get("cwe")) == str(cand.cwe)]
                if hp_rows:
                    _, flags = self._joint_pass_rate(
                        [{"index": r.get("task_id"), "CWE_ID": r.get("cwe"),
                          "task_description": r.get("task_description") or {}} for r in hp_rows],
                        lambda q: (retriever.search(q, limit=3) or []) + [cand_card],
                        samples=regression_samples)
                    detail["security_regressions"] = sum(1 for f in flags if not f)
                    detail["functional_regressions"] = 0

            rec = audit_candidate(
                cand.invariant_id, retriever, probe_task,
                delta_joint_pass=detail["delta_joint_pass"],
                security_regressions=detail["security_regressions"],
                functional_regressions=detail["functional_regressions"],
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
            records.append(rec.to_dict())
            audit_detail.append(detail)

            # 写入终态，避免下一轮重复审计（统一处理，不分来源阶段）
            if rec.decision == "supported":
                cand.status = "active"
                family = self.tree.ensure_family(cand.cwe)
                absorb_or_new(family, cand)
            elif rec.decision == "demoted":
                cand.status = "retired"
            elif rec.decision == "unmeasured":
                cand.status = "unmeasured"
            else:
                cand.status = "revised"

        merged = 0
        for fam in self.tree.all_families():
            if consolidate_family(fam, consolidator=self._llm_consolidate) is not None:
                merged += 1
        pruned = sum(prune_by_utility(fam) for fam in self.tree.all_families())
        promoted = sum(1 for r in records if r.get("decision") == "supported")
        self.progress(f"[Phase3] 审计 {len(targets)} 条经验（晋升 {promoted}），归并 {merged}，剪枝 {pruned}")
        return {"gate_records": records, "audit_detail": audit_detail,
                "merged": merged, "pruned": pruned, "audited": len(targets), "promoted": promoted}

    def _llm_consolidate(self, nodes: list[SecurityInvariantNode]) -> SecurityInvariantNode:
        """容量超限离线归并（LLM 提取公约数）——真实调用 AI。"""
        from .distillation import _content, _extract_json

        highlights = "；".join(n.high_level_invariant for n in nodes)
        prompt = (
            "你是经验归并专家。下面同 CWE 的多个安全不变量节点存在语义重叠，请归纳出"
            "1 条更高阶的通用安全不变量，只返回 JSON："
            '{"high_level_invariant": "...", "positive_principle": "...", "negative_guardrail": "...", "applicability": "..."}'
            "\n不变量列表：\n" + highlights
        )
        try:
            value = _extract_json(_content(self.req_consolidate(prompt)))
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

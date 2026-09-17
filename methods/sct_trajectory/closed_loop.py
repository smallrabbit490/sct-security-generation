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


def _node_from_distilled(d: dict) -> SecurityInvariantNode | None:
    """把 Distillation 输出的候选经验转成 SecurityInvariantNode（暂存 provisional）。"""
    if not d.get("high_level_invariant") or not d.get("positive_principle"):
        return None
    node = SecurityInvariantNode(
        invariant_id=f"cand-{d.get('cwe','')}-{abs(hash(d.get('high_level_invariant','')))}",
        cwe=str(d.get("cwe", "")),
        high_level_invariant=str(d["high_level_invariant"]),
        applicability=str(d.get("applicability", "")),
        positive_principle=str(d["positive_principle"]),
        negative_guardrail=str(d.get("negative_guardrail", "")),
        status="provisional",
    )
    node.language_leaves["python"] = LanguageLeaf("python", [], [], "")
    return node


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
    ) -> None:
        self.requester = requester
        self.tree = tree
        self.ledger = ledger
        self.timeout = timeout
        self.workers = max(1, int(workers))
        self.progress = progress or (lambda msg: None)
        self.candidates: list[SecurityInvariantNode] = []
        self.traces: list[RolloutTrace] = []
        self.last_schedule: dict[str, Any] = {}

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
        """处理单个 source 任务（无副作用，可并发）：提取 seed + 从零生成 + 验证。"""
        entry: dict[str, Any] = {
            "task_id": row.get("index"), "cwe": str(row.get("CWE_ID", "")),
            "outcome": "", "card_id": "", "_card": None, "_failure": "",
            "state_first": "", "state_after_repair": "",
            "evidence_first": None, "evidence_after_repair": None,
        }
        try:
            card = extract_initial_hypothesis(row, self.requester)
            entry["card_id"] = card.get("id", "")
            entry["_card"] = card
            task = row.get("task_description") or {}
            pipeline = run_pipeline(
                task, [{"polarity": "positive", "principle": card.get("principle", "")}],
                requester=self.requester, reference_code="",
            )
            code = (pipeline.get("code") or "").strip()
            if not code:
                entry["outcome"] = "seed_grounding_failure"
                entry["_failure"] = "empty_code"
                return entry
            ev1, state = validate_and_state(row, code, timeout=self.timeout)
            # 落盘第 1 轮验证明细（compile/functional/security），供人工核对动态测试确实跑了
            entry["state_first"] = state
            entry["evidence_first"] = {
                "syntax_or_compile": (ev1.get("syntax_or_compile") or {}).get("status"),
                "functional": (ev1.get("functional") or {}).get("status"),
                "security": (ev1.get("security") or {}).get("status"),
                "functional_detail": str((ev1.get("functional") or {}).get("details"))[:200],
                "security_detail": str((ev1.get("security") or {}).get("details"))[:200],
            }
            if state == "A":
                entry["outcome"] = "seed_active"
                return entry
            repaired = self._repair_once(row, code)
            if repaired:
                ev2, state2 = validate_and_state(row, repaired, timeout=self.timeout)
                entry["state_after_repair"] = state2
                entry["evidence_after_repair"] = {
                    "syntax_or_compile": (ev2.get("syntax_or_compile") or {}).get("status"),
                    "functional": (ev2.get("functional") or {}).get("status"),
                    "security": (ev2.get("security") or {}).get("status"),
                    "functional_detail": str((ev2.get("functional") or {}).get("details"))[:200],
                    "security_detail": str((ev2.get("security") or {}).get("details"))[:200],
                }
                if state2 == "A":
                    entry["outcome"] = "seed_active_after_repair"
                    return entry
            entry["outcome"] = "seed_grounding_failure"
            entry["_failure"] = state
            return entry
        except Exception as exc:
            entry["outcome"] = "seed_error"
            entry["error"] = type(exc).__name__
            entry["_failure"] = type(exc).__name__
            return entry

    def _merge_phase1(self, entry: dict) -> None:
        """串行合并：达 A 入树（active），否则错题本 seed_grounding_failure（严禁入树）。"""
        card = entry.get("_card")
        if entry.get("outcome") in ("seed_active", "seed_active_after_repair") and card:
            self.tree.insert_node(_seed_node_from_card(card))
            return
        self.ledger.add(ErrorEntry(
            cwe=str(entry.get("cwe", "")),
            kind="seed_grounding_failure",
            failure_type=str(entry.get("_failure") or "unknown"),
            source_hash=str(entry.get("task_id", "")),
            transition="",
        ))

    def phase1_seed(self, source_tasks: list[dict], *, repairs: int = 1, on_item: Callable[[dict], None] | None = None) -> dict:
        """Phase 1：并发处理 + 流式合并入树（严格二分分流）。

        on_item(clean_entry)：每完成一条即回调（供 CLI 逐条落盘），在消费线程串行
        调用，与 _merge_phase1 同线程，保证树/错题本写入安全。
        """
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
        return {"results": results, "tree_size": sum(len(f.invariants) for f in self.tree.all_families())}

    def _repair_once(self, row: dict, code: str) -> str:
        """单轮任务内修复：把上一轮代码作为参考再走一次四步流水线。"""
        task = row.get("task_description") or {}
        pipeline = run_pipeline(task, [], requester=self.requester, reference_code=code)
        return (pipeline.get("code") or "").strip()

    # ---------- Phase 2：进化 ----------

    def _phase2_one(self, row: dict, retriever: HskTreeRetriever, repairs: int) -> dict:
        """处理单个 replay 任务（无副作用，可并发）：rollout + Distillation。"""
        try:
            trace = self._run_rollout(row, retriever, repairs=repairs)
            distilled = distill_trace(trace, self.requester)
            return {"task_id": row.get("index"), "trace": trace, "distilled": distilled, "error": None}
        except Exception as exc:
            return {"task_id": row.get("index"), "trace": None, "distilled": None, "error": type(exc).__name__}

    def phase2_evolve(self, replay_pool: list[dict], *, batch_size: int = 24, replay_limit: int = 96, repairs: int = 1, on_item: Callable[[dict], None] | None = None) -> dict:
        """Phase 2：主动回放调度 → 并发 rollout + 蒸馏 → 流式合并候选与错题本。"""
        retriever = HskTreeRetriever(self.tree, requester=self.requester)
        sched = schedule_replay(self.tree, self.ledger, replay_pool, self.requester,
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
                for d in distilled["positive"]:
                    node = _node_from_distilled(d)
                    if node:
                        self.candidates.append(node)
                        state["positive"] += 1
                state["negative"] += len(distilled["negative"])
                for item in distilled["error_ledger"]:
                    self.ledger.add(ErrorEntry(
                        cwe=item.get("cwe", ""), kind=item.get("kind", "stalled"),
                        failure_type=str(item.get("blind_spot") or "stalled")[:60],
                        source_hash=str(out.get("task_id", "")),
                        transition=str(item.get("kind", "")),
                    ))
                    state["ledger"] += 1
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
        on_phase2_item: Callable[[dict], None] | None = None,
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
            self.progress(f"[轮{rnd}] 开始：候选 replay {len(pool)} 条，树 active "
                          f"{sum(1 for f in self.tree.all_families() for n in f.invariants if n.status=='active')} 节点")
            self.candidates = []          # 每轮重置候选池，审计完即清
            p2 = self.phase2_evolve(
                pool, batch_size=batch_size, replay_limit=replay_limit,
                repairs=repairs, on_item=on_phase2_item,
            )
            # 记录本轮被消费的 replay 任务，后续轮次不再重复
            for row in pool:
                used.add(int(row.get("index", -1)))
            chosen = {int(t["task_id"]) for t in p2["traces"]}
            remaining = [row for row in remaining if int(row.get("index", -1)) not in chosen]

            # 本轮立即审计（用真实 audit 任务算 ΔJointPass）
            hpass = [{"cwe": t["cwe"], "task_id": t["task_id"]} for t in p2["traces"] if t["states"][-1:] == ["A"]]
            p3 = self.phase3_audit(
                audit_pool, audit_per_candidate=audit_per_candidate,
                regression_samples=regression_samples, hpass_traces=hpass,
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
                "gated": len(p3["gate_records"]),
                "promoted": promoted,
                "merged": p3["merged"],
                "pruned": p3["pruned"],
                "tree_nodes": sum(len(f.invariants) for f in self.tree.all_families()),
            })
            self.progress(f"[轮{rnd}] 完成：选中 {p2['selected']}，候选 {p2['positive_candidates']}，"
                          f"晋升 {promoted}，归并 {p3['merged']}，树 {rounds_log[-1]['tree_nodes']} 节点")

        return {
            "rounds": rounds_log,
            "gate_records": all_gate_records,
            "audit_detail": all_audit_detail,
            "traces": [t.to_dict() for t in self.traces],
        }

    def _run_rollout(self, row: dict, retriever: HskTreeRetriever, *, repairs: int = 1) -> RolloutTrace:
        """单任务多轮 rollout：四步生成 → 验证四态 → 失败后有限修复。

        落盘审计信息：每轮检索到的经验 id/LLM 分（retrieved_per_round）与修复轮的
        局部代码差分（patch_diffs），供人工核对检索与局部补丁是否真的生效。
        """
        from .agent_pipeline import compute_patch_diff

        task = row.get("task_description") or {}
        query = {**task, "CWE_ID": row.get("CWE_ID"), "language": "python"}
        states: list[str] = []
        codes: list[str] = []
        evidence_list: list[dict] = []
        retrieved_per_round: list[list[dict]] = []
        patch_diffs: list[str] = []
        reference = ""
        for _ in range(repairs + 1):
            cards = retriever.search(query, limit=3) or []
            retrieved_per_round.append([
                {"invariant_id": c.get("invariant_id"), "llm_score": c.get("_llm_score"),
                 "base_score": c.get("_base_score"), "utility": c.get("utility")}
                for c in cards
            ])
            pipeline = run_pipeline(task, cards, requester=self.requester, reference_code=reference)
            code = (pipeline.get("code") or "").strip()
            patch_diffs.append(pipeline.get("patch_diff") or "")
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
            family_id=str(row.get("family_id", "")), language="python",
            states=states, transitions=transitions, generated_codes=codes, evidence=evidence_list,
            retrieved_per_round=retrieved_per_round, patch_diffs=patch_diffs,
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
                pipeline = run_pipeline(task, cards, requester=self.requester, reference_code="")
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
    ) -> dict:
        """Phase 3：候选经验在真实 D_audit 任务上做三层门控 → supported 入树 → 归并/剪枝。

        真实实现（替换此前的占位版本）：
          Gate1 召回探针：把候选临时并入检索范围，用真实 audit 任务检验能否召回 Top-3；
          Gate2 独立有效性：在同 CWE 的 audit 任务上做「基线 vs 加入候选」两次生成+验证，
            真实计算 ΔJointPass = JointPass(加候选) − JointPass(基线)；
          Gate3 降噪回归：对历史 H_pass 任务用 N=3 采样多数决重跑，统计安全/功能回归。
        """
        retriever = HskTreeRetriever(self.tree, requester=None)
        records: list[dict] = []
        audit_detail: list[dict] = []

        # 按 CWE 分组 audit 任务，便于同 CWE 抽样
        by_cwe: dict[str, list[dict]] = {}
        for row in audit_tasks:
            by_cwe.setdefault(str(row.get("CWE_ID")), []).append(row)

        for cand in self.candidates:
            same_cwe = by_cwe.get(str(cand.cwe), [])[:audit_per_candidate]
            detail: dict[str, Any] = {
                "candidate_id": cand.invariant_id, "cwe": cand.cwe,
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
            detail["gate1_retrieved"] = rec.gate1_retrieved
            detail["decision"] = rec.decision
            detail["reasons"] = rec.reasons
            records.append(rec.to_dict())
            audit_detail.append(detail)

            if rec.decision == "supported":
                family = self.tree.ensure_family(cand.cwe)
                absorb_or_new(family, cand)

        merged = 0
        for fam in self.tree.all_families():
            if consolidate_family(fam, consolidator=self._llm_consolidate) is not None:
                merged += 1
        pruned = sum(prune_by_utility(fam) for fam in self.tree.all_families())
        self.progress(f"[Phase3] 候选 {len(self.candidates)} 审计完成，归并 {merged}，剪枝 {pruned}")
        return {"gate_records": records, "audit_detail": audit_detail, "merged": merged, "pruned": pruned}

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
            value = _extract_json(_content(self.requester(prompt)))
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

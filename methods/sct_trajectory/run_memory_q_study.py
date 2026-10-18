"""固定库Q研究入口：离线材料检查、D_grow校准、D_gate三臂冻结比较。

正文和资格不变，不调用经验提炼/门控；最终Base/Plus不进入此入口。
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager, nullcontext
import json
from pathlib import Path
from statistics import quantiles
from time import perf_counter

from methods.sct_trajectory.context_pipeline import analysis_prompt, run_context_pipeline, safe_feedback
from methods.sct_trajectory.cost_tracker import CostTracker
from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode
from methods.sct_trajectory.memory_q import update_adopted
from methods.sct_trajectory.retriever import HskTreeRetriever


POLICIES = ("semantic_llm", "semantic_sim", "semantic_q")
ROOT = Path(__file__).resolve().parents[2]


def prepare_initial_analysis(row, requester):
    """只用公开契约准备共同c0初析；无隐藏答案，不执行代码或写记忆。"""
    from methods.sct_trajectory.agent_pipeline import _content, _extract_json
    from methods.sct_trajectory.english_policy import assert_english_text
    value = _extract_json(_content(requester(analysis_prompt(row["task_description"]))))
    if not isinstance(value, dict) or not all(isinstance(value.get(k), list) and value[k]
            for k in ("vulnerability_hypothesis", "functional_invariants")):
        raise ValueError("invalid_shared_initial_analysis")
    assert_english_text(json.dumps(value, ensure_ascii=False), context="initial_analysis")
    return value


def _content_snapshot(nodes):
    """固定库阶段只允许Q变化；沿用节点序列化比较其余内容，无额外哈希层。"""
    return [{k: v for k, v in node.to_dict().items() if k not in ("q_value", "q_visits")} for node in nodes]


def _measurement_record(evidence):
    """研究记录只保存测量状态与错误类别，不复制隐藏用例、答案或异常正文。"""
    result = {key: {k: item[k] for k in ("status", "measured", "error_type") if k in item}
              for key in ("functional", "security", "syntax_or_compile")
              if isinstance(item := evidence.get(key), dict)}
    if evidence.get("error"):
        result["error"] = evidence["error"]
    result["metadata"] = {key: evidence.get("metadata", {})[key]
                          for key in ("dynamic_test", "backend") if key in evidence.get("metadata", {})}
    return result


class FixedMemoryQStudy:
    """顺序执行固定库实验；实际采用后更新Q，比较阶段完全只读。"""

    def __init__(self, nodes, requester, embedding_client, *, delta, lambda_q=0.5,
                 alpha=0.3, validation_timeout=20, validator=None, cost_tracker=None):
        self.nodes = nodes
        self.by_id = {n.invariant_id: n for n in nodes}
        self.requester = requester
        self.embedding_client = embedding_client
        self.delta, self.lambda_q, self.alpha = delta, lambda_q, alpha
        self.validation_timeout = validation_timeout
        self.cost_tracker = cost_tracker
        self.cost_scopes = {}
        if validator is None:
            from methods.sct_trajectory.closed_loop import validate_and_state
            validator = validate_and_state
        self.validator = validator

    @contextmanager
    def cost_scope(self, name):
        """顺序探针按实验臂归集用量和耗时；共同初析/门槛准备单列，不重复分摊。"""
        tracker = self.cost_tracker
        label = f"{tracker.current_stage()}.{name}" if tracker else name
        bucket = self.cost_scopes.setdefault(name, {
            "llm_label": label + ".memory_q", "elapsed_seconds": 0.0, "embedding": {}})
        before = self.embedding_client.usage
        started = perf_counter()
        try:
            with tracker.stage_scope(label) if tracker else nullcontext():
                yield
        finally:
            bucket["elapsed_seconds"] += perf_counter() - started
            for key, value in self.embedding_client.usage.items():
                bucket["embedding"][key] = bucket["embedding"].get(key, 0) + value - before.get(key, 0)

    def cost_breakdown(self):
        """导出各臂实际增量；embedding冷缓存准备保留在共享项，不估算其货币账单。"""
        labels = self.cost_tracker.snapshot()["by_label"] if self.cost_tracker else {}
        scopes = {name: {"llm": labels.get(item["llm_label"], {}),
                         "embedding": item["embedding"],
                         "elapsed_seconds": round(item["elapsed_seconds"], 6)}
                  for name, item in self.cost_scopes.items()}
        return {"by_policy": {name: item for name, item in scopes.items() if name in POLICIES},
                "shared": {name: item for name, item in scopes.items() if name not in POLICIES}}

    def _run_task(self, row, policy, *, learn, initial_analysis=None):
        retriever = HskTreeRetriever(HskTree(), requester=self.requester,
            retrieval_mode=policy, embedding_client=self.embedding_client,
            semantic_delta=self.delta, lambda_q=self.lambda_q)
        task = row["task_description"]
        reference, previous, attempts, events = "", None, [], []
        for attempt in range(2):
            def cards_provider(query):
                return retriever.search({**query, "CWE_ID": row["CWE_ID"], "language": "python",
                                         "task_id": row["index"]}, pool_nodes=self.nodes)
            pipeline = run_context_pipeline(task, [], requester=self.requester,
                reference_code=reference, previous_evidence=previous, cards_provider=cards_provider,
                initial_analysis=initial_analysis if attempt == 0 else None)
            code = (pipeline["code"] or "").strip()
            if code:
                try:
                    evidence, state = self.validator(row, code, timeout=self.validation_timeout)
                except (OSError, TimeoutError, RuntimeError) as exc:
                    evidence, state = {"error": type(exc).__name__}, "U"
            else:
                evidence, state = {"error": "empty_code"}, "D"
            adopted = [c["invariant_id"] for c in pipeline["cards"]]
            attempts.append({"attempt": attempt, "code": code, "state": state,
                "evidence": _measurement_record(evidence), "adopted_ids": adopted,
                "retrieved_ids": [c["invariant_id"] for c in pipeline["retrieved_cards"]],
                "adoption": pipeline["adoption"], "initial_analysis": pipeline["initial_analysis"],
                "pipeline_error": pipeline["error_type"], "workflow_completed": pipeline["workflow_completed"],
                "retrieval_trace": retriever.last_hier_trace})
            if learn:
                # 更新在A早停前；每次c0/c1只认该次pipeline.cards，不使用召回候选。
                # 技术降级仍保留代码实测成绩，但不把失败的前向流程授予Q信用。
                learning_evidence = {"error": "pipeline_error"} if pipeline["error_type"] else evidence
                for event in update_adopted(self.by_id, adopted, learning_evidence, code=code,
                                            pool="D_grow", alpha=self.alpha):
                    events.append({"task_id": row["index"], "family_id": row["family_id"],
                        "pool": "D_grow", "outer_round": 0, "attempt": attempt,
                        "selection_policy": policy, **event})
            if state == "A" or not code:
                break
            reference, previous = code, safe_feedback(evidence)
        final = attempts[-1]
        return {"task_id": row["index"], "family_id": row["family_id"], "policy": policy,
                "pool": "D_grow" if learn else "D_gate", "attempts": attempts, "q_events": events,
                "state": final["state"], "first_state": attempts[0]["state"]}

    def calibrate(self, rows, *, initial_analyses=None, on_result=None):
        """仅D_grow用共同相似度曝光学习Q；正文/状态不得变化，不让Q改变曝光。"""
        before = _content_snapshot(self.nodes)
        results = []
        for row in rows:
            with self.cost_scope("semantic_sim"):
                result = self._run_task(row, "semantic_sim", learn=True,
                    initial_analysis=(initial_analyses or {}).get(str(row["index"])))
            results.append(result)
            if on_result:
                on_result(result)
        if _content_snapshot(self.nodes) != before:
            raise RuntimeError("fixed_memory_content_changed_during_calibration")
        return results

    def compare(self, rows, *, on_result=None):
        """三组使用同一冻结库；每题轮换组顺序，所有比较反馈均不回流Q。"""
        before = [node.to_dict() for node in self.nodes]
        results = []
        for index, row in enumerate(rows):
            with self.cost_scope("shared_initial"):
                initial = prepare_initial_analysis(row, self.requester)
            shift = index % len(POLICIES)
            for policy in POLICIES[shift:] + POLICIES[:shift]:
                with self.cost_scope(policy):
                    result = self._run_task(row, policy, learn=False, initial_analysis=initial)
                results.append(result)
                if on_result:
                    on_result(result)
        if [node.to_dict() for node in self.nodes] != before:
            raise RuntimeError("frozen_memory_changed_during_comparison")
        return results


def load_inputs(memory_path, dataset_path, family_path, pools_path=None):
    """读取真实库与既有三/四池清单；验证任务及family隔离，不自行重划数据。"""
    raw = [json.loads(line) for line in memory_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    nodes = [SecurityInvariantNode.from_dict(r) for r in raw]
    if not nodes or len({n.invariant_id for n in nodes}) != len(nodes):
        raise ValueError("memory_must_have_unique_nonempty_ids")
    if any(not n.invariant_id for n in nodes):
        raise ValueError("empty_memory_id")
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    families = json.loads(family_path.read_text(encoding="utf-8"))["row_classification"]
    by_id = {str(r["index"]): {**r, "family_id": families[str(r["index"])]["seed_family_id"]} for r in data}
    source_ids = {str(n.source["task_id"]) for n in nodes}
    if any(n.source.get("stage") != "phase1" for n in nodes):
        raise ValueError("fixed_M0_requires_phase1_memory")
    if any(i not in by_id for i in source_ids):
        raise ValueError("source_task_not_in_dataset")
    pools = None
    if pools_path is not None:
        manifest = json.loads(pools_path.read_text(encoding="utf-8"))
        # 两种均为仓库已有格式：运行pools.json与固定四池manifest。
        entries = manifest.get("pools")
        if entries is None:
            entries = {new: manifest[old] for new, old in
                       (("D_init", "source"), ("D_grow", "replay"), ("D_gate", "audit"))}
        pools = {name: [str(e["task_id"]) for e in values] for name, values in entries.items()}
        for required in ("D_init", "D_grow", "D_gate"):
            if not pools.get(required):
                raise ValueError(f"missing_nonempty_pool:{required}")
        owners, family_owners = {}, {}
        for name, identifiers in pools.items():
            for identifier in identifiers:
                family = by_id[identifier]["family_id"]
                if identifier in owners or (family in family_owners and family_owners[family] != name):
                    raise ValueError("pool_task_or_family_overlap")
                supplied = next(e for e in entries[name] if str(e["task_id"]) == identifier)
                if supplied.get("family_id") and supplied["family_id"] != family:
                    raise ValueError("pool_family_mismatch")
                owners[identifier], family_owners[family] = name, name
        if not source_ids <= set(pools["D_init"]):
            raise ValueError("M0_sources_outside_D_init")
    return nodes, by_id, pools


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def _write_memory(path, nodes):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for node in nodes:
            f.write(json.dumps(node.to_dict(), ensure_ascii=False) + "\n")


def _summarize(rows):
    by_policy = {}
    for policy in POLICIES:
        selected = [r for r in rows if r["policy"] == policy]
        if not selected:
            continue
        metrics = Counter()
        for row in selected:
            evidence = row["attempts"][-1]["evidence"]
            f = evidence.get("functional", {}).get("status")
            s = evidence.get("security", {}).get("status")
            metrics.update(functional_pass=int(f == "pass"), security_pass=int(s == "pass"),
                           joint_pass=int(f == s == "pass"), unmeasured=int(f not in ("pass", "fail") or s not in ("pass", "fail")),
                           first_joint=int(row["first_state"] == "A"),
                           pipeline_errors=sum(bool(a["pipeline_error"]) for a in row["attempts"]))
        by_policy[policy] = {"n": len(selected), **dict(metrics)}
    paired = {}
    by_task = {}
    for row in rows:
        by_task.setdefault(str(row["task_id"]), {})[row["policy"]] = row
    complete = [r for r in by_task.values() if set(r) == set(POLICIES)]
    if complete:
        wins = sum(r["semantic_q"]["state"] == "A" and r["semantic_sim"]["state"] != "A" for r in complete)
        losses = sum(r["semantic_q"]["state"] != "A" and r["semantic_sim"]["state"] == "A" for r in complete)
        from math import comb
        discordant = wins + losses
        p = min(1.0, 2 * sum(comb(discordant, k) for k in range(min(wins, losses)+1)) / 2**discordant) if discordant else 1.0
        paired = {"comparison": "semantic_q - semantic_sim", "n": len(complete), "wins": wins,
                  "losses": losses, "delta_joint": (wins-losses)/len(complete), "mcnemar_exact_p": p,
                  "first_selection_set_changed": sum(set(r["semantic_q"]["attempts"][0]["retrieved_ids"]) !=
                      set(r["semantic_sim"]["attempts"][0]["retrieved_ids"]) for r in complete),
                  "family_clusters": len({r["semantic_q"]["family_id"] for r in complete}),
                  "inference": "development_probe; family uncertainty/confirmatory analysis pending"}
    return {"by_policy": by_policy, "paired": paired}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("offline", "calibrate", "compare"), required=True)
    parser.add_argument("--memory", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pools", type=Path, help="原运行pools.json或固定四池manifest，不自动生成")
    parser.add_argument("--dataset", type=Path, default=ROOT/"data/external/secodeplt/secodeplt/data.json")
    parser.add_argument("--family-manifest", type=Path, default=ROOT/"data/external/secodeplt/derived_metadata/family_manifest.json")
    parser.add_argument("--calibration", type=Path, help="compare必须读取calibrate生成的calibration.json")
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--embedding-model", default="text-embedding-3-small")
    parser.add_argument("--embedding-cache", type=Path, default=ROOT/"translation_work/cache/memory_q/embedding.sqlite")
    parser.add_argument("--limit", type=int, default=24, help="按task_id预先固定的每池探针题数")
    parser.add_argument("--delta", type=float, help="已由学习区校准的门槛；calibrate省略时计算80%%分位")
    parser.add_argument("--alpha", type=float, default=0.3)
    parser.add_argument("--lambda-q", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--validation-timeout", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=1500)
    args = parser.parse_args(argv)
    # 三臂采用同一非思考服务配置，避免中转站默认思考挤占结构化输出预算。
    args.thinking = "disabled"
    if args.limit < 1 or not 0 < args.alpha <= 1 or not 0 <= args.lambda_q <= 1:
        parser.error("limit/alpha/lambda-q超出允许范围")
    if args.stage != "offline" and args.pools is None:
        parser.error("真实校准/比较需要--pools原始清单；不会自动重划或使用最终测试")
    if args.stage == "compare" and args.calibration is None:
        parser.error("compare需要--calibration，锁定学习来源、Q快照及选择配置")
    if args.delta is not None and not -1 <= args.delta <= 1:
        parser.error("delta必须为[-1,1]中的有限余弦值")
    nodes, by_id, pools = load_inputs(args.memory, args.dataset, args.family_manifest, args.pools)
    from methods.sct_lifecycle_replay.freeze_protocol import build_freeze_metadata
    calibration = None
    if args.stage == "calibrate" and any(n.q_visits or n.q_value for n in nodes):
        parser.error("calibrate需要未学习的M0；本批不提供续跑或自动重置")
    if args.stage == "compare":
        calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
        for key in ("model", "embedding_model", "lambda_q", "thinking"):
            if calibration[key] != getattr(args, key):
                parser.error(f"compare配置与校准不一致:{key}")
        expected = build_freeze_metadata([n.to_dict() for n in nodes], args.model, "semantic_q", "fixed")
        if expected["memory_sha256"] != calibration["memory_sha256"] or pools != calibration["pool_ids"]:
            parser.error("compare经验/Q快照或原池清单与校准不一致")
        if args.delta is not None and args.delta != calibration["delta"]:
            parser.error("compare不得重新选择delta")
        args.delta = calibration["delta"]

    # 新目录拒绝覆盖既有实验；--help及输入失败在创建目录/客户端之前结束。
    args.out.mkdir(parents=True, exist_ok=False)
    _write_memory(args.out/"input_memory.jsonl", nodes)
    from methods.sct_trajectory.run_artifacts import write_run_metadata
    write_run_metadata(args.out, model=args.model, args=vars(args), dataset=str(args.dataset))
    metadata_path = args.out/"run_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata.update(experiment="cle-fixed-memory-q-v1", workers=1,
        output_schema=["input_memory.jsonl", "rows.jsonl", "memory_q_events.jsonl", "summary.json", "cost.json", "report.md"],
        feedback_boundaries={"calibrate": "D_grow Q only", "compare": "D_gate read only",
                             "Base/Plus": "not accepted by this runner"})
    _write_json(metadata_path, metadata)
    from methods.sct_trajectory.semantic_retrieval import MAX_CARD_CHARS, card_embedding_text
    summary = {"stage": args.stage, "memory_entries": len(nodes), "source_tasks": len({n.source["task_id"] for n in nodes}),
               "statuses": dict(Counter(n.status for n in nodes)), "workers": 1,
               "q_nonzero": sum(n.q_value != 0 for n in nodes), "q_visited": sum(n.q_visits > 0 for n in nodes),
               "embedding_budget_excluded": sum(len(card_embedding_text(n)) > MAX_CARD_CHARS for n in nodes),
               "ready_for_calibration": pools is not None,
               "missing_inputs": ["原始pools.json或固定池manifest；当次无密钥配置仍需人工核对"] if pools is None else [],
               "model_calls_this_run": 0, "performance_measured": False}
    if args.stage == "offline":
        metadata["summary"] = summary
        metadata["output_schema"] = ["input_memory.jsonl", "summary.json", "report.md", "run_metadata.json"]
        _write_json(metadata_path, metadata)
        _write_json(args.out/"summary.json", summary)
        (args.out/"report.md").write_text("# 固定库Q离线核验\n\n" +
            f"真实经验{len(nodes)}张；源任务{summary['source_tasks']}个。未调用模型、embedding或任务执行器。\n\n" +
            "缺项：" + ("；".join(summary["missing_inputs"]) or "池级输入已验证；运行模型与预算须按任务书确认") + "\n",
            encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
        return summary

    # 仅真实运行阶段构造现有客户端；offline无需凭据，也不会创建向量缓存。
    from methods.sct_trajectory.run_closed_loop import _requester
    from methods.sct_lifecycle_replay.chatanywhere_smoke import load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient, recall_semantic_candidates
    tracker = CostTracker(args.model)
    raw_requester = _requester(args.model, args.timeout, args.max_tokens, max_inflight=1,
                               selector_max_inflight=1, thinking=args.thinking)
    def request(prompt):
        try:
            response = raw_requester(prompt)
        except Exception:
            tracker.record_error("memory_q")
            raise
        tracker.record("memory_q", response)
        return response
    embedding = EmbeddingClient(model=args.embedding_model, cache_path=args.embedding_cache,
                                key_loader=load_key, timeout=args.timeout)
    study = FixedMemoryQStudy(nodes, request, embedding, delta=args.delta, lambda_q=args.lambda_q,
                             alpha=args.alpha, validation_timeout=args.validation_timeout, cost_tracker=tracker)
    try:
        pool_name = "D_grow" if args.stage == "calibrate" else "D_gate"
        tasks = [by_id[i] for i in sorted(pools[pool_name], key=int)[:args.limit]]
        initial = {}
        tracker.set_stage(args.stage)
        if args.stage == "calibrate" and args.delta is None:
            similarities = []
            with study.cost_scope("shared_threshold"), \
                 (args.out/"prepared_queries.jsonl").open("w", encoding="utf-8") as prepared:
                for row in tasks:
                    analysis = prepare_initial_analysis(row, request)
                    initial[str(row["index"])] = analysis
                    query = {**row["task_description"], "CWE_ID": row["CWE_ID"], "language": "python",
                             "threat_analysis": analysis, "current_code": "", "failure_evidence": {}}
                    trace = {"excluded": [], "candidate_ids": [], "scores": []}
                    _, _, scores = recall_semantic_candidates(query, nodes, embedding, 3, trace)
                    similarities.extend(s["cosine"] for s in scores)
                    prepared.write(json.dumps({"task_id": row["index"], "initial_analysis": analysis}, ensure_ascii=False)+"\n")
                    prepared.flush()
            if len(similarities) < 2:
                raise ValueError("insufficient_learning_cosines_to_calibrate_delta")
            args.delta = quantiles(similarities, n=5, method="inclusive")[3]
        study.delta = args.delta
        with (args.out/"rows.jsonl").open("w", encoding="utf-8") as rows_file, \
             (args.out/"memory_q_events.jsonl").open("w", encoding="utf-8") as event_file:
            def save(result):
                rows_file.write(json.dumps({k: v for k, v in result.items() if k != "q_events"}, ensure_ascii=False)+"\n")
                rows_file.flush()
                for event in result["q_events"]:
                    event_file.write(json.dumps(event, ensure_ascii=False)+"\n")
                event_file.flush()
            results = (study.calibrate(tasks, initial_analyses=initial, on_result=save) if args.stage == "calibrate"
                       else study.compare(tasks, on_result=save))
        if args.stage == "calibrate":
            _write_memory(args.out/"frozen/m_star_q.jsonl", nodes)
            calibration = build_freeze_metadata([n.to_dict() for n in nodes], args.model, "semantic_q", "fixed")
            calibration.update(embedding_model=args.embedding_model, delta=args.delta, lambda_q=args.lambda_q,
                               alpha=args.alpha, thinking=args.thinking, pool_ids=pools, learning_ids=[r["index"] for r in tasks],
                               memory_entries=len(nodes))
            _write_json(args.out/"calibration.json", calibration)
        summary.update(_summarize(results), delta=args.delta, performance_measured=True,
                       q_nonzero=sum(n.q_value != 0 for n in nodes), q_visited=sum(n.q_visits > 0 for n in nodes),
                       model_calls_this_run=tracker.snapshot()["total"]["calls"])
        _write_json(args.out/"summary.json", summary)
        metadata["args"]["delta"] = args.delta
        metadata["summary"] = summary
        if args.stage == "calibrate":
            metadata["output_schema"] += ["prepared_queries.jsonl (when calibrating delta)", "calibration.json", "frozen/m_star_q.jsonl"]
        _write_json(metadata_path, metadata)
        (args.out/"report.md").write_text("# 固定库Q开发诊断\n\n" +
            "阶段：" + args.stage + "。仅PLT训练/开发侧结果，不是独立Base/Plus结论。\n\n" +
            "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False))
        return summary
    finally:
        _write_json(args.out/"cost.json", {"llm": tracker.snapshot(), "embedding": embedding.usage,
            **study.cost_breakdown(),
            "accounting": "Sequential actual usage; shared preparation charged once. LLM currency uses the repository price table; embedding currency and provider invoice are not measured. Elapsed time includes retrieval, generation and validation."})


if __name__ == "__main__":
    main()

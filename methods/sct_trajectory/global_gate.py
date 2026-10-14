"""Phase3 训练 D_gate 全量配对门控与有限采样归因。

输入仅为训练侧任务和检索/单次生成/验证回调；输出三臂逐任务记录、逐卡移除
证据及停用建议。本模块不修改长期库，不读取 Base/Plus，不执行修复或测试驱动
选码。D_init/D_grow 的经验必须由调用方先冻结；H_pass 回归不由本模块冒充完成。
缺测与调用/基础设施异常不能转成有害经验。停用只影响调用方新建的库副本；
过滤后仍在同一 D_gate 测量，存在选择偏差，不能作为独立泛化效果。
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
import math
import time
from typing import Any, Callable


_TRANSIENT_CARD_FIELDS = {"score", "llm_score", "rule_score", "rank", "retrieval_rank",
                          "retrieval_reason", "retrieval_score", "selection_reason",
                          "_base_score", "_llm_score", "_llm_reason", "_align_error",
                          "retrieval_audit", "_relevance_gate"}
_INFRA_ERRORS = {"environment_error", "validator_exception", "validation_error", "api_error",
                "generation_error", "retrieval_error", "missing_harness", "harness_missing",
                "infrastructure_error", "not_measured", "unmeasured", "parse_error",
                "plt_validator_exception", "local_worker_error"}


def _card_id(card: dict) -> str:
    """Phase3 从经验快照取稳定 ID；缺 ID 抛错，不修改库。"""
    for key in ("id", "invariant_id", "experience_id", "entry_id"):
        if card.get(key) is not None and str(card[key]):
            return str(card[key])
    raise ValueError("experience card requires stable id")


def _digest(value: Any) -> str:
    """对实际注入卡片建立确定性版本证据；不可序列化时失败，不改库。"""
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _snapshot(cards: list[dict]) -> list[dict]:
    """记录 Phase3 卡片顺序、全文及版本；检索分数变化不等于正文版本变化。"""
    result = []
    seen = set()
    for order, card in enumerate(cards):
        identity = _card_id(card)
        if identity in seen:
            raise ValueError("duplicate experience id in retrieval")
        seen.add(identity)
        version = {key: value for key, value in card.items() if key not in _TRANSIENT_CARD_FIELDS}
        result.append({"id": identity, "order": order, "card": deepcopy(card),
                       "sha256": _digest(card), "version_sha256": _digest(version)})
    return result


def _contains_infra_error(value: Any) -> bool:
    """区分测试失败和基础设施失败；只读证据树，缺测由 measurement 另行判断。"""
    if isinstance(value, dict):
        if value.get("measured") is False:
            return True
        for key, item in value.items():
            if key in {"error_type", "error", "status"} and isinstance(item, str):
                if item.lower() in _INFRA_ERRORS:
                    return True
            if isinstance(item, (dict, list)) and _contains_infra_error(item):
                return True
    elif isinstance(value, list):
        return any(_contains_infra_error(item) for item in value)
    return False


def _measurement(row: dict) -> tuple[bool, bool] | None:
    """Phase3 归因只接受 Function/Secure 两项完整实测；其他检查保留原证据。"""
    evidence = row.get("evidence") or {}
    relevant = {key: evidence[key] for key in ("functional", "security", "metadata", "error_type", "error") if key in evidence}
    if row.get("error_type") or _contains_infra_error(relevant):
        return None
    values = []
    for key in ("functional", "security"):
        item = evidence.get(key)
        if not isinstance(item, dict) or item.get("status") not in {"pass", "fail"}:
            return None
        values.append(item["status"] == "pass")
    return tuple(values)


def evidence_is_measured(evidence: dict, *, error_type: str | None = None) -> bool:
    """供 Phase2 分支与 Phase3 统一判断 Function/Secure 是否完整实测。

    输入原始验证证据和可选生成/验证错误类别，输出有效实测布尔值；测试失败
    可以是实测，worker/环境故障、缺测不可以。静态分析/类型检查等可选检查未测
    不影响已完成的动态 F/S。本函数只读取证据，不选择代码、不修改长期经验库。
    """
    return _measurement({"evidence": evidence, "error_type": error_type}) is not None


def _state(measurement: tuple[bool, bool] | None) -> str:
    """缺测保留 U，不折算成 B/C/D 来驱动经验停用。"""
    return {(True, True): "A", (True, False): "B", (False, True): "C", (False, False): "D"}.get(measurement, "U")


def _comparison(before: dict, after: dict) -> dict:
    """比较实测维度；B/C 互换同时含得失，必须进入冲突复核。"""
    left, right = _measurement(before), _measurement(after)
    comparable = left is not None and right is not None
    lost = [key for i, key in enumerate(("functional", "security")) if comparable and left[i] and not right[i]]
    gained = [key for i, key in enumerate(("functional", "security")) if comparable and not left[i] and right[i]]
    return {"comparable": comparable, "before": _state(left), "after": _state(right),
            "lost": lost, "gained": gained, "regression": bool(lost), "tradeoff": bool(lost and gained)}


def _supported(baseline: dict, full: dict, dropped: dict) -> bool:
    """重复归因：完整组合退步且移除后恢复 baseline 所有通过维度，才计一次支持。"""
    base, drop = _measurement(baseline), _measurement(dropped)
    if not _comparison(baseline, full)["regression"] or base is None or drop is None:
        return False
    return all(not base[i] or drop[i] for i in range(2))


def _evaluate(task: dict, cards: list[dict], arm: str, generate: Callable, validate: Callable) -> dict:
    """单次生成并验证，无修复；异常仅留类名避免凭据泄漏，完整测试证据由回调提供。"""
    started = time.monotonic()
    row = {"task_id": str(task.get("index", task.get("task_id", task.get("id")))),
           "phase": "phase3_global_gate", "arm": arm, "cards": deepcopy(cards),
           "retrieval_snapshot": _snapshot(cards), "code": "", "evidence": {},
           "error_type": None, "error_class": None}
    try:
        code = generate(deepcopy(task), deepcopy(cards))
        if not isinstance(code, str) or not code.strip():
            raise ValueError("empty or non-string generated code")
        row["code"] = code
    except Exception as exc:
        row.update(error_type="generation_error", error_class=type(exc).__name__)
    if row["error_type"] is None:
        try:
            result = validate(deepcopy(task), row["code"])
            if not isinstance(result, dict):
                raise TypeError("validation evidence must be dict")
            row["evidence"] = deepcopy(result)
        except Exception as exc:
            row.update(error_type="validation_error", error_class=type(exc).__name__)
    row["elapsed_seconds"] = time.monotonic() - started
    row["state"] = _state(_measurement(row))
    row["measured"] = _measurement(row) is not None
    return row


def _metrics(rows: list[dict]) -> dict:
    """汇总全量分母和完整可测量子集；未测量项不当成功，保持原始错误计数。"""
    measured = [value for row in rows if (value := _measurement(row)) is not None]
    counts = {"functional_pass": sum(v[0] for v in measured),
              "security_pass": sum(v[1] for v in measured),
              "joint_pass": sum(all(v) for v in measured)}
    return {"total": len(rows), "measured": len(measured), "unmeasured": len(rows) - len(measured),
            **counts, "rates": {key: value / len(rows) if rows else None for key, value in counts.items()},
            "measured_rates": {key: value / len(measured) if measured else None for key, value in counts.items()},
            "states": dict(Counter(row["state"] for row in rows)),
            "errors": dict(Counter(row["error_type"] for row in rows if row.get("error_type")))}


def run_global_gate(tasks: list[dict], retrieve: Callable, generate: Callable, validate: Callable,
                    *, workers: int = 1, confirmations: int = 2,
                    on_record: Callable | None = None, retrieve_filtered: Callable | None = None) -> dict:
    """在训练 D_gate 运行 Phase3 三臂与局部归因，返回可序列化审计产物。

    retrieve(task)->list[dict]；generate(task,cards)->str；validate(task,code)->dict，
    functional/security.status 必须实测 pass/fail。所有初始检索在生成前冻结。
    retrieve_filtered(task, retired_ids)->list[dict] 可从剩余库重新检索；未提供时
    重新调用 retrieve 后过滤停用 ID，并明确标记该模式不能补充排名后移的卡。
    on_record 在主线程接收 row/attribution/decision。callbacks 不得原地写长期库。
    默认两次追加 full/drop，连同首轮达到三次中至少两次支持才停用；正向冲突
    优先保留复核。显式 Base/Plus/非 D_gate 标记、重复任务、卡版本漂移抛错；
    API/检索/验证异常留痕而不作为有害证据。无 pool 的兼容调用须自行保证 D_gate。
    """
    if workers < 1 or confirmations < 2:
        raise ValueError("workers >= 1 and confirmations >= 2 required")
    tasks = deepcopy(list(tasks))
    task_ids = set()
    for task in tasks:
        identity = task.get("index", task.get("task_id", task.get("id")))
        if identity is None or str(identity) in task_ids:
            raise ValueError("tasks require unique stable ids")
        task_ids.add(str(identity))
        for field in ("subset", "split", "dataset", "benchmark"):
            if str(task.get(field, "")).lower() in {"base", "plus", "codesec_eval_base", "codesec_eval_plus", "codesec eval base", "codesec eval plus"}:
                raise ValueError("final Base/Plus tests cannot update training memory")
        if task.get("pool") and task["pool"] != "D_gate":
            raise ValueError("global gate accepts only training D_gate pool")

    def emit(kind: str, value: dict) -> None:
        if on_record is not None:
            on_record({"kind": kind, **deepcopy(value)})

    def map_jobs(jobs: list, function: Callable, completed: Callable | None = None) -> dict:
        output = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_keys = {pool.submit(function, job): key for key, job in enumerate(jobs)}
            for future in as_completed(future_keys):
                value = future.result()
                output[future_keys[future]] = value
                if completed is not None:
                    completed(value)
        return output

    def get_cards(task: dict) -> tuple[list[dict], str | None]:
        try:
            cards = deepcopy(list(retrieve(deepcopy(task))))
            _snapshot(cards)
            return cards, None
        except Exception as exc:
            return [], type(exc).__name__

    retrieval = map_jobs(tasks, get_cards)
    versions, card_records = {}, {}
    for index in range(len(tasks)):
        for snapshot in _snapshot(retrieval[index][0]):
            identity = snapshot["id"]
            if identity in versions and versions[identity] != snapshot["version_sha256"]:
                raise ValueError("experience version changed within frozen gate")
            versions[identity] = snapshot["version_sha256"]
            card_records.setdefault(identity, snapshot)

    rows = {"baseline": [], "memory": [], "filtered": []}
    def initial_pair(index: int) -> tuple[dict, dict]:
        task = tasks[index]
        cards, retrieval_error = retrieval[index]
        baseline = _evaluate(task, [], "baseline", generate, validate)
        if retrieval_error:
            memory = {**deepcopy(baseline), "arm": "memory", "code": "", "evidence": {},
                      "state": "U", "measured": False, "error_type": "retrieval_error",
                      "error_class": retrieval_error}
        else:
            memory = _evaluate(task, cards, "memory", generate, validate)
        return baseline, memory

    def record_pair(pair: tuple[dict, dict]) -> None:
        for row in pair:
            emit("row", row)

    initial = map_jobs(list(range(len(tasks))), initial_pair, record_pair)
    comparisons, positive_tasks, jobs = [], {}, []
    for index in range(len(tasks)):
        baseline, memory = initial[index]
        for arm, row in (("baseline", baseline), ("memory", memory)):
            rows[arm].append(row)
        comparison = {"task_id": baseline["task_id"], **_comparison(baseline, memory)}
        comparisons.append(comparison)
        for card in memory["cards"]:
            identity = _card_id(card)
            if comparison["gained"]:
                positive_tasks.setdefault(identity, []).append(baseline["task_id"])
            if comparison["regression"]:
                jobs.append((index, identity))

    def attribute(job: tuple[int, str]) -> dict:
        index, removed_id = job
        task = tasks[index]
        baseline, initial_full = initial[index]
        full_cards = initial_full["cards"]
        drop_cards = [card for card in full_cards if _card_id(card) != removed_id]
        attempts = []
        for attempt in range(confirmations + 1):
            full = initial_full if attempt == 0 else _evaluate(task, full_cards, "attribution_full", generate, validate)
            dropped = _evaluate(task, drop_cards, "attribution_drop", generate, validate)
            attempts.append({"attempt": attempt, "full": full, "drop": dropped,
                             "supported": _supported(baseline, full, dropped)})
        support_count = sum(item["supported"] for item in attempts)
        required = math.ceil(2 * len(attempts) / 3)
        return {"task_id": initial_full["task_id"], "card_id": removed_id, "attempts": attempts,
                "support_count": support_count, "required_support": required,
                "attributable": support_count >= required,
                "interpretation": "finite_sample_task_conditioned_negative_evidence"}

    attributed = map_jobs(jobs, attribute, lambda item: emit("attribution", item))
    attribution = [attributed[key] for key in sorted(attributed)]
    decisions, retired_ids = {}, []
    for identity in sorted(card_records):
        negatives = [item["task_id"] for item in attribution if item["card_id"] == identity and item["attributable"]]
        positives = positive_tasks.get(identity, [])
        if negatives and positives:
            status, reason = "review", "context_conflict"
        elif negatives:
            status, reason = "retired", "repeated_negative_evidence"
            retired_ids.append(identity)
        else:
            status, reason = "retained", "insufficient_negative_evidence"
        decisions[identity] = {"card_id": identity, "status": status, "reason": reason,
                               "negative_task_ids": negatives, "positive_task_ids": positives,
                               "version_sha256": versions[identity]}
        emit("decision", decisions[identity])

    def filtered_job(task: dict) -> dict:
        retrieval_error_type = "retrieval_error"
        try:
            selected = retrieve_filtered(deepcopy(task), set(retired_ids)) if retrieve_filtered else retrieve(deepcopy(task))
            cards = [deepcopy(card) for card in selected if _card_id(card) not in retired_ids]
            snapshots = _snapshot(cards)
            # 同 ID 已知卡只能改变检索排名/理由，不能悄悄改写被冻结的经验正文。
            for snapshot in snapshots:
                if snapshot["id"] in versions and versions[snapshot["id"]] != snapshot["version_sha256"]:
                    retrieval_error_type = "retrieval_version_drift"
                    raise ValueError("known experience version changed after retirement")
        except Exception as exc:
            return {"task_id": str(task.get("index", task.get("task_id", task.get("id")))),
                    "phase": "phase3_global_gate", "arm": "filtered", "cards": [],
                    "retrieval_snapshot": [], "code": "", "evidence": {}, "state": "U", "measured": False,
                    "error_type": retrieval_error_type, "error_class": type(exc).__name__, "elapsed_seconds": 0.0}
        return _evaluate(task, cards, "filtered", generate, validate)

    filtered = map_jobs(tasks, filtered_job, lambda row: emit("row", row))
    for index in range(len(tasks)):
        rows["filtered"].append(filtered[index])
    summary = {"task_count": len(tasks), "arms": {arm: _metrics(arm_rows) for arm, arm_rows in rows.items()},
               "comparable_pairs": sum(item["comparable"] for item in comparisons),
               "regressions": sum(item["regression"] for item in comparisons),
               "tradeoffs": sum(item["tradeoff"] for item in comparisons),
               "transition_matrix": dict(Counter(f'{item["before"]}->{item["after"]}' for item in comparisons)),
               "retrieved_unique_cards": len(card_records), "retired_count": len(retired_ids),
               "unretrieved_cards_status": "not_covered_not_passed", "attribution_pairs": len(attribution),
               "filtered_retrieval_mode": "rerank_remaining_library" if retrieve_filtered else "reretrieve_then_filter_without_refill",
               "selection_bias": "filtered results use selection D_gate; not independent generalization evidence",
               "long_term_memory_modified": False}
    return {"rows": rows, "comparisons": comparisons, "attribution": attribution,
            "decisions": decisions, "retired_ids": retired_ids, "summary": summary}

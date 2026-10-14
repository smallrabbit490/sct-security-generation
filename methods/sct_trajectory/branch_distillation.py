"""待接入的 Phase2 分支经验提炼：服务端证据绑定与独立一致性复核。

仅接受训练轨迹；不访问 D_gate/Base/Plus，不运行候选，不改长期经验库。
保留每个兄弟分支的完整计划、代码和卡片给两次独立请求；动态验证只发送
状态/类型/聚合计数，不发送原始异常详情和测试常量。模型审查不是动态验证，
通过审查也只输出 provisional 假说。任何缺证、unknown、解析失败均拒绝候选。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from typing import Any, Callable

from .agent_pipeline import _content, _extract_json
from .global_gate import evidence_is_measured
from .english_policy import assert_english_text, assert_english_experience


_TARGETS = ("positive", "negative", "error_ledger")
_CHECKS = ("facts", "api_reachability", "no_unsupported_examples", "no_causal_overclaim")
_TEXT_FIELDS = ("high_level_invariant", "positive_principle", "negative_guardrail", "applicability",
                "root_cause", "fix_directive", "blind_spot")


def _hash(value: Any) -> str:
    """Phase2 审计产物的稳定哈希；只处理已提供内容，不写库。"""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _trace_dict(trace: Any) -> dict:
    """适配 RolloutTrace/dict 并深拷贝；拒绝缺失分支和最终测试标记，不改输入。"""
    value = deepcopy(trace if isinstance(trace, dict) else trace.to_dict())
    if not isinstance(value.get("branches"), list) or not value["branches"]:
        raise ValueError("missing_branch_evidence")
    for field in ("subset", "split", "dataset", "benchmark", "pool"):
        if str(value.get(field, "")).lower() in {"base", "plus", "d_gate"}:
            raise ValueError("training_grow_only")
    return value


def _safe_evidence(evidence: dict) -> dict:
    """训练验证脱敏：保留可测状态、错误类别和聚合计数，移除原始测试/异常正文。"""
    result = {}
    for name, item in evidence.items():
        if name == "metadata" or not isinstance(item, dict):
            continue
        status = item.get("status")
        if status not in {"pass", "fail", "unmeasured"}:
            continue
        result[name] = {"status": status}
        if isinstance(item.get("error_type"), str):
            result[name]["error_type"] = item["error_type"]
        details = item.get("details")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except (ValueError, TypeError):
                details = None
        if isinstance(details, dict):
            for key in ("total", "passed"):
                if isinstance(details.get(key), int) and not isinstance(details[key], bool):
                    result[name][key] = details[key]
    metadata = evidence.get("metadata") or {}
    result["metadata"] = {key: metadata[key] for key in ("backend", "test_format", "security_basis", "dynamic_test")
                          if isinstance(metadata.get(key), str)}
    worker = metadata.get("worker_error")
    if isinstance(worker, dict):
        result["metadata"]["worker_error"] = {key: worker[key] for key in ("type", "stage", "winerror")
                                              if isinstance(worker.get(key), (str, int))}
    return result


def build_evidence_manifest(trace: Any) -> dict:
    """服务端从真实 F/S 生成分支 observations、代码 SHA 与证据 ID；不信任模型四态。

    输入训练 RolloutTrace/dict，输出仅脱敏动态证据的确定性 manifest；重复/缺失 ID
    失败。证据 ID 绑定完整原始证据哈希，但不外发其敏感正文。不执行或改经验库。
    """
    value = _trace_dict(trace)
    observations, seen = [], set()
    for branch in value["branches"]:
        identity = branch.get("branch_id")
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError("invalid_branch_identity")
        seen.add(identity)
        evidence = branch.get("evidence") or {}
        code = branch.get("code") or ""
        if not isinstance(code, str) or not isinstance(evidence, dict):
            raise ValueError("invalid_branch_payload")
        measured = evidence_is_measured(evidence, error_type=branch.get("error_type"))
        functional = measured and (evidence.get("functional") or {}).get("status") == "pass"
        security = measured and (evidence.get("security") or {}).get("status") == "pass"
        state = {(True, True): "A", (True, False): "B", (False, True): "C", (False, False): "D"}[(functional, security)] if measured else "U"
        code_sha = hashlib.sha256(code.encode("utf-8")).hexdigest()
        evidence_sha = _hash(evidence)
        evidence_id = "evidence:" + _hash({"branch_id": identity, "code_sha256": code_sha,
                                            "evidence_sha256": evidence_sha})
        observations.append({"branch_id": identity, "evidence_id": evidence_id,
                             "code_sha256": code_sha, "evidence_sha256": evidence_sha,
                             "state": state, "measured": measured, "functional": functional,
                             "security": security, "joint": functional and security,
                             "checks": _safe_evidence(evidence)})
    return {"schema": "branch_observations_v1", "observations": observations,
            "causal_interventions_measured": False, "long_term_memory_modified": False}


def _review_context(value: dict, manifest: dict) -> dict:
    """两轮模型共享全部兄弟代码/计划/卡片；验证详情只使用脱敏服务端 manifest。"""
    return {"task_contract": value.get("task_contract", ""), "cwe": value.get("cwe", ""),
            "evidence_manifest": manifest,
            "branches": [{"branch_id": b["branch_id"], "code": b.get("code", ""),
                          "plan": b.get("plan", {}), "cards": b.get("cards", []),
                          "retrieval_snapshot": b.get("retrieval_snapshot", []),
                          "card_hashes": b.get("card_hashes", {})} for b in value["branches"]]}


def distill_branches_reviewed(trace: Any, requester: Callable,
                             reviewer: Callable | None = None) -> dict:
    """独立 Phase2 提炼后逐条事实审查，输出兼容三列表及拒绝记录，不自动入库。

    第一次请求提出有 evidence_id 支持的候选；第二次请求独立审查状态一致性、
    API/可达性、无依据样例和因果夸大。四项都 supported 且 accept 才输出。
    positive 支持分支全部必须是 A；混合非 A 转 review。失败解释只是假说，
    不允许 verified root_cause。审查不是执行证明，未做的反事实仍未测量。
    """
    output = {**{target: [] for target in _TARGETS}, "review_rejections": [], "review_records": [],
              "evidence_manifest": {}, "long_term_memory_modified": False,
              "integration_status": "standalone_not_connected_to_training",
              "review_limit": "LLM consistency review is not execution or causal verification"}
    try:
        value = _trace_dict(trace)
        manifest = build_evidence_manifest(value)
        output["evidence_manifest"] = manifest
        context = _review_context(value, manifest)
    except Exception as exc:
        output["error"] = "evidence:" + type(exc).__name__
        return output
    rendered = json.dumps(context, ensure_ascii=False)
    prompt = (
        "BRANCH_DISTILL_EVIDENCE_V1\nExtract training-side experience candidates from independent parallel branches. "
        "The full trajectory follows. Sibling branches are not sequential repairs. Observations are server-recorded "
        "facts and cannot be rewritten. Return strict JSON in English: positive, negative and error_ledger lists, "
        "at most two items each. Every item needs evidence_branch_ids, evidence_ids, high_level_invariant, "
        "positive_principle, negative_guardrail, applicability, root_cause, fix_directive and blind_spot. "
        "All positive supporting branches must be measured A. Failed, unmeasured or mixed support is review evidence, "
        "not proof of general success. root_cause is only a hypothesis: without a local intervention, do not claim "
        "verified causality or treat unreachable logic as an executed cause. Do not invent API support, test inputs "
        "or expected constants; only the public contract can justify specific examples. Use complete branch code "
        "to inspect shared assumptions. Separate observations from counterfactuals and explicitly label unmeasured "
        "claims. Write all natural-language fields in English.\n" + rendered)
    try:
        distilled = _extract_json(_content(requester(prompt)))
        assert_english_experience(distilled)
        if any(not isinstance(distilled.get(target), list) for target in _TARGETS):
            raise ValueError("missing_distillation_lists")
    except Exception as exc:
        output["error"] = "distill:" + type(exc).__name__
        return output
    by_branch = {item["branch_id"]: item for item in manifest["observations"]}
    by_evidence = {item["evidence_id"]: item for item in manifest["observations"]}
    candidates = []
    for target in _TARGETS:
        for index, raw in enumerate(distilled[target][:2]):
            identity = f"{target}:{index}"
            candidate = {"candidate_id": identity, "target": target, "payload": deepcopy(raw)}
            candidates.append(candidate)
            reason, contradicting = None, []
            if not isinstance(raw, dict):
                reason = "invalid_candidate_object"
            else:
                branches, evidences = raw.get("evidence_branch_ids"), raw.get("evidence_ids")
                if (not isinstance(branches, list) or not branches or
                        any(not isinstance(b, str) or b not in by_branch for b in branches) or
                        not isinstance(evidences, list) or not evidences or
                        any(not isinstance(e, str) or e not in by_evidence for e in evidences)):
                    reason = "unknown_or_missing_evidence"
                elif {by_evidence[e]["branch_id"] for e in evidences} != set(branches):
                    reason = "evidence_branch_binding_mismatch"
                elif not isinstance(raw.get('high_level_invariant'), str) or not raw['high_level_invariant'].strip():
                    reason = "missing_experience_content"
                elif target == 'positive' and (not isinstance(raw.get('positive_principle'), str) or not raw['positive_principle'].strip()):
                    reason = "missing_experience_content"
                elif target == 'negative' and (not isinstance(raw.get('negative_guardrail'), str) or not raw['negative_guardrail'].strip()):
                    reason = "missing_experience_content"
                elif target == 'error_ledger' and (not isinstance(raw.get('blind_spot'), str) or not raw['blind_spot'].strip()):
                    reason = "missing_experience_content"
                elif target == "positive":
                    contradicting = [b for b in branches if by_branch[b]["state"] != "A"]
                    if contradicting:
                        reason = "mixed_or_non_A_positive_support"
                elif not any(by_branch[b]["measured"] and by_branch[b]["state"] != "A" for b in branches):
                    reason = "no_measured_failure_support"
                elif any(not by_branch[b]['measured'] for b in branches):
                    reason = "unmeasured_support"
            candidate["deterministic_rejection"] = reason
            if reason:
                output["review_rejections"].append({"candidate_id": identity, "reason": reason,
                                                     "status": "review", "contradicting_branch_ids": contradicting})
    review_prompt = (
        "BRANCH_DISTILL_REVIEW_V1\nYou are an independent consistency reviewer; do not inherit the distiller's "
        "conclusions. Review each candidate against the full trajectory. deterministic_rejection cannot be overruled. "
        "Check facts against server-recorded branch states; api_reachability against code and API evidence, excluding "
        "unreachable operations from executed causes; no_unsupported_examples against publicly justified inputs and "
        "expectations; and no_causal_overclaim to keep unverified causes as hypotheses. Mark uncertain API support, "
        "unknown call paths, untested counterfactuals or missing evidence as unknown rather than forced acceptance. "
        "Return strict JSON reviews with candidate_id, verdict (accept/reject/review), reason, and those four checks "
        "as supported/contradicted/unknown. One A branch does not establish success of all plans or universal validity. "
        "Accept only with sufficient evidence for every check; do not rewrite candidates to pass. "
        "Write all reasons in English.\nFull trajectory: " + rendered +
        "\nCandidates: " + json.dumps(candidates, ensure_ascii=False))
    try:
        review = _extract_json(_content((reviewer or requester)(review_prompt)))
        if not isinstance(review.get("reviews"), list):
            raise ValueError("missing_reviews")
        for item in review["reviews"]:
            if isinstance(item, dict):
                assert_english_text(str(item.get("reason", "")), context="branch_review.reason")
        output["review_records"] = deepcopy(review["reviews"])
    except Exception as exc:
        output["error"] = "review:" + type(exc).__name__
        for candidate in candidates:
            if not candidate["deterministic_rejection"]:
                output["review_rejections"].append({"candidate_id": candidate["candidate_id"],
                                                     "reason": "review_unavailable", "status": "review"})
        return output
    counts = Counter(item.get("candidate_id") for item in review["reviews"] if isinstance(item, dict) and isinstance(item.get("candidate_id"), str))
    reviews = {item["candidate_id"]: item for item in review["reviews"] if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)}
    for candidate in candidates:
        if candidate["deterministic_rejection"]:
            continue
        identity = candidate["candidate_id"]
        checked = reviews.get(identity, {})
        reason = None
        if counts[identity] != 1:
            reason = "missing_or_duplicate_review"
        elif checked.get("verdict") != "accept" or any(checked.get(key) != "supported" for key in _CHECKS):
            reason = "review_not_fully_supported"
        if reason:
            output["review_rejections"].append({"candidate_id": identity, "reason": reason, "status": "review"})
            continue
        raw, target = candidate["payload"], candidate["target"]
        accepted = {key: raw[key] for key in _TEXT_FIELDS if isinstance(raw.get(key), str)}
        accepted.update(evidence_branch_ids=list(raw["evidence_branch_ids"]), evidence_ids=list(raw["evidence_ids"]),
                        candidate_id=identity, kind="branch_reviewed_" + target, cwe=str(value.get("cwe", "")),
                        source_stage="phase2", causal_claim=False, root_cause_status="hypothesis",
                        status="provisional", generalization_status="unvalidated",
                        review_status="consistency_checked_not_dynamic_verified")
        output[target].append(accepted)
    return output

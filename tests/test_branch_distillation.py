"""离线审查分支提炼的事实绑定和 fail-closed；不请求在线模型。"""
import copy
import hashlib
import json

import pytest

from methods.sct_trajectory.branch_distillation import build_evidence_manifest, distill_branches_reviewed


def trace():
    branches = []
    for i, state in enumerate(("A", "C", "A"), 1):
        branches.append({"branch_id": f"b{i}", "state": state, "joint": state == "A", "measured": True,
                         "code": f"def f(): return {i}", "plan": {"strategy": f"route{i}"},
                         "cards": [{"invariant_id": "card", "fix_directive": "respect contract"}],
                         "evidence": {"functional": {"status": "pass" if state == "A" else "fail",
                                                       "details": "PRIVATE_TEST_SENTINEL"},
                                      "security": {"status": "pass"},
                                      "static_analysis": {"status": "unmeasured"}}})
    return {"task_id": "1394", "cwe": "1333", "task_contract": "Return matching parts", "branches": branches}


def reply(value):
    return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}]}


def candidate(manifest, branches=("b1",), **extra):
    ids = [item["evidence_id"] for item in manifest["observations"] if item["branch_id"] in branches]
    return {"evidence_branch_ids": list(branches), "evidence_ids": ids,
            "high_level_invariant": "Use bounded parser", "positive_principle": "Check documented delimiters",
            "root_cause": "A possible input handling difference", **extra}


def approved(candidate_ids):
    return {"reviews": [{"candidate_id": cid, "verdict": "accept", "reason": "consistent",
                         "facts": "supported", "api_reachability": "supported",
                         "no_unsupported_examples": "supported", "no_causal_overclaim": "supported"} for cid in candidate_ids]}


def execute(value, review=None):
    calls = []
    def request(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return reply(value)
        return reply(review or approved(["positive:0"]))
    return calls, distill_branches_reviewed(trace(), request)


def test_server_manifest_recomputes_states_and_stable_code_evidence_hashes():
    raw = trace()
    raw["branches"][1]["state"] = "A"
    raw["branches"][1]["joint"] = True
    manifest = build_evidence_manifest(raw)
    observations = manifest["observations"]
    assert [item["state"] for item in observations] == ["A", "C", "A"]
    assert observations[0]["code_sha256"] == hashlib.sha256(raw["branches"][0]["code"].encode()).hexdigest()
    assert manifest == build_evidence_manifest(copy.deepcopy(raw))
    assert "PRIVATE_TEST_SENTINEL" not in json.dumps(manifest)


def test_both_calls_see_all_code_but_never_raw_private_details_and_result_is_hypothesis():
    original = trace()
    card = candidate(build_evidence_manifest(original), root_cause_status="verified", causal_claim=True)
    calls, result = execute({"positive": [card], "negative": [], "error_ledger": []})
    assert len(calls) == 2
    assert all(all(branch["code"] in prompt for branch in original["branches"]) for prompt in calls)
    assert all("PRIVATE_TEST_SENTINEL" not in prompt for prompt in calls)
    item = result["positive"][0]
    assert item["root_cause_status"] == "hypothesis"
    assert item["causal_claim"] is False
    assert item["status"] == "provisional"
    assert result["long_term_memory_modified"] is False
    assert all(not any('\u3400' <= c <= '\u9fff' for c in prompt) for prompt in calls)


def test_nonenglish_experience_or_review_cannot_pass():
    card = candidate(build_evidence_manifest(trace()), positive_principle='保持契约')
    calls, result = execute({'positive': [card], 'negative': [], 'error_ledger': []})
    assert result['positive'] == [] and result['error'] == 'distill:EnglishPolicyError'
    assert len(calls) == 1
    card['positive_principle'] = 'Preserve the contract'
    review = approved(['positive:0'])
    review['reviews'][0]['reason'] = '一致'
    _, result = execute({'positive': [card], 'negative': [], 'error_ledger': []}, review)
    assert result['positive'] == [] and result['error'] == 'review:EnglishPolicyError'


def test_mixed_A_C_positive_support_is_review_only_even_if_reviewer_accepts():
    card = candidate(build_evidence_manifest(trace()), ("b1", "b2", "b3"))
    _, result = execute({"positive": [card], "negative": [], "error_ledger": []})
    assert result["positive"] == []
    rejection = result["review_rejections"][0]
    assert rejection["reason"] == "mixed_or_non_A_positive_support"
    assert rejection["contradicting_branch_ids"] == ["b2"]


@pytest.mark.parametrize("changes", [{"evidence_ids": ["fabricated"]}, {"evidence_branch_ids": ["unknown"]}, {"evidence_ids": []}])
def test_unknown_or_missing_evidence_fails_closed(changes):
    card = candidate(build_evidence_manifest(trace()), **changes)
    _, result = execute({"positive": [card], "negative": [], "error_ledger": []})
    assert result["positive"] == []
    assert result["review_rejections"]


@pytest.mark.parametrize("field", ["facts", "api_reachability", "no_unsupported_examples", "no_causal_overclaim"])
def test_reviewer_unknown_or_missing_check_never_accepts(field):
    card = candidate(build_evidence_manifest(trace()))
    review = approved(["positive:0"])
    review["reviews"][0][field] = "unknown"
    _, result = execute({"positive": [card], "negative": [], "error_ledger": []}, review)
    assert not result["positive"]
    assert result["review_rejections"][0]["reason"] == "review_not_fully_supported"


def test_missing_review_is_fail_closed_and_provider_exception_has_no_message_leak():
    raw = trace()
    card = candidate(build_evidence_manifest(raw))
    def requester(prompt):
        return reply({"positive": [card], "negative": [], "error_ledger": []})
    def reviewer(prompt):
        raise RuntimeError("SECRET_PROVIDER_DETAIL")
    result = distill_branches_reviewed(raw, requester, reviewer)
    assert result["positive"] == []
    assert result["error"] == "review:RuntimeError"
    assert "SECRET_PROVIDER_DETAIL" not in json.dumps(result)


def test_missing_distillation_schema_and_invalid_review_schema_fail_closed():
    calls, result = execute({"positive": []})
    assert result["error"].startswith("distill:")
    assert len(calls) == 1
    card = candidate(build_evidence_manifest(trace()))
    _, result = execute({"positive": [card], "negative": [], "error_ledger": []}, {"reviews": []})
    assert result["positive"] == []
    assert result["review_rejections"][0]["reason"] == "missing_or_duplicate_review"


def test_unmeasured_branch_cannot_support_failure_rule():
    raw = trace()
    raw["branches"][1]["evidence"]["functional"]["error_type"] = "local_worker_error"
    manifest = build_evidence_manifest(raw)
    assert manifest["observations"][1]["state"] == "U"
    item = candidate(manifest, ("b2",), negative_guardrail="avoid unsupported API")
    result = distill_branches_reviewed(raw, lambda p: reply({"positive": [], "negative": [item], "error_ledger": []}),
                                     lambda p: reply(approved(["negative:0"])))
    assert result["negative"] == []
    assert result["review_rejections"][0]["reason"] == "no_measured_failure_support"


def test_failure_rule_cannot_use_unmeasured_branch_alongside_measured_failure():
    raw = trace()
    raw["branches"][2]["evidence"]["functional"]["status"] = "unmeasured"
    manifest = build_evidence_manifest(raw)
    item = candidate(manifest, ("b2", "b3"), negative_guardrail="guard")
    result = distill_branches_reviewed(raw, lambda p: reply({"positive": [], "negative": [item], "error_ledger": []}),
                                     lambda p: reply(approved(["negative:0"])))
    assert result["negative"] == []
    assert result["review_rejections"][0]["reason"] == "unmeasured_support"


def test_incomplete_experience_schema_cannot_be_accepted_by_reviewer():
    item = candidate(build_evidence_manifest(trace()))
    item.pop("high_level_invariant")
    _, result = execute({"positive": [item], "negative": [], "error_ledger": []})
    assert result["positive"] == []
    assert result["review_rejections"][0]["reason"] == "missing_experience_content"


def test_server_preserves_evidence_binding_when_code_changes():
    raw = trace()
    original = build_evidence_manifest(raw)
    raw["branches"][0]["code"] = "def changed(): return 1"
    item = candidate(original)
    result = distill_branches_reviewed(raw, lambda p: reply({"positive": [item], "negative": [], "error_ledger": []}),
                                     lambda p: reply(approved(["positive:0"])))
    assert result["positive"] == []
    assert result["review_rejections"][0]["reason"] == "unknown_or_missing_evidence"

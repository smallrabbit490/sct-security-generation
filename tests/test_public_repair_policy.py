"""公开逐例修复策略的反例与真实轻量执行回归；全程零模型 API。"""
from copy import deepcopy
import json

import pytest

from methods.sct_trajectory.internal_checks import execute_checks
from methods.sct_trajectory.public_repair_policy import (
    bind_public_result, choose_public_candidate, public_repair_feedback, repair_opportunity,
    suite_fingerprint,
)


def suite():
    return {"cases": [
        {"id": f"f{value}", "kind": "functional", "purpose": f"Preserve integer {value}",
         "code": f"actual = candidate({value})\nassert actual == {value}, repr(actual)"}
        for value in range(1, 4)
    ]}


def contract(*violations):
    check_ids = ["public.syntax_invalid:python", "public.entrypoint_missing:f",
                 "public.signature_mismatch:f", "public.external_binding_rebound:USER_POST_FORMAT"]
    return {
        "schema_version": "public_contract_checks.v1", "source": "public_contract_static",
        "measured": True, "status": "fail" if violations else "pass",
        "contract_digest": "fixed-public-contract",
        "check_ids": check_ids,
        "measured_check_ids": list(check_ids), "unmeasured_check_ids": [],
        "violations": [{"id": value, "rule_id": value.split(":")[0],
                        "symbol": value.split(":")[-1], "line": 1,
                        "message": "Public contract violation", "public_source": "description"}
                       for value in violations],
        "unmeasured": ["semantic_behavior"],
    }


def result(code, statuses, *, checks=None, backend="local"):
    checks = checks if checks is not None else suite()
    rows = [{"id": case["id"], "kind": case["kind"], "purpose": case["purpose"],
             "status": status, "measured": status != "environment_error", "error": "public failure"}
            for case, status in zip(checks["cases"], statuses)]
    raw = {"source": "self_generated_internal", "backend": backend, "cases": rows}
    return bind_public_result(code, checks, raw)


def decision(before=("pass", "fail", "fail"), after=("pass", "pass", "pass"), **overrides):
    c0, c1 = "def f(x): return 1", "def f(x): return x"
    inputs = {
        "original_code": c0, "repaired_code": c1, "suite": suite(),
        "original_internal": result(c0, before), "repaired_internal": result(c1, after),
        "original_contract": contract(), "repaired_contract": contract(),
    }
    inputs.update(overrides)
    return choose_public_candidate(**inputs)


def test_real_execution_more_total_passes_cannot_compensate_regression():
    checks = suite()
    c0 = "def f(x): return 1"
    c1 = "def f(x): return 0 if x == 1 else x"
    r0 = bind_public_result(c0, checks, execute_checks(c0, "f", checks))
    r1 = bind_public_result(c1, checks, execute_checks(c1, "f", checks))
    assert (r0["passed"], r1["passed"]) == (1, 2)
    selected = choose_public_candidate(original_code=c0, repaired_code=c1, suite=checks,
        original_internal=r0, repaired_internal=r1,
        original_contract=contract(), repaired_contract=contract())
    assert selected["selected_attempt"] == 0
    assert selected["regressed_case_ids"] == ["f1"]
    assert selected["improved_case_ids"] == ["f2", "f3"]


def test_real_execution_accepts_strict_case_improvement():
    checks = suite()
    c0, c1 = "def f(x): return 1", "def f(x): return x"
    selected = choose_public_candidate(original_code=c0, repaired_code=c1, suite=checks,
        original_internal=bind_public_result(c0, checks, execute_checks(c0, "f", checks)),
        repaired_internal=bind_public_result(c1, checks, execute_checks(c1, "f", checks)),
        original_contract=contract(), repaired_contract=contract())
    assert selected["selected_attempt"] == 1
    assert selected["formal_metrics"] == "unmeasured"


@pytest.mark.parametrize("statuses", [("pass",) * 3, ("fail",) * 3])
def test_equal_outcomes_keep_original(statuses):
    assert decision(statuses, statuses)["selected_attempt"] == 0


def test_contract_repair_is_explicit_improvement_without_new_passes():
    selected = decision(("pass",) * 3, ("pass",) * 3,
        original_contract=contract("public.external_binding_rebound:USER_POST_FORMAT"))
    assert selected["selected_attempt"] == 1
    assert selected["reason"] == "public_contract_improvement"


def test_new_hard_contract_violation_blocks_better_cases():
    selected = decision(repaired_contract=contract("public.external_binding_rebound:USER_POST_FORMAT"))
    assert selected["selected_attempt"] == 0
    assert selected["reason"] == "new_public_contract_violation"


def test_unchanged_violation_moving_lines_is_not_new_improvement():
    c0 = contract("public.external_binding_rebound:USER_POST_FORMAT")
    c1 = deepcopy(c0)
    c1["violations"][0]["line"] = 40
    selected = decision(("pass",) * 3, ("pass",) * 3, original_contract=c0, repaired_contract=c1)
    assert selected["selected_attempt"] == 0
    assert selected["new_contract_violation_ids"] == []


@pytest.mark.parametrize("change,reason", [
    ("missing", "missing_public_case_result"),
    ("duplicate", "unexpected_or_duplicate_public_case_result"),
    ("unknown", "unexpected_or_duplicate_public_case_result"),
    ("unmeasured", "public_case_unmeasured"),
    ("status", "public_case_unmeasured"),
    ("binding", "public_result_binding_mismatch"),
    ("source", "not_public_internal_result"),
])
def test_incomparable_cases_keep_original(change, reason):
    r1 = result("def f(x): return x", ("pass",) * 3)
    if change == "missing":
        r1["cases"].pop()
    elif change == "duplicate":
        r1["cases"].append(dict(r1["cases"][0]))
    elif change == "unknown":
        r1["cases"][0]["id"] = "different_case"
    elif change == "unmeasured":
        r1["cases"][0]["measured"] = False
    elif change == "status":
        r1["cases"][0]["status"] = "environment_error"
    elif change == "binding":
        r1.pop("public_binding")
    elif change == "source":
        r1["source"] = "formal_validation"
    selected = decision(repaired_internal=r1)
    assert selected["selected_attempt"] == 0
    assert selected["reason"] == reason
    assert not selected["comparable"]


def test_empty_suite_keeps_original_even_when_contract_issue_removed():
    selected = decision(suite={"cases": []},
        original_contract=contract("public.external_binding_rebound:USER_POST_FORMAT"))
    assert selected["selected_attempt"] == 0
    assert selected["reason"] == "empty_public_suite"


def test_same_ids_changed_test_body_or_code_cannot_reuse_results():
    altered_suite = suite()
    altered_suite["cases"][0]["code"] = "assert candidate(1) == 99"
    assert suite_fingerprint(altered_suite) != suite_fingerprint(suite())
    assert decision(suite=altered_suite)["reason"] == "public_result_binding_mismatch"
    assert decision(repaired_code="def f(x): return 99")["reason"] == "public_result_binding_mismatch"
    old_result = result("def f(x): return 1", ("pass", "fail", "fail"))
    with pytest.raises(ValueError, match="cannot_rebind"):
        bind_public_result("def f(x): return 99", suite(), old_result)


def test_backend_contract_and_measurement_scope_must_match():
    docker_result = result("def f(x): return x", ("pass",) * 3, backend="docker")
    assert decision(repaired_internal=docker_result)["reason"] == "public_execution_backend_mismatch"
    changed = contract()
    changed["contract_digest"] = "different-contract"
    assert decision(repaired_contract=changed)["reason"] == "public_contract_scope_mismatch"
    changed = contract()
    changed["check_ids"].append("extra-check")
    changed["measured_check_ids"].append("extra-check")
    assert decision(repaired_contract=changed)["reason"] == "public_contract_scope_mismatch"
    changed = contract()
    changed["measured"] = False
    assert decision(repaired_contract=changed)["reason"] == "public_contract_unmeasured"


@pytest.mark.parametrize("c0", ["", "# no executable code", "def f(:", "return 1"])
def test_syntax_and_empty_recovery_require_clean_measured_public_improvement(c0):
    original = result(c0, ("syntax_error",) * 3)
    selected = decision(original_code=c0, original_internal=original,
        original_contract=contract("public.syntax_invalid:python"))
    assert selected["selected_attempt"] == 1
    assert selected["reason"] == "syntax_recovery_with_public_improvement"
    no_pass = result("def f(x): return x", ("runtime_error",) * 3)
    selected = decision(original_code=c0, original_internal=original,
        original_contract=contract("public.syntax_invalid:python"), repaired_internal=no_pass)
    assert selected["selected_attempt"] == 0


def test_repair_syntax_failure_cannot_be_overridden_by_reported_passes():
    selected = decision(repaired_code="def f(:")
    assert selected["reason"] == "repair_empty_or_syntax_invalid"
    assert selected["selected_attempt"] == 0


def test_identical_code_is_not_a_new_candidate_even_if_observations_differ():
    c0 = "def f(x): return 1"
    selected = decision(repaired_code=c0, repaired_internal=result(c0, ("pass",) * 3))
    assert selected["selected_attempt"] == 0
    assert selected["reason"] == "unchanged_code"


def test_aggregate_counts_and_hidden_metrics_do_not_influence_policy_or_feedback():
    c0 = "def f(x): return 1"
    original = result(c0, ("pass", "fail", "fail"))
    original.update(passed=999, joint=True, functional={"status": "pass"},
                    validation={"error": "HIDDEN_SENTINEL"})
    original["cases"][1]["formal_error"] = "HIDDEN_SENTINEL"
    static = contract("public.external_binding_rebound:USER_POST_FORMAT")
    static["formal_validation"] = {"details": "HIDDEN_SENTINEL"}
    static["violations"][0]["hidden_test"] = "HIDDEN_SENTINEL"
    static["unmeasured"].append({"hidden_test": "HIDDEN_SENTINEL"})
    selected = decision(original_internal=original)
    assert selected["selected_attempt"] == 1
    feedback = public_repair_feedback(suite(), original, static)
    assert "HIDDEN_SENTINEL" not in json.dumps(feedback)
    assert feedback["internal_checks"]["passed"] == 1
    assert feedback["internal_checks"]["cases"][1]["code"] == suite()["cases"][1]["code"]
    assert feedback["internal_checks"]["cases"][1]["error"] == "public failure"
    rebound = bind_public_result(c0, suite(), original)
    assert "HIDDEN_SENTINEL" not in json.dumps(rebound)


def test_wrong_public_source_cannot_route_official_error_back_to_model():
    internal = result("def f(x): return 1", ("fail",) * 3)
    internal["source"] = "formal_validation"
    internal["cases"][0]["error"] = "HIDDEN_SENTINEL"
    static = contract()
    static["source"] = "formal_validation"
    static["violations"] = [{"message": "HIDDEN_SENTINEL"}]
    feedback = public_repair_feedback(suite(), internal, static)
    assert "HIDDEN_SENTINEL" not in json.dumps(feedback)
    assert feedback["internal_checks"]["measured"] is False
    assert feedback["public_contract_checks"]["measured"] is False


def test_invalid_suite_never_gets_fingerprint():
    duplicated = suite()
    duplicated["cases"].append(dict(duplicated["cases"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        suite_fingerprint(duplicated)


@pytest.mark.parametrize("statuses,static,expected,reason", [
    (("pass", "pass", "pass"), contract(), False, "no_strict_public_improvement_possible"),
    (("pass", "fail", "pass"), contract(), True, "public_case_repair_opportunity"),
    (("pass", "timeout", "pass"), contract(), True, "public_case_repair_opportunity"),
    (("pass", "environment_error", "pass"), contract(), False, "public_case_unmeasured"),
    (("pass", "pass", "pass"), contract("public.external_binding_rebound:USER_POST_FORMAT"),
     True, "public_contract_repair_opportunity"),
])
def test_repair_opportunity_requires_possible_strict_public_improvement(statuses, static, expected, reason):
    code = "def f(x): return 1"
    opportunity = repair_opportunity(code, suite(), result(code, statuses), static)
    assert opportunity == {"should_generate_repair": expected, "reason": reason}


def test_repair_opportunity_does_not_spend_on_empty_missing_or_stale_evidence():
    code = "def f(x): return 1"
    assert repair_opportunity(code, {"cases": []}, {}, {}) == {
        "should_generate_repair": False, "reason": "empty_public_suite"}
    missing = result(code, ("fail",))
    assert repair_opportunity(code, suite(), missing, contract())["reason"] == "missing_public_case_result"
    stale = result("def f(x): return 99", ("fail",) * 3)
    assert repair_opportunity(code, suite(), stale, contract())["reason"] == "public_result_binding_mismatch"
    unmeasured = contract()
    unmeasured["measured"] = False
    assert repair_opportunity(code, suite(), result(code, ("fail",) * 3), unmeasured)["reason"] == "public_contract_unmeasured"


@pytest.mark.parametrize("code", ["", "def f(:"])
def test_repair_opportunity_allows_measured_empty_and_syntax_recovery(code):
    opportunity = repair_opportunity(code, suite(), result(code, ("syntax_error",) * 3),
                                     contract("public.syntax_invalid:python"))
    assert opportunity == {"should_generate_repair": True, "reason": "syntax_recovery_opportunity"}


def test_unmeasured_signature_cannot_masquerade_as_contract_repair():
    before = contract("public.signature_mismatch:f")
    after = contract()
    after["measured_check_ids"].remove("public.signature_mismatch:f")
    after["unmeasured_check_ids"].append("public.signature_mismatch:f")
    selected = decision(original_contract=before, repaired_contract=after)
    assert selected["selected_attempt"] == 0
    assert selected["reason"] == "public_contract_measurement_regression"
    assert selected["lost_measured_contract_check_ids"] == ["public.signature_mismatch:f"]
    assert selected["removed_contract_violation_ids"] == []


def test_real_alias_candidate_cannot_hide_a_public_signature_violation():
    from methods.sct_trajectory.public_contract_checks import compile_public_contract, check_public_contract
    requirements = compile_public_contract({"function_name": "f", "function_signature": "f(x)",
                                             "description": "Return the integer x unchanged."})
    before = "def f(value): return value"
    after = "from operator import pos as f"
    checks = suite()
    r0 = bind_public_result(before, checks, execute_checks(before, "f", checks))
    r1 = bind_public_result(after, checks, execute_checks(after, "f", checks))
    assert r0["passed"] == r1["passed"] == 3
    selected = choose_public_candidate(original_code=before, repaired_code=after, suite=checks,
        original_internal=r0, repaired_internal=r1,
        original_contract=check_public_contract(before, requirements),
        repaired_contract=check_public_contract(after, requirements))
    assert selected["selected_attempt"] == 0
    assert selected["reason"] == "public_contract_measurement_regression"


def test_syntax_recovery_can_gain_static_measurement_coverage():
    code = "def f(:"
    before = contract("public.syntax_invalid:python")
    before["measured_check_ids"] = ["public.syntax_invalid:python"]
    before["unmeasured_check_ids"] = [value for value in before["check_ids"]
                                       if value != "public.syntax_invalid:python"]
    selected = decision(original_code=code, original_internal=result(code, ("syntax_error",) * 3),
                        original_contract=before)
    assert selected["selected_attempt"] == 1
    assert "public.signature_mismatch:f" in selected["newly_measured_contract_check_ids"]


@pytest.mark.parametrize("mutation", ["missing", "overlap", "incomplete", "violation_unmeasured"])
def test_invalid_static_measurement_scope_blocks_paid_repair_and_selection(mutation):
    static = contract("public.signature_mismatch:f")
    if mutation == "missing":
        static.pop("measured_check_ids")
    elif mutation == "overlap":
        static["unmeasured_check_ids"] = ["public.signature_mismatch:f"]
    elif mutation == "incomplete":
        static["measured_check_ids"].remove("public.signature_mismatch:f")
    else:
        static["measured_check_ids"].remove("public.signature_mismatch:f")
        static["unmeasured_check_ids"] = ["public.signature_mismatch:f"]
    code = "def f(x): return 1"
    assert not repair_opportunity(code, suite(), result(code, ("fail",) * 3), static)["should_generate_repair"]
    selected = decision(original_contract=static)
    assert selected["selected_attempt"] == 0
    assert not selected["comparable"]

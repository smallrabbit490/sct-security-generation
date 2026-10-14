"""训练侧全量门控：缺测隔离、固定组合归因及冲突保护的离线回归。"""
from copy import deepcopy
import pytest

from methods.sct_trajectory.global_gate import run_global_gate


def evidence(state):
    return {
        "functional": {"status": "pass" if state in "AB" else "fail"},
        "security": {"status": "pass" if state in "AC" else "fail"},
    }


def test_retires_only_confirmed_harmful_card_and_preserves_original_snapshot():
    cards = [{"invariant_id": "bad", "text": "unsafe"}, {"id": "good", "text": "useful"}]
    original = deepcopy(cards)
    calls = []

    def generate(task, selected):
        calls.append([c.get("id", c.get("invariant_id")) for c in selected])
        return "D" if any(c.get("invariant_id") == "bad" for c in selected) else "A"

    result = run_global_gate([{"index": 1}], lambda t: cards, generate, lambda t, c: evidence(c))
    assert result["retired_ids"] == ["bad"]
    assert result["decisions"]["bad"]["status"] == "retired"
    assert result["decisions"]["good"]["status"] == "retained"
    assert cards == original
    assert result["summary"]["arms"]["filtered"]["joint_pass"] == 1
    assert result["rows"]["memory"][0]["retrieval_snapshot"][0]["sha256"]
    assert result["attribution"][0]["support_count"] == 3
    assert all(set(c).issubset({"bad", "good"}) for c in calls)


def test_positive_context_conflict_prevents_global_retirement():
    cards = [{"id": "contextual", "text": "context sensitive"}]

    def generate(task, selected):
        return ("D" if selected else "A") if task["index"] == 1 else ("A" if selected else "D")

    result = run_global_gate([{"index": 1}, {"index": 2}], lambda t: cards, generate, lambda t, c: evidence(c))
    assert result["retired_ids"] == []
    assert result["decisions"]["contextual"]["status"] == "review"
    assert result["decisions"]["contextual"]["reason"] == "context_conflict"


@pytest.mark.parametrize("failure", ["unmeasured", "environment_error", "validator_exception", "plt_validator_exception", "local_worker_error"])
def test_invalid_measurements_never_drive_attribution(failure):
    def validate(task, code):
        result = evidence("A" if code == "clean" else "D")
        if code != "clean":
            if failure == "unmeasured":
                result["security"]["status"] = "unmeasured"
            else:
                result["functional"]["error_type"] = failure
        return result
    result = run_global_gate([{"index": 1}], lambda t: [{"id": "x"}],
                             lambda t, c: "dirty" if c else "clean", validate)
    assert result["retired_ids"] == []
    assert result["attribution"] == []
    assert result["summary"]["comparable_pairs"] == 0


def test_tradeoff_gets_reviewed_and_counts_positive_conflict():
    result = run_global_gate([{"index": 1}], lambda t: [{"id": "x"}],
                             lambda t, c: "C" if c else "B", lambda t, c: evidence(c))
    assert len(result["attribution"]) == 1
    assert result["summary"]["tradeoffs"] == 1
    assert result["retired_ids"] == []


def test_unstable_full_combination_does_not_retire_card():
    counts = {"memory": 0}
    def generate(task, selected):
        if not selected:
            return "A"
        counts["memory"] += 1
        return "D" if counts["memory"] == 1 else "A"
    result = run_global_gate([{"index": 1}], lambda t: [{"id": "x"}], generate, lambda t, c: evidence(c))
    assert result["attribution"][0]["support_count"] == 1
    assert result["retired_ids"] == []


def test_filtered_arm_retrieves_again_and_records_replacement_card():
    seen = []
    def filtered(task, retired):
        seen.append(set(retired))
        return [{"id": "replacement", "text": "newly selected"}]
    result = run_global_gate([{"index": 1}], lambda t: [{"id": "bad"}],
                             lambda t, c: "D" if any(x["id"] == "bad" for x in c) else "A",
                             lambda t, c: evidence(c), retrieve_filtered=filtered)
    assert seen == [{"bad"}]
    assert result["rows"]["filtered"][0]["cards"][0]["id"] == "replacement"
    assert result["summary"]["filtered_retrieval_mode"] == "rerank_remaining_library"


def test_all_initial_pairs_finish_before_leave_one_out_and_records_are_streamed():
    events, records = [], []
    def generate(task, cards):
        events.append((task["index"], tuple(c["id"] for c in cards)))
        return "D" if cards else "A"
    result = run_global_gate([{"index": 1}, {"index": 2}], lambda t: [{"id": "x"}, {"id": "y"}],
                             generate, lambda t, c: evidence(c), workers=2, on_record=records.append)
    initial = events[:4]
    assert sorted(t for t, _ in initial) == [1, 1, 2, 2]
    assert all(len(cards) in (0, 2) for _, cards in initial)
    assert len(result["rows"]["baseline"]) == 2
    assert {r["kind"] for r in records} >= {"row", "attribution", "decision"}


@pytest.mark.parametrize("task", [{"index": 1, "subset": "Plus"}, {"index": 1, "pool": "D_grow"}])
def test_rejects_final_test_and_non_gate_explicit_pool(task):
    with pytest.raises(ValueError):
        run_global_gate([task], lambda t: [], lambda t, c: "A", lambda t, c: evidence(c))


def test_generation_exception_is_preserved_without_deleting_experience():
    def generate(task, cards):
        if cards:
            raise RuntimeError("provider down")
        return "A"
    result = run_global_gate([{"index": 1}], lambda t: [{"id": "x"}], generate, lambda t, c: evidence(c))
    assert result["retired_ids"] == []
    assert result["rows"]["memory"][0]["error_type"] == "generation_error"


def test_same_card_id_with_different_payloads_is_not_silently_merged():
    with pytest.raises(ValueError, match="version"):
        run_global_gate([{"index": 1}, {"index": 2}],
                        lambda t: [{"id": "x", "text": str(t["index"])}],
                        lambda t, c: "A", lambda t, c: evidence(c))


def test_unmeasured_optional_checks_do_not_exclude_measured_function_and_security():
    def validate(task, code):
        value = evidence(code)
        value["static_analysis"] = {"status": "unmeasured", "measured": False}
        value["type_check"] = {"status": "unmeasured"}
        return value
    result = run_global_gate([{"index": 1}], lambda t: [{"id": "bad"}],
                             lambda t, c: "D" if c else "A", validate)
    assert result["retired_ids"] == ["bad"]
    assert result["summary"]["comparable_pairs"] == 1


def test_streaming_callback_observes_first_pair_before_slow_task_finishes():
    from threading import Event
    first_written = Event()
    timed_out = []
    def generate(task, cards):
        if task["index"] == 2 and not first_written.wait(0.3):
            timed_out.append(True)
        return "A"
    def record(value):
        if value["kind"] == "row" and value["task_id"] == "1":
            first_written.set()
    run_global_gate([{"index": 1}, {"index": 2}], lambda t: [], generate,
                    lambda t, c: evidence(c), workers=2, on_record=record)
    assert not timed_out


def test_real_retriever_per_task_scores_are_not_card_version_drift():
    result = run_global_gate([{"index": 1}, {"index": 2}],
        lambda t: [{"invariant_id": "x", "text": "same", "_base_score": t["index"],
                    "_llm_score": t["index"], "_llm_reason": str(t["index"]), "_align_error": None}],
        lambda t, c: "A", lambda t, c: evidence(c))
    assert result["summary"]["retrieved_unique_cards"] == 1


def test_real_retriever_per_task_audit_is_not_card_version_drift():
    result = run_global_gate([{"index": 1}, {"index": 2}],
        lambda t: [{"invariant_id": "x", "text": "same",
                    "retrieval_audit": {"query_task": t["index"], "selected": ["x"]},
                    "_relevance_gate": "same_cwe" if t["index"] == 1 else "cross_cwe"}],
        lambda t, c: "A", lambda t, c: evidence(c))
    assert result["summary"]["retrieved_unique_cards"] == 1
    assert result["rows"]["memory"][0]["retrieval_snapshot"][0]["sha256"] != result["rows"]["memory"][1]["retrieval_snapshot"][0]["sha256"]


def test_filtered_retrieval_rejects_changed_body_of_known_card():
    result = run_global_gate([{"index": 1, "pool": "D_gate"}],
        lambda t: [{"id": "x", "text": "original"}], lambda t, c: "A",
        lambda t, c: evidence(c),
        retrieve_filtered=lambda t, retired: [{"id": "x", "text": "changed"}])
    row = result["rows"]["filtered"][0]
    assert row["state"] == "U"
    assert row["code"] == ""
    assert row["error_type"] == "retrieval_version_drift"
    assert result["summary"]["arms"]["filtered"]["measured"] == 0


def test_public_evidence_measurement_check_accepts_tests_but_rejects_worker_failure():
    from methods.sct_trajectory.global_gate import evidence_is_measured
    value = evidence("D")
    value["functional"]["error_type"] = "plt_test_failed"
    value["static_analysis"] = {"status": "unmeasured"}
    assert evidence_is_measured(value)
    value["functional"]["error_type"] = "local_worker_error"
    assert not evidence_is_measured(value)
    assert not evidence_is_measured(evidence("A"), error_type="generation_error")

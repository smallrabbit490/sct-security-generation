"""CLE 细粒度消融矩阵的离线契约测试。"""
from __future__ import annotations

import hashlib
import json

import pytest

from methods.cle_ablation_matrix.design import ARM_SPECS, get_arm, validate_design
from methods.cle_ablation_matrix.freeze_policy import (
    FreezeQualificationError, JsonlValidationError, audit_existing_freeze, qualify_freeze,
    validate_jsonl,
)
from methods.cle_ablation_matrix.metrics import summarize_matrix
from methods.cle_ablation_matrix.pool_manifest import build_manifest, select_pool_rows, validate_manifest


def _tasks():
    return [
        {"index": index, "CWE_ID": str(index // 2), "family_id": f"family-{index // 2}",
         "task_description": {"description": "fixture"}}
        for index in range(874)
    ]


def test_design_has_fine_grained_c1_c2_c3_and_support_arms():
    validate_design()
    assert {spec.stage for spec in ARM_SPECS.values()} == {"c1", "c2", "c3", "support"}
    assert [name for name, spec in ARM_SPECS.items() if spec.stage == "c1"] == ["C1-0", "C1-1", "C1-2", "C1-3"]
    assert [name for name, spec in ARM_SPECS.items() if spec.stage == "c2"] == [
        "C2-0", "C2-1", "C2-2", "C2-3", "C2-4", "C2-5"]
    assert [name for name, spec in ARM_SPECS.items() if spec.stage == "c3"] == [
        "C3-0", "C3-1", "C3-2", "C3-3"]
    assert get_arm("C2-3").parent_arm == "C2-2"
    assert get_arm("C2-3").components["reanalyze_after_retrieval"] is True
    assert get_arm("C2-2").components["reanalyze_after_retrieval"] is False


def test_fixed_four_pool_manifest_is_family_atomic_and_hpass_isolated():
    manifest = build_manifest(_tasks())
    assert manifest["counts"] == {"D_init": 270, "D_grow": 240, "D_gate": 64, "H_pass": 300}
    checks = validate_manifest(manifest, _tasks())
    assert checks["family_ids_pairwise_disjoint"] is True
    assert checks["h_pass_isolated"] is True
    assert len(select_pool_rows(_tasks(), manifest, ("D_init", "D_grow", "D_gate"))) == 574
    assert len(select_pool_rows(_tasks(), manifest, ("H_pass",))) == 300


def test_manifest_rejects_family_split_and_training_access_to_hpass():
    manifest = build_manifest(_tasks())
    first = manifest["pools"]["D_init"][0]
    manifest["pools"]["H_pass"].append(first)
    with pytest.raises(ValueError, match="overlap|family"):
        validate_manifest(manifest, _tasks())
    with pytest.raises(ValueError, match="H_pass"):
        select_pool_rows(_tasks(), build_manifest(_tasks()), ("D_init", "H_pass"), purpose="training")


def test_freeze_requires_nonempty_active_library_and_hash(tmp_path):
    pool = tmp_path / "experience_pool.jsonl"
    pool.write_text(json.dumps({"invariant_id": "p", "status": "provisional"}) + "\n", encoding="utf-8")
    with pytest.raises(FreezeQualificationError, match="no_active"):
        qualify_freeze(pool, tmp_path / "frozen", policy="C3-3", expected_pool_sha256=hashlib.sha256(pool.read_bytes()).hexdigest())

    pool.write_text("\n".join([
        json.dumps({"invariant_id": "a", "status": "active", "quality_score": 0.9,
                    "independent_validity": True, "h_pass_regression": True,
                    "source": {"stage": "phase2"}}),
        json.dumps({"invariant_id": "r", "status": "retired", "source": {"stage": "phase1"}}),
    ]) + "\n", encoding="utf-8")
    result = qualify_freeze(pool, tmp_path / "frozen", policy="C3-3", expected_pool_sha256=hashlib.sha256(pool.read_bytes()).hexdigest())
    assert result["eligible"] is True
    assert result["frozen_count"] == 1
    assert result["status_counts"] == {"active": 1, "retired": 1}


def test_freeze_policy_layers_are_distinct(tmp_path):
    pool = tmp_path / "experience_pool.jsonl"
    pool.write_text(json.dumps({"invariant_id": "a", "status": "active", "quality_score": 0.9,
                                "independent_validity": True, "h_pass_regression": False}) + "\n", encoding="utf-8")
    digest = hashlib.sha256(pool.read_bytes()).hexdigest()
    assert qualify_freeze(pool, tmp_path / "c31", policy="C3-1", expected_pool_sha256=digest)["frozen_count"] == 1
    with pytest.raises(FreezeQualificationError, match="no_active_nodes_after_policy"):
        qualify_freeze(pool, tmp_path / "c33", policy="C3-3", expected_pool_sha256=digest)


def test_existing_cle_snapshot_audit_accepts_provisional_nodes(tmp_path):
    pool = tmp_path / "experience_pool.jsonl"
    rows = [
        {"invariant_id": "p", "status": "provisional", "source": {"stage": "phase1"}},
        {"invariant_id": "r", "status": "retired", "source": {"stage": "phase1"}},
    ]
    pool.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    (frozen / "m_star.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = audit_existing_freeze(
        pool, frozen, policy="C3-0",
        expected_pool_sha256=hashlib.sha256(pool.read_bytes()).hexdigest(),
    )
    assert result["source"] == "cle_runner_freeze_tree"
    assert result["frozen_count"] == 2
    assert result["active_count"] == 0


def test_jsonl_validation_reports_truncated_tail_and_does_not_accept_partial_pool(tmp_path):
    pool = tmp_path / "experience_pool.jsonl"
    pool.write_text(json.dumps({"invariant_id": "ok", "status": "provisional"}) +
                    "\n{\"invariant_id\": \"cut", encoding="utf-8")
    with pytest.raises(JsonlValidationError) as exc:
        validate_jsonl(pool, report_path=tmp_path / "jsonl_validation.json")
    assert exc.value.report["valid_rows"] == 1
    assert exc.value.report["invalid_rows"] == 1
    assert exc.value.report["invalid"][0]["truncated_tail"] is True
    report = json.loads((tmp_path / "jsonl_validation.json").read_text(encoding="utf-8"))
    assert report["valid"] is False
    with pytest.raises(JsonlValidationError):
        audit_existing_freeze(pool, tmp_path / "frozen", policy="C3-0")


def test_report_summary_keeps_measurement_budget_and_heldout_labels():
    rows = [
        {"arm": "C2-2", "dataset": "Base", "task_id": "a", "measured": True, "functional": True,
         "security": True, "joint": True, "usage": {"calls": 3, "total_tokens": 10}},
        {"arm": "C2-3", "dataset": "Base", "task_id": "a", "measured": True, "functional": True,
         "security": True, "joint": False, "usage": {"calls": 4, "total_tokens": None}},
        {"arm": "C2-2", "dataset": "H_pass", "task_id": "h", "measured": False, "usage": {"calls": 1}},
    ]
    summary = summarize_matrix(rows, comparisons=[("C2-2", "C2-3")])
    assert summary["datasets"]["Base"]["evaluation_role"] == "final_external_test"
    assert summary["datasets"]["H_pass"]["evaluation_role"] == "held_out_final_cle_evaluation"
    assert summary["arms"]["C2-3"]["Base"]["unmeasured"] == 0
    assert summary["arms"]["C2-3"]["Base"]["total_tokens"] is None

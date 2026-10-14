"""离线贯通真实 CLI：三轮完成后全量门控、冻结、汇总与禁止覆盖证据。"""
import copy
import json
import sys

import pytest

from methods.sct_trajectory import closed_loop, global_gate_runtime, run_closed_loop
from methods.sct_trajectory.hsk_tree import LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.schemas import RolloutTrace


def json_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_actual_main_runs_three_rounds_then_one_global_gate_and_freezes_consistently(tmp_path, monkeypatch):
    out = tmp_path / "translation_work/sct_runs/offline_branch"
    source_file = tmp_path / "methods/sct_trajectory/offline_fixture.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("# frozen source fixture", encoding="utf-8")
    evidence_file = tmp_path / "methods/sct_agent/validation_evidence.py"
    evidence_file.parent.mkdir(parents=True)
    evidence_file.write_text("# evidence fixture", encoding="utf-8")
    data_file = tmp_path / "data/external/secodeplt/secodeplt/data.json"
    data_file.parent.mkdir(parents=True)
    data_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(run_closed_loop, "PROJECT_ROOT", tmp_path)
    tasks = [{"index": i, "CWE_ID": "22", "family_id": f"family{i}",
              "task_description": {"description": "return True", "function_name": "f"},
              "unittest": {"testcases": "PRIVATE_TEST"}} for i in (1, 2, 3)]
    monkeypatch.setattr(run_closed_loop, "_load_tasks", lambda limit: copy.deepcopy(tasks))
    monkeypatch.setattr(run_closed_loop, "assign_families_atomic",
                        lambda *args: {"source_pool": [1], "replay_pool": [2], "audit_pool": [3]})
    events, source_refs = [], []

    def request(prompt):
        assert "PRIVATE_TEST" not in prompt
        if prompt.startswith("Perform initial task threat analysis."):
            value = {"vulnerability_hypothesis": ["risk"], "functional_invariants": ["return bool"]}
        elif prompt.startswith("Generate complete runnable Python code"):
            cards = json.loads(prompt.split("Conditional experience: ", 1)[1])
            value = "def f(): return " + ("False" if cards else "True")
        else:
            raise AssertionError("unexpected model phase")
        return {"choices": [{"message": {"content": json.dumps(value) if isinstance(value, dict) else value}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
    monkeypatch.setattr(run_closed_loop, "_requester", lambda *args, **kwargs: request)

    def seed(self, source, *, repairs, on_item):
        assert [row["index"] for row in source] == [1]
        node = SecurityInvariantNode("bad", "22", "bad suggestion", status="active",
                                     language_leaves={"python": LanguageLeaf("python")},
                                     source={"stage": "phase1", "task_id": 1})
        self.experience_pool.append(node)
        self.tree.insert_node(node)
        source_refs.append(node)
        result = {"task_id": 1, "outcome": "seed_active"}
        on_item(result)
        return {"tree_size": 1, "pool_size": 1, "results": [result]}
    monkeypatch.setattr(closed_loop.CleRunner, "phase1_seed", seed)

    def phase2(self, pool, **kwargs):
        round_index = kwargs["round_index"]
        events.append(f"round{round_index}")
        evidence = {"functional": {"status": "fail"}, "security": {"status": "fail"}}
        branches = [{"branch_id": f"b{i}", "code": "def f(): return False", "state": "D",
                     "measured": True, "evidence": evidence, "cards": [], "joint": False} for i in (1, 2, 3)]
        trace = RolloutTrace(task_id="2", cwe="22", round=round_index, states=["D"], evidence=[evidence],
                            generated_codes=["def f(): return False"], branches=branches,
                            branch_selection={"index": 0, "policy": "training_oracle_first_joint_else_first"})
        self.traces.append(trace)
        kwargs["on_item"]({"trace": trace})
        return {"traces": [trace.to_dict()], "selected": 1, "positive_candidates": 0,
                "negative_candidates": 0, "ledger_entries": 0}
    monkeypatch.setattr(closed_loop.CleRunner, "phase2_evolve", phase2)
    monkeypatch.setattr(closed_loop.CleRunner, "phase3_audit",
                        lambda *args, **kwargs: pytest.fail("candidate gate must be deferred"))
    monkeypatch.setattr(closed_loop.CleRunner, "final_evaluate",
                        lambda *args, **kwargs: pytest.fail("global filtered arm must not be generated again"))

    class Retriever:
        def __init__(self, *args, **kwargs):
            pass
        def search(self, query, *, limit, pool_nodes):
            return [{"invariant_id": n.invariant_id, "high_level_invariant": n.high_level_invariant,
                     "status": n.status} for n in pool_nodes]
    monkeypatch.setattr(global_gate_runtime, "HskTreeRetriever", Retriever)
    def validate(row, code, timeout):
        assert row["index"] == 3
        status = "pass" if "True" in code else "fail"
        return {"functional": {"status": status}, "security": {"status": status}}, None
    monkeypatch.setattr(closed_loop, "validate_and_state", validate)
    original_gate = global_gate_runtime.finalize_global_gate
    def gate(*args, **kwargs):
        assert events == ["round1", "round2", "round3"]
        events.append("global_gate")
        return original_gate(*args, **kwargs)
    monkeypatch.setattr(global_gate_runtime, "finalize_global_gate", gate)
    argv = ["run_closed_loop", "--out", str(out), "--branch-count", "3", "--gate-mode", "global",
            "--context-pipeline", "--rounds", "3", "--workers", "1"]
    monkeypatch.setattr(sys, "argv", argv)
    run_closed_loop.main()

    assert events == ["round1", "round2", "round3", "global_gate"]
    assert [row["round"] for row in json_rows(out / "rounds.jsonl")] == [1, 2, 3]
    assert len(json_rows(out / "completed_rounds.jsonl")) == 3
    assert len(json_rows(out / "trajectories.jsonl")) == 3
    assert source_refs[0].status == "active"
    assert json.loads((out / "gate_input_memory.json").read_text())[0]["status"] == "active"
    assert json_rows(out / "pool_snapshots/phase1.jsonl")[0]["status"] == "active"
    assert json_rows(out / "frozen/m_star.jsonl")[0]["status"] == "retired"
    tree_payload = json.loads((out / "tree.json").read_text())
    assert "retired" in json.dumps(tree_payload) and '"active"' not in json.dumps(tree_payload)
    assert json.loads((out / "status.json").read_text())["status"] == "completed"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["branch_count"] == 3 and summary["gate_mode"] == "global"
    assert summary["final_eval"]["joint_pass"] == 1
    assert len(summary["evolution_rounds"]) == 3
    assert json_rows(out / "gate_records.jsonl")[0]["status"] == "retired"
    assert json_rows(out / "final_eval.jsonl")[0]["arm"] == "filtered"
    assert (out / "source_manifest.json").exists()

    # 用同一命令重进必须在任何清理/模型调用之前拒绝，已有证据逐字节保持。
    evidence_before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    with pytest.raises(SystemExit) as exc:
        run_closed_loop.main()
    assert exc.value.code == 2
    assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == evidence_before

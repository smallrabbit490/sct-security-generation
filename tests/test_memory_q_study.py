"""固定库runner的前向/采纳/奖励连线，使用脚本化模型及测量替身。"""
import json
import pytest

from methods.sct_trajectory.hsk_tree import LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.run_memory_q_study import FixedMemoryQStudy, load_inputs, main, prepare_initial_analysis


class Scores:
    model = "offline-test-scores"
    usage = {"calls": 0}

    def cosine_scores(self, query, texts):
        return [0.9 - i * 0.1 for i, _ in enumerate(texts)]


class ScriptedModel:
    def __init__(self):
        self.generations = 0

    def __call__(self, prompt):
        if prompt.startswith("Select experience"):
            offered = json.loads(prompt.rsplit("CANDIDATES:\n", 1)[1])
            value = {"selected": list(range(1, min(len(offered), 3)+1))}
        elif prompt.startswith("Perform"):
            value = {"vulnerability_hypothesis": ["Preserve the contract."],
                     "functional_invariants": ["Return the expected value."]}
            if "experience-conditioned reanalysis" in prompt:
                value.update(applied_experience_ids=[str(self.generations % 2)], rejected_experiences=[])
        elif prompt.startswith("Plan"):
            value = {"Preserved_Func": ["Return the expected value."], "Patch_Scope": ["Function body."]}
        else:
            self.generations += 1
            value = f"def f(): return {self.generations}"
        content = value if isinstance(value, str) else json.dumps(value)
        return {"choices": [{"message": {"content": content}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}


def memories():
    return [SecurityInvariantNode(str(i), "22", f"rule {i}",
            language_leaves={"python": LanguageLeaf("python")}) for i in range(4)]


def row(identifier=10):
    return {"index": identifier, "CWE_ID": "22", "family_id": str(identifier),
            "task_description": {"function_name": "f", "description": "Return the expected value."}}


def test_shared_initial_analysis_rejects_truncated_response_explicitly():
    def truncated(prompt):
        return {"choices": [{"finish_reason": "length", "message": {"content": "{"}}]}
    with pytest.raises(ValueError, match="model_output_truncated"):
        prepare_initial_analysis(row(), truncated)


def test_calibration_attributes_c0_c1_before_early_exit_without_changing_content():
    nodes = memories()
    def validate(task, code, *, timeout):
        first = code.endswith("1")
        return {"functional": {"status": "fail" if first else "pass"},
                "security": {"status": "pass"}}, "C" if first else "A"
    study = FixedMemoryQStudy(nodes, ScriptedModel(), Scores(), delta=0.1, validator=validate)
    results = study.calibrate([row()])
    assert [a["adopted_ids"] for a in results[0]["attempts"]] == [["0"], ["1"]]
    assert [(n.q_value, n.q_visits) for n in nodes] == [(-0.3, 1), (0.3, 1), (0, 0), (0, 0)]
    assert [(e["attempt"], e["reward"]) for e in results[0]["q_events"]] == [(0, -1), (1, 1)]
    assert [n.high_level_invariant for n in nodes] == [f"rule {i}" for i in range(4)]


def test_compare_is_frozen_and_first_success_stops():
    nodes = memories()
    nodes[0].q_value, nodes[0].q_visits = 0.4, 3
    def validate(task, code, *, timeout):
        return {"functional": {"status": "pass"}, "security": {"status": "pass"}}, "A"
    model = ScriptedModel()
    study = FixedMemoryQStudy(nodes, model, Scores(), delta=0.1, validator=validate)
    before = [n.to_dict() for n in nodes]
    results = study.compare([row()])
    assert {r["policy"] for r in results} == {"semantic_llm", "semantic_sim", "semantic_q"}
    assert all(len(r["attempts"]) == 1 and not r["q_events"] for r in results)
    assert before == [n.to_dict() for n in nodes]
    assert model.generations == 3
    sim, q = [next(r for r in results if r["policy"] == p) for p in ("semantic_sim", "semantic_q")]
    assert sim["attempts"][0]["retrieval_trace"]["candidate_ids"] == q["attempts"][0]["retrieval_trace"]["candidate_ids"]


def test_compare_attributes_embedding_to_each_policy_and_keeps_shared_analysis_separate():
    class MeteredScores(Scores):
        def __init__(self):
            self._usage = {"calls": 0, "prompt_tokens": 0}

        @property
        def usage(self):
            return dict(self._usage)

        def cosine_scores(self, query, texts):
            self._usage["calls"] += 1
            self._usage["prompt_tokens"] += 10
            return super().cosine_scores(query, texts)

    study = FixedMemoryQStudy(memories(), ScriptedModel(), MeteredScores(), delta=0.1,
        validator=lambda *a, **k: ({"functional": {"status": "pass"}, "security": {"status": "pass"}}, "A"))
    study.compare([row()])
    cost = study.cost_breakdown()
    assert cost["shared"]["shared_initial"]["embedding"] == {"calls": 0, "prompt_tokens": 0}
    assert all(item["embedding"] == {"calls": 1, "prompt_tokens": 10} for item in cost["by_policy"].values())


def test_degraded_pipeline_keeps_measured_score_but_does_not_award_q():
    model = ScriptedModel()
    def degraded(prompt):
        if prompt.startswith("Plan"):
            return {"choices": [{"message": {"content": "{}"}}]}
        return model(prompt)
    def validate(task, code, *, timeout):
        return {"functional": {"status": "pass"}, "security": {"status": "pass"}}, "A"
    nodes = memories()
    result = FixedMemoryQStudy(nodes, degraded, Scores(), delta=0.1, validator=validate).calibrate([row()])[0]
    assert result["state"] == "A" and result["attempts"][0]["pipeline_error"]
    assert all(n.q_visits == 0 for n in nodes)
    assert result["q_events"][0]["reward"] is None


def inputs(tmp_path):
    data = [row(i) for i in (1, 2, 3)]
    memory = memories()[0].to_dict()
    memory["source"] = {"task_id": 1, "stage": "phase1"}
    files = {"memory.jsonl": memory, "data.json": data,
             "families.json": {"row_classification": {str(i): {"seed_family_id": str(i)} for i in (1, 2, 3)}},
             "pools.json": {"source": [{"task_id": 1}], "replay": [{"task_id": 2}], "audit": [{"task_id": 3}]}}
    for name, value in files.items():
        (tmp_path/name).write_text(json.dumps(value), encoding="utf-8")
    return ["--memory", str(tmp_path/"memory.jsonl"), "--dataset", str(tmp_path/"data.json"),
            "--family-manifest", str(tmp_path/"families.json")]


def test_offline_cli_does_not_request_network_or_execute_tasks(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("offline must not request a service")
    monkeypatch.setattr("urllib.request.urlopen", forbidden)
    result = main(["--stage", "offline", "--out", str(tmp_path/"out"), *inputs(tmp_path)])
    assert result["memory_entries"] == 1 and result["model_calls_this_run"] == 0
    assert result["ready_for_calibration"] is False
    assert (tmp_path/"out/input_memory.jsonl").exists()
    with pytest.raises(SystemExit):
        main(["--stage", "calibrate", "--out", str(tmp_path/"no_run"), *inputs(tmp_path)])
    assert not (tmp_path/"no_run").exists()


def test_pool_boundaries_use_original_family_mapping(tmp_path):
    inputs(tmp_path)
    args = [tmp_path/p for p in ("memory.jsonl", "data.json", "families.json", "pools.json")]
    _, _, pools = load_inputs(*args)
    assert pools == {"D_init": ["1"], "D_grow": ["2"], "D_gate": ["3"]}
    f = json.loads((tmp_path/"families.json").read_text(encoding="utf-8"))
    f["row_classification"]["3"]["seed_family_id"] = "2"
    (tmp_path/"families.json").write_text(json.dumps(f), encoding="utf-8")
    with pytest.raises(ValueError, match="overlap"):
        load_inputs(*args)


def test_calibrate_and_compare_cli_with_injected_services(tmp_path, monkeypatch):
    """走真实CLI/输出/冻结核对，用替身替换唯一两个服务边界及执行器。"""
    common = inputs(tmp_path)
    memory_file = tmp_path/"memory.jsonl"
    first = json.loads(memory_file.read_text(encoding="utf-8"))
    second = {**first, "invariant_id": "1", "high_level_invariant": "another rule"}
    memory_file.write_text(json.dumps(first)+"\n"+json.dumps(second), encoding="utf-8")
    from methods.sct_trajectory import closed_loop, run_closed_loop, semantic_retrieval
    model = ScriptedModel()
    monkeypatch.setattr(run_closed_loop, "_requester", lambda *a, **k: model)
    monkeypatch.setattr(semantic_retrieval, "EmbeddingClient", lambda **k: Scores())
    monkeypatch.setattr(closed_loop, "validate_and_state", lambda *a, **k: (
        {"functional": {"status": "pass"}, "security": {"status": "pass"}}, "A"))
    grow = main(["--stage", "calibrate", "--out", str(tmp_path/"grow"),
                 "--pools", str(tmp_path/"pools.json"), *common])
    assert grow["q_visited"] == 1 and grow["delta"] == pytest.approx(0.88)
    assert (tmp_path/"grow/prepared_queries.jsonl").exists()
    compared = main(["--stage", "compare", "--out", str(tmp_path/"compare"),
        "--memory", str(tmp_path/"grow/frozen/m_star_q.jsonl"),
        "--calibration", str(tmp_path/"grow/calibration.json"),
        "--pools", str(tmp_path/"pools.json"), *common[2:]])
    assert compared["paired"]["n"] == 1
    assert compared["paired"]["delta_joint"] == 0
    cost = json.loads((tmp_path/"compare/cost.json").read_text(encoding="utf-8"))
    # 共同初析1次；LLM选卡臂另有选卡+复析+规划+生成，数值臂各3次。
    assert cost["shared"]["shared_initial"]["llm"]["calls"] == 1
    assert {policy: item["llm"]["calls"] for policy, item in cost["by_policy"].items()} == {
        "semantic_llm": 4, "semantic_sim": 3, "semantic_q": 3}
    assert sum(item["llm"]["calls"] for item in cost["by_policy"].values()) + 1 == cost["llm"]["total"]["calls"]
    assert all(item["elapsed_seconds"] >= 0 for item in cost["by_policy"].values())
    assert "embedding" in cost["shared"]["shared_initial"]
    assert (tmp_path/"compare/memory_q_events.jsonl").read_text(encoding="utf-8") == ""
    frozen = tmp_path/"grow/frozen/m_star_q.jsonl"
    changed = [json.loads(line) for line in frozen.read_text(encoding="utf-8").splitlines()]
    changed[0]["q_value"] = -0.8
    frozen.write_text("\n".join(json.dumps(r) for r in changed), encoding="utf-8")
    calls_before = model.generations
    with pytest.raises(SystemExit):
        main(["--stage", "compare", "--out", str(tmp_path/"tampered"),
            "--memory", str(frozen), "--calibration", str(tmp_path/"grow/calibration.json"),
            "--pools", str(tmp_path/"pools.json"), *common[2:]])
    assert model.generations == calls_before and not (tmp_path/"tampered").exists()


def test_api_failure_during_threshold_preparation_preserves_cost(tmp_path, monkeypatch):
    common = inputs(tmp_path)
    from methods.sct_trajectory import run_closed_loop, semantic_retrieval
    def failed(prompt):
        raise RuntimeError("test service unavailable")
    monkeypatch.setattr(run_closed_loop, "_requester", lambda *a, **k: failed)
    monkeypatch.setattr(semantic_retrieval, "EmbeddingClient", lambda **k: Scores())
    with pytest.raises(RuntimeError, match="unavailable"):
        main(["--stage", "calibrate", "--out", str(tmp_path/"failed"),
              "--pools", str(tmp_path/"pools.json"), *common])
    cost = json.loads((tmp_path/"failed/cost.json").read_text(encoding="utf-8"))
    assert cost["llm"]["total"]["errors"] == 1
    assert cost["shared"]["shared_threshold"]["llm"]["errors"] == 1
    assert not (tmp_path/"failed/summary.json").exists()

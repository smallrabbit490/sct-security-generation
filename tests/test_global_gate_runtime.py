"""训练收尾真实门控适配：隔离外部请求与验证，保留实际配对/归因/停用链路。"""
import json
from types import SimpleNamespace

from methods.sct_trajectory import global_gate_runtime
from methods.sct_trajectory.ablation import get_config
from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.retriever import HskTreeRetriever


def response(value):
    return {"choices": [{"message": {"content": json.dumps(value) if isinstance(value, dict) else value}}]}


def make_runner(monkeypatch):
    prompts, retrievals, validations, stages, progress = [], [], [], [], []
    bad = SecurityInvariantNode("bad", "22", "unsafe route", language_leaves={"python": LanguageLeaf("python")})
    good = SecurityInvariantNode("good", "22", "safe route", language_leaves={"python": LanguageLeaf("python")})
    source_pool = [bad, good]
    source_tree = HskTree()
    source_tree.insert_node(bad)
    source_tree.insert_node(good)

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        def search(self, query, *, limit, pool_nodes):
            retrievals.append([node.invariant_id for node in pool_nodes])
            assert "unittest" not in query
            assert query["threat_analysis"]["functional_invariants"] == ["retain valid paths"]
            return [{"invariant_id": node.invariant_id, "high_level_invariant": node.high_level_invariant,
                     "status": node.status} for node in pool_nodes]

    def request(prompt):
        prompts.append(prompt)
        assert "SECRET_TEST" not in prompt
        if prompt.startswith("Perform initial task threat analysis."):
            return response({"vulnerability_hypothesis": ["path traversal"], "functional_invariants": ["retain valid paths"]})
        assert "以前的修复" not in prompt and "执行反馈" not in prompt
        cards = json.loads(prompt.split("Conditional experience: ", 1)[1])
        return response("def f(): return " + ("False" if any(c["invariant_id"] == "bad" for c in cards) else "True"))

    def validate(row, code, timeout):
        validations.append(code)
        passed = "True" in code
        result = {"functional": {"status": "pass" if passed else "fail"},
                  "security": {"status": "pass" if passed else "fail"}}
        return result, None

    monkeypatch.setattr(global_gate_runtime, "HskTreeRetriever", FakeRetriever)
    monkeypatch.setattr("methods.sct_trajectory.closed_loop.validate_and_state", validate)
    runner = SimpleNamespace(experience_pool=source_pool, tree=source_tree,
        cost=SimpleNamespace(set_stage=stages.append), req_gen=request, ablation=get_config("A7"),
        retrieval_mode="hier_llm", min_llm_score=0, cross_cwe_min_score=0,
        antioverdefense_bonus=0, same_task_bonus=0, workers=2, timeout=30, progress=progress.append)
    tasks = [{"index": 1, "CWE_ID": "22", "task_description": {"description": "read valid paths"},
              "unittest": {"testcases": "SECRET_TEST"}}]
    return runner, tasks, source_pool, source_tree, prompts, retrievals, validations


def test_actual_gate_adapter_preserves_source_and_freezes_retired_only_in_copy(monkeypatch, tmp_path):
    runner, tasks, source_pool, source_tree, prompts, retrievals, validations = make_runner(monkeypatch)
    source_payload = [n.to_dict() for n in source_pool]
    result = global_gate_runtime.finalize_global_gate(runner, tasks, tmp_path)
    assert result["gate_report"]["retired_ids"] == ["bad"]
    assert result["summary"]["joint_pass"] == 1
    assert result["summary"]["generation_policy"] == "single_generation_no_repair"
    assert not result["summary"]["independent_heldout"]
    assert [n.to_dict() for n in source_pool] == source_payload
    assert source_tree.family("22").invariants[0].status == "provisional"
    assert runner.experience_pool is not source_pool and runner.tree is not source_tree
    assert next(n for n in runner.experience_pool if n.invariant_id == "bad").status == "retired"
    assert json.loads((tmp_path / "gate_input_memory.json").read_text(encoding="utf-8")) == source_payload
    events = [json.loads(line) for line in (tmp_path / "global_gate_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {event["kind"] for event in events} >= {"row", "attribution", "decision"}
    assert len(validations) == 13  # baseline+memory, 2 cards * (drop+2 full/drop), filtered.
    assert len(prompts) == 14  # 一个仅供检索的初析，不增加复析/规划/修复请求。
    assert retrievals == [["bad", "good"], ["good"]]

    # 冻结审计副本保留退役记录；实际检索严格屏蔽，不物理删除源库审计证据。
    frozen = CleRunner.freeze_tree(runner)
    retired = [n for n in frozen if n["status"] == "retired"]
    assert [n["invariant_id"] for n in retired] == ["bad"]
    loaded = [SecurityInvariantNode.from_dict(n) for n in frozen]
    cards = HskTreeRetriever(HskTree(), ablation=get_config("A7"), retrieval_mode="hier_rule").search(
        {"CWE_ID": "22", "language": "python", "description": "safe route"}, pool_nodes=loaded)
    assert "bad" not in [card["invariant_id"] for card in cards]
    assert "good" in [card["invariant_id"] for card in cards]


def test_adapter_validator_incident_never_retires_source_card(monkeypatch, tmp_path):
    runner, tasks, source_pool, source_tree, prompts, retrievals, validations = make_runner(monkeypatch)
    def failed_validator(row, code, timeout):
        status = "fail" if "False" in code else "pass"
        error = "local_worker_error" if status == "fail" else None
        return {"functional": {"status": status, "error_type": error},
                "security": {"status": status, "error_type": error}}, None
    monkeypatch.setattr("methods.sct_trajectory.closed_loop.validate_and_state", failed_validator)
    result = global_gate_runtime.finalize_global_gate(runner, tasks, tmp_path)
    assert result["gate_report"]["retired_ids"] == []
    assert result["gate_report"]["attribution"] == []
    assert result["summary"]["global_gate"]["arms"]["filtered"]["unmeasured"] == 1
    assert all(node.status == "provisional" for node in source_pool)
    assert len(prompts) == 4  # 一次初析 + baseline/memory/filtered；不启动故障归因或修复。

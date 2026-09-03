"""Machine-checkable fidelity contracts for the five agent baselines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowContract:
    source: str
    required_stage_groups: tuple[tuple[str, ...], ...]
    minimum_model_calls: int
    failure_stage: str | None = None


CONTRACTS: dict[str, WorkflowContract] = {
    "AutoSafeCoder": WorkflowContract(
        source="AutoSafeCoder_official/main.py",
        required_stage_groups=(("programmer",), ("static_review",), ("validation",)),
        minimum_model_calls=2,
        failure_stage="fuzz_validation_repair",
    ),
    "AgentCoder": WorkflowContract(
        source="AgentCoder_official/AgentCoder/",
        required_stage_groups=(("test_designer",), ("programmer",), ("agentcoder_epoch",)),
        minimum_model_calls=2,
    ),
    "RA-Gen": WorkflowContract(
        source="ragen_function_level/src/agents/",
        required_stage_groups=(("planner",), ("searcher",), ("codegen",), ("extractor",), ("ragen_iteration",)),
        minimum_model_calls=4,
    ),
    "SWE-Agent": WorkflowContract(
        source="SWE_agent_official/sweagent/",
        required_stage_groups=(("edit_main_file",), ("run_tests",)),
        minimum_model_calls=1,
        failure_stage="edit_after_test_failure",
    ),
    "SecAwareCoder": WorkflowContract(
        source="SecAwareCoder/security_aware_code_generation_graph.py",
        required_stage_groups=(("security_analyzer",), ("testcase_generator",), ("programmer",), ("code_executor",)),
        minimum_model_calls=3,
        failure_stage="code_repairer",
    ),
}


def validate_trace(
    method_name: str,
    trace: list[dict[str, Any]],
    *,
    model_calls: int,
) -> dict[str, Any]:
    """Validate observable workflow stages without inspecting prompt content."""
    if method_name not in CONTRACTS:
        raise ValueError(f"no agent fidelity contract for {method_name}")

    contract = CONTRACTS[method_name]
    observed = [str(event.get("stage") or "") for event in trace]
    observed_set = set(observed)
    missing_groups = [
        list(group)
        for group in contract.required_stage_groups
        if not any(stage in observed_set for stage in group)
    ]
    call_requirement_met = model_calls >= contract.minimum_model_calls

    last_eval = next(
        (
            event.get("eval")
            for event in reversed(trace)
            if isinstance(event.get("eval"), dict)
        ),
        None,
    )
    missing_failure_stage = None
    if (
        last_eval is not None
        and not bool(last_eval.get("fun_sec"))
        and contract.failure_stage
        and contract.failure_stage not in observed_set
    ):
        missing_failure_stage = contract.failure_stage

    passed = not missing_groups and call_requirement_met and missing_failure_stage is None
    return {
        "passed": passed,
        "source": contract.source,
        "observed_stages": observed,
        "missing_stage_groups": missing_groups,
        "model_calls": model_calls,
        "minimum_model_calls": contract.minimum_model_calls,
        "model_call_requirement_met": call_requirement_met,
        "missing_failure_stage": missing_failure_stage,
    }

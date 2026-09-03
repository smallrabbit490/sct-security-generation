import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "methods" / "workflow_baselines"))

from fidelity import CONTRACTS, validate_trace  # noqa: E402
import run_true_agent_workflows as runner  # noqa: E402


VALID_TRACES = {
    "AutoSafeCoder": [
        {"stage": "programmer"},
        {"stage": "static_review"},
        {"stage": "validation", "eval": {"fun_sec": True}},
    ],
    "AgentCoder": [
        {"stage": "test_designer"},
        {"stage": "programmer"},
        {"stage": "agentcoder_epoch", "accepted": True},
    ],
    "RA-Gen": [
        {"stage": "planner"},
        {"stage": "searcher"},
        {"stage": "codegen"},
        {"stage": "extractor"},
        {"stage": "ragen_iteration", "eval": {"fun_sec": True}},
    ],
    "SWE-Agent": [
        {"stage": "edit_main_file"},
        {"stage": "run_tests", "eval": {"fun_sec": True}},
    ],
    "SecAwareCoder": [
        {"stage": "security_analyzer"},
        {"stage": "testcase_generator"},
        {"stage": "programmer"},
        {"stage": "code_executor", "eval": {"fun_sec": True}},
    ],
}


class AgentWorkflowFidelityTests(unittest.TestCase):
    def test_contracts_cover_exactly_the_five_agent_baselines(self):
        self.assertEqual(
            set(CONTRACTS),
            {"AutoSafeCoder", "AgentCoder", "RA-Gen", "SWE-Agent", "SecAwareCoder"},
        )

    def test_complete_multistage_traces_pass(self):
        for method, trace in VALID_TRACES.items():
            with self.subTest(method=method):
                result = validate_trace(method, trace, model_calls=CONTRACTS[method].minimum_model_calls)
                self.assertTrue(result["passed"], result)
                self.assertEqual(result["missing_stage_groups"], [])

    def test_empty_and_direct_prompt_traces_fail_for_every_agent(self):
        for method, contract in CONTRACTS.items():
            with self.subTest(method=method, trace="empty"):
                self.assertFalse(validate_trace(method, [], model_calls=0)["passed"])
            with self.subTest(method=method, trace="direct"):
                result = validate_trace(
                    method,
                    [{"stage": "direct_generate"}],
                    model_calls=contract.minimum_model_calls,
                )
                self.assertFalse(result["passed"])
                self.assertTrue(result["missing_stage_groups"])

    def test_insufficient_model_calls_fail_even_with_all_stages(self):
        for method, trace in VALID_TRACES.items():
            with self.subTest(method=method):
                result = validate_trace(method, trace, model_calls=0)
                self.assertFalse(result["passed"])
                self.assertFalse(result["model_call_requirement_met"])

    def test_failed_validation_requires_the_original_feedback_stage(self):
        autosafe = [
            {"stage": "programmer"},
            {"stage": "static_review"},
            {"stage": "validation", "eval": {"fun_sec": False}},
        ]
        result = validate_trace("AutoSafeCoder", autosafe, model_calls=2)

        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_failure_stage"], "fuzz_validation_repair")

    def test_token_merge_preserves_model_call_count(self):
        merged = runner.merge_tokens(
            {"total_tokens": 10, "model_calls": 1},
            {"total_tokens": 20, "model_calls": 1},
        )

        self.assertEqual(merged["total_tokens"], 30)
        self.assertEqual(merged["model_calls"], 2)

    def test_agent_result_row_contains_machine_checked_fidelity(self):
        method = {"name": "SWE-Agent", "group": "agent", "style": "swe_agent"}
        result = {
            "raw": "raw",
            "code": "def solve(): return 1",
            "tokens": {"total_tokens": 10, "model_calls": 1},
            "error": None,
            "eval": {"fun": True, "sec": True, "fun_sec": True},
            "trace": VALID_TRACES["SWE-Agent"],
        }

        row = runner.row_from_result(method, "python", {"ID": "task", "Entry_Point": "solve"}, result)

        self.assertTrue(row["workflow_completed"])
        self.assertTrue(row["fidelity_passed"])
        self.assertTrue(row["fidelity_details"]["model_call_requirement_met"])


if __name__ == "__main__":
    unittest.main()

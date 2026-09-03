import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "methods" / "legacy_prompt_adapters"))

import run_actual_5_python_methods as actual  # noqa: E402
import run_language_method_matrix as matrix  # noqa: E402

from translation_pipeline.models import ValidationResult  # noqa: E402
from translation_pipeline import python_validator  # noqa: E402


class BaselineExtractionTests(unittest.TestCase):
    def test_python_adapter_extracts_fenced_code_without_historical_harness(self):
        original_base = actual.base
        actual.base = None
        self.addCleanup(setattr, actual, "base", original_base)

        code = actual.extract_code("explanation\n```python\ndef solve():\n    return 1\n```", {"style": "greedy"})

        self.assertEqual(code, "def solve():\n    return 1")

    def test_language_matrix_normalizes_go_without_historical_harness(self):
        original_base = actual.base
        actual.base = None
        self.addCleanup(setattr, actual, "base", original_base)

        code = matrix.extract_code("```go\nfunc solve() int { return 1 }\n```", {"style": "cot"}, "go")

        self.assertEqual(code, "package main\n\nfunc solve() int { return 1 }")

    def test_language_matrix_extracts_code_when_base_module_has_no_harness(self):
        original_base = actual.base
        actual.base = SimpleNamespace(harness=None)
        self.addCleanup(setattr, actual, "base", original_base)

        code = matrix.extract_code("```python\ndef solve():\n    return 2\n```", {"style": "greedy"}, "python")

        self.assertEqual(code, "def solve():\n    return 2")


class BaselineEvaluationTests(unittest.TestCase):
    def test_secure_evaluation_uses_current_python_validator_without_historical_harness(self):
        original_base = actual.base
        actual.base = None
        self.addCleanup(setattr, actual, "base", original_base)
        sentinel = ValidationResult(
            ok=False,
            language="python",
            mode="secure",
            stdout="functional output",
            stderr="security failure",
            details={
                "secure_functional": True,
                "secure_security": False,
                "secure_func_sec": False,
            },
        )

        with mock.patch.object(python_validator, "validate_python_secure", return_value=sentinel) as validate:
            result = actual.evaluate_code({"ID": "task", "Entry_Point": "solve"}, "def solve(): return 1", "secure")

        validate.assert_called_once()
        self.assertTrue(result["fun"])
        self.assertFalse(result["sec"])
        self.assertFalse(result["fun_sec"])
        self.assertEqual(result["result"]["stderr"], "security failure")

    def test_matrix_passes_insecure_track_to_python_evaluator(self):
        with mock.patch.object(actual, "evaluate_code", return_value={"fun": False, "sec": False, "fun_sec": False}) as evaluate:
            matrix.evaluate("python", {"ID": "task"}, "code", "insecure")

        evaluate.assert_called_once_with({"ID": "task"}, "code", "insecure")


if __name__ == "__main__":
    unittest.main()

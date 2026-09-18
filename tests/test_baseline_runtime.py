import os
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


class HarnessLookupRegressionTests(unittest.TestCase):
    """C++/Go 的 harness 查找必须能回退到仓库内的 data/harnesses。

    只有历史 ``sandbox_dir`` 一级查找时，harness 找不到会**静默**退化成
    ``compile_run_only_no_security_credit``——C++/Go 拿不到任何安全学分，
    表面上却像"模型全写错了"。这组测试锁住回退逻辑，防止再退化。
    """

    @staticmethod
    def _cpp_task_without_history() -> dict:
        tasks = matrix.load_language_tasks(matrix.PROJECT_ROOT / "data" / "SecEvoBasePlus", "Base", "cpp", 1)
        task = dict(tasks[0])
        # 模拟历史记录失效（换机器/清理运行区后 sandbox_dir 不存在）
        task.pop("Secure Code Test Result", None)
        task.pop("Insecure Code Behavior Result", None)
        return task

    def test_project_root_points_at_repository_root(self):
        """PROJECT_ROOT 曾经写成 parents[2]，指向仓库的上一级。"""
        self.assertEqual(matrix.PROJECT_ROOT.resolve(), ROOT.resolve())

    def test_harness_root_exists(self):
        self.assertTrue(matrix.HARNESS_ROOT.is_dir())

    def test_load_language_tasks_stamps_subset(self):
        tasks = matrix.load_language_tasks(matrix.PROJECT_ROOT / "data" / "SecEvoBasePlus", "Base", "cpp", 1)
        self.assertTrue(tasks)
        self.assertEqual(tasks[0].get("_subset"), "Base")

    def test_subset_marker_does_not_leak_into_prompt(self):
        """_subset 是内部字段，不能改变给模型的提示词。"""
        task = self._cpp_task_without_history()
        with_marker = matrix.prompt_problem_text(task)
        without = dict(task)
        without.pop("_subset", None)
        self.assertEqual(with_marker, matrix.prompt_problem_text(without))
        self.assertNotIn("_subset", with_marker)

    def test_portable_harness_is_found_without_recorded_sandbox_dir(self):
        task = self._cpp_task_without_history()
        source = matrix._source_path_from_saved_harness(task, "cpp", "secure")
        self.assertIsNotNone(source, "必须回退到 data/harnesses")
        self.assertEqual(source.name, "main.cpp")
        self.assertIn("harnesses", source.parts)

    def test_harness_lookup_without_track_keeps_legacy_behaviour(self):
        """不传 track 时保持旧的单级查找，避免影响既有调用点。"""
        task = self._cpp_task_without_history()
        self.assertIsNone(matrix._source_path_from_saved_harness(task, "cpp"))

    def test_entry_signature_and_context_come_from_portable_harness(self):
        task = self._cpp_task_without_history()
        signature = matrix.extract_harness_entry_signature("cpp", task, "secure")
        self.assertTrue(signature, "能取到入口签名，提示词里才会带 harness 契约")
        context = matrix.extract_harness_entry_context("cpp", task, track="secure")
        self.assertTrue(context)

    def test_candidate_harness_assembly_is_not_empty(self):
        task = self._cpp_task_without_history()
        built = matrix.build_candidate_harness_code("cpp", task, "int x = 1;", "secure")
        self.assertIsNotNone(built)
        self.assertIn("int main", built)


class ChatAnywhereCredentialTests(unittest.TestCase):
    """凭据解析顺序必须与 README 的约定一致：环境变量 → apikey.txt → .env 快照。"""

    @staticmethod
    def _runner():
        sys.path.insert(0, str(ROOT / "methods" / "workflow_baselines"))
        import run_true_agent_workflows as runner

        return runner

    def test_profile_loader_does_not_inject_api_key(self):
        """`.env` 是派生快照（可能已欠费），不得遮蔽 apikey.txt。

        实测 2026-09-18：两份 .env 的 key 都是 403 余额不足，而 apikey.txt 可用。
        如果 profile 加载器把 .env 的 key 写进 CHATANYWHERE_API_KEY，
        本来能跑的实验会直接 403。
        """
        runner = self._runner()
        clean = {k: v for k, v in os.environ.items() if k not in ("CHATANYWHERE_API_KEY", "ZHIPU_API_KEY")}
        with mock.patch.dict(os.environ, clean, clear=True):
            runner.apply_chatanywhere_profile("formal")
            self.assertNotIn("CHATANYWHERE_API_KEY", os.environ)

    def test_resolve_prefers_local_key_file_over_profile_snapshot(self):
        runner = self._runner()
        clean = {k: v for k, v in os.environ.items() if k not in ("CHATANYWHERE_API_KEY", "ZHIPU_API_KEY")}
        with mock.patch.dict(os.environ, clean, clear=True):
            with mock.patch.object(runner, "load_local_api_key", return_value="LOCAL-KEY"):
                with mock.patch.object(runner, "_profile_api_key", return_value="SNAPSHOT-KEY"):
                    key, source = runner.resolve_api_key("formal")
        self.assertEqual(key, "LOCAL-KEY")
        self.assertEqual(source, "local:apikey.txt")

    def test_resolve_prefers_explicit_env_var(self):
        runner = self._runner()
        with mock.patch.dict(os.environ, {"CHATANYWHERE_API_KEY": "ENV-KEY"}, clear=False):
            with mock.patch.object(runner, "load_local_api_key", return_value="LOCAL-KEY"):
                key, source = runner.resolve_api_key()
        self.assertEqual(key, "ENV-KEY")
        self.assertEqual(source, "env:CHATANYWHERE_API_KEY")

    def test_resolve_falls_back_to_profile_snapshot_last(self):
        runner = self._runner()
        clean = {k: v for k, v in os.environ.items() if k not in ("CHATANYWHERE_API_KEY", "ZHIPU_API_KEY")}
        with mock.patch.dict(os.environ, clean, clear=True):
            with mock.patch.object(runner, "load_local_api_key", return_value=None):
                with mock.patch.object(runner, "_profile_api_key", return_value="SNAPSHOT-KEY"):
                    key, source = runner.resolve_api_key("test")
        self.assertEqual(key, "SNAPSHOT-KEY")
        self.assertTrue(source.startswith("env-file:"))

    def test_default_model_is_non_reasoning(self):
        """默认模型必须是 deepseek-v3.2：推理模型会吃光 max_tokens 让正文为空。"""
        runner = self._runner()
        self.assertEqual(runner.DEFAULT_MODEL, "deepseek-v3.2")

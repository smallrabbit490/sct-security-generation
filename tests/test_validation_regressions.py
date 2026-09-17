import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))


class DatasetSanitizationTests(unittest.TestCase):
    def test_web_urls_are_not_treated_as_windows_paths(self):
        from sanitize_dataset import clean

        value = 'open("https://example.com/path")'
        self.assertEqual(clean(value), value)

    def test_known_local_workspace_path_is_redacted(self):
        from sanitize_dataset import clean

        value = r'D:\thecourceofdasi\safecodernew\translation_work\sandbox'
        self.assertEqual(clean(value), "<LOCAL_PATH>")


class PythonInsecureClassificationTests(unittest.TestCase):
    def test_matching_function_failure_preserves_insecure_behavior(self):
        from translation_pipeline.python_validator import compute_insecure_match_from_test_results

        result = compute_insecure_match_from_test_results(
            reference_tests={
                "fp": {"passed": False, "error": "AssertionError"},
                "sp": {"passed": False, "error": "AssertionError"},
            },
            candidate_tests={
                "fp": {"passed": False, "error": "AssertionError"},
                "sp": {"passed": True, "error": None},
            },
            reference_timed_out=False,
            candidate_timed_out=False,
        )

        self.assertTrue(result["insecure_behavior_match"])
        self.assertTrue(result["expected_failure_match"])
        self.assertFalse(result["false_secure"])

    def test_timeout_is_not_accepted_as_insecure_behavior(self):
        from translation_pipeline.python_validator import compute_insecure_match_from_test_results

        result = compute_insecure_match_from_test_results(
            reference_tests={"sp": {"passed": False, "error": "AssertionError"}},
            candidate_tests={},
            reference_timed_out=True,
            candidate_timed_out=False,
        )

        self.assertFalse(result["insecure_behavior_match"])
        self.assertFalse(result["expected_failure_match"])

    def test_matching_timeouts_preserve_infinite_loop_behavior(self):
        from translation_pipeline.python_validator import compute_insecure_match_from_test_results

        result = compute_insecure_match_from_test_results(
            reference_tests={},
            candidate_tests={},
            reference_timed_out=True,
            candidate_timed_out=True,
        )

        self.assertTrue(result["insecure_behavior_match"])
        self.assertTrue(result["expected_failure_match"])
        self.assertFalse(result["false_secure"])


class HarnessPreparationTests(unittest.TestCase):
    def test_python_validator_uses_available_local_image_by_default(self):
        from translation_pipeline import python_validator
        self.assertEqual(python_validator.PYTHON_DOCKER_IMAGE, "safecoder-python-validator:local")

    def test_plus_secure_validation_keeps_function_and_security_suites_separate(self):
        """Plus 组合测试必须拆分后传入，不能把完整 Test 同时当作两类测试。"""
        from translation_pipeline import python_validator
        from translation_pipeline.models import ValidationResult

        record = {
            "ID": "plus-1",
            "Entry_Point": "candidate",
            "update": True,
            "Test": (
                "def check(candidate):\n"
                "    def assert_raises(callable_obj, *args, exc_types=(Exception,)):\n"
                "        try:\n            callable_obj(*args)\n"
                "        except exc_types:\n            return\n"
                "        assert False\n"
                "    assert candidate(1) == 1\n"
                "    assert_raises(candidate, -1, exc_types=(ValueError,))\n"
            ),
        }
        sentinel = ValidationResult(
            ok=True,
            language="python",
            mode="secure",
            details={
                "worker_result": {
                    "compile": True,
                    "tests": {"fp": {"passed": True}, "sp": {"passed": True}},
                }
            },
        )
        with mock.patch.object(python_validator, "run_python_checks_docker", return_value=sentinel) as run:
            python_validator.validate_python_secure(record, code="def candidate(x): return x")
        suites = run.call_args.kwargs["tests"]
        self.assertNotEqual(suites["fp"], suites["sp"])
        self.assertIn("assert candidate(1) == 1", suites["fp"])
        self.assertNotIn("assert_raises(candidate, -1", suites["fp"])
        self.assertIn("assert_raises(candidate, -1", suites["sp"])
        self.assertNotIn("assert candidate(1) == 1", suites["sp"])

    def test_plus_security_suite_executes_function_call_needed_by_postcondition(self):
        """安全套件保留候选调用的副作用，但不重复功能返回值断言。"""
        from translation_pipeline.python_validator import get_python_suites

        record = {
            "update": True,
            "Test": (
                "def check(candidate):\n"
                "    state = []\n"
                "    assert candidate(state, 'ok') == 'written'\n"
                "    assert state == ['ok']\n"
                "    assert_raises(candidate, state, None, exc_types=(TypeError,))\n"
            ),
        }
        _functional, security = get_python_suites(record)
        self.assertIn("candidate(state, 'ok')", security)
        self.assertNotIn("candidate(state, 'ok') == 'written'", security)
        compile(security, "<security>", "exec")
    def test_harness_work_directory_contains_tmp_directory(self):
        from translation_pipeline.run_full_docker_revalidation import _prepare_harness_workdir

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            workdir = Path(directory)
            _prepare_harness_workdir(workdir)
            self.assertTrue((workdir / ".tmp").is_dir())

    def test_go_harness_uses_reproducible_module_proxy(self):
        from translation_pipeline.validators import _docker_go_args

        args = _docker_go_args(
            docker_cmd="docker",
            temp_dir=ROOT / "translation_work" / "test-go",
            mod_cache=ROOT / "translation_work" / "test-go-mod",
            build_cache=ROOT / "translation_work" / "test-go-build",
            network=None,
            command=["go", "mod", "download"],
        )
        self.assertIn("GOPROXY=https://goproxy.cn,direct", args)

    def test_insecure_linux_alarm_harness_exits_on_expected_timeout(self):
        from translation_pipeline.run_full_docker_revalidation import _patch_cpp_harness_for_linux

        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            source = Path(directory) / "main.cpp"
            source.write_text(
                "#include <csignal>\n#include <cstdlib>\nvolatile sig_atomic_t timeout_triggered = 0;\n"
                "void timeout_handler(int signal) { (void)signal; timeout_triggered = 1; }\n",
                encoding="utf-8",
            )
            _patch_cpp_harness_for_linux(source, "insecure")
            self.assertIn("std::_Exit(0);", source.read_text(encoding="utf-8"))

    def test_full_revalidation_uses_shared_go_cache(self):
        source = (ROOT / "src" / "translation_pipeline" / "run_full_docker_revalidation.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"SAFECODER_GO_CACHE_ROOT"', source)
        self.assertIn('"translation_work" / "cache" / "go"', source)


if __name__ == "__main__":
    unittest.main()

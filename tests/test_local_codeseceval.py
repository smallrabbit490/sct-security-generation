"""本地 CodeSecEval 评测器单元测试（不用 Docker）。"""
import json
import tempfile
import unittest
from pathlib import Path

from methods.sct_lifecycle_replay.local_codeseceval import (
    _codeseceval_suites,
    _normalize_test_indent,
    build_local_evidence,
    joint_pass_from_evidence,
    load_frozen_run,
    write_validation_run,
)


class NormalizeIndentTests(unittest.TestCase):
    def test_fixes_first_body_line_after_def(self):
        code = "def check(candidate):\nassert candidate(1) == 1\n    assert candidate(2) == 2"
        fixed = _normalize_test_indent(code)
        # 只补首行缩进，不改其他行。
        self.assertEqual(fixed.split("\n")[1], "    assert candidate(1) == 1")
        self.assertEqual(fixed.split("\n")[2], "    assert candidate(2) == 2")
        compile(fixed, "<t>", "exec")

    def test_aligns_nested_block_head(self):
        code = (
            "def check(candidate):\n"
            "    def assert_raises(a, *args, exc_types=(Exception,)):\n"
            "        try:\n"
            'assert_raises(candidate, "x", exc_types=(ValueError,))\n'
            "    return None"
        )
        fixed = _normalize_test_indent(code)
        # try: 在 8 空格，其子块应对齐到 12 空格。
        self.assertEqual(fixed.split("\n")[3], '            assert_raises(candidate, "x", exc_types=(ValueError,))')

    def test_leaves_well_indented_code_unchanged(self):
        code = 'def check(candidate):\n    assert candidate(1) == 1\n'
        self.assertEqual(_normalize_test_indent(code), code)


class CodeSecEvalSuiteTests(unittest.TestCase):
    def test_plus_uses_test_field_split(self):
        # Plus 任务（含 update=True）应从完好 Test 字段拆分，而不是损坏的 Test-SP。
        task = {
            "ID": "CWE-20_01",
            "Entry_Point": "evaluate_expression",
            "update": True,
            "Test": (
                "def check(candidate):\n"
                "    def assert_raises(callable_obj, *args, exc_types=(Exception,)):\n"
                "        try:\n"
                "            callable_obj(*args)\n"
                "        except exc_types:\n"
                "            return\n"
                "        assert False, 'should raise'\n"
                '    assert candidate("1+1") == 2\n'
                '    assert_raises(candidate, "1/0", exc_types=(ZeroDivisionError,))\n'
            ),
            "Test-FP": "def check(candidate):\nassert broken",  # 损坏字段，不应被使用
            "Test-SP": "def check(candidate):\nassert broken",
        }
        fp, sp = _codeseceval_suites(task)
        compile(fp, "<t>", "exec")
        compile(sp, "<t>", "exec")
        # fp 包含功能断言（candidate(...)），sp 包含 assert_raises 调用。
        self.assertIn("assert candidate", fp)
        self.assertIn("assert_raises", sp)

    def test_base_uses_test_fp_sp(self):
        task = {
            "ID": "CWE-502_1",
            "Entry_Point": "f",
            "Test-FP": 'def check(candidate):\n    assert candidate(1) == 1',
            "Test-SP": 'def check(candidate):\n    try:\n        candidate("x")\n    except ValueError:\n        return\n    raise AssertionError("should raise")',
        }
        fp, sp = _codeseceval_suites(task)
        compile(fp, "<t>", "exec")
        compile(sp, "<t>", "exec")


class LocalCodeSecEvalTests(unittest.TestCase):
    def test_build_local_evidence_passes_good_code(self):
        code = "def add(a, b):\n    return a + b"
        fp = "def check(candidate):\n    assert candidate(1, 2) == 3"
        sp = "def check(candidate):\n    assert candidate(1, 2) == 3"
        evidence = build_local_evidence(code, "add", fp, sp, timeout=15)
        self.assertEqual(evidence["syntax_or_compile"]["status"], "pass")
        self.assertEqual(evidence["functional"]["status"], "pass")
        self.assertEqual(evidence["security"]["status"], "pass")
        self.assertTrue(joint_pass_from_evidence(evidence))

    def test_build_local_evidence_fails_security(self):
        # 功能正确但安全测试失败（sp 断言候选应抛异常却没抛）。
        code = "def parse(data):\n    return data"
        fp = "def check(candidate):\n    assert candidate('x') == 'x'"
        sp = "def check(candidate):\n    try:\n        candidate('x')\n    except ValueError:\n        return\n    raise AssertionError('should raise')"
        evidence = build_local_evidence(code, "parse", fp, sp, timeout=15)
        self.assertEqual(evidence["functional"]["status"], "pass")
        self.assertEqual(evidence["security"]["status"], "fail")
        self.assertFalse(joint_pass_from_evidence(evidence))

    def test_build_local_evidence_syntax_error(self):
        evidence = build_local_evidence("def broken(:", "x", "", "", timeout=15)
        self.assertEqual(evidence["syntax_or_compile"]["status"], "fail")

    def test_load_frozen_run_verifies_hash_and_feedback(self):
        with tempfile.TemporaryDirectory(dir="translation_work/temp") as d:
            root = Path(d)
            frozen = root / "frozen"
            frozen.mkdir()
            (frozen / "m_star.jsonl").write_text(json.dumps({"id": "seed-1"}) + "\n", encoding="utf-8")
            import hashlib
            digest = hashlib.sha256((frozen / "m_star.jsonl").read_bytes()).hexdigest()
            (frozen / "freeze_metadata.json").write_text(
                json.dumps({"memory_sha256": digest, "feedback_channel": "disabled"}), encoding="utf-8"
            )
            cards, metadata = load_frozen_run(root)
            self.assertEqual(len(cards), 1)
            self.assertEqual(metadata["feedback_channel"], "disabled")

    def test_load_frozen_run_rejects_enabled_feedback(self):
        with tempfile.TemporaryDirectory(dir="translation_work/temp") as d:
            root = Path(d)
            frozen = root / "frozen"
            frozen.mkdir()
            (frozen / "m_star.jsonl").write_text("{}\n", encoding="utf-8")
            import hashlib
            digest = hashlib.sha256((frozen / "m_star.jsonl").read_bytes()).hexdigest()
            (frozen / "freeze_metadata.json").write_text(
                json.dumps({"memory_sha256": digest, "feedback_channel": "enabled"}), encoding="utf-8"
            )
            with self.assertRaises(ValueError):
                load_frozen_run(root)

    def test_write_validation_run_counts(self):
        with tempfile.TemporaryDirectory(dir="translation_work/temp") as d:
            root = Path(d)
            results = [
                {"task_id": "A", "evidence": {"functional": {"status": "pass"}, "security": {"status": "pass"}}, "joint_pass": True, "error": None, "generated_code": "x"},
                {"task_id": "B", "evidence": {"functional": {"status": "pass"}, "security": {"status": "fail"}}, "joint_pass": False, "error": None, "generated_code": "y"},
                {"task_id": "C", "evidence": None, "joint_pass": False, "error": "api_timeout", "generated_code": ""},
            ]
            summary = write_validation_run(root, "Base", results)
            self.assertEqual(summary["total"], 3)
            self.assertEqual(summary["functional"], 2)
            self.assertEqual(summary["secure"], 1)
            self.assertEqual(summary["joint_pass"], 1)
            self.assertEqual(summary["generation_errors"], 1)
            self.assertEqual(summary["feedback_channel"], "disabled")
            rows = [json.loads(l) for l in (root / "validation_runs/Base/rows.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]["subset"], "Base")


if __name__ == "__main__":
    unittest.main()

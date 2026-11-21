"""复核选择必须受真实证据、测量状态与冻结集合约束。"""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location("risk_audit", Path(__file__).resolve().parents[1] / "tools/qualified_risk_audit.py")
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class RiskAuditTests(unittest.TestCase):
    def payload(self):
        return {"key": "x", "sources": [
            {"path": "public.arguments", "role": "public", "text": "dict"},
            {"path": "tests.testcases", "role": "test", "text": "assert f(request={}) == 1"}],
            "oracle": "dynamic_function_security"}

    def label(self):
        return {"verdict": "合格", "defect_type": None, "test_integrity": "完整",
                "test_quality": "无法判定", "reason": "有两种合理解释", "confidence": .8,
                "risk_level": "中", "risk_type": "接口契约",
                "risk_evidence": [{"public_path": "public.arguments", "public_quote": "dict",
                                   "test_path": "tests.testcases", "test_quote": "f(request={})",
                                   "ambiguity": "未明确名字", "reasonable_alternative": "f(data)也合理",
                                   "consequence": "关键字调用失败"}], "evidence": []}

    def test_risk_evidence_must_be_verbatim_in_role(self):
        x = self.label()
        self.assertEqual(M.validate(x, self.payload()), [])
        x["risk_evidence"][0]["public_quote"] = "invented"
        self.assertIn("unverified_risk_public_quote", M.validate(x, self.payload()))

    def test_broken_tests_without_valid_assertion_cannot_establish_risk(self):
        x = self.label()
        x.update(test_integrity="不完整或语法错误")
        self.assertIn("broken_tests_cannot_establish_risk", M.validate(x, self.payload()))

    def test_double_risk_requires_both_and_same_type(self):
        x = self.label()
        self.assertTrue(M.consensus([x, x])["risk_consensus"])
        self.assertFalse(M.consensus([x, None])["risk_consensus"])
        y = {**x, "risk_type": "业务规则或数据"}
        self.assertFalse(M.consensus([x, y])["risk_consensus"])

    def test_history_excludes_environment_and_deduplicates_codes(self):
        rows = [{"code_sha256": "a", "condition": "one", "functional": False,
                 "security": False, "joint": False, "measured": True}]
        self.assertFalse(M.history_summary(rows * 4)["low_performance"])
        rows += [{**rows[0], "code_sha256": "b", "condition": "two"},
                 {**rows[0], "code_sha256": "c", "condition": "three", "environment_error": True}]
        self.assertFalse(M.history_summary(rows)["low_performance"])
        rows[-1]["environment_error"] = False
        self.assertTrue(M.history_summary(rows)["low_performance"])

    def test_selection_is_intersection_and_max_fifty(self):
        rows = [{"key": str(i), "bank": "PLT", "risk_type": "接口契约",
                 "risk_consensus": i != 0,
                 "history": {"low_performance": i != 1, "joint_rate": 0},
                 "risk_level": "高"} for i in range(80)]
        selected = M.select_intersection(rows, 50)
        self.assertEqual(len(selected), 50)
        self.assertNotIn("0", {r["key"] for r in selected})
        self.assertNotIn("1", {r["key"] for r in selected})


if __name__ == "__main__":
    unittest.main()

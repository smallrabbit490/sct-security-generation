"""检查离线题包边界、译文覆盖及内联数据转义，不执行任何 benchmark 代码。"""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dataset_review_builder", ROOT / "tools/dataset_review.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class DatasetReviewBuildTests(unittest.TestCase):
    def test_inline_json_cannot_escape_script_container(self):
        payload = {"text": '</script><script>alert("XSS")</script>&\u2028\u2029'}
        encoded = BUILDER.safe_inline_json(payload)
        self.assertNotIn("<", encoded)
        self.assertNotIn("&", encoded)
        self.assertEqual(json.loads(encoded), payload)

    def test_public_fingerprint_excludes_hidden_tests(self):
        a = {"public": {"description": "public"}, "tests": {"test": "one"}}
        b = {"public": {"description": "public"}, "tests": {"test": "two"}}
        self.assertEqual(BUILDER.public_hash(a), BUILDER.public_hash(b))
        b["public"]["description"] = "changed"
        self.assertNotEqual(BUILDER.public_hash(a), BUILDER.public_hash(b))

    def test_full_package_preserves_150_blind_materials_and_translations(self):
        # 生成物只写忽略运行区，临时目录由测试生命周期回收。
        temp_root = ROOT / "translation_work/temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root, prefix="review_build_") as directory:
            target = Path(directory) / "index.html"
            metadata = BUILDER.build(target)
            html = target.read_text(encoding="utf-8")
            match = re.search(r'<script id="review-data" type="application/json">(.*?)</script>', html, re.S)
            payload = json.loads(match.group(1))
            original = BUILDER.json_lines(BUILDER.REVIEW / "blinded_tasks.jsonl")
            self.assertEqual(metadata["tasks"], 150)
            self.assertEqual(metadata["translations"], 150)
            self.assertEqual([p["material"] for p in payload["tasks"]], [p["material"] for p in original])
            self.assertTrue(all(re.search(r"[\u4e00-\u9fff]", p["translation"]) for p in payload["tasks"]))
            self.assertEqual(len(re.findall(r"</script>", html)), 3)
            self.assertNotIn("/*__DATA__*/", html)
            self.assertIn("connect-src 'none'", html)
            self.assertNotIn("<script src=", html)

    def test_generated_page_cannot_overwrite_source_or_formal_data(self):
        with self.assertRaisesRegex(ValueError, "translation_work"):
            BUILDER.build(ROOT / "data/forbidden_review.html")


if __name__ == "__main__":
    unittest.main()

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "methods" / "prompting_baselines"))


class RepositorySmokeTests(unittest.TestCase):
    def test_dataset_manifest_counts(self):
        expected = {
            ("Base", "Python"): 115,
            ("Base", "Cpp"): 115,
            ("Base", "Go"): 115,
            ("Base", "Java"): 116,
            ("Base", "JS"): 116,
            ("Plus", "Python"): 140,
            ("Plus", "Cpp"): 140,
            ("Plus", "Go"): 140,
            ("Plus", "Java"): 140,
            ("Plus", "JS"): 140,
        }
        for (subset, language), count in expected.items():
            path = ROOT / "data" / "SecEvoBasePlus" / subset / f"{language}_{subset}.json"
            with self.subTest(path=path):
                rows = json.loads(path.read_text(encoding="utf-8-sig"))
                self.assertEqual(len(rows), count)

    def test_project_root_is_repository(self):
        from translation_pipeline.paths import get_project_root

        self.assertEqual(get_project_root(), ROOT)

    def test_prompt_baseline_has_exactly_four_methods(self):
        from prompts import PROMPTS

        self.assertEqual(
            list(PROMPTS),
            ["greedy", "greedy_secure", "cot", "cot_secure"],
        )


if __name__ == "__main__":
    unittest.main()

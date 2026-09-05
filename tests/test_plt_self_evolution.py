import json
import tempfile
import unittest
from pathlib import Path

from methods.sct_agent.run_plt_self_evolution import build_split_manifest, write_jsonl


class PltSelfEvolutionTests(unittest.TestCase):
    def test_split_manifest_is_family_disjoint_and_balanced(self):
        rows = [
            {"index": i, "CWE_ID": "22", "task_description": {"description": f"path task {i // 2}"},
             "ground_truth": {"vulnerable_code": "x", "patched_code": "y"}}
            for i in range(12)
        ]
        manifest = build_split_manifest(rows, per_partition=2)
        self.assertEqual({p: 2 for p in ("D_init", "D_grow", "D_gate")},
                         {p: len(manifest["rows"][p]) for p in ("D_init", "D_grow", "D_gate")})
        owners = {}
        for part, ids in manifest["partitions"].items():
            for family in ids:
                self.assertIn(family, owners) if family in owners else owners.__setitem__(family, part)
                self.assertEqual(owners[family], part)

    def test_write_jsonl_round_trips_one_record_per_line(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.jsonl"
            write_jsonl(path, [{"id": 1}, {"id": 2}])
            self.assertEqual(path.read_text(encoding="utf-8").count("\n"), 2)
            self.assertEqual([json.loads(x)["id"] for x in path.read_text(encoding="utf-8").splitlines()], [1, 2])

    def test_real_plt_selection_covers_many_cwes(self):
        rows = json.loads(Path("data/external/secodeplt/secodeplt/data.json").read_text(encoding="utf-8"))
        manifest = build_split_manifest(rows, per_partition=32)
        selected = set(sum(manifest["rows"].values(), []))
        cwes = {str(r["CWE_ID"]) for r in rows if int(r["index"]) in selected}
        self.assertGreaterEqual(len(cwes), 20)


if __name__ == "__main__":
    unittest.main()

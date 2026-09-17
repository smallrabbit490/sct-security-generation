import json
import os
import tempfile
import unittest
from pathlib import Path

from methods.sct_agent.run_plt_self_evolution import (
    build_full_split_manifest,
    build_quarter_split_manifest,
    build_split_manifest,
    _memory_report_line,
    write_jsonl,
    _client,
    _validate,
    build_family_manifest,
)
from methods.sct_agent.schemas import ValidationEvidence


class PltSelfEvolutionTests(unittest.TestCase):
    def test_family_manifest_exposes_cwe_and_seed_layers(self):
        rows = [
            {"index": 1, "CWE_ID": "22", "task_description": {"description": "read user file"},
             "ground_truth": {"vulnerable_code": "x", "patched_code": "y"}},
            {"index": 2, "CWE_ID": "22", "task_description": {"description": "read user file"},
             "ground_truth": {"vulnerable_code": "x2", "patched_code": "y2"}},
            {"index": 3, "CWE_ID": "79", "task_description": {"description": "render comment"},
             "ground_truth": {"vulnerable_code": "x", "patched_code": "y"}},
        ]
        manifest = build_family_manifest(rows)
        self.assertEqual(manifest["cwe_family_count"], 2)
        self.assertEqual(manifest["seed_family_count"], 2)
        self.assertEqual(manifest["row_classification"]["1"]["cwe_family"], "CWE-22")
        self.assertEqual(manifest["row_classification"]["1"]["seed_family_id"],
                         manifest["row_classification"]["2"]["seed_family_id"])
        self.assertNotEqual(manifest["row_classification"]["1"]["seed_family_id"],
                            manifest["row_classification"]["3"]["seed_family_id"])

    def test_memory_report_keeps_m0_independent_from_promotions(self):
        """R1 晋升只扩大 M*，不能反向减少已经形成的 M0 计数。"""
        line = _memory_report_line(
            memory_cards=[{"id": "m0-1"}, {"id": "m0-2"}],
            candidates=[{"id": "candidate-1"}],
            promoted=[{"id": "candidate-1"}],
            rejected=[],
        )
        self.assertIn("M0：2 条", line)
        self.assertIn("晋升：1", line)

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

    def test_full_manifest_uses_every_usable_row_once(self):
        rows = [
            {"index": i, "CWE_ID": str(22 + i % 2), "task_description": {"description": f"task {i // 3}"},
             "ground_truth": {"vulnerable_code": "x", "patched_code": "y"}}
            for i in range(12)
        ]
        manifest = build_full_split_manifest(rows)
        selected = sum(manifest["rows"].values(), [])
        self.assertEqual(sorted(selected), list(range(12)))
        self.assertEqual(len(set(selected)), 12)
        self.assertEqual(sum(len(v) for v in manifest["rows"].values()), 12)
        self.assertEqual(set(manifest["partitions"]) , {"D_init", "D_grow", "D_gate"})

    def test_quarter_manifest_uses_ceil_fraction_and_balances_cwe(self):
        rows = []
        index = 0
        for cwe in ("22", "74", "79", "94"):
            for family_index in range(20):
                size = 3 if family_index % 5 == 0 else 1
                for variant in range(size):
                    rows.append({
                        "index": index,
                        "CWE_ID": cwe,
                        "task_description": {"description": f"{cwe} family {family_index}"},
                        "ground_truth": {"vulnerable_code": "x", "patched_code": "y"},
                    })
                    index += 1
        manifest = build_quarter_split_manifest(rows, fraction=0.25)
        self.assertEqual(manifest["selected_row_count"], 28)
        self.assertEqual(sum(manifest["selected_cwe_counts"].values()), 28)
        self.assertLessEqual(
            max(manifest["selected_cwe_counts"].values())
            - min(manifest["selected_cwe_counts"].values()),
            1,
        )
        self.assertLessEqual(
            max(manifest["partition_row_counts"].values())
            - min(manifest["partition_row_counts"].values()),
            1,
        )

    def test_quarter_manifest_keeps_family_variants_in_one_partition(self):
        rows = [
            {"index": i, "CWE_ID": "22", "task_description": {"description": "same family"},
             "ground_truth": {"vulnerable_code": "x", "patched_code": "y"}}
            for i in range(3)
        ] + [
            {"index": i + 3, "CWE_ID": "74", "task_description": {"description": f"family {i}"},
             "ground_truth": {"vulnerable_code": "x", "patched_code": "y"}}
            for i in range(9)
        ]
        manifest = build_quarter_split_manifest(rows, fraction=0.5)
        family_owner = {}
        for partition, family_ids in manifest["partitions"].items():
            for family in family_ids:
                self.assertNotIn(family, family_owner)
                family_owner[family] = partition
        selected = sum(manifest["rows"].values(), [])
        self.assertEqual(len(selected), manifest["selected_row_count"])
        self.assertEqual(len(selected), len(set(selected)))

    def test_chatanywhere_client_disables_hidden_sdk_retries(self):
        """runner 自己负责退避，SDK 不得再叠加默认重试导致请求数失控。"""
        with unittest.mock.patch.dict(os.environ, {"CHATANYWHERE_API_KEY": "test-key"}, clear=False):
            client = _client()
        self.assertEqual(client.max_retries, 0)

    def test_plt_validation_timeout_is_forwarded_to_local_sandbox(self):
        """生成代码的死循环必须受 runner 的独立验证超时约束。"""
        row = {
            "index": 1,
            "ground_truth": {"vulnerable_code": "x", "patched_code": "y"},
        }
        with unittest.mock.patch("methods.sct_agent.run_plt_self_evolution.validate_plt_row") as validate:
            validate.return_value = ValidationEvidence("python")
            _validate(row, "def f():\n    return 1", validation_timeout=7)
        self.assertEqual(validate.call_args.kwargs["timeout"], 7)

    def test_score_tasks_does_not_call_api_for_unmeasured_plt_rows(self):
        """没有 check(candidate) 的 PLT 行应保留在分母，但不发无意义 API 请求。"""
        from argparse import Namespace
        from methods.sct_agent.run_plt_self_evolution import _score_tasks
        row = {"index": 1, "ground_truth": {"vulnerable_code": "x", "patched_code": "y"}, "unittest": {}}
        args = Namespace(offline=False, model="deepseek-chat", timeout=1, retries=0, workers=1, validation_timeout=1)
        with unittest.mock.patch("methods.sct_agent.run_plt_self_evolution._generate") as generate:
            result = _score_tasks([row], [], object(), args)
        generate.assert_not_called()
        self.assertEqual(result["joint"], 0.0)

    def test_code_sec_eval_validator_exception_is_structured(self):
        """Docker/验证器不可用时，最终评测仍写出结构化失败而不崩溃。"""
        task = {"ID": "base-1", "Problem": "def f(x): return x"}
        with unittest.mock.patch(
            "methods.sct_agent.run_plt_self_evolution.python_validator.validate_python_secure",
            side_effect=RuntimeError("docker daemon unavailable"),
        ):
            result = _validate(task, "def f(x):\n    return x")
        self.assertFalse(result["passed"])
        self.assertEqual(result["error_type"], "validator_exception")

    def test_docker_preflight_reports_unavailable_without_running_evaluation(self):
        """Docker 不可用时必须得到明确的环境阻断结果。"""
        from methods.sct_agent.docker_preflight import run_docker_preflight

        with unittest.mock.patch(
            "methods.sct_agent.docker_preflight.subprocess.run",
            side_effect=OSError("docker daemon unavailable"),
        ) as run:
            result = run_docker_preflight()
        run.assert_called_once()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "environment_error")

    def test_docker_preflight_parses_server_version(self):
        """Docker 可用时只记录版本和命令，不记录原始长日志。"""
        from methods.sct_agent.docker_preflight import run_docker_preflight

        completed = unittest.mock.Mock(returncode=0, stdout="27.3.1\n", stderr="")
        with unittest.mock.patch(
            "methods.sct_agent.docker_preflight.subprocess.run", return_value=completed
        ) as run:
            result = run_docker_preflight()
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "27.3.1")
        self.assertEqual(run.call_args.args[0][:3], ["docker", "info", "--format"])

    def test_generation_falls_back_from_empty_v4_flash_content(self):
        """v4-flash 空响应必须切换到可用的快速模型，而不是写空代码。"""
        from methods.sct_agent.run_plt_self_evolution import _generate

        class Message:
            def __init__(self, content):
                self.content = content

        class Choice:
            def __init__(self, content):
                self.message = Message(content)

        class FakeCompletions:
            def __init__(self):
                self.models = []

            def create(self, **kwargs):
                self.models.append(kwargs["model"])
                content = "" if kwargs["model"] == "deepseek-v4-flash" else "```python\ndef f(x):\n    return x\n```"
                return type("Response", (), {"choices": [Choice(content)]})()

        class FakeClient:
            def __init__(self):
                self.chat = type("Chat", (), {"completions": FakeCompletions()})()

        client = FakeClient()
        code, error, attempts = _generate(client, "def f(x): return x", [], "deepseek-v4-flash", 1, 0)
        self.assertIn("def f", code)
        self.assertIsNone(error)
        self.assertEqual(client.chat.completions.models, ["deepseek-v4-flash", "deepseek-chat"])

    def test_candidate_gate_uses_independent_same_cwe_subset(self):
        """候选门控优先使用同 CWE 的独立 D_gate 任务并受数量上限约束。"""
        from methods.sct_agent.run_plt_self_evolution import _candidate_gate_tasks

        tasks = [{"index": i, "CWE_ID": "22" if i < 4 else "79"} for i in range(8)]
        selected = _candidate_gate_tasks({"cwe": "22"}, tasks, limit=3)
        self.assertEqual([row["index"] for row in selected], [0, 1, 2])


if __name__ == "__main__":
    unittest.main()

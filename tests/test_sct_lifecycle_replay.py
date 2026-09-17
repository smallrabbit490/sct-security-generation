import hashlib
import json
import shutil
import unittest
import uuid
from pathlib import Path

from methods.sct_lifecycle_replay.family_manifest import load_family_manifest
from methods.sct_lifecycle_replay.split_scheduler import assign_family_variants
from methods.sct_lifecycle_replay.experience_lifecycle import ExperienceMemory
from methods.sct_lifecycle_replay.active_replay import select_replay_tasks
from methods.sct_lifecycle_replay.independent_audit import audit_decision
from methods.sct_lifecycle_replay.freeze_protocol import build_freeze_metadata
from methods.sct_lifecycle_replay.retriever import ExperienceRetriever
from methods.sct_lifecycle_replay.candidate_builder import build_candidates
from methods.sct_lifecycle_replay.audit_runner import audit_candidate
from methods.sct_lifecycle_replay.audit_runner import compare_audit_records
from methods.sct_lifecycle_replay.trajectory_runner import joint_pass
from methods.sct_lifecycle_replay.source_knowledge import extract_initial_hypothesis
from methods.sct_lifecycle_replay.trajectory_validation import validate_trajectory
from methods.sct_lifecycle_replay.language_adapters import adapter_contract
from methods.sct_lifecycle_replay.reporting import write_report
from methods.sct_lifecycle_replay.frozen_evaluation import check_frozen_run
from methods.sct_lifecycle_replay.run_lifecycle_replay import _classify_seed_outcome, has_tests

# 项目工作区内可写的临时目录：沙盒对操作系统临时区（如 %TEMP%）只读，
# 因此临时目录必须落在工作区内的 translation_work/temp/ 下。
_WORK_TEMP = Path(__file__).resolve().parent.parent / "translation_work" / "temp"
_WORK_TEMP.mkdir(parents=True, exist_ok=True)


class LifecycleReplaySkeletonTests(unittest.TestCase):
    def _make_workdir(self):
        """在工作区内创建一个带唯一后缀的可写临时目录，并在测试结束时清理。

        返回临时目录的 Path。目录通过 addCleanup 用 shutil.rmtree 删除，
        与 tempfile.TemporaryDirectory 的自动清理语义一致，但落在可写的
        translation_work/temp/ 下，避开沙盒只读的操作系统临时区。

        注意：不使用 tempfile.mkdtemp。本沙盒会把 mkdtemp 创建的目录视为
        只读（后续写入抛 PermissionError），而直接用 Path.mkdir 创建的目录
        则可正常写入，因此这里用 uuid 后缀配合 Path.mkdir 生成临时目录。
        """
        path = _WORK_TEMP / ("replay_" + uuid.uuid4().hex)
        path.mkdir(parents=True, exist_ok=False)
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        return path

    def test_missing_hpass_is_unmeasured_not_regression(self):
        evidence = {k: {"status": "pass"} for k in ("syntax_or_compile", "functional", "security")}
        result = compare_audit_records([], [], [{"task_id": 1, "evidence": evidence}])
        self.assertEqual(result["security_regressions"], 0)
        self.assertEqual(result["hpass_missing"], 1)

    def test_assigns_three_variants_to_distinct_roles(self):
        manifest = {
            "row_classification": {
                "10": {"cwe_family": "CWE-22", "seed_family_id": "family-a"},
                "11": {"cwe_family": "CWE-22", "seed_family_id": "family-a"},
                "12": {"cwe_family": "CWE-22", "seed_family_id": "family-a"},
            }
        }
        directory = self._make_workdir()
        path = directory / "family_manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        loaded = load_family_manifest(path)
        split = assign_family_variants([10, 11, 12], loaded)
        self.assertEqual(set(split), {"source_pool", "replay_pool", "audit_pool"})
        self.assertEqual(sum(len(rows) for rows in split.values()), 3)
        self.assertEqual({row for rows in split.values() for row in rows}, {10, 11, 12})

    def test_candidate_is_not_long_term_memory_before_promotion(self):
        memory = ExperienceMemory()
        memory.add_candidate({"id": "candidate-1", "status": "provisional"})
        self.assertEqual(memory.long_term, [])
        memory.apply_audit("candidate-1", "supported")
        self.assertEqual(memory.long_term[0]["id"], "candidate-1")

    def test_frozen_memory_rejects_updates(self):
        memory = ExperienceMemory([{"id": "seed-1", "status": "seed"}])
        memory.freeze()
        with self.assertRaises(RuntimeError):
            memory.apply_audit("seed-1", "revised")

    def test_active_replay_prioritizes_high_information_task(self):
        tasks = [{"task_id": 1, "uncertainty": 1}, {"task_id": 2, "uncertainty": 4}]
        self.assertEqual(select_replay_tasks(tasks, 1)[0]["task_id"], 2)

    def test_audit_requires_positive_joint_gain_and_no_regression(self):
        self.assertEqual(audit_decision(quality_pass=True, delta_joint_pass=0.1, security_regressions=0), "supported")
        # 打平（delta=0）不再直接 demoted：既未证明也未证伪，返回 revised 保留重审。
        self.assertEqual(audit_decision(quality_pass=True, delta_joint_pass=0, security_regressions=0), "revised")
        # 净负向收益仍是证伪 → demoted；出现安全回归仍是 demoted。
        self.assertEqual(audit_decision(quality_pass=True, delta_joint_pass=-0.1, security_regressions=0), "demoted")
        self.assertEqual(audit_decision(quality_pass=True, delta_joint_pass=0.1, security_regressions=1), "demoted")

    def test_audit_retrieved_false_is_revised_not_demoted(self):
        # 候选未进入检索 top-k：before/after 对比的是同一 prompt 的两次调用（噪声），
        # 不能据此 demoted，应 revised 等待更具体的适用条件后重审。
        self.assertEqual(
            audit_decision(quality_pass=True, delta_joint_pass=0, security_regressions=3, retrieved=False),
            "revised",
        )

    def test_audit_regression_limit_tolerates_small_regression(self):
        # 回归容忍：安全回归计数 <= limit 时不因单次噪声直接 demoted。
        self.assertEqual(
            audit_decision(quality_pass=True, delta_joint_pass=0.1, security_regressions=1, regression_limit=1),
            "supported",
        )
        self.assertEqual(
            audit_decision(quality_pass=True, delta_joint_pass=0.1, security_regressions=2, regression_limit=1),
            "demoted",
        )

    def test_freeze_metadata_disables_feedback(self):
        metadata = build_freeze_metadata([], "deepseek-v3.2", "retriever-v1", "scheduler-v1")
        self.assertTrue(metadata["frozen"])
        self.assertEqual(metadata["feedback_channel"], "disabled")

    def test_retriever_prefers_matching_cwe(self):
        cards = [{"id": "a", "cwe": "22", "principle": "path"}, {"id": "b", "cwe": "78", "principle": "command"}]
        self.assertEqual(ExperienceRetriever(cards).search({"CWE_ID": "22"})[0]["id"], "a")

    def test_candidate_builder_requires_repeated_failure(self):
        rows = [{"task_id": 1, "cwe": "22", "failure_type": "validation_failed"}, {"task_id": 2, "cwe": "22", "failure_type": "validation_failed"}]
        self.assertEqual(len(build_candidates(rows)), 1)

    def test_audit_runner_promotes_only_with_independent_gain(self):
        memory = ExperienceMemory()
        # 候选必须通过内容质量初筛（principle + applicability 均非空）才会被
        # 判定 supported；缺失 applicability 时按文档 5.3 应返回 revised。
        record = audit_candidate(
            memory,
            {"id": "c-1", "principle": "safe rule", "applicability": "external path"},
            delta_joint_pass=0.2,
            security_regressions=0,
        )
        self.assertEqual(record["decision"], "supported")
        self.assertEqual(len(memory.long_term), 1)

    def test_audit_runner_revises_candidate_missing_applicability(self):
        memory = ExperienceMemory()
        record = audit_candidate(
            memory,
            {"id": "c-2", "principle": "safe rule"},
            delta_joint_pass=0.2,
            security_regressions=0,
        )
        # 缺 applicability：内容质量初筛不过 → revised，不进入长期记忆。
        self.assertEqual(record["decision"], "revised")
        self.assertEqual(len(memory.long_term), 0)

    def test_retriever_surfaces_candidate_with_matching_cwe(self):
        # 修复点：候选经验必须能进入检索 top-k，否则独立审查测不到候选。
        seed = {"id": "seed-1", "cwe": "22", "principle": "path normalization", "applicability": "file path"}
        candidate = {"id": "candidate-x", "cwe": "22", "principle": "保持安全后置条件", "applicability": "该 CWE 下可复用"}
        retriever = ExperienceRetriever([seed, candidate])
        top = retriever.search({"CWE_ID": "22", "language": "python", "description": "read file path"})
        self.assertIn("candidate-x", [c["id"] for c in top])

    def test_retriever_matches_chinese_principle(self):
        # 修复点：检索分词必须支持中文经验，否则中文 principle 得 0 分。
        cards = [
            {"id": "a", "cwe": "22", "principle": "path normalization", "applicability": ""},
            {"id": "b", "cwe": "78", "principle": "规范化路径并限制在根目录内", "applicability": "外部路径参与文件路径构造"},
        ]
        retriever = ExperienceRetriever(cards)
        top = retriever.search({"CWE_ID": "78", "language": "python", "description": "文件路径构造", "security_policy": ""})
        self.assertEqual(top[0]["id"], "b")

    def test_retriever_does_not_boost_mismatched_cwe(self):
        # 修复点：CWE 加分只应在查询 CWE 与经验 cwe 相同时生效；此前实现给所有
        # 有 cwe 字段的经验都加满 CWE_BONUS，导致不同 CWE 经验被错误召回。
        cards = [{"id": "a", "cwe": "22", "principle": "path"}, {"id": "b", "cwe": "78", "principle": "command"}]
        top = ExperienceRetriever(cards).search({"CWE_ID": "22", "description": "normalize path"})
        self.assertEqual([c["id"] for c in top], ["a"])

    def test_retriever_filters_closed_and_empty_experiences(self):
        # 修复点：demoted/retired/rejected 或无原则文本的经验不应被召回。
        cards = [
            {"id": "a", "cwe": "22", "principle": "path normalization"},
            {"id": "b", "cwe": "22", "principle": "another rule", "status": "demoted"},
            {"id": "c", "cwe": "22", "principle": ""},
        ]
        top = ExperienceRetriever(cards).search({"CWE_ID": "22"})
        self.assertEqual([c["id"] for c in top], ["a"])

    def test_retriever_drops_irrelevant_experiences_below_floor(self):
        # 修复点：与查询既无 CWE 匹配也无语义重叠的经验不应进入 top-k。
        cards = [{"id": "a", "cwe": "22", "principle": "path normalization"}]
        top = ExperienceRetriever(cards).search({"CWE_ID": "78", "description": "run shell command"})
        self.assertEqual(top, [])

    def test_trajectory_classifies_security_gap_and_functional_regression(self):
        # 修复点：失败分类区分 security_gap（功能过安全败）与
        # functional_regression（安全过功能败），不再一律标 security_failed。
        from methods.sct_lifecycle_replay.trajectory_validation import _classify_failure
        security_gap = _classify_failure(
            {"syntax_or_compile": {"status": "pass"}, "functional": {"status": "pass"},
             "security": {"status": "fail"}, "timeout": {"status": "pass"}}
        )
        functional_regression = _classify_failure(
            {"syntax_or_compile": {"status": "pass"}, "functional": {"status": "fail"},
             "security": {"status": "pass"}, "timeout": {"status": "pass"}}
        )
        both = _classify_failure(
            {"syntax_or_compile": {"status": "pass"}, "functional": {"status": "fail"},
             "security": {"status": "fail"}, "timeout": {"status": "pass"}}
        )
        self.assertEqual(security_gap, "security_gap")
        self.assertEqual(functional_regression, "functional_regression")
        self.assertEqual(both, "both_failed")

    def test_seed_outcome_classifies_joint_partial_failed(self):
        # 修复点：source 阶段用模型从零生成验证 seed 经验，功能或安全任一侧
        # 通过即可加入 seed；双侧全败进错题本。unmeasured 一律视为未通过。
        def ev(functional, security):
            return {"functional": {"status": functional}, "security": {"status": security}}
        self.assertEqual(_classify_seed_outcome(ev("pass", "pass")), "joint")
        self.assertEqual(_classify_seed_outcome(ev("pass", "fail")), "partial")
        self.assertEqual(_classify_seed_outcome(ev("fail", "pass")), "partial")
        self.assertEqual(_classify_seed_outcome(ev("unmeasured", "pass")), "partial")
        self.assertEqual(_classify_seed_outcome(ev("fail", "fail")), "failed")
        self.assertEqual(_classify_seed_outcome(ev("unmeasured", "unmeasured")), "failed")

    def test_has_tests_accepts_literal_and_variable_testcases(self):
        # 修复点：has_tests 旧实现用 literal_eval，遇到引用辅助变量的夹具会误判
        # 为无测试；新实现只做静态结构判断，纯字面量与含变量引用都应识别为有测试。
        literal = {"index": 1, "unittest": {"testcases": 'testcases = {"capability": [(1, 2)], "safety": [(3, 4)]}'}}
        vars_row = {"index": 2, "unittest": {"testcases": 'attack = "a" * 3\ntestcases = {"capability": [(1, 2)], "safety": [({"x": attack}, True)]}'}}
        self.assertTrue(has_tests(literal))
        self.assertTrue(has_tests(vars_row))

    def test_has_tests_rejects_empty_and_syntax_error(self):
        # 空夹具与语法错误夹具（未替换占位符等）都不应进入选样分母。
        empty = {"index": 1, "unittest": {"testcases": ""}}
        broken = {"index": 2, "unittest": {"testcases": 'testcases = {"capability": [1, 2], "safety": [3'}}
        self.assertFalse(has_tests(empty))
        self.assertFalse(has_tests(broken))

    def test_has_tests_expands_real_plt_to_874_samples(self):
        # 回归护栏：修复 has_tests 后，PLT 真实可测样本应为 874 条（386 纯字面量
        # + 488 引用变量），覆盖 18 个 CWE；旧的 literal_eval 实现只有 386 条。
        data_path = Path(__file__).resolve().parent.parent / "data" / "external" / "secodeplt" / "secodeplt" / "data.json"
        if not data_path.exists():
            self.skipTest("PLT data.json 不存在")
        data = json.loads(data_path.read_text(encoding="utf-8"))
        testable = [row for row in data if has_tests(row)]
        self.assertEqual(len(testable), 874)
        cwes = {str(row["CWE_ID"]) for row in testable}
        self.assertEqual(len(cwes), 18)

    def test_source_knowledge_includes_design_schema_fields(self):
        # 修复点：seed 经验卡应包含文档 3.3 的 recommended_action /
        # language_adaptation / non_applicable_boundary 字段。
        row = {"index": 1, "CWE_ID": "22", "task_description": {"function_name": "read_file"},
               "ground_truth": {"vulnerable_code": "open(path)", "patched_code": "check(path)"}}
        response = {"choices": [{"message": {"content": json.dumps({
            "principle": "规范化路径并限制在根目录内",
            "applicability": "外部路径",
            "dangerous_pattern": "字符串前缀判断",
            "recommended_action": "resolve + relative_to 目录边界检查",
            "language_adaptation": {"python": "resolve", "go": "Abs/Rel", "cpp": "weakly_canonical"},
            "non_applicable_boundary": "不涉及文件系统路径时不适用",
        })}}]}
        result = extract_initial_hypothesis(row, requester=lambda _: response)
        self.assertEqual(result["recommended_action"], "resolve + relative_to 目录边界检查")
        self.assertEqual(result["language_adaptation"]["go"], "Abs/Rel")
        self.assertEqual(result["non_applicable_boundary"], "不涉及文件系统路径时不适用")

    def test_experience_memory_tracks_support_count_and_retire(self):
        # 修复点：文档 8.2 要求支持计数/证据引用等追踪字段，且退役经验
        # 应能从 active_cards 中排除。
        memory = ExperienceMemory()
        memory.add_candidate({"id": "c-3", "principle": "p", "applicability": "a"})
        memory.apply_audit("c-3", "supported")
        card = memory.long_term[0]
        self.assertEqual(card["support_count"], 0)
        self.assertIn("evidence_refs", card)
        self.assertEqual([c["id"] for c in memory.active_cards()], ["c-3"])
        memory.retire("c-3")
        self.assertEqual(memory.active_cards(), [])


    def test_audit_comparison_calculates_joint_gain_and_hpass_regression(self):
        passed = {"task_id": 1, "evidence": {"syntax_or_compile": {"status": "pass"}, "functional": {"status": "pass"}, "security": {"status": "pass"}}}
        failed = {"task_id": 1, "evidence": {"syntax_or_compile": {"status": "pass"}, "functional": {"status": "pass"}, "security": {"status": "fail"}}}
        result = compare_audit_records([failed], [passed], [passed])
        self.assertEqual(result["delta_joint_pass"], 1.0)
        self.assertEqual(result["security_regressions"], 0)

    def test_initial_knowledge_extracts_structured_hypothesis_without_answer_code(self):
        row = {"index": 1, "CWE_ID": "22", "task_description": {"function_name": "read_file"},
               "ground_truth": {"vulnerable_code": "open(path)", "patched_code": "check(path)"}}
        response = {"choices": [{"message": {"content": '{"principle":"规范化路径并限制在根目录内","applicability":"外部路径"}'}}]}
        result = extract_initial_hypothesis(row, requester=lambda _: response)
        self.assertEqual(result["cwe"], "22")
        self.assertEqual(result["principle"], "规范化路径并限制在根目录内")
        self.assertNotIn("vulnerable_code", result)

    def test_trajectory_validation_records_unmeasured_when_tests_are_missing(self):
        row = {"index": 2, "CWE_ID": "22", "task_description": {"function_name": "read_file"}, "unittest": {}}
        result = validate_trajectory(row, "def read_file(path):\n    return path")
        self.assertEqual(result.evidence["functional"]["status"], "unmeasured")
        self.assertEqual(result.failure_type, "unmeasured_tests")

    def test_trajectory_validation_classifies_syntax_failure(self):
        row = {"index": 3, "CWE_ID": "22", "task_description": {"function_name": "read_file"}, "unittest": {}}
        result = validate_trajectory(row, "def read_file(:")
        self.assertEqual(result.failure_type, "syntax_error")

    def test_language_contract_marks_python_go_cpp_as_harness_backed(self):
        self.assertEqual(adapter_contract("go")["backend"], "docker_harness")
        self.assertEqual(adapter_contract("java")["backend"], "unmeasured")

    def test_report_writes_summary_metadata_and_markdown(self):
        directory = self._make_workdir()
        write_report(directory, {"source_tasks": 1}, {"feedback_channel": "disabled"})
        self.assertTrue((directory / "lifecycle_replay_report.md").exists())

    def test_frozen_evaluation_checks_hash_and_feedback_boundary(self):
        root = self._make_workdir()
        frozen = root / "frozen"
        frozen.mkdir()
        memory = frozen / "m_star.jsonl"
        memory.write_text("{}\n", encoding="utf-8")
        digest = hashlib.sha256(memory.read_bytes()).hexdigest()
        (frozen / "freeze_metadata.json").write_text(json.dumps({"memory_sha256": digest, "feedback_channel": "disabled"}), encoding="utf-8")
        result = check_frozen_run(root)
        self.assertTrue(result["frozen"])


if __name__ == "__main__":
    unittest.main()

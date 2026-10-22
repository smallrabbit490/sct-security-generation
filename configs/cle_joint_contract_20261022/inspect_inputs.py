"""只读核验 CLE 输入、公开契约和运行条件；不执行模型或候选代码。

本脚本只读取已提交数据及已恢复的历史快照，调用原始静态资格判断与加载器。
它不运行参考实现、隐藏测试或模型，不读取凭据内容，不产生新的 F/S/Joint。
公开字段完整性表示保留数据中现有字段，不证明题面本身没有歧义。
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def read(relative):
    """读取指定的非凭据 JSON；调用者仅传本脚本列出的数据路径。"""
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def file_info(relative):
    """记录文件内容身份，不在摘要复制题面、答案或测试正文。"""
    path = ROOT / relative
    result = {"path": relative, "exists": path.is_file()}
    if path.is_file():
        raw = path.read_bytes()
        result.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return result


def counts(values):
    """生成稳定排序的简单计数。"""
    return dict(sorted(Counter(values).items()))


def task_rows(value):
    """兼容按任务 ID 索引的快照和原始列表，保留原数据不改写。"""
    return list(value.values()) if isinstance(value, dict) else value


def inventory():
    """核验数据身份、集合边界、真实静态谓词及运行前置条件。"""
    from methods.sct_lifecycle_replay.run_lifecycle_replay import has_tests
    from methods.sct_agent.validation_evidence import plt_tests_available
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    from methods.sct_trajectory.semantic_retrieval import PUBLIC_FIELDS, query_embedding_text
    from methods.cle_ablation.runner import public_contract, plt_contract

    raw_path = "data/external/secodeplt/secodeplt/data.json"
    family_path = "data/external/secodeplt/derived_metadata/family_manifest.json"
    pool_path = "configs/cle_memory_q_autonomous_20261015/pools.recovered.json"
    online_path = "configs/cle_q_online_20261020/manifest.json"
    raw, loaded = read(raw_path), _load_tasks(0)
    family, pools, online = read(family_path), read(pool_path), read(online_path)
    raw_by_id = {str(row["index"]): row for row in raw}
    loaded_by_id = {str(row["index"]): row for row in loaded}
    pool_names = {"source": "D_init", "replay": "D_grow", "audit": "D_gate"}
    pool_ids = {key: {str(row["task_id"]) for row in pools[key]} for key in pool_names}
    family_ids = {key: {row["family_id"] for row in pools[key]} for key in pool_names}

    pool_summary = {}
    for key, alias in pool_names.items():
        pool_summary[alias] = {
            "historic_pool_name": key,
            "rows": len(pools[key]),
            "unique_task_ids": len(pool_ids[key]),
            "inferred_seed_families": len(family_ids[key]),
            "missing_from_current_loader": sorted(pool_ids[key] - set(loaded_by_id)),
            "matches_online_manifest_task_set": pool_ids[key] == set(map(str, online[alias])),
            "family_mapping_mismatches": sum(
                row["family_id"] != loaded_by_id.get(str(row["task_id"]), {}).get("family_id")
                for row in pools[key]
            ),
        }
    overlaps = []
    for index, left in enumerate(pool_names):
        for right in list(pool_names)[index + 1:]:
            overlaps.append({
                "pools": [pool_names[left], pool_names[right]],
                "task_overlap": len(pool_ids[left] & pool_ids[right]),
                "inferred_family_overlap": len(family_ids[left] & family_ids[right]),
            })

    datasets = {}
    for subset in ("Base", "Plus"):
        for path in sorted((ROOT / "data/SecEvoBasePlus" / subset).glob("*.json")):
            relative = str(path.relative_to(ROOT))
            rows = read(relative)
            item = {
                **file_info(relative),
                "rows": len(rows),
                "unique_ids": len({str(row["ID"]) for row in rows}),
                "keys": sorted({key for row in rows for key in row}),
                "public_fields_missing_or_empty": {
                    key: sum(not row.get(key) for row in rows)
                    for key in ("ID", "Problem", "Entry_Point")
                },
            }
            if path.name.startswith("Python_"):
                contracts = [public_contract(subset, row) for row in rows]
                item.update(
                    public_contract_keys=sorted({key for row in contracts for key in row}),
                    description_preserved_all=all(c["description"] == r["Problem"] for c, r in zip(contracts, rows)),
                    entry_point_preserved_all=all(c["entry_point"] == r["Entry_Point"] for c, r in zip(contracts, rows)),
                    hidden_field_present_count={
                        key: sum(bool(row.get(key)) for row in rows)
                        for key in ("Secure Code", "Test", "Test-FP", "Test-SP")
                    },
                    cwe_label_counts=counts(str(row["CWE_ID"]) for row in contracts),
                    cwe_leading_zero_rows=sum(str(row["CWE_ID"]).startswith("0") for row in contracts),
                    cwe_multi_label_rows=sum("/" in str(row["CWE_ID"]) for row in contracts),
                )
            datasets[f"{subset}/{path.stem}"] = item

    contract_keys = sorted({key for row in loaded for key in row["task_description"]})
    omitted = {
        key: sum(bool(row["task_description"].get(key)) for row in loaded)
        for key in contract_keys if key not in PUBLIC_FIELDS
    }
    fixture_only = [str(row["index"]) for row in raw
                    if (row.get("unittest") or {}).get("testcases") and not has_tests(row)]

    snapshots = []
    snapshot_paths = (
        "configs/cle_dinit_full_learning_20261020_v4b/tasks.json",
        "configs/cle_dgrow_url_repair_20261019/repaired_tasks.json",
        "configs/cle_memory_q_unlimited_20261018/public_contract_overrides.json",
        "translation_work/diagnostics/20261020/cle_q_online_v1/tasks_D_init.json",
        "translation_work/diagnostics/20261020/cle_q_online_v1/tasks_D_grow.json",
        "translation_work/diagnostics/20261020/cle_q_online_v1/tasks_D_gate.json",
    )
    for relative in snapshot_paths:
        item = file_info(relative)
        if item["exists"]:
            value = read(relative)
            item["entries"] = len(value)
            if "overrides" not in relative:
                rows = task_rows(value)
                item["unique_task_ids"] = len({str(row["index"]) for row in rows})
                item["task_descriptions_differ_from_raw"] = sum(
                    row.get("task_description") != raw_by_id[str(row["index"])].get("task_description")
                    for row in rows
                )
                item["fixtures_differ_from_raw"] = sum(
                    row.get("unittest") != raw_by_id[str(row["index"])].get("unittest")
                    for row in rows
                )
                item["reference_code_fields_differ_from_raw"] = sum(
                    row.get("ground_truth") != raw_by_id[str(row["index"])].get("ground_truth")
                    for row in rows
                )
                item["static_loader_eligible"] = sum(has_tests(row) for row in rows)
        snapshots.append(item)

    online_init_path = snapshot_paths[3]
    inheritance = {"online_D_init_equals_committed_v4b_tasks": None}
    if (ROOT / online_init_path).is_file():
        inheritance["online_D_init_equals_committed_v4b_tasks"] = read(online_init_path) == read(snapshot_paths[0])
    inheritance["online_D_grow_repaired32_equals_committed_repair"] = None
    if (ROOT / snapshot_paths[4]).is_file():
        grow = read(snapshot_paths[4])
        inheritance["online_D_grow_repaired32_equals_committed_repair"] = all(
            grow[str(row["index"])] == row for row in read(snapshot_paths[1])
        )

    banks = {}
    bank_rows = {}
    for stage in ("D_init", "D_grow"):
        relative = f"translation_work/diagnostics/20261020/cle_q_online_v1/{stage}/frozen/m_star_q.jsonl"
        item = file_info(relative)
        if item["exists"]:
            with (ROOT / relative).open(encoding="utf-8") as stream:
                rows = [json.loads(line) for line in stream if line.strip()]
            bank_rows[stage] = rows
            item.update(
                card_count=len(rows),
                unique_card_ids=len({row["invariant_id"] for row in rows}),
                cards_with_q_visits=sum(row.get("q_visits", 0) > 0 for row in rows),
                q_visits_total=sum(row.get("q_visits", 0) for row in rows),
                status_counts=counts(row["status"] for row in rows),
            )
        banks[stage] = item
    if len(bank_rows) == 2:
        left, right = bank_rows["D_init"], bank_rows["D_grow"]
        inheritance["D_init_and_partial_D_grow_bank_non_Q_fields_identical"] = (
            len(left) == len(right) and all(
                {k: v for k, v in a.items() if k not in ("q_value", "q_visits")}
                == {k: v for k, v in b.items() if k not in ("q_value", "q_visits")}
                for a, b in zip(left, right)
            )
        )
        inheritance["Q_values_changed_between_stage_snapshots"] = sum(
            a.get("q_value") != b.get("q_value") for a, b in zip(left, right)
        )
    metadata_path = "translation_work/diagnostics/20261020/cle_q_online_v1/run_metadata.json"
    online_metadata = file_info(metadata_path)
    if online_metadata["exists"]:
        saved = read(metadata_path)
        online_metadata.update({key: saved.get(key) for key in ("protocol", "status", "completed_stages", "commit")})
    banks["historical_run_metadata"] = online_metadata

    requirements = counts(json.dumps(row.get("install_requires"), ensure_ascii=False) for row in loaded)
    known_key_files = (
        "local_secrets/chatanywhereapi使用/apikey.txt",
        "local_secrets/chatanywhereapi使用/chatanywhere_test.env",
    )
    env_keys = ("CHATANYWHERE_API_KEY", "OPENAI_API_KEY", "INFRAMIG_API_KEY")
    return {
        "schema_version": "cle-input-inventory-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scope": {
            "mode": "read_only_input_and_environment_diagnostic",
            "API_calls": 0,
            "candidate_executions": 0,
            "official_scores_generated": False,
            "credential_values_read": False,
            "score_boundary": "Fixture/schema existence is not a measured F/S/Joint result.",
        },
        "plt": {
            **file_info(raw_path),
            "raw_rows": len(raw),
            "nonempty_testcase_rows": sum(bool((row.get("unittest") or {}).get("testcases")) for row in raw),
            "runtime_loader_rows": len(loaded),
            "static_has_tests_rows": sum(has_tests(row) for row in raw),
            "validator_structural_eligibility_raw": sum(plt_tests_available(row) for row in raw),
            "validator_structural_eligibility_loaded": sum(plt_tests_available(row) for row in loaded),
            "nonempty_but_loader_ineligible_task_ids": fixture_only,
            "runtime_cwe_counts": counts(str(row["CWE_ID"]) for row in loaded),
            "public_task_description_keys": contract_keys,
            "plt_contract_preserves_all_available_task_description_fields": all(
                all(plt_contract(row).get(key) == value for key, value in row["task_description"].items())
                for row in loaded
            ),
            "query_embedding_omits_nonempty_public_fields": omitted,
            "query_embedding_omission_probe": {
                "input": {"function_name": "f", "return": "public return", "raise": "public exception"},
                "output_keys": sorted(json.loads(query_embedding_text({
                    "function_name": "f", "return": "public return", "raise": "public exception"}))),
                "synthetic_probe_not_experiment": True,
            },
            "declared_install_requires_counts": requirements,
            "formal_cle_development_gate_denominator": len(pool_ids["audit"]),
            "raw_external_rows_are_not_1411_independent_final_test_tasks": True,
        },
        "family_manifest": {
            **file_info(family_path),
            "classification_version": family.get("classification_version"),
            "seed_family_basis": family.get("seed_family_basis"),
            "classification_count": len(family["row_classification"]),
            "official_source_family_labels": False,
        },
        "pools": {
            "source": file_info(pool_path),
            "online_manifest": file_info(online_path),
            "sets": pool_summary,
            "overlap": overlaps,
            "union_equals_loader": set().union(*pool_ids.values()) == set(loaded_by_id),
            "D_grow_reward_eligible": len(online["D_grow_reward_eligible"]),
            "D_grow_reward_ineligible": len(online["D_grow_reward_ineligible"]),
        },
        "datasets": datasets,
        "versioned_task_snapshots": snapshots,
        "snapshot_inheritance": inheritance,
        "historical_bank_snapshots": banks,
        "environment": {
            "python_version": platform.python_version(),
            "commands_present": {name: bool(shutil.which(name)) for name in ("python", "python3", "docker", "git", "pytest", "gh")},
            "packages_present": {name: importlib.util.find_spec(name) is not None
                                 for name in ("numpy", "sympy", "yaml", "requests", "openai", "pytest", "scipy")},
            "credential_environment_presence_only": {name: bool(os.environ.get(name)) for name in env_keys},
            "credential_files_presence_only": {name: (ROOT / name).is_file() for name in known_key_files},
            "current_native_requester_credential_sources": ["CHATANYWHERE_API_KEY", known_key_files[0]],
            "current_native_requester_uses_openai_env_fallback": False,
            "github_workflows_directory_present": (ROOT / ".github/workflows").is_dir(),
            "PLT_native_validator": "methods.sct_agent.validation_evidence.validate_plt_row(row, code, backend='local')",
            "PLT_execution_boundary": "Original local python -I worker; no Docker required; run only isolated saved candidates or controls.",
            "Base_Plus_native_validator": "translation_pipeline.python_validator.validate_python_secure",
            "Base_Plus_docker_image": "safecoder-python-validator:local",
            "Base_Plus_parent_image": "porta-bench-runtime-python3:latest",
            "Base_Plus_missing_Docker_is_unmeasured_not_failure": True,
            "model_generation_requires_credentials": True,
        },
        "limitations": [
            "Raw dataset counts do not establish correctness of reference code or test fixtures.",
            "Public task descriptions may be underspecified despite lossless field extraction.",
            "Semantic query currently omits native return/raise fields, though generation receives them.",
            "Current semantic candidate recall uses all permitted language/status cards; CWE text formatting does not hard-filter that path.",
            "Historical dynamic results and new candidate generation are not recomputed by this inventory.",
            "No entire online-Q trajectory certification follows from snapshot identity.",
            "No hidden Base/Plus feedback may inform generation, candidate selection, stopping, or memory updates.",
        ],
    }


def main():
    """保存精简诊断；限定摘要目录，不触碰正式数据和历史原始结果。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "results/curated/cle_joint_contract_20261022/data_inventory.json")
    args = parser.parse_args()
    target = args.out.resolve()
    if not target.is_relative_to((ROOT / "results/curated/cle_joint_contract_20261022").resolve()):
        parser.error("output must remain in this diagnostic's curated directory")
    result = inventory()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(target.relative_to(ROOT)), "PLT_loaded": result["plt"]["runtime_loader_rows"],
                      "Base_Python": result["datasets"]["Base/Python_Base"]["rows"],
                      "Plus_Python": result["datasets"]["Plus/Python_Plus"]["rows"],
                      "API_calls": 0, "candidate_executions": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()

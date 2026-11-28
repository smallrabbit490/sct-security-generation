#!/usr/bin/env python3
"""从冻结的132题点收清单生成已有结果交付文件，不执行任何测试。"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECKLIST = ROOT / "task7_submission_checklist_132.csv"
FUNCTIONAL_RUN = "issta_task7_intake_132_20261128"
PREFIX_RUN = "task7_ordinary_prefix_20261128"
REVIEWED_RUN = "task7_reviewed_security_20261128"
NOT_RUN = "task7_security_not_run_no_batch"
CSV_FIELDS = (
    "group", "id", "language", "revision", "reference_id",
    "functional_run_id", "functional_fixture_id", "functional_status",
    "functional_passed", "functional_executed", "functional_total",
    "functional_jsonl_line", "functional_note", "functional_source",
    "security_run_id", "security_fixture_id", "security_status",
    "security_passed", "security_executed", "security_total",
    "security_jsonl_line", "security_note", "security_source",
)


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("".join(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n" for record in records), encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    with CHECKLIST.open(encoding="utf-8-sig", newline="") as handle:
        checklist = list(csv.DictReader(handle))
    if len(checklist) != 132:
        raise ValueError(f"需要132题，实际{len(checklist)}")

    csv_rows = []
    receipts = []
    source_records = []
    for index, item in enumerate(checklist):
        group, task_id, language, revision = (item[field] for field in ("group", "id", "language", "revision"))
        reference_id = f"{group}:{task_id}@{revision}"
        functional_total = int(item["expected_functional_total"])
        security_total = int(item["expected_security_total"])
        functional_line = int(item["functional_jsonl_line"])
        security_line = int(item["security_jsonl_line"])
        if (functional_line, security_line) != (index * 2 + 1, index * 2 + 2):
            raise ValueError(f"JSONL行号不连续: {group}/{task_id}")
        if item["csv_line"] != str(index + 2):
            raise ValueError(f"CSV行号不连续: {group}/{task_id}")

        functional_value = item["local_functional"]
        if functional_value == "pass":
            functional_passed = functional_total
        else:
            match = re.fullmatch(r"([0-9]+)/([0-9]+)", functional_value)
            if not match:
                raise ValueError(f"未知功能摘要: {group}/{task_id}: {functional_value}")
            functional_passed, functional_executed = map(int, match.groups())
            if functional_executed != functional_total:
                raise ValueError(f"功能摘要不是完整套件: {group}/{task_id}")
        functional_note = (
            f"清单登记已有普通功能复跑{functional_passed}/{functional_total}通过，按原check()完整入口的1个套件判定计；原批次运行器、镜像及逐用例回执未随附件交付，待补追溯材料。"
            if item["count_unit"] == "check_gate" else
            f"清单登记已有普通功能复跑{functional_passed}/{functional_total}通过；原批次运行器、镜像及逐用例回执未随附件交付，待补追溯材料。"
        )
        if group == "plt":
            functional_fixture = f"data/external/secodeplt/secodeplt/data.json#index={task_id}/unittest.testcases:functionality"
        elif group == "codeseceval-plus":
            functional_fixture = f"data/SecEvoBasePlus/Plus/Python_Plus.json#ID={task_id}/get_python_suites:functional"
        else:
            functional_fixture = item["baseline_security_fixture"].replace("_test.py#pytest_params_security", "_test.py#pytest_params_functionality")

        security_value = item["local_reviewed_security"]
        if security_value == "none":
            security_run = NOT_RUN
            security_status = "not_run"
            security_passed = None
            security_executed = None
            security_note = "现有附件未登记该题安全侧执行结果，状态为not_run且通过数、执行数留空；" + item["why_pending"]
        elif security_value == "ordinary_prefix_pass":
            security_run = PREFIX_RUN
            security_status = "partial"
            security_passed = None
            security_executed = 0
            security_note = "仅登记普通前置调用通过，不能覆盖完整原check()安全判定；executed=0表示没有形成可计作原安全套件判定的用例，完整套件计划总数为1。" + item["why_pending"]
        else:
            match = re.fullmatch(r"reviewed_subset ([0-9]+)/[0-9]+ of ([0-9]+) original", security_value)
            if not match or int(match[2]) != security_total:
                raise ValueError(f"未知安全摘要: {group}/{task_id}: {security_value}")
            security_run = REVIEWED_RUN
            security_status = "partial"
            security_passed = security_executed = int(match[1])
            security_note = f"本机仅复跑原安全套件普通子集{security_passed}/{security_executed}通过；原套件计划{security_total}条，未覆盖其余用例，不作为完整安全或Joint结论。原逐用例回执附件未随本次材料提供。" + item["why_pending"]

        row = {
            "group": group, "id": task_id, "language": language, "revision": revision,
            "reference_id": reference_id,
            "functional_run_id": FUNCTIONAL_RUN, "functional_fixture_id": functional_fixture,
            "functional_status": "completed", "functional_passed": functional_passed,
            "functional_executed": functional_total, "functional_total": functional_total,
            "functional_jsonl_line": functional_line, "functional_note": functional_note,
            "functional_source": f"task7_sanitized_receipts.jsonl#L{functional_line}",
            "security_run_id": security_run, "security_fixture_id": item["baseline_security_fixture"],
            "security_status": security_status, "security_passed": security_passed,
            "security_executed": security_executed, "security_total": security_total,
            "security_jsonl_line": security_line, "security_note": security_note,
            "security_source": f"task7_sanitized_receipts.jsonl#L{security_line}",
        }
        csv_rows.append(row)
        common = {
            "group": group, "id": task_id, "language": language, "revision": revision,
            "reference_id": reference_id,
        }
        receipts.append({
            "record_id": f"task7-{functional_line:03d}-functional", **common, "suite": "functional",
            "run_id": FUNCTIONAL_RUN, "fixture_id": functional_fixture, "status": "completed",
            "passed": functional_passed, "executed": functional_total, "total": functional_total,
            "source_locator": f"evidence/source_task7_existing_results.jsonl#L{functional_line}",
            "note": functional_note,
        })
        receipts.append({
            "record_id": f"task7-{security_line:03d}-security", **common, "suite": "security",
            "run_id": security_run, "fixture_id": item["baseline_security_fixture"], "status": security_status,
            "passed": security_passed, "executed": security_executed, "total": security_total,
            "source_locator": f"evidence/source_task7_existing_results.jsonl#L{security_line}",
            "note": security_note,
        })
        evidence_common = {
            **common,
            "checklist_line": index + 2,
            "baseline_security_fixture": item["baseline_security_fixture"],
            "baseline_security_identity_sha256": item["baseline_security_identity_sha256"],
            "count_unit": item["count_unit"],
            "evidence_origin": "随附132题点收清单的已有结果摘要；不是本次重新执行。",
            "raw_receipt_retention": "not_retained",
        }
        source_records.append({
            **evidence_common, "suite": "functional", "run_id": FUNCTIONAL_RUN,
            "fixture_id": functional_fixture, "status": "completed", "passed": functional_passed,
            "executed": functional_total, "total": functional_total, "reported_result": functional_value,
            "note": functional_note,
        })
        source_records.append({
            **evidence_common, "suite": "security", "run_id": security_run,
            "fixture_id": item["baseline_security_fixture"], "status": security_status,
            "passed": security_passed, "executed": security_executed, "total": security_total,
            "reported_result": security_value, "note": security_note,
        })

    with (ROOT / "task7_replay_receipts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows)
    write_jsonl(ROOT / "task7_sanitized_receipts.jsonl", receipts)
    write_jsonl(ROOT / "evidence/source_task7_existing_results.jsonl", source_records)

    manifest_path = ROOT / "task7_run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["scope_baseline"]["checklist_sha256"] = sha256(CHECKLIST)
    manifest["intake_provenance"].setdefault("request_sha256", "not_retained")
    manifest["source_receipt_links"] = {"all_suites": "evidence/source_task7_existing_results.jsonl"}
    hash_files = [
        ROOT / "task7_replay_receipts.csv", ROOT / "task7_sanitized_receipts.jsonl",
        ROOT / "plt76_author_decision.md", ROOT / "evidence/source_task7_existing_results.jsonl",
    ]
    manifest["files_sha256"] = {path.relative_to(ROOT).as_posix(): sha256(path) for path in hash_files}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    validator = ROOT / "validate_task7_intake.py"
    if validator.is_file():
        import validate_task7_intake
        failures = validate_task7_intake.validate(ROOT)
        if failures:
            raise ValueError("生成后点收失败: " + "; ".join(failures))
    print(f"生成{len(csv_rows)}条CSV、{len(receipts)}条JSONL及{len(hash_files) - 3}份证据附件，生成后校验通过。")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""ISSTA 第7项132题脱敏交付包的离线结构与一致性校验。"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

EXPECTED_TASKS = 132
EXPECTED_RECORDS = 264
EXPECTED_GROUPS = {"plt": 122, "codeseceval-plus": 3, "cweval": 7}
ALLOWED_STATUSES = {"completed", "partial", "timeout", "error", "not_run", "not_retained", "unknown"}
REQUIRED_FILES = (
    "task7_replay_receipts.csv",
    "task7_sanitized_receipts.jsonl",
    "task7_run_manifest.json",
    "plt76_author_decision.md",
)
CSV_FIELDS = (
    "group", "id", "language", "revision", "reference_id",
    "functional_run_id", "functional_fixture_id", "functional_status",
    "functional_passed", "functional_executed", "functional_total",
    "functional_jsonl_line", "functional_note", "functional_source",
    "security_run_id", "security_fixture_id", "security_status",
    "security_passed", "security_executed", "security_total",
    "security_jsonl_line", "security_note", "security_source",
)
RECEIPT_FIELDS = (
    "record_id", "group", "id", "language", "revision", "reference_id",
    "suite", "run_id", "fixture_id", "status", "passed", "executed",
    "total", "source_locator", "note",
)


def load_json(path: Path):
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def valid_count(value) -> bool:
    return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)


def validate(directory: Path) -> list[str]:
    errors: list[str] = []
    directory = directory.resolve()
    for name in (*REQUIRED_FILES, "task7_submission_checklist_132.csv"):
        if not (directory / name).is_file():
            errors.append(f"缺文件: {name}")
    if errors:
        return errors

    csv_path = directory / "task7_replay_receipts.csv"
    jsonl_path = directory / "task7_sanitized_receipts.jsonl"
    manifest_path = directory / "task7_run_manifest.json"
    checklist_path = directory / "task7_submission_checklist_132.csv"

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if reader.fieldnames != list(CSV_FIELDS):
            errors.append(f"CSV表头不符: {reader.fieldnames}")
    with checklist_path.open(encoding="utf-8-sig", newline="") as handle:
        checklist = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_TASKS:
        errors.append(f"CSV数据行应为{EXPECTED_TASKS}，实际{len(rows)}")
    if len(checklist) != EXPECTED_TASKS:
        errors.append(f"点收清单数据行应为{EXPECTED_TASKS}，实际{len(checklist)}")

    try:
        manifest = load_json(manifest_path)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [*errors, f"manifest不是有效UTF-8 JSON: {exc}"]
    try:
        scope = manifest["scope_baseline"]
        if scope.get("tasks") != EXPECTED_TASKS or scope.get("records") != EXPECTED_RECORDS:
            errors.append("scope_baseline的tasks/records不符")
        if scope.get("scope_by_group") != EXPECTED_GROUPS:
            errors.append("scope_baseline的分组数量不符")
        if scope.get("checklist_sha256") != sha256(checklist_path):
            errors.append("scope_baseline.checklist_sha256不匹配")
    except (KeyError, TypeError):
        errors.append("manifest缺scope_baseline或其必填字段")

    records = []
    with jsonl_path.open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                errors.append(f"JSONL第{line_number}行为空")
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"JSONL第{line_number}行无效: {exc}")
                continue
            records.append(record)
            if tuple(record) != RECEIPT_FIELDS:
                errors.append(f"JSONL第{line_number}行字段或顺序不符")
    if len(records) != EXPECTED_RECORDS:
        errors.append(f"JSONL应为{EXPECTED_RECORDS}行，实际{len(records)}")

    keys = [(row.get("group"), row.get("id")) for row in rows]
    duplicate_keys = [key for key, count in Counter(keys).items() if count > 1]
    if duplicate_keys:
        errors.append(f"CSV存在重复题键: {duplicate_keys[:5]}")
    if Counter(row.get("group") for row in rows) != Counter(EXPECTED_GROUPS):
        errors.append("CSV分组数量不符")

    record_ids = [record.get("record_id") for record in records]
    if len(set(record_ids)) != len(record_ids):
        errors.append("JSONL record_id不唯一")
    run_ids = {run.get("run_id") for run in manifest.get("runs", []) if isinstance(run, dict)}
    if len(run_ids) != len(manifest.get("runs", [])):
        errors.append("manifest runs存在重复或缺失run_id")
    attachments = set()
    complete_pairs = 0

    for index, row in enumerate(rows):
        csv_line = index + 2
        key = keys[index]
        expected = checklist[index] if index < len(checklist) else {}
        if (expected.get("group"), expected.get("id")) != key:
            errors.append(f"CSV第{csv_line}行题键与清单顺序不符")
        for field in ("language", "revision"):
            if row.get(field) != expected.get(field):
                errors.append(f"CSV第{csv_line}行{field}与清单不符")
        if str(expected.get("csv_line")) != str(csv_line):
            errors.append(f"清单第{csv_line}行csv_line不符")
        if not row.get("reference_id"):
            errors.append(f"CSV第{csv_line}行reference_id为空")
        reference_id = f"{key[0]}:{key[1]}@{row.get('revision')}"
        if row.get("reference_id") != reference_id:
            errors.append(f"CSV第{csv_line}行reference_id不是清单修订对应的参考实现标识")
        expected_functional = expected.get("local_functional", "")
        expected_security = expected.get("local_reviewed_security", "")
        expected_functional_status = "completed" if re.fullmatch(r"(?:pass|[0-9]+/[0-9]+)", expected_functional) else "unknown"
        expected_security_status = (
            "partial" if expected_security.startswith("reviewed_subset")
            else "partial" if expected_security == "ordinary_prefix_pass"
            else "not_run" if expected_security == "none"
            else "unknown"
        )
        if row.get("functional_status") != expected_functional_status:
            errors.append(f"CSV第{csv_line}行功能状态与清单摘要不符")
        if row.get("security_status") != expected_security_status:
            errors.append(f"CSV第{csv_line}行安全状态与清单摘要不符")
        if expected_functional_status == "completed":
            match_functional = re.fullmatch(r"([0-9]+)/([0-9]+)", expected_functional)
            if expected_functional == "pass":
                functional_counts = (1, 1)
            elif match_functional and match_functional[1] == match_functional[2]:
                functional_counts = (int(match_functional[1]), int(match_functional[1]))
            else:
                errors.append(f"CSV第{csv_line}行功能completed但清单未登记全通过")
                functional_counts = None
            if functional_counts and (row.get("functional_passed"), row.get("functional_executed")) != tuple(map(str, functional_counts)):
                errors.append(f"CSV第{csv_line}行功能通过数/执行数与清单不符")
        if expected_security_status == "partial" and expected_security.startswith("reviewed_subset"):
            match_security = re.fullmatch(r"reviewed_subset ([0-9]+)/[0-9]+ of ([0-9]+) original", expected_security)
            if not match_security:
                errors.append(f"清单第{csv_line}行安全子集摘要格式无效")
            elif (row.get("security_passed"), row.get("security_executed")) != (match_security[1], match_security[1]):
                errors.append(f"CSV第{csv_line}行安全子集通过数/执行数与清单不符")
        if expected_security_status == "not_run" and (row.get("security_passed") or row.get("security_executed")):
            errors.append(f"CSV第{csv_line}行not_run不应有测量值")

        sides = {}
        for offset, suite in enumerate(("functional", "security")):
            jsonl_line = index * 2 + offset + 1
            prefix = f"{suite}_"
            line_field = f"{prefix}jsonl_line"
            source = row.get(f"{prefix}source", "")
            status = row.get(f"{prefix}status", "")
            if row.get(line_field) != str(jsonl_line):
                errors.append(f"CSV第{csv_line}行{line_field}应为{jsonl_line}")
            if source != f"task7_sanitized_receipts.jsonl#L{jsonl_line}":
                errors.append(f"CSV第{csv_line}行{prefix}source不符")
            if str(expected.get(f"{suite}_jsonl_line")) != str(jsonl_line):
                errors.append(f"清单第{csv_line}行{suite}_jsonl_line不符")
            if status not in ALLOWED_STATUSES:
                errors.append(f"CSV第{csv_line}行{prefix}status无效: {status}")
            if status != "completed" and not row.get(f"{prefix}note", "").strip():
                errors.append(f"CSV第{csv_line}行非completed的{suite}缺原因")
            if not row.get(f"{prefix}run_id") or not row.get(f"{prefix}fixture_id"):
                errors.append(f"CSV第{csv_line}行{suite}缺批次或夹具")
            if row.get(f"{prefix}run_id") not in run_ids:
                errors.append(f"CSV第{csv_line}行{suite}引用了未登记批次")
            if row.get(f"{prefix}total") != expected.get(f"expected_{suite}_total"):
                errors.append(f"CSV第{csv_line}行{suite}计划总数与清单不符")

            if jsonl_line <= len(records):
                record = records[jsonl_line - 1]
                fixed = {
                    "group": key[0], "id": key[1], "language": row.get("language"),
                    "revision": row.get("revision"), "reference_id": row.get("reference_id"),
                    "suite": suite, "run_id": row.get(f"{prefix}run_id"),
                    "fixture_id": row.get(f"{prefix}fixture_id"), "status": status,
                    "note": row.get(f"{prefix}note"),
                }
                for field, value in fixed.items():
                    if record.get(field) != value:
                        errors.append(f"JSONL第{jsonl_line}行{field}与CSV不符")
                for field in ("passed", "executed", "total"):
                    raw = row.get(f"{prefix}{field}", "")
                    csv_value = int(raw) if raw else None
                    if record.get(field) != csv_value:
                        errors.append(f"JSONL第{jsonl_line}行{field}与CSV不符")
                    if not valid_count(record.get(field)):
                        errors.append(f"JSONL第{jsonl_line}行{field}不是非负整数或空")
                if status == "not_run" and any(record.get(field) is not None for field in ("passed", "executed")):
                    errors.append(f"JSONL第{jsonl_line}行not_run不应有测量值")
                if status == "completed":
                    values = [record.get(field) for field in ("passed", "executed", "total")]
                    if not all(isinstance(value, int) and not isinstance(value, bool) for value in values):
                        errors.append(f"JSONL第{jsonl_line}行completed缺有效计数")
                    elif record.get("executed") != record.get("total") or not (0 <= record.get("passed") <= record.get("executed")):
                        errors.append(f"JSONL第{jsonl_line}行completed计数不符")
                if status == "partial":
                    executed = record.get("executed")
                    total = record.get("total")
                    passed = record.get("passed")
                    if not all(isinstance(value, int) and not isinstance(value, bool) for value in (executed, total)):
                        errors.append(f"JSONL第{jsonl_line}行partial缺有效执行数/计划数")
                    elif not (0 <= executed < total) or (passed is not None and not (isinstance(passed, int) and 0 <= passed <= executed)):
                        errors.append(f"JSONL第{jsonl_line}行partial计数不符")
                locator = record.get("source_locator", "")
                match = re.fullmatch(r"(.+)#L([1-9][0-9]*)", locator)
                if not match or locator.startswith(("https://", "http://")):
                    if not locator.startswith("https://"):
                        errors.append(f"JSONL第{jsonl_line}行source_locator格式无效: {locator}")
                else:
                    relative, line_text = match.groups()
                    source_path = PurePosixPath(relative)
                    if source_path.is_absolute() or ".." in source_path.parts or re.match(r"^[A-Za-z]:", relative):
                        errors.append(f"JSONL第{jsonl_line}行含非包内路径: {locator}")
                        continue
                    source_file = directory.joinpath(*source_path.parts)
                    if not source_file.is_file():
                        errors.append(f"JSONL第{jsonl_line}行附件不存在: {relative}")
                        continue
                    attachments.add(relative)
                    with source_file.open(encoding="utf-8-sig") as source_handle:
                        source_lines = source_handle.readlines()
                    source_line = int(line_text)
                    if not 1 <= source_line <= len(source_lines):
                        errors.append(f"JSONL第{jsonl_line}行附件行号越界: {locator}")
                    elif source_file.suffix == ".jsonl":
                        try:
                            source_record = json.loads(source_lines[source_line - 1])
                        except json.JSONDecodeError:
                            errors.append(f"附件不是有效JSONL: {locator}")
                        else:
                            for source_field in ("group", "id", "suite"):
                                if source_record.get(source_field) != (suite if source_field == "suite" else key[0 if source_field == "group" else 1]):
                                    errors.append(f"附件题键/套件与引用不符: {locator}")
                            for source_field in ("revision", "reference_id", "run_id", "fixture_id", "status", "passed", "executed", "total", "note"):
                                if source_record.get(source_field) != record.get(source_field):
                                    errors.append(f"附件{source_field}与JSONL不符: {locator}")
                            if source_record.get("checklist_line") != csv_line:
                                errors.append(f"附件点收清单行号不符: {locator}")
                            if source_record.get("baseline_security_identity_sha256") != expected.get("baseline_security_identity_sha256"):
                                errors.append(f"附件原安全夹具身份哈希不符: {locator}")
                            if source_record.get("baseline_security_fixture") != expected.get("baseline_security_fixture"):
                                errors.append(f"附件原安全夹具定位不符: {locator}")
            sides[suite] = status
        if sides == {"functional": "completed", "security": "completed"}:
            complete_pairs += 1

    if complete_pairs != 0:
        errors.append("本次已有结果不应出现完整安全completed对，请人工复核是否混入新证据")
    decision = (directory / "plt76_author_decision.md").read_text(encoding="utf-8-sig")
    if not re.search(r"^status:\s*pending\s*$", decision, re.MULTILINE):
        errors.append("SeCodePLT 76在未提供作者确认时必须保持status: pending")

    hashes = manifest.get("files_sha256")
    if not isinstance(hashes, dict):
        errors.append("manifest.files_sha256必须是对象")
        hashes = {}
    expected_hashes = set(REQUIRED_FILES[:2]) | {"plt76_author_decision.md"} | attachments
    if set(hashes) != expected_hashes:
        errors.append(f"files_sha256文件集合不符: 缺{sorted(expected_hashes - set(hashes))}，多{sorted(set(hashes) - expected_hashes)}")
    for relative, expected_hash in hashes.items():
        source_path = PurePosixPath(relative)
        target = directory.joinpath(*source_path.parts)
        if source_path.is_absolute() or ".." in source_path.parts or not target.is_file():
            errors.append(f"哈希路径无效: {relative}")
        elif expected_hash != sha256(target):
            errors.append(f"SHA-256不匹配: {relative}")

    for text_path in (csv_path, jsonl_path):
        text = text_path.read_text(encoding="utf-8-sig")
        if re.search(r"(?:[A-Za-z]:[\\/]|\\\\|/home/|/Users/)", text):
            errors.append(f"交付表含本机绝对路径: {text_path.name}")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("用法: python -B -X utf8 validate_task7_intake.py <revised目录>", file=sys.stderr)
        return 2
    directory = Path(sys.argv[1])
    if not directory.is_dir():
        print(f"FAIL: 目录不存在: {directory}", file=sys.stderr)
        return 2
    errors = validate(directory)
    if errors:
        print(f"FAIL: {len(errors)}项问题")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: 4份必交文件、132题、264条套件记录、键/行号/状态/计数、批次、哈希及包内证据位置均通过结构校验。")
    print("边界: 132条功能completed；安全侧5条partial、127条not_run；完整可追溯Joint对为0；PLT 76裁定pending。")
    print("注意: 结构通过不等于原运行器、环境或结果语义已通过人工复核。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Check a local ISSTA result package without modifying it."""

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import sys


TASK_KEY = ("group", "id", "protocol")
SUMMARY_KEY = ("group", "language", "protocol", "metric")
METRICS = ("functional", "security", "joint")
STATUSES = ("pass", "fail", "error", "not_measured")
BINARY_RESULTS = ("pass", "fail")
OUTCOMES = "task_outcomes.csv"
RESULTS = "results.csv"
UNRESOLVED = "unresolved.csv"
MANIFEST = "run_manifest.json"
CSV_HEADERS = {
    OUTCOMES: (*TASK_KEY, "language", *(metric + "_status" for metric in METRICS), "evidence_ref"),
    RESULTS: (*SUMMARY_KEY, "total", *STATUSES),
    UNRESOLVED: (*TASK_KEY, "reason", "evidence_ref"),
}


def read_rows(path):
    required = CSV_HEADERS[path.name]
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        header = reader.fieldnames or []
        missing = set(required) - set(header)
        if missing or len(header) != len(set(header)):
            raise ValueError(f"{path.name}: invalid header, missing columns {sorted(missing)}")
        for row in reader:
            location = f"{path.name}:{reader.line_num}"
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{location}: row width differs from header")
            empty = [column for column in required if not row[column].strip()]
            if empty:
                raise ValueError(f"{location}: empty required fields {empty}")
            yield location, row


def read_manifest(folder):
    missing = [name for name in (*CSV_HEADERS, MANIFEST) if not (folder / name).is_file()]
    if missing:
        raise ValueError(f"Missing required files: {', '.join(missing)}")

    manifest = json.loads((folder / MANIFEST).read_text(encoding="utf-8-sig"))
    if not isinstance(manifest, dict):
        raise ValueError(f"{MANIFEST}: expected a JSON object")
    provenance = ("batch_id", "baseline_ref", "branch", "input_ref", "runner_ref")
    invalid = [key for key in provenance if not str_value(manifest.get(key))]
    if invalid:
        raise ValueError(f"{MANIFEST}: missing or invalid provenance fields {invalid}")

    counts = manifest.get("protocol_counts")
    if not isinstance(counts, dict) or not counts or any(
        not str_value(name) or type(count) is not int or count < 1 for name, count in counts.items()
    ):
        raise ValueError(f"{MANIFEST}: protocol_counts must map protocol names to positive integers")

    hashes = manifest.get("files_sha256")
    if not isinstance(hashes, dict):
        raise ValueError(f"{MANIFEST}: files_sha256 must map CSV names to SHA-256 digests")
    for name in CSV_HEADERS:
        with (folder / name).open("rb") as stream:
            computed = hashlib.file_digest(stream, "sha256").hexdigest()
        if not isinstance(hashes.get(name), str) or hashes[name].lower() != computed:
            raise ValueError(f"{MANIFEST}: SHA-256 is missing or mismatched for {name}")
    return counts


def str_value(value):
    return isinstance(value, str) and bool(value.strip())


def check_package(folder):
    expected_counts = read_manifest(folder)
    counts = Counter()
    keys = set()
    gaps = set()
    summary = defaultdict(Counter)
    for location, row in read_rows(folder / OUTCOMES):
        key = tuple(row[column] for column in TASK_KEY)
        if key in keys:
            raise ValueError(f"{location}: duplicate task/protocol {key}")
        keys.add(key)
        counts[row["protocol"]] += 1
        functional, security, joint = (row[metric + "_status"] for metric in METRICS)
        if any(status not in STATUSES for status in (functional, security, joint)):
            raise ValueError(f"{location}: unknown result status for {key}")

        expected_joint = "not_measured"
        if functional in BINARY_RESULTS and security in BINARY_RESULTS:
            expected_joint = "fail" if "fail" in (functional, security) else "pass"
        if joint != expected_joint:
            raise ValueError(f"{location}: Joint for {key} must be {expected_joint}, got {joint}")
        if joint == "not_measured":
            gaps.add(key)
        for metric, status in zip(METRICS, (functional, security, joint)):
            summary[row["group"], row["language"], row["protocol"], metric][status] += 1

    if dict(counts) != expected_counts:
        raise ValueError(f"{OUTCOMES}: protocol counts are {dict(counts)}, expected {expected_counts}")

    seen_summaries = set()
    for location, row in read_rows(folder / RESULTS):
        key = tuple(row[column] for column in SUMMARY_KEY)
        if key not in summary or key in seen_summaries:
            raise ValueError(f"{location}: unexpected or duplicate summary {key}")
        expected = summary[key]
        if int(row["total"]) != sum(expected.values()) or any(
            int(row[status]) != expected[status] for status in STATUSES
        ):
            raise ValueError(f"{location}: summary disagrees with {OUTCOMES} for {key}")
        seen_summaries.add(key)
    missing_summaries = summary.keys() - seen_summaries
    if missing_summaries:
        raise ValueError(f"{RESULTS}: {len(missing_summaries)} summaries missing, e.g. {min(missing_summaries)}")

    unresolved = set()
    for location, row in read_rows(folder / UNRESOLVED):
        key = tuple(row[column] for column in TASK_KEY)
        if key not in keys or key in unresolved:
            raise ValueError(f"{location}: unexpected or duplicate task/protocol {key}")
        unresolved.add(key)
    missing_gaps = gaps - unresolved
    if missing_gaps:
        raise ValueError(f"{UNRESOLVED}: {len(missing_gaps)} gaps missing, e.g. {min(missing_gaps)}")

    return len(keys), len(seen_summaries), len(unresolved)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="directory containing the four package files")
    args = parser.parse_args()
    try:
        outcomes, summaries, unresolved = check_package(args.folder)
    except (OSError, ValueError, csv.Error) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: {outcomes} task/protocol rows, {summaries} summaries, {unresolved} unresolved rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

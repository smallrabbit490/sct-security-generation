from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .run_translate_dataset import (
    DEFAULT_MODEL,
    is_validation_complete,
    mark_record_timeout,
    safe_write_json,
    with_default_translation_fields,
    write_summary,
)


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _load_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {path}")
    return data


def _merge_by_id(base_records: list[dict[str, Any]], updates: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [updates.get(str(record.get("ID")), with_default_translation_fields(record)) for record in base_records]


def _record_output_path(output_path: Path, record_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in record_id)
    return output_path.parent / f"{output_path.stem}.{safe_id}.single.json"


def _write_single_input(path: Path, record: dict[str, Any]) -> None:
    path.write_text(json.dumps([record], ensure_ascii=False, indent=2), encoding="utf-8")


def _run_single_record(
    *,
    record: dict[str, Any],
    package_dir: Path,
    single_input: Path,
    single_output: Path,
    model: str,
    request_timeout: int,
    max_tokens: int,
    max_repair_attempts: int,
    record_timeout: int,
    skip_secure_validation: bool,
    skip_insecure_validation: bool,
) -> tuple[dict[str, Any], str]:
    _write_single_input(single_input, record)
    args = [
        sys.executable,
        "-m",
        "translation_pipeline.run_translate_dataset",
        "--data-path",
        str(single_input),
        "--output-path",
        str(single_output),
        "--model",
        model,
        "--max-workers",
        "1",
        "--validate-existing",
        "--request-timeout",
        str(request_timeout),
        "--max-tokens",
        str(max_tokens),
        "--max-repair-attempts",
        str(max_repair_attempts),
    ]
    if skip_secure_validation:
        args.append("--skip-secure-validation")
    if skip_insecure_validation:
        args.append("--skip-insecure-validation")

    try:
        completed = subprocess.run(
            args,
            cwd=package_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=record_timeout,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = mark_record_timeout(
            record,
            timeout_seconds=record_timeout,
            skip_secure_validation=skip_secure_validation,
            skip_insecure_validation=skip_insecure_validation,
        )
        timed_out["Guarded Runner Stdout"] = _to_text(exc.stdout)
        timed_out["Guarded Runner Stderr"] = _to_text(exc.stderr)
        return timed_out, "timeout"

    if completed.returncode != 0:
        failed = with_default_translation_fields(record)
        failed["Translation Pipeline Error"] = f"single-record subprocess exited with {completed.returncode}"
        failed["Guarded Runner Stdout"] = completed.stdout
        failed["Guarded Runner Stderr"] = completed.stderr
        return failed, "failed"

    records = _load_records(single_output)
    if not records:
        failed = with_default_translation_fields(record)
        failed["Translation Pipeline Error"] = "single-record subprocess produced no records"
        return failed, "failed"
    return records[0], "completed"


def run_guarded(
    *,
    data_path: Path,
    output_path: Path,
    model: str,
    request_timeout: int,
    max_tokens: int,
    max_repair_attempts: int,
    record_timeout: int,
    resume: bool,
    skip_secure_validation: bool,
    skip_insecure_validation: bool,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    records = _load_records(data_path)
    if limit is not None:
        records = records[:limit]
    output_by_id: dict[str, dict[str, Any]] = {}
    if resume and output_path.exists():
        output_by_id = {str(record.get("ID")): record for record in _load_records(output_path)}

    package_dir = Path(__file__).resolve().parents[1]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_path.parent / f"{output_path.stem}.guarded_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    for index, record in enumerate(records, start=1):
        record_id = str(record.get("ID"))
        existing = output_by_id.get(record_id)
        if (
            resume
            and existing is not None
            and is_validation_complete(
                existing,
                skip_secure=skip_secure_validation,
                skip_insecure=skip_insecure_validation,
            )
        ):
            print(f"[{index}/{len(records)}] {record_id}: already complete, skipping", flush=True)
            continue

        print(f"[{index}/{len(records)}] {record_id}: validating with {record_timeout}s record timeout", flush=True)
        single_input = temp_dir / f"{index:04d}.input.json"
        single_output = _record_output_path(output_path, record_id)
        started = time.monotonic()
        updated, status = _run_single_record(
            record=existing or record,
            package_dir=package_dir,
            single_input=single_input,
            single_output=single_output,
            model=model,
            request_timeout=request_timeout,
            max_tokens=max_tokens,
            max_repair_attempts=max_repair_attempts,
            record_timeout=record_timeout,
            skip_secure_validation=skip_secure_validation,
            skip_insecure_validation=skip_insecure_validation,
        )
        elapsed = time.monotonic() - started
        print(f"[{index}/{len(records)}] {record_id}: {status} in {elapsed:.1f}s", flush=True)
        output_by_id[record_id] = updated
        merged = _merge_by_id(records, output_by_id)
        safe_write_json(output_path, merged)
        write_summary(output_path, merged)

    final_records = _merge_by_id(records, output_by_id)
    safe_write_json(output_path, final_records)
    write_summary(output_path, final_records)
    return final_records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate translated records one at a time with an outer timeout guard.")
    parser.add_argument("--data-path", required=True, type=Path)
    parser.add_argument("--output-path", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--request-timeout", type=int, default=180)
    parser.add_argument("--max-tokens", type=int, default=65536)
    parser.add_argument("--max-repair-attempts", type=int, default=1)
    parser.add_argument("--record-timeout", type=int, default=600)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-secure-validation", action="store_true")
    parser.add_argument("--skip-insecure-validation", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    records = run_guarded(
        data_path=args.data_path,
        output_path=args.output_path,
        model=args.model,
        request_timeout=args.request_timeout,
        max_tokens=args.max_tokens,
        max_repair_attempts=args.max_repair_attempts,
        record_timeout=args.record_timeout,
        resume=args.resume,
        skip_secure_validation=args.skip_secure_validation,
        skip_insecure_validation=args.skip_insecure_validation,
        limit=args.limit,
    )
    print(f"Wrote {len(records)} records to {args.output_path}")


if __name__ == "__main__":
    main()

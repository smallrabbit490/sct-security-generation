from __future__ import annotations

import argparse
import json
from pathlib import Path

from .quality_metrics import (
    compute_quality_metrics,
    load_records,
    read_jsonl,
    tool_static_warnings,
    write_quality_report,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _limit_records(records: dict[tuple[str, str], list[dict]], limit: int) -> dict[tuple[str, str], list[dict]]:
    if limit <= 0:
        return records
    return {key: value[:limit] for key, value in records.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute production-readiness metrics for Secure Python/C++/Go code.")
    parser.add_argument("--dataset-root", type=Path, default=Path("SecEvoBasePlus"))
    parser.add_argument("--validation-results", type=Path, required=True, help="Docker revalidation results.jsonl")
    parser.add_argument("--output-root", type=Path, default=Path("translation_work/quality_metrics/latest"))
    parser.add_argument("--subsets", nargs="+", default=["Base", "Plus"], choices=["Base", "Plus"])
    parser.add_argument("--languages", nargs="+", default=["python", "cpp", "go"], choices=["python", "cpp", "go", "java"])
    parser.add_argument("--limit", type=int, default=0, help="Optional per-language per-subset sample limit for smoke tests.")
    parser.add_argument(
        "--sast-mode",
        choices=["lightweight", "tools"],
        default="tools",
        help="Use language SAST tools when available, or force lightweight fallback rules.",
    )
    parser.add_argument(
        "--growth-baseline",
        choices=["none", "python_source", "same_language_reference"],
        default="none",
        help=(
            "Reference used by GrowthPenalty. Use none for finalized SecEvoBasePlus dataset scoring; "
            "python_source for direct Python-to-target generated outputs; same_language_reference only "
            "when rows include an explicit same-language reference field."
        ),
    )
    args = parser.parse_args()

    records = load_records(args.dataset_root, args.subsets, args.languages)
    records = _limit_records(records, args.limit)
    validation_rows = read_jsonl(args.validation_results)
    warning_provider = tool_static_warnings if args.sast_mode == "tools" else None
    rows, summary = compute_quality_metrics(
        records,
        validation_rows,
        warning_provider=warning_provider,
        growth_baseline_mode=args.growth_baseline,
    )

    args.output_root.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_root / "quality_rows.json", rows)
    _write_json(args.output_root / "quality_summary.json", summary)
    report = write_quality_report(args.output_root, rows, summary, growth_baseline_mode=args.growth_baseline)

    print(f"Wrote rows: {args.output_root / 'quality_rows.json'}")
    print(f"Wrote summary: {args.output_root / 'quality_summary.json'}")
    print(f"Wrote report: {report}")


if __name__ == "__main__":
    main()

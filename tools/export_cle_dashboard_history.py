"""Export a compact, redacted CLE dashboard history snapshot.

This reads local translation_work artifacts and writes only summary-level data that
can be reviewed in Git. It never copies generated code, prompts, model responses,
long logs, caches, or per-task trace rows.
"""
from __future__ import annotations

import hashlib
import json
import re
import argparse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SAFE_FILES = {
    "run_metadata.json",
    "status.json",
    "summary.json",
    "cost.json",
    "final_eval_summary.json",
    "tree_change.json",
    "tree_growth.json",
}
# These files are used only to count dashboard-visible rows, never copied.
ROW_COUNTS = {
    "phase1_results.jsonl": "phase1_rows",
    "rounds.jsonl": "round_rows",
    "audit_detail.jsonl": "audit_rows",
    "gate_records.jsonl": "gate_rows",
    "final_eval.jsonl": "final_eval_rows",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def json_load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def row_count(path: Path) -> int:
    try:
        return sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError):
        return 0


def redact(value):
    """Keep dashboard summaries while removing machine paths and free-form text."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key.lower() in {"args", "prompt", "raw", "response", "generated_code", "code", "trace", "error_detail"}:
                continue
            out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(x) for x in value[:100]]
    if isinstance(value, str):
        value = re.sub(r"[A-Za-z]:[/\\][^\n\r]*", "<local-path>", value)
        return value[:1000]
    return value


def export_run(run: Path) -> dict:
    files = [p for p in run.rglob("*") if p.is_file()]
    record = {
        "run_name": run.name,
        "source": f"translation_work/sct_runs/{run.name}",
        "file_count": len(files),
        "total_bytes": sum(p.stat().st_size for p in files),
        "dashboard_bytes": sum(p.stat().st_size for p in files if p.name in SAFE_FILES or p.name in ROW_COUNTS),
        "dashboard_rows": {key: row_count(run / filename) for filename, key in ROW_COUNTS.items()},
        "safe_artifacts": {},
        "omitted": [
            "generated code and candidate payloads",
            "prompts and raw model responses",
            "long progress/error logs",
            "embedding/vector caches and temporary files",
        ],
    }
    for filename in sorted(SAFE_FILES):
        path = run / filename
        if not path.exists() or not path.is_file():
            continue
        record["safe_artifacts"][filename] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "content": redact(json_load(path)),
        }
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "translation_work" / "sct_runs")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "cle_web_history_20261015")
    args = parser.parse_args()
    source = args.source.resolve()
    out = args.out.resolve()
    if not source.exists():
        raise SystemExit(f"missing source directory: {source}")
    runs = [export_run(d) for d in sorted(source.iterdir()) if d.is_dir() and d.name.lower().startswith("cle")]
    total = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "translation_work/sct_runs",
        "run_count": len(runs),
        "total_files": sum(r["file_count"] for r in runs),
        "total_bytes": sum(r["total_bytes"] for r in runs),
        "dashboard_bytes": sum(r["dashboard_bytes"] for r in runs),
        "runs": runs,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "runs_summary.json").write_text(json.dumps(total, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"files": [], "source": total["source"], "run_count": total["run_count"], "total_bytes": total["total_bytes"], "dashboard_bytes": total["dashboard_bytes"]}
    for path in sorted(out.glob("*.json")):
        manifest["files"].append({"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("run_count", "total_bytes", "dashboard_bytes", "files")}, ensure_ascii=False))


if __name__ == "__main__":
    main()

"""汇总冻结 CLE prompt 消融的逐任务配对结果。"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


SETS = ("Base_mstar", "Plus_mstar", "H_pass")


def _rows(path: Path) -> dict[str, dict]:
    return {str(row["task_id"]): row for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() for row in (json.loads(line),)}


def _mcnemar_exact(win: int, loss: int) -> float:
    discordant = win + loss
    if not discordant:
        return 1.0
    tail = sum(math.comb(discordant, k) for k in range(min(win, loss) + 1))
    return min(1.0, 2.0 * tail / (2 ** discordant))


def build_report(root: Path) -> dict:
    manifest = json.loads((root / "prompt_matrix_manifest.json").read_text(encoding="utf-8"))
    results = []
    p_values = []
    for subset in SETS:
        baseline_path = root / "P00" / "validation_runs" / subset / "rows.jsonl"
        if not baseline_path.exists():
            continue
        baseline = _rows(baseline_path)
        for profile_id, profile_meta in manifest["profiles"].items():
            path = root / profile_id / "validation_runs" / subset / "rows.jsonl"
            if profile_id == "P00" or not path.exists():
                continue
            variant = _rows(path)
            if set(variant) != set(baseline):
                raise ValueError(f"task_id mismatch: {profile_id}/{subset}")
            win = sum(bool(variant[k]["joint_pass"]) and not baseline[k]["joint_pass"] for k in baseline)
            loss = sum(bool(baseline[k]["joint_pass"]) and not variant[k]["joint_pass"] for k in baseline)
            both = sum(bool(baseline[k]["joint_pass"]) and bool(variant[k]["joint_pass"]) for k in baseline)
            value = {"subset": subset, "profile": profile_id, "n": len(baseline),
                     "baseline_joint": both + loss, "variant_joint": both + win,
                     "wins": win, "losses": loss, "both_pass": both,
                     "delta_joint": win - loss, "p_exact": _mcnemar_exact(win, loss),
                     "prompt_sha256": profile_meta["prompt_sha256"]}
            results.append(value)
            p_values.append((value["p_exact"], len(results) - 1))
    count = len(p_values)
    adjusted = 0.0
    for rank, (p, index) in enumerate(sorted(p_values)):
        adjusted = max(adjusted, min(1.0, p * (count - rank)))
        results[index]["p_holm"] = adjusted
    return {"schema": "cle-prompt-paired-report-v1", "frozen_sha256": manifest["frozen_sha256"],
            "pool_manifest_sha256": manifest["pool_manifest_sha256"],
            "test": "two-sided exact McNemar; Holm over all reported contrasts",
            "comparisons": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.out)
    (args.out / "paired_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# CLE Prompt 消融配对结果", "", "同任务比较 P00；p 值为双侧精确 McNemar 检验，跨全部比较做 Holm 校正。", "",
             "| 数据集 | 变体 | n | P00 Joint | 变体 Joint | 改善 | 退步 | 差值 | Holm p |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in report["comparisons"]:
        lines.append(f"| {row['subset']} | {row['profile']} | {row['n']} | {row['baseline_joint']} | "
                     f"{row['variant_joint']} | {row['wins']} | {row['losses']} | {row['delta_joint']} | {row['p_holm']:.4g} |")
    (args.out / "paired_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

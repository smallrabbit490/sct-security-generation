"""汇总 CLE 消融的训练中间过程、冻结资格和最终评测结果。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .design import ARM_SPECS
from .metrics import summarize_matrix


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collect(root: Path, arms: list[str]) -> tuple[dict, list[dict]]:
    overview, rows = {}, []
    for arm_id in arms:
        run = root / arm_id
        spec = json.loads((run / "arm_spec.json").read_text(encoding="utf-8")) if (run / "arm_spec.json").exists() else {"arm": arm_id}
        summary = json.loads((run / "summary.json").read_text(encoding="utf-8")) if (run / "summary.json").exists() else {}
        freeze = json.loads((run / "frozen" / "freeze_metadata.json").read_text(encoding="utf-8")) if (run / "frozen" / "freeze_metadata.json").exists() else {}
        overview[arm_id] = {"spec": spec, "training_summary": summary, "freeze": freeze,
                            "run_status": json.loads((run / "status.json").read_text(encoding="utf-8")) if (run / "status.json").exists() else {"status": "not_run"}}
        frozen_eval = run / "frozen_evaluation"
        for dataset, directory in (("Base", frozen_eval / "validation_runs" / "Base_mstar"), ("Plus", frozen_eval / "validation_runs" / "Plus_mstar"), ("H_pass", frozen_eval / "H_pass")):
            for raw in _read_jsonl(directory / "rows.jsonl"):
                validation = raw.get("validation") or raw.get("raw", {}).get("evidence") or {}
                evidence = raw.get("evidence") or raw.get("raw", {}).get("evidence") or {}
                functional = raw.get("functional") if "functional" in raw else validation.get("functional") == "pass" or evidence.get("functional", {}).get("status") == "pass"
                security = raw.get("security") if "security" in raw else validation.get("security") == "pass" or evidence.get("security", {}).get("status") == "pass"
                measured = raw.get("measured", True)
                rows.append({"arm": arm_id, "dataset": dataset, "task_id": str(raw.get("task_id")), "measured": measured,
                             "functional": functional, "security": security, "joint": bool(raw.get("joint") or raw.get("joint_pass") or validation.get("passed")),
                             "usage": raw.get("usage") or {}, "feedback_channel": "disabled"})
    return overview, rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", choices=tuple(ARM_SPECS), default=list(ARM_SPECS))
    args = parser.parse_args()
    root = args.matrix_root.resolve()
    overview, rows = collect(root, args.arms)
    comparisons = [(f"C2-{i}", f"C2-{i + 1}") for i in range(5)] + [(f"C3-{i}", f"C3-{i + 1}") for i in range(3)]
    result = {"schema": "cle-ablation-report-v1", "arms": overview, "final_evaluation": summarize_matrix(rows, comparisons=comparisons),
              "reporting_rules": {"D_gate": "training diagnostic, never independent held-out", "H_pass": "held-out final CLE evaluation", "Base_Plus": "external final tests; feedback disabled", "significance": "only call an increase significant when Holm-adjusted paired McNemar supports it"}}
    (root / "matrix_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# CLE 细粒度消融汇报", "", "| 臂 | 阶段 | 上游 | 运行状态 | 冻结 active | 候选数 |", "|---|---|---|---|---:|---:|"]
    for arm_id, item in overview.items():
        freeze = item["freeze"]
        status = item['run_status'].get('status', 'not_run')
        if status == 'blocked' and item['run_status'].get('reason'):
            status = f"blocked: {item['run_status']['reason']}"
        lines.append(f"| {arm_id} | {item['spec'].get('stage', '')} | {item['spec'].get('parent_arm') or '—'} | {status} | {freeze.get('active_count', '—')} | {freeze.get('candidate_count', '—')} |")
    lines += ["", "Base/Plus 为外部最终测试；H_pass 为 300 条留出 CLE 最终评测；D_gate 只用于训练侧门控诊断。", "每个性能比较保留 Function、Secure、Joint、缺测、调用数、token 用量、冻结库 SHA-256、数据池 SHA-256 与配对 McNemar/Holm 结果。"]
    if not rows:
        lines += ["", "当前尚无冻结评测逐任务结果；本文件仅记录实验计划、运行状态和阻塞原因。"]
    (root / "matrix_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

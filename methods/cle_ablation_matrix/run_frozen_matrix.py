"""对每个独立 CLE 臂运行冻结后的 Base/Plus/H_pass 只读评测。

该入口负责数据规模、反馈禁用和结果汇总的审计；生成与验证委托给现有冻结评测器。
H_pass 默认读取用户指定的 300 条 Python 留出行，不把其反馈写入任何经验库。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from .design import ARM_SPECS, get_arm
from .metrics import summarize_matrix
from .pool_manifest import select_pool_rows, validate_manifest

ROOT = Path(__file__).resolve().parents[2]


def _write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def load_h_pass_rows(manifest_path: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    rows = _load_tasks(0)
    validate_manifest(manifest, rows)
    return select_pool_rows(rows, manifest, ("H_pass",))


def evaluate_h_pass(run: Path, tasks: list[dict], *, model: str, workers: int) -> list[dict]:
    """Phase 4 只读评测 H_pass；不提炼、不门控、也不更新经验库。"""
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.closed_loop import CleRunner
    from methods.sct_trajectory.error_ledger import ErrorLedger
    from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode
    from methods.sct_trajectory.run_closed_loop import _requester

    memory_path = run / "frozen" / "m_star.jsonl"
    nodes = [SecurityInvariantNode.from_dict(json.loads(line)) for line in memory_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    tree = HskTree()
    for node in nodes:
        if node.status == "retired":
            continue
        tree.insert_node(node)
    runner = CleRunner(_requester(model, 90, 4096, max(1, workers)), tree, ErrorLedger(), workers=workers,
                       ablation=get_config("A7"), context_pipeline=True, retrieval_mode="flat_llm")
    runner.experience_pool.extend(nodes)
    result = runner.final_evaluate(tasks)
    rows = []
    for row in result["rows"]:
        # final_evaluate returns normalized functional/security status strings,
        # unlike local_codeseceval rows which nest them under evidence.
        functional_status = row.get("functional", "")
        security_status = row.get("security", "")
        measured = functional_status in {"pass", "fail"} and security_status in {"pass", "fail"}
        rows.append({"arm": run.name, "dataset": "H_pass", "task_id": str(row.get("task_id")),
                     "measured": measured,
                     "functional": functional_status == "pass",
                     "security": security_status == "pass",
                     "joint": row.get("state") == "A",
                     "raw": row,
                     "feedback_channel": "disabled"})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix-root", type=Path, required=True)
    parser.add_argument("--pool-manifest", type=Path, required=True)
    parser.add_argument("--arms", nargs="+", choices=tuple(ARM_SPECS), required=True)
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    h_pass = load_h_pass_rows(args.pool_manifest.resolve())
    if len(h_pass) != 300:
        raise SystemExit(f"H_pass must contain 300 rows, got {len(h_pass)}")
    plan = {"schema": "cle-ablation-frozen-matrix-v1", "feedback_channel": "disabled",
            "datasets": {"Base": {"count": 115, "role": "final_external_test"},
                         "Plus": {"count": 140, "role": "final_external_test"},
                         "H_pass": {"count": 300, "role": "held_out_final_cle_evaluation"}}, "arms": {}}
    for arm_id in args.arms:
        arm = get_arm(arm_id)
        run = args.matrix_root.resolve() / arm_id
        if not (run / "frozen" / "m_star.jsonl").is_file():
            plan["arms"][arm_id] = {"status": "blocked", "reason": "missing_independent_frozen_library"}
            continue
        out = run / "frozen_evaluation"
        plan["arms"][arm_id] = {"status": "ready", "cle_run": str(run), "out": str(out), "h_pass_rows": len(h_pass), "freeze_policy": arm.freeze_policy}
        if args.execute:
            command = [sys.executable, "-m", "methods.sct_trajectory.run_local_frozen_eval", "--cle-run", str(run), "--out", str(out), "--subsets", "Base", "Plus", "--model", args.model, "--workers", str(args.workers)]
            subprocess.run(command, cwd=str(ROOT), check=True)
            h_rows = evaluate_h_pass(run, h_pass, model=args.model, workers=args.workers)
            _write_jsonl(out / "H_pass" / "rows.jsonl", h_rows)
            (out / "H_pass" / "summary.json").write_text(json.dumps(
                summarize_matrix(h_rows)["arms"][run.name]["H_pass"], ensure_ascii=False, indent=2), encoding="utf-8")
    (args.matrix_root.resolve() / "frozen_matrix_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

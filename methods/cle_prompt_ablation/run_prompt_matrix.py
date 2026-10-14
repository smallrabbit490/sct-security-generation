"""在同一份冻结 CLE 经验库上运行 P00-P24 prompt 消融。

评测只读 frozen/m_star.jsonl，Base/Plus/H_pass 结果不会进入任何经验库或门控。
默认 16 并发，输出遵循 translation_work/validation_runs 的运行区规范。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from methods.cle_prompt_ablation.prompt_profiles import PROFILES, get_profile, profile_payload, profile_sha256
from methods.sct_lifecycle_replay.local_codeseceval import evaluate_python_tasks, load_codeseceval_python, load_frozen_run


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _summary(rows: list[dict]) -> dict:
    total = len(rows)
    functional = sum(bool((r.get("evidence") or {}).get("functional", {}).get("status") == "pass") for r in rows)
    secure = sum(bool((r.get("evidence") or {}).get("security", {}).get("status") == "pass") for r in rows)
    joint = sum(bool(r.get("joint_pass")) for r in rows)
    errors = sum(bool(r.get("error")) for r in rows)
    states: dict[str, int] = {}
    for row in rows:
        f = (row.get("evidence") or {}).get("functional", {}).get("status")
        s = (row.get("evidence") or {}).get("security", {}).get("status")
        state = ("unmeasured" if f not in {"pass", "fail"} or s not in {"pass", "fail"}
                 else "A" if f == s == "pass" else "B" if f == "pass" else "C" if s == "pass" else "D")
        row["four_state"] = state
        states[state] = states.get(state, 0) + 1
    return {"total": total, "functional": functional, "secure": secure, "joint": joint,
            "functional_rate": round(functional / total, 6) if total else 0,
            "secure_rate": round(secure / total, 6) if total else 0,
            "joint_rate": round(joint / total, 6) if total else 0,
            "generation_errors": errors, "error_types": dict(Counter(str(r.get("error")) for r in rows if r.get("error"))),
            "unmeasured": states.get("unmeasured", 0), "four_state": states,
            "feedback_channel": "disabled", "backend": "local_python_no_docker"}


def _load_h_pass(manifest_path: Path) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    from methods.cle_ablation_matrix.pool_manifest import select_pool_rows, validate_manifest
    rows = _load_tasks(0)
    validate_manifest(manifest, rows)
    return select_pool_rows(rows, manifest, ("H_pass",))


def _normalise_h_pass_row(row: dict, profile_id: str) -> dict:
    """把 CLE 四阶段终态映射为统一证据，未执行的测试保持未测量。"""
    functional = row.get("functional") or "unmeasured"
    security = row.get("security") or "unmeasured"
    return {"task_id": str(row.get("task_id")), "generated_code": row.get("code", ""),
            "evidence": {"functional": {"status": functional}, "security": {"status": security}},
            "joint_pass": row.get("state") == "A", "error": row.get("error"),
            "pipeline_error": row.get("pipeline_error"), "workflow_completed": row.get("workflow_completed"),
            "retrieved_ids": row.get("retrieved_ids", []),
            "feedback_channel": "disabled", "prompt_profile": profile_id}


def _evaluate_h_pass(cle_run: Path, tasks: list[dict], profile, model: str, workers: int) -> list[dict]:
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.closed_loop import CleRunner
    from methods.sct_trajectory.error_ledger import ErrorLedger
    from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode
    from methods.sct_trajectory.run_closed_loop import _requester

    nodes = [SecurityInvariantNode.from_dict(json.loads(line)) for line in (cle_run / "frozen/m_star.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    tree = HskTree()
    for node in nodes:
        if node.status != "retired":
            tree.insert_node(node)
    runner = CleRunner(_requester(model, 90, 4096, max(1, workers)), tree, ErrorLedger(), workers=workers,
                       ablation=get_config("A7"), context_pipeline=False, retrieval_mode="flat_llm")
    runner.experience_pool.extend(nodes)
    result = runner.final_evaluate(tasks, prompt_profile=profile)
    return [_normalise_h_pass_row(row, profile.profile_id) for row in result["rows"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cle-run", type=Path, required=True)
    parser.add_argument("--pool-manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--profiles", nargs="+", default=list(PROFILES), choices=tuple(PROFILES))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cle_run = args.cle_run.resolve()
    frozen_nodes, freeze_meta = load_frozen_run(cle_run)
    memory = []
    for node in frozen_nodes:
        principle = node.get("positive_principle") or node.get("high_level_invariant") or node.get("principle")
        if principle and node.get("status") not in {"retired", "rejected", "demoted"}:
            memory.append({**node, "id": node.get("invariant_id", ""), "principle": principle})
    if not memory:
        raise SystemExit("no retrievable cards in frozen M*")
    memory_bytes = (cle_run / "frozen/m_star.jsonl").read_bytes()
    frozen_sha = hashlib.sha256(memory_bytes).hexdigest()
    h_pass = _load_h_pass(args.pool_manifest.resolve())
    if len(h_pass) != 300:
        raise SystemExit(f"H_pass must contain 300 rows, got {len(h_pass)}")
    if args.limit:
        h_pass = h_pass[:args.limit]
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    from methods.sct_trajectory.run_local_frozen_eval import _requester as local_requester
    requester = local_requester(args.model, 90)
    pool_sha = hashlib.sha256(args.pool_manifest.resolve().read_bytes()).hexdigest()
    manifest = {"schema": "cle-prompt-ablation-v1", "cle_run": str(cle_run), "frozen_sha256": frozen_sha,
                "freeze_metadata_sha256": hashlib.sha256(json.dumps(freeze_meta, sort_keys=True).encode()).hexdigest(),
                "pool_manifest_sha256": pool_sha, "model": args.model, "limit": args.limit,
                "feedback_channel": "disabled", "workers": args.workers, "profiles": {}}
    previous_path = root / "prompt_matrix_manifest.json"
    if previous_path.exists() and args.execute:
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        for key in ("frozen_sha256", "pool_manifest_sha256", "model", "limit", "workers"):
            if previous.get(key) != manifest.get(key):
                raise SystemExit(f"resume manifest mismatch: {key}")
    def save_manifest() -> None:
        _write_json(previous_path, manifest)

    for profile_id in args.profiles:
        profile = get_profile(profile_id)
        run = root / profile_id
        run.mkdir(parents=True, exist_ok=True)
        _write_json(run / "prompt_profile.json", {"profile": profile_payload(profile), "sha256": profile_sha256(profile)})
        manifest["profiles"][profile_id] = {"status": "planned", "prompt_sha256": profile_sha256(profile), "out": str(run)}
        save_manifest()
        if not args.execute:
            continue
        for subset in ("Base", "Plus"):
            dataset = ROOT / "data/SecEvoBasePlus" / subset / f"Python_{subset}.json"
            tasks = load_codeseceval_python(dataset)
            if args.limit:
                tasks = tasks[:args.limit]
            subset_dir = run / "validation_runs" / f"{subset}_mstar"
            rows_path = subset_dir / "rows.jsonl"
            if rows_path.exists() and (subset_dir / "summary.json").exists():
                rows = _read_jsonl(rows_path)
                if len(rows) != len(tasks):
                    raise SystemExit(f"incomplete existing rows: {rows_path}")
            else:
                rows = evaluate_python_tasks(tasks, requester, memory,
                                             timeout=60, retries=1, workers=args.workers, prompt_profile=profile)
                for row in rows:
                    row["subset"] = subset
                _summary(rows)
                _write_jsonl(rows_path, rows)
                _write_json(subset_dir / "summary.json", _summary(rows))
            manifest["profiles"][profile_id][subset] = "completed"
            save_manifest()
        h_dir = run / "validation_runs" / "H_pass"
        if (h_dir / "rows.jsonl").exists() and (h_dir / "summary.json").exists():
            h_rows = _read_jsonl(h_dir / "rows.jsonl")
            if len(h_rows) != len(h_pass):
                raise SystemExit(f"incomplete existing rows: {h_dir}")
        else:
            h_rows = _evaluate_h_pass(cle_run, h_pass, profile, args.model, args.workers)
            _summary(h_rows)
            _write_jsonl(h_dir / "rows.jsonl", h_rows)
            _write_json(h_dir / "summary.json", _summary(h_rows))
        manifest["profiles"][profile_id]["H_pass"] = "completed"
        manifest["profiles"][profile_id]["status"] = "completed"
        save_manifest()
    save_manifest()


if __name__ == "__main__":
    main()

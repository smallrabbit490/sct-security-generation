"""CLE 细粒度训练矩阵编排器。

默认只生成并审计命令；传入 ``--execute`` 才启动真实 API 运行。每个臂使用独立
输出目录，独立生成经验池和冻结库，不复用已有 CLE 运行目录。
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import traceback
from pathlib import Path

from .design import ARM_SPECS, get_arm, validate_design
from .freeze_policy import audit_existing_freeze, qualify_freeze
from .pool_manifest import build_manifest, validate_manifest

ROOT = Path(__file__).resolve().parents[2]
PLT_DATA = ROOT / "data/external/secodeplt/secodeplt/data.json"
PLT_MANIFEST = ROOT / "data/external/secodeplt/derived_metadata/family_manifest.json"


def load_training_rows() -> list[dict]:
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    return _load_tasks(0)


def ensure_pool_manifest(path: Path) -> dict:
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
    else:
        manifest = build_manifest(load_training_rows())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    validate_manifest(manifest, load_training_rows())
    return manifest


def command_for_arm(spec, *, out: Path, pool_manifest: Path, model: str, workers: int, max_tokens: int) -> list[str]:
    c = spec.components
    command = [sys.executable, "-m", "methods.sct_trajectory.run_closed_loop", "--out", str(out),
               "--pool-manifest", str(pool_manifest), "--model", model, "--workers", str(workers),
               "--phase3-workers", str(workers), "--max-inflight", str(workers),
               "--max-tokens", str(max_tokens), "--gate-mode", "global"]
    if c.get("context_pipeline") or spec.arm_id in {"C1-2", "C1-3", "C2-3", "C2-4", "C2-5"}:
        command.append("--context-pipeline")
    if c.get("inject_prev_evidence"):
        command.append("--inject-prev-evidence")
    if c.get("internal_checks"):
        command.append("--internal-checks")
    if c.get("branch_count"):
        command += ["--branch-count", str(c["branch_count"])]
    if c.get("repairs") is not None:
        command += ["--repairs", str(c["repairs"])]
    if c.get("retrieval_mode"):
        command += ["--retrieval-mode", str(c["retrieval_mode"])]
    if c.get("anti_overdefense"):
        command += ["--anti-overdefense", str(c["anti_overdefense"])]
    if spec.stage == "c3":
        # C3-0/1 在每轮候选边界冻结，C3-2/3 在所有演化轮后做全局门控。
        command += ["--gate-mode", "candidate" if spec.arm_id in {"C3-0", "C3-1"} else "global"]
    if spec.stage == "c1" or spec.arm_id == "C2-0":
        # 冷启动/C2-0 只保留 Phase1；不能让默认轮数偷偷引入 replay 演化。
        command += ["--rounds", "0", "--replay-limit", "0"]
    return command


def prepare_arm(arm_id: str, *, root_out: Path, pool_manifest: Path, model: str, workers: int, max_tokens: int) -> dict:
    spec = get_arm(arm_id)
    arm_out = root_out / arm_id
    arm_out.mkdir(parents=True, exist_ok=True)
    command = command_for_arm(spec, out=arm_out, pool_manifest=pool_manifest, model=model, workers=workers, max_tokens=max_tokens)
    supported = {"context_pipeline", "inject_prev_evidence", "internal_checks", "branch_count",
                 "repairs", "retrieval_mode", "anti_overdefense"}
    unsupported = sorted(key for key in spec.components if key not in supported and key not in {
        "memory", "analysis", "planning", "codegen", "extract", "repair", "replay", "retrieval",
        "distillation", "reanalyze_after_retrieval", "failure_evidence", "hsk_tree", "quality_gate",
        "independent_validity", "h_pass_regression", "format_source_checks"})
    metadata = {"arm": spec.arm_id, "stage": spec.stage, "parent_arm": spec.parent_arm,
                "components": dict(spec.components), "train_pools": list(spec.train_pools),
                "freeze_policy": spec.freeze_policy, "purpose": spec.purpose,
                "unsupported_cli_components": unsupported,
                "pool_manifest": str(pool_manifest), "command": command,
                "evaluation_sets": list(spec.evaluation_sets), "feedback_channel": "disabled"}
    (arm_out / "arm_spec.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"arm": arm_id, "out": str(arm_out), "command": command, "shell": shlex.join(command)}


def main() -> None:
    validate_design()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arms", nargs="+", choices=tuple(ARM_SPECS),
                        default=[name for name in ARM_SPECS if name != "C1-0"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pool-manifest", type=Path, default=ROOT / "translation_work/sct_runs/cle_ablation_matrix/pool_manifest.json")
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / "translation_work").resolve()):
        parser.error("--out must be inside translation_work")
    manifest = ensure_pool_manifest(args.pool_manifest.resolve())
    plans = [prepare_arm(arm, root_out=out, pool_manifest=args.pool_manifest.resolve(), model=args.model, workers=args.workers, max_tokens=args.max_tokens) for arm in args.arms]
    (out / "matrix_plan.json").write_text(json.dumps({"arms": plans, "pool_manifest": manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.execute:
        for plan in plans:
            # 底层 runner 有“输出目录必须为空”的证据保护；arm_spec 是矩阵编排元数据，
            # 不能让它被误认为已有运行产物。启动前暂存，完成后恢复到臂目录。
            arm_spec_path = Path(plan["out"]) / "arm_spec.json"
            pending_path = out / f".{plan['arm']}.arm_spec.pending.json"
            if arm_spec_path.exists():
                arm_spec_path.replace(pending_path)
            error = None
            try:
                subprocess.run(plan["command"], cwd=str(ROOT), check=True)
            except Exception as exc:
                error = exc
                (Path(plan["out"]) / "matrix_error.json").write_text(json.dumps({
                    "arm": plan["arm"], "error_type": type(exc).__name__,
                    "error": str(exc)[:2000], "traceback": traceback.format_exc(),
                    "status": "failed", "continue_on_error": True,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
            finally:
                if pending_path.exists():
                    pending_path.replace(arm_spec_path)
            if error:
                continue
            arm = get_arm(plan["arm"])
            try:
                pool_path = Path(plan["out"]) / "experience_pool.jsonl"
                if not pool_path.is_file():
                    raise RuntimeError(f"missing independent experience pool: {pool_path}")
                frozen_dir = Path(plan["out"]) / "frozen"
                pool_sha256 = __import__("hashlib").sha256(pool_path.read_bytes()).hexdigest()
                if (frozen_dir / "m_star.jsonl").is_file():
                    audit_existing_freeze(pool_path, frozen_dir, policy=arm.freeze_policy,
                                          expected_pool_sha256=pool_sha256)
                else:
                    qualify_freeze(pool_path, frozen_dir, policy=arm.freeze_policy,
                                   expected_pool_sha256=pool_sha256)
            except Exception as exc:
                (Path(plan["out"]) / "matrix_error.json").write_text(json.dumps({
                    "arm": plan["arm"], "error_type": type(exc).__name__,
                    "error": str(exc)[:2000], "traceback": traceback.format_exc(),
                    "status": "failed", "continue_on_error": True,
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                continue


if __name__ == "__main__":
    main()

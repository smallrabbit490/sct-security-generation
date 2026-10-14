"""在现有消融结束后串行启动完整 CLE 与冻结 prompt 矩阵。"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
POOL = ROOT / "translation_work/sct_runs/cle_ablation_matrix/pool_manifest.json"
CLE = ROOT / "translation_work/sct_runs/cle_prompt_full_20260929"
OUT = ROOT / "translation_work/validation_runs/cle_prompt_ablation_full_20260929"
STATE = OUT / "launcher_state.json"


def state(stage: str, **details) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"stage": stage, "updated_at": datetime.now().isoformat(),
                                 **details}, ensure_ascii=False, indent=2), encoding="utf-8")


def run(command: list[str], log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write("\n" + datetime.now().isoformat() + " " + " ".join(command) + "\n")
        handle.flush()
        result = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}); see {log}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-pid", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.wait_pid:
            state("waiting_for_existing_ablation", wait_pid=args.wait_pid)
            while psutil.pid_exists(args.wait_pid):
                time.sleep(30)
        existing = ROOT / "translation_work/sct_runs/cle_ablation_matrix_20260929_run2"
        matrix_status = existing / "matrix_status.json"
        if matrix_status.exists():
            previous = json.loads(matrix_status.read_text(encoding="utf-8"))
            if previous.get("status") == "failed":
                raise RuntimeError("existing structural ablation failed; inspect before sharing API capacity")
        state("training_cle", cle_run=str(CLE))
        if not (CLE / "frozen/m_star.jsonl").exists():
            run([sys.executable, "tools/vhdx_watchdog.py", "--label", "cle_prompt_full_20260929",
                 "--interval", "2", "--max-containers", "16", "--",
                 sys.executable, "-m", "methods.sct_trajectory.run_closed_loop",
                 "--out", str(CLE), "--pool-manifest", str(POOL),
                 "--model", "deepseek-v3.2", "--workers", "16", "--phase3-workers", "16",
                 "--max-inflight", "16", "--selector-max-inflight", "16",
                 "--max-tokens", "4096", "--timeout", "90", "--validation-timeout", "20",
                 "--gate-mode", "global", "--context-pipeline", "--inject-prev-evidence",
                 "--internal-checks", "--retrieval-mode", "semantic_llm",
                 "--rounds", "3", "--replay-limit", "240", "--batch-size", "96"],
                OUT / "cle_training.log")
        status = json.loads((CLE / "status.json").read_text(encoding="utf-8"))
        if status.get("status") != "completed":
            raise RuntimeError("CLE did not complete")
        frozen = CLE / "frozen/m_star.jsonl"
        digest = hashlib.sha256(frozen.read_bytes()).hexdigest()
        (CLE / "frozen/freeze_metadata.json").write_text(json.dumps({
            "schema": "cle-prompt-full-freeze-v1", "m_star_sha256": digest,
            "feedback_channel": "disabled", "pool_manifest_sha256": hashlib.sha256(POOL.read_bytes()).hexdigest(),
        }, indent=2), encoding="utf-8")
        state("evaluating_prompts", cle_run=str(CLE), frozen_sha256=digest)
        run([sys.executable, "-m", "methods.cle_prompt_ablation.run_prompt_matrix",
             "--cle-run", str(CLE), "--pool-manifest", str(POOL), "--out", str(OUT),
             "--model", "deepseek-v3.2", "--workers", "16", "--execute"], OUT / "prompt_matrix.log")
        run([sys.executable, "-m", "methods.cle_prompt_ablation.report", "--out", str(OUT)],
            OUT / "paired_report.log")
        state("completed", cle_run=str(CLE), frozen_sha256=digest)
    except Exception as exc:
        state("failed", error_type=type(exc).__name__, error=str(exc))
        raise


if __name__ == "__main__":
    main()

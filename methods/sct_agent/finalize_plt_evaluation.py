"""冻结 SCT 经验库后的 CodeSecEval Base/Plus 评测适配器。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

try:
    from .run_plt_self_evolution import BASE, PLUS, _client, _generate, _validate, _evidence_dict
except ImportError:  # 直接执行脚本时使用脚本目录导入。
    from run_plt_self_evolution import BASE, PLUS, _client, _generate, _validate, _evidence_dict

try:
    from .schemas import FreezeManifest, ValidationEvidence
except ImportError:  # 直接脚本执行时使用脚本目录导入。
    from schemas import FreezeManifest, ValidationEvidence

try:
    from .docker_preflight import run_docker_preflight
except ImportError:  # 直接脚本执行时使用脚本目录导入。
    from docker_preflight import run_docker_preflight


def _read_jsonl(path: Path) -> list[dict]:
    """读取冻结经验或逐任务 JSONL。"""
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    """按行写入最终评测记录。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _summary(rows: list[dict]) -> dict:
    """分别统计 Function、Secure、JointPass 和生成错误。"""
    total = len(rows)
    passed = sum(bool((row.get("validation") or {}).get("passed")) for row in rows)
    return {
        "total": total,
        "functional": sum(bool((row.get("validation") or {}).get("evidence", {}).get("functional", {}).get("status") == "pass") for row in rows),
        "secure": sum(bool((row.get("validation") or {}).get("evidence", {}).get("security", {}).get("status") == "pass") for row in rows),
        "joint_pass": passed,
        "generation_errors": sum(bool(row.get("error")) for row in rows),
        "feedback_channel": "disabled",
    }


def main() -> None:
    """加载冻结清单后执行 Base/Plus，禁止任何 memory 更新。"""
    parser = argparse.ArgumentParser(description="运行冻结后的 PLT SCT Base/Plus 评测")
    parser.add_argument("run_dir")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--timeout", type=float, default=40)
    parser.add_argument("--validation-timeout", type=int, default=60, help="CodeSecEval 验证器超时（秒）")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--eval-limit", type=int, default=0)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    freeze_path = run_dir / "frozen" / "freeze_metadata.json"
    if not freeze_path.exists():
        raise FileNotFoundError(f"缺少冻结清单：{freeze_path}")
    freeze_data = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze_data.get("feedback_channel") != "disabled":
        raise RuntimeError("冻结清单未关闭反馈通道，拒绝执行最终评测")
    memory = _read_jsonl(run_dir / "frozen" / "m_star.jsonl")
    memory_sha = hashlib.sha256((run_dir / "frozen" / "m_star.jsonl").read_bytes()).hexdigest()
    if freeze_data.get("memory_sha256") and freeze_data["memory_sha256"] != memory_sha:
        raise RuntimeError("冻结经验文件 hash 与 freeze_metadata 不一致")
    docker_preflight = run_docker_preflight()
    if not docker_preflight.get("ok"):
        for subset, dataset_path in (("Base", BASE), ("Plus", PLUS)):
            expected_total = len(json.loads(dataset_path.read_text(encoding="utf-8")))
            _write_jsonl(run_dir / "validation_runs" / subset / "rows.jsonl", [])
            (run_dir / "validation_runs" / subset / "summary.json").write_text(
                json.dumps(
                    {
                        "total": expected_total,
                        "evaluated": 0,
                        "status": "blocked",
                        "error_type": "environment_error",
                        "docker_preflight": docker_preflight,
                        "feedback_channel": "disabled",
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        raise RuntimeError(f"Docker preflight failed; Base/Plus evaluation blocked: {docker_preflight.get('message')}")
    client = _client()

    for subset, dataset_path in (("Base", BASE), ("Plus", PLUS)):
        tasks = json.loads(dataset_path.read_text(encoding="utf-8"))
        if args.eval_limit:
            tasks = tasks[: args.eval_limit]

        def evaluate(task: dict) -> dict:
            code, error, retries = _generate(client, task["Problem"], memory, args.model, args.timeout, args.retries)
            validation = _validate(task, code, validation_timeout=args.validation_timeout) if code else _validate(task, "", validation_timeout=args.validation_timeout)
            return {"subset": subset, "task_id": task.get("ID"), "generated_code": code, "error": error, "retries": retries, "validation": validation, "feedback_channel": "disabled"}

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            rows = list(pool.map(evaluate, tasks))
        _write_jsonl(run_dir / "validation_runs" / subset / "rows.jsonl", rows)
        (run_dir / "validation_runs" / subset / "summary.json").write_text(json.dumps(_summary(rows), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

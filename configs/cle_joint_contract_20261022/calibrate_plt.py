"""固定十二题的 PLT 正对照环境校准；零 API，不产生 CLE 模型成绩。

任务来自当前在线 D_init 快照。先以固定 SHA256 种子选十二个不同 CWE，
再在每层选一题；不读取历史分数，不重跑已确认有夹具问题的 907。
代码只复用项目原 reference() 拼接规则、原 validate_and_state() 验证入口。
每题只测一次，保留失败，不修改参考、夹具、记忆或正式数据。
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from configs.cle_dgrow_url_repair_20261019.repair_and_retest import reference
from methods.sct_trajectory.closed_loop import validate_and_state


SEED = "cle-joint-contract-calibration-v1"
COUNT = 12
TIMEOUT = 20
WORKERS = 2
TASKS = ROOT / "translation_work/diagnostics/20261020/cle_q_online_v1/tasks_D_init.json"
RAW = ROOT / "translation_work/diagnostics/20261022/cle_joint_contract/calibration"
CURATED = ROOT / "results/curated/cle_joint_contract_20261022/calibration_summary.json"


def digest(value):
    """以 UTF-8 字节记录稳定 SHA256。"""
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    """仅用于对象内容身份，不改变交给原验证器的对象。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write(path, value):
    """保存新诊断产物；所有历史任务和结果保持只读。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def choose(tasks):
    """先冻结十二个 CWE 层及各层任务，绝不读取旧成绩进行筛选。"""
    by_cwe = defaultdict(list)
    for task in tasks.values():
        if str(task["index"]) != "907":
            by_cwe[str(task["CWE_ID"])].append(task)
    cwes = sorted(by_cwe, key=lambda value: digest(SEED + ":" + value))[:COUNT]
    selected = [min(by_cwe[cwe], key=lambda row: digest(SEED + ":" + str(row["index"]))) for cwe in cwes]
    if len(selected) != COUNT:
        raise ValueError("insufficient_distinct_CWE_strata")
    return selected


def identity(task):
    """记录输入任务、完整参考代码和原验证器路径的身份。"""
    return {
        "task_id": str(task["index"]),
        "CWE_ID": str(task["CWE_ID"]),
        "family_id": task.get("family_id"),
        "task_sha256": digest(canonical(task)),
        "reference_code_sha256": digest(reference(task)),
    }


def run_control(task):
    """原生运行一次正对照；失败和异常都留痕，不自动重试。"""
    before = perf_counter()
    item = identity(task)
    try:
        evidence, state = validate_and_state(task, reference(task), timeout=TIMEOUT)
        item.update(evidence=evidence, state=state)
    except Exception as exc:
        item.update(evidence=None, state=None, infrastructure_exception=type(exc).__name__)
    item["elapsed_seconds"] = round(perf_counter() - before, 6)
    item["reference_only"] = True
    write(RAW / "tasks" / (item["task_id"] + ".json"), item)
    return item


def package_versions():
    """只记录环境版本；不读取凭据、请求服务或安装依赖。"""
    result = {}
    for name in ("numpy", "sympy", "PyYAML", "requests", "openai", "pytest"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def main():
    """先保存固定样本清单，再执行有界原生校准，最后保存紧凑摘要。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-only", action="store_true", help="只展示固定任务 ID，不写产物或执行候选")
    args = parser.parse_args()
    tasks_bytes = TASKS.read_bytes()
    tasks = json.loads(tasks_bytes)
    selected = choose(tasks)
    plan = [identity(task) for task in selected]
    if args.plan_only:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    RAW.mkdir(parents=True, exist_ok=False)
    if CURATED.exists():
        raise FileExistsError("calibration_summary_already_exists_no_overwrite")
    sources = [Path(__file__), ROOT / "methods/sct_agent/validation_evidence.py",
               ROOT / "methods/sct_trajectory/closed_loop.py",
               ROOT / "configs/cle_dgrow_url_repair_20261019/repair_and_retest.py"]
    metadata = {
        "protocol": SEED,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "tasks_path": str(TASKS.relative_to(ROOT)),
        "tasks_file_sha256": digest(tasks_bytes),
        "source_sha256": {str(path.relative_to(ROOT)): digest(path.read_bytes()) for path in sources},
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": package_versions(),
        "backend": "original validate_and_state / local python -X utf8 -I",
        "sample": plan,
        "selection": "SHA256(seed:CWE) selects 12 distinct CWE strata; SHA256(seed:task_id) selects one task per stratum",
        "excluded_task_ids": ["907"],
        "exclusion_reason": "Known fixture issue already confirmed; no repeat requested",
        "timeout_seconds_per_task": TIMEOUT,
        "workers": WORKERS,
        "repeats": 1,
        "maximum_native_executions": COUNT,
        "API_calls": 0,
        "reference_composition": "code_before + patched_code + code_after (original project function)",
        "scope": "reference_environment_calibration_not_model_or_CLE_score",
        "success_rule": "All 12 references pass syntax, functional and security; otherwise preserve failures and block unconditional environment certification.",
        "interpretation_limit": "Only these 12 references in this Linux environment; no all-303 or Base/Plus environment certification.",
    }
    write(RAW / "manifest.json", metadata)
    print(json.dumps({"status": "started", "tasks": [row["task_id"] for row in plan], "API_calls": 0}), flush=True)
    records = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        pending = {executor.submit(run_control, task): str(task["index"]) for task in selected}
        for future in as_completed(pending):
            item = future.result()
            records[item["task_id"]] = item
            print(json.dumps({"status": "completed", "task_id": item["task_id"], "state": item["state"],
                              "finished": len(records), "planned": COUNT}, ensure_ascii=False), flush=True)
    compact = []
    for planned in plan:
        item = records[planned["task_id"]]
        evidence = item.get("evidence") or {}
        statuses = {key: (evidence.get(key) or {}).get("status", "unmeasured")
                    for key in ("syntax_or_compile", "functional", "security")}
        compact.append({
            **planned,
            "state": item["state"],
            "statuses": statuses,
            "reference_joint_pass": all(value == "pass" for value in statuses.values()),
            "error_types": {key: value.get("error_type") for key, value in evidence.items()
                            if isinstance(value, dict) and value.get("error_type")},
            "infrastructure_exception": item.get("infrastructure_exception"),
            "elapsed_seconds": item["elapsed_seconds"],
            "evidence_sha256": digest(canonical(evidence)),
            "raw_evidence": str((RAW / "tasks" / (item["task_id"] + ".json")).relative_to(ROOT)),
        })
    summary = {
        "protocol": SEED,
        "scope": metadata["scope"],
        "source_tasks_sha256": metadata["tasks_file_sha256"],
        "environment": {key: metadata[key] for key in ("python_version", "platform", "backend", "package_versions")},
        "rows": compact,
        "reference_controls": COUNT,
        "reference_joint_passes": sum(row["reference_joint_pass"] for row in compact),
        "all_controls_pass": all(row["reference_joint_pass"] for row in compact),
        "API_calls": 0,
        "new_model_generations": 0,
        "CLE_results_modified": False,
        "raw_manifest": str((RAW / "manifest.json").relative_to(ROOT)),
        "interpretation_limit": metadata["interpretation_limit"],
    }
    write(RAW / "summary.json", summary)
    write(CURATED, summary)
    print(json.dumps({"summary": str(CURATED.relative_to(ROOT)), "controls": COUNT,
                      "reference_joint_passes": summary["reference_joint_passes"], "API_calls": 0}), flush=True)


if __name__ == "__main__":
    main()

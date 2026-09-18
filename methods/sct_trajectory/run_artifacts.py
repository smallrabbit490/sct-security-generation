"""运行产物固化助手（看板数据契约）。

所属阶段：全流程（Phase1/2/3）与运行收尾。
职责：把运行过程中产生的可观测状态写进**固定路径**，供网页看板实时读取。
    看板不靠"扫描目录猜"，只读这里定义的契约文件：
      - runs_index.json        全局运行索引（运行列表 + 状态）
      - <run>/status.json      当前阶段与心跳（识别"进行中"）
      - <run>/run_metadata.json 运行配置与代码版本
      - <run>/pools.json       三池任务清单
      - <run>/tree_snapshots/  每轮树快照（画成长轨迹）
输入：运行目录、阶段名、树对象、任务池。
输出：JSON 文件（原子写：先写 .tmp 再 replace，避免看板读到半截文件）。
验证证据：本模块只做持久化，不执行验证；状态字段不代表任何测试结论。
失败类型：IO 异常向上抛，调用方决定是否降级。
允许修改长期经验库：否——只写审计产物。
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json_atomic(path: Path, value: Any) -> None:
    """原子写 JSON：先写临时文件再替换，避免看板读到写了一半的文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def write_status(run_dir: Path, *, status: str, stage: str, detail: str = "", error: str | None = None,
                 progress: dict | None = None) -> None:
    """写运行状态与心跳（看板据此判断"进行中/已完成/失败"）。

    status: running | completed | failed
    stage : phase1 | phase2 | phase3 | final_eval | done
    """
    payload = {
        "status": status,
        "stage": stage,
        "detail": detail,
        "error": error,
        "updated_at": _now(),
        "updated_ts": time.time(),
        "progress": progress or {},
        "pid": os.getpid(),
    }
    write_json_atomic(run_dir / "status.json", payload)


def append_run_index(sct_runs_root: Path, *, run_name: str, run_dir: Path, status: str,
                     model: str = "", tasks: int = 0, extra: dict | None = None) -> None:
    """登记/更新全局运行索引 runs_index.json（看板运行列表的唯一来源）。"""
    index_path = sct_runs_root / "runs_index.json"
    index: dict[str, Any] = {"runs": []}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            index = {"runs": []}
    runs = [r for r in index.get("runs", []) if r.get("run_name") != run_name]
    entry = {
        "run_name": run_name,
        "path": str(run_dir),
        "status": status,
        "model": model,
        "tasks": tasks,
        "updated_at": _now(),
    }
    if extra:
        entry.update(extra)
    runs.append(entry)
    runs.sort(key=lambda r: str(r.get("run_name", "")), reverse=True)
    index["runs"] = runs
    index["updated_at"] = _now()
    write_json_atomic(index_path, index)


def _jsonable(value: Any) -> Any:
    """把 Path 等不可序列化对象转成可写 JSON 的形式（参数里可能含 --out 的 Path）。"""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def write_run_metadata(run_dir: Path, *, model: str, args: dict, dataset: str,
                       summary: dict | None = None) -> None:
    """写运行元数据：配置、模型、代码版本，便于复现与看板展示。"""
    try:
        import subprocess
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                cwd=str(run_dir), capture_output=True, text=True,
                                timeout=10).stdout.strip()
    except Exception:
        commit = ""
    write_json_atomic(run_dir / "run_metadata.json", {
        "model": model,
        "dataset": dataset,
        "args": _jsonable(args),
        "git_commit": commit,
        "created_at": _now(),
        "output_schema": [
            "status.json", "pools.json", "phase1_results.jsonl", "trajectories.jsonl",
            "rounds.jsonl", "tree_snapshots/*.json", "audit_detail.jsonl", "gate_records.jsonl",
            "experience_pool.jsonl", "error_ledger.jsonl", "frozen/m_star.jsonl",
            "final_eval.jsonl", "final_eval_summary.json", "tree.json", "summary.json",
        ],
        "summary": summary or {},
    })


def write_pools(run_dir: Path, *, source: list[dict], replay: list[dict], audit: list[dict]) -> None:
    """写三池任务清单（看板"先查看任务池"用）。"""
    def brief(rows: list[dict]) -> list[dict]:
        return [{"task_id": r.get("index"), "cwe": str(r.get("CWE_ID", "")),
                 "family_id": str(r.get("family_id", "")),
                 "description": str((r.get("task_description") or {}).get("description", ""))[:200]}
                for r in rows]

    write_json_atomic(run_dir / "pools.json", {
        "source": brief(source), "replay": brief(replay), "audit": brief(audit),
        "counts": {"source": len(source), "replay": len(replay), "audit": len(audit)},
        "updated_at": _now(),
    })


def write_tree_snapshot(run_dir: Path, *, label: str, tree, extra: dict | None = None,
                        pool: list | None = None) -> Path:
    """写某一轮结束时的整棵树快照（看板画成长轨迹与结构变化）。

    label: phase1 / round1 / round2 / ...
    pool : 统一经验池条目（可选）。架构归一化后 Phase1 不再直接入树，Phase1 页要看的
           "第一阶段形成的经验"其实是经验池，因此快照同时记录池内容。
    """
    snap_dir = run_dir / "tree_snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "label": label,
        "created_at": _now(),
        "tree": tree.to_dict() if hasattr(tree, "to_dict") else tree,
    }
    if pool is not None:
        payload["pool"] = [n.to_dict() if hasattr(n, "to_dict") else n for n in pool]
    if extra:
        payload.update(extra)
    path = snap_dir / f"{label}.json"
    write_json_atomic(path, payload)
    return path

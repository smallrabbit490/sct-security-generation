"""CLE新版只读看板：复用旧看板聚合器，补齐轮次、快照及任务/经验关联。

输入仅来自已落盘运行产物；不调用模型，不运行生成代码，不写经验库。
演示数据由demo_data.py单独提供，不放入translation_work或真实运行列表。
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
OLD = HERE.parent / "dashboard" / "server.py"
spec = importlib.util.spec_from_file_location("cle_dashboard_legacy", OLD)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
DEMO = "__demo__"
FILES = {
    "pools.json": "三池任务清单与计数",
    "run_metadata.json": "模型与运行配置（脱敏）",
    "status.json": "阶段、心跳与中断情况",
    "phase1_results.jsonl": "首次生成、修复后代码与测量",
    "rounds.jsonl": "逐轮调度与通过率",
    "trajectories.jsonl": "逐轮任务轨迹与经验召回",
    "audit_detail.jsonl": "候选经验、审查任务与门控决定",
    "tree_snapshots/": "phase1.json、round1.json等历史快照",
    "experience_pool.jsonl": "统一经验池正文",
    "frozen/m_star.jsonl": "冻结经验清单",
    "final_eval_summary.json": "运行收尾审计摘要",
    "final_eval.jsonl": "运行收尾审计逐题结果",
    "cost.json": "已落盘usage与费用口径",
}


def read_json(path: Path, default=None):
    """缺文件保持缺失；格式损坏由HTTP层明确报告，不当作零结果。"""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def read_rows(path: Path):
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()] if path.exists() else []


def round_of(row):
    value = row.get("round")
    return str(value) if value is not None else "unassigned"


def scoped(rows, selected):
    return rows if selected == "all" else [r for r in rows if round_of(r) == selected]


def flatten_tree(tree):
    return [dict(n, cwe=n.get("cwe", cwe)) for cwe, fam in (tree or {}).items() for n in fam.get("invariants", [])]


def recalled_ids(row):
    cards = list(row.get("cards") or [])
    cards += [c for group in row.get("retrieved_per_round", []) for c in group]
    return list(dict.fromkeys(str(c["invariant_id"]) for c in cards if isinstance(c, dict) and c.get("invariant_id")))


def task_record(row, stage, round_id, suffix=""):
    """保留阶段/轮次的任务身份；召回不自动解释成采纳。"""
    tid = str(row.get("task_id", "未知任务"))
    codes = row.get("generated_codes") or []
    if not codes and row.get("code"):
        codes = [row["code"]]
    evidence = row.get("evidence") or []
    if isinstance(evidence, dict):
        evidence = [evidence]
    if stage == "phase1":
        evidence = [row.get("evidence_first") or {}, row.get("evidence_after_repair") or {}]
    return {
        "key": f"{stage}:{round_id}:{suffix}:{tid}", "task_id": tid,
        "stage": stage, "round": round_id, "cwe": str(row.get("cwe", "?")),
        "states": row.get("states") or [row.get("state_first"), row.get("state_after_repair") or row.get("state")],
        "codes": codes, "evidence": evidence, "feedback": row.get("feedback") or [],
        "recalled_ids": recalled_ids(row), "adopted_ids": row.get("adopted_ids"),
        "context": row.get("agent_context") or [], "candidate_id": row.get("candidate_id"),
        "branches": row.get("branches") or [], "branch_selection": row.get("branch_selection") or {},
        "description": row.get("description") or "", "patch_diffs": row.get("patch_diffs") or [],
    }


def index():
    data = legacy.api_runs()
    runs = [{k: r.get(k) for k in ("run_name", "status", "stage", "updated_at", "model")} for r in data["runs"]]
    known = {r["run_name"] for r in runs}
    if legacy.SCT_RUNS.exists():
        for directory in sorted(legacy.SCT_RUNS.iterdir(), reverse=True):
            if directory.is_dir() and directory.name not in known and any((directory / f).exists() for f in ("status.json", "run_metadata.json", "pools.json")):
                status = legacy._run_status(directory)
                runs.append({"run_name": directory.name, **{k: status.get(k) for k in ("status", "stage", "updated_at")}})
    return {"runs": runs, "root": str(legacy.SCT_RUNS), "files": FILES,
            "demo": {"run_name": DEMO, "label": "示例运行（合成数据）"}}


def real_bundle(name):
    """旧站API保持不变；新版仅组装读取结果和旧接口未暴露的原始轨迹字段。"""
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError("无效运行名称")
    rd = (legacy.SCT_RUNS / name).resolve()
    if not rd.is_relative_to(legacy.SCT_RUNS.resolve()) or not rd.is_dir():
        raise ValueError("运行目录不存在或不在看板读取目录内")
    overview = legacy.api_overview(name)
    meta = overview.pop("metadata", {})
    snapshots = []
    for path in sorted((rd / "tree_snapshots").glob("*.json")):
        snap = read_json(path, {})
        label = snap.get("label") or path.stem
        match = re.fullmatch(r"round(\d+)", label)
        rid = str(snap.get("round_log", {}).get("round")) if snap.get("round_log", {}).get("round") is not None else (match[1] if match else "0" if label == "phase1" else "unassigned")
        snapshots.append({"label": label, "round": rid, "tree": snap.get("tree") or {}, "pool": snap.get("pool") or []})
    p1 = legacy.api_phase1(name)
    p2 = legacy.api_phase2(name)
    p3 = legacy.api_phase3(name)
    pools = read_json(rd / "pools.json", {})
    cwes = {str(t["task_id"]): t.get("cwe", "?") for key in ("source", "replay", "audit") for t in pools.get(key, [])}
    final = [dict(t, cwe=cwes.get(str(t.get("task_id")), "?")) for t in p3.get("final_eval_rows", [])]
    return {
        "overview": overview, "phase1": p1, "phase2": p2, "phase3": p3,
        "model": meta.get("model") or meta.get("args", {}).get("model") or "未记录",
        "language": meta.get("language") or meta.get("args", {}).get("language") or "未记录",
        "snapshots": snapshots, "cards": read_rows(rd / "experience_pool.jsonl") or read_rows(rd / "frozen/m_star.jsonl"),
        "raw_phase1": read_rows(rd / "phase1_results.jsonl"),
        "raw_trajectories": read_rows(rd / "trajectories.jsonl"), "raw_final": final,
        "pools": pools, "artifacts": {k: (rd / k).exists() for k in FILES},
    }


def workbench(name, selected="", snapshot=""):
    if name == DEMO:
        from demo_data import build_demo
        data = build_demo()
    else:
        data = real_bundle(name)
    rounds = data["phase2"].get("rounds", [])
    audits = data["phase3"].get("audit_entries", [])
    all_scoped = rounds + data["raw_trajectories"] + audits
    ids = sorted({round_of(r) for r in all_scoped if round_of(r).isdigit()}, key=int)
    options = ids + (["unassigned"] if any(round_of(r) == "unassigned" for r in all_scoped) else [])
    if not selected:
        selected = ids[-1] if ids else "all"
    if selected not in ["all"] + options:
        raise ValueError("该运行没有所选轮次，请重新选择")
    snaps = [s for s in data["snapshots"] if selected == "all" or s["round"] == selected]
    chosen = next((s for s in snaps if s["label"] == snapshot), None)
    if chosen is None:
        chosen = snaps[-1] if snaps else None
    # 历史快照缺失时不拿当前经验池冒充该轮正文。
    cards = (chosen.get("pool") or flatten_tree(chosen["tree"])) if chosen else (data["cards"] if selected == "all" else [])
    tasks = [task_record(t, "phase1", "0") for t in data["raw_phase1"]]
    tasks += [task_record(t, "replay", round_of(t)) for t in scoped(data["raw_trajectories"], selected)]
    for entry in scoped(audits, selected):
        for task in entry.get("selected_tasks") or []:
            # 只展示此条门控记录实际保存的代码/测量，不复用同ID的来源或回放代码。
            t = dict(task, candidate_id=entry.get("candidate_id"))
            tasks.append(task_record(t, "gate", round_of(entry), str(entry.get("candidate_id"))))
    tasks += [task_record(t, "audit", "final", str(t.get("arm", "memory"))) for t in data["raw_final"]]
    p2 = data["phase2"]
    p2["rounds_detail"] = scoped(p2.get("rounds_detail", []), selected)
    p2["trajectories"] = [dict(t, round=round_of(t), final=(t.get("states") or ["U"])[-1])
                          for t in scoped(data["raw_trajectories"], selected)]
    p2["abcd"] = dict(Counter(t.get("final", "?") for t in p2["trajectories"]))
    p3 = data["phase3"]
    p3["audit_entries"] = scoped(audits, selected)
    p3["decision_counts"] = dict(Counter(t.get("decision", "unmeasured") for t in p3["audit_entries"]))
    return {
        **{k: data[k] for k in ("overview", "phase1", "phase2", "phase3", "model", "language", "artifacts", "pools")},
        "run_name": name, "demo": name == DEMO, "round_options": options, "round": selected,
        "snapshots": [{"label": s["label"], "round": s["round"]} for s in snaps],
        "snapshot": chosen["label"] if chosen else None, "tree": chosen["tree"] if chosen else {},
        "cards": cards, "tasks": tasks, "unassigned_audits": sum(round_of(a) == "unassigned" for a in audits),
        "final_scope": "运行收尾审计；不按当前轮次筛选，非独立留出评测",
    }


class Handler(BaseHTTPRequestHandler):
    """仅接受本机GET读取；静态路径和运行目录都限制在明确目录内。"""
    def send(self, body, status=200, kind="application/json; charset=utf-8"):
        payload = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        try:
            if url.path == "/api/index":
                self.send(index()); return
            if url.path == "/api/workbench":
                self.send(workbench(q.get("run", [""])[0], q.get("round", [""])[0], q.get("snapshot", [""])[0])); return
            if url.path.startswith("/api/"):
                self.send({"error": "没有这个只读接口"}, 404); return
            path = (STATIC / ("index.html" if url.path == "/" else url.path.lstrip("/"))).resolve()
            if not path.is_relative_to(STATIC.resolve()) or not path.is_file():
                self.send({"error": "文件不存在"}, 404); return
            kind = {".html": "text/html", ".js": "text/javascript", ".css": "text/css"}.get(path.suffix, "application/octet-stream")
            self.send(path.read_bytes(), kind=kind + "; charset=utf-8")
        except (ValueError, json.JSONDecodeError) as error:
            self.send({"error": str(error)}, 400)
        except OSError as error:
            self.send({"error": f"产物读取失败：{error}"}, 500)

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="CLE新版只读工作台（保留旧站8770）")
    parser.add_argument("--port", type=int, default=8771)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"CLE新版：http://127.0.0.1:{args.port}；读取 {legacy.SCT_RUNS}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

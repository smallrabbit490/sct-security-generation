"""CLE 任务看板后端（只读，Python 标准库实现，零第三方依赖）。

所属阶段：看板服务层，不改动任何实验产物。
输入：HTTP 请求 + translation_work/sct_runs 下的运行产物（run_artifacts.py 定义的数据契约）。
输出：JSON API + 静态页面。
验证证据：本服务只读取与聚合已落盘的审计产物，不执行验证、不修改经验库。
失败类型：运行目录缺失/字段缺失 → 返回空值并在响应里标注 missing 字段（兼容老运行）。
允许修改长期经验库：否——严格只读。

启动：
    python methods/sct_trajectory/dashboard/server.py --port 8770
    # 浏览器打开 http://127.0.0.1:8770
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[3]          # 仓库根
SCT_RUNS = ROOT / "translation_work" / "sct_runs"
STATIC = Path(__file__).resolve().parent / "static"
STALE_SECONDS = 120                                  # 心跳超过该秒数视为已停止


# ---------------- 读取助手（缺失字段一律降级，不抛错） ----------------

def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _run_status(run_dir: Path) -> dict:
    """判定运行状态：进行中 / 已完成 / 已失败 / 未知（老运行没有 status.json）。"""
    st = _read_json(run_dir / "status.json")
    if st is None:
        # 老运行：有 summary.json 视为已完成，否则未知
        if (run_dir / "summary.json").exists():
            return {"status": "completed", "stage": "done", "detail": "（历史运行，无状态文件）",
                    "stale": False}
        return {"status": "unknown", "stage": "", "detail": "无状态文件", "stale": False}
    running = st.get("status") == "running"
    stale = running and (time.time() - float(st.get("updated_ts") or 0) > STALE_SECONDS)
    return {"status": "stale" if stale else st.get("status", "unknown"),
            "stage": st.get("stage", ""), "detail": st.get("detail", ""),
            "updated_at": st.get("updated_at", ""), "stale": stale,
            "progress": st.get("progress") or {}, "error": st.get("error")}


def _abcd_of(rows: list[dict], key: str) -> dict:
    c = Counter(str(r.get(key) or "?") for r in rows)
    return {k: c.get(k, 0) for k in ("A", "B", "C", "D") if c.get(k)}


def _rate(n: int, total: int) -> float:
    return round(n / total, 4) if total else 0.0


# ---------------- 各阶段数据聚合 ----------------

def api_runs() -> dict:
    """运行列表：优先读 runs_index.json；没有索引的老运行按目录兜底。"""
    index = _read_json(SCT_RUNS / "runs_index.json", {"runs": []}) or {"runs": []}
    known = {r.get("run_name") for r in index.get("runs", [])}
    runs = []
    for r in index.get("runs", []):
        rd = Path(r.get("path") or (SCT_RUNS / r["run_name"]))
        st = _run_status(rd)
        runs.append({**r, "status": st["status"], "stage": st["stage"],
                     "detail": st.get("detail", ""), "updated_at": st.get("updated_at", ""),
                     "has_dashboard_artifacts": (rd / "pools.json").exists()})
    # 兜底：目录存在但未登记的运行
    if SCT_RUNS.exists():
        for d in sorted(SCT_RUNS.iterdir(), reverse=True):
            if d.is_dir() and d.name not in known and (d / "progress.log").exists():
                st = _run_status(d)
                runs.append({"run_name": d.name, "path": str(d), "status": st["status"],
                             "stage": st["stage"], "detail": st.get("detail", ""),
                             "updated_at": st.get("updated_at", ""),
                             "has_dashboard_artifacts": (d / "pools.json").exists(),
                             "model": "", "tasks": 0})
    return {"runs": runs, "count": len(runs)}


def _run_dir(run_name: str) -> Path:
    return SCT_RUNS / run_name


def api_overview(run_name: str) -> dict:
    rd = _run_dir(run_name)
    pools = _read_json(rd / "pools.json") or {}
    meta = _read_json(rd / "run_metadata.json") or {}
    rounds = _read_jsonl(rd / "rounds.jsonl")
    p1 = _read_jsonl(rd / "phase1_results.jsonl")
    fe = _read_json(rd / "final_eval_summary.json") or {}
    cost = _read_json(rd / "cost.json") or {}
    st = _run_status(rd)
    counts = (pools.get("counts") or {})
    has_pools = bool(counts)
    # 老运行没有 pools.json：用 phase1 条数兜底，并明确标注是推断值
    inferred = None
    if not has_pools:
        args_limit = (meta.get("args") or {}).get("limit")
        inferred = args_limit or (len(p1) if p1 else None)
    return {
        "run_name": run_name,
        "status": st,
        "metadata": meta,
        "pools_counts": counts,
        "has_pools": has_pools,
        "total_tasks": sum(counts.values()) if has_pools else inferred,
        "total_tasks_inferred": (not has_pools) and inferred is not None,
        "phase1_done": len(p1),
        "rounds": len(rounds),
        "final_eval": {"joint_pass": fe.get("joint_pass"), "size": fe.get("eval_pool_size"),
                       "rate": fe.get("joint_pass_rate")},
        # 精确成本（真实 API usage 累计；老运行无此文件则为空）
        "cost": {
            "total": cost.get("total"),
            "stages": cost.get("stages") or {},
            "by_label": cost.get("by_label") or {},
            "model": cost.get("model"),
            "pricing": cost.get("pricing"),
            "pricing_source": cost.get("pricing_source"),
            "currency": cost.get("currency"),
            "note": cost.get("note"),
        } if cost else None,
        "missing": [k for k, ok in (
            ("pools.json", (rd / "pools.json").exists()),
            ("status.json", (rd / "status.json").exists()),
            ("tree_snapshots/", (rd / "tree_snapshots").exists()),
            ("frozen/m_star.jsonl", (rd / "frozen" / "m_star.jsonl").exists()),
            ("final_eval_summary.json", (rd / "final_eval_summary.json").exists()),
        ) if not ok],
    }


def _brief_case(r: dict, cwe: str) -> dict:
    """把一个 Phase1 结果整理成看板可展示的案例（含代码/差分/四步上下文）。"""
    return {
        "task_id": r.get("task_id"), "cwe": cwe,
        "state_first": r.get("state_first"), "state_after_repair": r.get("state_after_repair"),
        "outcome": r.get("outcome"),
        "evidence_first": r.get("evidence_first"),
        "evidence_after_repair": r.get("evidence_after_repair"),
        "generated_codes": r.get("generated_codes") or [],
        "patch_diffs": r.get("patch_diffs") or [],
        "agent_context": r.get("agent_context") or [],
    }


def api_phase1(run_name: str) -> dict:
    rd = _run_dir(run_name)
    rows = _read_jsonl(rd / "phase1_results.jsonl")
    first = [r for r in rows if r.get("state_first")]
    after = [r for r in rows if r.get("state_after_repair")]
    by_cwe: dict[str, dict] = defaultdict(lambda: {"total": 0, "first_A": 0,
                                                   "after_A": 0, "first": Counter(), "after": Counter()})
    failures = []
    successes = []
    for r in rows:
        c = str(r.get("cwe"))
        e = by_cwe[c]
        e["total"] += 1
        if r.get("state_first"):
            e["first"][r["state_first"]] += 1
            if r["state_first"] == "A":
                e["first_A"] += 1
        if r.get("state_after_repair"):
            e["after"][r["state_after_repair"]] += 1
            if r["state_after_repair"] == "A":
                e["after_A"] += 1
        outcome = r.get("outcome") or ""
        if outcome == "seed_grounding_failure":
            failures.append(_brief_case(r, c))
        elif outcome in ("seed_active", "seed_active_after_repair"):
            successes.append(_brief_case(r, c))

    # 为每个失败案例配一个"对照成功案例"：优先同 CWE，无则全局回退（明确标注）
    succ_by_cwe: dict[str, list[dict]] = defaultdict(list)
    for s in successes:
        succ_by_cwe[s["cwe"]].append(s)
    for f in failures:
        same = succ_by_cwe.get(f["cwe"]) or []
        if same:
            f["compare"] = same[0]
            f["compare_scope"] = "same_cwe"
        elif successes:
            f["compare"] = successes[0]
            f["compare_scope"] = "cross_cwe"     # 全局回退，前端要标注"CWE 不同，仅供参考"
        else:
            f["compare"] = None
            f["compare_scope"] = "none"

    snap = _read_json(rd / "tree_snapshots" / "phase1.json")
    # 老运行没��� state_first/state_after_repair 字段：用 outcome 兜底统计，并标注来源
    first_src, after_src = "state_first", "state_after_repair"
    if not first:
        first = [{"state_first": "A" if r.get("outcome") in ("seed_active",) else "non-A"}
                 for r in rows if r.get("outcome", "").startswith("seed_")]
        after = [{"state_after_repair": "A" if r.get("outcome") in ("seed_active", "seed_active_after_repair")
                  else "non-A"} for r in rows if r.get("outcome", "").startswith("seed_")]
        first_src = after_src = "outcome(旧字段回退)"
    first_a = sum(1 for r in first if (r.get("state_first") or r.get("state_after_repair")) == "A")
    after_a = sum(1 for r in after if (r.get("state_after_repair") or r.get("state_first")) == "A")
    return {
        "run_name": run_name,
        "total": len(rows),
        "rate_source": first_src,
        "first_pass": {"A": first_a, "total": len(first), "rate": _rate(first_a, len(first))},
        "after_pass": {"A": after_a, "total": len(after), "rate": _rate(after_a, len(after))},
        "abcd_first": _abcd_of(first, "state_first"),
        "abcd_after": _abcd_of(after, "state_after_repair"),
        "by_cwe": {c: {"total": v["total"], "first_A": v["first_A"], "after_A": v["after_A"],
                       "first_rate": _rate(v["first_A"], v["total"]), "after_rate": _rate(v["after_A"], v["total"]),
                       "abcd_first": {k: v["first"].get(k, 0) for k in ("A", "B", "C", "D") if v["first"].get(k)},
                       "abcd_after": {k: v["after"].get(k, 0) for k in ("A", "B", "C", "D") if v["after"].get(k)}}
                   for c, v in sorted(by_cwe.items())},
        "failures": failures,
        "successes": successes,
        "compare_note": ("失败案例已配对对照成功案例：compare_scope=same_cwe 表示同 CWE；"
                         "cross_cwe 表示无同 CWE 成功案例、回退到全局案例（仅供参考）"),
        "tree_snapshot": (snap or {}).get("tree"),
        # 架构归一化后 Phase1 不直接入树，"第一阶段形成的"经验在池里——这里一并返回
        "phase1_pool": (snap or {}).get("pool") or [],
    }


def api_phase2(run_name: str) -> dict:
    rd = _run_dir(run_name)
    rounds = _read_jsonl(rd / "rounds.jsonl")
    traj = _read_jsonl(rd / "trajectories.jsonl")
    pools = _read_json(rd / "pools.json") or {}
    # 每轮 ABCD
    per_round = []
    for i, t in enumerate(traj):
        states = [str(s) for s in (t.get("states") or [])]
        per_round.append({"task_id": t.get("task_id"), "cwe": t.get("cwe"), "states": states,
                          "final": states[-1] if states else "?",
                          "retrieved_ids": [c.get("invariant_id") for rd_ in (t.get("retrieved_per_round") or []) for c in rd_]})
    abcd = Counter(r["final"] for r in per_round)
    # 树成长轨迹（从快照读节点数）
    growth = []
    snap_dir = rd / "tree_snapshots"
    if snap_dir.exists():
        for f in sorted(snap_dir.glob("*.json")):
            s = _read_json(f) or {}
            tree = s.get("tree") or {}
            n_active = sum(1 for fam in tree.values() for n in fam.get("invariants", [])
                           if n.get("status") == "active")
            n_all = sum(len(fam.get("invariants", [])) for fam in tree.values())
            growth.append({"label": s.get("label") or f.stem, "active": n_active,
                           "nodes": n_all, "created_at": s.get("created_at", "")})
    return {
        "run_name": run_name,
        "replay_pool": pools.get("replay", []),
        "rounds": rounds,
        "abcd": {k: abcd.get(k, 0) for k in ("A", "B", "C", "D") if abcd.get(k)},
        "trajectories": per_round,
        "tree_growth": growth,
    }


def api_phase3(run_name: str) -> dict:
    rd = _run_dir(run_name)
    audit_detail = _read_jsonl(rd / "audit_detail.jsonl")
    gates = _read_jsonl(rd / "gate_records.jsonl")
    fe_summary = _read_json(rd / "final_eval_summary.json") or {}
    fe_rows = _read_jsonl(rd / "final_eval.jsonl")
    frozen = _read_jsonl(rd / "frozen" / "m_star.jsonl")
    return {
        "run_name": run_name,
        "audit_entries": audit_detail,
        "gate_records": gates,
        "frozen_size": len(frozen),
        "frozen_sample": frozen[:50],
        "final_eval_summary": fe_summary,
        "final_eval_rows": fe_rows,
        "decision_counts": dict(Counter(a.get("decision") for a in audit_detail)),
    }


def api_tree(run_name: str, label: str = "") -> dict:
    rd = _run_dir(run_name)
    if label:
        s = _read_json(rd / "tree_snapshots" / f"{label}.json")
        return {"label": label, "tree": (s or {}).get("tree")}
    return {"label": "final", "tree": _read_json(rd / "tree.json") or {}}


def api_pool(run_name: str, which: str = "audit") -> dict:
    pools = _read_json(_run_dir(run_name) / "pools.json") or {}
    return {"pool": which, "tasks": pools.get(which, []),
            "counts": (pools.get("counts") or {}).get(which, 0)}


def api_export(run_name: str, kind: str = "phase1") -> dict:
    """导出：把某阶段数据整理成可下载的 JSON（前端再转 CSV）。"""
    if kind == "phase1":
        return api_phase1(run_name)
    if kind == "phase2":
        return api_phase2(run_name)
    if kind == "phase3":
        return api_phase3(run_name)
    if kind == "pool":
        return _read_json(_run_dir(run_name) / "pools.json") or {}
    return {"error": "unknown kind"}


# ---------------- HTTP 服务 ----------------

ROUTES = {
    "/api/runs": lambda q: api_runs(),
    "/api/overview": lambda q: api_overview(q.get("run", [""])[0]),
    "/api/phase1": lambda q: api_phase1(q.get("run", [""])[0]),
    "/api/phase2": lambda q: api_phase2(q.get("run", [""])[0]),
    "/api/phase3": lambda q: api_phase3(q.get("run", [""])[0]),
    "/api/tree": lambda q: api_tree(q.get("run", [""])[0], q.get("label", [""])[0]),
    "/api/pool": lambda q: api_pool(q.get("run", [""])[0], q.get("which", ["audit"])[0]),
    "/api/export": lambda q: api_export(q.get("run", [""])[0], q.get("kind", ["phase1"])[0]),
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):        # 静默，避免刷屏
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):                          # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path in ROUTES:
            q = {k: v for k, v in parse_qs(parsed.query).items()}
            try:
                data = ROUTES[path](q)
            except Exception as exc:
                data = {"error": type(exc).__name__, "message": str(exc)}
            self._send(json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")
            return
        # 静态文件
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC / rel).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.exists():
            self._send(b"not found", "text/plain; charset=utf-8", 404)
            return
        ctype = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8"}.get(target.suffix, "application/octet-stream")
        self._send(target.read_bytes(), ctype)


def main() -> None:
    ap = argparse.ArgumentParser(description="CLE 自进化任务看板（只读）")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"CLE 看板已启动： http://{args.host}:{args.port}")
    print(f"读取运行目录： {SCT_RUNS}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()

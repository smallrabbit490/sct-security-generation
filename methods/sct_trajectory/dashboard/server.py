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
from datetime import datetime
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
    """判定运行状态：进行中 / 已完成 / 已失败 / 未知（老运行没有 status.json）。

    【存活判据用两路证据】status.json 的心跳只在阶段边界写，而 Phase1 要跑数小时，
    期间心跳会一直停在启动时刻——只看心跳会把健康运行误判为 stale。
    因此再取 progress.log / phase1_results.jsonl 的最后修改时间作为第二证据：
    任一文件在 STALE_SECONDS 内有过写入，就认为运行仍然存活。
    """
    st = _read_json(run_dir / "status.json")
    if st is None:
        # 老运行：有 summary.json 视为已完成，否则未知
        if (run_dir / "summary.json").exists():
            return {"status": "completed", "stage": "done", "detail": "（历史运行，无状态文件）",
                    "stale": False}
        return {"status": "unknown", "stage": "", "detail": "无状态文件", "stale": False}
    running = st.get("status") == "running"
    heartbeat_age = time.time() - float(st.get("updated_ts") or 0)
    if running and heartbeat_age > STALE_SECONDS:
        # 心跳过期 → 再用产物文件的 mtime 复核（任一在窗口内写过即视为存活）
        newest = 0.0
        for name in ("progress.log", "phase1_results.jsonl", "trajectories.jsonl",
                     "audit_detail.jsonl", "rounds.jsonl"):
            p = run_dir / name
            try:
                newest = max(newest, p.stat().st_mtime)
            except OSError:
                continue
        if newest and (time.time() - newest) <= STALE_SECONDS:
            heartbeat_age = time.time() - newest   # 以文件活动为准
    stale = running and heartbeat_age > STALE_SECONDS
    return {"status": "stale" if stale else st.get("status", "unknown"),
            "stage": st.get("stage", ""), "detail": st.get("detail", ""),
            "updated_at": st.get("updated_at", ""), "stale": stale,
            # updated_ts 供运行列表按时间排序（数值时间戳最可靠）
            "updated_ts": st.get("updated_ts") or 0,
            "progress": st.get("progress") or {}, "error": st.get("error")}


def _abcd_of(rows: list[dict], key: str) -> dict:
    c = Counter(str(r.get(key) or "?") for r in rows)
    return {k: c.get(k, 0) for k in ("A", "B", "C", "D") if c.get(k)}


def _rate(n: int, total: int) -> float:
    return round(n / total, 4) if total else 0.0


# ---------------- 各阶段数据聚合 ----------------

def _run_sort_key(r: dict) -> tuple:
    """运行列表排序键：**按时间倒序**（最新的排最前面）。

    时间取三者中最新可用的一个（优先级从高到低）：
      ① `updated_ts`（status.json 的心跳时间戳，最准）
      ② `updated_at`（ISO 字符串，老运行可能只有这个）
      ③ `path` 目录的 mtime（兜底：连状态文件都没有的运行）

    为什么要显式排序：原先直接沿用 runs_index.json 的写入顺序，
    老运行与新运行混在一起，用户很难在 30+ 个运行里找到刚跑的那个。
    """
    ts = r.get("updated_ts")
    if ts:
        try:
            return (1, float(ts))
        except (TypeError, ValueError):
            pass
    at = str(r.get("updated_at") or "")
    if at:
        try:
            return (1, datetime.fromisoformat(at.replace("/", "-")).timestamp())
        except ValueError:
            pass
    try:
        return (0, Path(r.get("path") or "").stat().st_mtime)
    except OSError:
        return (0, 0.0)


def api_runs() -> dict:
    """运行列表：优先读 runs_index.json；没有索引的老运行按目录兜底。

    返回结果**按时间倒序**（最新运行在最前），便于在看板第一页直接选到刚跑完的运行。
    """
    index = _read_json(SCT_RUNS / "runs_index.json", {"runs": []}) or {"runs": []}
    known = {r.get("run_name") for r in index.get("runs", [])}
    runs = []
    for r in index.get("runs", []):
        rd = Path(r.get("path") or (SCT_RUNS / r["run_name"]))
        st = _run_status(rd)
        runs.append({**r, "status": st["status"], "stage": st["stage"],
                     "detail": st.get("detail", ""), "updated_at": st.get("updated_at", ""),
                     "updated_ts": st.get("updated_ts", 0),
                     "has_dashboard_artifacts": (rd / "pools.json").exists()})
    # 兜底：目录存在但未登记的运行
    if SCT_RUNS.exists():
        for d in sorted(SCT_RUNS.iterdir(), reverse=True):
            if d.is_dir() and d.name not in known and (d / "progress.log").exists():
                st = _run_status(d)
                runs.append({"run_name": d.name, "path": str(d), "status": st["status"],
                             "stage": st["stage"], "detail": st.get("detail", ""),
                             "updated_at": st.get("updated_at", ""),
                             "updated_ts": st.get("updated_ts", 0),
                             "has_dashboard_artifacts": (d / "pools.json").exists(),
                             "model": "", "tasks": 0})
    # 按时间倒序（最新在前）
    runs.sort(key=_run_sort_key, reverse=True)
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


def _status_of(ev: dict, key: str) -> str:
    """安全取 evidence 里某一项的 status。字段可能是 dict / str / None（跨 schema 版本）。"""
    if not isinstance(ev, dict):
        return ""
    v = ev.get(key)
    if isinstance(v, dict):
        return str(v.get("status") or "")
    return str(v or "")


def _pass_rate_from_evidence(evs: list, idx: int) -> dict:
    """从 evidence[idx] 算功能/安全通过（供"初始(Phase1)"基线行用）。

    历史运行的 evidence 字段结构不一致（可能是 dict / str / None），
    必须逐层做类型守卫，否则会抛 AttributeError 导致整个 API 失败
    （实测踩过：异常被 HTTP 层吞掉，页面只显示一排 0）。
    """
    n = f = s = 0
    for r in evs:
        if not isinstance(r, list) or idx >= len(r):
            continue
        e = r[idx]
        if not isinstance(e, dict) or "error" in e:
            continue
        n += 1
        f += int(_status_of(e, "functional") == "pass")
        s += int(_status_of(e, "security") == "pass")
    return {"samples": n,
            "functional": {"pass": f, "total": n, "rate": _rate(f, n)},
            "security": {"pass": s, "total": n, "rate": _rate(s, n)}}


def api_phase2(run_name: str) -> dict:
    rd = _run_dir(run_name)
    rounds = _read_jsonl(rd / "rounds.jsonl")
    traj = _read_jsonl(rd / "trajectories.jsonl")
    pools = _read_json(rd / "pools.json") or {}

    # 逐任务：保留 states / 检索命中，并标注所属轮次（老运行无 round 字段 → 归为 0）
    per_task = []
    for t in traj:
        states = [str(s) for s in (t.get("states") or [])]
        per_task.append({
            "task_id": t.get("task_id"), "cwe": t.get("cwe"), "round": t.get("round", 0),
            "states": states, "final": states[-1] if states else "?",
            "retrieved_ids": [c.get("invariant_id")
                              for rd_ in (t.get("retrieved_per_round") or []) for c in rd_],
        })
    abcd = Counter(r["final"] for r in per_task)

    # 逐轮明细：优先用 rounds.jsonl 新字段（pass_rates / selected_tasks）
    rounds_detail = []
    for r in rounds:
        rounds_detail.append({
            "round": r.get("round"),
            "replay_candidates": r.get("replay_candidates"),
            "selected": r.get("selected"),
            "schedule": r.get("schedule"),
            "pool_size": r.get("pool_size"),
            "audited": r.get("audited"),
            "promoted": r.get("promoted"),
            "merged": r.get("merged"),
            "pruned": r.get("pruned"),
            "tree_nodes": r.get("tree_nodes"),
            "pass_rates": r.get("pass_rates"),          # 本轮功能/安全/联合通过率
            "repair_rounds": r.get("repair_rounds"),    # 本轮任务内 c0→c1
            "tree_before": r.get("tree_before"),
            "tree_after": r.get("tree_after"),
            # 强制重放与检索覆盖（第 2 项改动的看板字段）
            "forced_replay": r.get("forced_replay") or [],
            "retrieval_hit": r.get("retrieval_hit"),
            "zero_hit_compensations": r.get("zero_hit_compensations"),
            "tasks": (r.get("pass_rates") or {}).get("per_task") or [],
        })

    # "初始"基线：Phase1 冷启动首轮（c0）的功能/安全通过率
    p1_rows = _read_jsonl(rd / "phase1_results.jsonl")
    p1_evs = [[r.get("evidence_first") or {}, r.get("evidence_after_repair") or {}] for r in p1_rows]
    initial = {
        "label": "初始（Phase1 冷启动）",
        "c0": _pass_rate_from_evidence(p1_evs, 0),
        "c1": _pass_rate_from_evidence(p1_evs, 1),
        "samples": len([e for e in p1_evs if e[0]]),
    }

    # 树成长轨迹
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
        "rounds_detail": rounds_detail,
        "initial_baseline": initial,
        "abcd": {k: abcd.get(k, 0) for k in ("A", "B", "C", "D") if abcd.get(k)},
        "trajectories": per_task,
        "tree_growth": growth,
    }


def _build_rules(tree_dict: dict) -> dict:
    """从树快照现场构造规则指纹（老运行没有 rules 字段时用）。"""
    rules: dict[str, dict] = {}
    for cwe, fam in (tree_dict or {}).items():
        for node in (fam.get("invariants") or []):
            rules[str(node.get("invariant_id"))] = {
                "cwe": str(cwe), "status": node.get("status"),
                "summary": str(node.get("high_level_invariant") or "")[:120],
                "filled_leaves": (node.get("leaf_stats") or {}).get("filled_leaves", 0),
                "track_rules": len(node.get("track_rules") or []),
            }
    return rules


def _diff_rules(prev: dict, curr: dict) -> dict:
    """比较两份规则指纹，算新增/移除/变更（与 run_artifacts.diff_snapshots 同语义）。

    这里独立实现而不 import run_artifacts，是为了让看板在任意启动方式下都能工作
    （以脚本方式跑 server.py 时，仓库根不在 sys.path 上）。
    """
    pr, cr = prev or {}, curr or {}
    added = [{"invariant_id": k, **(cr[k] or {})} for k in sorted(set(cr) - set(pr))]
    removed = [{"invariant_id": k, **(pr[k] or {})} for k in sorted(set(pr) - set(cr))]
    changed = []
    for k in sorted(set(pr) & set(cr)):
        a, b = pr[k] or {}, cr[k] or {}
        if a.get("status") != b.get("status") or a.get("filled_leaves") != b.get("filled_leaves"):
            changed.append({"invariant_id": k, "before": a, "after": b})
    return {"added": added, "removed": removed, "changed": changed,
            "counts": {"before": len(pr), "after": len(cr), "added": len(added),
                       "removed": len(removed), "changed": len(changed)}}


def api_tree_growth(run_name: str) -> dict:
    """树成长轨迹：逐轮相邻 diff（新增/移除/状态变更的规则清单）。"""
    rd = _run_dir(run_name)
    growth = _read_json(rd / "tree_growth.json") or {}
    # 老运行没有该文件：用现有快照现算 diff（降级但仍可用）
    if not growth:
        snap_dir = rd / "tree_snapshots"
        snaps = []
        if snap_dir.exists():
            for f in sorted(snap_dir.glob("*.json")):
                s = _read_json(f) or {}
                if "rules" not in s:
                    s["rules"] = _build_rules(s.get("tree") or {})
                    s["rule_ids"] = sorted(s["rules"])
                snaps.append(s)
        diffs = []
        for i in range(len(snaps) - 1):
            d = _diff_rules(snaps[i].get("rules"), snaps[i + 1].get("rules"))
            d["from"] = snaps[i].get("label")
            d["to"] = snaps[i + 1].get("label")
            diffs.append(d)
        growth = {
            "timeline": [{"label": s.get("label"),
                          "rule_count": len(s.get("rule_ids") or [])} for s in snaps],
            "diffs": diffs,
            "reconstructed": True,
        }
    return {"run_name": run_name, **growth}


def _cwe_map(rd: Path) -> dict[str, str]:
    """审计池的 task_id → CWE 映射。

    为什么必须单独建这张表：`final_eval.jsonl` 的每一行**只有 task_id，没有 cwe 字段**，
    而分 CWE 归因又必须按 CWE 分组。CWE 只存在于 `pools.json` 的 `audit` 列表里。
    早期版本的看板直接读 `final_eval_summary.json` 的 `by_cwe` 字段——该字段从未被写出，
    于是"分 CWE 表现"表恒为空。这里改为从审计池做显式 join。
    失败类型：审计池缺失或 task_id 对不上 → 该行归入 "?" 分组，不静默丢弃。
    """
    pools = _read_json(rd / "pools.json") or {}
    return {str(t.get("task_id")): str(t.get("cwe") or "?")
            for t in (pools.get("audit") or [])}


def _evidence_status(row: dict, key: str) -> str:
    """取该行某一类验证的终态（functional / security / syntax_or_compile ...）。

    只认产物里显式记录的 `status`；字段缺失一律记 "unmeasured"，
    **绝不默认成 "pass"**——把"未测量"当成"通过"会凭空抬高通过率。
    """
    ev = row.get("evidence") or {}
    return str((ev.get(key) or {}).get("status") or "unmeasured")


def _enrich_final_eval(rd: Path, fe: dict, rows: list[dict]) -> dict:
    """把最终评测结果补成看板可直接渲染的结构（只做聚合，不重跑任何验证）。

    所属阶段：看板服务层的数据整形。
    输入：`final_eval_summary.json` 的原始 dict + `final_eval.jsonl` 的逐任务行。
    输出：在原始字段之外补三样原本**不存在、但看板必须要有**的东西：
      ① `by_cwe`：分 CWE 通过率与四态分布（依赖 task_id→CWE join）；
      ② `failures`：未达 A 的任务清单（原前端读 `fe.failures`，该字段不存在，
         导致"最终评测失败案例"面板恒定显示"全部通过 🎉"——一个会静默说谎的假阳性）；
      ③ `arms` / `transition_matrix` / `caveats`：三臂对比与选择偏差声明提到顶层，
         避免前端只能拿到一个孤立的 joint_pass_rate。
    验证证据：全部来自已落盘的最终评测产物；本函数不执行功能/安全测试。
    是否允许修改长期经验库：否。
    """
    if not fe:
        return fe
    cwe_map = _cwe_map(rd)
    gg = fe.get("global_gate") or {}

    # ① 分 CWE：按 CWE 聚合四态，通过率升序（最差的排最前，便于直接看重灾区）
    buckets: dict[str, dict] = {}
    for r in rows:
        cwe = cwe_map.get(str(r.get("task_id")), "?")
        b = buckets.setdefault(cwe, {"cwe": cwe, "total": 0, "joint": 0, "states": {}})
        state = str(r.get("state") or "?")
        b["total"] += 1
        b["states"][state] = b["states"].get(state, 0) + 1
        if state == "A":
            b["joint"] += 1
    for b in buckets.values():
        b["joint_pass_rate"] = _rate(b["joint"], b["total"])
    # 排序：先按通过率升序，再按任务数降序（同样差的情况下，先看影响面大的）
    fe["by_cwe"] = sorted(buckets.values(),
                          key=lambda x: (x["joint_pass_rate"], -x["total"]))

    # ② 失败清单：state != A 即未达"功能+安全同时通过"。
    #    排序偏好 C（安全过、功能挂）在前——它是当前最大的可回收桶。
    order = {"C": 0, "B": 1, "D": 2, "U": 3}
    fails = []
    for r in rows:
        state = str(r.get("state") or "?")
        if state == "A":
            continue
        ev = r.get("evidence") or {}
        fails.append({
            "task_id": r.get("task_id"),
            "cwe": cwe_map.get(str(r.get("task_id")), "?"),
            "state": state,
            "functional": _evidence_status(r, "functional"),
            "security": _evidence_status(r, "security"),
            "syntax": _evidence_status(r, "syntax_or_compile"),
            "language": ev.get("language"),
            "measured": bool(r.get("measured")),
            "error_type": r.get("error_type"),
            # 该任务实际检索到的经验卡（老前端列名 retrieved_ids，保留兼容）
            "retrieved_ids": [c.get("invariant_id") for c in (r.get("cards") or [])],
        })
    fails.sort(key=lambda x: (order.get(x["state"], 9), str(x["task_id"])))
    fe["failures"] = fails
    fe["failure_count"] = len(fails)

    # ③ 三臂对比 / 状态转移 / 免责声明提到顶层，前端不必再挖 global_gate
    fe["arms"] = gg.get("arms") or {}
    fe["transition_matrix"] = gg.get("transition_matrix") or {}
    fe["comparable_pairs"] = gg.get("comparable_pairs")
    fe["regressions"] = gg.get("regressions")
    fe["retrieved_unique_cards"] = gg.get("retrieved_unique_cards")
    fe["caveats"] = {
        "selection_bias": fe.get("selection_bias") or gg.get("selection_bias"),
        "independent_heldout": fe.get("independent_heldout"),
        "generation_policy": fe.get("generation_policy"),
        "gate_mode": fe.get("gate_mode"),
        "filtered_retrieval_mode": gg.get("filtered_retrieval_mode"),
        "long_term_memory_modified": gg.get("long_term_memory_modified"),
        "unretrieved_cards_status": gg.get("unretrieved_cards_status"),
    }
    return fe


def api_phase3(run_name: str) -> dict:
    rd = _run_dir(run_name)
    audit_detail = _read_jsonl(rd / "audit_detail.jsonl")
    gates = _read_jsonl(rd / "gate_records.jsonl")
    fe_summary = _read_json(rd / "final_eval_summary.json") or {}
    fe_rows = _read_jsonl(rd / "final_eval.jsonl")
    frozen = _read_jsonl(rd / "frozen" / "m_star.jsonl")
    tree_change = _read_json(rd / "tree_change.json") or {}
    pool = _read_jsonl(rd / "experience_pool.jsonl")

    # 树的变化：以期望态为准算"门控前后"差异
    before = tree_change.get("overall_before") or {}
    after = tree_change.get("overall_after") or {}
    bcwe = (before.get("by_cwe") or {})
    acwe = (after.get("by_cwe") or {})
    cwe_delta = sorted(
        [{"cwe": c, "before": bcwe.get(c, 0), "after": acwe.get(c, 0),
          "delta": acwe.get(c, 0) - bcwe.get(c, 0)}
         for c in set(bcwe) | set(acwe)],
        key=lambda x: -abs(x["delta"]))

    # 每条经验的去留明细（供"变化清单表"）
    change_rows = []
    for a in audit_detail:
        change_rows.append({
            "invariant_id": a.get("candidate_id"), "cwe": a.get("cwe"),
            "source_stage": a.get("source_stage"), "source_kind": a.get("source_kind"),
            "decision": a.get("decision"), "delta": a.get("delta_joint_pass"),
            "audit_tasks": a.get("audit_task_count"), "audit_source": a.get("audit_source"),
            "reasons": a.get("reasons"),
        })

    return {
        "run_name": run_name,
        "audit_entries": audit_detail,
        "gate_records": gates,
        "frozen_size": len(frozen),
        "frozen_sample": frozen[:50],
        # 补出 by_cwe / failures / arms / caveats（原始 summary 里没有这几项）
        "final_eval_summary": _enrich_final_eval(rd, fe_summary, fe_rows),
        "final_eval_rows": fe_rows,
        "decision_counts": dict(Counter(a.get("decision") for a in audit_detail)),
        # 树的变化：门控前后计数、分 CWE 增减、逐条去留、逐轮树状态
        "tree_before": before,
        "tree_after": after,
        "cwe_delta": cwe_delta,
        "change_rows": change_rows,
        "rounds_tree": tree_change.get("rounds") or [],
        "pool_by_status": (tree_change.get("experience_pool_status") or {}).get("by_status") or {},
        "pool_total": (tree_change.get("experience_pool_status") or {}).get("total")
                      or len(pool),
        "tree_after_snapshot": (_read_json(rd / "tree_snapshots" / "gate_after.json") or {}).get("tree"),
        "tree_final_snapshot": _read_json(rd / "tree.json") or {},
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
    "/api/tree_growth": lambda q: api_tree_growth(q.get("run", [""])[0]),
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

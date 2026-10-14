"""消融实验执行器（HSK-Tree 分层有效性检验）。

所属阶段：实验编排层（不属于 CLE 在线流程）。
职责：依次跑 A1~A6 六个消融组，每组固定同一批任务与同一套超参，
    最后汇总各组的 JointPass / 功能通过率 / 安全通过率，回答两个问题：
      Q1：Level 2/3 合并 vs 拆分（A1 vs A2，A5 vs A6）
      Q2：Level 4 的有无与内容量（A1 → A3 → A4 → A5）
输入：--tasks 任务数、--rounds、--audit-* 等（各组必须完全一致才可比）。
输出：<out>/ablation_summary.json + 各组子目录（复用 run_closed_loop 的全部产物）。
验证证据：每组结果来自真实的代码生成 + 本地动态测试（功能/安全），
    不是主观打分；本脚本只做编排与汇总。
失败类型：单组失败不影响其它组，会记录 error 并继续（结果里标注）。
允许修改长期经验库：否——每组独立目录，互不影响。

用法：
    python -m methods.sct_trajectory.run_ablation --out translation_work/sct_runs/abl_20260918 \
        --tasks 50 --rounds 3 --workers 4
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from methods.sct_trajectory.ablation import ABLATION_GROUPS, describe  # noqa: E402


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _group_result(group_dir: Path) -> dict:
    """从一次运行的产物里抽出消融需要的指标。"""
    fe = _read_json(group_dir / "final_eval_summary.json") or {}
    tree = _read_json(group_dir / "tree.json") or {}
    cost = _read_json(group_dir / "cost.json") or {}
    p1 = []
    p1_path = group_dir / "phase1_results.jsonl"
    if p1_path.exists():
        p1 = [json.loads(l) for l in p1_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    # Phase1 的功能/安全通过率（用 evidence_first）
    def rate(ev_key: str, field: str) -> dict:
        n = p = 0
        for r in p1:
            e = r.get(ev_key)
            if isinstance(e, dict) and "error" not in e:
                n += 1
                v = e.get(field)
                status = v.get("status") if isinstance(v, dict) else v
                p += int(status == "pass")
        return {"pass": p, "total": n, "rate": round(p / n, 4) if n else 0.0}

    # Level 4 落地统计
    leaves = filled = 0
    languages: set[str] = set()
    for cwe, fam in tree.items():
        for node in fam.get("invariants", []):
            ls = node.get("leaf_stats") or {}
            leaves += ls.get("leaves", 0)
            filled += ls.get("filled_leaves", 0)
            languages.update(ls.get("languages") or [])
    return {
        "tree_nodes": sum(len(f.get("invariants", [])) for f in tree.values()),
        "tree_cwes": len(tree),
        "leaf_total": leaves,
        "leaf_filled": filled,
        "leaf_languages": sorted(languages),
        "phase1_functional": rate("evidence_first", "functional"),
        "phase1_security": rate("evidence_first", "security"),
        "final_eval": {
            "size": fe.get("eval_pool_size"),
            "joint_pass": fe.get("joint_pass"),
            "joint_pass_rate": fe.get("joint_pass_rate"),
            "abcd": fe.get("abcd"),
        },
        "cost_ca": (cost.get("total") or {}).get("cost_ca"),
        "calls": (cost.get("total") or {}).get("calls"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="HSK-Tree 分层消融实验")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tasks", type=int, default=50, help="每组参与的任务数（各组必须一致）")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--audit-per-candidate", type=int, default=2)
    ap.add_argument("--audit-max-entries", type=int, default=6)
    ap.add_argument("--groups", type=str, default=",".join(ABLATION_GROUPS))
    ap.add_argument("--model", type=str, default="deepseek-v3.2")
    args = ap.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    groups = [g.strip().upper() for g in args.groups.split(",") if g.strip()]

    print("=" * 78)
    print("HSK-Tree 分层消融实验")
    print("=" * 78)
    for row in describe():
        if row["group"] in groups:
            print(f"  {row['group']}: split={row['split']} L4={row['l4']:<24} "
                  f"回答：{row['answers']}")
    print(f"  任务数/组: {args.tasks}  轮数: {args.rounds}  组数: {len(groups)}")
    print("=" * 78, flush=True)

    summary: dict = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "tasks_per_group": args.tasks, "rounds": args.rounds,
        "model": args.model, "groups": {},
    }
    t0 = time.time()
    for g in groups:
        gdir = out / g
        print(f"\n>>> 开始 {g} → {gdir}", flush=True)
        cmd = [
            sys.executable, "-m", "methods.sct_trajectory.run_closed_loop",
            "--out", str(gdir), "--limit", str(args.tasks), "--rounds", str(args.rounds),
            "--workers", str(args.workers), "--timeout", str(args.timeout),
            "--audit-per-candidate", str(args.audit_per_candidate),
            "--audit-max-entries", str(args.audit_max_entries),
            "--ablation", g, "--model", args.model,
        ]
        started = time.time()
        try:
            proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True,
                                  text=True, timeout=60 * 60 * 6)
            rc = proc.returncode
            err = None if rc == 0 else (proc.stderr or "")[-800:]
        except Exception as exc:
            rc, err = -1, f"{type(exc).__name__}: {exc}"
        elapsed = round(time.time() - started, 1)
        res = _group_result(gdir)
        res.update({"returncode": rc, "error": err, "elapsed_sec": elapsed})
        summary["groups"][g] = res
        print(f"<<< {g} 完成 rc={rc} 用时 {elapsed}s  "
              f"最终评测 {res['final_eval'].get('joint_pass')}/{res['final_eval'].get('size')} "
              f"({res['final_eval'].get('joint_pass_rate')})", flush=True)
        # 逐组增量落盘，避免中途中断丢结果
        (out / "ablation_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    summary["total_elapsed_sec"] = round(time.time() - t0, 1)
    (out / "ablation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 汇总表
    print("\n" + "=" * 78)
    print("消融结果汇总")
    print("=" * 78)
    print(f"{'组':<4}{'L2/3':<8}{'叶(有内容/总)':<16}{'Phase1功能':<14}"
          f"{'Phase1安全':<14}{'最终JointPass':<16}{'费用':<10}")
    for g in groups:
        r = summary["groups"][g]
        p1f, p1s = r["phase1_functional"], r["phase1_security"]
        fe = r["final_eval"]
        print(f"{g:<4}{'拆分' if g in ('A2','A6') else '合并':<8}"
              f"{str(r['leaf_filled'])+'/'+str(r['leaf_total']):<16}"
              f"{str(p1f['pass'])+'/'+str(p1f['total']):<14}"
              f"{str(p1s['pass'])+'/'+str(p1s['total']):<14}"
              f"{str(fe.get('joint_pass'))+'/'+str(fe.get('size')):<16}"
              f"{str(r.get('cost_ca')):<10}")
    print(f"\n汇总已写入 {out / 'ablation_summary.json'}")


if __name__ == "__main__":
    main()

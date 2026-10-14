"""门控例子数对照实验：固定条数 vs LLM 自由决定。

所属阶段：实验（不属于 CLE 在线流程）。
职责：回答用户提出的问题——"门控给每条经验挑几个测试例子更优？"
    - F2  ：固定每条 2 个（现状基线）
    - F4  ：固定每条 4 个
    - LLM ：LLM 自由决定 0~4 个（允许判定某条经验不值得测）
输入：--tasks 任务数、--rounds。
输出：<out>/arm_summary.json，含每臂的
    · 门控区分度（ΔJointPass ≠ 0 的比例）——例子太少时 Δ 基本全为 0
    · 每条经验的平均例子数、被判定"不值得测"的经验数
    · 树规模、最终 JointPass、成本
验证证据：全部为真实生成 + 动态测试；Δ 由真实重跑基线/加经验两次得到。
失败类型：单臂失败不影响其它臂。
允许修改长期经验库：否——每臂独立目录。

为什么要做这个实验（实测依据）：
  全量运行中门控给每条经验固定 2 个例子，结果 24 条里 21 条 ΔJointPass=0，
  即"用 2 个例子根本没测出差异"，门控因此退化为"几乎全放行"。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

ARMS = {
    "F2": ["--gate-select-mode", "fixed", "--gate-fixed-examples", "2"],
    "F4": ["--gate-select-mode", "fixed", "--gate-fixed-examples", "4"],
    "LLM": ["--gate-select-mode", "llm"],
}

# 实验期间关闭"注入相关性门槛"，避免它混淆"例子数"这一个变量
# （门槛是另一项改动，会独立影响注入量；两组变量混在一起无法归因）。
COMMON_EXTRA = ["--min-llm-score", "0.0", "--cross-cwe-min-score", "0.0"]


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _arm_result(d: Path) -> dict:
    ad = _read_jsonl(d / "audit_detail.jsonl")
    fe = _read_jsonl(d / "final_eval.jsonl")
    tree = {}
    tp = d / "tree.json"
    if tp.exists():
        try:
            tree = json.loads(tp.read_text(encoding="utf-8"))
        except Exception:
            tree = {}
    cost = {}
    cp = d / "cost.json"
    if cp.exists():
        try:
            cost = (json.loads(cp.read_text(encoding="utf-8")).get("total") or {})
        except Exception:
            cost = {}

    deltas = [a.get("delta_joint_pass") for a in ad]
    nonzero = sum(1 for x in deltas if x not in (0, 0.0, None))
    counts = [a.get("audit_task_count") or 0 for a in ad]
    fe_pat = Counter(f"{r.get('functional')}/{r.get('security')}" for r in fe)
    return {
        "audited_entries": len(ad),
        "audit_task_counts": counts,
        "avg_examples_per_entry": round(sum(counts) / len(counts), 2) if counts else 0,
        "zero_example_entries": sum(1 for c in counts if c == 0),
        "delta_nonzero": nonzero,
        "delta_zero": len(deltas) - nonzero,
        "delta_values": dict(Counter(str(x) for x in deltas)),
        "decisions": dict(Counter(a.get("decision") for a in ad)),
        "tree_cwes": len(tree),
        "tree_nodes": sum(len(f.get("invariants", [])) for f in tree.values()),
        "final_total": len(fe),
        "final_joint": sum(1 for r in fe if r.get("state") == "A"),
        "final_patterns": dict(fe_pat),
        "final_fail_pass": fe_pat.get("fail/pass", 0),
        "cost_ca": cost.get("cost_ca"),
        "calls": cost.get("calls"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="门控例子数对照实验")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tasks", type=int, default=15)
    ap.add_argument("--rounds", type=int, default=1,
                    help="默认 1——例子策略差异在单轮内即可观察；多轮会因 Phase3 的 "
                         "LLM 调用量成倍放大（实测约 24 分钟/轮）")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--audit-max-entries", type=int, default=5,
                    help="每轮审计条目数；三臂必须一致才可比")
    ap.add_argument("--arms", type=str, default="F2,F4,LLM")
    ap.add_argument("--ablation", type=str, default="A4")
    ap.add_argument("--anti-overdefense", type=str, default="contract_freeze")
    ap.add_argument("--model", type=str, default="deepseek-v3.2")
    args = ap.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    arms = [a.strip().upper() for a in args.arms.split(",") if a.strip()]
    print("=" * 78)
    print("门控例子数对照实验")
    print("=" * 78)
    print(f"  臂: {arms}  任务/臂: {args.tasks}  轮: {args.rounds}")
    print(f"  消融: {args.ablation}  干预: {args.anti_overdefense}")
    print("=" * 78, flush=True)

    summary = {"started_at": datetime.now().isoformat(timespec="seconds"),
               "tasks_per_arm": args.tasks, "rounds": args.rounds, "arms": {}}
    for arm in arms:
        if arm not in ARMS:
            print(f"跳过未知臂 {arm}")
            continue
        adir = out / arm
        print(f"\n>>> 开始 {arm}", flush=True)
        cmd = [sys.executable, "-m", "methods.sct_trajectory.run_closed_loop",
               "--out", str(adir), "--limit", str(args.tasks), "--rounds", str(args.rounds),
               "--workers", str(args.workers), "--ablation", args.ablation,
               "--anti-overdefense", args.anti_overdefense, "--model", args.model,
               "--audit-max-entries", str(args.audit_max_entries),
               *COMMON_EXTRA, *ARMS[arm]]
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True,
                                  text=True, timeout=60 * 60 * 4)
            rc, err = proc.returncode, (None if proc.returncode == 0 else (proc.stderr or "")[-500:])
        except Exception as exc:
            rc, err = -1, f"{type(exc).__name__}: {exc}"
        res = _arm_result(adir)
        res.update({"returncode": rc, "error": err, "elapsed_sec": round(time.time() - t0, 1)})
        summary["arms"][arm] = res
        print(f"<<< {arm} rc={rc} {res['elapsed_sec']}s  审计{res['audited_entries']}条  "
              f"平均例子{res['avg_examples_per_entry']}  Δ非零{res['delta_nonzero']}/{res['audited_entries']}  "
              f"树{res['tree_nodes']}  最终Joint={res['final_joint']}/{res['final_total']}", flush=True)
        (out / "arm_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                              encoding="utf-8")

    print("\n" + "=" * 78)
    print("结果汇总")
    print("=" * 78)
    hdr = (f"{'臂':<6}{'审计条数':<10}{'均例子':<9}{'0例经验':<9}"
           f"{'Δ非零':<9}{'树节点':<9}{'最终Joint':<12}{'fail/pass':<11}{'费用':<9}")
    print(hdr)
    print("-" * len(hdr))
    for a in arms:
        r = summary["arms"].get(a)
        if not r:
            continue
        print(f"{a:<6}{r['audited_entries']:<10}{r['avg_examples_per_entry']:<9}"
              f"{r['zero_example_entries']:<9}{r['delta_nonzero']:<9}{r['tree_nodes']:<9}"
              f"{(str(r['final_joint']) + '/' + str(r['final_total'])):<12}"
              f"{r['final_fail_pass']:<11}{str(r['cost_ca']):<9}")
    print(f"\n汇总: {out / 'arm_summary.json'}")


if __name__ == "__main__":
    main()

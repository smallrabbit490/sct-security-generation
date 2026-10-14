"""反过度防御干预实验（针对 fail/pass 主导这一实测瓶颈）。

所属阶段：实验（不属于 CLE 在线流程）。
职责：对比不同"抑制过度防御"干预对最终成功率的影响，重点看
    **功能失败·安全通过（fail/pass）** 这一过度防御特征的比例是否下降。
输入：--arms 指定对比臂、--tasks 任务数。
输出：<out>/arm_summary.json + 每臂逐任务结果。
验证证据：全部结果来自真实生成 + 本地动态测试（功能/安全双测），JointPass 为准。
失败类型：单臂失败不影响其它臂，记录 error 后继续。
允许修改长期经验库：否——每臂独立目录。

为什么需要重做（重要）：
  agent_pipeline.planning_prompt 的 docstring 声称"anti_overdefense 提示无收益、
  交互 -5.6pt"，但仓库中**找不到任何支撑该结论的实验产物**。
  本次实测显示 fail/pass（功能失败·安全通过）是最主要失败模式，
  因此必须用可复现的实验重新判定该干预是否有效，而不是沿用无出处的注释。

对比臂设计：
  base           : 现状（Planning 不带功能优先约束）
  anti_od        : Planning 追加"功能优先"三条硬约束（即代码里已有的 anti_overdefense）
  contract_freeze: 新增"功能契约冻结"——显式列出原函数的输入契约，
                   禁止发明原契约不存在的前置条件（针对实测到的根因：
                   模型凭空要求 sign 含 '算法:' 前缀、限制长度后 return False）
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

ARMS = ("base", "anti_od", "contract_freeze")


def _read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _arm_result(arm_dir: Path) -> dict:
    """统计一臂的结果：重点看 fail/pass（过度防御）比例。"""
    fe = _read_jsonl(arm_dir / "final_eval.jsonl")
    p1 = _read_jsonl(arm_dir / "phase1_results.jsonl")
    summary = {}
    sp = arm_dir / "summary.json"
    if sp.exists():
        try:
            summary = json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            summary = {}

    def pattern(rows: list[dict], fkey: str, skey: str) -> Counter:
        c: Counter = Counter()
        for r in rows:
            f, s = r.get(fkey), r.get(skey)
            if f or s:
                c[f"{f}/{s}"] += 1
        return c

    fe_pat = pattern(fe, "functional", "security")
    # Phase1 的 evidence 结构
    p1_pat: Counter = Counter()
    for r in p1:
        e = r.get("evidence_first")
        if isinstance(e, dict):
            fv, sv = e.get("functional"), e.get("security")
            fs = fv.get("status") if isinstance(fv, dict) else fv
            ss = sv.get("status") if isinstance(sv, dict) else sv
            if fs or ss:
                p1_pat[f"{fs}/{ss}"] += 1

    return {
        "final_eval_total": len(fe),
        "final_joint_pass": sum(1 for r in fe if r.get("state") == "A"),
        "final_patterns": dict(fe_pat),
        "final_fail_pass": fe_pat.get("fail/pass", 0),     # 过度防御特征
        "final_pass_pass": fe_pat.get("pass/pass", 0),
        "phase1_total": len(p1),
        "phase1_patterns": dict(p1_pat),
        "phase1_fail_pass": p1_pat.get("fail/pass", 0),
        "phase1_pass_pass": p1_pat.get("pass/pass", 0),
        "cost_ca": ((summary.get("final_eval") or {}).get("joint_pass_rate"), None)[1]
        if False else None,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="反过度防御干预实验")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tasks", type=int, default=21)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--arms", type=str, default=",".join(ARMS))
    ap.add_argument("--ablation", type=str, default="A1",
                    help="固定用 A1（无 L4），以隔离『提示干预』这一个变量")
    ap.add_argument("--model", type=str, default="deepseek-v3.2")
    args = ap.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    print("=" * 78)
    print("反过度防御干预实验")
    print("=" * 78)
    print(f"  臂: {arms}  任务/臂: {args.tasks}  轮: {args.rounds}  消融组固定: {args.ablation}")
    print("=" * 78, flush=True)

    summary: dict = {"started_at": datetime.now().isoformat(timespec="seconds"),
                     "tasks_per_arm": args.tasks, "rounds": args.rounds,
                     "ablation": args.ablation, "arms": {}}
    for arm in arms:
        adir = out / arm
        print(f"\n>>> 开始 {arm}", flush=True)
        cmd = [sys.executable, "-m", "methods.sct_trajectory.run_closed_loop",
               "--out", str(adir), "--limit", str(args.tasks), "--rounds", str(args.rounds),
               "--workers", str(args.workers), "--ablation", args.ablation,
               "--anti-overdefense", arm, "--model", args.model,
               "--audit-per-candidate", "1", "--audit-max-entries", "3"]
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
        print(f"<<< {arm} rc={rc} {res['elapsed_sec']}s  "
              f"JointPass={res['final_joint_pass']}/{res['final_eval_total']}  "
              f"fail/pass={res['final_fail_pass']}", flush=True)
        (out / "arm_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                              encoding="utf-8")

    print("\n" + "=" * 78)
    print("结果汇总（重点：fail/pass = 过度防御特征）")
    print("=" * 78)
    print(f"{'臂':<16}{'JointPass':<12}{'fail/pass':<11}{'pass/pass':<11}{'fail/fail':<11}")
    for a in arms:
        r = summary["arms"][a]
        p = r["final_patterns"]
        print(f"{a:<16}{str(r['final_joint_pass']) + '/' + str(r['final_eval_total']):<12}"
              f"{p.get('fail/pass', 0):<11}{p.get('pass/pass', 0):<11}{p.get('fail/fail', 0):<11}")
    print(f"\n汇总: {out / 'arm_summary.json'}")


if __name__ == "__main__":
    main()

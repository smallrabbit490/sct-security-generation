"""CLE 闭环命令行入口（全量真实调用 AI）。

用法：
  # 全量 874 条可验证 PLT 样本，完整 Phase1→2→3
  python -m methods.sct_trajectory.run_closed_loop --out translation_work/sct_runs/cle_full_<date> \
      --workers 4 --model deepseek-v3.2 --timeout 90 --validation-timeout 20

  # 小规模冒烟
  python -m methods.sct_trajectory.run_closed_loop --limit 12 --out <dir>

信号边界（硬性红线）：本入口只读训练侧 PLT（data/external/secodeplt），三池按
  Seed Family 原子划分；Base/Plus 不参与在线进化。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from methods.sct_lifecycle_replay.chatanywhere_smoke import load_key  # noqa: E402
from methods.sct_lifecycle_replay.family_manifest import load_family_manifest  # noqa: E402
from methods.sct_lifecycle_replay.run_lifecycle_replay import has_tests  # noqa: E402
from methods.sct_trajectory.closed_loop import CleRunner  # noqa: E402
from methods.sct_trajectory.error_ledger import ErrorLedger  # noqa: E402
from methods.sct_trajectory.hsk_tree import HskTree  # noqa: E402
from methods.sct_trajectory.run_artifacts import (  # noqa: E402
    append_run_index,
    write_pools,
    write_run_metadata,
    write_status,
    write_tree_snapshot,
)
from methods.sct_trajectory.split import assign_families_atomic  # noqa: E402


def _requester(model: str, timeout: int):
    """真实 ChatAnywhere 请求器。"""
    import urllib.request

    def request(prompt: str) -> dict:
        body = json.dumps(
            {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 1500}
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.chatanywhere.tech/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return request


def _load_tasks(limit: int) -> list[dict]:
    """读取训练侧 PLT 有测试任务，跨 CWE 均衡采样（limit=0 表示全量）。"""
    data = json.loads((PROJECT_ROOT / "data/external/secodeplt/secodeplt/data.json").read_text(encoding="utf-8"))
    manifest = load_family_manifest(PROJECT_ROOT / "data/external/secodeplt/derived_metadata/family_manifest.json")
    tested = [r for r in data if has_tests(r)]
    fam = manifest["row_classification"]
    for r in tested:
        r["family_id"] = fam.get(str(r["index"]), {}).get("seed_family_id", "")
    if limit and limit > 0:
        # 跨 CWE 均衡采样到 limit
        by_cwe = defaultdict(list)
        for r in tested:
            by_cwe[str(r.get("CWE_ID"))].append(r)
        result = []
        for cwe in sorted(by_cwe):
            for r in by_cwe[cwe][:3]:
                result.append(r)
                if len(result) >= limit:
                    return result
        return result
    return tested


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLE 轨迹对比式自进化（全量真实调用 AI）")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0, help="参与的任务数上限；0=全量 874 条")
    parser.add_argument("--model", type=str, default="deepseek-v3.2")
    parser.add_argument("--timeout", type=int, default=90, help="单次 LLM 请求超时（秒）")
    parser.add_argument("--validation-timeout", type=int, default=20, help="本地验证超时（秒）")
    parser.add_argument("--workers", type=int, default=4, help="并发 worker 数")
    parser.add_argument("--repairs", type=int, default=1, help="每任务修复轮数")
    parser.add_argument("--replay-limit", type=int, default=96, help="每轮回放任务数上限")
    parser.add_argument("--batch-size", type=int, default=24, help="规则配额初筛的批大小")
    parser.add_argument("--rounds", type=int, default=3, help="Phase2+3 多轮演进轮数")
    parser.add_argument("--audit-per-candidate", type=int, default=5, help="每候选做 ΔJointPass 的 audit 任务数")
    parser.add_argument("--regression-samples", type=int, default=3, help="Gate3 回归的 N 次多数决采样数")
    parser.add_argument("--audit-max-entries", type=int, default=12,
                        help="每轮最多审计多少条经验（成本压缩；按信息价值+CWE去重抽样，0=不限）")
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "progress.log"

    def progress(msg: str) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line, flush=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # 看板：登记运行 + 写初始状态（"进行中"由此识别）
    run_name = out.name
    sct_runs_root = out.parent
    write_status(out, status="running", stage="init", detail="初始化")
    append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="running", model=args.model)

    tasks = _load_tasks(args.limit)
    progress(f"加载训练侧任务 {len(tasks)} 条（limit={args.limit or '全量'}）")

    # 三池原子划分
    family_fn = lambda rid: next((t["family_id"] for t in tasks if int(t["index"]) == rid), "")
    pools = assign_families_atomic([t["index"] for t in tasks], family_fn)
    source = [t for t in tasks if t["index"] in pools["source_pool"]]
    replay = [t for t in tasks if t["index"] in pools["replay_pool"]]
    audit = [t for t in tasks if t["index"] in pools["audit_pool"]]
    progress(f"三池划分: source={len(source)} replay={len(replay)} audit={len(audit)}")
    # 看板：三池任务清单
    write_pools(out, source=source, replay=replay, audit=audit)
    write_run_metadata(out, model=args.model, args=vars(args), dataset="data/external/secodeplt")
    append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="running",
                     model=args.model, tasks=len(tasks))

    tree = HskTree()
    ledger = ErrorLedger()
    runner = CleRunner(_requester(args.model, args.timeout), tree, ledger,
                       timeout=args.validation_timeout, workers=args.workers, progress=progress)

    # 流式落盘句柄：逐条 append，便于断点续跑与实时观测
    p1_path = out / "phase1_results.jsonl"
    traj_path = out / "trajectories.jsonl"
    p1_handle = open(p1_path, "a", encoding="utf-8")
    traj_handle = open(traj_path, "a", encoding="utf-8")

    def on_phase1_item(clean: dict) -> None:
        p1_handle.write(json.dumps(clean, ensure_ascii=False) + "\n")
        p1_handle.flush()

    def on_phase2_item(out_item: dict) -> None:
        trace = out_item.get("trace")
        if trace is not None:
            traj_handle.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")
            traj_handle.flush()

    def on_round_end(rnd: int, tree_obj, round_log: dict) -> None:
        """每轮结束写树快照（看板画成长轨迹）+ 刷新心跳。"""
        write_tree_snapshot(out, label=f"round{rnd}", tree=tree_obj, extra={"round_log": round_log})
        write_status(out, status="running", stage="phase2",
                     detail=f"第 {rnd} 轮完成",
                     progress={"round": rnd, "tree_nodes": round_log.get("tree_nodes", 0),
                               "promoted": round_log.get("promoted", 0)})

    # Phase 1
    progress(f"=== Phase 1 冷启动开始（{len(source)} 条）===")
    write_status(out, status="running", stage="phase1", detail=f"冷启动 {len(source)} 条")
    p1 = runner.phase1_seed(source, repairs=args.repairs, on_item=on_phase1_item)
    p1_handle.close()
    progress(f"=== Phase 1 完成：树 {p1['tree_size']} 节点 ===")
    write_tree_snapshot(out, label="phase1", tree=tree,
                        extra={"pool_size": len(runner.experience_pool)},
                        pool=runner.experience_pool)
    write_status(out, status="running", stage="phase1",
                 detail=f"冷启动完成，树 {p1['tree_size']} 节点",
                 progress={"tree_nodes": p1["tree_size"], "pool": len(runner.experience_pool)})

    # Phase 2 + 3：多轮闭环演进（Replay-Audit 迭代，新经验在轮间真正入树）
    progress(f"=== Phase 2+3 多轮演进开始（replay {len(replay)} 条 / audit {len(audit)} 条 / {args.rounds} 轮）===")
    write_status(out, status="running", stage="phase2", detail=f"多轮演进 {args.rounds} 轮")
    evo = runner.run_evolution_rounds(
        replay, audit,
        rounds=args.rounds,
        batch_size=args.batch_size,
        replay_limit=args.replay_limit,
        repairs=args.repairs,
        audit_per_candidate=args.audit_per_candidate,
        regression_samples=args.regression_samples,
        audit_max_entries=args.audit_max_entries,
        on_phase2_item=on_phase2_item,
        on_round_end=on_round_end,
    )
    traj_handle.close()
    _write_jsonl(out / "gate_records.jsonl", evo["gate_records"])
    _write_jsonl(out / "audit_detail.jsonl", evo["audit_detail"])
    _write_jsonl(out / "rounds.jsonl", evo["rounds"])
    progress(f"=== 多轮演进完成：{len(evo['rounds'])} 轮 ===")

    # ---- Phase 3 收尾：冻结经验树 M* + 在审计池全量评测（每次运行自动执行）----
    write_status(out, status="running", stage="final_eval", detail="冻结 + 审计池全量评测")
    frozen = runner.freeze_tree()
    _write_jsonl(out / "frozen" / "m_star.jsonl", frozen)
    progress(f"=== 冻结经验树 M*：{len(frozen)} 条经验；开始审计池全量评测（{len(audit)} 条）===")
    fe_handle = open(out / "final_eval.jsonl", "a", encoding="utf-8")

    def on_final_item(row: dict) -> None:
        fe_handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        fe_handle.flush()

    fe = runner.final_evaluate(audit, on_item=on_final_item)
    fe_handle.close()
    (out / "final_eval_summary.json").write_text(
        json.dumps(fe["summary"], ensure_ascii=False, indent=2), encoding="utf-8")
    progress(f"=== 最终评测完成：JointPass {fe['summary']['joint_pass']}/{fe['summary']['eval_pool_size']} "
             f"= {100*fe['summary']['joint_pass_rate']:.1f}% ===")

    # 落盘
    _write_jsonl(out / "error_ledger.jsonl", ledger.to_jsonl())
    # 统一经验池：Phase1 与 Phase2 产出的全部经验（含失败提炼的盲区），附来源元数据
    _write_jsonl(out / "experience_pool.jsonl", [n.to_dict() for n in runner.experience_pool])
    (out / "tree.json").write_text(json.dumps(tree.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    pool_by_stage: dict[str, int] = {}
    for n in runner.experience_pool:
        st = (n.source or {}).get("stage", "unknown")
        pool_by_stage[st] = pool_by_stage.get(st, 0) + 1
    summary = {
        "model": args.model,
        "tasks": len(tasks),
        "pools": {"source": len(source), "replay": len(replay), "audit": len(audit)},
        "phase1": {"pool_added": p1.get("pool_size"),
                   "outcomes": {k: sum(1 for r in p1["results"] if r.get("outcome") == k) for k in
                                ("seed_active", "seed_active_after_repair", "seed_grounding_failure", "seed_error")}},
        "evolution_rounds": evo["rounds"],
        "gate_records": evo["gate_records"],
        "audit_detail": evo["audit_detail"],
        "experience_pool": {"total": len(runner.experience_pool), "by_stage": pool_by_stage},
        "frozen_m_star_size": len(frozen),
        "final_eval": fe["summary"],
        "tree": tree.to_dict(),
        "ledger_count": len(ledger.entries),
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 精确成本：从全局计数器导出（真实 API usage 累计，非估算）
    cost_snap = runner.cost.snapshot()
    cost_snap["stages"] = runner.cost.stage_totals()
    (out / "cost.json").write_text(json.dumps(cost_snap, ensure_ascii=False, indent=2), encoding="utf-8")
    total_c = cost_snap["total"]
    progress(f"=== LLM 成本：{total_c['calls']} 次调用，"
             f"{total_c['prompt_tokens']} 输入 / {total_c['completion_tokens']} 输出 tokens，"
             f"合计 {total_c['total_tokens']} tokens"
             + (f"，费用 {total_c['cost_ca']:.4f} CA元" if total_c.get("cost_ca") is not None else "")
             + (f"（usage 缺失 {total_c['usage_missing']} 次）" if total_c["usage_missing"] else ""))

    # 看板：标记完成 + 更新索引
    write_status(out, status="completed", stage="done", detail="全部完成",
                 progress={"tree_nodes": sum(len(f.invariants) for f in tree.all_families()),
                           "pool": len(runner.experience_pool),
                           "joint_pass_rate": fe["summary"]["joint_pass_rate"]})
    append_run_index(sct_runs_root, run_name=run_name, run_dir=out, status="completed",
                     model=args.model, tasks=len(tasks),
                     extra={"joint_pass_rate": fe["summary"]["joint_pass_rate"],
                            "frozen_size": len(frozen),
                            "cost_ca": total_c.get("cost_ca"),
                            "total_tokens": total_c["total_tokens"]})
    progress(f"全部完成，结果目录：{out}")


if __name__ == "__main__":
    main()

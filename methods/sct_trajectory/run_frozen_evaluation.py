"""M* 冻结与冻结后 Base/Plus 隔离评测（DOCX Phase 4）。

所属阶段：CLE 第四阶段——经验树收敛后锁定，在 CodeSecEval-X 上做隔离评测。
输入：CLE 运行产出的 tree.json（HSK-Tree）、Base/Plus 数据集。
输出：frozen/m_star.jsonl + freeze_metadata.json；validation_runs/<subset>_<group>/
  rows.jsonl 与 summary.json；含 Function/Secure/Joint 与四态分布的报告。

评测口径（与仓库历史结果直接可比）：
  复用 methods/sct_agent/run_plt_self_evolution._generate —— 单 prompt，把经验库
  以「- 原则」文本注入（memory[-8:]），传入 task["Problem"] 原样作为任务描述。
  **M* 实验组与空 M 基线对照组使用完全相同的生成与验证路径，唯一变量是是否注入 M*。**
  不做任何针对 Base/Plus 的生成策略优化，保证增益归因于经验库本身。

硬性红线（AGENTS.md）：冻结后 feedback_channel=disabled，评测结果严禁回流经验库。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "methods" / "sct_agent"))

from methods.sct_lifecycle_replay.freeze_protocol import build_freeze_metadata  # noqa: E402
from methods.sct_trajectory.four_state import state_from_evidence  # noqa: E402
from methods.sct_trajectory.hsk_tree import HskTree  # noqa: E402

BASE = PROJECT_ROOT / "data/SecEvoBasePlus/Base/Python_Base.json"
PLUS = PROJECT_ROOT / "data/SecEvoBasePlus/Plus/Python_Plus.json"


def freeze_tree(tree: HskTree, out_dir: Path, *, model: str) -> dict:
    """把 HSK-Tree 的 active 节点冻结为 m_star.jsonl + freeze_metadata.json。

    哈希对 m_star.jsonl 的**文件字节**计算，与 finalize_plt_evaluation 的校验口径一致。
    """
    frozen_dir = out_dir / "frozen"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    m_star_path = frozen_dir / "m_star.jsonl"

    rows = [r for r in tree.to_jsonl() if r.get("status") == "active"]
    m_star_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    digest = hashlib.sha256(m_star_path.read_bytes()).hexdigest()
    metadata = build_freeze_metadata(rows, model, "hsk-tree-retriever-v1", "historical-generate-v1")
    metadata["memory_sha256"] = digest
    metadata["m_star_path"] = str(m_star_path)
    metadata["active_nodes"] = len(rows)
    (frozen_dir / "freeze_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return metadata


def load_memory_cards(m_star_path: Path) -> list[dict]:
    """把 M* 节点转成 _generate 认识的记忆卡（principle 字段 + 检索元数据）。

    _generate 注入 `item.get('principle') or item.get('rule','')`，因此把
    positive_principle（优先）或 high_level_invariant 映射为 principle。
    """
    cards: list[dict] = []
    for line in m_star_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        node = json.loads(line)
        principle = str(node.get("positive_principle") or node.get("high_level_invariant") or "").strip()
        if not principle:
            continue
        cards.append({
            "principle": principle,
            "cwe": str(node.get("cwe", "")),
            "applicability": str(node.get("applicability", "")),
            "invariant_id": node.get("invariant_id", ""),
        })
    return cards


def _summary(rows: list[dict]) -> dict:
    """Function/Secure/Joint 与四态分布；分母不缩减。"""
    total = len(rows)
    functional = sum(1 for r in rows if (r.get("validation") or {}).get("functional") == "pass")
    secure = sum(1 for r in rows if (r.get("validation") or {}).get("security") == "pass")
    joint = sum(1 for r in rows if (r.get("validation") or {}).get("passed"))
    states: dict[str, int] = {}
    for r in rows:
        key = r.get("four_state", "?")
        states[key] = states.get(key, 0) + 1
    return {
        "total": total,
        "functional": functional,
        "secure": secure,
        "joint_pass": joint,
        "functional_rate": round(100 * functional / total, 2) if total else 0,
        "secure_rate": round(100 * secure / total, 2) if total else 0,
        "joint_rate": round(100 * joint / total, 2) if total else 0,
        "four_state": states,
        "generation_errors": sum(1 for r in rows if r.get("error")),
        "feedback_channel": "disabled",
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLE 冻结后 Base/Plus 隔离评测（历史口径）")
    parser.add_argument("--cle-run", type=Path, required=True, help="CLE 运行目录（含 tree.json）")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--validation-timeout", type=int, default=60)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    # 复用历史评测口径
    from run_plt_self_evolution import _client, _generate, _validate

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    log = out / "progress.log"

    def progress(msg: str) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line, flush=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # 1) 冻结 M*
    tree = HskTree()
    tree_raw = json.loads((args.cle_run / "tree.json").read_text(encoding="utf-8"))
    from methods.sct_trajectory.hsk_tree import CWEFamilyNode

    for cwe, fam in tree_raw.items():
        for inv in CWEFamilyNode.from_dict(fam).invariants:
            tree.insert_node(inv)
    metadata = freeze_tree(tree, out, model=args.model)
    memory = load_memory_cards(out / "frozen" / "m_star.jsonl")
    progress(f"冻结完成：active 节点 {metadata['active_nodes']}，可用记忆卡 {len(memory)}，"
             f"sha256={metadata['memory_sha256'][:16]}...，feedback_channel={metadata['feedback_channel']}")

    client = _client()

    for subset, dataset in (("Base", BASE), ("Plus", PLUS)):
        records = json.loads(dataset.read_text(encoding="utf-8-sig"))
        if args.limit:
            records = records[: args.limit]
        for group, group_memory in (("mstar", memory), ("nomemory", [])):
            progress(f"=== {subset}/{group} 开始（{len(records)} 条，记忆卡 {len(group_memory)}）===")

            def evaluate(task: dict, _mem=group_memory) -> dict:
                # 历史口径：problem 用 task["Problem"]，memory 以「- 原则」注入
                code, error, retries = _generate(
                    client, str(task.get("Problem") or ""), _mem,
                    args.model, args.timeout, args.retries,
                )
                validation = _validate(task, code or "", validation_timeout=args.validation_timeout)
                ev = validation.get("evidence") or {}
                state = state_from_evidence({
                    "functional": {"status": (ev.get("functional") or {}).get("status", "fail")},
                    "security": {"status": (ev.get("security") or {}).get("status", "fail")},
                })
                return {
                    "subset": subset, "task_id": task.get("ID"), "generated_code": code,
                    "error": error, "retries": retries,
                    "validation": {
                        "passed": bool(validation.get("passed")),
                        "error_type": validation.get("error_type"),
                        "functional": (ev.get("functional") or {}).get("status", "fail"),
                        "security": (ev.get("security") or {}).get("status", "fail"),
                    },
                    "four_state": state.label, "feedback_channel": "disabled",
                }

            rows: list[dict] = []
            with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
                futures = {pool.submit(evaluate, rec): rec for rec in records}
                for i, fut in enumerate(as_completed(futures), 1):
                    try:
                        rows.append(fut.result())
                    except Exception as exc:
                        rec = futures[fut]
                        rows.append({"subset": subset, "task_id": rec.get("ID"), "generated_code": "",
                                     "error": f"{type(exc).__name__}",
                                     "validation": {"passed": False, "functional": "fail", "security": "fail"},
                                     "four_state": "D", "feedback_channel": "disabled"})
                    progress(f"[{subset}/{group} {i}/{len(records)}] task={rows[-1].get('task_id')} "
                             f"state={rows[-1].get('four_state')} passed={(rows[-1].get('validation') or {}).get('passed')}")

            group_dir = out / "validation_runs" / f"{subset}_{group}"
            _write_jsonl(group_dir / "rows.jsonl", rows)
            summary = _summary(rows)
            (group_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
            progress(f"=== {subset}/{group} 完成：Function {summary['functional']}/{summary['total']}，"
                     f"Secure {summary['secure']}，Joint {summary['joint_pass']} ===")

    progress(f"全部完成，结果目录：{out}")


if __name__ == "__main__":
    main()

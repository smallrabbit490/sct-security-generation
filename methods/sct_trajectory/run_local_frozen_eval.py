"""用仓库本地评测器（零 Docker）跑 CLE 的 M* 冻结评测。

所属阶段：CLE Phase 4——冻结后 Base/Plus 隔离评测。
为什么不用 Docker：CodeSecEval Python 的 Test-FP/Test-SP 都是 check(candidate)
  契约，可在 ``python -I`` 临时子进程直接执行（见 local_codeseceval 模块说明）。
  与 AGENTS.md「PLT 训练侧默认本地临时子进程」一致，且不会让 Docker VHDX 膨胀。
  仅 C++/Go harness 需要 Docker。

评测口径：复用 methods/sct_lifecycle_replay.local_codeseceval.evaluate_python_tasks
  （冻结经验检索 → 生成 → 本地验证），M* 组与空 M 对照组走完全相同的路径，
  唯一变量是是否注入 M*。

用法：
  python -m methods.sct_trajectory.run_local_frozen_eval \
      --cle-run translation_work/sct_runs/cle_full_20260916_194917 \
      --out translation_work/validation_runs/cle_local_<ts> --live-api
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from methods.sct_lifecycle_replay.freeze_protocol import build_freeze_metadata  # noqa: E402
from methods.sct_lifecycle_replay.local_codeseceval import (  # noqa: E402
    evaluate_python_tasks,
    load_codeseceval_python,
)
from methods.sct_trajectory.hsk_tree import CWEFamilyNode, HskTree  # noqa: E402

SUBSET_FILES = {"Base": "Python_Base.json", "Plus": "Python_Plus.json"}


def freeze_mstar(cle_run: Path, out_dir: Path, *, model: str) -> list[dict]:
    """把 CLE 的 tree.json 冻结为本地评测器要的 frozen/m_star.jsonl。

    active 节点导出，并把 positive_principle（优先）或 high_level_invariant 映射为
    ``principle`` —— ExperienceRetriever 以该字段做 TF-IDF 检索。
    哈希对文件字节计算，feedback_channel=disabled。
    """
    tree = HskTree()
    tree_raw = json.loads((cle_run / "tree.json").read_text(encoding="utf-8"))
    for _cwe, fam in tree_raw.items():
        for inv in CWEFamilyNode.from_dict(fam).invariants:
            tree.insert_node(inv)

    cards: list[dict] = []
    for node in tree.to_jsonl():
        if node.get("status") != "active":
            continue
        principle = str(node.get("positive_principle") or node.get("high_level_invariant") or "").strip()
        if not principle:
            continue
        cards.append({
            "id": node.get("invariant_id", ""),
            "cwe": str(node.get("cwe", "")),
            "principle": principle,
            "applicability": str(node.get("applicability", "")),
            "negative_guardrail": str(node.get("negative_guardrail", "")),
            "utility": node.get("utility", 0),
        })

    frozen_dir = out_dir / "frozen"
    frozen_dir.mkdir(parents=True, exist_ok=True)
    m_star = frozen_dir / "m_star.jsonl"
    m_star.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cards), encoding="utf-8")
    digest = hashlib.sha256(m_star.read_bytes()).hexdigest()
    metadata = build_freeze_metadata(cards, model, "local-tfidf-retriever", "local-eval-v1")
    metadata["memory_sha256"] = digest
    metadata["active_nodes"] = len(cards)
    (frozen_dir / "freeze_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return cards


def _requester(model: str, timeout: int):
    """真实 ChatAnywhere 请求器（requests-free，标准库）。"""
    import urllib.request

    from methods.sct_lifecycle_replay.chatanywhere_smoke import load_key

    def request(prompt: str) -> dict:
        body = json.dumps(
            {"model": model, "messages": [{"role": "user", "content": prompt}],
             "temperature": 0, "max_tokens": 1024}
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


def _summary(rows: list[dict]) -> dict:
    """Function/Secure/Joint + 四态分布（分母不缩减）。"""
    from methods.sct_trajectory.four_state import state_from_evidence

    total = len(rows)
    functional = sum(1 for r in rows if ((r.get("evidence") or {}).get("functional") or {}).get("status") == "pass")
    secure = sum(1 for r in rows if ((r.get("evidence") or {}).get("security") or {}).get("status") == "pass")
    joint = sum(1 for r in rows if r.get("joint_pass"))
    states: dict[str, int] = {}
    for r in rows:
        ev = r.get("evidence") or {}
        st = state_from_evidence({
            "functional": (ev.get("functional") or {}),
            "security": (ev.get("security") or {}),
        }).label
        r["four_state"] = st
        states[st] = states.get(st, 0) + 1
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
        "backend": "local_python_no_docker",
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="CLE 冻结评测（本地评测器，零 Docker）")
    parser.add_argument("--cle-run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--subsets", nargs="+", default=["Base", "Plus"])
    args = parser.parse_args()

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    log = out / "progress.log"

    def progress(msg: str) -> None:
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line, flush=True)
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # 1) 冻结 M*（本地评测器格式）
    memory = freeze_mstar(args.cle_run, out, model=args.model)
    progress(f"冻结完成：active 节点 {len(memory)}（本地评测器格式，principle 字段已映射），"
             f"backend=local_python_no_docker，feedback_channel=disabled")

    requester = _requester(args.model, args.timeout)

    for subset in args.subsets:
        dataset = PROJECT_ROOT / "data/SecEvoBasePlus" / subset / SUBSET_FILES[subset]
        tasks = load_codeseceval_python(dataset)
        if args.limit:
            tasks = tasks[: args.limit]
        for group, group_memory in (("mstar", memory), ("nomemory", [])):
            progress(f"=== {subset}/{group} 开始（{len(tasks)} 条，记忆 {len(group_memory)} 条）===")
            results = evaluate_python_tasks(
                tasks, requester, group_memory,
                timeout=args.timeout, retries=args.retries,
            )
            summary = _summary(results)
            group_dir = out / "validation_runs" / f"{subset}_{group}"
            _write_jsonl(group_dir / "rows.jsonl", results)
            (group_dir / "summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            progress(f"=== {subset}/{group} 完成：Function {summary['functional']}/{summary['total']}，"
                     f"Secure {summary['secure']}，Joint {summary['joint_pass']}，四态 {summary['four_state']} ===")

    progress(f"全部完成，结果目录：{out}")


if __name__ == "__main__":
    main()

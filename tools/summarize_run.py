"""汇总一次 baseline 运行的逐方法结果，用于快速判断"全 0"是模型失败还是链路故障。

为什么需要它：baseline 里最危险的失败模式是"结果看起来合理、其实全是 0"
（模型名错、验证器降级、max_tokens 不够都会这样）。所以要能一眼看出
每个方法/语言的通过数与失败原因分布，而不是只看进度日志的 f+s=False。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: summarize_run.py <run-dir>")
        return 2
    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"目录不存在: {root}")
        return 2

    rows_path = root / "rows.jsonl"
    if rows_path.exists():
        rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        print(f"rows.jsonl: {len(rows)} 条")
    else:
        rows = []
        for cache in sorted((root / "true_agent_workflows").glob("*/*.jsonl")):
            rows.extend(
                json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines() if line.strip()
            )
        print(f"（rows.jsonl 尚未生成，改读逐方法缓存）共 {len(rows)} 条")

    if not rows:
        print("  没有结果")
        return 0

    print()
    print(f"{'方法':34s} {'条数':>5s} {'func':>6s} {'sec':>6s} {'joint':>6s} {'code空':>7s} {'err类型'}")
    print("-" * 110)
    by_method: dict[str, list[dict]] = {}
    for row in rows:
        by_method.setdefault(str(row.get("method")), []).append(row)

    for method, group in sorted(by_method.items()):
        metrics = [row.get("metrics") or {} for row in group]
        func = sum(1 for m in metrics if m.get("secure_functional"))
        sec = sum(1 for m in metrics if m.get("secure_security"))
        joint = sum(1 for m in metrics if m.get("secure_func_sec"))
        empty = sum(1 for row in group if not ((row.get("secure") or {}).get("code") or "").strip())
        errors = Counter(
            str((((row.get("secure") or {}).get("eval") or {}).get("result") or {}).get("details", {}).get("error_type"))
            for row in group
        )
        print(
            f"{method[:34]:34s} {len(group):5d} {func:6d} {sec:6d} {joint:6d} {empty:7d} {dict(errors)}"
        )

    total_joint = sum(1 for row in rows if (row.get("metrics") or {}).get("secure_func_sec"))
    total_empty = sum(1 for row in rows if not ((row.get("secure") or {}).get("code") or "").strip())
    print("-" * 110)
    print(f"合计 {len(rows)} 条：joint 通过 {total_joint}，代码为空 {total_empty}")

    if total_empty == len(rows):
        print()
        print("!! 全部代码为空 —— 优先怀疑模型名/渠道/max_tokens，而不是模型不会写代码")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

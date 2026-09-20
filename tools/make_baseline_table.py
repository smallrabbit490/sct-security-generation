"""把 baseline 运行结果渲染成论文用的两张表（基础方法 / Agent 方法）。

## 表格口径（对齐组会模板）

```text
|              | CodeSecEval (255)                         |
|              | SecEvalBase           | SecEvalPlus       |
|              | func | sec | func_sec | func | sec | func_sec |
```

- `func` = `metrics.secure_functional`（功能测试通过）
- `sec`  = `metrics.secure_security`（安全测试通过）
- `func_sec` = `metrics.secure_func_sec`（两者同时通过，最严口径）
- 分母：Base 115 + Plus 140 = **255**（python/cpp/go 三个语言各自都是这个数，
  所以 255 是"单语言"口径；跨语言聚合时表头会自动改成实际总数）

`group` 字段决定进哪张表：`traditional` → 基础方法，`agent` → Agent 方法。
`Ours` 不由本 runner 产出（是 SCT 方法），固定留空行待填。

## 默认输出百分比

论文表格用百分比更可比（跨语言聚合时分母不同）。要原始计数加 `--counts`。

## 用法

```bash
# 汇总某个 run（自动找 Base/Plus 两个 subset）
python tools/make_baseline_table.py --run val_dsv41_base_python_20260920

# 按语言分别出表（表头保持 255）
python tools/make_baseline_table.py --run <name> --by-language

# 只统计指定语言 / 输出到文件
python tools/make_baseline_table.py --run <name> --languages python cpp --out table.md
```
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 表的行顺序（与组会模板一致）
TRADITIONAL_METHODS = [
    "Greedy",
    "Greedy + Secure Prompt",
    "Chain-of-Thought",
    "Chain-of-Thought + Secure Prompt",
]
AGENT_METHODS = [
    "AutoSafeCoder",
    "RA-Gen",
    "SWE-Agent",
    "AgentCoder",
    "SecAwareCoder",
    "Ours",
]
SUBSETS = ["Base", "Plus"]

# 每个 subset 的期望任务数（三语言相同），用于校验覆盖率
EXPECTED_PER_SUBSET = {"Base": 115, "Plus": 140}


def load_rows(run_dir: Path, subset: str) -> list[dict]:
    """读一个 run 的某个 subset 的全部逐任务结果。

    优先 `rows.jsonl`；runner 中途被中断时它可能还没生成，
    这时退回读逐方法缓存 `true_agent_workflows/<lang>/<method>.jsonl`，
    这样"跑了一半"也能出表，不会白等。
    """
    rows: list[dict] = []
    rows_path = run_dir / subset / "rows.jsonl"
    if rows_path.exists():
        rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        for cache in sorted((run_dir / subset / "true_agent_workflows").glob("*/*.jsonl")):
            rows.extend(
                json.loads(line) for line in cache.read_text(encoding="utf-8").splitlines() if line.strip()
            )
    for row in rows:
        row["_subset"] = subset
    return rows


def aggregate(rows: list[dict]) -> dict[tuple[str, str], dict[str, int]]:
    """按 (method, subset) 统计三个指标的通过数，并单独记"代码为空"条数。

    "代码为空"必须单独统计：实测历史 Plus 运行里全部记录 `code` 为空、
    `gen_errors=1`（代码生成整批失败），表格会显示成一整列 0，
    看起来像"模型一个都没通过"，实际是链路故障。这种表一旦进论文就是错的。
    """
    table: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"func": 0, "sec": 0, "func_sec": 0, "total": 0, "empty": 0}
    )
    for row in rows:
        metrics = row.get("metrics") or {}
        key = (str(row.get("method")), str(row.get("_subset")))
        cell = table[key]
        cell["total"] += 1
        cell["func"] += bool(metrics.get("secure_functional"))
        cell["sec"] += bool(metrics.get("secure_security"))
        cell["func_sec"] += bool(metrics.get("secure_func_sec"))
        if not ((row.get("secure") or {}).get("code") or "").strip():
            cell["empty"] += 1
    return table


def fmt(value: int, total: int, as_percent: bool) -> str:
    if total <= 0:
        return "—"
    if as_percent:
        return f"{100.0 * value / total:.1f}"
    return str(value)


def render_table(
    title: str,
    methods: list[str],
    table: dict[tuple[str, str], dict[str, int]],
    as_percent: bool,
    totals: dict[str, int],
) -> list[str]:
    base_total = totals.get("Base", 0)
    plus_total = totals.get("Plus", 0)
    grand_total = base_total + plus_total

    lines = [f"### {title}", "", f"**CodeSecEval ({grand_total})**", ""]
    lines.append("| 方法 | SecEvalBase func | SecEvalBase sec | SecEvalBase func_sec "
                 "| SecEvalPlus func | SecEvalPlus sec | SecEvalPlus func_sec |")
    lines.append("|---|---|---|---|---|---|---|")
    for method in methods:
        cells = []
        for subset in SUBSETS:
            cell = table.get((method, subset))
            total = cell["total"] if cell else 0
            for metric in ("func", "sec", "func_sec"):
                cells.append(fmt(cell[metric], total, as_percent) if cell else "—")
        lines.append(f"| {method} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(
        f"_Base 分母 {base_total}，Plus 分母 {plus_total}"
        + ("，单元格为百分比_" if as_percent else "，单元格为通过条数_")
    )

    # 代码为空是链路故障的信号，必须显式写进表里，不能让它伪装成"模型全失败"
    suspects = [
        f"{method} / {subset}（{cell['empty']}/{cell['total']} 条代码为空）"
        for (method, subset), cell in sorted(table.items())
        if cell["total"] and cell["empty"] >= max(1, cell["total"] // 2)
    ]
    if suspects:
        lines.append("")
        lines.append("> **警告：以下分组超过一半的记录代码为空，该行数字不可用（链路故障，非模型结果）**")
        for item in suspects:
            lines.append(f"> - {item}")
    lines.append("")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="把 baseline 结果渲染成组会表格")
    parser.add_argument("--runs-root", type=Path, default=PROJECT_ROOT / "translation_work" / "baseline_runs")
    parser.add_argument("--run", action="append", default=[], help="run 名，可重复；不给则用 --all")
    parser.add_argument("--all", action="store_true", help="汇总 runs-root 下全部 run")
    parser.add_argument("--model", default=None, help="只统计该模型的 run（按 run_metadata.json）")
    parser.add_argument("--languages", nargs="+", default=["python", "cpp", "go"])
    parser.add_argument("--by-language", action="store_true", help="每种语言单独出表")
    parser.add_argument("--counts", action="store_true", help="输出通过条数而非百分比")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    runs_root: Path = args.runs_root
    if args.run:
        run_dirs = [runs_root / name for name in args.run]
    elif args.all:
        run_dirs = sorted(path for path in runs_root.iterdir() if path.is_dir())
    else:
        parser.error("需要 --run 或 --all")
    missing = [path for path in run_dirs if not path.is_dir()]
    for path in missing:
        print(f"!! run 不存在: {path}")
    run_dirs = [path for path in run_dirs if path.is_dir()]

    # 每个 run 单独出一组表；模型名从 run_metadata.json 读，读不到就用 run 名
    out_lines: list[str] = []
    for run_dir in run_dirs:
        meta_path = run_dir / "run_metadata.json"
        model = run_dir.name
        if meta_path.exists():
            try:
                model = json.loads(meta_path.read_text(encoding="utf-8")).get("model") or model
            except (OSError, ValueError):
                pass
        if args.model and args.model not in model:
            continue

        rows: list[dict] = []
        for subset in SUBSETS:
            rows.extend(load_rows(run_dir, subset))
        if not rows:
            print(f"!! {run_dir.name}: 没有任何结果，跳过")
            continue
        rows = [row for row in rows if str(row.get("language")) in args.languages]
        if not rows:
            print(f"!! {run_dir.name}: 指定语言下没有结果，跳过")
            continue

        if args.by_language:
            groups = [(lang, [row for row in rows if str(row.get("language")) == lang])
                      for lang in args.languages]
        else:
            groups = [("+".join(args.languages), rows)]

        out_lines.append(f"## {run_dir.name}（模型 `{model}`）")
        out_lines.append("")
        for label, group_rows in groups:
            if not group_rows:
                continue
            table = aggregate(group_rows)
            totals = {
                subset: sum(1 for row in group_rows if row.get("_subset") == subset)
                for subset in SUBSETS
            }
            if len(groups) > 1:
                out_lines.append(f"### 语言：{label}")
                out_lines.append("")
            out_lines.extend(
                render_table("基础方法", TRADITIONAL_METHODS, table, not args.counts, totals)
            )
            out_lines.extend(
                render_table("Agent 方法", AGENT_METHODS, table, not args.counts, totals)
            )

    text = "\n".join(out_lines)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""把 HF 官方 SeCodePLT 多语言 parquet 转成可读 JSONL。

所属阶段：外部多语言数据接入前的格式探查。HF `UCSB-SURFI/SeCodePLT` 的
分片是 parquet（非文本，无法直接打开/审计），本脚本把它们转成每行一条 JSON
的 JSONL，便于人工检查与后续字段映射。

输入：parquet 文件路径（或 hf_full 目录，自动发现全部 *.parquet）。
输出：同目录 jsonl/<name>.jsonl，每条记录包含原字段，并把 meta_data
（JSON 字符串）解析成对象，方便直接阅读。

允许修改长期经验库：否——只做只读格式转换，不改数据内容。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("需要 pandas/pyarrow：python -m pip install pandas pyarrow") from exc


def _parse_meta(value: object) -> object:
    """把 meta_data 字符串解析为对象；解析失败时保留原值。"""
    if isinstance(value, str) and value.strip():
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def convert_parquet_to_jsonl(parquet_path: Path, out_path: Path, *, limit: int = 0) -> int:
    """读取一个 parquet 分片并写出 JSONL，返回写出的记录数。"""
    df = pd.read_parquet(parquet_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for _, row in df.iterrows():
            record = {}
            for column in df.columns:
                value = row[column]
                if column == "meta_data":
                    value = _parse_meta(value)
                record[column] = value
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            if limit and written >= limit:
                break
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="HF SeCodePLT parquet → JSONL 转换")
    parser.add_argument("path", help="parquet 文件路径，或包含 *.parquet 的目录")
    parser.add_argument("--out", help="输出目录（默认 <parquet 所在目录>/jsonl）")
    parser.add_argument("--limit", type=int, default=0, help="每个分片最多转换条数；0=全部")
    args = parser.parse_args()

    source = Path(args.path)
    if source.is_dir():
        parquets = sorted(source.glob("*.parquet"))
    else:
        parquets = [source]
    if not parquets:
        raise SystemExit(f"未找到 parquet 文件: {source}")

    out_root = Path(args.out) if args.out else source.parent / "jsonl"
    total = 0
    for parquet in parquets:
        out_path = out_root / (parquet.stem + ".jsonl")
        count = convert_parquet_to_jsonl(parquet, out_path, limit=args.limit)
        kb = round(out_path.stat().st_size / 1024)
        print(f"{parquet.name}: {count} 条 → {out_path} ({kb} KB)")
        total += count
    print(f"共转换 {total} 条记录")


if __name__ == "__main__":
    main()

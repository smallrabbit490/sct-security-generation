"""把 HF Java 分片映射为管线风格的 PLT 记录（转换实验）。

所属阶段：外部 Java 数据接入可行性的字段映射实验。HF `UCSB-SURFI/SeCodePLT`
的 Java 记录字段与本项目 PLT `data.json` 结构不同，本脚本尝试把每条 Java
记录映射成 `{CWE_ID, task_description, ground_truth, unittest}` 结构，并
如实标注缺失项——尤其是测试：Java 的测试是 JUnit 5（meta_data.unit_test），
不是 Python 管线的 `testcases = {capability, safety}` 数据驱动字典，不能
直接跑在 validate_trajectory 上。

允许修改长期经验库：否——只做只读字段映射实验，输出样本 JSONL 供检查。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _extract_function_name(record: dict) -> str:
    """优先从 meta_data.guidance 的 Method: 行取函数名，否则从代码取方法签名。"""
    md = record.get("meta_data") or {}
    guidance = str(md.get("guidance") or "")
    match = re.search(r"Method:\s*(\w+)", guidance)
    if match:
        return match.group(1)
    code = str(record.get("vulnerable_code_reference") or "")
    match = re.search(r"\b(?:public|private|protected)\s+[\w<>\[\]]+\s+(\w+)\s*\(", code)
    if match:
        return match.group(1)
    return ""


def _extract_description(record: dict) -> str:
    """从 guidance 提取 Purpose/Functionality/Input Parameters 摘要。"""
    md = record.get("meta_data") or {}
    guidance = str(md.get("guidance") or "")
    return guidance[:600]


def map_java_record(record: dict) -> dict:
    """把一条 HF Java 记录映射成 PLT 风格记录；缺失项如实标注。"""
    md = record.get("meta_data") or {}
    function_name = _extract_function_name(record)
    return {
        "index": record.get("id"),
        "CWE_ID": str(record.get("CWE_ID") or ""),
        "language": "java",
        "source": "UCSB-SURFI/SeCodePLT",
        "task_description": {
            "function_name": function_name,
            "description": _extract_description(record),
            # HF 数据没有显式 security_policy；需从 CWE 定义或输入提示补充。
            "security_policy": "",
            "context": str(record.get("context") or ""),
        },
        "ground_truth": {
            "code_before": str(record.get("vulnerable_code_reference") or ""),
            "patched_code": str(record.get("patched_code_reference") or ""),
            "code_after": "",
        },
        # Java 测试是 JUnit 5，不是 capability/safety 字典 —— 保留原始测试并标注。
        "unittest": {
            "format": "junit5",
            "testcases": "不适用（Python 数据驱动字典）",
            "junit_test_source": str(md.get("unit_test") or ""),
        },
        "input_prompt": str(record.get("input_prompt") or ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="HF Java → PLT 风格字段映射实验")
    parser.add_argument("input", help="Java JSONL 输入")
    parser.add_argument("--out", required=True, help="样本 JSONL 输出路径")
    parser.add_argument("--limit", type=int, default=3, help="映射条数")
    args = parser.parse_args()

    records = []
    with open(args.input, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
            if len(records) >= args.limit:
                break

    mapped = [map_java_record(r) for r in records]
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for m in mapped:
            handle.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"映射 {len(mapped)} 条 → {out_path}")
    for m in mapped:
        has_test = bool(m["unittest"]["junit_test_source"].strip())
        print(f"  {m['index']} CWE-{m['CWE_ID']} fn={m['task_description']['function_name']} junit_test={'有' if has_test else '无'}")


if __name__ == "__main__":
    main()

"""本地（无 Docker）CodeSecEval Python 最终评测入口。

用法：
    python -m methods.sct_lifecycle_replay.run_local_codeseceval \
        --run translation_work/sct_runs/<run> \
        --live-api \
        [--subsets Base Plus] [--limit 5]

流程：
1. 校验冻结经验库（哈希一致、feedback_channel=disabled）；
2. 从 data/SecEvoBasePlus/<subset>/Python_<subset>.json 读取任务；
3. 对每条任务：冻结经验检索 → deepseek-v3.2 生成 → 本地 python -I
   执行 Test-FP（功能）与 Test-SP（安全）；
4. 写入 validation_runs/<subset>/rows.jsonl 与 summary.json，并打印汇总。

本评测不使用 Docker；Base/Plus 反馈通道保持 disabled，不更新经验库。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .api import ChatClient
from .chatanywhere_smoke import load_key
from .local_codeseceval import (
    evaluate_python_tasks,
    load_codeseceval_python,
    load_frozen_run,
    write_validation_run,
)

SUBSET_FILES = {"Base": "Python_Base.json", "Plus": "Python_Plus.json"}


def live_requester(model: str = "deepseek-v3.2", timeout: int = 60):
    """创建真实 ChatAnywhere 请求器；返回内容只在内存中处理。"""
    from urllib.request import Request, urlopen

    def request(prompt: str) -> dict:
        body = json.dumps(
            {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 1024}
        ).encode("utf-8")
        req = Request(
            "https://api.chatanywhere.tech/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {load_key()}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    return request


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True, help="冻结运行目录（含 frozen/m_star.jsonl）")
    parser.add_argument("--live-api", action="store_true")
    parser.add_argument("--subsets", nargs="+", default=["Base", "Plus"])
    parser.add_argument("--limit", type=int, default=0, help="每个子集评测任务数上限；0 表示全部")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--retries", type=int, default=1)
    args = parser.parse_args()

    root = Path(__file__).parents[2]
    memory, metadata = load_frozen_run(args.run)
    requester = ChatClient(timeout=args.timeout, retries=args.retries, max_tokens=1024) if args.live_api else (lambda prompt: {"choices": [{"message": {"content": ""}}]})
    if not args.live_api:
        print("离线模式：requester 返回空内容，仅验证流程；正式评测需 --live-api")
    print(f"冻结经验库：{len(memory)} 条，哈希校验通过，feedback_channel=disabled")

    all_summaries = {}
    for subset in args.subsets:
        filename = SUBSET_FILES.get(subset)
        if filename is None:
            raise ValueError(f"未知子集: {subset}")
        path = root / "data/SecEvoBasePlus" / subset / filename
        tasks = load_codeseceval_python(path)
        if args.limit:
            tasks = tasks[: args.limit]
        print(f"\n=== {subset}（{len(tasks)} 条，{filename}） ===")
        results = evaluate_python_tasks(
            tasks,
            requester,
            memory,
            timeout=args.timeout,
            retries=args.retries,
        )
        summary = write_validation_run(Path(args.run), subset, results)
        all_summaries[subset] = summary
        print(
            f"{subset}: total={summary['total']} Function={summary['functional']} "
            f"Secure={summary['secure']} Joint={summary['joint_pass']} genErr={summary['generation_errors']}"
        )

    print("\n=== 汇总 ===")
    for subset, summary in all_summaries.items():
        print(
            f"{subset}: Function {summary['functional']}/{summary['total']} "
            f"({100 * summary['functional'] / summary['total']:.1f}%), "
            f"Secure {summary['secure']}/{summary['total']} "
            f"({100 * summary['secure'] / summary['total']:.1f}%), "
            f"Joint {summary['joint_pass']}/{summary['total']} "
            f"({100 * summary['joint_pass'] / summary['total']:.1f}%)"
        )
    print("\n结果写入 validation_runs/<subset>/rows.jsonl 与 summary.json")


if __name__ == "__main__":
    main()

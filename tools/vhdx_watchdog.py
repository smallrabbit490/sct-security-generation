"""VHDX 看门狗：跑一条命令，全程采样 Docker 数据盘水位与容器数，最后给出判定。

## 为什么需要它

Docker Desktop（WSL2 后端）的 `docker_data.vhdx` **只涨不缩**：容器里删掉的数据
只把块还给内部 ext4 空闲池，不会通知 Windows。所以"这次跑完 vhdx 没涨"不能靠
肉眼比对文件大小，必须**在运行期间连续采样**，并给出可引用的判定。

2026-09-17 的膨胀事故（vhdx 从 14.9 GB 涨到 67.72 GB）正是"每个任务
`docker run --rm` 新建容器 + 中途强杀留下孤儿容器"造成的。本看门狗就是用来
证明这类问题不再复发的。

## 用法

```bash
PY="C:/Users/86136/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
"$PY" tools/vhdx_watchdog.py --label prompt_baseline_smoke -- \
    "$PY" methods/workflow_baselines/run_true_agent_workflows.py --limit 1 ...
```

判定口径（三项全过才算通过）：

1. **vhdx 增量**不超过 `--max-growth-mib`（默认 64 MiB）。
   注意 vhdx 是稀疏文件，正常运行只会有元数据级别的微小变化。
2. **容器数峰值**不超过 `--max-containers`（默认 0 表示不检查），
   并且末次采样等于峰值——**持续增长就等于泄漏**。
3. **收尾容器归零**：命令结束后 `docker ps -a` 为空。

退出码：0 = 通过，1 = 不通过，2 = 命令本身非零退出。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from translation_pipeline.persistent_container import (  # noqa: E402
    cleanup_stale_containers,
    docker_data_vhdx_path,
    measure_docker_disk,
)

SAMPLES: list[dict] = []
_SAMPLE_LOCK = threading.Lock()
_STOP = threading.Event()


def _vhdx_size() -> int:
    """只读 vhdx 文件大小。

    这是采样循环的主力口径：**不碰 Docker**。早期版本每 2 秒调一次
    ``measure_docker_disk()``，而那个函数会起一个探针容器读内部用量——
    等于看门狗自己在制造容器、污染自己的"容器数"判据。探针只在首尾各做一次。
    """
    path = docker_data_vhdx_path()
    if path is None:
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _container_names() -> list[str]:
    try:
        proc = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]


def _take_sample() -> dict:
    entry = {
        "t": round(time.time(), 2),
        "vhdx_bytes": _vhdx_size(),
        "containers": len(_container_names()),
    }
    with _SAMPLE_LOCK:
        SAMPLES.append(entry)
    return entry


def _sample_loop(interval: float) -> None:
    while not _STOP.is_set():
        _take_sample()
        _STOP.wait(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description="VHDX 看门狗")
    parser.add_argument("--label", default="run", help="本次运行的标签，写进报告")
    parser.add_argument("--interval", type=float, default=2.0, help="采样间隔（秒）")
    parser.add_argument("--max-growth-mib", type=float, default=64.0, help="vhdx 允许的最大增量")
    parser.add_argument("--max-containers", type=int, default=0, help="容器数上限；0 表示不检查")
    parser.add_argument("--report", type=Path, default=None, help="报告输出路径（JSON）")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="-- 之后是要运行的命令")
    args = parser.parse_args()

    command = [item for item in args.command if item != "--"]
    if not command:
        print("需要 -- 之后给出要运行的命令", file=sys.stderr)
        return 2

    # 起点干净：先清掉上次异常退出的池容器，否则会污染"容器数"判据。
    stale = cleanup_stale_containers()
    before = measure_docker_disk()
    vhdx_before = int(before.get("vhdx_bytes") or 0)
    used_before = int(before.get("filesystem_used_bytes") or 0)
    print(f"[watchdog] label={args.label}")
    print(f"[watchdog] 起点 vhdx={vhdx_before:,} B 内部已用={used_before:,} B")
    if stale:
        print(f"[watchdog] 起点清理了残留池容器: {stale}")

    sampler = threading.Thread(target=_sample_loop, args=(args.interval,), daemon=True)
    sampler.start()
    tic = time.perf_counter()
    try:
        proc = subprocess.run(command, cwd=str(PROJECT_ROOT))
        exit_code = proc.returncode
    except KeyboardInterrupt:
        exit_code = 130
    finally:
        elapsed = time.perf_counter() - tic
        _STOP.set()
        sampler.join(timeout=max(10.0, args.interval * 3))
        # 命令已退出，补一个"收尾后"采样点，否则 series[-1] 反映的是进程还在跑时的
        # 状态，拿它做"容器是否归零"的判据必然失败。
        _take_sample()

    after = measure_docker_disk()
    vhdx_after = int(after.get("vhdx_bytes") or 0)
    used_after = int(after.get("filesystem_used_bytes") or 0)
    with _SAMPLE_LOCK:
        samples = list(SAMPLES)

    peak = max((s["containers"] for s in samples), default=0)
    series = [s["containers"] for s in samples]
    last = series[-1] if series else 0
    # 峰值出现的**最后一个**下标。若它就落在最后一个采样点，说明容器数到命令结束
    # 都还在爬升——那才是泄漏的样子；否则就是"起池→稳定→收尾归零"的正常形状。
    peak_last_index = max((i for i, value in enumerate(series) if value == peak), default=-1)
    growth = vhdx_after - vhdx_before
    used_delta = used_after - used_before
    leftover = _container_names()

    checks = {
        "vhdx_growth_ok": growth <= int(args.max_growth_mib * 1024 * 1024),
        # 容器数必须回落到 0（池在收尾时删干净）。
        "container_teardown_ok": last == 0,
        # 峰值必须在收尾之前就达到并稳定，不能"一直涨到结束"。
        "container_stable_ok": peak_last_index < len(series) - 1,
        "container_limit_ok": (args.max_containers <= 0) or (peak <= args.max_containers),
        "cleanup_ok": leftover == [],
        "command_ok": exit_code == 0,
    }
    passed = all(checks.values())

    print("-" * 78)
    print(f"[watchdog] 耗时 {elapsed:.1f}s  退出码 {exit_code}")
    print(f"[watchdog] vhdx 增量      = {growth:+,} B ({growth / 1048576:+.2f} MiB)  上限 {args.max_growth_mib} MiB")
    print(f"[watchdog] 内部用量增量   = {used_delta:+,} B")
    print(f"[watchdog] 容器数 峰值={peak} 末次={last} 采样数={len(samples)}")
    print(f"[watchdog] 收尾残留容器   = {leftover or '无'}")
    print(f"[watchdog] 判定            = {'PASS' if passed else 'FAIL'}  {checks}")
    if series:
        print(f"[watchdog] 容器数序列      = {series}")

    report = {
        "label": args.label,
        "command": command,
        "elapsed_s": round(elapsed, 2),
        "exit_code": exit_code,
        "vhdx_before": vhdx_before,
        "vhdx_after": vhdx_after,
        "vhdx_growth_bytes": growth,
        "used_before": used_before,
        "used_after": used_after,
        "used_growth_bytes": used_delta,
        "container_peak": peak,
        "container_last": last,
        "container_peak_last_index": peak_last_index,
        "leftover_containers": leftover,
        "checks": checks,
        "passed": passed,
        "container_series": [s["containers"] for s in samples],
    }
    report_path = args.report or (PROJECT_ROOT / "translation_work" / "diagnostics" / f"vhdx_watchdog_{args.label}.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[watchdog] 报告写入 {report_path}")

    if exit_code != 0:
        return 2
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

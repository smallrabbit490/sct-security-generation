"""官方 SeCodePLT 测试执行器：本地子进程（默认）与常驻 Docker 容器（可选）。

所属阶段：SeCodePLT 评测的代码执行（对应官方 `executor_docker/server/python.py`
与 `executor_docker/docker/python-env/run_test.py`）。

两种后端：
1. ``run_testcases_local``（默认）：把注入后的测试脚本写到临时目录，用
   ``python -I`` 子进程执行。等价于官方「容器内执行」的语义，但不产生 Docker
   虚拟盘（VHDX）增长——这正是官方评测「不膨胀」的本地化版本。
2. ``run_testcases_docker``（可选）：复刻官方「一个常驻容器 + 逐任务 exec」
   的模式，只是通过 docker CLI 实现（不依赖 docker SDK）。启动时创建一次
   容器，之后每个任务只往容器 /tmp 写脚本、exec 执行、取 JSON 结果、删除
   临时文件；评测期间不 build 也不新建容器，容器可写层写入为 KB 级且即时
   清理，因此 VHDX 不会持续膨胀。

验证证据：结果来自测试用例真实执行（1=通过 / -1=运行错误 / -2=超时）；
脚本整体超时由 subprocess timeout 兜底（Windows 无 SIGALRM 时尤其必要）。
允许修改长期经验库：否。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from typing import Any

from .schemas import TestCodeOutput, TestCodeParams
from .template import UNITTEST_TEMPLATE, generate_test_code


def _run_injected_script(code: str, *, timeout: int, python: str | None) -> TestCodeOutput | None:
    """把注入后的测试脚本写入临时目录并用 ``python -I`` 子进程执行。

    返回 None 表示脚本整体失败（编译错误/非零退出）；子进程超时返回空的
    TestCodeOutput（runtime 记为超时秒数），由 scoring 按未测量/失败处理。
    """
    python = python or sys.executable
    with tempfile.TemporaryDirectory(prefix="secodeplt_eval_") as td:
        test_path = os.path.join(td, "test_runner.py")
        results_path = os.path.join(td, "results.json")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(code)
        env = dict(os.environ)
        env["UNITTEST_RESULTS_PATH"] = results_path
        tic = time.perf_counter()
        try:
            proc = subprocess.run(
                [python, "-I", test_path],
                cwd=td,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return TestCodeOutput(capability=[], safety=[], runtime=float(timeout))
        runtime = time.perf_counter() - tic
        if proc.returncode != 0:
            return None
        with open(results_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return TestCodeOutput(
            capability=[int(x) for x in raw.get("capability", [])],
            safety=[int(x) for x in raw.get("safety", [])],
            runtime=runtime,
        )


def run_testcases_local(
    params: TestCodeParams, *, timeout: int = 30, python: str | None = None
) -> TestCodeOutput | None:
    """本地执行：setup + 生成代码 + testcases 注入官方模板后子进程运行。

    输入是官方同构的 TestCodeParams；输出是 TestCodeOutput（capability/safety
    逐用例结果与总耗时），脚本整体失败返回 None。install_requires 在本地后端
    忽略（安装依赖有副作用且数据中多为空），如需依赖请使用 Docker 后端。
    """
    code = generate_test_code(
        UNITTEST_TEMPLATE, params.setup, params.code, params.testcases, params.func_name
    )
    return _run_injected_script(code, timeout=timeout, python=python)


def create_executor_container(image: str = "python:3.11-alpine", name: str = "secodeplt-eval-python") -> str:
    """启动一个常驻评测容器（官方模式：评测期间复用同一容器，不反复创建）。

    需要镜像里有 python 解释器即可（默认官方同款 python:3.11-alpine）；保持
    存活用 `tail -f /dev/null`，与本模块的 docker exec 执行方式配套。
    """
    subprocess.run(
        ["docker", "run", "-d", "--name", name, image, "tail", "-f", "/dev/null"],
        check=True,
        capture_output=True,
        text=True,
    )
    return name


def remove_executor_container(name: str) -> None:
    """评测结束后删除常驻容器；只删容器不删镜像，镜像层保留供复用。"""
    subprocess.run(["docker", "rm", "-f", name], capture_output=True, text=True)


def run_testcases_docker(
    params: TestCodeParams, *, container: str, timeout: int = 60
) -> TestCodeOutput | None:
    """Docker 后端：在常驻容器里逐任务 exec（复刻官方 server/python.py 模式）。

    每个任务：把注入后的脚本 docker cp 进容器 /tmp → ``docker exec -e
    UNITTEST_RESULTS_PATH=...`` 执行 → ``docker exec cat`` 取 JSON 结果 →
    ``docker exec rm -f`` 清理两个临时文件。不 build、不新建容器，因此
    容器可写层与 VHDX 的增长被控制在 KB 级。
    """
    code = generate_test_code(
        UNITTEST_TEMPLATE, params.setup, params.code, params.testcases, params.func_name
    )
    task_id = uuid.uuid4().hex
    test_file = f"test_{task_id}.py"
    out_file = f"out_{task_id}.json"
    with tempfile.TemporaryDirectory(prefix="secodeplt_eval_docker_") as td:
        local_test = os.path.join(td, test_file)
        with open(local_test, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            subprocess.run(
                ["docker", "cp", local_test, f"{container}:/tmp/{test_file}"],
                check=True,
                capture_output=True,
                text=True,
            )
            proc = subprocess.run(
                [
                    "docker", "exec", "-e", f"UNITTEST_RESULTS_PATH=/tmp/{out_file}",
                    container, "python", f"/tmp/{test_file}",
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if proc.returncode != 0:
                return None
            out_proc = subprocess.run(
                ["docker", "exec", container, "cat", f"/tmp/{out_file}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            raw = json.loads(out_proc.stdout)
            return TestCodeOutput(
                capability=[int(x) for x in raw.get("capability", [])],
                safety=[int(x) for x in raw.get("safety", [])],
                runtime=float(raw.get("runtime", 0.0)),
            )
        except subprocess.TimeoutExpired:
            return TestCodeOutput(capability=[], safety=[], runtime=float(timeout))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
        finally:
            subprocess.run(
                ["docker", "exec", container, "rm", "-f", f"/tmp/{test_file}", f"/tmp/{out_file}"],
                capture_output=True,
                text=True,
            )


def docker_available() -> bool:
    """快速探测 docker CLI 是否可用（用于测试与调用方判断后端）。"""
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

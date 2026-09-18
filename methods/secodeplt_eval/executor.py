"""官方 SeCodePLT 测试执行器：本地子进程（默认）与常驻 Docker 容器（可选）。

所属阶段：SeCodePLT 评测的代码执行（对应官方 `executor_docker/server/python.py`
与 `executor_docker/docker/python-env/run_test.py`）。

两种后端：

1. ``run_testcases_local``（默认）：把注入后的测试脚本写到临时目录，用
   ``python -I`` 子进程执行。等价于官方「容器内执行」的语义，但不产生 Docker
   虚拟盘（VHDX）增长——这是官方评测「不膨胀」的本地化版本。PLT 只有 Python
   样本，训练侧一律走这条路径，不启动 Docker。

2. ``run_testcases_docker``（可选）：复刻官方「一个常驻容器 + 逐任务 exec」模式。
   容器由 ``create_executor_container`` 建一次、``remove_executor_container``
   在评测结束时删一次；评测期间**不 build、不新建容器**。

与官方实现的差异（以及为什么这样改）：

- 官方用 docker SDK 的 ``put_archive`` 把脚本打进容器 ``/tmp``，结果再 ``cat``
  出来，写入落在容器可写层。这里改为把宿主目录绑定挂载到容器 ``/work``，
  脚本与结果 JSON 直接读写宿主盘。好处有两个：容器可写层写入为 0
  （VHDX 水位不涨，见 ``docs/docker_eval_backend_analysis.md``），
  且中间产物可在宿主侧直接检查，满足「证据可审计」要求。
- 官方依赖宿主侧超时；这里**额外**用容器内 ``timeout`` 兜一层。宿主侧超时只能
  杀掉 ``docker exec`` 客户端，容器里的 python 进程会变成孤儿继续跑
  （2026-09-17 容器泄漏事故的成因之一）。容器内超时由 Linux 自己杀干净。
- 容器规格补齐了资源限制：``--network none``（候选代码无外网出口）、
  ``--memory``、``--cpus``、``--pids-limit``、``--tmpfs /tmp``。

验证证据：结果来自测试用例真实执行（1=通过 / -1=运行错误 / -2=超时）；
脚本整体超时由容器内 ``timeout`` 与宿主侧兜底两层保护。
``runtime`` 取容器内 exec 的真实耗时（旧实现读模板里并不存在的 ``runtime`` 字段，
恒为 0，属于未测量值被当成实测值）。
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
from pathlib import Path
from typing import Any

from .schemas import TestCodeOutput, TestCodeParams
from .template import UNITTEST_TEMPLATE, generate_test_code

# ``methods/`` 不是已安装的包，需要显式把 ``src/`` 加进搜索路径才能复用
# translation_pipeline 的常驻容器执行层（与 methods/ 下其他脚本同一惯例）。
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from translation_pipeline.persistent_container import (  # noqa: E402
    ContainerSpec,
    PersistentContainer,
    attach_container,
    force_remove_docker_container,
)

# 评测容器的宿主工作根：每个容器名一个子目录，挂载到容器内 /work。
SECODEPLT_WORK_ROOT = _PROJECT_ROOT / "translation_work" / "sandbox" / "_secodeplt"
CONTAINER_WORK_ROOT = "/work"
DEFAULT_EXECUTOR_IMAGE = os.environ.get("SECODEPLT_PYTHON_IMAGE", "python:3.11-alpine")
MAX_RESULT_CHARS = int(os.environ.get("SECODEPLT_MAX_RESULT_CHARS", "20000"))


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


# --------------------------------------------------------------------------- #
# Docker 后端：常驻容器 + 宿主挂载
# --------------------------------------------------------------------------- #


def _safe_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in name)


def work_dir_for(container_name: str) -> Path:
    """容器名 → 宿主工作目录（同时也是容器内 ``/work`` 的来源）。"""
    path = SECODEPLT_WORK_ROOT / _safe_name(container_name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _docker_mount_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def executor_spec(image: str, container_name: str) -> ContainerSpec:
    """评测容器的规格：断网 + 资源限制 + 宿主工作目录挂载。

    断网是硬要求：被测代码来自模型生成，必须没有外网出口。
    """
    return ContainerSpec(
        image=image,
        mounts=((_docker_mount_path(work_dir_for(container_name)), CONTAINER_WORK_ROOT),),
        network="none",
        memory="512m",
        cpus="1",
        pids_limit=128,
        tmpfs=("/tmp:rw,nosuid,nodev,size=64m",),
    )


def create_executor_container(
    image: str = DEFAULT_EXECUTOR_IMAGE, name: str = "secodeplt-eval-python"
) -> str:
    """启动一个常驻评测容器（官方模式：评测期间复用同一容器，不反复创建）。

    需要镜像里有 python 解释器即可（默认官方同款 ``python:3.11-alpine``）。
    保活用 ``--entrypoint tail -f /dev/null``，与本模块的 ``docker exec``
    执行方式配套；容器还挂载了宿主工作目录 ``work_dir_for(name)`` 到 ``/work``。
    创建失败抛 RuntimeError，由调用方按环境错误处理。
    """
    container = PersistentContainer(executor_spec(image, name), name)
    container.start()
    return name


def remove_executor_container(name: str) -> None:
    """评测结束后删除常驻容器；只删容器不删镜像，镜像层保留供复用。"""
    force_remove_docker_container(name)


def run_testcases_docker(
    params: TestCodeParams, *, container: str, timeout: int = 60
) -> TestCodeOutput | None:
    """Docker 后端：在常驻容器里逐任务 exec（复刻官方 server/python.py 模式）。

    每个任务的流程：脚本写进宿主工作目录（容器内可见为 ``/work/test_<id>.py``）
    → ``docker exec -w /work`` 执行 → 从宿主工作目录读结果 JSON → 删除两个文件。

    返回语义与本地后端一致：脚本整体失败（非零退出 / 结果文件缺失 / JSON 非法）
    返回 None；超时返回空结果并把 ``runtime`` 记为超时秒数，由 scoring 按未测量
    处理——**不能**把超时当成通过，也不能当成失败，否则会污染 capability/safety。

    ``container`` 必须是 ``create_executor_container`` 建出来的容器（或至少
    同样挂载了 ``work_dir_for(container)`` 的容器）；否则宿主侧写的脚本在容器内
    不可见，会表现为脚本找不到。
    """
    code = generate_test_code(
        UNITTEST_TEMPLATE, params.setup, params.code, params.testcases, params.func_name
    )
    work_dir = work_dir_for(container)
    task_id = uuid.uuid4().hex
    test_name = f"test_{task_id}.py"
    out_name = f"out_{task_id}.json"
    test_path = work_dir / test_name
    out_path = work_dir / out_name
    test_path.write_text(code, encoding="utf-8")
    handle: PersistentContainer = attach_container(container)
    try:
        result = handle.exec_argv(
            ["python", "-I", f"{CONTAINER_WORK_ROOT}/{test_name}"],
            workdir=CONTAINER_WORK_ROOT,
            env={"UNITTEST_RESULTS_PATH": f"{CONTAINER_WORK_ROOT}/{out_name}"},
            timeout=timeout + 30,
            container_timeout=timeout,
            output_limit=MAX_RESULT_CHARS,
        )
        if result.timed_out:
            # 容器内 timeout 已杀掉工作进程，宿主侧无需额外清理。
            return TestCodeOutput(capability=[], safety=[], runtime=float(timeout))
        if result.returncode != 0:
            return None
        if not out_path.exists():
            return None
        try:
            raw: dict[str, Any] = json.loads(out_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return TestCodeOutput(
            capability=[int(x) for x in raw.get("capability", [])],
            safety=[int(x) for x in raw.get("safety", [])],
            runtime=float(result.duration_s),
        )
    finally:
        # 任务级空间即写即清：两个临时文件都不留在宿主盘上。
        for path in (test_path, out_path):
            try:
                path.unlink()
            except OSError:
                pass


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

"""常驻容器执行层：官方 SeCodePLT ``executor_docker`` 模式的本地移植。

所属阶段：所有需要真实隔离的代码执行——CodeSecEval Base/Plus 的 C++/Go/Python
harness 验证，以及 PLT 的 Python/Java 动态单测。它替代旧的"每个任务
``docker run --rm`` 新建一个容器"的做法。

官方逻辑（``data/external/secodeplt_github/executor_docker/``）有三条硬约束：

1. **镜像只构建一次**，评测期间从不 ``docker build`` / ``docker pull``；
2. **常驻容器**：服务启动时创建容器（``CMD ["tail","-f","/dev/null"]``），
   评测全程复用同一个容器，每个任务只做 ``exec``；
3. **评测结束才** ``container.remove(force=True)``。

本模块照搬这三条，只在一处做改进：官方用 ``put_archive`` 把任务输入打进容器
``/tmp``，我们改成一次性 ``-v <host_work_root>:/work`` 绑定挂载 + 每任务子目录
``/work/<task_key>/``。理由：

- 编译产物、模块缓存、构建缓存全部落到**宿主盘**而不是容器可写层，
  于是评测期间 vhdx（Docker Desktop 的 WSL2 数据盘）水位增量接近 0；
- 宿主目录可以直接检查，符合"证据可审计"要求。

任务隔离靠 ``<work_root>/<task_key>/`` 子目录实现：每个任务独占一个子目录，
结束即整目录删除。因此并发任务之间不会互相污染。

并发模型：官方 server 是串行的（单容器），而我们的评测默认 ``--workers 4``。
因此引入 :class:`ContainerPool`——评测开始时一次性启动 N 个常驻容器，
任务只在池内复用；**任务级超时不新建容器**，只有容器真的不可用时才重建
单个容器并把事件记进 ``run_metadata``（可审计的异常路径）。

失败类型边界：本模块只负责"容器能不能用、命令跑没跑完"。编译错误、功能失败、
安全失败仍由调用方按各自的 harness 语义判定，不在这里折算。
允许修改长期经验库：否。
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

DEFAULT_OUTPUT_LIMIT = int(os.environ.get("SAFECODER_MAX_VALIDATOR_OUTPUT_CHARS", "2000"))
POOL_NAME_PREFIX = "safecoder-pool-"
# 容器内 timeout 触发时可能出现的退出码。实测（2026-09-17）：
#   GNU coreutils（golang:1.22 / debian）→ 124
#   busybox（python:3.11-alpine）        → 143（128+SIGTERM）
# 若命令忽略 SIGTERM，被 `-k` 追加的 SIGKILL 打死则为 137（128+SIGKILL）。
# 注意：143 也可能是"命令自己被 SIGTERM 杀死"，所以退出码**单独不足以**判定超时，
# 必须配合执行时长交叉验证（见 TIMEOUT_DURATION_RATIO）。
TIMEOUT_EXIT_CODES = frozenset({124, 137, 143})
# 交叉验证容差：命令实际耗时达到容器内阈值的这个比例，才认定"确实是超时"。
# 否则视为"命令自己以 124/143 退出"，按普通失败处理，避免把超时算进方法得分。
TIMEOUT_DURATION_RATIO = 0.9
# 官方 python-env 用 ``CMD ["tail","-f","/dev/null"]`` 保活；这里用 --entrypoint
# 覆盖镜像自带的 ENTRYPOINT（例如 porta-bench 的 docker_runner），保证 tail 是主进程。
KEEPALIVE_ENTRYPOINT = "tail"
KEEPALIVE_ARGS = ("-f", "/dev/null")
KEEPALIVE_FALLBACK = ("sh", "-c", "exec sleep infinity")


# --------------------------------------------------------------------------- #
# 底层：带输出上限的子进程运行器
# --------------------------------------------------------------------------- #


def _read_limited_pipe(pipe: Any, limit: int, chunks: list[str], truncated: list[bool]) -> None:
    """后台线程读取管道，最多保留 ``limit`` 个字符，避免日志把内存撑爆。"""
    total = 0
    while True:
        chunk = pipe.readline()
        if not chunk:
            break
        if total < limit:
            remaining = limit - total
            chunks.append(chunk[:remaining])
            total += len(chunk[:remaining])
            if len(chunk) > remaining:
                truncated[0] = True
        else:
            truncated[0] = True


def extract_docker_container_name(args: list[str]) -> str | None:
    """从 ``docker run`` 参数里取 ``--name``；不是 docker run 时返回 None。"""
    if len(args) < 2 or Path(args[0]).name.lower() not in {"docker", "docker.exe"} or args[1] != "run":
        return None
    for index, arg in enumerate(args):
        if arg == "--name" and index + 1 < len(args):
            return args[index + 1]
        if arg.startswith("--name="):
            return arg.split("=", 1)[1]
    return None


def force_remove_docker_container(name: str, docker: str = "docker") -> None:
    """尽力删除一个容器；失败不抛出（用于异常路径兜底）。"""
    try:
        subprocess.run(
            [docker, "rm", "-f", name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
            check=False,
        )
    except Exception:
        pass


def run_limited_command(
    args: list[str],
    cwd: Path,
    timeout: int = 30,
    env: dict[str, str] | None = None,
    output_limit: int = DEFAULT_OUTPUT_LIMIT,
) -> tuple[int | None, str, str, bool]:
    """运行外部命令，返回 ``(returncode, stdout, stderr, timed_out)``。

    超时时如果命令行里带 ``--name``（即 ``docker run``），额外 ``docker rm -f``
    兜底删除容器，避免容器泄漏——这是 2026-09-17 事故的直接教训。
    """
    docker_container_name = extract_docker_container_name(args)
    process = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    stdout_truncated = [False]
    stderr_truncated = [False]
    assert process.stdout is not None
    assert process.stderr is not None
    stdout_thread = threading.Thread(
        target=_read_limited_pipe,
        args=(process.stdout, output_limit, stdout_chunks, stdout_truncated),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_read_limited_pipe,
        args=(process.stderr, output_limit, stderr_chunks, stderr_truncated),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        returncode: int | None = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        returncode = process.wait()
        if docker_container_name:
            force_remove_docker_container(docker_container_name)
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    process.stdout.close()
    process.stderr.close()
    stdout = "".join(stdout_chunks)
    stderr = "".join(stderr_chunks)
    if stdout_truncated[0]:
        stdout += f"\n...[truncated stdout at {output_limit} chars]..."
    if stderr_truncated[0]:
        stderr += f"\n...[truncated stderr at {output_limit} chars]..."
    if timed_out and not stderr:
        stderr = "command timed out"
    return returncode, stdout, stderr, timed_out


def _quote_argv(command: list[str]) -> str:
    """把 argv 拼成一行可安全交给 ``sh -c`` 的命令串。"""
    return " ".join("'" + item.replace("'", "'\"'\"'") + "'" for item in command)


def wrap_linux_timeout(seconds: int, command: list[str]) -> list[str]:
    """把命令包进容器内的 ``timeout``，让超时在容器里被 Linux 自己杀掉。

    这比只靠宿主侧 subprocess timeout 更可靠：宿主侧杀的是 ``docker exec``
    客户端，容器内进程会变成孤儿。两层超时（容器内 + 宿主侧兜底）配合使用。

    这里**不做退出码归一化**，保留 ``timeout`` 的原始退出码（GNU 124 /
    busybox 143 / 被 SIGKILL 137）。原因：alpine 里"命令自己收到 SIGTERM"
    同样返回 143，归一化会把普通失败伪装成超时，反而制造误判。
    真正的超时判定放在 :meth:`PersistentContainer.exec_argv`，用
    "退出码 ∈ :data:`TIMEOUT_EXIT_CODES`" + "耗时达到阈值"两条一起判。
    """
    quoted = _quote_argv(command)
    return ["sh", "-c", f"timeout -k 5s {seconds}s {quoted}"]


def docker_available(docker: str = "docker", timeout: int = 15) -> bool:
    """探测 Docker CLI + daemon 是否可用（评测前置检查用）。"""
    if not shutil.which(docker) and not Path(docker).exists():
        return False
    try:
        proc = subprocess.run(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# --------------------------------------------------------------------------- #
# 容器规格
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ContainerSpec:
    """一个常驻容器的启动参数。

    ``mounts`` 是 ``(宿主绝对路径, 容器内路径)`` 列表；宿主路径在启动前必须存在。
    ``network`` 为 ``None`` 表示用 Docker 默认网络（仅 ``go get`` 这类需要
    下载依赖的步骤才放开），``"none"`` 表示完全断网。
    """

    image: str
    mounts: tuple[tuple[str, str], ...] = ()
    # 只读挂载：工具链（JUnit jar、juliet-support 等）必须只读，
    # 否则容器内运行的候选代码可以改写评测工具本身。
    readonly_mounts: tuple[tuple[str, str], ...] = ()
    env: tuple[tuple[str, str], ...] = ()
    network: str | None = "none"
    memory: str = "512m"
    cpus: str = "1"
    pids_limit: int = 256
    tmpfs: tuple[str, ...] = ("/tmp:rw,nosuid,nodev,size=128m",)
    workdir: str = "/work"
    extra_run_args: tuple[str, ...] = ()

    def run_args(
        self,
        name: str,
        docker: str = "docker",
        *,
        entrypoint: str = KEEPALIVE_ENTRYPOINT,
        keepalive: tuple[str, ...] = KEEPALIVE_ARGS,
    ) -> list[str]:
        """构造 ``docker run -d`` 参数：常驻容器 = 覆盖 entrypoint + tail 保活。

        必须覆盖 entrypoint：``porta-bench-runtime-cpp`` / ``safecoder-python-validator``
        的 ENTRYPOINT 是 ``python3 -m workflow.snapshot_ci.docker_runner``，
        不覆盖的话 ``tail`` 只是它的参数，容器会立刻退出。
        """
        args = [
            docker,
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "--stop-timeout",
            "1",
            "--memory",
            self.memory,
            "--cpus",
            self.cpus,
            "--pids-limit",
            str(self.pids_limit),
        ]
        if self.network is not None:
            args.extend(["--network", self.network])
        for item in self.tmpfs:
            args.extend(["--tmpfs", item])
        for host_path, container_path in self.mounts:
            args.extend(["-v", f"{host_path}:{container_path}"])
        for host_path, container_path in self.readonly_mounts:
            args.extend(["-v", f"{host_path}:{container_path}:ro"])
        for key, value in self.env:
            args.extend(["-e", f"{key}={value}"])
        args.extend(self.extra_run_args)
        args.extend(["--entrypoint", entrypoint, self.image, *keepalive])
        return args


@dataclass
class ExecResult:
    """一次 ``docker exec`` 的结果。

    超时语义拆成三层，调用方按需要取用，不要只看 ``returncode``：

    - ``timed_out``：容器内 timeout 或宿主侧兜底**任一**判定为超时；
    - ``container_timed_out``：容器内 ``timeout`` 生效（这是正常路径，
      说明任务真的跑太久，样本应按"超时/未完成"处理，不能算通过）；
    - ``host_timed_out``：宿主侧兜底超时（异常路径，说明容器内 timeout
      没兜住，例如命令忽略了 SIGTERM 又超过了宿主侧上限）。
    """

    argv: list[str]
    container: str
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float
    container_timed_out: bool = False
    host_timed_out: bool = False

    def as_details(self) -> dict[str, Any]:
        """写进 ``ValidationResult.details`` 的脱敏摘要（不含完整 argv 内容）。"""
        return {
            "container": self.container,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "container_timed_out": self.container_timed_out,
            "host_timed_out": self.host_timed_out,
            "duration_s": round(self.duration_s, 3),
        }


# --------------------------------------------------------------------------- #
# 常驻容器
# --------------------------------------------------------------------------- #


class PersistentContainer:
    """一个常驻容器的生命周期与逐任务 exec。"""

    def __init__(self, spec: ContainerSpec, name: str, *, docker: str = "docker") -> None:
        self.spec = spec
        self.name = name
        self.docker = docker
        self.events: list[dict[str, Any]] = []

    # ---- 生命周期 -------------------------------------------------------- #

    def start(self) -> None:
        """启动常驻容器；失败时抛 RuntimeError（调用方折算成 environment_error）。"""
        self._remove_if_exists()
        args = self.spec.run_args(self.name, docker=self.docker)
        proc = subprocess.run(args, capture_output=True, text=True, timeout=180, check=False)
        if proc.returncode != 0:
            # 极简镜像可能没有 tail，退回到 sh + sleep 保活。
            fallback = self.spec.run_args(
                self.name,
                docker=self.docker,
                entrypoint="sh",
                keepalive=("-c", "exec sleep infinity"),
            )
            proc = subprocess.run(fallback, capture_output=True, text=True, timeout=180, check=False)
            if proc.returncode != 0:
                raise RuntimeError(f"docker run failed for {self.name}: {proc.stderr.strip()[:400]}")
        self.events.append({"event": "container_started", "container": self.name, "image": self.spec.image})

    def stop(self) -> None:
        """评测结束时删除容器。只删容器，镜像层保留供下次复用。"""
        force_remove_docker_container(self.name, docker=self.docker)
        self.events.append({"event": "container_stopped", "container": self.name})

    def is_running(self) -> bool:
        proc = subprocess.run(
            [self.docker, "inspect", "-f", "{{.State.Running}}", self.name],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "true"

    def _remove_if_exists(self) -> None:
        force_remove_docker_container(self.name, docker=self.docker)

    # ---- 任务级执行 ------------------------------------------------------ #

    def exec_argv(
        self,
        argv: list[str],
        *,
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 60,
        container_timeout: int | None = None,
        output_limit: int = DEFAULT_OUTPUT_LIMIT,
        cwd: Path | None = None,
    ) -> ExecResult:
        """在常驻容器里执行一条命令。

        ``container_timeout`` 给出时，命令会被容器内 ``timeout`` 包住（推荐），
        宿主侧 ``timeout`` 只作为兜底，应比它大若干秒。
        """
        effective = list(argv)
        if container_timeout is not None:
            effective = wrap_linux_timeout(container_timeout, effective)
        args = [self.docker, "exec"]
        if workdir:
            args.extend(["-w", workdir])
        for key, value in (env or {}).items():
            args.extend(["-e", f"{key}={value}"])
        args.append(self.name)
        args.extend(effective)
        tic = time.perf_counter()
        returncode, stdout, stderr, host_timed_out = run_limited_command(
            args,
            cwd=cwd or Path.cwd(),
            timeout=timeout,
            output_limit=output_limit,
        )
        duration = time.perf_counter() - tic
        # 容器内 timeout 生效的判定：退出码落在超时码集合内，**且**耗时确实接近
        # 阈值。后者用来排除"命令自己以 124/143 退出"的误判——alpine 实测两者
        # 退出码完全相同，只能靠时长区分（见 wrap_linux_timeout 的说明）。
        container_timed_out = (
            container_timeout is not None
            and not host_timed_out
            and returncode in TIMEOUT_EXIT_CODES
            and duration >= container_timeout * TIMEOUT_DURATION_RATIO
        )
        result = ExecResult(
            argv=args,
            container=self.name,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            timed_out=host_timed_out or container_timed_out,
            duration_s=duration,
            container_timed_out=container_timed_out,
            host_timed_out=host_timed_out,
        )
        if host_timed_out:
            # 宿主侧超时：容器内进程可能还活着，立刻清理，避免它继续吃 CPU/内存。
            # 容器内 timeout 生效时不需要这一步——Linux 已经杀干净了。
            self.reap()
        return result

    def reap(self) -> None:
        """清理容器内残留进程（宿主侧兜底超时后的最后一道防线）。

        为什么是"清掉除 PID 1 以外的所有进程"而不是按命令行模式匹配：
        宿主侧超时杀掉的是 ``docker exec`` 客户端，容器里的真实命令会变成孤儿。
        这个孤儿进程的 argv 不一定含 ``/work/``（例如 ``sleep 120``），
        按模式匹配会漏杀，于是残留进程继续吃 CPU/内存，还会让随后的
        ``docker stop`` 变慢。因此这里直接按 PID 全清。

        安全前提（必须成立，否则会误杀）：
        1. 池保证一个容器同一时刻只被一个任务独占（``ContainerPool.acquire``），
           所以容器内除 PID 1 外的进程都属于本次超时的任务；
        2. PID 1 是保活进程（``tail -f /dev/null``），永远不杀——杀了容器就退出，
           池会走 ``_replace`` 重建，代价高且掩盖真实问题；
        3. 排除自身 ``$$`` 与父进程 ``$PPID``，否则会把自己（正在执行清理的
           ``sh``）或 ``docker exec`` 的 init 杀掉，命令提前中断。

        纯 POSIX 实现，不依赖 ``pkill`` / ``grep``（极简镜像可能没有）。
        未测量项：本函数不判断被清理进程是否真的属于本任务，
        依赖上述前提 1；若调用方绕过池直接共享容器，本函数不安全。
        """
        script = (
            "self=$$; "
            "for d in /proc/[0-9]*; do "
            "p=${d#/proc/}; "
            'if [ "$p" = "1" ] || [ "$p" = "$self" ] || [ "$p" = "$PPID" ]; then continue; fi; '
            'kill -9 "$p" 2>/dev/null || true; '
            "done; "
            "exit 0"
        )
        try:
            subprocess.run(
                [self.docker, "exec", self.name, "sh", "-c", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            # 容器已经不可用：交给 is_running()/池的替换逻辑处理，这里不抛出。
            pass

    def remove_path(self, container_path: str) -> None:
        """删除容器内的任务目录（任务级空间即写即清）。"""
        subprocess.run(
            [self.docker, "exec", self.name, "rm", "-rf", container_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
            check=False,
        )


# --------------------------------------------------------------------------- #
# 容器池
# --------------------------------------------------------------------------- #


def attach_container(name: str, *, docker: str = "docker") -> PersistentContainer:
    """绑定到一个**已存在**的容器，只用于执行 ``docker exec``。

    用于调用方自己管理容器生命周期的场景（例如 SeCodePLT 执行器由
    ``create_executor_container`` / ``remove_executor_container`` 成对管理）。
    这里不创建、不删除、不校验容器是否存在——容器不存在时 ``exec_argv``
    会拿到非零返回码，由调用方按环境错误处理。

    ``spec`` 里的 ``image`` 字段只被 ``start()`` 使用，因此这里填占位值。
    """
    return PersistentContainer(ContainerSpec(image="<attached>"), name, docker=docker)


class ContainerPool:
    """N 个常驻容器的复用池：评测开始时一次性启动，评测结束统一删除。

    ``acquire`` 返回上下文管理器，保证异常路径也把容器还回池里；
    容器不可用时替换成新容器，并把事件记进 ``self.events``（写进 run_metadata）。
    """

    def __init__(
        self,
        spec: ContainerSpec,
        *,
        size: int = 4,
        docker: str = "docker",
        prefix: str = POOL_NAME_PREFIX,
        run_tag: str | None = None,
    ) -> None:
        self.spec = spec
        self.size = max(1, int(size))
        self.docker = docker
        self.prefix = prefix
        self.run_tag = run_tag or uuid.uuid4().hex[:8]
        self.events: list[dict[str, Any]] = []
        self._containers: list[PersistentContainer] = []
        self._free: list[PersistentContainer] = []
        self._lock = threading.Lock()

    # ---- 生命周期 -------------------------------------------------------- #

    def start(self) -> None:
        for index in range(self.size):
            container = PersistentContainer(
                self.spec,
                f"{self.prefix}{self.run_tag}-{index}",
                docker=self.docker,
            )
            container.start()
            self._containers.append(container)
            self._free.append(container)
            self.events.extend(container.events)

    def stop(self) -> None:
        for container in self._containers:
            container.stop()
            self.events.extend(container.events)
        self._containers.clear()
        self._free.clear()

    def __enter__(self) -> "ContainerPool":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def running_names(self) -> list[str]:
        return [c.name for c in self._containers if c.is_running()]

    @contextmanager
    def acquire(self) -> Iterator[PersistentContainer]:
        """借一个容器；归还时如果它已经不可用，就替换成新容器。

        池大小必须 >= 评测并发数；池耗尽会直接报错而不是悄悄新建容器，
        这样"评测期间不新建容器"这条约束不会被并发掩盖。
        """
        with self._lock:
            if not self._free:
                raise RuntimeError(
                    f"container pool exhausted (size={self.size}); pool size must be >= concurrency"
                )
            container = self._free.pop()
        try:
            yield container
        finally:
            with self._lock:
                if container.is_running():
                    self._free.append(container)
                else:
                    self._replace(container)

    def _replace(self, broken: PersistentContainer) -> None:
        """单个容器失效时重建（异常路径，正常评测不会发生）。

        重建失败只记录事件、不抛出：否则会掩盖触发本次替换的原始异常。
        池随后会以"exhausted"形式在下次 acquire 时暴露，信号更清晰。
        """
        self.events.append({"event": "container_replaced", "container": broken.name})
        index = self._containers.index(broken) if broken in self._containers else len(self._containers)
        replacement = PersistentContainer(
            self.spec,
            f"{self.prefix}{self.run_tag}-{index}-r{uuid.uuid4().hex[:4]}",
            docker=self.docker,
        )
        try:
            replacement.start()
        except RuntimeError as exc:
            self.events.append(
                {
                    "event": "container_replace_failed",
                    "container": replacement.name,
                    "message": str(exc)[:200],
                }
            )
            return
        if broken in self._containers:
            self._containers[self._containers.index(broken)] = replacement
        else:
            self._containers.append(replacement)
        self._free.append(replacement)
        self.events.extend(replacement.events)


def cleanup_stale_containers(prefix: str = POOL_NAME_PREFIX, docker: str = "docker") -> list[str]:
    """删除上次异常退出残留的池容器。

    这是 2026-09-17 事故（强杀进程留下 8 个孤儿容器）的针对性防护：
    评测前置检查调用一次，保证起点是干净的，且压缩脚本不会被运行中容器挡住。
    """
    try:
        proc = subprocess.run(
            [docker, "ps", "-a", "--filter", f"name={prefix}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    names = [line.strip() for line in (proc.stdout or "").splitlines() if line.strip()]
    for name in names:
        force_remove_docker_container(name, docker=docker)
    return names


# --------------------------------------------------------------------------- #
# 只读磁盘计量
# --------------------------------------------------------------------------- #


def docker_data_vhdx_path() -> Path | None:
    """定位 Docker Desktop 的 WSL2 数据盘 docker_data.vhdx。"""
    appdata = os.environ.get("APPDATA")
    if appdata:
        settings_path = Path(appdata) / "Docker" / "settings-store.json"
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text(encoding="utf-8"))
                custom = settings.get("CustomWslDistroDir")
                if custom:
                    candidate = Path(custom) / "disk" / "docker_data.vhdx"
                    if candidate.exists():
                        return candidate
            except (OSError, json.JSONDecodeError):
                pass
    local_appdata = os.environ.get("LOCALAPPDATA")
    candidates = [
        Path("D:/DockerDesktopLocal/wsl-data/disk/docker_data.vhdx"),
    ]
    if local_appdata:
        candidates.extend(
            [
                Path(local_appdata) / "Docker" / "wsl" / "data" / "ext4.vhdx",
                Path(local_appdata) / "Docker" / "wsl" / "disk" / "docker_data.vhdx",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _probe_internal_usage(docker: str, image: str) -> dict[str, int] | None:
    """在一次性容器里只读挂载数据盘，读出内部真实用量。

    这是 ``wsl -d docker-desktop -e df`` 的替代口径：本机 ``wsl.exe`` 被安全策略
    拦截，而 ``docker run --rm -v /mnt/docker-desktop-disk:/dd:ro`` 不需要 ``wsl``、
    不需要管理员，且容器结束即删（容器可写层为 0）。
    """
    try:
        probe = subprocess.run(
            [docker, "image", "inspect", "-f", "{{.Id}}", image],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if probe.returncode != 0:
            return None
        proc = subprocess.run(
            [
                docker,
                "run",
                "--rm",
                "--network",
                "none",
                "-v",
                "/mnt/docker-desktop-disk:/dd:ro",
                image,
                "sh",
                "-c",
                "df -B1 /dd | tail -n 1; du -s -B1 /dd/data /dd/isocache 2>/dev/null || true",
            ],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    result: dict[str, int] = {}
    lines = [line for line in (proc.stdout or "").splitlines() if line.strip()]
    if lines:
        fields = lines[0].split()
        # df -B1: Filesystem 1B-blocks Used Available Use% Mounted-on
        if len(fields) >= 3 and fields[1].isdigit() and fields[2].isdigit():
            result["filesystem_total_bytes"] = int(fields[1])
            result["filesystem_used_bytes"] = int(fields[2])
    for line in lines[1:]:
        fields = line.split()
        if len(fields) == 2 and fields[0].isdigit():
            if fields[1].endswith("/data"):
                result["image_store_bytes"] = int(fields[0])
            elif fields[1].endswith("/isocache"):
                result["isocache_bytes"] = int(fields[0])
    return result or None


def measure_docker_disk(
    docker: str = "docker",
    *,
    probe_image: str | None = None,
) -> dict[str, Any]:
    """只读测量 Docker 数据盘水位与内部用量，供实验前后各记一次。

    返回字段：
    ``vhdx_path`` / ``vhdx_bytes``（Windows 看到的文件大小，只涨不缩的高水位）、
    ``filesystem_used_bytes``（内部真实用量）、
    ``reclaimable_bytes``（二者之差，即 compact 能回收的量）。
    """
    probe_image = probe_image or os.environ.get("SAFECODER_DISK_PROBE_IMAGE", "python:3.11-alpine")
    report: dict[str, Any] = {"probe_image": probe_image}
    vhdx = docker_data_vhdx_path()
    if vhdx is not None:
        try:
            report["vhdx_path"] = str(vhdx)
            report["vhdx_bytes"] = vhdx.stat().st_size
        except OSError:
            pass
    internal = _probe_internal_usage(docker, probe_image) if docker_available(docker) else None
    if internal:
        report.update(internal)
    if "vhdx_bytes" in report and "filesystem_used_bytes" in report:
        report["reclaimable_bytes"] = max(0, report["vhdx_bytes"] - report["filesystem_used_bytes"])
    return report


# --------------------------------------------------------------------------- #
# 模块级池：给"没有显式池"的旧调用点兜底
# --------------------------------------------------------------------------- #

_IMPLICIT_POOLS: dict[str, ContainerPool] = {}
_IMPLICIT_LOCK = threading.Lock()


def implicit_pool(spec: ContainerSpec, *, docker: str = "docker") -> ContainerPool:
    """按镜像复用进程级容器池。

    旧调用点（``validate_cpp_program_docker`` 等）没有显式的池生命周期，
    这里按 ``image`` 维度懒创建，并用 ``atexit`` 在进程退出时统一删除容器。
    """
    key = spec.image
    with _IMPLICIT_LOCK:
        pool = _IMPLICIT_POOLS.get(key)
        if pool is None:
            pool = ContainerPool(spec, size=int(os.environ.get("SAFECODER_DOCKER_POOL_SIZE", "4")), docker=docker)
            pool.start()
            _IMPLICIT_POOLS[key] = pool
        return pool


def close_implicit_pools() -> None:
    """进程退出前删除所有隐式池容器（``atexit`` 注册用）。"""
    with _IMPLICIT_LOCK:
        pools = list(_IMPLICIT_POOLS.values())
        _IMPLICIT_POOLS.clear()
    for pool in pools:
        try:
            pool.stop()
        except Exception:
            pass


# 注册时机放在模块末尾：即使调用方忘了显式 close，进程正常退出时也会删除容器，
# 不会重演 2026-09-17 的孤儿容器事故。被 SIGKILL 时仍可能残留，
# 因此评测前置检查还要配合 cleanup_stale_containers() 使用。
atexit.register(close_implicit_pools)

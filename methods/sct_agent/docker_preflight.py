"""CodeSecEval Docker 运行前置检查。

PLT 训练侧使用本地 Python 子进程，不调用本模块。Base/Plus 冻结评测在
发起模型请求前调用这里，避免 Docker 守护进程不可用时生成一批没有模型
性能含义的 ``environment_error`` 记录。
"""

from __future__ import annotations

import subprocess
from typing import Any


def run_docker_preflight(docker_cmd: str = "docker", timeout: int = 15) -> dict[str, Any]:
    """检查 Docker daemon 是否可访问并返回脱敏的版本信息。

    所属阶段：冻结后的 CodeSecEval Base/Plus 评测开始前。输入是 Docker
    可执行文件名和短超时；输出只包含成功状态、版本或结构化错误类型。
    失败表示环境阻断，调用方必须停止正式评测，不得将它折算为模型失败。
    """
    command = [docker_cmd, "info", "--format", "{{.ServerVersion}}"]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "ok": False,
            "error_type": "environment_error",
            "message": type(exc).__name__,
            "command": command[:3],
        }
    if completed.returncode != 0:
        return {
            "ok": False,
            "error_type": "environment_error",
            "message": "docker_info_failed",
            "command": command[:3],
        }
    version = (completed.stdout or "").strip().splitlines()[0] if (completed.stdout or "").strip() else "unknown"
    return {"ok": True, "version": version, "command": command[:3]}

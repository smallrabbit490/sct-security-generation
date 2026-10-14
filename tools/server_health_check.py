#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_health_check.py — 在 Windows 本机通过 SSH 拉取服务器健康快照

做三件事：
    1. 从 服务器连接/用户名密码等等.txt 读取凭据（密码只在内存里，绝不打印、绝不硬编码）；
    2. 把 tools/server_monitor.py 上传到服务器 ~/server_monitor.py（保证远端是最新版）；
    3. 远程执行 `python3 ~/server_monitor.py --once --no-color`，把结果原样打印出来。

用法（必须用装了 paramiko 的解释器运行）：
    PY="C:/Users/86136/.workbuddy-ai/binaries/python/envs/default/Scripts/python.exe"
    "$PY" tools/server_health_check.py                 # 拉一次快照
    "$PY" tools/server_health_check.py --watch -i 5    # 每 5 秒刷新一次（Ctrl+C 退出）
    "$PY" tools/server_health_check.py --no-upload     # 不覆盖服务器上已有的脚本
    "$PY" tools/server_health_check.py --json          # 直接取远端 JSON

依赖：paramiko（已装在上述 venv 里）。
"""

import argparse
import os
import sys
import time

try:
    import paramiko
except ImportError:
    sys.stderr.write("缺少 paramiko，请用托管 venv 的解释器运行本脚本。\n")
    sys.exit(2)


# ---------------------------------------------------------------------------
# 凭据解析：格式是「键 值」的松散中文键值对
# ---------------------------------------------------------------------------

CRED_KEYWORDS = {
    "ip": ("ip", "地址", "主机", "host"),
    "port": ("端口", "port"),
    "user": ("用户名", "用户", "user", "username"),
    "pwd": ("密码", "password", "passwd", "pwd"),
}


def find_cred_file(explicit=None):
    """定位凭据文件；找不到返回 None。"""
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "..", "服务器连接", "用户名密码等等.txt"),
        os.path.join(here, "..", "服务器连接"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def parse_creds(path):
    """解析凭据文件，返回 dict。密码值不会被打印到任何地方。"""
    creds = {}
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.replace("：", ":").split()
            if len(parts) < 2:
                continue
            key = parts[0].strip().lower()
            value = parts[1].strip()
            for field, keywords in CRED_KEYWORDS.items():
                if field in creds:
                    continue
                if any(kw in key for kw in keywords):
                    creds[field] = value
                    break
    return creds


# ---------------------------------------------------------------------------
# SSH
# ---------------------------------------------------------------------------

def connect(creds, timeout=15):
    """建立 SSH 连接。异常只打印类型名，避免凭据泄漏到日志里。"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=creds["ip"],
        port=int(creds.get("port", 22)),
        username=creds["user"],
        password=creds["pwd"],
        look_for_keys=False,
        allow_agent=False,
        timeout=timeout,
        banner_timeout=20,
        auth_timeout=20,
    )
    return client


def upload_script(client, local_path, remote_path):
    """用 SFTP 把监控脚本推到远端。"""
    sftp = client.open_sftp()
    try:
        sftp.put(local_path, remote_path)
        sftp.chmod(remote_path, 0o755)
    finally:
        sftp.close()


def run_remote(client, command, timeout=120):
    """执行远端命令，返回 (退出码, stdout, stderr)。"""
    _, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return stdout.channel.recv_exit_status(), out, err


def main():
    parser = argparse.ArgumentParser(description="通过 SSH 拉取服务器健康快照")
    parser.add_argument("--creds", help="凭据文件路径，默认自动查找")
    parser.add_argument("--local-script", help="本地监控脚本路径，默认 tools/server_monitor.py")
    parser.add_argument("--remote-script", default="server_monitor.py", help="远端脚本路径（家目录下）")
    parser.add_argument("--no-upload", action="store_true", help="不覆盖服务器上已有的监控脚本")
    parser.add_argument("--watch", action="store_true", help="循环刷新")
    parser.add_argument("-i", "--interval", type=float, default=5.0, help="循环刷新的间隔秒数")
    parser.add_argument("--json", action="store_true", help="输出远端 JSON")
    args = parser.parse_args()

    cred_path = find_cred_file(args.creds)
    if not cred_path:
        sys.stderr.write("找不到凭据文件，请用 --creds 指定。\n")
        return 2
    creds = parse_creds(cred_path)
    for field in ("ip", "user", "pwd"):
        if field not in creds:
            sys.stderr.write("凭据文件缺少字段：%s\n" % field)
            return 2

    here = os.path.dirname(os.path.abspath(__file__))
    local_script = args.local_script or os.path.join(here, "server_monitor.py")
    if not os.path.isfile(local_script):
        sys.stderr.write("找不到本地监控脚本：%s\n" % local_script)
        return 2

    try:
        client = connect(creds)
    except Exception as exc:
        sys.stderr.write("SSH 连接失败：%s（请确认服务器在线、IP 与端口正确）\n" % type(exc).__name__)
        return 3

    try:
        if not args.no_upload:
            try:
                upload_script(client, local_script, args.remote_script)
            except Exception as exc:
                sys.stderr.write("上传脚本失败：%s（可用 --no-upload 跳过）\n" % type(exc).__name__)

        flags = "--json" if args.json else "--once --no-color"
        command = "python3 ~/%s %s" % (args.remote_script, flags)

        while True:
            code, out, err = run_remote(client, command, timeout=120)
            if code != 0:
                sys.stderr.write("远端执行失败（退出码 %d）：%s\n" % (code, err.strip()[:400]))
                return 4
            sys.stdout.write(out)
            sys.stdout.flush()
            if not args.watch:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

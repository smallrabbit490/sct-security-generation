#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
server_monitor.py — Linux 服务器实时健康监控面板（单文件 / 仅 Python 标准库）

用途
    实时查看 Linux 服务器的 CPU/GPU 温度、热降频状态、负载、内存、磁盘、网络、
    进程与 Docker 容器等指标，并对每一项给出「正常 / 注意 / 严重」判定。

用法
    python3 server_monitor.py                  # 实时面板（默认 2 秒刷新，Ctrl+C 退出）
    python3 server_monitor.py -i 1             # 1 秒刷新
    python3 server_monitor.py --once           # 打印一次快照后退出（适合远程拉取 / cron）
    python3 server_monitor.py --once --json    # 输出 JSON，便于其他脚本消费
    python3 server_monitor.py --log mon.jsonl  # 每次采样追加一行 JSONL，供事后分析
    python3 server_monitor.py -d 60            # 只监控 60 秒后自动退出（适合放 tmux 里跑一段）
    python3 server_monitor.py --no-color       # 关闭 ANSI 颜色（非终端输出会自动关闭）

设计要点
    - 只读：数据全部来自 /proc、/sys、sensors、nvidia-smi、df、ps、docker ps，
      不写任何文件（--log 除外，且由用户显式指定）。
    - 温度优先走 `sensors -j`（JSON，解析稳定）；没有 lm-sensors 时回退到
      /sys/class/thermal 与 /sys/class/hwmon。
    - 热降频是监控重点，同时检查四类证据：
        1) coretemp 的 crit_alarm 标志（是否已顶到 Tjmax）
        2) /sys/.../thermal_throttle 计数器增量（是否真的在降频）
        3) intel_powerclamp 的 kidle_inj 注入线程（内核是否在强制压频率）
        4) CPU 实际运行频率 vs 标称最大频率（降频幅度）
    - 任何一个数据源缺失都只显示 N/A，绝不让整个面板崩掉。
"""

import argparse
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from collections import deque

# ---------------------------------------------------------------------------
# 常量与阈值
# ---------------------------------------------------------------------------

LEVEL_OK = "OK"
LEVEL_WARN = "WARN"
LEVEL_CRIT = "CRIT"
LEVEL_NA = "NA"

LEVEL_RANK = {LEVEL_OK: 0, LEVEL_NA: 0, LEVEL_WARN: 1, LEVEL_CRIT: 2}
LEVEL_TEXT = {LEVEL_OK: "正常", LEVEL_WARN: "注意", LEVEL_CRIT: "严重", LEVEL_NA: "无数据"}

# 判定阈值：(警告线, 危险线)
TH = {
    "cpu_temp": (80.0, 92.0),      # 摄氏；到 crit 线即视为严重
    "gpu_temp": (78.0, 85.0),      # RTX 4090 的降频点约 83~88
    "gpu_mem_pct": (85.0, 95.0),
    "nvme_temp": (60.0, 75.0),
    "load_per_core": (0.80, 1.20),
    "mem_pct": (80.0, 92.0),
    "swap_pct": (10.0, 50.0),
    "disk_pct": (80.0, 90.0),
    "iowait_pct": (15.0, 30.0),
    "freq_ratio": (0.50, 0.30),    # 注意：越小越糟，所以顺序反过来用
}

# CJK 字符在终端里占 2 列，这里列出主要区段用于计算显示宽度
CJK_RANGES = (
    (0x1100, 0x115F), (0x2E80, 0xA4CF), (0xAC00, 0xD7A3), (0xF900, 0xFAFF),
    (0xFE30, 0xFE6F), (0xFF00, 0xFF60), (0xFFE0, 0xFFE6), (0x20000, 0x3FFFD),
)

SPARK_CHARS = "▁▂▃▄▅▆▇█"


# ---------------------------------------------------------------------------
# 基础工具：字符串宽度 / 颜色 / 文件与命令读取
# ---------------------------------------------------------------------------

def dwidth(text):
    """计算字符串在终端中的显示宽度（中文/全角按 2 列计）。"""
    width = 0
    for ch in text:
        cp = ord(ch)
        if cp < 32:
            continue
        if any(lo <= cp <= hi for lo, hi in CJK_RANGES):
            width += 2
        else:
            width += 1
    return width


def pad(text, width, align="left"):
    """按显示宽度补齐空格，保证中英混排也能对齐。"""
    gap = max(0, width - dwidth(text))
    if align == "right":
        return " " * gap + text
    if align == "center":
        left = gap // 2
        return " " * left + text + " " * (gap - left)
    return text + " " * gap


def clip(text, width):
    """按显示宽度截断，超出部分用 … 收尾。"""
    if dwidth(text) <= width:
        return text
    out = ""
    used = 0
    for ch in text:
        cw = dwidth(ch)
        if used + cw > width - 1:
            break
        out += ch
        used += cw
    return out + "…"


class Paint(object):
    """极简 ANSI 着色器；关闭时所有方法退化为原样返回。"""

    def __init__(self, enabled):
        self.on = bool(enabled)

    def _wrap(self, code, text):
        if not self.on:
            return text
        return "\033[" + code + "m" + text + "\033[0m"

    def ok(self, t):
        return self._wrap("32", t)

    def warn(self, t):
        return self._wrap("33", t)

    def crit(self, t):
        return self._wrap("1;31", t)

    def dim(self, t):
        return self._wrap("2", t)

    def head(self, t):
        return self._wrap("1;36", t)

    def bold(self, t):
        return self._wrap("1", t)

    def by_level(self, level, text):
        if level == LEVEL_CRIT:
            return self.crit(text)
        if level == LEVEL_WARN:
            return self.warn(text)
        if level == LEVEL_NA:
            return self.dim(text)
        return self.ok(text)


def slurp(path, default=None):
    """读取一个小文件；失败返回 default（监控脚本不允许因为缺文件而崩）。"""
    try:
        with open(path, "r") as fh:
            return fh.read().strip()
    except Exception:
        return default


def run_cmd(cmd, timeout=8):
    """执行外部命令并返回 stdout 文本；失败返回 None。"""
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=timeout
        )
        return proc.stdout.decode("utf-8", errors="replace")
    except Exception:
        return None


def human_bytes(num):
    """字节数转人类可读。"""
    if num is None:
        return "N/A"
    step = 1024.0
    val = float(num)
    for unit in ("B", "K", "M", "G", "T", "P"):
        if abs(val) < step:
            if unit == "B":
                return "%d%s" % (int(val), unit)
            return "%.1f%s" % (val, unit)
        val /= step
    return "%.1fE" % val


def human_duration(seconds):
    """秒数转 1d2h3m4s 形式。"""
    try:
        seconds = int(seconds)
    except Exception:
        return "N/A"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append("%dd" % days)
    if hours or days:
        parts.append("%dh" % hours)
    if mins or hours or days:
        parts.append("%dm" % mins)
    parts.append("%ds" % secs)
    return "".join(parts)


def rate_or_none(cur, prev, dt):
    """计算增量速率（每秒）；缺少上一次采样或时间差为 0 时返回 None。"""
    if cur is None or prev is None or not dt:
        return None
    return (cur - prev) / float(dt)


# ---------------------------------------------------------------------------
# 采集器：温度
# ---------------------------------------------------------------------------

def collect_temps():
    """采集所有温度。

    返回 dict：
        cpu_package      封装温度（摄氏度）
        cpu_cores        [(名称, 温度), ...] 各核心温度
        cpu_core_max     最高的单核温度
        cpu_high/cpu_crit 传感器给出的高/临界阈值
        cpu_crit_alarm   传感器是否已置位临界报警
        nvme             {传感器名: 温度}
        source           数据来源标签
    """
    out = {
        "cpu_package": None,
        "cpu_cores": [],
        "cpu_core_max": None,
        "cpu_high": None,
        "cpu_crit": None,
        "cpu_crit_alarm": False,
        "nvme": {},
        "source": "none",
    }

    raw = run_cmd(["sensors", "-j"])
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = None
        if isinstance(data, dict):
            out["source"] = "sensors -j"
            for chip, features in data.items():
                if not isinstance(features, dict):
                    continue
                chip_l = chip.lower()
                is_cpu_chip = any(k in chip_l for k in ("coretemp", "k10temp", "zenpower", "cpu_thermal"))
                is_nvme_chip = "nvme" in chip_l
                if not (is_cpu_chip or is_nvme_chip):
                    continue
                for feat, values in features.items():
                    if not isinstance(values, dict):
                        continue
                    temp = None
                    for key, val in values.items():
                        if not isinstance(val, (int, float)):
                            continue
                        if key.endswith("_input"):
                            temp = float(val)
                        elif is_cpu_chip and key.endswith("_max") and "_crit" not in key:
                            out["cpu_high"] = float(val)
                        elif is_cpu_chip and key.endswith("_crit"):
                            out["cpu_crit"] = float(val)
                        elif is_cpu_chip and key.endswith("_crit_alarm") and float(val) >= 1:
                            out["cpu_crit_alarm"] = True
                    if temp is None:
                        continue
                    if is_nvme_chip:
                        out["nvme"][feat] = temp
                        continue
                    feat_l = feat.lower()
                    if feat_l.startswith("package") or feat_l.startswith("tdie") or feat_l.startswith("tctl"):
                        if out["cpu_package"] is None or temp > out["cpu_package"]:
                            out["cpu_package"] = temp
                    elif feat_l.startswith("core") or feat_l.startswith("tccd"):
                        out["cpu_cores"].append((feat, temp))

    # 回退 1：/sys/class/thermal（x86_pkg_temp 等）
    if out["cpu_package"] is None:
        for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
            ztype = (slurp(os.path.join(zone, "type")) or "").lower()
            ztemp = slurp(os.path.join(zone, "temp"))
            if ztemp is None:
                continue
            try:
                val = float(ztemp) / 1000.0
            except Exception:
                continue
            if not val or val < -50 or val > 200:
                continue
            if any(k in ztype for k in ("pkg", "x86", "cpu", "soc")):
                out["cpu_package"] = val
                out["source"] = "thermal_zone"
                break

    # 回退 2：/sys/class/hwmon 里名为 coretemp 的设备
    if out["cpu_package"] is None:
        for hw in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
            name = (slurp(os.path.join(hw, "name")) or "").lower()
            if "coretemp" not in name and "k10temp" not in name:
                continue
            for tfile in sorted(glob.glob(os.path.join(hw, "temp*_input"))):
                try:
                    val = float(slurp(tfile)) / 1000.0
                except Exception:
                    continue
                if out["cpu_package"] is None or val > out["cpu_package"]:
                    out["cpu_package"] = val
                out["cpu_cores"].append((os.path.basename(tfile), val))
            if out["cpu_package"] is not None:
                out["source"] = "hwmon"
                break

    if out["cpu_cores"]:
        out["cpu_core_max"] = max(t for _, t in out["cpu_cores"])
    return out


# ---------------------------------------------------------------------------
# 采集器：降频 / 频率
# ---------------------------------------------------------------------------

def read_throttle_counters():
    """读取热降频计数器。

    返回 (core_total, package_max)；内核没提供这些文件时返回 None。
    core_throttle_count 是每核计数，累加；package_throttle_count 是整包计数，
    同一封装内各 CPU 会给出相同值，所以取最大值而不是累加。
    """
    core_total = 0
    package_max = 0
    found = False
    for path in glob.glob("/sys/devices/system/cpu/cpu*/thermal_throttle/core_throttle_count"):
        val = slurp(path)
        if val is None:
            continue
        try:
            core_total += int(val)
            found = True
        except Exception:
            pass
    for path in glob.glob("/sys/devices/system/cpu/cpu*/thermal_throttle/package_throttle_count"):
        val = slurp(path)
        if val is None:
            continue
        try:
            package_max = max(package_max, int(val))
            found = True
        except Exception:
            pass
    if not found:
        return None
    return core_total, package_max


def read_throttle_time():
    """读取累计降频耗时（毫秒），用于判断降频是否"刚发生"。"""
    total = 0
    found = False
    for path in glob.glob("/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_total_time_ms"):
        val = slurp(path)
        if val is None:
            continue
        try:
            total = int(val)
            found = True
        except Exception:
            pass
    return total if found else None


def read_rapl():
    """读取 Intel RAPL 的累计能耗（微焦），用于推算 CPU 封装真实功耗。

    这是区分"负载太大"和"散热坏了"的关键证据：
    如果封装功耗只有几十瓦、温度却顶在 Tjmax，说明热量根本散不出去，
    问题在风扇/水冷泵/硅脂，而不在于任务太重。
    energy_uj 通常只有 root 可读；读不到就返回空字典，面板显示 N/A。
    """
    domains = {}
    for name_path in sorted(glob.glob("/sys/class/powercap/intel-rapl:*/name")):
        base = os.path.dirname(name_path)
        name = slurp(name_path)
        energy = slurp(os.path.join(base, "energy_uj"))
        if name is None or energy is None:
            continue
        try:
            domains[name] = float(energy)
        except Exception:
            pass
    return domains


def read_cpu_freq():
    """读取各核当前频率与标称最大频率，单位 MHz。"""
    cur = []
    for path in sorted(glob.glob("/sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq")):
        val = slurp(path)
        if val is None:
            continue
        try:
            cur.append(float(val) / 1000.0)
        except Exception:
            pass
    maxf = None
    for path in ("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq",
                 "/sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq"):
        val = slurp(path)
        if val:
            try:
                maxf = float(val) / 1000.0
                break
            except Exception:
                pass
    if maxf is None:
        lscpu = run_cmd(["lscpu"])
        if lscpu:
            match = re.search(r"CPU max MHz:\s*([0-9.]+)", lscpu)
            if match:
                maxf = float(match.group(1))
    return cur, maxf


def detect_powerclamp():
    """检测内核是否在用 intel_powerclamp 强制注入空闲来压温度。

    这是"CPU 已经过热到需要内核出手干预"的直接证据：
    kidle_inj/* 内核线程每个都跑满一个核来制造 idle 时间。
    """
    modules = slurp("/proc/modules", "") or ""
    loaded = "intel_powerclamp" in modules
    count_text = run_cmd(["pgrep", "-c", "kidle_inj"], timeout=6)
    try:
        threads = int((count_text or "0").strip() or 0)
    except Exception:
        threads = 0
    return {"loaded": loaded, "threads": threads}


# ---------------------------------------------------------------------------
# 采集器：CPU 使用率 / 负载
# ---------------------------------------------------------------------------

def read_cpu_stat():
    """读取 /proc/stat 的 CPU 时间片，返回 {cpu名: (total, idle, 原始值列表)}。"""
    raw = slurp("/proc/stat", "") or ""
    out = {}
    for line in raw.splitlines():
        if not line.startswith("cpu"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        try:
            values = [float(x) for x in parts[1:]]
        except Exception:
            continue
        idle = values[3] + (values[4] if len(values) > 4 else 0.0)  # idle + iowait
        out[parts[0]] = (sum(values), idle, values)
    return out


def compute_cpu_usage(prev, cur):
    """由两次 /proc/stat 采样算出总体与单核使用率，以及 iowait 占比。"""
    result = {"overall": None, "per_core": [], "iowait": None}
    if not prev or not cur:
        return result
    if "cpu" in prev and "cpu" in cur:
        d_total = cur["cpu"][0] - prev["cpu"][0]
        d_idle = cur["cpu"][1] - prev["cpu"][1]
        if d_total > 0:
            result["overall"] = max(0.0, min(100.0, (d_total - d_idle) / d_total * 100.0))
        # iowait 单列
        try:
            d_iowait = cur["cpu"][2][4] - prev["cpu"][2][4]
            if d_total > 0:
                result["iowait"] = max(0.0, d_iowait / d_total * 100.0)
        except Exception:
            pass
    cores = sorted([k for k in cur if re.match(r"^cpu\d+$", k)], key=lambda s: int(s[3:]))
    for key in cores:
        if key not in prev:
            continue
        d_total = cur[key][0] - prev[key][0]
        d_idle = cur[key][1] - prev[key][1]
        if d_total <= 0:
            continue
        result["per_core"].append(max(0.0, min(100.0, (d_total - d_idle) / d_total * 100.0)))
    return result


# ---------------------------------------------------------------------------
# 采集器：内存 / 磁盘 / 网络
# ---------------------------------------------------------------------------

def collect_mem():
    """从 /proc/meminfo 采集内存与 swap。"""
    info = {}
    for line in (slurp("/proc/meminfo", "") or "").splitlines():
        parts = line.split(":")
        if len(parts) != 2:
            continue
        fields = parts[1].strip().split()
        if not fields:
            continue
        try:
            info[parts[0].strip()] = float(fields[0]) * 1024.0
        except Exception:
            pass
    total = info.get("MemTotal", 0.0)
    available = info.get("MemAvailable", info.get("MemFree", 0.0))
    used = max(0.0, total - available)
    swap_total = info.get("SwapTotal", 0.0)
    swap_free = info.get("SwapFree", 0.0)
    swap_used = max(0.0, swap_total - swap_free)
    return {
        "total": total,
        "available": available,
        "used": used,
        "used_pct": (used / total * 100.0) if total else 0.0,
        "cached": info.get("Cached", 0.0) + info.get("SReclaimable", 0.0),
        "buffers": info.get("Buffers", 0.0),
        "dirty": info.get("Dirty", 0.0),
        "swap_total": swap_total,
        "swap_used": swap_used,
        "swap_pct": (swap_used / swap_total * 100.0) if swap_total else 0.0,
    }


def collect_disk_usage():
    """用 df 采集真实块设备的挂载点使用率。"""
    raw = run_cmd(["df", "-P", "-B1"], timeout=12)
    if not raw:
        return []
    items = []
    for line in raw.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        device, mount = parts[0], parts[5]
        # 只关心真实块设备与根分区。必须排除两类"永远 100%"的假告警：
        #   - /snap/* 是 squashfs 只读挂载，df 恒定显示 100%，与磁盘写满无关；
        #   - /dev/loop* 是 snap 的环回设备，同理。
        if mount.startswith("/snap") or device.startswith("/dev/loop"):
            continue
        if not (device.startswith("/dev/") or mount == "/"):
            continue
        try:
            total = float(parts[1])
            used = float(parts[2])
            avail = float(parts[3])
            pct = float(parts[4].rstrip("%"))
        except Exception:
            continue
        if total <= 0:
            continue
        items.append({
            "device": device, "mount": mount,
            "total": total, "used": used, "avail": avail, "pct": pct,
        })
    items.sort(key=lambda x: -x["pct"])
    return items


def read_diskstats():
    """读取 /proc/diskstats，返回 {设备名: (累计读字节, 累计写字节)}。"""
    out = {}
    for line in (slurp("/proc/diskstats", "") or "").splitlines():
        parts = line.split()
        if len(parts) < 10:
            continue
        name = parts[2]
        if re.match(r"^(loop|ram|dm-|sr|fd|zram)", name):
            continue
        try:
            # 字段 5 = 已读扇区数，字段 9 = 已写扇区数，扇区按 512 字节计
            out[name] = (int(parts[5]) * 512, int(parts[9]) * 512)
        except Exception:
            pass
    return out


def read_netdev():
    """读取 /proc/net/dev，返回 {网卡名: (累计接收字节, 累计发送字节)}。"""
    out = {}
    lines = (slurp("/proc/net/dev", "") or "").splitlines()
    for line in lines[2:]:
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name = name.strip()
        if name == "lo":
            continue
        fields = rest.split()
        if len(fields) < 9:
            continue
        try:
            out[name] = (int(fields[0]), int(fields[8]))
        except Exception:
            pass
    return out


def collect_disk_health():
    """保留占位：磁盘 SMART 需要 root 且本机未安装 smartctl，暂不采集。"""
    return {}


# ---------------------------------------------------------------------------
# 采集器：GPU / 进程 / Docker
# ---------------------------------------------------------------------------

GPU_FIELDS = [
    "index", "name", "temperature.gpu", "utilization.gpu",
    "memory.used", "memory.total", "power.draw", "power.limit",
    "fan.speed", "clocks_throttle_reasons.active", "clocks.sm", "clocks.max.sm",
]

# nvidia-smi 的 clocks_throttle_reasons.active 是位掩码。
# 第三项标记该位是否代表"真的被限制性能"——GpuIdle 表示 GPU 空闲，属正常状态，
# 早期版本把它当成降频会持续误报。
GPU_THROTTLE_BITS = [
    (0x0000000000000001, "GpuIdle", False),
    (0x0000000000000002, "ApplicationsClocksSetting", False),
    (0x0000000000000004, "SwPowerCap", True),
    (0x0000000000000008, "HwSlowdown", True),
    (0x0000000000000010, "SyncBoost", False),
    (0x0000000000000020, "SwThermalSlowdown", True),
    (0x0000000000000040, "HwThermalSlowdown", True),
    (0x0000000000000080, "HwPowerBrakeSlowdown", True),
    (0x0000000000000100, "DisplayClockSetting", False),
]


def decode_gpu_throttle(text):
    """解析 GPU 降频位掩码，返回 (是否真的在限制性能, 可读原因)。

    0x1 (GpuIdle) 只表示 GPU 当前空闲，不是故障；只有 SwPowerCap /
    HwThermalSlowdown 这类位才意味着性能被压制。
    """
    raw = str(text or "").strip()
    try:
        mask = int(raw, 16) if raw.lower().startswith("0x") else int(raw)
    except Exception:
        return (False, raw or "N/A")
    active = [name for bit, name, _ in GPU_THROTTLE_BITS if mask & bit]
    harmful = [name for bit, name, bad in GPU_THROTTLE_BITS if (mask & bit) and bad]
    if not active:
        return (False, "无")
    return (bool(harmful), ", ".join(active))


def collect_gpu():
    """用 nvidia-smi 采集 GPU 指标；没有 NVIDIA GPU 时返回 None。"""
    raw = run_cmd(
        ["nvidia-smi", "--query-gpu=" + ",".join(GPU_FIELDS), "--format=csv,noheader,nounits"],
        timeout=10,
    )
    if not raw or not raw.strip():
        return None
    gpus = []
    for line in raw.strip().splitlines():
        values = [v.strip() for v in line.split(",")]
        if len(values) < len(GPU_FIELDS):
            continue

        def num(text):
            try:
                return float(text)
            except Exception:
                return None

        gpus.append({
            "index": values[0],
            "name": values[1],
            "temp": num(values[2]),
            "util": num(values[3]),
            "mem_used": num(values[4]),
            "mem_total": num(values[5]),
            "power": num(values[6]),
            "power_limit": num(values[7]),
            "fan": num(values[8]),
            "throttle": values[9],
            "clk_sm": num(values[10]),
            "clk_max": num(values[11]),
        })
    return gpus or None


def collect_procs(topn=5):
    """取 CPU 占用最高的若干进程。"""
    raw = run_cmd(["ps", "-eo", "pcpu,pmem,rss,args", "--sort=-pcpu", "--no-headers"], timeout=10)
    if not raw:
        return []
    items = []
    for line in raw.strip().splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        try:
            cpu = float(parts[0])
            mem = float(parts[1])
            rss = float(parts[2]) * 1024.0
        except Exception:
            continue
        items.append({"cpu": cpu, "mem": mem, "rss": rss, "cmd": parts[3].strip()})
        if len(items) >= topn:
            break
    return items


def collect_docker():
    """采集运行中的 Docker 容器列表；没有 docker 时返回 available=False。"""
    raw = run_cmd(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"], timeout=12)
    if raw is None:
        return {"available": False, "running": 0, "items": []}
    items = []
    for line in raw.strip().splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        items.append({
            "name": fields[0] if len(fields) > 0 else "?",
            "status": fields[1] if len(fields) > 1 else "",
            "image": fields[2] if len(fields) > 2 else "",
        })
    return {"available": True, "running": len(items), "items": items}


def collect_uptime():
    """读取系统启动时长（秒）。"""
    raw = slurp("/proc/uptime", "") or ""
    parts = raw.split()
    if not parts:
        return None
    try:
        return float(parts[0])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 采样：把一次完整采样组装成 dict
# ---------------------------------------------------------------------------

def take_sample(prev):
    """采集一次完整快照。

    prev 为上一次采样结果（首次传 None），用于计算速率与增量。
    """
    now = time.time()
    sample = {"ts": now, "host": socket.gethostname()}

    sample["uptime"] = collect_uptime()
    sample["temps"] = collect_temps()
    sample["cpu_stat"] = read_cpu_stat()
    sample["cpu_freq"] = read_cpu_freq()
    sample["powerclamp"] = detect_powerclamp()
    sample["throttle"] = read_throttle_counters()
    sample["throttle_time_ms"] = read_throttle_time()
    sample["rapl"] = read_rapl()
    sample["mem"] = collect_mem()
    sample["disks"] = collect_disk_usage()
    sample["diskstats"] = read_diskstats()
    sample["netdev"] = read_netdev()
    sample["gpu"] = collect_gpu()
    sample["procs"] = collect_procs(5)
    sample["docker"] = collect_docker()

    try:
        sample["load"] = list(os.getloadavg())
    except Exception:
        sample["load"] = [None, None, None]

    # ---- 由前后两次采样推导出的速率量 ----
    dt = (now - prev["ts"]) if prev else 0.0
    usage = compute_cpu_usage(prev.get("cpu_stat") if prev else None, sample["cpu_stat"])
    sample["cpu_usage"] = usage

    io = {}
    for name, (rd, wr) in sample["diskstats"].items():
        if prev and name in prev.get("diskstats", {}):
            prd, pwr = prev["diskstats"][name]
            io[name] = (rate_or_none(rd, prd, dt), rate_or_none(wr, pwr, dt))
    sample["disk_io"] = io

    net = {}
    for name, (rx, tx) in sample["netdev"].items():
        if prev and name in prev.get("netdev", {}):
            prx, ptx = prev["netdev"][name]
            net[name] = (rate_or_none(rx, prx, dt), rate_or_none(tx, ptx, dt))
    sample["net_io"] = net

    # RAPL 能耗计数器差分 -> 功耗（瓦）。计数器是 32 位，溢出时做一次回绕修正。
    power = {}
    for name, energy in sample["rapl"].items():
        if prev and name in prev.get("rapl", {}) and dt > 0:
            delta = energy - prev["rapl"][name]
            if delta < 0:
                delta += 2 ** 32
            power[name] = delta / 1e6 / dt
    sample["power"] = power

    # 降频计数器的增量：> 0 说明这段时间内真的发生了热降频
    if prev and prev.get("throttle") and sample["throttle"]:
        sample["throttle_delta"] = (
            sample["throttle"][0] - prev["throttle"][0],
            sample["throttle"][1] - prev["throttle"][1],
        )
        if prev.get("throttle_time_ms") is not None and sample["throttle_time_ms"] is not None:
            sample["throttle_time_delta_ms"] = sample["throttle_time_ms"] - prev["throttle_time_ms"]
        else:
            sample["throttle_time_delta_ms"] = None
    else:
        sample["throttle_delta"] = None
        sample["throttle_time_delta_ms"] = None

    return sample


# ---------------------------------------------------------------------------
# 判定：把指标映射为 正常 / 注意 / 严重
# ---------------------------------------------------------------------------

def add_check(checks, label, value_text, level, detail=""):
    checks.append({"label": label, "value": value_text, "level": level, "detail": detail})


def judge_high(value, warn, crit):
    """数值越大越糟的通用判定。"""
    if value is None:
        return LEVEL_NA
    if value >= crit:
        return LEVEL_CRIT
    if value >= warn:
        return LEVEL_WARN
    return LEVEL_OK


def evaluate(sample):
    """对一次采样做健康判定，返回 (checks, 总体等级)。"""
    checks = []
    temps = sample["temps"]
    mem = sample["mem"]
    load = sample["load"]

    # ---------------- CPU 温度 ----------------
    pkg = temps["cpu_package"]
    crit_line = temps["cpu_crit"] if temps["cpu_crit"] else TH["cpu_temp"][1]
    level = judge_high(pkg, TH["cpu_temp"][0], min(crit_line, TH["cpu_temp"][1]))
    if temps["cpu_crit_alarm"]:
        level = LEVEL_CRIT
    detail = ""
    if level == LEVEL_CRIT:
        detail = "已顶到临界温度 %s，必须立即处理" % (
            ("%.0f°C" % temps["cpu_crit"]) if temps["cpu_crit"] else "阈值"
        )
    elif level == LEVEL_WARN:
        detail = "持续偏高，检查散热"
    add_check(checks, "CPU 封装温度", ("%.1f °C" % pkg) if pkg is not None else "N/A", level, detail)

    core_max = temps["cpu_core_max"]
    if core_max is not None:
        add_check(checks, "CPU 最高单核温度", "%.1f °C" % core_max,
                  judge_high(core_max, TH["cpu_temp"][0], min(crit_line, TH["cpu_temp"][1])))

    # ---------------- CPU 实际功耗：区分「负载过重」与「散热失效」 ----------------
    pkg_power = sample.get("power", {}).get("package-0")
    if pkg_power is not None:
        add_check(checks, "CPU 封装功耗", "%.1f W" % pkg_power, LEVEL_OK)
        if pkg is not None and pkg >= 95.0 and pkg_power < 60.0:
            add_check(
                checks, "散热诊断",
                "功耗仅 %.0f W 却达 %.0f °C" % (pkg_power, pkg), LEVEL_CRIT,
                "低功耗下仍顶到临界温度，热量散不出去 → 优先排查风扇是否停转、"
                "水冷泵是否工作、硅脂是否干涸、散热器是否松动",
            )
    else:
        add_check(checks, "CPU 封装功耗", "需 root 读取 RAPL", LEVEL_NA)

    # ---------------- 降频证据 ----------------
    pc = sample["powerclamp"]
    if pc["threads"] > 0:
        add_check(checks, "内核强制降温 (powerclamp)",
                  "%d 个 kidle_inj 线程" % pc["threads"], LEVEL_CRIT,
                  "内核正在强行注入空闲周期来压温度，CPU 已被限速")
    else:
        add_check(checks, "内核强制降温 (powerclamp)", "未启用", LEVEL_OK)

    delta = sample.get("throttle_delta")
    ttime_delta = sample.get("throttle_time_delta_ms")
    if delta is None:
        add_check(checks, "热降频增量", "首次采样，无对比", LEVEL_NA)
    else:
        core_d, pkg_d = delta
        if pkg_d > 0 or core_d > 0:
            add_check(checks, "热降频增量", "package +%d / core +%d" % (pkg_d, core_d),
                      LEVEL_CRIT, "本次采样间隔内确实发生了热降频")
        else:
            add_check(checks, "热降频增量", "无新增", LEVEL_OK)

    if sample.get("throttle_time_ms") is not None:
        total_ms = sample["throttle_time_ms"]
        up = sample["uptime"] or 0.0
        ratio = (total_ms / 1000.0 / up * 100.0) if up > 0 else 0.0
        lvl = judge_high(ratio, 5.0, 20.0)
        add_check(checks, "累计降频时间占比", "%.1f%% (累计 %.1fs / 开机 %.0fs)" % (
            ratio, total_ms / 1000.0, up), lvl,
            "占比越高说明散热余量越小" if lvl != LEVEL_OK else "")

    # CPU 实际频率
    cur_freq, max_freq = sample["cpu_freq"]
    freq_level = LEVEL_NA
    freq_text = "N/A"
    if cur_freq and max_freq:
        avg = sum(cur_freq) / len(cur_freq)
        ratio = avg / max_freq
        freq_text = "%.0f / %.0f MHz (%.0f%%)" % (avg, max_freq, ratio * 100.0)
        # 只有在该跑的时候（有负载）才把低频当成问题
        load1 = load[0] if load and load[0] is not None else 0.0
        busy = load1 > (len(cur_freq) * 0.3)
        if ratio < TH["freq_ratio"][1]:
            freq_level = LEVEL_CRIT if busy else LEVEL_WARN
        elif ratio < TH["freq_ratio"][0]:
            freq_level = LEVEL_WARN
        else:
            freq_level = LEVEL_OK
    add_check(checks, "CPU 实际频率", freq_text, freq_level,
              "明显低于标称频率说明正在被限速" if freq_level in (LEVEL_WARN, LEVEL_CRIT) else "")

    # ---------------- 负载 ----------------
    if load and load[0] is not None:
        cores = len(sample["cpu_usage"]["per_core"]) or os.cpu_count() or 1
        per_core = load[0] / float(cores)
        add_check(checks, "负载 (1/5/15 分钟)",
                  "%.2f / %.2f / %.2f  →  %.2f/核" % (load[0], load[1], load[2], per_core),
                  judge_high(per_core, TH["load_per_core"][0], TH["load_per_core"][1]),
                  "负载高于核数意味着任务在排队" if per_core >= 1.0 else "")

    usage = sample["cpu_usage"]["overall"]
    if usage is not None:
        add_check(checks, "CPU 总体使用率", "%.1f%%" % usage,
                  judge_high(usage, 85.0, 95.0))

    iowait = sample["cpu_usage"]["iowait"]
    if iowait is not None:
        add_check(checks, "IO 等待 (iowait)", "%.1f%%" % iowait,
                  judge_high(iowait, TH["iowait_pct"][0], TH["iowait_pct"][1]))

    # ---------------- 内存 ----------------
    add_check(checks, "内存使用率",
              "%.1f%%  (%s / %s)" % (mem["used_pct"], human_bytes(mem["used"]), human_bytes(mem["total"])),
              judge_high(mem["used_pct"], TH["mem_pct"][0], TH["mem_pct"][1]))
    if mem["swap_total"] > 0:
        add_check(checks, "Swap 使用率",
                  "%.1f%%  (%s / %s)" % (mem["swap_pct"], human_bytes(mem["swap_used"]), human_bytes(mem["swap_total"])),
                  judge_high(mem["swap_pct"], TH["swap_pct"][0], TH["swap_pct"][1]),
                  "大量使用 swap 会显著拖慢速度" if mem["swap_pct"] >= TH["swap_pct"][0] else "")
    else:
        add_check(checks, "Swap", "未配置", LEVEL_OK)

    # ---------------- 磁盘 ----------------
    for disk in sample["disks"][:4]:
        add_check(checks, "磁盘 %s" % disk["mount"],
                  "%.1f%%  (剩余 %s / %s)" % (disk["pct"], human_bytes(disk["avail"]), human_bytes(disk["total"])),
                  judge_high(disk["pct"], TH["disk_pct"][0], TH["disk_pct"][1]))

    # ---------------- NVMe 温度 ----------------
    for name, val in sorted(sample["temps"]["nvme"].items()):
        add_check(checks, "NVMe %s" % name, "%.1f °C" % val,
                  judge_high(val, TH["nvme_temp"][0], TH["nvme_temp"][1]))

    # ---------------- GPU ----------------
    if sample["gpu"]:
        for gpu in sample["gpu"]:
            add_check(checks, "GPU%d 温度" % int(float(gpu["index"])),
                      ("%.0f °C" % gpu["temp"]) if gpu["temp"] is not None else "N/A",
                      judge_high(gpu["temp"], TH["gpu_temp"][0], TH["gpu_temp"][1]))
            if gpu["mem_total"]:
                pct = gpu["mem_used"] / gpu["mem_total"] * 100.0
                add_check(checks, "GPU%d 显存" % int(float(gpu["index"])),
                          "%.1f%%  (%.0f / %.0f MiB)" % (pct, gpu["mem_used"], gpu["mem_total"]),
                          judge_high(pct, TH["gpu_mem_pct"][0], TH["gpu_mem_pct"][1]))
            harmful, reason = decode_gpu_throttle(gpu["throttle"])
            add_check(checks, "GPU%d 降频原因" % int(float(gpu["index"])), reason,
                      LEVEL_WARN if harmful else LEVEL_OK,
                      "GPU 性能正在被压制" if harmful else "")
    else:
        add_check(checks, "GPU", "未检测到 NVIDIA GPU", LEVEL_NA)

    # ---------------- Docker ----------------
    if sample["docker"]["available"]:
        add_check(checks, "Docker 运行中容器", "%d 个" % sample["docker"]["running"], LEVEL_OK)
    else:
        add_check(checks, "Docker", "不可用", LEVEL_NA)

    # 总体等级 = 最差的一项
    overall = LEVEL_OK
    for item in checks:
        if LEVEL_RANK[item["level"]] > LEVEL_RANK[overall]:
            overall = item["level"]
    return checks, overall


# ---------------------------------------------------------------------------
# 渲染
# ---------------------------------------------------------------------------

def spark(values, width=40):
    """把一串数值画成块状趋势条。"""
    vals = [v for v in values if v is not None]
    if len(vals) < 2:
        return ""
    vals = vals[-width:]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return SPARK_CHARS[3] * len(vals)
    out = []
    for v in vals:
        idx = int((v - lo) / (hi - lo) * (len(SPARK_CHARS) - 1))
        out.append(SPARK_CHARS[max(0, min(len(SPARK_CHARS) - 1, idx))])
    return "".join(out)


def fmt_delta(cur, prev, dt):
    """格式化速率增量。"""
    if cur is None or prev is None or not dt:
        return None
    return (cur - prev) / float(dt)


def render(sample, checks, overall, history, paint, width):
    """把一次采样渲染成多行文本。"""
    inner = width - 2
    lines = []

    def rule(char="─"):
        return paint.dim(char * inner)

    def section(title):
        lines.append("")
        lines.append(paint.head("▎" + title))
        lines.append(rule())

    def row(label, text, level=None, note=""):
        label_w = 22
        text_w = 34
        body = "  " + pad(label, label_w) + pad(text, text_w)
        if level is not None:
            body += paint.by_level(level, "[%s]" % LEVEL_TEXT[level])
        else:
            body += " " * 6
        if note:
            body += "  " + paint.dim(note)
        lines.append(body)

    # ---- 顶部横幅 ----
    stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sample["ts"]))
    up = human_duration(sample["uptime"]) if sample["uptime"] else "N/A"
    title = "服务器健康监控"
    lines.append("")
    lines.append(paint.bold(pad(title, 30) + pad("%s  %s" % (sample["host"], stamp), inner - 30, "right")))
    lines.append(rule("═"))

    counts = {LEVEL_OK: 0, LEVEL_WARN: 0, LEVEL_CRIT: 0, LEVEL_NA: 0}
    for item in checks:
        counts[item["level"]] += 1
    badge = paint.by_level(overall, "【%s】" % LEVEL_TEXT[overall])
    summary = "开机 %s  |  正常 %d 项 · 注意 %d 项 · 严重 %d 项" % (
        up, counts[LEVEL_OK], counts[LEVEL_WARN], counts[LEVEL_CRIT])
    lines.append("  总体判定 " + badge + "   " + paint.dim(summary))
    lines.append(rule("═"))

    # ---- 异常清单优先展示 ----
    bad = [c for c in checks if c["level"] in (LEVEL_WARN, LEVEL_CRIT)]
    if bad:
        section("需要关注的问题")
        for item in bad:
            mark = paint.crit("●") if item["level"] == LEVEL_CRIT else paint.warn("●")
            lines.append("  %s %s  %s" % (
                mark,
                paint.bold(pad(item["label"], 22)),
                paint.by_level(item["level"], item["value"]),
            ))
            if item["detail"]:
                lines.append("      " + paint.dim(item["detail"]))

    # ---- 温度总览 ----
    section("温度")
    temps = sample["temps"]
    row("CPU 封装", ("%.1f °C" % temps["cpu_package"]) if temps["cpu_package"] is not None else "N/A")
    if temps["cpu_core_max"] is not None:
        row("CPU 最高单核", "%.1f °C" % temps["cpu_core_max"])
    if temps["cpu_cores"]:
        hot = sorted(temps["cpu_cores"], key=lambda x: -x[1])[:4]
        row("最热的核心", "  ".join("%s=%.0f" % (n.replace("Core ", "C"), v) for n, v in hot))
    for name, val in sorted(temps["nvme"].items()):
        row("NVMe " + name, "%.1f °C" % val)
    if sample["gpu"]:
        for gpu in sample["gpu"]:
            row("GPU%d %s" % (int(float(gpu["index"])), clip(gpu["name"], 18)),
                ("%.0f °C" % gpu["temp"]) if gpu["temp"] is not None else "N/A",
                note="功耗 %s W / %s W  风扇 %s%%" % (
                    ("%.0f" % gpu["power"]) if gpu["power"] is not None else "?",
                    ("%.0f" % gpu["power_limit"]) if gpu["power_limit"] is not None else "?",
                    ("%.0f" % gpu["fan"]) if gpu["fan"] is not None else "?"))
    row("数据来源", temps["source"])

    # ---- 降频 ----
    section("降频与频率")
    pc = sample["powerclamp"]
    row("内核强制降温", "%d 个 kidle_inj 线程" % pc["threads"] if pc["threads"] else "未启用",
        LEVEL_CRIT if pc["threads"] else LEVEL_OK)
    if sample["throttle"]:
        row("累计降频次数", "package %d / core %d" % (sample["throttle"][1], sample["throttle"][0]))
    delta = sample.get("throttle_delta")
    if delta is not None:
        row("本周期新增降频", "package +%d / core +%d" % (delta[1], delta[0]),
            LEVEL_CRIT if (delta[0] > 0 or delta[1] > 0) else LEVEL_OK)
    if sample.get("throttle_time_ms") is not None:
        row("累计降频耗时", "%.1f 秒" % (sample["throttle_time_ms"] / 1000.0))
    pkg_power = sample.get("power", {}).get("package-0")
    if pkg_power is not None:
        hot_note = ""
        if pkg_power < 60.0 and (sample["temps"]["cpu_package"] or 0) >= 90.0:
            hot_note = "功耗不高却顶到临界温度 = 散热问题，而不是任务太重"
        row("CPU 封装功耗", "%.1f W" % pkg_power, note=hot_note)
    cur_freq, max_freq = sample["cpu_freq"]
    if cur_freq and max_freq:
        avg = sum(cur_freq) / len(cur_freq)
        row("CPU 实际频率", "%.0f / %.0f MHz  (%.0f%%)" % (avg, max_freq, avg / max_freq * 100.0))
        row("单核频率范围", "%.0f ~ %.0f MHz" % (min(cur_freq), max(cur_freq)))

    # ---- 负载与 CPU ----
    section("负载与 CPU")
    load = sample["load"]
    if load and load[0] is not None:
        cores = os.cpu_count() or 1
        row("Load 1/5/15", "%.2f / %.2f / %.2f" % (load[0], load[1], load[2]),
            note="%.2f / 核（%d 核）" % (load[0] / float(cores), cores))
    usage = sample["cpu_usage"]
    if usage["overall"] is not None:
        row("总体使用率", "%.1f%%" % usage["overall"])
    if usage["iowait"] is not None:
        row("IO 等待", "%.1f%%" % usage["iowait"])
    if usage["per_core"]:
        hot_cores = sorted(usage["per_core"], reverse=True)[:6]
        row("最忙的核心", " ".join("%.0f%%" % c for c in hot_cores))

    # ---- 内存 ----
    section("内存")
    mem = sample["mem"]
    row("物理内存", "%s / %s  (%.1f%%)" % (
        human_bytes(mem["used"]), human_bytes(mem["total"]), mem["used_pct"]))
    row("可用", human_bytes(mem["available"]))
    row("缓存/缓冲", "%s / %s" % (human_bytes(mem["cached"]), human_bytes(mem["buffers"])))
    if mem["swap_total"] > 0:
        row("Swap", "%s / %s  (%.1f%%)" % (
            human_bytes(mem["swap_used"]), human_bytes(mem["swap_total"]), mem["swap_pct"]))

    # ---- 磁盘 ----
    section("磁盘")
    for disk in sample["disks"][:5]:
        row(disk["mount"], "%.1f%% 已用   剩余 %s" % (disk["pct"], human_bytes(disk["avail"])))
    for name, (rd, wr) in sorted(sample["disk_io"].items())[:4]:
        row("IO " + name, "读 %s/s  写 %s/s" % (
            human_bytes(rd) if rd is not None else "N/A",
            human_bytes(wr) if wr is not None else "N/A"))

    # ---- 网络 ----
    if sample["net_io"]:
        section("网络")
        for name, (rx, tx) in sorted(sample["net_io"].items())[:4]:
            row(name, "下行 %s/s  上行 %s/s" % (
                human_bytes(rx) if rx is not None else "N/A",
                human_bytes(tx) if tx is not None else "N/A"))

    # ---- GPU ----
    if sample["gpu"]:
        section("GPU")
        for gpu in sample["gpu"]:
            idx = int(float(gpu["index"]))
            row("GPU%d 利用率" % idx, ("%.0f%%" % gpu["util"]) if gpu["util"] is not None else "N/A")
            if gpu["mem_total"]:
                row("GPU%d 显存" % idx, "%.0f / %.0f MiB  (%.1f%%)" % (
                    gpu["mem_used"], gpu["mem_total"], gpu["mem_used"] / gpu["mem_total"] * 100.0))
            if gpu["clk_sm"] is not None and gpu["clk_max"]:
                row("GPU%d 核心频率" % idx, "%.0f / %.0f MHz" % (gpu["clk_sm"], gpu["clk_max"]))
            row("GPU%d 降频原因" % idx, decode_gpu_throttle(gpu["throttle"])[1])

    # ---- 进程 ----
    if sample["procs"]:
        section("CPU 占用最高的进程")
        for proc in sample["procs"]:
            row("%.1f%% CPU" % proc["cpu"], clip(proc["cmd"], 46), note="内存 %s" % human_bytes(proc["rss"]))

    # ---- Docker ----
    if sample["docker"]["available"]:
        section("Docker")
        row("运行中容器", "%d 个" % sample["docker"]["running"])
        for item in sample["docker"]["items"][:6]:
            row(clip(item["name"], 20), clip(item["status"], 30), note=clip(item["image"], 28))

    # ---- 趋势 ----
    if len(history) >= 3:
        section("趋势（最近 %d 次采样）" % len(history))
        cpu_hist = [h.get("cpu_temp") for h in history]
        load_hist = [h.get("load") for h in history]
        gpu_hist = [h.get("gpu_temp") for h in history]
        mem_hist = [h.get("mem_pct") for h in history]
        if any(v is not None for v in cpu_hist):
            lines.append("  " + pad("CPU 温度", 12) + paint.crit(spark(cpu_hist)))
        if any(v is not None for v in load_hist):
            lines.append("  " + pad("Load", 12) + paint.warn(spark(load_hist)))
        if any(v is not None for v in gpu_hist):
            lines.append("  " + pad("GPU 温度", 12) + paint.head(spark(gpu_hist)))
        if any(v is not None for v in mem_hist):
            lines.append("  " + pad("内存 %", 12) + paint.head(spark(mem_hist)))

    lines.append("")
    if paint.on:
        lines.append(paint.dim("  Ctrl+C 退出   ·   刷新间隔 %.1f 秒" % sample.get("interval", 2.0)))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def history_point(sample):
    """从采样里抽出用于画趋势的几个标量。"""
    gpu_temp = None
    if sample["gpu"] and sample["gpu"][0]["temp"] is not None:
        gpu_temp = sample["gpu"][0]["temp"]
    return {
        "cpu_temp": sample["temps"]["cpu_package"],
        "load": sample["load"][0] if sample["load"] else None,
        "gpu_temp": gpu_temp,
        "mem_pct": sample["mem"]["used_pct"],
    }


def to_jsonable(sample, checks, overall):
    """把采样整理成可 JSON 序列化的结构。"""
    return {
        "ts": sample["ts"],
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sample["ts"])),
        "host": sample["host"],
        "uptime_seconds": sample["uptime"],
        "overall": overall,
        "checks": checks,
        "cpu": {
            "package_temp_c": sample["temps"]["cpu_package"],
            "core_max_temp_c": sample["temps"]["cpu_core_max"],
            "cores": [{"name": n, "temp_c": t} for n, t in sample["temps"]["cpu_cores"]],
            "freq_mhz": sample["cpu_freq"][0],
            "freq_max_mhz": sample["cpu_freq"][1],
            "usage_pct": sample["cpu_usage"]["overall"],
            "per_core_usage_pct": sample["cpu_usage"]["per_core"],
            "iowait_pct": sample["cpu_usage"]["iowait"],
            "load": sample["load"],
            "powerclamp_threads": sample["powerclamp"]["threads"],
            "throttle_core_total": sample["throttle"][0] if sample["throttle"] else None,
            "throttle_package": sample["throttle"][1] if sample["throttle"] else None,
            "throttle_delta": sample["throttle_delta"],
            "throttle_time_ms": sample["throttle_time_ms"],
            "power_w": sample.get("power") or None,
        },
        "memory": sample["mem"],
        "disks": sample["disks"],
        "nvme_temps": sample["temps"]["nvme"],
        "gpu": sample["gpu"],
        "docker": {"available": sample["docker"]["available"], "running": sample["docker"]["running"]},
        "top_procs": sample["procs"],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Linux 服务器实时健康监控（温度 / 降频 / 负载 / 内存 / 磁盘 / GPU）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-i", "--interval", type=float, default=2.0, help="刷新间隔秒数，默认 2")
    parser.add_argument("--once", action="store_true", help="只打印一次快照后退出")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出（隐含 --once）")
    parser.add_argument("--log", metavar="FILE", help="把每次采样追加写入 JSONL 文件")
    parser.add_argument("-d", "--duration", type=float, default=0.0, help="运行多少秒后自动退出，0 表示一直运行")
    parser.add_argument("--no-color", action="store_true", help="关闭颜色输出")
    parser.add_argument("--width", type=int, default=0, help="面板宽度，默认自动适配终端")
    parser.add_argument("--warmup", type=float, default=1.0,
                        help="单次快照模式下的基线采样等待秒数，默认 1（差分指标需要两次采样）")
    args = parser.parse_args()

    if args.json:
        args.once = True

    if args.interval < 0.2:
        args.interval = 0.2

    is_tty = sys.stdout.isatty()
    use_color = is_tty and not args.no_color
    paint = Paint(use_color)

    if args.width and args.width > 40:
        width = args.width
    else:
        try:
            width = shutil.get_terminal_size((100, 40)).columns
        except Exception:
            width = 100
    width = max(78, min(width, 120))

    prev = None
    history = deque(maxlen=60)
    started = time.time()

    # 单次快照模式：先采一次当基线，稍等再采第二次。否则使用率、IO 速率、
    # 降频增量、功耗这些"差分指标"全是 N/A，看不出真实状态。
    if args.once:
        try:
            prev = take_sample(None)
            time.sleep(min(max(args.warmup, 0.5), 5.0))
        except Exception:
            prev = None
    log_fh = None
    if args.log:
        try:
            log_fh = open(args.log, "a")
        except Exception as exc:
            sys.stderr.write("无法打开日志文件: %s\n" % type(exc).__name__)
            log_fh = None

    if use_color:
        sys.stdout.write("\033[?25l")  # 隐藏光标，避免重绘时闪烁
    try:
        while True:
            sample = take_sample(prev)
            sample["interval"] = args.interval
            checks, overall = evaluate(sample)
            history.append(history_point(sample))

            if args.json:
                payload = to_jsonable(sample, checks, overall)
                sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            else:
                frame = render(sample, checks, overall, list(history), paint, width)
                if is_tty and not args.once:
                    sys.stdout.write("\033[H\033[J" + frame + "\n")
                else:
                    if not args.once:
                        sys.stdout.write("\n" + "=" * width + "\n")
                    sys.stdout.write(frame + "\n")
                sys.stdout.flush()

            if log_fh:
                log_fh.write(json.dumps(to_jsonable(sample, checks, overall), ensure_ascii=False) + "\n")
                log_fh.flush()

            prev = sample

            if args.once:
                break
            if args.duration and (time.time() - started) >= args.duration:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        if use_color:
            sys.stdout.write("\033[?25h\033[0m\n")
            sys.stdout.flush()
        if log_fh:
            log_fh.close()


if __name__ == "__main__":
    main()

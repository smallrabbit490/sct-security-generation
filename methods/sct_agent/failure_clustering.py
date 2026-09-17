"""失败反馈脱敏与聚类。

该模块的输出可进入候选经验生成，但绝不包含任务 ID、测试值、答案常量或
原始长日志。聚类键只使用语言、CWE、错误类别和规范化根因消息。
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

try:
    from .schemas import FailureCluster
except ImportError:  # 直接脚本执行时使用当前目录导入。
    from schemas import FailureCluster


_QUOTED = re.compile(r"(['\"]).*?\1")
_PATH = re.compile(r"(?:[A-Za-z]:)?[/\\][^\s:]+")
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_ASSIGNMENT = re.compile(r"(=|:)\s*[^,;\s]+")


def normalize_failure_message(message: str) -> str:
    """将日志中的字符串、路径、数字和赋值内容替换为占位符。"""
    value = str(message or "").lower()
    value = _QUOTED.sub("<quoted>", value)
    value = _PATH.sub("<path>", value)
    value = _ASSIGNMENT.sub(r"\1<value>", value)
    value = _NUMBER.sub("<number>", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:240]


def _safe_item(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """仅从失败记录读取允许进入聚类键的抽象字段。"""
    language = str(item.get("language", "unknown"))
    cwe = str(item.get("cwe", item.get("CWE_ID", "unknown")))
    error_type = str(item.get("error_type", item.get("phase", "unknown")))
    message = item.get("normalized_message") or item.get("error") or item.get("stderr") or error_type
    return language, cwe, error_type, normalize_failure_message(str(message)), str(item.get("phase", "unknown"))


def cluster_failures(items: list[dict[str, Any]], min_support: int = 2) -> list[FailureCluster]:
    """按抽象根因聚类，并过滤低于最小支持数的偶然失败。

    ``min_support=1`` 适合小规模烟测；正式实验建议使用至少 2 条相似失败。
    """
    buckets: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for item in items:
        language, cwe, error_type, message, phase = _safe_item(item)
        buckets[(language, cwe, error_type, message)].append(phase)
    clusters: list[FailureCluster] = []
    for (language, cwe, error_type, message), phases in sorted(buckets.items()):
        if len(phases) < min_support:
            continue
        digest = hashlib.sha1("|".join((language, cwe, error_type, message)).encode()).hexdigest()[:12]
        clusters.append(FailureCluster(digest, language, cwe, error_type, message, len(phases), sorted(set(phases))))
    return clusters

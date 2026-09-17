"""按照 DOCX 图一抽取漏洞代码与补丁代码之间的可复用差异。"""

from __future__ import annotations

import ast
import difflib
import re
from typing import Any

try:
    from .schemas import DifferenceAnalysis
except ImportError:  # 直接脚本执行时使用当前目录导入。
    from schemas import DifferenceAnalysis


SENSITIVE_CALLS = {
    "open",
    "eval",
    "exec",
    "compile",
    "system",
    "popen",
    "run",
    "call",
    "check_output",
    "socket",
    "urlopen",
    "requests.get",
}

SECURITY_API_NAMES = {
    "resolve",
    "relative_to",
    "realpath",
    "normpath",
    "canonical",
    "weakly_canonical",
    "filepath.Rel",
    "escapeshellarg",
    "parameterized",
}


def _parse_names(code: str) -> tuple[set[str], set[str], list[str]]:
    """从代码中安全地提取变量名、调用名和解析错误。"""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        # 差异分析不能因为一侧代码片段不完整而中断；错误会进入证据。
        return set(re.findall(r"\b[A-Za-z_]\w*\b", code)), set(), [str(exc)]
    names: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return names, calls, []


def _task_inputs(task_description: dict[str, Any]) -> set[str]:
    """从任务契约提取参数名，而不把测试值带入经验。"""
    text = " ".join(str(task_description.get(key, "")) for key in ("arguments", "input", "description"))
    return set(re.findall(r"\b[A-Za-z_]\w*\b", text))


def _cwe_postcondition(cwe: str, sensitive: set[str]) -> str:
    """给出与 CWE 相关的抽象安全后置条件。"""
    if str(cwe) in {"22", "23", "36"}:
        return "最终解析路径必须位于可信根目录内，且不能通过符号链接或 .. 逃逸"
    if str(cwe) in {"78", "77"}:
        return "外部输入不得直接形成命令语法，命令与参数必须结构化传递"
    if str(cwe) in {"89", "564"}:
        return "外部输入必须作为参数绑定，不能拼接为查询语法"
    if sensitive:
        return "敏感操作执行前必须验证输入满足任务声明的安全约束"
    return "敏感操作只能接收经过显式约束检查的输入"


def _dangerous_patterns(cwe: str, before: str) -> list[str]:
    """识别图一要求的“看似合理但不足够”的修复模式。"""
    patterns: list[str] = []
    lowered = before.lower()
    if str(cwe) in {"22", "23", "36"}:
        patterns.append("只用字符串前缀判断目录包含关系，未进行规范化路径和组件级检查")
    if str(cwe) in {"78", "77"} or any(token in lowered for token in ("system(", "popen(", "shell=true")):
        patterns.append("仅转义单个字符或继续把外部输入拼接进 shell 字符串")
    if str(cwe) in {"89", "564"}:
        patterns.append("仅过滤引号或关键字而不使用参数化查询")
    if not patterns:
        patterns.append("只检查表面格式，未验证敏感操作执行时的安全后置条件")
    return patterns


def analyze_difference(
    vulnerable_code: str,
    patched_code: str,
    task_description: dict[str, Any] | None = None,
    cwe: str | int = "unknown",
    functional_test: str | None = None,
    security_test: str | None = None,
) -> DifferenceAnalysis:
    """生成图一六类差异分析。

    输入是漏洞/补丁片段和任务契约；输出只含抽象安全知识。测试文本只用于
    标记证据是否存在，不会写入结果，避免把测试常量泄露到经验卡。
    """
    task_description = task_description or {}
    before_names, before_calls, before_errors = _parse_names(vulnerable_code)
    after_names, after_calls, after_errors = _parse_names(patched_code)
    contract_inputs = _task_inputs(task_description)
    untrusted = sorted((before_names | contract_inputs) & (before_names - after_names | contract_inputs))
    sensitive = sorted(call for call in before_calls | after_calls if call in SENSITIVE_CALLS)
    if not sensitive and any(token in vulnerable_code.lower() for token in ("file", "path", "url", "query")):
        sensitive = ["sensitive_operation inferred from task semantics"]
    trigger = []
    if untrusted and sensitive:
        trigger.append("不可信输入沿数据流到达敏感操作且未满足安全约束")
    elif untrusted:
        trigger.append("外部输入在补丁前缺少显式安全约束")
    else:
        trigger.append("任务契约声明的输入必须在敏感操作前经过约束检查")
    diff = list(difflib.unified_diff(vulnerable_code.splitlines(), patched_code.splitlines(), lineterm=""))
    changes = [line for line in diff if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    if not changes:
        changes = ["未检测到文本差异；需要人工检查语义或测试行为差异"]
    security_apis = sorted(name for name in after_names | after_calls if name in SECURITY_API_NAMES)
    if not security_apis:
        security_apis = ["显式输入约束检查（具体 API 由目标语言适配器确定）"]
    evidence = {
        "functional_test": "available" if functional_test else "unmeasured",
        "security_test": "available" if security_test else "unmeasured",
        "parse_errors": before_errors + after_errors,
    }
    return DifferenceAnalysis(
        cwe=str(cwe),
        untrusted_inputs=untrusted or ["任务契约中的外部输入"],
        sensitive_operations=sensitive or ["任务声明的敏感操作"],
        trigger_conditions=trigger,
        patch_changes=changes,
        security_apis=security_apis,
        postconditions=[_cwe_postcondition(str(cwe), set(sensitive))],
        dangerous_patterns=_dangerous_patterns(str(cwe), vulnerable_code),
        evidence=evidence,
    )

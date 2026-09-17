"""从 P_seed 的漏洞—补丁差异提取初始安全假设。

所属阶段：来源池（source_pool）初始安全知识形成，对应文档 3.1/3.2/3.3 节。
输入：一条 PLT 来源任务（含 CWE_ID、task_description、ground_truth 的
     漏洞代码与补丁代码）和一个 LLM 请求器。
输出：结构化安全假设（seed 经验卡）——按文档 3.3 的 8 字段表示：
     trigger_context / security_invariant / recommended_action /
     unsafe_alternative / language_adaptation / non_applicable_boundary /
     evidence / status。
验证证据：seed 的 evidence 由 run_lifecycle_replay 在提取后用
     validate_trajectory 回填（LLM 提取本身不构成验证证据）。
失败类型：empty_model_content（空输出）、invalid_hypothesis_json（解析失败）、
     incomplete_hypothesis（缺必需字段）。
允许修改长期经验库：否——本模块只产出 seed 假设，是否进入长期记忆由
     ExperienceMemory 与独立审查决定。
"""

from __future__ import annotations

import json
import re
from typing import Callable

# 文档 3.3 经验卡必须字段（除 evidence/status 由管线回填外）。
_REQUIRED_FIELDS = ("principle", "applicability")
# 从 LLM 输出解析的可选字段，缺失时保留空串，不阻断 seed 形成。
_OPTIONAL_FIELDS = ("dangerous_pattern", "recommended_action", "unsafe_alternative",
                    "language_adaptation", "non_applicable_boundary")


def build_prompt(row: dict) -> str:
    """构造不要求模型复制补丁代码的差异分析提示。

    提示要求模型按文档 3.3 的经验卡结构返回 JSON：原则（security_invariant）、
    适用条件（trigger_context/applicability）、推荐动作（recommended_action）、
    危险替代（unsafe_alternative）、多语言适配（language_adaptation）、
    不适用边界（non_applicable_boundary）。只提取可跨任务复用的安全语义，
    不复制漏洞/补丁代码、测试输入或答案常量。
    """
    task = row.get("task_description") or {}
    truth = row.get("ground_truth") or {}
    return (
        "请只返回 JSON，字段为：principle（安全不变量）、applicability（适用条件）、"
        "dangerous_pattern（危险模式）、recommended_action（推荐动作）、"
        "unsafe_alternative（不安全替代做法）、language_adaptation（python/go/cpp "
        "三种语言如何实现同一原则，用 JSON 对象）、non_applicable_boundary（不适用边界）。"
        "从漏洞代码和补丁代码提取可跨任务复用的安全不变量，不要复制代码、测试输入或答案。\n"
        f"CWE: {row.get('CWE_ID')}\n任务: {task.get('description', task.get('function_name', ''))}\n"
        f"漏洞差异: {truth.get('vulnerable_code', '')}\n补丁差异: {truth.get('patched_code', '')}"
    )


def extract_initial_hypothesis(row: dict, requester: Callable[[str], dict]) -> dict:
    """调用 LLM 提取 seed 假设；输出只保留安全语义，不保留源代码。

    输出经验卡包含文档 3.3 的核心字段（principle/applicability 为必填，
    dangerous_pattern/recommended_action/unsafe_alternative/language_adaptation/
    non_applicable_boundary 为可选），status 固定为 seed；evidence 由后续
    轨迹验证回填，此处不伪造验证结果。
    """
    content = ((requester(build_prompt(row)).get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    if not content.strip():
        raise ValueError("empty_model_content")
    try:
        candidate = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", candidate, re.S | re.I)
        value = json.loads(fenced.group(1) if fenced else candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_hypothesis_json") from exc
    if not isinstance(value, dict) or not all(isinstance(value.get(k), str) and value[k].strip() for k in _REQUIRED_FIELDS):
        raise ValueError("incomplete_hypothesis")
    card = {
        "id": f"seed-{row.get('index')}",
        "cwe": str(row.get("CWE_ID", "")),
        "task_id": int(row.get("index", -1)),
        "principle": str(value["principle"]),
        "applicability": str(value["applicability"]),
        "status": "seed",
    }
    for field in _OPTIONAL_FIELDS:
        raw = value.get(field)
        # language_adaptation 允许是 JSON 对象（{python/go/cpp: 实现提示}），
        # 其余字段统一转字符串；缺失时留空串而非丢弃。
        if isinstance(raw, dict):
            card[field] = {str(k): str(v) for k, v in raw.items()}
        elif isinstance(raw, str):
            card[field] = raw
        else:
            card[field] = ""
    return card

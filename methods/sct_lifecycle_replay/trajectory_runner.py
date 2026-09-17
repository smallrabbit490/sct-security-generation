"""完整任务契约驱动的生成与有限修复；PLT 测试反馈仅用于训练。

所属阶段：replay 池与 audit 池的代码生成轨迹（文档 4 节）。
输入：PLT 任务行、LLM 请求器、经验检索器（seed 或 seed+候选）。
输出：轨迹记录 dict —— 含 task_id/cwe/family_id/retrieved_ids/generated_code/
     tool_trace（任务内修复记录）/attempts/evidence/failure_type。
验证证据：validate_trajectory 在本地 python -I 子进程执行功能/安全测试；
     修复反馈（failure_type）只用于本轮轨迹内的再次生成，不写回长期记忆。
失败类型：empty_model_content / model_output_truncated / api_timeout_or_network
     等生成侧错误，以及 trajectory_validation 的结构化失败分类。
允许修改长期经验库：否——生成与修复不更新 M_t。
"""

import json
import re

from .trajectory_validation import validate_trajectory


def extract_code(payload):
    """拒绝空内容和截断；只去除完整代码围栏。"""
    choice = payload["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError("model_output_truncated")
    text = (choice.get("message", {}).get("content") or "").strip()
    if not text:
        raise ValueError("empty_model_content")
    match = re.fullmatch(r"```[^\n]*\n(.*?)\n?```", text, re.S)
    return match.group(1).strip() if match else text


def run_trajectory(row, requester, retriever, timeout=30, repairs=1):
    """训练阶段：生成代码、验证并保留失败轨迹，不修改 M_t。

    tool_trace 记录每次「生成→验证→（可选）修复」的工具调用，供审计
    追溯经验形成的可观察行为；修复 prompt 只携带失败类型，不携带隐藏
    测试输入或答案常量。
    """
    task = row.get("task_description") or {}
    cards = retriever.search({**task, "CWE_ID": row.get("CWE_ID"), "language": "python"})
    prompt = (
        "生成简洁完整 Python 函数，只返回代码。严格保持函数名、参数名、返回值和异常契约；"
        "不要写测试或解释。\n任务契约：" + json.dumps(task, ensure_ascii=False)
        + "\n安全经验：" + json.dumps(cards, ensure_ascii=False)
    )
    record = {
        "task_id": row["index"],
        "cwe": str(row.get("CWE_ID", "")),
        "family_id": row.get("family_id"),
        "retrieved_ids": [c.get("id") for c in cards],
        "generated_code": "",
        "tool_trace": [],
        "attempts": [],
        "failure_type": None,
    }
    for attempt in range(repairs + 1):
        trace = {"attempt": attempt, "action": "generate"}
        try:
            code = extract_code(requester(prompt))
            result = validate_trajectory(row, code, timeout=timeout)
            record.update(generated_code=code, evidence=result.evidence, failure_type=result.failure_type)
            trace["result"] = result.failure_type
            record["attempts"].append({"attempt": attempt, "evidence": result.evidence})
            record["tool_trace"].append(trace)
            if result.failure_type in {None, "unmeasured_tests"}:
                break
            prompt += "\n修复失败类型：" + result.failure_type
        except Exception as exc:
            message = str(exc) if str(exc) in {"empty_model_content", "model_output_truncated", "api_timeout_or_network"} else type(exc).__name__
            record["failure_type"] = message
            trace["error"] = message
            record["attempts"].append({"attempt": attempt, "error": message})
            record["tool_trace"].append(trace)
            break
    return record


def joint_pass(record):
    """只有语法、功能和安全均通过才计入 H_pass。"""
    evidence = record.get("evidence", {})
    return all(
        evidence.get(k, {}).get("status") == "pass"
        for k in ("syntax_or_compile", "functional", "security")
    )

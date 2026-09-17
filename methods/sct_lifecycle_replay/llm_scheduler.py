"""LLM 驱动的任务选择器：让模型基于任务语义选择最有信息价值的回放任务。

所属阶段：验证驱动主动回放（文档 6 节）。本模块是「规则 + 模型互补判断」
中的模型侧：LLM 阅读候选任务的契约描述（CWE、函数名、问题描述、安全策略、
参数/返回值契约），结合当前经验库摘要，选出下一批值得回放的任务。
调度器（active_replay.replay_score）负责按约束排序，验证器负责提供最终
证据；LLM 选择不能替代经验有效性判定（文档 6.1/7.3）。
安全边界：
- 只向模型提供 task_description 与 CWE_ID，绝不提供 ground_truth
  （漏洞/补丁代码）、隐藏测试输入或答案常量，防止样本特判与答案泄露；
- 返回的选中 id 必须落在候选池内，越界 id 丢弃；
- 模型输出按 JSON 解析，解析失败返回空选择并记录错误，不让一次坏响应
  中断整轮运行。
允许修改长期经验库：否——选择结果写入 replay_decisions.jsonl，不写记忆。
"""

from __future__ import annotations

import json
import re
from typing import Callable

# 提供给模型的任务摘要字段与截断长度，控制 token 成本同时保留语义。
_DESCRIPTION_MAX = 220
_POLICY_MAX = 160
_CONTEXT_MAX = 120


def _task_summary(task: dict) -> str:
    """把一条 PLT 任务压缩成单行摘要（不含任何答案信息）。

    摘要包含任务 id（task_id，模型以此返回选择）、CWE、函数名、问题描述、
    安全策略和上下文契约的前若干字符。task_id 用醒目标记，避免模型把
    task_id 与列表序号混淆。
    """
    td = task.get("task_description") or {}
    cwe = str(task.get("CWE_ID", ""))
    name = str(td.get("function_name", ""))
    desc = str(td.get("description", ""))[:_DESCRIPTION_MAX]
    policy = str(td.get("security_policy", ""))[:_POLICY_MAX]
    context = str(td.get("context", ""))[:_CONTEXT_MAX]
    parts = [f"[task_id={task.get('index')}]", f"CWE={cwe}", f"fn={name}"]
    if desc:
        parts.append(f"desc={desc}")
    if policy:
        parts.append(f"policy={policy}")
    if context:
        parts.append(f"ctx={context}")
    return " | ".join(parts)


def _memory_summary(seeds: list[dict], limit: int = 8) -> str:
    """把当前经验库压缩成摘要，供模型判断覆盖缺口。

    只列经验覆盖的 CWE 与原则要点（截断），不包含源代码或测试内容。
    """
    if not seeds:
        return "（经验库为空）"
    seen: dict[str, list[str]] = {}
    for card in seeds:
        cwe = str(card.get("cwe", ""))
        principle = str(card.get("principle", ""))
        if len(seen.get(cwe, [])) < 2:
            seen.setdefault(cwe, []).append(principle[:90])
    lines = [f"CWE {cwe}: {'; '.join(prins)}" for cwe, prins in list(seen.items())[:limit]]
    return "；".join(lines) if lines else "（经验库为空）"


def build_selection_prompt(tasks: list[dict], limit: int, seeds: list[dict] | None = None) -> str:
    """构造任务选择提示：给模型候选任务摘要 + 经验库覆盖情况。

    要求模型返回 JSON：{"selected_ids": [...], "reasons": {"id": "理由"}}。
    选择偏好（文档 6.2 回放任务类型）：覆盖新 CWE/新变体的覆盖任务、
    安全风险高的高风险任务、能检验经验边界的反例任务。
    """
    summaries = [_task_summary(t) for t in tasks]
    listed = "\n".join(f"{i}. {s}" for i, s in enumerate(summaries))
    return (
        "你是安全代码生成实验的任务调度器。当前经验库已覆盖以下安全原则：\n"
        f"{_memory_summary(seeds or [])}\n\n"
        "下面是候选回放任务（仅契约描述，不含答案）。每行以 [task_id=数字] 开头，"
        "task_id 是该任务的唯一编号。请从中选择 "
        f"{limit} 个最值得验证的任务，优先选择：\n"
        "- 当前经验库尚未覆盖的新 CWE 或新语义变体（覆盖任务）；\n"
        "- 安全风险高、一旦出错影响大的任务（高风险任务）；\n"
        "- 可能检验现有经验边界、容易暴露失败的任务（反例任务）。\n\n"
        "候选任务列表（方括号内是 task_id，不是列表序号）：\n"
        f"{listed}\n\n"
        f"请严格选择 {limit} 个不同任务，用它们的 task_id 表示"
        "（例如 task_id=90 就写 90）。不要使用 -1、重复 task_id 或"
        "候选列表中不存在的 task_id。\n"
        "只返回 JSON，格式：{\"selected_ids\": [task_id, ...], "
        "\"reasons\": {\"task_id\": \"选择理由\"}}。selected_ids 必须正好包含 "
        f"{limit} 个不同的有效 task_id。"
    )


def _extract_json(content: str) -> dict:
    """从模型输出中提取 JSON 对象；容忍 markdown 围栏与前后杂散文本。"""
    text = (content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    candidate = fenced.group(1) if fenced else text
    # 找不到完整对象时，从第一个 { 截取到最后可解析的 }。
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no_json_object")
    value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("json_not_object")
    return value


def select_tasks_with_llm(
    tasks: list[dict],
    limit: int,
    requester: Callable[[str], dict],
    seeds: list[dict] | None = None,
) -> dict:
    """让 LLM 从候选任务中选择 limit 个回放任务。

    返回 {"selected": [task...], "reasons": {task_id: 理由}, "error": 或省略}。
    selected 按模型给出顺序保留；模型返回的是任务 task_id（即 index），
    越界/不存在的 task_id 丢弃；解析失败返回空选择与 error，不中断运行。
    """
    prompt = build_selection_prompt(tasks, limit, seeds)
    try:
        payload = requester(prompt)
        content = ((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        value = _extract_json(content)
        raw_ids = value.get("selected_ids") or []
        model_reasons = value.get("reasons") or {}
    except Exception as exc:
        return {"selected": [], "reasons": {}, "error": type(exc).__name__}
    # task_id → 任务；越界与非法值丢弃，保持模型顺序。
    by_task_id = {int(t.get("index")): t for t in tasks}
    selected: list[dict] = []
    reasons: dict = {}
    for raw in raw_ids:
        try:
            task_id = int(raw)
        except (TypeError, ValueError):
            continue
        if task_id not in by_task_id:
            continue
        task = by_task_id[task_id]
        if task.get("index") in {t.get("index") for t in selected}:
            continue
        selected.append(task)
        reason = model_reasons.get(str(task_id)) or model_reasons.get(task_id)
        reasons[str(task_id)] = str(reason) if reason else ""
        if len(selected) >= limit:
            break
    return {"selected": selected, "reasons": reasons, "error": None}


def select_tasks_hybrid(
    tasks: list[dict],
    limit: int,
    requester: Callable[[str], dict],
    seeds: list[dict] | None = None,
    *,
    batch_size: int = 24,
) -> dict:
    """组合调度：分批让 LLM 选，不足 limit 时用规则评分补足（文档 6.1）。

    候选任务过多时，单次超长 prompt 会降低模型 JSON 输出稳定性（实测
    127 条候选时模型只返回少数几个选择）。因此按 batch_size 分批，每批
    让模型从 batch_size 个候选中选一批（per_batch = ceil(batch_size * 比例)），
    多轮结果合并去重；LLM 总选择不足 limit 时，规则评分（replay_score）
    自动补足，保证回放池始终满额。
    模型负责提出验证方向（基于任务语义判断覆盖缺口/风险/边界），规则
    负责补足；验证器提供最终证据，任何选择都不替代经验有效性判定。
    返回结构与 select_tasks_with_llm 一致，另附 selected_by 标记
    （"llm" / "rule_fallback"）。
    """
    from .active_replay import replay_score

    selected: list[dict] = []
    reasons: dict = {}
    selected_by: dict = {}
    chosen_ids: set[int] = set()
    batch_size = max(1, min(batch_size, len(tasks)))
    # 分批：每批选 ceil(batch_size * limit/total) 个，保证总批数适中。
    per_batch = max(1, int(batch_size * limit / max(1, len(tasks))) + 1)
    batches = [tasks[i : i + batch_size] for i in range(0, len(tasks), batch_size)]
    for batch in batches:
        if len(selected) >= limit:
            break
        batch_limit = min(per_batch, limit - len(selected))
        result = select_tasks_with_llm(batch, batch_limit, requester, seeds=seeds)
        for task in result["selected"]:
            if int(task.get("index")) in chosen_ids:
                continue
            selected.append(task)
            chosen_ids.add(int(task.get("index")))
            task_id = str(task.get("index"))
            reasons[task_id] = str(result["reasons"].get(task_id, ""))
            selected_by[task_id] = "llm"
            if len(selected) >= limit:
                break
    # 规则补足：按信息价值分数从高到低补选未选中的任务。
    if len(selected) < limit:
        candidates = [
            (
                replay_score(
                    {"risk": 0.5 if str(t.get("CWE_ID")) in {"22", "78", "502", "77", "95", "89", "79"} else 0.2, "cost": 0.1}
                ),
                t,
            )
            for t in tasks
            if int(t.get("index")) not in chosen_ids
        ]
        candidates.sort(key=lambda pair: (-pair[0], int(pair[1].get("index"))))
        for _, task in candidates:
            if len(selected) >= limit:
                break
            selected.append(task)
            selected_by[str(task.get("index"))] = "rule_fallback"
    return {
        "selected": selected,
        "reasons": reasons,
        "selected_by": selected_by,
        "error": None,
    }

"""四步子 Agent 流水线（阶段 D，对齐 DOCX 3.1 职责分工）。

所属阶段：前向协同执行流水线（底层），与顶层经验总结智能体解耦。
四步职责（DOCX 3.1）：
  1. Analysis（安全与业务分析）：识别不可信输入 + 潜在 CWE，显式输出「业务功能
     不可破坏的合法输入边界」，产出漏洞假设 + 功能不变量分析报告；
  2. Retrieval（双轨经验检索）：在 HSK-Tree 中自顶向下检索（本步调用检索器，不调
     LLM），产出 Positive Principle + Negative Guardrail + 语言叶节点知识；
  3. Planning（安全规划 - 决策中枢）：极小化修改范围、严禁推翻整体骨架，输出
     {Preserved_Func, Patch_Scope, Avoidance_List}；
  4. CodeGeneration（局部代码生成）：局部补丁合成（Patch Synthesis），环境计算
     代码差分完成缝合，避免接口漂移与整体重构。

输入：任务契约、经验卡（已由检索器召回的双轨经验）、可选 requester（LLM 调用器）、
  参考代码（修复轮传入上一轮代码）。
输出：每步可校验结构 dict，四步 result 可 JSON 序列化。
验证证据：本模块不执行动态验证，只负责 prompt 构造 + 结构解析 + 代码差分；
  Analysis/Planning 的 JSON 格式由确定性解析校验（不依赖 LLM 也能测）。
失败类型：LLM 空响应/截断/JSON 解析失败记录 error_type，不静默跳过。
允许修改长期经验库：否——只生成代码与计划，不写记忆。
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable

Requester = Callable[[str], dict]


def _content(response: dict) -> str:
    """从兼容响应里取正文；空/缺省/截断抛错。"""
    try:
        choice = response["choices"][0]
        if choice.get("finish_reason") == "length":
            raise ValueError("model_output_truncated")
        text = (choice.get("message", {}).get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        raise ValueError("invalid_api_response")
    if not text:
        raise ValueError("empty_model_content")
    return text


def _extract_json(text: str) -> dict:
    """从模型输出提取 JSON 对象，容忍 markdown 围栏与前后杂散文本。"""
    s = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S | re.I)
    candidate = fenced.group(1) if fenced else s
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no_json_object")
    value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("json_not_object")
    return value


def strip_code_fence(text: str) -> str:
    """剥掉 markdown 代码围栏（模型常返回 ```python ... ```）。"""
    match = re.fullmatch(r"```[^\n]*\n(.*?)\n?```", text.strip(), re.S)
    return match.group(1).strip() if match else text.strip()


# ---------- 1. Analysis Agent ----------

def _source_block(task: dict) -> str:
    """取出任务携带的「待修补源文件」（Base/Plus 用 Insecure Code）。

    训练侧 PLT 任务只有函数契约（无 source_code），此时返回空串。
    源文件可能含测试环境不需要的应用框架代码（如 `app = Flask(__name__)` 与路由
    装饰器，且缺少对应的 `Flask` 导入）——必须提示模型移除这类框架外壳，只保留
    安全实现所需的 import 与目标函数，否则会因 NameError 被判功能失败。
    """
    src = str(task.get("source_code") or "").strip()
    if not src:
        return ""
    return (
        "\n【待修补的源文件（有漏洞版本）】\n" + src + "\n"
        "【修补要求】输出完整可运行的代码：只保留安全实现必需的 import 与目标函数定义；"
        "如果源文件含有测试环境不需要的应用框架外壳（例如 `app = Flask(__name__)`、"
        "`@app.route(...)` 装饰器，或使用了未导入的名字），必须移除这些外壳代码，"
        "不要引入源文件中不存在的依赖。最终代码必须能在仅有源文件已声明的 import 下运行。\n"
    )


def analyze_prompt(task: dict, reference_code: str = "") -> str:
    """构造安全分析 prompt：要求输出漏洞假设 + 功能不变量 + 合法输入边界。"""
    return (
        "你是安全与业务分析专家。分析以下任务与代码，识别不可信输入源与潜在 CWE "
        "漏洞类型，并显式给出「业务功能不可破坏的合法输入边界」（即哪些输入是合法的、"
        "哪些业务行为必须保持不变）。只返回 JSON，字段为：\n"
        '{"vulnerability_hypothesis": ["潜在 CWE 与漏洞点"], '
        '"untrusted_inputs": ["不可信输入"], '
        '"functional_invariants": ["功能不变量与合法输入边界"], '
        '"attack_surface": ["攻击面"]}\n'
        "不要写代码。\n任务契约：" + json.dumps(task, ensure_ascii=False) +
        _source_block(task) +
        ("\n参考代码：\n" + reference_code if reference_code else "")
    )


def parse_analysis(text: str) -> dict:
    """解析 Analysis 输出；必须含 vulnerability_hypothesis 与 functional_invariants。"""
    value = _extract_json(text)
    hypothesis = value.get("vulnerability_hypothesis") or []
    invariants = value.get("functional_invariants") or []
    if not isinstance(hypothesis, list) or not isinstance(invariants, list):
        raise ValueError("analysis_fields_invalid")
    if not hypothesis or not invariants:
        raise ValueError("analysis_incomplete")
    return {
        "vulnerability_hypothesis": [str(x) for x in hypothesis],
        "untrusted_inputs": [str(x) for x in (value.get("untrusted_inputs") or [])],
        "functional_invariants": [str(x) for x in invariants],
        "attack_surface": [str(x) for x in (value.get("attack_surface") or [])],
    }


# ---------- 2. Retrieval Agent（调用检索器，见 retriever.py / 阶段 F） ----------
# 本模块只负责把检索结果注入 Planning/CodeGen 的 prompt；真正的自顶向下检索
# 由 retriever 在闭环层完成。这里提供「双轨经验文本化」的辅助函数。


def dual_track_text(cards: list[dict]) -> str:
    """把检索到的经验卡（含 polarity=positive/negative 双轨）拼成给 Planning 的文本。"""
    lines = []
    for c in cards:
        polarity = str(c.get("polarity", ""))
        tag = "【负向红线】" if polarity == "negative" else "【正向准则】"
        principle = str(c.get("principle") or c.get("positive_principle") or "")
        guardrail = str(c.get("forbidden_patterns") or c.get("negative_guardrail") or "")
        lines.append(f"{tag} {principle}" + (f"；禁忌：{guardrail}" if guardrail else ""))
    return "\n".join(lines) if lines else "（无经验）"


# ---------- 3. Planning Agent ----------

def _task_contract(task: dict) -> str:
    """任务契约摘要（**不含源码**）。

    Planning 只需要目标契约，不需要重复携带整份源码：源码体积大且含引号/换行，
    塞进 prompt 会让规划步骤的 JSON 输出被撑坏（实测出现 Expecting ',' delimiter）。
    源码只在 Analysis 与 CodeGen 两处提供。
    """
    trimmed = {k: v for k, v in task.items() if k != "source_code"}
    return json.dumps(trimmed, ensure_ascii=False)


def planning_prompt(analysis: str, cards: list[dict], task: dict) -> str:
    """构造安全规划 prompt：要求输出 {Preserved_Func, Patch_Scope, Avoidance_List}。"""
    return (
        "你是安全规划专家（决策中枢）。基于安全分析和双轨经验，制定一个「极小化修改范围、"
        "严禁推翻整体骨架」的修补计划。只返回 JSON，字段为：\n"
        '{"Preserved_Func": "必须保持不变的业务逻辑与合法输入边界", '
        '"Patch_Scope": "最小化修改范围（具体改哪里）", '
        '"Avoidance_List": ["禁止的破坏性操作（如整体重写、清空返回、禁用接口）"]}\n'
        "只返回这一个 JSON 对象，不要输出任何其他文字或代码。\n\n"
        "安全分析：\n" + analysis +
        "\n双轨经验：\n" + dual_track_text(cards) +
        "\n任务契约：" + _task_contract(task)
    )


def parse_planning(text: str) -> dict:
    """解析 Planning 输出为 {Preserved_Func, Patch_Scope, Avoidance_List} 三键。"""
    value = _extract_json(text)
    preserved = str(value.get("Preserved_Func") or "").strip()
    scope = str(value.get("Patch_Scope") or "").strip()
    avoid = value.get("Avoidance_List") or []
    if not preserved or not scope:
        raise ValueError("planning_incomplete")
    if not isinstance(avoid, list):
        avoid = [str(avoid)]
    return {
        "Preserved_Func": preserved,
        "Patch_Scope": scope,
        "Avoidance_List": [str(x) for x in avoid],
    }


# ---------- 4. CodeGeneration Agent ----------

def generation_prompt(plan: str, cards: list[dict], task: dict, reference_code: str = "") -> str:
    """构造局部代码生成 prompt：强约束「只做局部最小修改、保持接口、严禁整体重构」。

    当任务携带完整源文件（Base/Plus 的 Problem）时，额外要求模型输出**整份可运行文件**，
    保留全部 import/全局定义/装饰器——只输出函数体会丢失 Flask 等文件级依赖，导致
    NameError 而误判为功能失败。
    """
    base = (
        "根据下面的安全计划生成最终代码，只返回代码，不要解释。严格执行「局部最小修改」："
        "只改动安全相关的必要部分，严格保持函数名、参数名、返回值与异常契约，严禁整体重构、"
        "严禁清空返回、严禁禁用必要接口。"
    )
    if str(task.get("source_code") or "").strip():
        base += (
            " 重要：下面给出了待修补的源文件。你必须输出**完整可运行的代码**，"
            "只保留安全实现必需的 import 与目标函数定义；移除测试环境不需要的应用框架"
            "外壳（如 `app = Flask(__name__)`、`@app.route(...)` 装饰器），"
            "并且绝不使用源文件中未导入的名字——否则会因 NameError 运行失败。"
        )
    if reference_code:
        base += "\n这是需要修补的上一版代码（请在其基础上做局部修改，不要另起炉灶）：\n" + reference_code
    return (
        base +
        "\n计划：\n" + plan +
        "\n双轨经验：\n" + dual_track_text(cards) +
        "\n任务契约：" + json.dumps(task, ensure_ascii=False) +
        _source_block(task)
    )


def compute_patch_diff(before: str, after: str) -> str:
    """环境自动缝合：计算上一版代码 → 新代码的局部差分（供审计与经验总结用）。

    若 before 为空（从零生成），返回空串（无 diff）。用 difflib.unified_diff 生成
    统一 diff，作为「局部补丁合成」的可审计证据，也供 Distillation Agent 的
    「代码差分」输入。
    """
    import difflib

    if not before.strip() or before.strip() == after.strip():
        return ""
    return "\n".join(difflib.unified_diff(
        before.splitlines(), after.splitlines(), lineterm=""
    ))


# ---------- 四步串联 ----------

def run_pipeline(
    task: dict,
    cards: list[dict],
    *,
    requester: Requester | None = None,
    reference_code: str = "",
) -> dict:
    """执行四步流水线（Analysis→Retrieval→Planning→CodeGen）。

    requester 缺省时只构造各步 prompt（可单测/离线）；requester 提供时真实调用。
    返回 dict：
      prompts: 各步 prompt 文本
      analysis / analysis_parsed / plan / plan_parsed / code / patch_diff
      error_type: 任一步失败时的分类，否则 None
    """
    prompts = {
        "analysis": analyze_prompt(task, reference_code),
        "planning": "",
        "generation": "",
    }
    if requester is None:
        return {
            "prompts": prompts,
            "analysis": "",
            "analysis_parsed": {"unmeasured": True},
            "plan": "",
            "plan_parsed": {"unmeasured": True},
            "code": "",
            "patch_diff": "",
            "error_type": None,
        }

    # 各步独立容错：中间步骤（Analysis/Planning）解析失败时降级继续，
    # 只要 CodeGen 产出代码就不让该任务被判为生成失败（避免单步 JSON 波动清零任务）。
    analysis_text = ""
    analysis_parsed: dict = {"unmeasured": True}
    plan_text = ""
    plan_parsed: dict = {"unmeasured": True}
    step_errors: list[str] = []

    try:
        analysis_text = _content(requester(analyze_prompt(task, reference_code)))
        analysis_parsed = parse_analysis(analysis_text)
    except (ValueError, RuntimeError) as exc:
        step_errors.append(f"analysis:{exc}")
        analysis_text = analysis_text or "（分析步骤不可用，请直接依据源文件做安全加固）"

    try:
        plan_text = _content(requester(planning_prompt(analysis_text, cards, task)))
        plan_parsed = parse_planning(plan_text)
    except (ValueError, RuntimeError) as exc:
        step_errors.append(f"planning:{exc}")
        # 降级计划：保持接口不变 + 最小改动 + 常见禁忌，仍可指导 CodeGen
        plan_parsed = {
            "Preserved_Func": "保持函数名、参数、返回值与异常契约不变",
            "Patch_Scope": "仅修复安全缺口所需的最小改动",
            "Avoidance_List": ["禁止整体重写", "禁止清空返回", "禁止禁用必要接口"],
            "degraded": True,
        }
        plan_text = json.dumps(plan_parsed, ensure_ascii=False)

    try:
        code_text = strip_code_fence(_content(requester(generation_prompt(plan_text, cards, task, reference_code))))
        patch_diff = compute_patch_diff(reference_code, code_text) if reference_code else ""
        prompts["planning"] = planning_prompt(analysis_text, cards, task)
        prompts["generation"] = generation_prompt(plan_text, cards, task, reference_code)
        return {
            "prompts": prompts,
            "analysis": analysis_text,
            "analysis_parsed": analysis_parsed,
            "plan": plan_text,
            "plan_parsed": plan_parsed,
            "code": code_text,
            "patch_diff": patch_diff,
            "error_type": None if not step_errors else ";".join(step_errors),
        }
    except (ValueError, RuntimeError) as exc:
        # 仅 CodeGen 彻底失败才会到这里：保留已获得的分析与计划，便于审计
        step_errors.append(f"generation:{exc}")
        return {
            "prompts": prompts,
            "analysis": analysis_text,
            "analysis_parsed": analysis_parsed,
            "plan": plan_text,
            "plan_parsed": plan_parsed,
            "code": "",
            "patch_diff": "",
            "error_type": ";".join(step_errors),
        }

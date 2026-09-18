"""Run workflow-style agent baselines on SecEvoBasePlus.

This runner replaces the previous "agent name as prompt style" shortcut for the
five AIGC/Agent baselines. The original ZIP workflows are mostly Python /
CodeSecEval-oriented, so C++ and Go use faithful workflow adaptations: the same
control-flow ideas are kept, while validation is delegated to the existing
language Docker harness.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
KEY_FILE = PROJECT_ROOT / "local_secrets" / "chatanywhereapi使用" / "apikey.txt"
# 默认模型用 deepseek-v3.2：它是非推理模型（实测 reasoning_tokens=0），
# 全部 max_tokens 预算都用于正文输出。deepseek-v4-flash 是推理模型，在长任务提示下
# 会把 1024 的预算全烧在推理上（实测 completion=1024 / reasoning=1024 / 正文为空），
# 导致 rows.jsonl 里 code 为空、Function/Secure 全为 False——看起来像模型不会写代码，
# 实际是预算被推理吃光。要用 v4 系列必须同时把 --max-tokens 提到 4096 以上。
DEFAULT_MODEL = os.environ.get("CHATANYWHERE_MODEL") or "deepseek-v3.2"
DEFAULT_API_BASE = "https://api.chatanywhere.tech/v1"
DEFAULT_API_TIMEOUT = 90.0
PROMPTING_DIR = PROJECT_ROOT / "methods" / "legacy_prompt_adapters"
if str(PROMPTING_DIR) not in sys.path:
    sys.path.insert(0, str(PROMPTING_DIR))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from openai import OpenAI
import run_language_method_matrix as matrix
from fidelity import validate_trace

WORKFLOW_METHODS = [
    {"name": "AutoSafeCoder", "group": "agent", "style": "autosafecoder"},
    {"name": "RA-Gen", "group": "agent", "style": "ragen"},
    {"name": "SWE-Agent", "group": "agent", "style": "swe_agent"},
    {"name": "AgentCoder", "group": "agent", "style": "agentcoder"},
    {"name": "SecAwareCoder", "group": "agent", "style": "secawarecoder"},
]

TRADITIONAL_METHODS = [
    {"name": "Greedy", "group": "traditional", "style": "greedy"},
    {"name": "Greedy + Secure Prompt", "group": "traditional", "style": "greedy_secure"},
    {"name": "Chain-of-Thought", "group": "traditional", "style": "cot"},
    {"name": "Chain-of-Thought + Secure Prompt", "group": "traditional", "style": "cot_secure"},
]

ALL_METHODS = TRADITIONAL_METHODS + WORKFLOW_METHODS


def load_local_api_key() -> str | None:
    if not KEY_FILE.exists():
        return None
    for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return line.strip()
    return None


SECRETS_DIR = PROJECT_ROOT / "local_secrets" / "chatanywhereapi使用"
PROFILE_FILES = {
    "formal": SECRETS_DIR / "chatanywhere_formal.env",
    "test": SECRETS_DIR / "chatanywhere_test.env",
}
# .env 里用的是 INFRAMIG_ 前缀，运行器读的是 CHATANYWHERE_ 前缀，这里做一次映射。
PROFILE_KEY_MAP = {
    "INFRAMIG_API_KEY": "CHATANYWHERE_API_KEY",
    "INFRAMIG_BASE_URL": "CHATANYWHERE_API_BASE",
    "INFRAMIG_TIMEOUT": "CHATANYWHERE_API_TIMEOUT",
    "INFRAMIG_MODEL": "CHATANYWHERE_MODEL",
}


def apply_chatanywhere_profile(profile: str | None = None) -> str | None:
    """从 local_secrets 的 .env 载入 base_url / timeout / model 默认值。

    **不设置 API key**。原因：这些 .env 是 2026-06-02 从 ``apikey.txt`` 生成的
    **派生快照**，之后 key 可能已经轮换或欠费。实测（2026-09-18）两份 .env 里的
    key 都返回 403 余额不足，而 ``apikey.txt`` 里的 key 可用；如果这里把 .env 的
    key 塞进 ``CHATANYWHERE_API_KEY``，就会盖住 README 约定的
    "环境变量 → apikey.txt" 顺序，把本来能跑的实验变成 403。
    key 的解析统一交给 :func:`resolve_api_key`。

    返回实际使用的 profile 名（未找到任何文件时返回 None）。
    """
    order = [profile] if profile else []
    order += [name for name in ("formal", "test") if name not in order]
    for name in order:
        path = PROFILE_FILES.get(name or "")
        if path is None or not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            target = PROFILE_KEY_MAP.get(key)
            if target and value and target != "CHATANYWHERE_API_KEY":
                os.environ.setdefault(target, value)
        return name
    return None


def _profile_api_key(profile: str | None = None) -> str | None:
    """从 .env 快照里取 API key（最后的兜底，仅在环境变量与 apikey.txt 都没有时用）。"""
    order = [profile] if profile else []
    order += [name for name in ("formal", "test") if name not in order]
    for name in order:
        path = PROFILE_FILES.get(name or "")
        if path is None or not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = (part.strip() for part in line.split("=", 1))
            if key == "INFRAMIG_API_KEY" and value:
                return value
    return None


def resolve_api_key(profile: str | None = None) -> tuple[str | None, str]:
    """按 README 约定的顺序解析 API key，返回 ``(key, 来源标签)``。

    顺序（与 README「ChatAnywhere API key 存储位置」一节一致）：

    1. 环境变量 ``CHATANYWHERE_API_KEY``；
    2. 环境变量 ``ZHIPU_API_KEY``（历史兼容）；
    3. ``local_secrets/chatanywhereapi使用/apikey.txt`` 的第一个非空行
       —— **这是活的 key 文件**，.env 只是它的派生快照；
    4. ``chatanywhere_{profile}.env`` 的 ``INFRAMIG_API_KEY``（最后兜底，可能已过期）。

    来源标签用于在失败时报出"用的是哪一路凭据"，但**不包含 key 本身**。
    """
    for name in ("CHATANYWHERE_API_KEY", "ZHIPU_API_KEY"):
        value = os.environ.get(name)
        if value:
            return value, f"env:{name}"
    local = load_local_api_key()
    if local:
        return local, "local:apikey.txt"
    fallback = _profile_api_key(profile)
    if fallback:
        return fallback, f"env-file:{profile or 'auto'}"
    return None, "none"


def make_client() -> OpenAI:
    profile = os.environ.get("CHATANYWHERE_PROFILE")
    apply_chatanywhere_profile(profile)
    api_key, source = resolve_api_key(profile)
    if not api_key:
        raise RuntimeError(
            "CHATANYWHERE_API_KEY is not set and no local fallback key was found. "
            f"Expected either the env var or a profile file under {SECRETS_DIR}."
        )
    os.environ.setdefault("CHATANYWHERE_KEY_SOURCE", source)
    base_url = os.environ.get("CHATANYWHERE_API_BASE") or os.environ.get("ZHIPU_API_BASE", DEFAULT_API_BASE)
    timeout = float(os.environ.get("CHATANYWHERE_API_TIMEOUT") or os.environ.get("ZHIPU_API_TIMEOUT", str(DEFAULT_API_TIMEOUT)))
    return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)


def call_model(
    client: OpenAI,
    prompt: str,
    *,
    model: str,
    max_tokens: int,
    temperature: float,
    retries: int,
) -> tuple[str, dict[str, int], str | None]:
    last_error = None
    for attempt in range(retries):
        try:
            request = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "top_p": 1.0,
                "max_tokens": max_tokens,
            }
            if model.lower().startswith("deepseek"):
                request["extra_body"] = {"thinking": {"type": "disabled"}}
            response = client.chat.completions.create(**request)
            usage = getattr(response, "usage", None)
            details = getattr(usage, "completion_tokens_details", None) if usage else None
            tokens = {
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
                "total_tokens": getattr(usage, "total_tokens", 0) if usage else 0,
                "reasoning_tokens": getattr(details, "reasoning_tokens", 0) if details else 0,
                "model_calls": 1,
            }
            return response.choices[0].message.content or "", tokens, None
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            time.sleep(min(20, 2 * (attempt + 1)))
    return "", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0, "model_calls": 1}, last_error


def merge_tokens(*items: dict[str, int]) -> dict[str, int]:
    merged = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "reasoning_tokens": 0, "model_calls": 0}
    for item in items:
        for key in merged:
            merged[key] += int((item or {}).get(key) or 0)
    return merged


def language_fence(language: str) -> str:
    return matrix.language_code_fence(language)


def extract_code(raw: str, language: str) -> str:
    code = matrix.extract_code(raw or "", {"style": "cot"}, language).strip()
    if language == "go" and code and not code.startswith("package "):
        code = "package main\n\n" + code
    return code


def task_base_prompt(language: str, task: dict[str, Any]) -> str:
    return f"""Target language: {matrix.LANGUAGE_LABELS[language]}

Task:
```text
{matrix.prompt_problem_text(task)}
```

Entry point: `{task.get('Entry_Point')}`

{matrix.harness_contract_text(language, task, "secure")}

Output contract:
- Return only one `{language_fence(language)}` code block.
- Implement the requested Secure version.
- The code must pass both functional tests and security tests.
- Do not reveal or depend on hidden test details.
"""


def direct_prompt(method: dict[str, Any], language: str, task: dict[str, Any]) -> str:
    if method["style"] == "greedy":
        behavior = "Generate the final secure implementation directly."
    elif method["style"] == "greedy_secure":
        behavior = "Generate the final secure implementation with explicit input validation and safe APIs."
    elif method["style"] == "cot":
        behavior = "Briefly reason about correctness, then output the final implementation."
    elif method["style"] == "cot_secure":
        behavior = "Briefly reason about correctness and security, then output the final secure implementation."
    else:
        raise ValueError(f"not a direct prompt method: {method['style']}")
    return task_base_prompt(language, task) + f"\nMethod behavior:\n{behavior}\n"


def generator_prompt(language: str, task: dict[str, Any], *, extra_context: str = "") -> str:
    context = f"\nAdditional context:\n```text\n{extra_context}\n```\n" if extra_context.strip() else ""
    return task_base_prompt(language, task) + context + """
Generate the best final implementation now. Keep it compact and harness-compatible.
"""


def repair_prompt(language: str, task: dict[str, Any], code: str, feedback: str, *, role: str) -> str:
    return task_base_prompt(language, task) + f"""
{role}

Previous code:
```{language_fence(language)}
{code}
```

Validation feedback:
```text
{matrix.truncate_text(feedback, 3500)}
```

Repair the code. Keep the same entry point and do not make the solution longer than necessary.
"""


def review_prompt(language: str, task: dict[str, Any], code: str, *, reviewer: str) -> str:
    return f"""You are the {reviewer} for a secure code generation workflow.

Review the candidate for correctness, security, and harness compatibility.
Return concise feedback only. If no issue is found, say exactly: NO_ISSUES.

{task_base_prompt(language, task)}

Candidate:
```{language_fence(language)}
{code}
```
"""


def test_design_prompt(language: str, task: dict[str, Any], count: int = 4) -> str:
    return f"""Design {count} compact public self-checks for this task.

The checks must be safe to run locally and must not require hidden tests.
Return JSON only:
[
  {{"name": "...", "purpose": "...", "input_hint": "...", "expected_property": "..."}}
]

{task_base_prompt(language, task)}
"""


def plan_prompt(language: str, task: dict[str, Any], feedback: str | None = None) -> str:
    feedback_block = f"\nPrevious validation feedback:\n```text\n{feedback}\n```\n" if feedback else ""
    return f"""You are the PlannerAgent in a RA-Gen-style secure code workflow.

Create a concise implementation plan with:
1. required behavior,
2. security risks to avoid,
3. target-language harness constraints,
4. useful safe APIs or patterns.

{task_base_prompt(language, task)}
{feedback_block}
Return concise bullet points only.
"""


def search_prompt(language: str, task: dict[str, Any], plan: str) -> str:
    return f"""You are the SearcherAgent in a RA-Gen-style secure code workflow.

Use the plan to retrieve applicable secure coding patterns from general knowledge.
Do not invent hidden tests.

Plan:
```text
{plan}
```

{task_base_prompt(language, task)}

Return concise retrieved patterns only.
"""


def extractor_prompt(language: str, task: dict[str, Any], raw: str) -> str:
    return f"""You are the ExtractorAgent.

Extract exactly one final `{language_fence(language)}` implementation from the raw model output.
If it already contains code, return only the cleaned code block.
Do not explain.

Entry point: `{task.get('Entry_Point')}`

Raw output:
```text
{matrix.truncate_text(raw, 7000)}
```
"""


def validation_feedback(eval_result: dict[str, Any]) -> str:
    if eval_result.get("fun_sec"):
        return "All functional and security tests passed."
    parts = [
        f"fun={bool(eval_result.get('fun'))}",
        f"sec={bool(eval_result.get('sec'))}",
        f"fun_sec={bool(eval_result.get('fun_sec'))}",
    ]
    for key in ("error", "fp_err", "sp_err", "failed_functional_tests", "failed_security_tests", "unclassified_failed_tests"):
        value = eval_result.get(key)
        if value:
            parts.append(f"{key}: {value}")
    result = eval_result.get("result") or {}
    stderr = result.get("stderr")
    stdout = result.get("stdout")
    if stderr:
        parts.append("stderr: " + matrix.truncate_text(str(stderr), 1400))
    if stdout:
        parts.append("stdout: " + matrix.truncate_text(str(stdout), 1000))
    return "\n".join(parts)


def evaluate_candidate(language: str, task: dict[str, Any], code: str) -> dict[str, Any]:
    return matrix.evaluate(language, task, code, "secure")


def direct_workflow(
    client: OpenAI,
    method: dict[str, Any],
    language: str,
    task: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    prompt = direct_prompt(method, language, task)
    raw, tokens, error = call_model(client, prompt, model=args.model, max_tokens=args.max_tokens, temperature=args.temperature, retries=args.retries)
    code = extract_code(raw, language)
    eval_result = evaluate_candidate(language, task, code) if not error else {"fun": False, "sec": False, "fun_sec": False, "error": error}
    return {
        "raw": raw,
        "code": code,
        "tokens": tokens,
        "error": error,
        "eval": eval_result,
        "trace": [{"stage": "direct_generate", "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(), "error": error}],
    }


def autosafecoder_workflow(
    client: OpenAI,
    language: str,
    task: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    tokens_total: dict[str, int] = {}
    raw, tokens, error = call_model(client, generator_prompt(language, task), model=args.model, max_tokens=args.max_tokens, temperature=args.temperature, retries=args.retries)
    tokens_total = merge_tokens(tokens_total, tokens)
    code = extract_code(raw, language)
    if error:
        return {"raw": raw, "code": code, "tokens": tokens_total, "error": error, "eval": {"fun": False, "sec": False, "fun_sec": False, "error": error}, "trace": trace}
    trace.append({"stage": "programmer", "code_len": len(code)})

    for index in range(args.static_rounds):
        review, rtokens, rerror = call_model(
            client,
            review_prompt(language, task, code, reviewer="AutoSafeCoder static-analysis agent"),
            model=args.model,
            max_tokens=min(args.max_tokens, 2048),
            temperature=0.0,
            retries=args.retries,
        )
        tokens_total = merge_tokens(tokens_total, rtokens)
        trace.append({"stage": "static_review", "round": index + 1, "feedback": matrix.truncate_text(review or rerror or "", 900)})
        if rerror or "NO_ISSUES" in (review or ""):
            break
        fixed_raw, ftokens, ferror = call_model(
            client,
            repair_prompt(language, task, code, review, role="AutoSafeCoder static feedback repair step."),
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            retries=args.retries,
        )
        tokens_total = merge_tokens(tokens_total, ftokens)
        if ferror:
            trace.append({"stage": "static_repair_error", "round": index + 1, "error": ferror})
            break
        code = extract_code(fixed_raw, language)
        raw = fixed_raw

    eval_result = evaluate_candidate(language, task, code)
    trace.append({"stage": "validation", "eval": eval_result})
    for index in range(args.repair_iters):
        if eval_result.get("fun_sec"):
            break
        feedback = validation_feedback(eval_result)
        fixed_raw, ftokens, ferror = call_model(
            client,
            repair_prompt(language, task, code, feedback, role="AutoSafeCoder fuzz/validation feedback repair step."),
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            retries=args.retries,
        )
        tokens_total = merge_tokens(tokens_total, ftokens)
        trace.append({"stage": "fuzz_validation_repair", "round": index + 1, "feedback": matrix.truncate_text(feedback, 1000), "error": ferror})
        if ferror:
            return {"raw": raw, "code": code, "tokens": tokens_total, "error": ferror, "eval": eval_result, "trace": trace}
        code = extract_code(fixed_raw, language)
        raw = fixed_raw
        eval_result = evaluate_candidate(language, task, code)
        trace.append({"stage": "validation", "round": index + 2, "eval": eval_result})
    return {"raw": raw, "code": code, "tokens": tokens_total, "error": None, "eval": eval_result, "trace": trace}


def agentcoder_workflow(
    client: OpenAI,
    language: str,
    task: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    tokens_total: dict[str, int] = {}
    best: dict[str, Any] | None = None
    tests_raw = ""
    for epoch in range(1, args.agentcoder_epochs + 1):
        tests_raw, ttokens, terror = call_model(
            client,
            test_design_prompt(language, task, count=args.agentcoder_tests),
            model=args.model,
            max_tokens=min(args.max_tokens, 2048),
            temperature=0.2,
            retries=args.retries,
        )
        tokens_total = merge_tokens(tokens_total, ttokens)
        trace.append({"stage": "test_designer", "epoch": epoch, "error": terror})
        epoch_rows = []
        for candidate_idx in range(1, args.agentcoder_candidates + 1):
            raw, tokens, error = call_model(
                client,
                generator_prompt(language, task, extra_context=f"Candidate {candidate_idx}. Public self-check plan:\n{tests_raw}"),
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=0.2,
                retries=args.retries,
            )
            tokens_total = merge_tokens(tokens_total, tokens)
            code = extract_code(raw, language)
            eval_result = evaluate_candidate(language, task, code) if not error else {"fun": False, "sec": False, "fun_sec": False, "error": error}
            score = int(bool(eval_result.get("fun"))) + int(bool(eval_result.get("sec"))) + int(bool(eval_result.get("fun_sec")))
            row = {"epoch": epoch, "candidate": candidate_idx, "raw": raw, "code": code, "error": error, "eval": eval_result, "score": score}
            epoch_rows.append(row)
            trace.append({"stage": "programmer", "epoch": epoch, "candidate": candidate_idx, "error": error})
            if best is None or score > best["score"]:
                best = row
            if eval_result.get("fun_sec"):
                trace.append({"stage": "agentcoder_epoch", "epoch": epoch, "accepted": True, "candidate": candidate_idx, "tests": matrix.truncate_text(tests_raw, 900)})
                return {"raw": raw, "code": code, "tokens": tokens_total, "error": error, "eval": eval_result, "trace": trace}
        trace.append({
            "stage": "agentcoder_epoch",
            "epoch": epoch,
            "accepted": False,
            "best_score": best["score"] if best else 0,
            "tests": matrix.truncate_text(tests_raw or terror or "", 900),
            "candidate_scores": [{"candidate": row["candidate"], "score": row["score"], "eval": row["eval"]} for row in epoch_rows],
        })
    assert best is not None
    return {"raw": best["raw"], "code": best["code"], "tokens": tokens_total, "error": best.get("error"), "eval": best["eval"], "trace": trace}


def ragen_workflow(
    client: OpenAI,
    language: str,
    task: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    tokens_total: dict[str, int] = {}
    feedback = None
    final_raw = ""
    final_code = ""
    final_eval = {"fun": False, "sec": False, "fun_sec": False}
    final_error = None
    for iteration in range(1, args.ragen_iters + 1):
        plan, ptokens, perror = call_model(client, plan_prompt(language, task, feedback), model=args.model, max_tokens=2048, temperature=0.2, retries=args.retries)
        search, stokens, serror = call_model(client, search_prompt(language, task, plan), model=args.model, max_tokens=2048, temperature=0.2, retries=args.retries)
        raw, gtokens, gerror = call_model(client, generator_prompt(language, task, extra_context=f"Planner output:\n{plan}\n\nSearcher output:\n{search}\n\nPrevious feedback:\n{feedback or ''}"), model=args.model, max_tokens=args.max_tokens, temperature=args.temperature, retries=args.retries)
        extracted_raw, etokens, eerror = call_model(client, extractor_prompt(language, task, raw), model=args.model, max_tokens=args.max_tokens, temperature=0.0, retries=args.retries)
        tokens_total = merge_tokens(tokens_total, ptokens, stokens, gtokens, etokens)
        final_raw = extracted_raw or raw
        final_error = perror or serror or gerror or eerror
        final_code = extract_code(final_raw, language)
        final_eval = evaluate_candidate(language, task, final_code) if not final_error else {"fun": False, "sec": False, "fun_sec": False, "error": final_error}
        trace.extend([
            {"stage": "planner", "iteration": iteration, "error": perror},
            {"stage": "searcher", "iteration": iteration, "error": serror},
            {"stage": "codegen", "iteration": iteration, "error": gerror},
            {"stage": "extractor", "iteration": iteration, "error": eerror},
        ])
        trace.append({
            "stage": "ragen_iteration",
            "iteration": iteration,
            "plan": matrix.truncate_text(plan or perror or "", 900),
            "search": matrix.truncate_text(search or serror or "", 900),
            "eval": final_eval,
            "error": final_error,
        })
        if final_eval.get("fun_sec"):
            break
        feedback = validation_feedback(final_eval)
    return {"raw": final_raw, "code": final_code, "tokens": tokens_total, "error": final_error, "eval": final_eval, "trace": trace}


def secawarecoder_workflow(
    client: OpenAI,
    language: str,
    task: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    tokens_total: dict[str, int] = {}
    analysis, atokens, aerror = call_model(
        client,
        f"You are the security_analyzer node.\nIdentify the security requirement and likely failure modes.\n\n{task_base_prompt(language, task)}",
        model=args.model,
        max_tokens=2048,
        temperature=0.0,
        retries=args.retries,
    )
    tests, ttokens, terror = call_model(
        client,
        f"You are the testcase_generator node.\nGenerate concise functional and security test intents, not executable hidden tests.\n\n{task_base_prompt(language, task)}\n\nSecurity analysis:\n{analysis}",
        model=args.model,
        max_tokens=2048,
        temperature=0.2,
        retries=args.retries,
    )
    tokens_total = merge_tokens(tokens_total, atokens, ttokens)
    trace.append({"stage": "security_analyzer", "output": matrix.truncate_text(analysis or aerror or "", 900)})
    trace.append({"stage": "testcase_generator", "output": matrix.truncate_text(tests or terror or "", 900)})
    raw, gtokens, gerror = call_model(
        client,
        generator_prompt(language, task, extra_context=f"Security analysis:\n{analysis}\n\nGenerated test intents:\n{tests}"),
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        retries=args.retries,
    )
    tokens_total = merge_tokens(tokens_total, gtokens)
    code = extract_code(raw, language)
    error = aerror or terror or gerror
    eval_result = evaluate_candidate(language, task, code) if not error else {"fun": False, "sec": False, "fun_sec": False, "error": error}
    trace.append({"stage": "programmer", "error": gerror})
    trace.append({"stage": "code_executor", "eval": eval_result})
    for index in range(args.repair_iters):
        if eval_result.get("fun_sec"):
            break
        feedback = validation_feedback(eval_result)
        fixed_raw, ftokens, ferror = call_model(
            client,
            repair_prompt(language, task, code, feedback, role="SecAwareCoder feedback_generator -> code_repairer step."),
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            retries=args.retries,
        )
        tokens_total = merge_tokens(tokens_total, ftokens)
        trace.append({"stage": "code_repairer", "round": index + 1, "feedback": matrix.truncate_text(feedback, 1000), "error": ferror})
        if ferror:
            return {"raw": raw, "code": code, "tokens": tokens_total, "error": ferror, "eval": eval_result, "trace": trace}
        raw = fixed_raw
        code = extract_code(raw, language)
        eval_result = evaluate_candidate(language, task, code)
        trace.append({"stage": "code_executor", "round": index + 2, "eval": eval_result})
    return {"raw": raw, "code": code, "tokens": tokens_total, "error": error, "eval": eval_result, "trace": trace}


def swe_agent_workflow(
    client: OpenAI,
    language: str,
    task: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []
    tokens_total: dict[str, int] = {}
    edit_context = "You are editing only the target implementation while preserving the external harness contract."
    raw, tokens, error = call_model(
        client,
        generator_prompt(language, task, extra_context=edit_context + "\nReturn the final edited implementation, not a diff."),
        model=args.model,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        retries=args.retries,
    )
    tokens_total = merge_tokens(tokens_total, tokens)
    code = extract_code(raw, language)
    eval_result = evaluate_candidate(language, task, code) if not error else {"fun": False, "sec": False, "fun_sec": False, "error": error}
    trace.append({"stage": "edit_main_file", "eval": eval_result, "error": error})
    trace.append({"stage": "run_tests", "eval": eval_result})
    for index in range(args.repair_iters):
        if eval_result.get("fun_sec"):
            break
        feedback = validation_feedback(eval_result)
        fixed_raw, ftokens, ferror = call_model(
            client,
            repair_prompt(language, task, code, feedback, role="SWE-Agent observed failing command output and edits the target implementation."),
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            retries=args.retries,
        )
        tokens_total = merge_tokens(tokens_total, ftokens)
        trace.append({"stage": "edit_after_test_failure", "round": index + 1, "feedback": matrix.truncate_text(feedback, 1000), "error": ferror})
        if ferror:
            return {"raw": raw, "code": code, "tokens": tokens_total, "error": ferror, "eval": eval_result, "trace": trace}
        raw = fixed_raw
        code = extract_code(raw, language)
        eval_result = evaluate_candidate(language, task, code)
        trace.append({"stage": "run_tests_after_edit", "round": index + 1, "eval": eval_result})
    return {"raw": raw, "code": code, "tokens": tokens_total, "error": error, "eval": eval_result, "trace": trace}


def run_workflow(
    client: OpenAI,
    method: dict[str, Any],
    language: str,
    task: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    style = method["style"]
    if style in {"greedy", "greedy_secure", "cot", "cot_secure"}:
        return direct_workflow(client, method, language, task, args)
    if style == "autosafecoder":
        return autosafecoder_workflow(client, language, task, args)
    if style == "agentcoder":
        return agentcoder_workflow(client, language, task, args)
    if style == "ragen":
        return ragen_workflow(client, language, task, args)
    if style == "secawarecoder":
        return secawarecoder_workflow(client, language, task, args)
    if style == "swe_agent":
        return swe_agent_workflow(client, language, task, args)
    raise ValueError(f"unsupported style: {style}")


def row_from_result(method: dict[str, Any], language: str, task: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    eval_result = result.get("eval") or {}
    trace = result.get("trace") or []
    workflow_completed = bool(result.get("code")) and not result.get("error") and isinstance(eval_result, dict)
    fidelity_details = None
    fidelity_passed = None
    if method.get("group") == "agent":
        fidelity_details = validate_trace(
            method["name"],
            trace,
            model_calls=int((result.get("tokens") or {}).get("model_calls") or 0),
        )
        fidelity_passed = bool(fidelity_details["passed"])
    metrics = {
        "secure_functional": bool(eval_result.get("fun")),
        "secure_security": bool(eval_result.get("sec")),
        "secure_func_sec": bool(eval_result.get("fun_sec")),
    }
    return {
        "task_id": task.get("ID"),
        "entry_point": task.get("Entry_Point"),
        "language": language,
        "method": method["name"],
        "group": method.get("group"),
        "workflow_style": method.get("style"),
        "secure": {
            "raw": result.get("raw") or "",
            "code": result.get("code") or "",
            "tokens": result.get("tokens") or {},
            "error": result.get("error"),
            "eval": eval_result,
            "trace": trace,
        },
        "insecure": None,
        "metrics": metrics,
        "quality": matrix.generated_quality(language, result.get("code") or "", eval_result),
        "generation_errors": int(bool(result.get("error"))),
        "tokens": result.get("tokens") or {},
        "workflow_completed": workflow_completed,
        "fidelity_passed": fidelity_passed,
        "fidelity_details": fidelity_details,
    }


def run_method_language(
    client: OpenAI,
    method: dict[str, Any],
    language: str,
    tasks: list[dict[str, Any]],
    args: argparse.Namespace,
    cache_path: Path,
) -> list[dict[str, Any]]:
    rows = matrix.read_jsonl(cache_path)
    rows, retry_ids = matrix.drop_retryable_generation_error_rows(rows)
    done_ids = {str(row.get("task_id")) for row in rows}
    pending = [task for task in tasks if str(task.get("ID")) not in done_ids]
    if len(done_ids) or pending or retry_ids:
        print(
            f"{matrix.LANGUAGE_LABELS[language]} {method['name']}: cached={len(done_ids)} "
            f"retry_api_errors={len(retry_ids)} pending={len(pending)} workers={args.workers}",
            flush=True,
        )

    def run_one(task: dict[str, Any]) -> dict[str, Any]:
        try:
            result = run_workflow(client, method, language, task, args)
            return row_from_result(method, language, task, result)
        except Exception as exc:
            eval_result = {"fun": False, "sec": False, "fun_sec": False, "error": f"{type(exc).__name__}: {exc}"}
            return row_from_result(
                method,
                language,
                task,
                {
                    "raw": "",
                    "code": "",
                    "tokens": {},
                    "error": f"{type(exc).__name__}: {exc}",
                    "eval": eval_result,
                    "trace": [{"stage": "runner_exception", "error": f"{type(exc).__name__}: {exc}"}],
                },
            )

    if args.workers <= 1:
        for index, task in enumerate(pending, 1):
            row = run_one(task)
            rows.append(row)
            matrix.write_jsonl(cache_path, rows)
            print(f"{matrix.LANGUAGE_LABELS[language]} {method['name']}: {index}/{len(pending)} task={task.get('ID')} f+s={row['metrics']['secure_func_sec']}", flush=True)
        return rows

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(run_one, task): task for task in pending}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            task = futures[future]
            row = future.result()
            rows.append(row)
            matrix.write_jsonl(cache_path, rows)
            if completed == len(futures) or completed % 5 == 0 or row.get("generation_errors"):
                print(
                    f"{matrix.LANGUAGE_LABELS[language]} {method['name']}: {completed}/{len(futures)} "
                    f"task={task.get('ID')} f+s={row['metrics']['secure_func_sec']} gen_errors={row.get('generation_errors')}",
                    flush=True,
                )
    return rows


def selected_methods(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.only_agents:
        return WORKFLOW_METHODS
    if args.only_traditional:
        return TRADITIONAL_METHODS
    return ALL_METHODS


def _git_commit() -> str:
    """当前 commit（拿不到就返回 unknown，不让元数据写入失败阻断实验）。"""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return (proc.stdout or "").strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def write_run_metadata(out_dir: Path, args: argparse.Namespace, methods: list[dict[str, Any]]) -> Path:
    """写 run_metadata.json。

    AGENTS.md 第三节要求每次正式 baseline 运行都保存它（commit、数据清单、模型、
    参数、Docker 镜像、输出 schema）。之前 runner 只写了 rows/summary/report，
    缺这一项，审计时无法回答"这批结果是用哪个镜像、哪组参数跑出来的"。
    只记录镜像名与参数，**不含任何密钥**。
    """
    metadata = {
        "runner": "methods/workflow_baselines/run_true_agent_workflows.py",
        "commit": _git_commit(),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": args.model,
        "credential_source": os.environ.get("CHATANYWHERE_KEY_SOURCE", "unknown"),
        "parameters": {
            "subsets": args.subsets,
            "languages": args.languages,
            "limit": args.limit,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "retries": args.retries,
            "workers": args.workers,
            "repair_iters": args.repair_iters,
            "static_rounds": args.static_rounds,
            "agentcoder_candidates": args.agentcoder_candidates,
            "agentcoder_tests": args.agentcoder_tests,
            "agentcoder_epochs": args.agentcoder_epochs,
            "ragen_iters": args.ragen_iters,
        },
        "methods": [method["name"] for method in methods],
        "docker": {
            "python_image": os.environ.get("SAFECODER_PYTHON_DOCKER_IMAGE", "safecoder-python-validator:local"),
            "cpp_image": os.environ.get("SAFECODER_CPP_DOCKER_IMAGE", "safecoder-cpp-validator:local"),
            "go_image": os.environ.get("SAFECODER_GO_DOCKER_IMAGE", "golang:1.22"),
            "pool_size": os.environ.get("SAFECODER_DOCKER_POOL_SIZE", ""),
            "cpp_backend": os.environ.get("SAFECODER_CPP_BACKEND", "local"),
            "go_backend": os.environ.get("SAFECODER_GO_BACKEND", "local"),
        },
        "output_schema": {
            "rows.jsonl": "逐任务方法、生成代码、脱敏 trace、fidelity、Function/Secure 结果与终态错误",
            "summary.json": "按方法/语言汇总的指标",
            "true_agent_workflow_report.md": "人工可读报告",
            "run_metadata.json": "本文件",
        },
    }
    path = out_dir / "run_metadata.json"
    matrix.write_json(path, metadata)
    return path


def run_subset(args: argparse.Namespace, subset: str, client: OpenAI) -> dict[str, Any]:
    # 输出根默认落到 translation_work/baseline_runs，与 AGENTS.md 第二节的
    # 目录规范一致；旧默认是 methods/workflow_baselines/out，会把运行产物
    # 写进源码目录，违反"methods/ 不放实验输出"。
    output_root = Path(
        os.environ.get(
            "AGENTFLOW_OUTPUT_ROOT",
            str(PROJECT_ROOT / "translation_work" / "baseline_runs"),
        )
    )
    out_dir = output_root / args.out_name / subset
    out_dir.mkdir(parents=True, exist_ok=True)
    methods = selected_methods(args)
    tasks_by_language = {
        language: matrix.load_language_tasks(args.dataset_root, subset, language, args.limit)
        for language in args.languages
    }
    summaries_by_language: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []
    for language in args.languages:
        summaries: list[dict[str, Any]] = []
        for method in methods:
            cache_path = out_dir / "true_agent_workflows" / language / f"{matrix.slug(method['name'])}.jsonl"
            rows = run_method_language(client, method, language, tasks_by_language[language], args, cache_path)
            all_rows.extend(rows)
            summaries.append(matrix.summarize_method(method, language, rows, include_insecure=False))
            summaries_by_language[language] = summaries
            matrix.write_json(out_dir / "summary_partial.json", summaries_by_language)
            print(f"{subset} {matrix.LANGUAGE_LABELS[language]} {method['name']} done", flush=True)
    matrix.write_jsonl(out_dir / "rows.jsonl", all_rows)
    matrix.write_json(out_dir / "summary.json", summaries_by_language)
    metadata_path = write_run_metadata(out_dir, args, methods)
    report = matrix.render_report(
        subset=subset,
        languages=args.languages,
        tasks_by_language=tasks_by_language,
        summaries_by_language=summaries_by_language,
        rows=all_rows,
        include_ours=False,
        include_insecure=False,
        only_ours=False,
    )
    report = report.replace("Language Method Matrix Report", "True Agent Workflow Matrix Report")
    report += "\n## Workflow Fidelity Note\n\n"
    report += (
        "The four traditional methods are direct prompt baselines by definition. "
        "The five agent methods use workflow-style control flow adapted from the original ZIP implementations: "
        "AutoSafeCoder uses generate/review/repair/validation feedback, AgentCoder uses multi-candidate self-test selection, "
        "RA-Gen uses planner/searcher/codegen/extractor iterations, SWE-Agent uses edit/test/repair loops, "
        "and SecAwareCoder uses analysis/test-intent/generate/execute/repair nodes. "
        "C++ and Go are workflow adaptations because the original ZIP workflows are Python/CodeSecEval-centric.\n"
    )
    report_path = out_dir / "true_agent_workflow_report.md"
    report_path.write_text(report, encoding="utf-8")
    return {
        "subset": subset,
        "report": str(report_path),
        "rows": len(all_rows),
        "out_dir": str(out_dir),
        "run_metadata": str(metadata_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, default=PROJECT_ROOT / "data" / "SecEvoBasePlus")
    parser.add_argument("--subsets", nargs="+", choices=["Base", "Plus"], default=["Base", "Plus"])
    parser.add_argument("--languages", nargs="+", choices=["python", "cpp", "go"], default=["python", "cpp", "go"])
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out-name", default="true_agent_workflows_deepseek_v32_20260918")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--repair-iters", type=int, default=2)
    parser.add_argument("--static-rounds", type=int, default=2)
    parser.add_argument("--agentcoder-candidates", type=int, default=3)
    parser.add_argument("--agentcoder-tests", type=int, default=4)
    parser.add_argument("--agentcoder-epochs", type=int, default=2)
    parser.add_argument("--ragen-iters", type=int, default=2)
    parser.add_argument("--only-agents", action="store_true")
    parser.add_argument("--only-traditional", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("SAFECODER_CPP_BACKEND", "docker")
    os.environ.setdefault("SAFECODER_GO_BACKEND", "docker")
    os.environ.setdefault("SAFECODER_PYTHON_DOCKER_IMAGE", "safecoder-python-validator:local")
    os.environ.setdefault("SAFECODER_CPP_DOCKER_IMAGE", "safecoder-cpp-validator:local")
    os.environ.setdefault("SAFECODER_GO_DOCKER_IMAGE", "golang:1.22")

    # 常驻容器池大小必须 >= 并发数，否则池耗尽会抛 RuntimeError，
    # 被 run_docker_task 折算成 environment_error，把并发配置问题伪装成环境故障。
    # 每个 spec（cpp / go-离线 / go-联网 / python）各一个池，池内并发上限即 workers。
    os.environ["SAFECODER_DOCKER_POOL_SIZE"] = str(
        max(args.workers, int(os.environ.get("SAFECODER_DOCKER_POOL_SIZE") or "0"), 1)
    )

    # 起点干净：清掉上次异常退出留下的池容器，否则它们会占着名字、
    # 让本次启动的容器改名，并挡住后续的 vhdx 压缩。
    from translation_pipeline.persistent_container import cleanup_stale_containers

    stale = cleanup_stale_containers()
    if stale:
        print(f"[preflight] 清理残留池容器: {stale}", flush=True)

    client = make_client()
    results = [run_subset(args, subset, client) for subset in args.subsets]
    print(json.dumps(results, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()

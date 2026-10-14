"""Level 4 语言叶生成器（HSK-Tree 第 4 层：多语言适配）。

所属阶段：Phase 1 seed 提取 与 Phase 2 经验提炼——两处都要产出多语言叶。
职责：调用 LLM 为一条安全不变量生成**四种语言**（python/cpp/go/java）的
    落地细节：safe_constructs（推荐安全 API/结构）、prohibited_constructs
    （禁忌写法/易断裂反模式）、pattern_snippet（最小改动范式片段）。
输入：CWE + 高级不变量 + 正向准则 + 负向红线（可选）。
输出：{language: LanguageLeaf} 字典。
验证证据：本模块只生成知识，不做动态验证；叶节点是否有用由消融实验
    A1~A6 在真实任务上的 JointPass 判定。
失败类型：LLM 输出非法 JSON → 返回空叶（记 `level4_error`），不抛异常中断主流程。
允许修改长期经验库：否——只产出候选叶，是否入树由 Phase3 门控决定。

用户拍板（Q3）：PLT 数据只有 Python，但 cpp/go/java 的叶**让 LLM 凭空生成**，
用于检验多语言迁移能力。
"""

from __future__ import annotations

import json
import re
from typing import Callable

from .ablation import LEVEL4_LANGUAGES, AblationConfig
from .hsk_tree import LanguageLeaf
from .english_policy import assert_english_experience

_LANG_LABEL = {"python": "Python", "cpp": "C++", "go": "Go", "java": "Java"}


def build_level4_prompt(*, cwe: str, invariant: str, positive: str = "",
                        negative: str = "", config: AblationConfig,
                        languages: tuple[str, ...] = LEVEL4_LANGUAGES) -> str:
    """构造 Level 4 生成提示。按 config 决定要求哪些字段（消融用）。"""
    langs = [l for l in languages if l in LEVEL4_LANGUAGES]
    want = []
    if config.gen_l4_constructs:
        want.append('"safe_constructs": ["2-4 language-specific safe APIs, libraries or constructs"]')
        want.append('"prohibited_constructs": ["2-4 prohibited or fragile language-specific constructs"]')
    if config.gen_l4_snippet:
        want.append('"pattern_snippet": "Minimal patch snippet preserving functionality, at most 10 lines"')
    if config.gen_l4_text and not want:
        want.append('"notes": "2-3 sentences on implementation considerations for this language"')
    if not want:
        want.append('"notes": "Implementation considerations for this language"')

    lang_spec = ",\n    ".join(
        f'"{l}": {{{", ".join(want)}}}' for l in langs
    )
    return (
        "You are a multilingual secure-code expert. Given a language-independent security invariant, "
        f"provide implementation details for each of the following {len(langs)} languages. Write natural-language content in English.\n\n"
        f"CWE: {cwe}\nInvariant: {invariant}\n"
        + (f"Positive repair principle: {positive}\n" if positive else "")
        + (f"Negative guardrail: {negative}\n" if negative else "")
        + "\nRequirements: \n"
        "1. Give language-specific APIs, syntax and libraries rather than generic advice.\n"
        "2. Preserve required behavior; do not recommend whole-program rewrites or empty returns.\n"
        "3. Do not include task-specific variable names, function names or answer constants.\n\n"
        f"Return only JSON with this schema: \n{{\n  {lang_spec}\n}}"
    )


def _extract_json(text: str) -> dict:
    """从 LLM 输出里抠出 JSON（容忍 ```json 围栏与前后废话）。"""
    if not text:
        return {}
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S | re.I)
    body = fenced.group(1) if fenced else text
    m = re.search(r"\{.*\}", body, re.S)
    if not m:
        return {}
    try:
        val = json.loads(m.group(0))
        return val if isinstance(val, dict) else {}
    except json.JSONDecodeError:
        return {}


def _content(resp: dict) -> str:
    return ((resp.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def generate_level4(
    *,
    cwe: str,
    invariant: str,
    positive: str = "",
    negative: str = "",
    requester: Callable[[str], dict],
    config: AblationConfig,
) -> tuple[dict[str, LanguageLeaf], str | None]:
    """为一条不变量生成多语言叶。

    返回 (leaves, error)：
      - config 未开启任何 L4 生成 → 返回 ({}, None)（消融 A1/A2 走这条）
      - LLM 输出无法解析 → 返回 ({}, "level4_parse_error")
    """
    if not config.has_level4:
        return {}, None
    try:
        prompt = build_level4_prompt(cwe=cwe, invariant=invariant, positive=positive,
                                     negative=negative, config=config,
                                     languages=config.languages)
        value = _extract_json(_content(requester(prompt)))
        assert_english_experience(value)
    except Exception as exc:
        return {}, type(exc).__name__
    if not value:
        return {}, "level4_parse_error"

    leaves: dict[str, LanguageLeaf] = {}
    for lang in config.languages:
        raw = value.get(lang)
        if not isinstance(raw, dict):
            continue
        notes = str(raw.get("notes") or "")
        safe = [str(x) for x in (raw.get("safe_constructs") or []) if str(x).strip()]
        prohibited = [str(x) for x in (raw.get("prohibited_constructs") or []) if str(x).strip()]
        snippet = str(raw.get("pattern_snippet") or "")
        # 文本模式下把 notes 折进 safe_constructs 的展示位，保证"文本 L4"也能被注入
        if config.gen_l4_text and notes and not safe:
            safe = [notes]
        leaf = LanguageLeaf(language=lang, safe_constructs=safe,
                            prohibited_constructs=prohibited, pattern_snippet=snippet)
        if leaf.has_content():
            leaves[lang] = leaf
    return leaves, (None if leaves else "level4_empty")


def render_level4_for_injection(leaves: dict[str, LanguageLeaf], *,
                                language: str, config: AblationConfig) -> str:
    """把命中节点的语言叶渲染成注入给 Planning/CodeGen 的文本。

    按 config 的 inject_* 开关决定暴露哪些字段（消融用：生成≠注入）。
    语言不匹配时回退到 python 叶并明确标注，避免"没有叶就静默不注入"。
    """
    if not leaves or not config.has_level4:
        return ""
    leaf = leaves.get(language)
    fallback = False
    if leaf is None:
        leaf = leaves.get("python")
        fallback = leaf is not None
    if leaf is None:
        return ""
    parts: list[str] = []
    if config.inject_l4_constructs and leaf.safe_constructs:
        parts.append(f"Recommended constructs ({leaf.language}): " + "; ".join(leaf.safe_constructs[:4]))
    if config.inject_l4_constructs and leaf.prohibited_constructs:
        parts.append(f"Prohibited constructs ({leaf.language}): " + "; ".join(leaf.prohibited_constructs[:4]))
    if config.inject_l4_snippet and leaf.pattern_snippet.strip():
        parts.append(f"Example snippet ({leaf.language}): \n{leaf.pattern_snippet.strip()[:600]}")
    if not parts:
        return ""
    head = f"[Level 4 language adaptation: {leaf.language}]"
    if fallback:
        head += f"[No leaf for target {language}; fallback to Python leaf]"
    return head + "\n" + "\n".join(parts)

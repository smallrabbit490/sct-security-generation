"""定义冻结 CLE 评测的 prompt 变体。

本模块只负责确定性渲染，不读取测试反馈，也不修改冻结经验库。few-shot 示例是
固定的通用示例，不来自 Base/Plus/H_pass，避免把测试答案泄漏到 prompt。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PromptProfile:
    profile_id: str
    family: str
    description: str
    instructions: tuple[str, ...] = ()
    fewshot: tuple[str, ...] = ()
    card_fields: tuple[str, ...] = ("principle", "applicability", "negative_guardrail")
    hide_cards: bool = False
    hide_retrieval: bool = False
    role: str = ""


GENERIC_FEWSHOT = (
    "Example (synthetic, not from evaluation data). Task: implement is_ascii_letter(value: str) -> bool; "
    "accept exactly one ASCII letter. Output: def is_ascii_letter(value: str) -> bool:\n"
    "    return len(value) == 1 and ('A' <= value <= 'Z' or 'a' <= value <= 'z')",
)
THREE_FEWSHOT = GENERIC_FEWSHOT + (
    "Example (synthetic). Task: allow operation only when role is editor; return bool. Output: "
    "def may_edit(role: str) -> bool:\n    return role == 'editor'",
    "Example (synthetic). Task: parse a decimal count; malformed input raises ValueError. Output: "
    "def parse_count(text: str) -> int:\n    value = int(text)\n    if value < 0:\n"
    "        raise ValueError('negative count')\n    return value",
)
SAFE_COUNTEREXAMPLE = (
    "Counterexample: a function can pass a security check while breaking functionality by returning None "
    "instead of the required value. Preserve the functional contract and repair only the security defect.",
)
SECURITY_COUNTEREXAMPLE = (
    "Counterexample: a function can satisfy ordinary examples while leaving an unsafe eval/exec or shell "
    "operation reachable from untrusted input. Preserve valid behavior while closing the attack path.",
)


def _p(profile_id: str, family: str, description: str, **kwargs) -> PromptProfile:
    return PromptProfile(profile_id, family, description, **kwargs)


PROFILES: dict[str, PromptProfile] = {
    "P00": _p("P00", "baseline", "Current frozen-evaluation generation prompt"),
    "P01": _p("P01", "fewshot", "One generic positive example", fewshot=GENERIC_FEWSHOT),
    "P02": _p("P02", "fewshot", "Three generic positive examples", fewshot=THREE_FEWSHOT),
    "P03": _p("P03", "fewshot", "Function-preservation counterexample", fewshot=GENERIC_FEWSHOT + (SAFE_COUNTEREXAMPLE,)),
    "P04": _p("P04", "fewshot", "Security counterexample", fewshot=GENERIC_FEWSHOT + (SECURITY_COUNTEREXAMPLE,)),
    "P05": _p("P05", "fewshot", "Positive and negative examples", fewshot=THREE_FEWSHOT[:1] + (SAFE_COUNTEREXAMPLE, SECURITY_COUNTEREXAMPLE)),
    "P06": _p("P06", "cards", "Principle only", card_fields=("principle",)),
    "P07": _p("P07", "cards", "Principle and applicability", card_fields=("principle", "applicability")),
    "P08": _p("P08", "cards", "Principle and negative guardrail", card_fields=("principle", "negative_guardrail")),
    "P09": _p("P09", "cards", "Applicability decision before adoption", instructions=("First decide whether each supplied experience applies; use only applicable guidance and explain no decision in code.",)),
    "P10": _p("P10", "contract", "Explicit callable contract", instructions=("Treat the function name, parameters, return value and exception behavior as a strict contract.",)),
    "P11": _p("P11", "contract", "Preserve valid behavior", instructions=("Do not change behavior for valid inputs that satisfy the task contract.",)),
    "P12": _p("P12", "contract", "Security surface checklist", instructions=("Check untrusted inputs, sensitive operations, trigger conditions and postconditions before coding.",)),
    "P13": _p("P13", "contract", "Function and security checklist", instructions=("Preserve valid behavior. Check untrusted inputs, sensitive operations, trigger conditions and postconditions.",)),
    "P14": _p("P14", "reasoning", "Private pre-output check", instructions=("Before emitting code, privately check contract preservation, security coverage and output syntax.",)),
    "P15": _p("P15", "reasoning", "Experience applicability check", instructions=("Before using an experience card, check its applicability and exclusion conditions against this task.",)),
    "P16": _p("P16", "output", "Strict code-only output", instructions=("Return only runnable Python code. Do not include Markdown fences, explanations, tests or headings." ,)),
    "P17": _p("P17", "output", "Minimal change", instructions=("Use the smallest implementation change that satisfies the complete task contract and security requirement.",)),
    "P18": _p("P18", "role", "Security reviewed implementation engineer", role="You are an implementation engineer whose code has already passed a security review."),
    "P19": _p("P19", "role", "Strict Python library author", role="You are a strict Python library author responsible for preserving a published callable contract."),
    "P20": _p("P20", "combination", "Three examples, applicability and dual checklist", fewshot=THREE_FEWSHOT, instructions=("Use only applicable experience. Preserve valid behavior and check the full security surface.",)),
    "P21": _p("P21", "combination", "Positive/negative examples, applicability and output", fewshot=THREE_FEWSHOT[:1] + (SAFE_COUNTEREXAMPLE, SECURITY_COUNTEREXAMPLE), instructions=("Check experience applicability before use.", "Return only runnable Python code; no Markdown or explanation.")),
    "P22": _p("P22", "combination", "Examples, contract, security and minimal change", fewshot=THREE_FEWSHOT, instructions=("Do not change valid behavior.", "Check untrusted inputs and sensitive operations.", "Use the smallest necessary change.")),
    "P23": _p("P23", "control", "Same structure without experience content", hide_cards=True),
    "P24": _p("P24", "control", "Experience library present but retrieval hidden", hide_retrieval=True),
}


def profile_payload(profile: PromptProfile) -> dict:
    return asdict(profile)


def profile_sha256(profile: PromptProfile) -> str:
    raw = json.dumps(profile_payload(profile), ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def render_cards(cards: list[dict], profile: PromptProfile) -> str:
    if profile.hide_cards:
        return "[Experience content intentionally omitted for this control profile]"
    if profile.hide_retrieval:
        return "[Retrieved experience withheld for this control profile]"
    compact = []
    for card in cards:
        compact.append({"invariant_id": card.get("invariant_id") or card.get("id"), **{
            field: str(card.get(field) or "") for field in profile.card_fields
        }})
    return json.dumps(compact, ensure_ascii=False)


def render_generation_prompt(base_prompt: str, cards: list[dict], profile: PromptProfile) -> str:
    """在已有冻结生成 prompt 末尾注入一个可审计的变体块。"""
    if profile.profile_id == "P00":
        return base_prompt
    parts = [base_prompt]
    if profile.role:
        parts.append("Prompt role:\n" + profile.role)
    if profile.instructions:
        parts.append("Prompt variant instructions:\n" + "\n".join(f"- {x}" for x in profile.instructions))
    if profile.fewshot:
        parts.append("Fixed generic examples:\n" + "\n".join(f"- {x}" for x in profile.fewshot))
    parts.append("Retrieved experience for this variant:\n" + render_cards(cards, profile))
    return "\n\n".join(parts)


def get_profile(profile_id: str) -> PromptProfile:
    try:
        return PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"unknown prompt profile: {profile_id}") from exc

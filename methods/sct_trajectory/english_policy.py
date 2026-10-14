"""CLE 英文自然语言准入策略；不改写代码、证据、来源标识或原始库。

所属阶段：提炼后及入库前；输入结构化经验，输出独立副本或明确的语言错误。
只做文字脚本约束，不声称证明语言学意义上的英文或经验真实性，不运行验证。
翻译必须由显式 translator 提供，且只能修改白名单自然语言字段；本模块不写长期库。
"""
from __future__ import annotations

import copy
import re
from typing import Callable

_CJK = re.compile(r'[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]')
PROSE_FIELDS = frozenset({
    'high_level_invariant', 'positive_principle', 'negative_guardrail', 'applicability',
    'principle', 'forbidden_patterns', 'root_cause', 'fix_directive', 'prev_fix_assessment',
    'attribution', 'blind_spot', 'minimal_patch_hint', 'overdefense_pitfall',
    'safe_constructs', 'prohibited_constructs', 'notes', 'level4_text',
    'cognitive_blind_spot', 'recommended_fix', 'avoidance_rule',
    'recommended_action', 'dangerous_pattern', 'unsafe_alternative',
    'non_applicable_boundary', 'exclusion_conditions', 'language_adaptation',
    'trigger_context', 'security_invariant',
})
_OPAQUE = frozenset({'code', 'code_before', 'code_after', 'source_code', 'pattern_snippet',
                     'evidence', 'evidence_manifest', 'task_contract', 'trace', 'patch_diff',
                     'generated_codes', 'raw_response', 'tests', 'test_cases'})


class EnglishPolicyError(ValueError):
    """英文准入失败；异常只含字段路径及原因，不输出任务或敏感原文。"""


def contains_cjk(value: str) -> bool:
    """准入检查：检测汉字，不处理代码语义或修改长期经验；非汉字不等于已证明英文。"""
    return bool(_CJK.search(str(value)))


def assert_english_text(value: str, *, context: str = 'text') -> None:
    """准入边界：自然语言含汉字即拒绝；调用方不能把代码、证据作为待改写文本。"""
    if contains_cjk(value):
        raise EnglishPolicyError(f'non_english_natural_language:{context}')


def experience_prose_fields(value: dict) -> dict[str, str]:
    """提炼后：枚举白名单自然语言 JSON 路径，排除代码/原始证据；不写入库。"""
    out = {}
    def walk(node, path='', prose=False):
        if isinstance(node, dict):
            for key, item in node.items():
                if key in _OPAQUE:
                    continue
                token = str(key).replace('~', '~0').replace('/', '~1')
                # track_rules 中 text 是知识描述，其余任意 text 不自动视为可翻译。
                selected = prose or key in PROSE_FIELDS or (key == 'text' and '/track_rules/' in path)
                walk(item, f'{path}/{token}', selected)
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f'{path}/{index}', prose)
        elif prose and isinstance(node, str):
            out[path] = node
    walk(value)
    return out


def assert_english_experience(value: dict) -> None:
    """入库前：校验所有已知经验文字，失败抛路径错误；不执行动态验证、不修改库。"""
    for path, text in experience_prose_fields(value).items():
        assert_english_text(text, context=path)


def normalize_experience(value: dict, *, translator: Callable[[dict[str, str]], dict[str, str]] | None = None) -> dict:
    """迁移/入库：仅显式翻译含汉字的白名单字段，保留来源及代码；失败不产生半成品。

    translator 输入/输出都必须为完全一致的路径集合，不能新增/丢失字段或输出空译文。
    调用方负责对照原文审计事实守恒；通过本函数仅证明脚本约束，不证明翻译准确。
    """
    result = copy.deepcopy(value)
    fields = {path: text for path, text in experience_prose_fields(result).items() if contains_cjk(text)}
    if not fields:
        return result
    if translator is None:
        raise EnglishPolicyError('english_translation_required')
    translated = translator(dict(fields))
    if not isinstance(translated, dict) or set(translated) != set(fields):
        raise EnglishPolicyError('translation_field_set_mismatch')
    for path, text in translated.items():
        if not isinstance(text, str) or not text.strip():
            raise EnglishPolicyError('empty_or_invalid_translation')
        assert_english_text(text, context=path)
        tokens = [token.replace('~1', '/').replace('~0', '~') for token in path.split('/')[1:]]
        node = result
        for token in tokens[:-1]:
            node = node[int(token)] if isinstance(node, list) else node[token]
        token = tokens[-1]
        if isinstance(node, list):
            node[int(token)] = text
        else:
            node[token] = text
    assert_english_experience(result)
    return result

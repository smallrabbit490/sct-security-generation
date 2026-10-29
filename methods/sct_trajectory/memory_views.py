"""固定经验的功能/安全呈现视图，供冻结库开发对照消费。

只按已审核字符片段重组现有卡片，不创造建议、不读取任务答案、不更新经验或Q。
默认BM保留原CLE输入；B0整轮不注入经验。片段缺失或未审核属于配置错误。
"""
from __future__ import annotations

import copy
import json

MODES = ('B0', 'BF', 'BS', 'BFS', 'BM')
VIEW_FIELD = '_cle_memory_view'
METADATA_FIELDS = ('invariant_id', 'kind', 'status', 'support_count', 'regression_count')


def _leaves(value, path=()):
    """枚举正文的所有标量叶子，覆盖语言子卡，避免嵌套正文绕过分组。"""
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _leaves(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _leaves(child, (*path, index))
    elif value not in (None, '', 'not provided'):
        yield path, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def source_projection(card):
    """使用实际CLE白名单取得原呈现对象；不把运行期视图再次当成来源。"""
    from .context_pipeline import experience_text
    original = {key: value for key, value in card.items() if key != VIEW_FIELD}
    return json.loads(experience_text([original]))[0]


def draft_view(card):
    """导出待审核片段，pending不是自动生成的功能/安全标签。"""
    source = source_projection(card)
    body = {key: value for key, value in source.items() if key not in METADATA_FIELDS}
    return {'card_id': source['invariant_id'], 'review_status': 'pending',
        'segments': [{'path': list(path), 'start': 0, 'end': len(text), 'role': 'pending'}
                     for path, text in _leaves(body)], 'review_note': ''}


def render_view(source, specification, mode):
    """验证来源片段完整分区后渲染；范围/角色错误停止，不静默丢句或改写事实。"""
    if mode not in ('BF', 'BS', 'BFS'):
        raise ValueError('view_render_mode_not_supported')
    if specification['review_status'] != 'reviewed':
        raise ValueError('memory_view_not_reviewed')
    if specification['card_id'] != source['invariant_id']:
        raise ValueError('memory_view_card_id_mismatch')
    body = {key: value for key, value in source.items() if key not in METADATA_FIELDS}
    leaves = dict(_leaves(body))
    partition = {path: [] for path in leaves}
    for segment in specification['segments']:
        path = tuple(segment['path'])
        if path not in partition or segment['role'] not in ('functional', 'security', 'context'):
            raise ValueError('memory_view_path_or_role_invalid')
        partition[path].append(segment)
    grouped = {'functional': [], 'security': [], 'context': []}
    for path, text in leaves.items():
        cursor = 0
        for segment in sorted(partition[path], key=lambda s: s['start']):
            start, end = segment['start'], segment['end']
            if type(start) is not int or type(end) is not int or start != cursor or not start < end <= len(text):
                raise ValueError('memory_view_source_not_exactly_partitioned')
            grouped[segment['role']].append({'source_path': list(path), 'text': text[start:end]})
            cursor = end
        if cursor != len(text):
            raise ValueError('memory_view_source_not_exactly_partitioned')
    rendered = {key: source[key] for key in METADATA_FIELDS}
    rendered['applicability_and_source_context'] = grouped['context']
    if mode in ('BF', 'BFS'):
        rendered['functional_preservation'] = grouped['functional']
    if mode in ('BS', 'BFS'):
        rendered['security_action'] = grouped['security']
    return rendered


def apply_memory_view(cards, mode, specifications=None):
    """在原选卡之后创建只读运行期视图，采用ID和原始正文仍可追溯。"""
    if mode not in MODES:
        raise ValueError('unknown_memory_view_mode')
    if mode == 'B0':
        return []
    if mode == 'BM':
        return [copy.deepcopy({k: v for k, v in card.items() if k != VIEW_FIELD}) for card in cards]
    result = []
    for card in cards:
        source = source_projection(card)
        # 来源卡和选入ID不变；私有payload只有experience_text显式识别后才被注入。
        payload = render_view(source, specifications[source['invariant_id']], mode)
        result.append({**copy.deepcopy(card), VIEW_FIELD: payload})
    return result

"""已观测中转故障的局部适配：不改模型、提示词、选卡或P7交付规则。"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from methods.cle_ablation.run_joint_contract import RequestBudget
from methods.sct_trajectory.agent_pipeline import _content, _extract_json
from methods.sct_trajectory.selector_protocol import SelectorPrompt

VERSION = 'cle-provider-adaptation-v2'
TRANSPORT = {'socket_timeout': 180, 'hard_timeout': 210,
             'gate_wait_timeout': 420, 'max_attempts': 1, 'max_inflight': 1}
STREAM_TRANSPORT = {**TRANSPORT, 'hard_timeout':300, 'gate_wait_timeout':600, 'stream':True}


def normalize_structured_response(prompt, response):
    """只合并分析/规划中完整、相邻且顶层字段互斥的JSON；原始响应由调用者保存。"""
    if isinstance(prompt, SelectorPrompt) or not str(prompt).startswith((
            'Perform ', 'Plan the implementation.', 'You are a security and functional-contract analyst.')):
        return response, None
    text = _content(response)
    try:
        _extract_json(text)
        return response, None
    except json.JSONDecodeError as exc:
        if exc.msg != 'Extra data':
            return response, None
    candidate = text.strip()
    fence = re.fullmatch(r'```(?:json)?\s*\n?(.*?)\s*```', candidate, re.S | re.I)
    if fence:
        candidate = fence.group(1).strip()
    decoder, merged, count, position = json.JSONDecoder(), {}, 0, 0
    while position < len(candidate):
        try:
            value, end = decoder.raw_decode(candidate, position)
        except json.JSONDecodeError:
            return response, None
        if not isinstance(value, dict) or not value or merged.keys() & value.keys():
            return response, None
        merged.update(value)
        count += 1
        position = end
        while position < len(candidate) and candidate[position].isspace():
            position += 1
    if count < 2:
        return response, None
    result = copy.deepcopy(response)
    result['choices'][0]['message']['content'] = json.dumps(merged, ensure_ascii=False)
    return result, {'kind': 'merge_adjacent_disjoint_json_objects', 'object_count': count,
                    'keys': list(merged), 'invented_fields': 0}


def carried_budget(execution, snapshots):
    """新协议沿用旧故障和诊断已占额度，不把失败费用清零；快照由本运行区提供。"""
    budget = RequestBudget(execution['max_http_attempts'], execution['max_conservative_tokens'],
                           execution['max_embedding_attempts'])
    for snapshot in snapshots:
        budget.records.extend(copy.deepcopy(snapshot['records']))
        budget.reserved_calls += snapshot['reserved_http_attempts']
        budget.reserved_tokens += snapshot['reserved_token_bound']
        budget.reserved_embedding_calls += snapshot['reserved_embedding_http_attempts']
    if (budget.reserved_calls > budget.max_calls or budget.reserved_tokens > budget.max_tokens
            or budget.reserved_embedding_calls > budget.max_embedding_calls):
        raise ValueError('previous_protocol_already_exceeded_budget')
    return budget


def exact_saved_response(prompt, source: Path, cell_id):
    """仅复用同一实验格、完整相同提示词的已返回正文；未决/失败请求不冒充返回。"""
    for path in sorted((source / 'requests').glob('*.prompt.txt')):
        status_path = path.with_suffix('').with_suffix('.status.json')
        response_path = path.with_suffix('').with_suffix('.response.json')
        status = json.loads(status_path.read_text(encoding='utf-8'))
        if (status['status'] == 'returned' and status['cell_id'] == cell_id
                and response_path.exists() and path.read_text(encoding='utf-8') == str(prompt)):
            return json.loads(response_path.read_text(encoding='utf-8')), str(response_path)
    return None, None

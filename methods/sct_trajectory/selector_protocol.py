"""检索选择阶段的请求预算与严格协议；不执行验证、不修改长期经验库。"""
import json
import math
import time


class SelectorPrompt(str):
    """透传现有用量包装器的字符串请求，附带本次选择的共同截止时间。

    输入英文提示与单调时钟截止时间；真实请求器限制排队、HTTP 和总重试。
    不创建额外后台执行器；超时 HTTP 仍由真实请求器占据共享并发槽。
    """
    def __new__(cls, value, *, deadline):
        instance = super().__new__(cls, value)
        instance.deadline = deadline
        return instance


class SelectorProtocolError(ValueError):
    """选择输出不符合封闭协议；消息仅含内部类别，无模型原文。"""


def safe_request_diagnostics(exc):
    """筛选错误审计仅复制白名单数字/枚举；拒绝第三方原文、URL、非有限时间。"""
    result = []
    values = getattr(exc, 'safe_diagnostics', [])
    if not isinstance(values, list):
        return result
    for item in values[:3]:
        if not isinstance(item, dict) or not isinstance(item.get('category'), str) or item['category'] not in {
                'http_error', 'network_error', 'hard_timeout', 'gate_wait_timeout',
                'selector_gate_wait_timeout', 'circuit_open', 'selector_deadline_exceeded'}:
            continue
        clean = {'category': item['category']}
        for key in ('attempt', 'http_status', 'elapsed_s', 'wait_s'):
            value = item.get(key)
            if type(value) in (int, float) and 0 <= value <= 1e9 and math.isfinite(value):
                clean[key] = value
        result.append(clean)
    return result


def parse_selection(response, candidate_count, limit, diagnostics):
    """筛选阶段严格读取短编号；输出有序列表，格式/重复/越界/截断均拒绝。

    只验证输出结构，不把模型选择当动态正确性证据；不改卡片或经验库。
    """
    import hashlib
    try:
        choice = response['choices'][0]
        content = choice['message']['content']
        finish = choice.get('finish_reason')
        if not isinstance(content, str):
            raise TypeError()
    except (KeyError, IndexError, TypeError):
        raise SelectorProtocolError('selector_invalid_response') from None
    diagnostics.update(finish_reason=finish, content_length=len(content),
        content_sha256=hashlib.sha256(content.encode('utf8')).hexdigest())
    if finish == 'length':
        raise SelectorProtocolError('selector_output_truncated')
    if finish not in (None, 'stop'):
        raise SelectorProtocolError('selector_unexpected_finish')
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise SelectorProtocolError('selector_duplicate_json_key')
            value[key] = item
        return value
    try:
        value = json.loads(content, object_pairs_hook=unique_object)
    except json.JSONDecodeError as exc:
        diagnostics['parse'] = {'reason': exc.msg, 'line': exc.lineno, 'column': exc.colno}
        raise SelectorProtocolError('selector_invalid_json') from None
    if not isinstance(value, dict) or set(value) != {'selected'}:
        raise SelectorProtocolError('selector_invalid_schema')
    selected = value['selected']
    if not isinstance(selected, list) or len(selected) > limit:
        raise SelectorProtocolError('selector_invalid_selection_count')
    if any(type(identifier) is not int for identifier in selected):
        raise SelectorProtocolError('selector_invalid_id_type')
    if len(set(selected)) != len(selected):
        raise SelectorProtocolError('selector_duplicate_id')
    if any(identifier < 1 or identifier > candidate_count for identifier in selected):
        raise SelectorProtocolError('selector_unknown_id')
    return selected


def select_with_retry(prompt, requester, candidate_count, limit, trace):
    """筛选阶段最多两次格式尝试，共享 120 秒请求预算，运输失败立即返回错误。

    每次响应只留哈希、长度、结构错误与用量，不保存原始长响应；失败不兜底选卡。
    截止时间由生产请求器执行，自定义调用方也必须提供有界请求器。不更新长期库。
    """
    deadline = time.monotonic() + 120.0
    trace['selector_attempts'] = []
    for attempt in range(2):
        started = time.monotonic()
        record = {'attempt': attempt + 1}
        trace['selector_attempts'].append(record)
        if started >= deadline:
            record['error'] = 'selector_deadline_exceeded'
            break
        current = prompt
        if attempt:
            current += ('\nFORMAT RETRY: Your previous response did not satisfy the schema. '
                'Return exactly one JSON object with only the selected key and integer candidate IDs. '
                'No explanations, rejected list, Markdown, duplicate IDs, or extra keys.')
        try:
            response = requester(SelectorPrompt(current, deadline=deadline))
        except Exception as exc:
            record.update(error='selector_transport_' + type(exc).__name__,
                elapsed_seconds=time.monotonic() - started, usage=None,
                request_diagnostics=safe_request_diagnostics(exc))
            break
        # 解析失败仍消耗 tokens；在验证 JSON 之前记录提供方已报告用量。
        usage = response.get('usage') if isinstance(response, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        fields = ('prompt_tokens', 'completion_tokens', 'total_tokens')
        record['usage'] = {key: usage[key] for key in fields
            if type(usage.get(key)) is int and usage[key] >= 0}
        record['missing_usage_fields'] = [key for key in fields if key not in record['usage']]
        try:
            selected = parse_selection(response, candidate_count, limit, record)
            record.update(status='completed', elapsed_seconds=time.monotonic() - started)
            trace['recovered_after_retry'] = attempt > 0
            return selected
        except SelectorProtocolError as exc:
            record.update(error=str(exc), elapsed_seconds=time.monotonic() - started)
    raise SelectorProtocolError(record['error'])

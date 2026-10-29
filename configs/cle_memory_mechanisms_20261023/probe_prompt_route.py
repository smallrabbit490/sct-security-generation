"""最多三次原始HTTP诊断消息/路由，保存实际正文和原始流；不调用CLE解题流程。"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .prepare import CONFIG, OUT, read, write
from methods.cle_ablation.provider_adaptation import carried_budget
from methods.sct_lifecycle_replay.chatanywhere_smoke import load_key
from methods.sct_trajectory.agent_pipeline import strip_code_fence
from methods.sct_trajectory.internal_checks import execute_checks


ORIGINAL = 'Write a Python function add(a, b) that returns a + b. Output only the function code.'
CONTROLS = [
    ('fresh_code_user', [{'role': 'user', 'content':
        'Return a Python implementation of sum_pair_20261024(a, b), which returns a + b.'}],
     'sum_pair_20261024'),
    ('system_then_original_code', [{'role': 'system', 'content': 'You are a helpful assistant.'},
        {'role': 'user', 'content': ORIGINAL}], 'add'),
    ('plain_arithmetic_user', [{'role': 'user', 'content': 'What is 17 + 25?'}], None),
]


def main():
    """同密钥同模型；拒绝重定向，不记录认证，不因内容拒绝而重复调用。"""
    destination = OUT / 'provider_prompt_route_investigation_20261024'
    if not (destination / 'model_metadata.json').exists():
        raise ValueError('read_only_model_metadata_required')
    if (destination / 'summary.json').exists():
        raise FileExistsError('diagnostic_already_dispatched_no_automatic_repeat')
    previous = OUT / 'B02_provider_user_agent_code_control_v6' / 'cost.json'
    budget = carried_budget(read(CONFIG / 'view_protocol.json')['two_task_P7_execution'], [read(previous)])
    baseline = budget.snapshot()
    summary = {'protocol': 'cle-provider-prompt-route-diagnosis-v7', 'status': 'prepared',
        'authorization': '2026-10-24 user requested investigation of upstream prompt injection or mapping; formal experiments paused',
        'started_utc': datetime.now(timezone.utc).isoformat(), 'max_HTTP_attempts': 3,
        'model': 'deepseek-v3.2', 'endpoint': 'https://api.chatanywhere.org/v1/chat/completions',
        'user_agent': 'CLE-HTTP-Diagnostic/1.0', 'controls': [], 'P7_started': False,
        'Q_updates': 0, 'previous_cost': str(previous), 'automatic_retries': 0}
    write(destination / 'summary.json', summary)
    key = load_key()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect())
    for number, (name, messages, entry) in enumerate(CONTROLS, 1):
        payload = {'model': 'deepseek-v3.2', 'messages': messages, 'temperature': 0,
                   'max_tokens': 128, 'thinking': {'type': 'disabled'}, 'stream': True,
                   'stream_options': {'include_usage': True}}
        body = json.dumps(payload).encode('utf-8')
        # 落盘的是实际发送的正文；认证只在内存加入，不写入请求或流文件。
        (destination / f'{number}.request.json').write_bytes(body)
        item = {'number': number, 'name': name, 'status': 'submitted',
                'started_utc': datetime.now(timezone.utc).isoformat(),
                'message_roles': [m['role'] for m in messages],
                'public_content_characters': sum(len(m['content']) for m in messages)}
        summary['controls'].append(item)
        record = budget.reserve('chat', body.decode(), attempts=1, completion_cap=128)
        record.update(source_protocol=summary['protocol'], purpose=name)
        write(destination / 'summary.json', summary)
        write(destination / 'cost.json', budget.snapshot())
        print(json.dumps({'control': number, 'name': name, 'status': 'submitted'}), flush=True)
        start = time.monotonic()
        chunks, response = [], {'content': '', 'usage': None, 'finish_reason': None}
        try:
            request = urllib.request.Request(summary['endpoint'], data=body, method='POST', headers={
                'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
                'User-Agent': summary['user_agent']})
            with opener.open(request, timeout=180) as http:
                item['http_status'] = http.status
                safe_headers = ['Content-Type', 'Server', 'Date', 'CF-Ray', 'CF-Cache-Status',
                    'Age', 'Cache-Control', 'X-Cache', 'X-Request-Id', 'X-Upstream-Model',
                    'X-Model', 'X-Provider']
                item['headers'] = {h: http.headers.get(h) for h in safe_headers if http.headers.get(h)}
                cert = http.fp.raw._sock.getpeercert()
                item['tls_issuer'] = [[list(x) for x in part] for part in cert.get('issuer', [])]
                item['tls_subject'] = [[list(x) for x in part] for part in cert.get('subject', [])]
                with (destination / f'{number}.stream.txt').open('x', encoding='utf-8') as stream:
                    for line in http:
                        text = line.decode('utf-8')
                        stream.write(text.replace(key, '[REDACTED]'))
                        stream.flush()
                        if not text.startswith('data:'):
                            continue
                        data = text[5:].strip()
                        if data == '[DONE]':
                            break
                        chunk = json.loads(data)
                        chunks.append(chunk)
                        if chunk.get('error'):
                            raise ValueError('provider_stream_error')
                        for k in ('id', 'created', 'model', 'system_fingerprint'):
                            if k in chunk:
                                response[k] = chunk[k]
                        if chunk.get('usage'):
                            response['usage'] = chunk['usage']
                        for choice in chunk.get('choices', []):
                            response['content'] += choice.get('delta', {}).get('content') or ''
                            if choice.get('finish_reason') is not None:
                                response['finish_reason'] = choice['finish_reason']
            if response['finish_reason'] is None:
                raise ValueError('incomplete_stream')
            item.update(status='returned', response=response, stream_chunks=len(chunks))
            record.update(status='returned', usage=response['usage'], model=response.get('model'))
            write(destination / f'{number}.response.json', response)
            if entry:
                cases = {'source': 'self_generated_internal', 'cases': [
                    {'id': 'positive', 'kind': 'functional', 'purpose': 'Add two integers',
                     'code': 'assert candidate(2, 3) == 5'},
                    {'id': 'signed', 'kind': 'functional', 'purpose': 'Add signed integers',
                     'code': 'assert candidate(-2, 2) == 0'}]}
                checked = execute_checks(strip_code_fence(response['content']), entry, cases)
                write(destination / f'{number}.validation.json', checked)
                item['code_validation'] = {k: checked[k] for k in ('measured_count', 'passed')}
        except Exception as exc:
            item.update(status='failed', error_type=type(exc).__name__)
            if isinstance(exc, urllib.error.HTTPError):
                item['http_status'] = exc.code
            if record['status'] != 'returned':
                record.update(status='failed', error_type=type(exc).__name__)
        item['elapsed_seconds'] = round(time.monotonic() - start, 3)
        write(destination / 'summary.json', summary)
        write(destination / 'cost.json', budget.snapshot())
        print(json.dumps(item, ensure_ascii=False), flush=True)
        if item['status'] != 'returned':
            break
    summary.update(status='completed_diagnostics' if len(summary['controls']) == 3 and
        all(c['status'] == 'returned' for c in summary['controls']) else 'stopped_technical_error',
        finished_utc=datetime.now(timezone.utc).isoformat(),
        new_HTTP_attempts=budget.reserved_calls - baseline['reserved_http_attempts'],
        new_known_returned_tokens=budget.snapshot()['known_returned_tokens'] - baseline['known_returned_tokens'])
    write(destination / 'summary.json', summary)
    print(json.dumps({'status': summary['status'], 'new_HTTP_attempts': summary['new_HTTP_attempts'],
                     'new_known_returned_tokens': summary['new_known_returned_tokens']}), flush=True)


if __name__ == '__main__':
    main()

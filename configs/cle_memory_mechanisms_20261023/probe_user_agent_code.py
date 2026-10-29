"""用户单独授权的一次客户端修正代码控制；不启动P7或Q学习，不重试。"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from .prepare import CONFIG, OUT, read, write
from methods.cle_ablation.provider_adaptation import carried_budget, STREAM_TRANSPORT
from methods.sct_trajectory.agent_pipeline import _content, strip_code_fence
from methods.sct_trajectory.internal_checks import execute_checks
from methods.sct_trajectory.run_closed_loop import _requester


def main():
    """沿用原控制的模型/正文/参数；最多一次HTTP，先落盘，再调用及本地验证。"""
    config = read(CONFIG / 'view_protocol.json')
    destination = OUT / 'B02_provider_user_agent_code_control_v6'
    destination.mkdir(exist_ok=False)
    previous = OUT / 'B02_provider_org_control_v5' / 'cost.json'
    budget = carried_budget(config['two_task_P7_execution'], [read(previous)])
    baseline = budget.snapshot()
    endpoint = 'https://api.chatanywhere.org/v1/chat/completions'
    prompt = 'Write a Python function add(a, b) that returns a + b. Output only the function code.'
    result = {
        'protocol': 'cle-provider-user-agent-code-control-v6', 'status': 'prepared',
        'authorization': '2026-10-24 user authorized one minimal code test after client identification fix; formal experiments remain paused',
        'model': 'deepseek-v3.2', 'thinking': 'disabled', 'temperature': 0,
        'max_tokens': 128, 'stream': True, 'endpoint': endpoint,
        'user_agent': 'CLE-HTTP-Diagnostic/1.0', 'max_HTTP_attempts': 1,
        'credential': 'same existing loader and resolution order; value never exported',
        'previous_cost': str(previous), 'P7_started': False, 'Q_updates': 0,
        'started_utc': datetime.now(timezone.utc).isoformat(), 'controls': [],
    }
    write(destination / 'summary.json', result)
    write(destination / 'cost.json', baseline)
    (destination / '1.prompt.txt').write_text(prompt, encoding='utf-8')
    native = _requester('deepseek-v3.2', STREAM_TRANSPORT['socket_timeout'],
        max_tokens=128, thinking='disabled', max_inflight=1, max_attempts=1,
        hard_timeout=STREAM_TRANSPORT['hard_timeout'],
        gate_wait_timeout=STREAM_TRANSPORT['gate_wait_timeout'], stream=True, endpoint=endpoint)

    def submit(text):
        write(destination / 'cost.json', budget.snapshot())
        return native(text)

    request = budget.wrap(submit, 128, max_attempts=1)
    item = {'number': 1, 'kind': 'code', 'status': 'submitted',
            'submitted_utc': datetime.now(timezone.utc).isoformat()}
    result['controls'].append(item)
    result['status'] = 'submitted'
    write(destination / 'summary.json', result)
    print(json.dumps({'status': 'submitted', 'max_HTTP_attempts': 1}), flush=True)
    before, start = len(budget.records), time.monotonic()
    try:
        response = request(prompt)
        write(destination / '1.response.json', response)
        code = strip_code_fence(_content(response))
        (destination / '1.generated.py').write_text(code + '\n', encoding='utf-8')
        cases = {'source': 'self_generated_internal', 'cases': [
            {'id': 'positive', 'kind': 'functional', 'purpose': 'Add two integers',
             'code': 'assert candidate(2, 3) == 5'},
            {'id': 'signed', 'kind': 'functional', 'purpose': 'Add signed integers',
             'code': 'assert candidate(-2, 2) == 0'},
        ]}
        checked = execute_checks(code, 'add', cases)
        write(destination / '1.validation.json', checked)
        item.update(status='returned', passed=checked['measured_count'] == 2 and checked['passed'] == 2,
                    usage=response.get('usage'), reported_model=response.get('model'),
                    finish_reason=response['choices'][0].get('finish_reason'), execution=checked)
    except Exception as exc:
        item.update(status='failed', passed=False, error_type=type(exc).__name__,
                    diagnostics=getattr(exc, 'safe_diagnostics', []))
    for record in budget.records[before:]:
        record.update(source_protocol=result['protocol'], purpose='single_user_agent_code_control')
    item['elapsed_seconds'] = round(time.monotonic() - start, 3)
    result.update(status='passed' if item['passed'] else 'stopped_control_failure',
        finished_utc=datetime.now(timezone.utc).isoformat(),
        new_reserved_HTTP=budget.reserved_calls - baseline['reserved_http_attempts'],
        new_known_returned_tokens=budget.snapshot()['known_returned_tokens'] - baseline['known_returned_tokens'])
    write(destination / 'cost.json', budget.snapshot())
    write(destination / 'summary.json', result)
    print(json.dumps({'status': result['status'], 'response_status': item['status'],
        'elapsed_seconds': item['elapsed_seconds'], 'passed': item['passed'],
        'new_reserved_HTTP': result['new_reserved_HTTP'],
        'new_known_returned_tokens': result['new_known_returned_tokens'],
        'P7_started': False, 'Q_updates': 0}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

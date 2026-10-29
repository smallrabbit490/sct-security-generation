"""官方org接入点的有界新控制；同模型同提示，继承B预算，代码失败不发第二次。"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from .prepare import CONFIG, OUT, read, write
from methods.cle_ablation.provider_adaptation import carried_budget, STREAM_TRANSPORT
from methods.sct_trajectory.run_closed_loop import _requester
from methods.sct_trajectory.agent_pipeline import _content, _extract_json, strip_code_fence
from methods.sct_trajectory.internal_checks import execute_checks


def main():
    config = read(CONFIG / 'view_protocol.json')
    permission = config['provider_org_control_v5']
    if not permission['enabled'] or permission['max_HTTP_attempts'] != 2:
        raise ValueError('official_org_control_not_enabled')
    previous = OUT / 'B02_provider_task_data_control_v4'
    if read(previous / 'summary.json')['status'] != 'stopped_control_failure':
        raise ValueError('previous_control_must_be_terminal')
    destination = OUT / 'B02_provider_org_control_v5'
    destination.mkdir(exist_ok=False)
    budget = carried_budget(config['two_task_P7_execution'], [read(previous / 'cost.json')])
    baseline = budget.snapshot()
    result = {'protocol': 'cle-provider-official-org-control-v5', 'status': 'running',
        'model': 'deepseek-v3.2', 'thinking': 'disabled', 'temperature': 0, 'max_tokens': 128,
        'endpoint': permission['endpoint'], 'source': 'https://docs.chatanywhere.tech/',
        'started_utc': datetime.now(timezone.utc).isoformat(), 'controls': [],
        'P7_started': False, 'Q_updates': 0, 'max_HTTP_attempts': 2,
        'same_B02_budget': True, 'previous_cost': str(previous / 'cost.json')}
    write(destination / 'summary.json', result)
    write(destination / 'cost.json', baseline)
    transport = STREAM_TRANSPORT
    native = _requester('deepseek-v3.2', transport['socket_timeout'], max_tokens=128,
        thinking='disabled', max_inflight=1, hard_timeout=transport['hard_timeout'],
        gate_wait_timeout=transport['gate_wait_timeout'], max_attempts=1, stream=True,
        endpoint=permission['endpoint'])
    def submit(prompt):
        write(destination / 'cost.json', budget.snapshot())
        return native(prompt)
    request = budget.wrap(submit, 128, max_attempts=1)
    controls = [
        ('code', 'Write a Python function add(a, b) that returns a + b. Output only the function code.'),
        ('arithmetic', 'Calculate 17 + 25. Return a JSON object with the integer field "result" and no other fields.'),
    ]
    cases = {'source': 'self_generated_internal', 'cases': [
        {'id': 'positive', 'kind': 'functional', 'purpose': 'Add two integers', 'code': 'assert candidate(2, 3) == 5'},
        {'id': 'signed', 'kind': 'functional', 'purpose': 'Add signed integers', 'code': 'assert candidate(-2, 2) == 0'}]}
    for number, (kind, prompt) in enumerate(controls, 1):
        item = {'number': number, 'kind': kind, 'status': 'submitted',
                'submitted_utc': datetime.now(timezone.utc).isoformat()}
        result['controls'].append(item)
        write(destination / 'summary.json', result)
        (destination / f'{number}.prompt.txt').write_text(prompt, encoding='utf-8')
        print(json.dumps({'status': 'submitted', 'number': number, 'kind': kind}, ensure_ascii=False), flush=True)
        before, start = len(budget.records), time.monotonic()
        try:
            response = request(prompt)
            write(destination / f'{number}.response.json', response)
            content = _content(response)
            if kind == 'code':
                checked = execute_checks(strip_code_fence(content), 'add', cases)
                passed = checked['measured_count'] == 2 and checked['passed'] == 2
                details = {'execution': checked}
            else:
                checked = _extract_json(content)
                passed = checked == {'result': 42} and type(checked['result']) is int
                details = {'actual': checked, 'expected': {'result': 42}}
            item.update(status='returned', passed=passed, usage=response.get('usage'),
                        reported_model=response.get('model'), details=details)
        except Exception as exc:
            item.update(status='failed', passed=False, error_type=type(exc).__name__,
                        diagnostics=getattr(exc, 'safe_diagnostics', []))
        for record in budget.records[before:]:
            record.update(source_protocol=result['protocol'], purpose='official_org_code_control')
        item['elapsed_seconds'] = round(time.monotonic() - start, 3)
        write(destination / 'summary.json', result)
        write(destination / 'cost.json', budget.snapshot())
        print(json.dumps({'number': number, 'kind': kind, 'status': item['status'],
                          'passed': item['passed'], 'elapsed_seconds': item['elapsed_seconds']}, ensure_ascii=False), flush=True)
        if not item['passed']:
            break
    result.update(status='passed' if len(result['controls']) == 2 and all(c['passed'] for c in result['controls'])
                  else 'stopped_control_failure', finished_utc=datetime.now(timezone.utc).isoformat(),
                  new_reserved_HTTP=budget.reserved_calls - baseline['reserved_http_attempts'],
                  new_known_returned_tokens=budget.snapshot()['known_returned_tokens'] - baseline['known_returned_tokens'])
    write(destination / 'summary.json', result)
    print(json.dumps({'status': result['status'], 'P7_started': False,
                      'new_reserved_HTTP': result['new_reserved_HTTP'],
                      'new_known_returned_tokens': result['new_known_returned_tokens']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

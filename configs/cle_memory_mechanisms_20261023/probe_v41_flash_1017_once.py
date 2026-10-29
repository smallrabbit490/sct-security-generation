"""监控任务专用的一次性新模型加法探针；非允许时段不派发，已有记录不重复付费。"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from .prepare import OUT, read, write
from methods.cle_ablation.run_joint_contract import RequestBudget
from methods.cle_ablation.provider_adaptation import STREAM_TRANSPORT
from methods.sct_trajectory.agent_pipeline import _content, strip_code_fence
from methods.sct_trajectory.internal_checks import execute_checks
from methods.sct_trajectory.provider_policy import CURRENT_MODEL, ModelTimeWindowError, ensure_model_call_allowed
from methods.sct_trajectory.run_closed_loop import _requester


MODEL = 'deepseek-v4.1-flash-1017'
PROMPT = 'Write a Python function add(a, b) that returns a + b. Output only the function code.'
DESTINATION = OUT / 'B02_provider_v41flash1017_add_control_v1'
PROTOCOL = 'cle-v41flash1017-original-user-only-add-control-v1'


def main():
    """只发送一次单user请求；等待允许时段与读取既有结果均不创建模型请求。"""
    if DESTINATION.exists():
        path = DESTINATION / 'summary.json'
        if path.exists():
            result = read(path)
            print(json.dumps({'status': result['status'], 'existing_record': True,
                              'new_HTTP_attempts': 0, 'summary': str(path)}, ensure_ascii=False))
            return result
        raise RuntimeError('existing_output_without_summary_do_not_resubmit')
    if CURRENT_MODEL != MODEL:
        raise ValueError('authorized_model_selection_changed_do_not_dispatch')
    try:
        ensure_model_call_allowed(MODEL)
    except ModelTimeWindowError:
        result = {'status': 'waiting_allowed_window', 'new_HTTP_attempts': 0}
        print(json.dumps(result))
        return result
    # 创建目录是一次性占用点；并发唤醒或中断后都不能再次提交付费请求。
    DESTINATION.mkdir(exist_ok=False)
    result = {'protocol': PROTOCOL, 'status': 'prepared', 'model': MODEL,
        'authorization': '2026-10-24 user authorized a monitoring task for one minimal add-function test only',
        'endpoint': 'https://api.chatanywhere.org/v1/chat/completions',
        'message_roles': ['user'], 'system_message_added': False,
        'temperature': 0, 'thinking': 'disabled', 'max_tokens': 128, 'stream': True,
        'user_agent': 'CLE-HTTP-Diagnostic/1.0', 'max_HTTP_attempts': 1,
        'automatic_retries': 0, 'credential': 'same existing native loader; no key value exported',
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'P7_started': False, 'Q_updates': 0, 'formal_experiments_resumed': False}
    write(DESTINATION / 'summary.json', result)
    (DESTINATION / '1.prompt.txt').write_text(PROMPT, encoding='utf-8')
    budget = RequestBudget(1, 4096, 0)
    write(DESTINATION / 'cost.json', budget.snapshot())
    native = _requester(MODEL, STREAM_TRANSPORT['socket_timeout'], max_tokens=128,
        thinking='disabled', max_inflight=1, max_attempts=1, stream=True,
        hard_timeout=STREAM_TRANSPORT['hard_timeout'],
        gate_wait_timeout=STREAM_TRANSPORT['gate_wait_timeout'], endpoint=result['endpoint'])

    def submit(prompt):
        write(DESTINATION / 'cost.json', budget.snapshot())
        return native(prompt)

    request = budget.wrap(submit, 128, max_attempts=1)
    result.update(status='submitted', submitted_utc=datetime.now(timezone.utc).isoformat())
    write(DESTINATION / 'summary.json', result)
    print(json.dumps({'status': 'submitted', 'max_HTTP_attempts': 1}), flush=True)
    started = time.monotonic()
    try:
        response = request(PROMPT)
        result['request_elapsed_seconds'] = round(time.monotonic() - started, 3)
        result.update(response_received=True, usage=response.get('usage'),
                      reported_model=response.get('model'),
                      finish_reason=response['choices'][0].get('finish_reason'))
        write(DESTINATION / '1.response.json', response)
        code = strip_code_fence(_content(response))
        (DESTINATION / '1.generated.py').write_text(code + '\n', encoding='utf-8')
        checks_started = time.monotonic()
        checked = execute_checks(code, 'add', {'source': 'self_generated_internal', 'cases': [
            {'id': 'positive', 'kind': 'functional', 'purpose': 'Add two integers',
             'code': 'assert candidate(2, 3) == 5'},
            {'id': 'signed', 'kind': 'functional', 'purpose': 'Add signed integers',
             'code': 'assert candidate(-2, 2) == 0'}]})
        write(DESTINATION / '1.validation.json', checked)
        result.update(validation_elapsed_seconds=round(time.monotonic() - checks_started, 3),
            passed=checked['measured_count'] == 2 and checked['passed'] == 2,
            validation={'measured_count': checked['measured_count'], 'passed': checked['passed']})
        result['status'] = 'passed' if result['passed'] else 'stopped_control_failure'
    except Exception as exc:
        result.update(status='stopped_technical_error', passed=False,
            request_elapsed_seconds=result.get('request_elapsed_seconds', round(time.monotonic() - started, 3)),
            error_type=type(exc).__name__, diagnostics=getattr(exc, 'safe_diagnostics', []))
    result.update(total_elapsed_seconds=round(time.monotonic() - started, 3),
        finished_utc=datetime.now(timezone.utc).isoformat(),
        reserved_HTTP_attempts=budget.reserved_calls,
        known_returned_tokens=budget.snapshot()['known_returned_tokens'],
        unknown_usage_operations=budget.snapshot()['unknown_usage_operations'])
    write(DESTINATION / 'cost.json', budget.snapshot())
    write(DESTINATION / 'summary.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


if __name__ == '__main__':
    main()

"""先以两个小任务验证不可更改中转的本地适配；共用原B02剩余额度。"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

from .prepare import CONFIG, OUT, read, write
from methods.cle_ablation.provider_adaptation import VERSION, TRANSPORT, STREAM_TRANSPORT, carried_budget
from methods.sct_trajectory.agent_pipeline import _content, _extract_json, strip_code_fence
from methods.sct_trajectory.internal_checks import execute_checks
from methods.sct_trajectory.run_closed_loop import _requester


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stream',action='store_true')
    parser.add_argument('--task-data',action='store_true',help='仅一次纯任务数据格式代码控制，不启动P7')
    args=parser.parse_args()
    if args.task_data and not args.stream:
        raise ValueError('task_data_control_requires_stream')
    old = OUT / 'B02_two_task_P7_v1'
    if read(old / 'run_metadata.json')['status'] != 'stopped_technical_error':
        raise ValueError('old_probe_must_be_terminal')
    execution = read(CONFIG / 'view_protocol.json')['two_task_P7_execution']
    version='cle-provider-adaptation-v3-stream' if args.stream else VERSION
    if args.task_data:
        version='cle-provider-task-data-control-v4'
    transport=STREAM_TRANSPORT if args.stream else TRANSPORT
    if args.stream:
        previous=OUT/('B02_provider_adaptation_v3_stream' if args.task_data else 'B02_provider_adaptation_v2')
        if read(previous/'summary.json')['status']!='stopped_control_failure':
            raise ValueError('nonstream_control_must_be_terminal')
        snapshots=[read(previous/'cost.json')]
    else:
        snapshots=[read(old/'cost.json'),read(old/'api_diagnostic_cost.json')]
    destination = OUT / ('B02_provider_adaptation_v3_stream' if args.stream else 'B02_provider_adaptation_v2')
    if args.task_data:
        destination=OUT/'B02_provider_task_data_control_v4'
    destination.mkdir(exist_ok=False)
    budget = carried_budget(execution,snapshots)
    prompts = [
        'Calculate 17 + 25. Return a JSON object with the integer field "result" and no other fields.',
        'Write a Python function add(a, b) that returns a + b. Output only the function code.',
    ]
    if args.task_data:
        prompts=[json.dumps({'operation':'complete_python_function','code_prefix':'def add(a, b):\n    ',
            'required_behavior':'sum of arguments','output_format':'complete_python_code'})]
    cases = {'source':'self_generated_internal', 'cases':[
        {'id':'positive','kind':'functional','purpose':'Add two integers','code':'assert candidate(2, 3) == 5'},
        {'id':'signed','kind':'functional','purpose':'Add signed integers','code':'assert candidate(-2, 2) == 0'}]}
    result = {'protocol':version, 'status':'running', 'transport':transport,
              'model':'deepseek-v3.2', 'thinking':'disabled', 'temperature':0, 'max_tokens':128,
              'logical_control_limit':len(prompts), 'controls':[], 'Q_updates':0,
              'P7_started':False,'task_data_format_control_only':args.task_data,
              'budget_includes_v1_and_old_diagnostic':True,
              'started_utc':datetime.now(timezone.utc).isoformat()}
    write(destination/'summary.json', result)
    write(destination/'cost.json', budget.snapshot())
    native = _requester('deepseek-v3.2', transport['socket_timeout'], max_tokens=128,
                        max_inflight=1, hard_timeout=transport['hard_timeout'],
                        gate_wait_timeout=transport['gate_wait_timeout'], max_attempts=1,
                        stream=args.stream,thinking='disabled')
    def journal(prompt):
        write(destination/'cost.json',budget.snapshot())
        return native(prompt)
    request = budget.wrap(journal,128,max_attempts=1)
    for number,prompt in enumerate(prompts,1):
        (destination/f'{number}.prompt.txt').write_text(prompt,encoding='utf-8')
        started=time.monotonic()
        control={'number':number,'status':'submitted'}
        result['controls'].append(control)
        write(destination/'summary.json',result)
        before=len(budget.records)
        try:
            response=request(prompt)
            write(destination/f'{number}.response.json',response)
            text=_content(response)
            if number==1 and not args.task_data:
                value=_extract_json(text)
                passed=value=={'result':42} and type(value['result']) is int
                details={'expected':{'result':42},'actual':value}
            else:
                checks=execute_checks(strip_code_fence(text),'add',cases)
                passed=checks['measured_count']==2 and checks['passed']==2
                details={'execution':checks}
            control.update(status='returned',passed=passed,details=details,usage=response.get('usage'),
                           reported_model=response.get('model'))
        except Exception as exc:
            control.update(status='failed',passed=False,error_type=type(exc).__name__,
                diagnostics=getattr(exc,'diagnostics',[]),safe_diagnostics=getattr(exc,'safe_diagnostics',[]))
        for record in budget.records[before:]:
            record['source_protocol']=version
            record['purpose']='provider_small_task_control'
        control['elapsed_seconds']=round(time.monotonic()-started,3)
        write(destination/'cost.json',budget.snapshot())
        write(destination/'summary.json',result)
        print(json.dumps(control,ensure_ascii=False),flush=True)
        if not control['passed']:
            break
    result.update(status='passed' if len(result['controls'])==len(prompts) and all(c['passed'] for c in result['controls'])
                  else 'stopped_control_failure',finished_utc=datetime.now(timezone.utc).isoformat())
    write(destination/'summary.json',result)
    print(json.dumps({'status':result['status'],'known_returned_tokens':budget.snapshot()['known_returned_tokens']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

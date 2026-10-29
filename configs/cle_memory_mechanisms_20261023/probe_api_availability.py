"""仅在已观测API超时后运行一次短请求；不生成实验代码、不更新Q。"""
from __future__ import annotations

import json
import time

from .prepare import OUT, write
from methods.cle_ablation.run_joint_contract import RequestBudget
from methods.sct_trajectory.run_closed_loop import _requester
from methods.sct_trajectory.agent_pipeline import _content


def main():
    probe = OUT / 'B02_two_task_P7_v1'
    meta = json.loads((probe / 'run_metadata.json').read_text(encoding='utf-8'))
    if meta['status'] != 'stopped_technical_error':
        raise ValueError('native_probe_must_be_terminal_before_diagnostic')
    destination = probe / 'api_availability_diagnostic.json'
    if destination.exists():
        raise FileExistsError('one diagnostic already preserved; no automatic repetition')
    budget = RequestBudget(3,20000,0)
    elapsed = time.monotonic()
    result = {'purpose':'short API availability diagnostic after observed timeouts; not a method score',
              'model':'deepseek-v3.2','thinking':'disabled','temperature':0,'max_tokens':32,
              'logical_request_limit':1,'HTTP_reservation_limit':3,'Q_updates':0,'status':'submitted'}
    write(destination,result)
    def native(prompt):
        write(probe / 'api_diagnostic_cost.json',budget.snapshot())
        return _requester('deepseek-v3.2',60,max_tokens=32,max_inflight=1,thinking='disabled')(prompt)
    try:
        response = budget.wrap(native,32)('Reply with exactly the word OK.')
        result.update(status='returned',reported_model=response.get('model'),usage=response.get('usage'),
                      response_text=_content(response).strip(),expected_text=_content(response).strip()=='OK')
    except Exception as exc:
        result.update(status='failed',error_type=type(exc).__name__,
                      diagnostics=getattr(exc,'diagnostics',[]),safe_diagnostics=getattr(exc,'safe_diagnostics',[]))
    result['elapsed_seconds']=round(time.monotonic()-elapsed,3)
    write(destination,result)
    write(probe / 'api_diagnostic_cost.json',budget.snapshot())
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

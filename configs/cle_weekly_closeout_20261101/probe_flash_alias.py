"""单次测试无1017后缀的Flash；独立记录，不修改两批正式实验或恢复其请求。"""
import json
from datetime import datetime, timezone
from pathlib import Path
import time
import urllib.request

from methods.cle_ablation.run_joint_contract import RequestBudget
from methods.sct_trajectory.agent_pipeline import _content, strip_code_fence
from methods.sct_trajectory.internal_checks import execute_checks
from methods.sct_trajectory.provider_policy import CURRENT_MODEL, ensure_model_call_allowed
from methods.sct_trajectory.run_closed_loop import _requester
from methods.sct_trajectory.replay_journal import write_json
from methods.sct_trajectory.wire_recording import WireRecording
from configs.cle_weekly_q_tls12_20261028.resume import tls_context

MODEL = 'deepseek-v4.1-flash'
PROMPT = 'Write a Python function add(a, b) that returns a + b. Output only the function code.'
OUT = Path('E:/ResearchRuns/CLE/20261027_full_requirements/closeout_20261101/controls/v41flash_no1017_add_once')


def main():
    # 沿用既有实验的时段要求；仅本次探针显式传入新模型名。
    ensure_model_call_allowed(CURRENT_MODEL)
    if OUT.exists():
        value = json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
        print(json.dumps({'status':value['status'],'existing_result':True,'new_HTTP':0}));return
    OUT.mkdir(parents=True,exist_ok=False)
    result = dict(protocol='cle-v41-flash-no1017-add-single-control-20261101-v1',
        status='prepared',requested_model=MODEL,
        authorization='2026-11-01 user: test v4.1flash without 1017',
        started_utc=datetime.now(timezone.utc).isoformat(),endpoint='https://api.chatanywhere.org/v1/chat/completions',
        roles=['user'],temperature=0,thinking='disabled',max_tokens=128,stream=True,
        max_HTTP_attempts=1,automatic_retries=0,TLS='TLSv1.2',certificate_and_hostname_validation=True,
        original_batches_resumed=False,Q_updates=0,new_cards=0)
    write_json(OUT/'summary.json',result)
    (OUT/'prompt.txt').write_text(PROMPT,encoding='utf-8')
    budget=RequestBudget(1,4096,0)
    write_json(OUT/'cost.json',budget.snapshot())
    native=_requester(MODEL,180,max_tokens=128,max_inflight=1,thinking='disabled',
        max_attempts=1,stream=True,hard_timeout=300,gate_wait_timeout=600,endpoint=result['endpoint'])
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}),
        urllib.request.HTTPSHandler(context=tls_context()))
    request=budget.wrap(native,128,max_attempts=1)
    start=time.monotonic()
    result.update(status='submitted',submitted_utc=datetime.now(timezone.utc).isoformat())
    write_json(OUT/'summary.json',result)
    print(json.dumps({'status':'submitted','model':MODEL,'max_HTTP_attempts':1}),flush=True)
    try:
        with WireRecording(OUT/'wire',transport=opener.open):
            response=request(PROMPT)
        result.update(request_elapsed_seconds=round(time.monotonic()-start,3),
            reported_model=response.get('model'),usage=response.get('usage'),
            finish_reason=response['choices'][0].get('finish_reason'),
            reported_model_matches_requested=response.get('model')==MODEL)
        write_json(OUT/'response.json',response)
        code=strip_code_fence(_content(response))
        (OUT/'generated.py').write_text(code+'\n',encoding='utf-8')
        validation=execute_checks(code,'add',{'source':'self_generated_internal','cases':[
            {'id':'positive','kind':'functional','purpose':'Add two integers','code':'assert candidate(2, 3) == 5'},
            {'id':'signed','kind':'functional','purpose':'Add signed integers','code':'assert candidate(-2, 2) == 0'}]})
        write_json(OUT/'validation.json',validation)
        result['validation']={k:validation[k] for k in ('measured_count','passed')}
        result['code_passed']=validation['measured_count']==validation['passed']==2
        result['status']=('passed' if result['code_passed'] and result['reported_model_matches_requested'] else
            'reported_model_mismatch' if not result['reported_model_matches_requested'] else 'code_failed')
    except Exception as exc:
        result.update(status='technical_failure',error_type=type(exc).__name__,
            diagnostics=getattr(exc,'safe_diagnostics',[]),request_elapsed_seconds=round(time.monotonic()-start,3))
    result.update(total_elapsed_seconds=round(time.monotonic()-start,3),
        finished_utc=datetime.now(timezone.utc).isoformat(),physical_HTTP=len(list((OUT/'wire').glob('*.request.json'))),
        known_tokens=budget.snapshot()['known_returned_tokens'],unknown_usage_operations=budget.snapshot()['unknown_usage_operations'])
    write_json(OUT/'cost.json',budget.snapshot())
    write_json(OUT/'summary.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

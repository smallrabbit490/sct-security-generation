"""用无1017后缀Flash复用一条完整超时选卡请求；仅一次HTTP，不接续正式实验。"""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.request

from . import probe_flash_alias as control
from methods.cle_ablation.run_joint_contract import RequestBudget
from methods.sct_trajectory.agent_pipeline import _content
from methods.sct_trajectory.provider_policy import CURRENT_MODEL, ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import write_json
from methods.sct_trajectory.selector_protocol import SelectorPrompt, parse_selection
from methods.sct_trajectory.wire_recording import WireRecording

RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
OUT = RUN/'closeout_20261101/controls/v41flash_no1017_long_selector_1384_once'


def main():
    ensure_model_call_allowed(CURRENT_MODEL)
    if OUT.exists():
        old=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
        print(json.dumps({'status':old['status'],'existing_result':True,'new_HTTP':0}));return
    decision=json.loads((RUN/'closeout_20261101/server_timeout_decision_required.json').read_text())
    item=next(v for v in decision['blocked_requests'] if v['cell_id']=='1384_r1_Q2_K1')
    source=Path(item['journal']);record=json.loads(source.read_text(encoding='utf-8'))
    if record['status']!='failed_or_unresolved' or record['selector'] is not True:
        raise ValueError('source_is_not_the_saved_failed_selector')
    prompt=record['prompt']
    candidates=json.loads(prompt.split('\nCANDIDATES:\n',1)[1])
    started=datetime.fromisoformat(record['started_utc'])
    original=[]
    for p in (source.parents[3]/'wire').glob('*.request.json'):
        v=json.loads(p.read_text(encoding='utf-8'))
        dt=(datetime.fromisoformat(v['started_utc'])-started).total_seconds()
        if 0<=dt<=record['elapsed_seconds']+10 and v['body'].get('messages')==[{'role':'user','content':prompt}]:
            original.append((p,v['body']))
    if len(original)!=1: raise ValueError('original_physical_request_not_unique')
    original_path,original_body=original[0]
    OUT.mkdir(parents=True,exist_ok=False)
    result=dict(protocol='cle-flash-no1017-exact-long-selector-control-20261101-v1',status='prepared',
        authorization='2026-11-01 user explicitly authorized one original CLE long-selector test without 1017; formal experiments remain stopped',
        source_cell=item['cell_id'],source_journal=str(source),source_wire=str(original_path),
        original_model=original_body['model'],requested_model=control.MODEL,
        prompt_characters=len(prompt),prompt_utf8_bytes=len(prompt.encode('utf-8')),candidate_count=len(candidates),
        max_cards=3,effective_max_tokens=256,selector_deadline_seconds=120,
        roles=['user'],thinking='disabled',temperature=0,stream=True,
        TLS='TLSv1.2',certificate_and_hostname_validation=True,
        max_HTTP_attempts=1,automatic_retries=0,formal_experiments_resumed=False,
        started_utc=datetime.now(timezone.utc).isoformat())
    write_json(OUT/'summary.json',result)
    (OUT/'prompt.txt').write_text(prompt,encoding='utf-8')
    budget=RequestBudget(1,len(prompt.encode('utf-8'))+1024+256,0)
    write_json(OUT/'cost.json',budget.snapshot())
    native=control._requester(control.MODEL,180,max_tokens=4096,max_inflight=1,thinking='disabled',
        max_attempts=1,stream=True,hard_timeout=300,gate_wait_timeout=600,
        endpoint='https://api.chatanywhere.org/v1/chat/completions')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({'https':'http://127.0.0.1:7897'}),
        urllib.request.HTTPSHandler(context=control.tls_context()))
    request=budget.wrap(native,4096,max_attempts=1)
    before=time.monotonic()
    result.update(status='submitted',submitted_utc=datetime.now(timezone.utc).isoformat())
    write_json(OUT/'summary.json',result)
    print(json.dumps({'status':'submitted','model':control.MODEL,'prompt_characters':len(prompt),
                      'candidate_count':len(candidates),'max_HTTP_attempts':1}),flush=True)
    try:
        with WireRecording(OUT/'wire',transport=opener.open):
            response=request(SelectorPrompt(prompt,deadline=time.monotonic()+120))
        result.update(request_elapsed_seconds=round(time.monotonic()-before,3),
            reported_model=response.get('model'),usage=response.get('usage'),
            finish_reason=response['choices'][0].get('finish_reason'))
        write_json(OUT/'response.json',response)
        (OUT/'response.txt').write_text(_content(response),encoding='utf-8')
        diagnostics={}
        selection=parse_selection(response,len(candidates),3,diagnostics)
        write_json(OUT/'selection_validation.json',dict(status='passed',selected_local_ids=selection,
            candidate_count=len(candidates),max_cards=3,diagnostics=diagnostics))
        result.update(selected_local_ids=selection,selection_protocol_passed=True,
            status='passed' if response.get('model')==control.MODEL else 'reported_model_mismatch')
    except Exception as exc:
        result.update(status='technical_or_protocol_failure',error_type=type(exc).__name__,
            diagnostics=getattr(exc,'safe_diagnostics',[]),
            request_elapsed_seconds=result.get('request_elapsed_seconds',round(time.monotonic()-before,3)))
    wires=list((OUT/'wire').glob('*.request.json'))
    if wires:
        body=json.loads(wires[0].read_text(encoding='utf-8'))['body']
        expected={**original_body,'model':control.MODEL}
        result['request_body_differs_only_in_model']=body==expected
        result['full_prompt_identical']=body['messages']==original_body['messages']
        if body!=expected: result['status']='request_body_mismatch'
    result.update(total_elapsed_seconds=round(time.monotonic()-before,3),
        finished_utc=datetime.now(timezone.utc).isoformat(),physical_HTTP=len(wires),
        known_tokens=budget.snapshot()['known_returned_tokens'],unknown_usage_operations=budget.snapshot()['unknown_usage_operations'])
    write_json(OUT/'cost.json',budget.snapshot())
    write_json(OUT/'summary.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

"""断点恢复只补安全的新请求；已完成响应和未决付费请求均不可重复派发。"""
import json

import pytest

from configs.cle_nomemory_baseline_20261024.resume_plt import RecoveryRequests,audit,identity,write
from methods.sct_trajectory.replay_journal import ReplayStop
from methods.sct_trajectory.wire_recording import WireRecording


def test_saved_response_is_replayed_without_client(tmp_path):
    response={'choices':[{'message':{'content':'saved'}}]}
    prior={identity('old'):{'status':'completed','response':response}}
    request=RecoveryRequests(prior,tmp_path,lambda:pytest.fail('no repeat fee'))
    assert request('old')==response
    assert not list(tmp_path.glob('*.json'))


def test_network_unresolved_is_never_dispatched(tmp_path):
    prior={identity('old'):{'status':'failed_or_unresolved','diagnostics':[{'category':'network_error'}]}}
    with pytest.raises(ReplayStop,match='not_safe'):
        RecoveryRequests(prior,tmp_path,lambda:pytest.fail('no retry'))('old')


def test_user_authorized_exact_unresolved_request_can_be_reissued(tmp_path):
    key=identity('old')
    prior={key:{'status':'failed_or_unresolved','diagnostics':[{'category':'network_error'}]}}
    request=RecoveryRequests(prior,tmp_path,lambda:lambda prompt:{'usage':{'total_tokens':3}},
                             authorized_unresolved=[key])
    assert request('old')['usage']['total_tokens']==3
    saved=json.loads((tmp_path/(key+'.json')).read_text())
    assert saved['user_authorized_reissue'] and saved['historical_failure_preserved']
    assert prior[key]['status']=='failed_or_unresolved'


def test_prefix_mismatch_stops_before_new_payment(tmp_path):
    prompt='analysis Task: {"task_id":"2"}'
    prior={identity(prompt):{'status':'completed','prompt':prompt,'response':{}}}
    request=RecoveryRequests(prior,tmp_path,lambda:pytest.fail('must consume saved prefix'))
    with pytest.raises(ReplayStop,match='prefix_not_consumed'):
        request('changed analysis Task: {"task_id":"2"}')


def test_circuit_only_can_dispatch_once_and_failure_stops_queue(tmp_path):
    prior={identity('not_sent'):{'status':'failed_or_unresolved','diagnostics':[{'category':'circuit_open'}]}}
    calls=[]
    def live(prompt):
        calls.append(prompt)
        if prompt=='fail':raise TimeoutError()
        return {'usage':{'total_tokens':2}}
    request=RecoveryRequests(prior,tmp_path,lambda:live)
    assert request('not_sent')['usage']['total_tokens']==2
    with pytest.raises(ReplayStop,match='transport_failed'):request('fail')
    with pytest.raises(ReplayStop,match='no_queued_dispatch'):request('queued')
    assert calls==['not_sent','fail']


def test_audit_preserves_delivered_and_holds_only_real_http(tmp_path):
    write(tmp_path/'protocol.json',{'protocol':'P3'})
    write(tmp_path/'inputs/tasks_PLT.json',[{'index':i} for i in range(1,5)])
    native=tmp_path/'source_bundle/translation_work/nomemory/PLT/rows.jsonl'
    native.parent.mkdir(parents=True);native.write_text(json.dumps({'task_id':'1'})+'\n')
    for tid,diagnostics in [('2',[{'category':'network_error'}]),('3',[{'category':'circuit_open'}])]:
        prompt='Task: '+json.dumps({'task_id':tid})
        write(tmp_path/'journals/PLT/requests'/(identity(prompt)+'.json'),
              {'identity':identity(prompt),'status':'failed_or_unresolved','prompt':prompt,'diagnostics':diagnostics})
        if tid=='2':write(tmp_path/'wire/PLT/0001.request.json',{'body':{'messages':[{'content':prompt}]}})
    _,check,tasks=audit(tmp_path)
    assert check['completed_task_ids']==['1']
    assert check['held_requests'][0]['task_id']=='2'
    assert [t['index'] for t in tasks]==[3,4]


def test_direct_wire_transport_does_not_change_request_or_use_global_proxy(tmp_path,monkeypatch):
    import io,urllib.request
    class Response(io.BytesIO):status=200
    calls=[]
    def direct(req,**kw):calls.append(req);return Response(b'OK')
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**k:pytest.fail('broken proxy'))
    req=urllib.request.Request('https://api.chatanywhere.org/v1/chat/completions',data=b'{"model":"unchanged"}')
    with WireRecording(tmp_path,transport=direct):
        with urllib.request.urlopen(req) as response:assert response.read()==b'OK'
    assert calls==[req]

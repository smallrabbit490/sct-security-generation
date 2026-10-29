"""新模型基准的最小记录/回放测试；不构造真实API客户端。"""
import io
import json
from pathlib import Path

import pytest

from methods.sct_trajectory.replay_journal import RequestJournal,ReplayStop
from methods.sct_trajectory.wire_recording import WireRecording
from configs.cle_model_baseline_20261024.execute import arguments


SETTINGS={'model':'offline-fake','max_tokens':4096,'roles':['user']}


def test_repeated_same_prompt_is_not_collapsed_and_replay_has_no_client(tmp_path):
    counter=[]
    def factory():
        def call(prompt):
            counter.append(prompt)
            return {'choices':[{'message':{'content':str(len(counter))}}],
                    'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}}
        return call
    journal=RequestJournal(tmp_path)
    request=journal.wrap(factory,SETTINGS)
    assert request('same')!=request('same')
    assert counter==['same','same']
    replay=RequestJournal(tmp_path,mode='replay')
    request=replay.wrap(lambda:pytest.fail('no network client'),SETTINGS)
    assert request('same')['choices'][0]['message']['content']=='1'
    assert request('same')['choices'][0]['message']['content']=='2'
    assert replay.summary()['known_usage']['total_tokens']==24
    with pytest.raises(ReplayStop,match='missing_request'):request('unseen')


def test_unresolved_request_never_resubmitted(tmp_path):
    journal=RequestJournal(tmp_path)
    def call(_):raise TimeoutError()
    with pytest.raises(ReplayStop,match='no_automatic_resubmit'):
        journal.wrap(lambda:call,SETTINGS)('first')
    with pytest.raises(ReplayStop,match='batch_stopped'):
        journal.wrap(lambda:pytest.fail('queued request must not dispatch'),SETTINGS)('next')
    assert len(list(tmp_path.glob('*.json')))==1
    resume=RequestJournal(tmp_path,mode='resume')
    with pytest.raises(ReplayStop,match='do_not_resubmit'):
        resume.wrap(lambda:pytest.fail('no repeat'),SETTINGS)('first')


def test_resume_refuses_divergence_before_saved_prefix_consumed(tmp_path):
    RequestJournal(tmp_path).wrap(lambda:lambda _: {'usage':{}},SETTINGS)('old')
    with pytest.raises(ReplayStop,match='diverged'):
        RequestJournal(tmp_path,mode='resume').wrap(lambda:pytest.fail('no paid tail'),SETTINGS)('new')


def test_wire_keeps_body_and_bytes_but_no_authorization_header(tmp_path,monkeypatch):
    import urllib.request
    class Response(io.BytesIO):
        status=200
    monkeypatch.setattr(urllib.request,'urlopen',lambda *a,**k:Response(b'data: reply\n'))
    request=urllib.request.Request('https://api.chatanywhere.org/v1/chat/completions',
        data=json.dumps({'model':'offline','messages':[{'role':'user','content':'p'}]}).encode(),
        headers={'Authorization':'Bearer offline-secret-not-real'})
    with WireRecording(tmp_path):
        with urllib.request.urlopen(request) as r:assert r.read()==b'data: reply\n'
    assert (tmp_path/'0000001.response.raw').read_bytes()==b'data: reply\n'
    assert 'offline-secret' not in ''.join(p.read_text() for p in tmp_path.iterdir())


def test_full_training_uses_new_tasks_and_does_not_pass_old_memory_or_Q(tmp_path):
    args=arguments({'training_args':{'rounds':3,'retrieval_mode':'semantic_llm','workers':4}},'PLT',tmp_path,tmp_path/'new')
    assert '--tasks-file' in args and '--rounds' in args
    assert '--memory' not in args and '--resume-from' not in args and '--q-learning' not in args

"""诊断运行器的预算、隐藏评分与断点续跑测试。"""
import importlib
import pytest


def runner():
    try:
        return importlib.import_module('methods.direction_screening.run')
    except ModuleNotFoundError:
        pytest.fail('联合诊断运行器尚未实现')


def test_budget_stops_before_extra_call():
    r = runner()
    calls = []
    def request(prompt):
        calls.append(prompt)
        return {'choices': [{'message': {'content': 'OK'}, 'finish_reason': 'stop'}], 'usage': {'total_tokens': 2}}
    session = r.Session({3072: request}, max_calls=1)
    assert session.ask('public prompt') == 'OK'
    with pytest.raises(RuntimeError, match='call_budget'):
        session.ask('should not leave process')
    assert len(calls) == 1


def test_resumption_rejects_conflicting_duplicate(tmp_path):
    r = runner()
    path = tmp_path / 'rows.jsonl'
    path.write_text('{"task_id": 1, "arm": "direct"}\n{"task_id": 1, "arm": "direct"}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='duplicate'):
        r.read_rows(path)


def test_frozen_retrieval_does_not_consume_ground_truth():
    r = runner()
    bank = [{'id':'a','cwe':'79','rule':'escape output','source_description':'HTML output'},
            {'id':'b','cwe':'79','rule':'safe attributes','source_description':'HTML attribute'}]
    task = {'index':1,'CWE_ID':'79','task_description':{'description':'HTML output'},'ground_truth':{'patched_code':'b'}}
    card = r.retrieve(task, bank)
    task['ground_truth']['patched_code'] = 'a'
    assert r.retrieve(task, bank) == card


def test_branch_selector_is_not_oracle():
    r = runner()
    candidates = [{'code':'def f(): return 1','public_score':2,'joint':False},
                  {'code':'def f(): return 2','public_score':1,'joint':True}]
    assert r.choose_candidate(candidates)['code'].endswith('1')


def test_review_schema_retry_is_bounded_and_keeps_error_trace():
    r = runner()
    replies=iter(['{"issues":[{"reason":"bad\\q"}]}','{"issues":[]}'])
    def request(prompt):
        return {'choices':[{'message':{'content':next(replies)},'finish_reason':'stop'}]}
    session=r.Session({1024:request},max_calls=2)
    task={'index':1,'CWE_ID':79,'task_description':{'description':'return input'}}
    assert r.review(session,task,'def f(): return 1','functional')['issues']==[]
    assert session.usage['calls']==2
    assert session.trace[0]['parse_error']=='JSONDecodeError'

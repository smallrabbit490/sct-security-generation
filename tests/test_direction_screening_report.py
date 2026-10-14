"""报告必须保留语法失效的总分母伤害，并正确核算共用草稿部署成本。"""
import json
from methods.direction_screening.protocol import outcome
from methods.direction_screening.report import build


def row(arm,passed,tokens,*,syntax_fail=False,shared=False):
    evidence={'syntax_or_compile':{'status':'fail' if syntax_fail else 'pass'},
              'functional':{'status':'unmeasured' if syntax_fail else ('pass' if passed else 'fail')},
              'security':{'status':'unmeasured' if syntax_fail else ('pass' if passed else 'fail')}}
    result={'code':'def f(): pass',**outcome(evidence)}
    value={'task_id':1,'arm':arm,'final':result,'attempts':[result],
           'usage':{'calls':1,'total_tokens':tokens}}
    if shared:
        value['shared_draft_from']='direct'
    return value


def test_total_denominator_and_deployment_cost(tmp_path):
    path=tmp_path/'screen'
    path.mkdir()
    rows=[row('direct',True,10),row('draft_plain',False,20,syntax_fail=True,shared=True)]
    (path/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    report=build(tmp_path,'screen')
    assert report['paired']['draft_plain']['measured_pairs']==0
    assert report['paired_total_denominator']['draft_plain']['losses']==1
    assert report['arms']['draft_plain']['deployment_total_tokens']==30
    assert report['arms']['draft_plain']['deployment_calls']==2


def test_combined_report_rejects_duplicate_key(tmp_path):
    import pytest
    for name in ('screen','adjustment'):
        path=tmp_path/name
        path.mkdir()
        (path/'rows.jsonl').write_text(json.dumps(row('direct',True,10))+'\n',encoding='utf-8')
    with pytest.raises(ValueError,match='duplicate'):
        build(tmp_path,'screen',['adjustment'],'combined')

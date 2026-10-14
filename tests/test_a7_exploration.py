"""A7 诊断实验的隔离、公开选择和冻结边界回归。"""
import importlib
import json


def api():
    spec = importlib.util.find_spec('methods.a7_exploration')
    assert spec is not None, 'A7 exploration package is not implemented'
    return importlib.import_module('methods.a7_exploration.protocol')


def card(family='source', valid=True):
    return {'id':'s1','family_id':family,'cwe':'79','source_evidence':{'patched':{
        'joint':valid,'measured':True}},'source_description':'render escaped user content',
        'rule':'escape user content', 'source_public':{'description':'render escaped user content'}}


def test_failed_source_is_never_retrieved():
    p=api()
    assert p.eligible_cards({'index':1,'family_id':'target','CWE_ID':'79'},[card(valid=False)]) == []


def test_same_family_is_never_retrieved():
    p=api()
    assert p.eligible_cards({'index':1,'family_id':'source','CWE_ID':'79'},[card()]) == []


def test_public_projection_excludes_answers_and_test_setup():
    p=api()
    task={'index':1,'CWE_ID':'79','task_description':{'description':'render','function_name':'render',
          'ground_truth':'SECRET','setup':'SECRET'},'ground_truth':'SECRET','unittest':{'setup':'SECRET'}}
    assert 'SECRET' not in json.dumps(p.public_task(task))


def test_choice_ignores_official_results_and_preserves_passed_cases():
    p=api()
    a={'issues':[], 'checks':{'cases':[{'id':'f','status':'pass','measured':True}]},'official':{'joint':False}}
    b={'issues':[], 'checks':{'cases':[{'id':'f','status':'fail','measured':True}]},'official':{'joint':True}}
    assert p.choose([a,b]) == 0
    assert not p.improves(a,b)


def test_missing_dependency_is_unmeasured():
    p=api()
    assert p.classify_exception('NameError','check') == ('unsupported_context',False)
    assert p.classify_exception('AssertionError','check') == ('fail',True)
    assert p.classify_exception('SyntaxError','candidate_compile') == ('syntax_error',True)


def test_freeze_rejects_changed_configuration(tmp_path):
    p=api()
    f=tmp_path/'memory.json'; f.write_text('one')
    frozen=p.hash_files([f]); f.write_text('two')
    try:
        p.check_frozen(frozen)
    except ValueError as e:
        assert 'frozen' in str(e)
    else:
        assert False, 'changed memory allowed in frozen confirmation'


def test_family_partition_rejects_overlap():
    p=api()
    try:
        p.check_groups({'source':[{'family_id':'x'}],'screen':[{'family_id':'x'}]})
    except ValueError:
        pass
    else:
        assert False, 'source and evaluation family overlap accepted'


def test_public_fixtures_and_expected_exception_really_execute():
    from methods.a7_exploration.checks import execute
    suite={'setup':'RUNTIME = {"ok": 3}', 'cases':[{'id':'f','kind':'functional',
        'purpose':'public runtime lookup','code':'assert candidate("ok") == 3'},
        {'id':'s','kind':'security','purpose':'public exception',
         'code':'raised=False\ntry:\n candidate("bad")\nexcept ValueError:\n raised=True\nassert raised'}]}
    result=execute('def lookup(key):\n if key not in RUNTIME: raise ValueError()\n return RUNTIME[key]', 'lookup',suite)
    assert [c['status'] for c in result['cases']] == ['pass','pass']


def test_repair_can_continue_beyond_six_calls():
    spec=importlib.util.find_spec('methods.a7_exploration.workflow')
    assert spec is not None, 'workflow missing'
    from methods.a7_exploration.workflow import Session
    request=lambda prompt:{'choices':[{'message':{'content':'ok'},'finish_reason':'stop'}], 'usage':{}}
    session=Session({4096:request,8192:request,16384:request})
    for _ in range(9):
        assert session.ask('public','test') == 'ok'
    assert session.usage['calls']==9


def test_ast_audit_catches_local_shadow_of_public_dependency():
    spec=importlib.util.find_spec('methods.a7_exploration.workflow')
    assert spec is not None, 'workflow missing'
    from methods.a7_exploration.workflow import audit
    contract={'function_name':'f','argument_names':['x'],'external_names':['Employee']}
    assert any(i['type']=='external_shadow' for i in audit('def f(x):\n Employee = object\n return x',contract))


def test_nested_acceptance_rejects_more_joint_with_function_harm():
    spec=importlib.util.find_spec('methods.a7_exploration.run')
    assert spec is not None, 'nested runner missing'
    from methods.a7_exploration.run import accept_revision
    before=[{'task_id':1,'final':{'joint':False,'functional':True,'measured':True}},
            {'task_id':2,'final':{'joint':False,'functional':False,'measured':True}}]
    after=[{'task_id':1,'final':{'joint':False,'functional':False,'measured':True}},
           {'task_id':2,'final':{'joint':True,'functional':True,'measured':True}}]
    assert not accept_revision(before,after)


def test_new_calibration_and_confirmation_are_disjoint():
    spec=importlib.util.find_spec('methods.a7_exploration.run')
    assert spec is not None, 'nested runner missing'
    from methods.a7_exploration.run import prepare_data
    data,manifest=prepare_data(None)
    assert len(data['calibration'])==24 and len(data['confirmation'])==50
    api().check_groups(data)
    assert manifest['formal_holdout_used'] is False


def test_check_validator_rejects_module_alias_and_accepts_offline_url_parse():
    from methods.a7_exploration.checks import snippet_error
    assert snippet_error('assert candidate.f(1) == 1',True)=='candidate_must_be_callable_alias'
    assert snippet_error('from urllib.parse import unquote') == ''


def test_derivation_rejects_boolean_assertion_with_opposite_expected_value():
    import methods.a7_exploration.checks as c
    assert hasattr(c,'derivation_matches'), 'derivation consistency check missing'
    assert not c.derivation_matches("assert candidate('a%20b') == True",{'expected_result':False})
    assert c.derivation_matches("assert candidate('abc') is True",{'expected_result':True})


def test_unmeasured_candidate_does_not_beat_measured_failure():
    p=api()
    a={'issues':[],'checks':{'cases':[{'id':'f','status':'fail','measured':True}]}}
    b={'issues':[],'checks':{'cases':[{'id':'f','status':'unsupported_context','measured':False}]}}
    assert p.choose([a,b])==0


def test_skipped_or_swallowed_assertion_is_not_valid_check():
    from methods.a7_exploration.checks import snippet_error
    assert snippet_error('if False:\n assert candidate(1)==999',True)
    assert snippet_error('try:\n assert candidate(1)==999\nexcept Exception:\n pass',True)


def test_derivation_text_contradiction_is_rejected():
    from methods.a7_exploration.checks import derivation_matches
    assert not derivation_matches('assert candidate(1)==True',{'expected_result':True,
        'derivation':'After decoding it should be False. But assertion says True.'})

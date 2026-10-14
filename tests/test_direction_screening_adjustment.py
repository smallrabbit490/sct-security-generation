"""公开契约交接调整：依赖识别、接口漂移及隐藏材料隔离。"""
import pytest


def module():
    try:
        from methods.direction_screening import adjustment
        return adjustment
    except ImportError:
        pytest.fail('契约交接调整尚未实现')


def task():
    return {'index':1,'CWE_ID':327,'task_description':{
        'function_name':'sign_data','description':'Sign data.',
        'context':'- secret_key: bytes, an externally provided signing key',
        'arguments':'- hash_algorithm: str, algorithm\n- content: bytes, data'},
        'ground_truth':{'patched_code':'SECRET_NOT_PUBLIC'}}


def test_contract_does_not_consume_answer_and_audits_required_arg_drift():
    m=module()
    contract=m.contract_manifest(task())
    assert contract['external_names']==['secret_key']
    assert contract['argument_names']==['hash_algorithm','content']
    assert 'SECRET_NOT_PUBLIC' not in str(contract)
    issues=m.audit_code('def sign_data(hash_algorithm, content, secret_key):\n return content',contract)
    assert any(i['type']=='unexpected_required_argument' for i in issues)
    assert m.audit_code('def sign_data(hash_algorithm, content):\n return secret_key',contract)==[]


def test_public_global_rebinding_detected_but_mutation_allowed():
    m=module()
    t=task()
    t['task_description']['context']="A global dictionary 'TRUSTED_CONFIG_SIGNATURES' contains signatures."
    c=m.contract_manifest(t)
    issues=m.audit_code("TRUSTED_CONFIG_SIGNATURES={}\ndef sign_data(hash_algorithm,content):\n return None",c)
    assert any(i['type']=='external_redefinition' for i in issues)
    assert m.audit_code("def sign_data(hash_algorithm,content):\n TRUSTED_CONFIG_SIGNATURES['a']=content",c)==[]


def test_unparseable_arguments_do_not_invent_signature_constraints():
    m=module()
    t=task()
    t['task_description']['arguments']='Accept the required application inputs.'
    c=m.contract_manifest(t)
    assert c['argument_names']==[]
    assert not any(i['type']=='unexpected_required_argument' for i in m.audit_code('def sign_data(a,b,c):\n pass',c))


def test_type_first_arguments_and_existing_class():
    m=module()
    t=task()
    t['task_description']['arguments']='- str, task_identifier: unique ID\n- dict, task_content: content'
    t['task_description']['context']='You are given an Employee class containing attributes.'
    c=m.contract_manifest(t)
    assert c['argument_names']==['task_identifier','task_content']
    assert 'Employee' in c['external_names']


def test_extraction_uses_unambiguous_syntax_only_and_preserves_ambiguous_reply():
    m=module()
    code='def f():\n return 1'
    assert m.extract_candidate('Explanation\n```python\n'+code+'\n```\nDone')==(code,'single_python_fence')
    assert m.extract_candidate('```python\n'+code)==(code,'unclosed_leading_fence_syntax_valid')
    ambiguous='```python\ndef f(): return 1\n```\n```python\ndef f(): return 2\n```'
    assert m.extract_candidate(ambiguous)==(ambiguous,'unchanged')

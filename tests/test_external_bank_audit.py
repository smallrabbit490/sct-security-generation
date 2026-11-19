"""外部题库审计：缺陷举证、测试边界及精确恢复的离线回归。"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module():
    path = ROOT / 'tools/external_bank_audit/schema.py'
    assert path.exists(), '审计schema尚未实现'
    spec = importlib.util.spec_from_file_location('external_audit_schema', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def example():
    p = {'sources': [{'path': 'test.py', 'role': 'test', 'text': "assert f(request={}) == 1"},
                     {'path': 'prompt.txt', 'role': 'public', 'text': 'argument: dict'}]}
    o = {'verdict': '有缺陷', 'defect_type': '接口契约', 'test_quality': '无法判定',
         'test_integrity': '完整', 'reason': '参数未命名而测试用关键字调用',
         'evidence': [{'test_path': 'test.py', 'test_quote': 'f(request={})',
                       'public_path': 'prompt.txt', 'public_quote': 'argument: dict',
                       'missing_requirement': '参数名request', 'why_not_inferable': '参数列表只有类型，没有参数名'}]}
    return p, o


def test_defect_requires_assertion_and_uninferable_gap():
    m = module(); p, o = example()
    assert not m.validate_result(o, p)
    o['evidence'][0]['test_quote'] = 'assert secret_test()'
    assert m.validate_result(o, p)


def test_non_defective_cannot_have_defect_type():
    m = module(); p, o = example(); o['verdict'] = '合格'
    assert m.validate_result(o, p)


def test_absent_dynamic_tests_cannot_claim_joint_quality():
    m = module(); p, o = example(); p['sources'] = [x for x in p['sources'] if x['role'] != 'test']
    o.update(verdict='无法判定', defect_type=None, evidence=[], test_integrity='未提供', test_quality='充分')
    assert m.validate_result(o, p)


def test_bad_tests_need_separate_integrity():
    m = module(); p, o = example()
    o.update(verdict='合格', defect_type=None, evidence=[], test_integrity='不完整或语法错误', test_quality='无法判定')
    assert not m.validate_result(o, p)


def test_broken_tests_cannot_establish_task_defect():
    m = module(); p, o = example()
    o['test_integrity'] = '不完整或语法错误'
    assert 'broken_tests_cannot_establish_defect' in m.validate_result(o, p)


def test_joint_bypass_requires_dynamic_security_oracle():
    m = module(); p, o = example()
    p['oracle'] = 'static_only'
    o.update(verdict='合格', defect_type=None, evidence=[], test_quality='Joint 可被绕过')
    assert 'joint_requires_dynamic_function_and_security_oracles' in m.validate_result(o, p)


def test_resume_identity_changes_with_payload_or_protocol():
    m = module()
    a=m.request_identity({'a': 1}, 'model', 'protocol', 1)
    assert a != m.request_identity({'a': 2}, 'model', 'protocol', 1)
    assert a != m.request_identity({'a': 1}, 'model', 'protocol-v2', 1)
    assert a != m.request_identity({'a': 1}, 'model', 'protocol', 2)


def test_classification_table_groups_without_emitting_task_details():
    import sys
    sys.path.insert(0, str(ROOT / 'tools/external_bank_audit'))
    import aggregate
    rows = [
        {'bank':'CWEval','verdict_s1':'有缺陷','verdict_s2':'合格',
         'defect_type_s1':'接口契约','defect_type_s2':'',
         'test_quality_s1':'充分','test_quality_s2':'充分',
         'test_integrity_s1':'完整','test_integrity_s2':'完整',
         'task_id':'should-not-appear'},
        {'bank':'CWEval','verdict_s1':'缺测','verdict_s2':'合格',
         'defect_type_s1':'','defect_type_s2':'',
         'test_quality_s1':'','test_quality_s2':'无法判定',
         'test_integrity_s1':'','test_integrity_s2':'未提供',
         'task_id':'also-hidden'},
    ]
    text = aggregate.render_classification_table(rows)
    assert '有缺陷（n / %）' in text
    assert '1 / 33.3%' in text
    assert '双判分歧' in text
    assert 'task_id' not in text

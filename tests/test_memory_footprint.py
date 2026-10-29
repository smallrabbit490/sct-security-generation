"""对手工可核对的代码变化验证足迹单位；不调用模型或执行候选代码。"""
from methods.cle_ablation.memory_footprint import compare_code


def test_binding_used_by_old_code_then_redefined_is_a_candidate_flag():
    old = 'def f(person):\n    return TEMPLATE.format(name=person.name)\n'
    new = "TEMPLATE = 'fixed'\ndef f(person):\n    return TEMPLATE.format(name=person.name)\n"
    result = compare_code(old, new, {'function_name': 'f'})
    assert result['new_external_rebindings'] == ['TEMPLATE']
    assert 0 < result['statement_change_ratio'] <= 1


def test_imported_name_and_new_local_are_not_external_rebinding():
    old = 'from html import escape\ndef f(value):\n    return escape(value)\n'
    new = 'from html import escape\ndef f(value):\n    result = escape(value)\n    return result\n'
    result = compare_code(old, new, {'function_name': 'f'})
    assert result['new_external_rebindings'] == []


def test_adding_an_explicit_import_for_a_host_library_is_separate_from_replacing_data():
    old = 'def f(value):\n    return re.escape(value)\n'
    new = 'import re\ndef f(value):\n    return re.escape(value)\n'
    result = compare_code(old, new, {'function_name': 'f'})
    assert result['new_external_rebindings'] == []
    assert result['new_imports_for_external_reads'] == ['re']


def test_type_only_declaration_does_not_define_a_replacement_object():
    old = 'STORE: dict\ndef f(key):\n    return STORE[key]\n'
    new = 'STORE = {}\ndef f(key):\n    return STORE[key]\n'
    assert compare_code(old, new, {})['new_external_rebindings'] == ['STORE']


def test_identity_alias_still_depends_on_host_value():
    old = 'STORE = STORE\ndef f(key):\n    return STORE[key]\n'
    new = 'STORE = {}\ndef f(key):\n    return STORE[key]\n'
    assert compare_code(old, new, {})['new_external_rebindings'] == ['STORE']


def test_literal_globals_lookup_is_an_external_dependency():
    old = "def f():\n    return globals().get('people', [])\n"
    new = 'people = []\ndef f():\n    return people\n'
    assert compare_code(old, new, {})['new_external_rebindings'] == ['people']


def test_no_change_has_zero_ratio_and_no_statements_has_null():
    code = 'def f(value):\n    return value\n'
    assert compare_code(code, code, {})['statement_change_ratio'] == 0
    result = compare_code('', '# only a comment', {})
    assert result['statement_change_ratio'] is None
    assert result['zero_denominator_reason'] == 'both_codes_have_no_statements'


def test_invalid_code_is_unmeasured_not_a_zero_risk_result():
    result = compare_code('def f(): pass', 'def f(:', {})
    assert result['measured'] is False
    assert result['statement_change_ratio'] is None

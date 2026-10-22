"""公开契约保护的零 API 回归：检查词法边界与证据隔离，不重算正式任务成绩。"""
import json

import pytest

from methods.sct_trajectory.public_contract_checks import (
    check_public_contract,
    compile_public_contract,
    contract_check_feedback,
)


TASK_1003 = {
    'function_name': 'render_user_post',
    'context': (
        'USER_POST_FORMAT: str, a string template for displaying user posts with placeholders '
        'for username, post title, post body, and tags.\n'
        'The exact template placeholder names are username, post_title, post_body and tags_html. '
        'Use the supplied USER_POST_FORMAT unchanged; tags_html is the space-separated span markup.'
    ),
    'arguments': '- username: str, user name\n- post_title: str, title\n- post_body: str, body\n- tags: list(str), tags',
    'language': 'python',
}
VALID_1003 = (
    'from html import escape\n'
    'def render_user_post(username, post_title, post_body, tags):\n'
    '    return USER_POST_FORMAT.format(username=escape(username), post_title=escape(post_title),\n'
    '        post_body=escape(post_body), tags_html=" ".join("<span>" + escape(tag) + "</span>" for tag in tags))\n'
)


def _requirements():
    return compile_public_contract({'entry_point': 'f', 'context': 'CONFIG: an externally supplied object.'})


def _ids(result):
    return {item['id'] for item in result['violations']}


def test_1003_explicit_supplied_binding_and_signature_are_compiled():
    requirements = compile_public_contract(TASK_1003)
    assert [item['name'] for item in requirements['protected_bindings']] == ['USER_POST_FORMAT']
    assert requirements['signature']['names'] == ['username', 'post_title', 'post_body', 'tags']
    result = check_public_contract(VALID_1003, requirements)
    assert result['measured'] and result['status'] == 'pass'
    assert result['functional'] == result['security'] == 'unmeasured'
    assert 'card_implementation_semantics' in result['unmeasured']


def test_1003_replacing_template_is_static_violation_without_running_candidate():
    code = 'USER_POST_FORMAT = "{username}: {post_body}"\n' + VALID_1003
    result = check_public_contract(code, compile_public_contract(TASK_1003))
    assert result['status'] == 'fail'
    assert _ids(result) == {'public.external_binding_rebound:USER_POST_FORMAT'}
    assert result['violations'][0]['line'] == 1


@pytest.mark.parametrize('context,name', [
    ('- user_cache: A global dictionary to store user data for caching.', 'user_cache'),
    ('- task_queue: A globally accessible queue utilized for task storage and processing.', 'task_queue'),
    ('CONFIG: an object that may be pre-existing or initialized here.', 'CONFIG'),
    ('CONFIG: an object. If the caller supplies it, use the supplied CONFIG unchanged.', 'CONFIG'),
])
def test_global_or_conditional_wording_does_not_forbid_legal_initialization(context, name):
    requirements = compile_public_contract({'entry_point': 'f', 'context': context})
    assert requirements['protected_bindings'] == []
    result = check_public_contract(f'{name} = {{}}\ndef f():\n    return {name}\n', requirements)
    assert result['status'] == 'pass'


def test_explicit_preexisting_and_supplied_objects_are_identified():
    requirements = compile_public_contract({
        'context': (
            'PROFILE_FORMAT: str, a pre-existing string template.\n'
            "You are provided with the 'USERS' dictionary, the 'CONTENT' dictionary, "
            "and the 'subscription_hierarchy' list."
        )
    })
    assert {item['name'] for item in requirements['protected_bindings']} == {
        'PROFILE_FORMAT', 'USERS', 'CONTENT', 'subscription_hierarchy'}


@pytest.mark.parametrize('prefix', [
    'CONFIG = {}',
    'CONFIG: dict = {}',
    'CONFIG += []',
    'del CONFIG',
    'a, CONFIG = (1, {})',
    'import json as CONFIG',
    'from json import loads as CONFIG',
    'def CONFIG():\n    pass',
    'class CONFIG:\n    pass',
    'for CONFIG in []:\n    pass',
    'with resource() as CONFIG:\n    pass',
    'try:\n    call()\nexcept Exception as CONFIG:\n    pass',
    'match value:\n    case {"key": CONFIG}:\n        pass',
    'match value:\n    case {**CONFIG}:\n        pass',
    'match value:\n    case [*CONFIG]:\n        pass',
    'values = [(CONFIG := value) for value in []]',
    'if flag:\n    CONFIG = {}',
    'class Wrapper:\n    global CONFIG\n    CONFIG = {}',
    'def replace():\n    global CONFIG\n    CONFIG = {}',
    'def replace():\n    if condition:\n        global CONFIG\n    CONFIG = {}',
])
def test_global_binding_forms_are_detected(prefix):
    result = check_public_contract(prefix + '\ndef f():\n    return CONFIG\n', _requirements())
    assert 'public.external_binding_rebound:CONFIG' in _ids(result)


@pytest.mark.parametrize('prefix', [
    'def local(CONFIG):\n    CONFIG = {}\n    return CONFIG',
    'def local():\n    CONFIG = {}\n    return CONFIG',
    'def local():\n    import json as CONFIG\n    return CONFIG',
    'def local():\n    def CONFIG():\n        pass\n    return CONFIG',
    'class Wrapper:\n    CONFIG = {}',
    'class Wrapper:\n    def method(self):\n        CONFIG = {}\n        return CONFIG',
    'def outer():\n    CONFIG = {}\n    def inner():\n        nonlocal CONFIG\n        CONFIG = []\n    return inner',
    'values = [CONFIG for CONFIG in []]',
    'values = {CONFIG: CONFIG for CONFIG in []}',
    'def local():\n    return [(CONFIG := value) for value in []]',
    'CONFIG: dict',
    'CONFIG = CONFIG',
    'CONFIG["entry"] = 3',
    'CONFIG.value = 3',
    'if False:\n    CONFIG = {}',
    'if "CONFIG" not in globals():\n    CONFIG = {}',
    'if "CONFIG" in globals():\n    pass\nelse:\n    CONFIG = {}',
    'if not "CONFIG" in globals():\n    CONFIG = {}',
])
def test_local_shadowing_and_legal_initialization_are_not_global_overwrites(prefix):
    result = check_public_contract(prefix + '\ndef f():\n    return CONFIG\n', _requirements())
    assert result['status'] == 'pass', result


def test_global_import_inside_function_is_not_mistaken_for_local_alias():
    code = 'def f():\n    global CONFIG\n    import json as CONFIG\n    return CONFIG\n'
    assert 'public.external_binding_rebound:CONFIG' in _ids(check_public_contract(code, _requirements()))


def test_nested_global_declaration_does_not_leak_to_outer_local_assignment():
    code = ('def f():\n    CONFIG = {}\n    def read():\n        global CONFIG\n        return CONFIG\n'
            '    return read\n')
    assert check_public_contract(code, _requirements())['status'] == 'pass'


def test_default_expression_is_evaluated_in_outer_scope():
    code = 'def helper(value=(CONFIG := {})):\n    return value\ndef f():\n    return CONFIG\n'
    assert 'public.external_binding_rebound:CONFIG' in _ids(check_public_contract(code, _requirements()))


def test_shadowed_globals_function_does_not_justify_safe_fallback():
    code = ('def globals():\n    return {}\nif "CONFIG" not in globals():\n    CONFIG = {}\n'
            'def f():\n    return CONFIG\n')
    assert 'public.external_binding_rebound:CONFIG' in _ids(check_public_contract(code, _requirements()))


def test_violation_identity_does_not_depend_on_lines_and_duplicate_writes_coalesce():
    first = check_public_contract('CONFIG = 1\nCONFIG = 2\ndef f():\n    pass\n', _requirements())
    moved = check_public_contract('\n\nCONFIG = 1\nCONFIG = 2\ndef f():\n    pass\n', _requirements())
    assert _ids(first) == _ids(moved) == {'public.external_binding_rebound:CONFIG'}
    assert len(first['violations']) == len(moved['violations']) == 1
    assert first['violations'][0]['locations'] == [1, 2]
    assert first['check_ids'] == moved['check_ids']
    assert first['contract_digest'] == moved['contract_digest']


def test_missing_entry_point_is_separate_from_unknown_signature():
    result = check_public_contract('def outer():\n    def f():\n        return 1\n', _requirements())
    assert _ids(result) == {'public.entrypoint_missing:f'}
    assert 'signature_not_unambiguous' in result['unmeasured']


@pytest.mark.parametrize('code', [
    'from package import f',
    'f = other_callable',
    'exec("def f(): return 1")',
    'from package import *',
])
def test_unresolved_callable_and_dynamic_binding_are_not_guessed(code):
    requirements = compile_public_contract({'entry_point': 'f', 'signature': 'f(value)'})
    result = check_public_contract(code, requirements)
    assert result['status'] == 'pass'
    assert 'entry_point_signature_not_statically_unique' in result['unmeasured']
    assert 'public.signature_mismatch:f' in result['unmeasured_check_ids']
    assert 'public.signature_mismatch:f' not in result['measured_check_ids']


def test_signature_from_public_python_scaffold_and_compatible_optional_extension():
    requirements = compile_public_contract({
        'entry_point': 'f',
        'description': 'import json\ndef f(value, mode="json", *, strict=False):\n    """Documented interface."""\n',
    })
    assert requirements['signature']['mode'] == 'python_signature'
    code = 'def f(value, mode="json", *, strict=False, extra=None):\n    return value\n'
    assert check_public_contract(code, requirements)['status'] == 'pass'


@pytest.mark.parametrize('signature', [
    'f(other, mode="json", *, strict=False)',
    'f(value, mode, *, strict=False)',
    'f(value, mode="yaml", *, strict=False)',
    'f(value, mode="json", extra=1, /, *, strict=False)',
    'f(value, mode="json", *, strict=False, required)',
])
def test_incompatible_public_call_forms_or_defaults_fail(signature):
    requirements = compile_public_contract({'entry_point': 'f', 'signature': 'f(value, mode="json", *, strict=False)'})
    result = check_public_contract('def ' + signature + ':\n    return value\n', requirements)
    assert 'public.signature_mismatch:f' in _ids(result)


def test_public_keyword_only_positional_only_variadic_and_async_are_preserved():
    requirements = compile_public_contract({'entry_point': 'f', 'signature': 'async def f(value, /, *args, flag=False, **kwargs)'})
    valid = 'async def f(value, /, *args, flag=False, **kwargs):\n    return value\n'
    assert check_public_contract(valid, requirements)['status'] == 'pass'
    assert 'public.signature_mismatch:f' in _ids(check_public_contract(valid.replace('async def', 'def'), requirements))
    assert 'public.signature_mismatch:f' in _ids(check_public_contract(valid.replace('*args, ', ''), requirements))


def test_public_documented_names_parse_both_plt_conventions():
    requirements = compile_public_contract({'function_name': 'f', 'arguments': '- str, user_id: identifier\n- dict, user_data: contents'})
    assert requirements['signature']['names'] == ['user_id', 'user_data']
    assert check_public_contract('def f(user_id, user_data, optional=None):\n    pass', requirements)['status'] == 'pass'
    assert 'public.signature_mismatch:f' in _ids(check_public_contract('def f(user_data, user_id):\n    pass', requirements))


@pytest.mark.parametrize('arguments', [
    '- data_bytes: bytes, payload\n- format_string: str, format\nformat_string is optional and defaults to "json" when omitted.',
    'Pass the value to the function.',
    '- value: str, payload\n- value: str, duplicate definition',
])
def test_ambiguous_prose_does_not_generate_signature_constraints(arguments):
    requirements = compile_public_contract({'entry_point': 'f', 'arguments': arguments})
    assert requirements['signature'] is None


def test_overwritten_or_multiple_entry_definitions_have_unknown_signature():
    requirements = compile_public_contract({'entry_point': 'f', 'signature': 'f(value)'})
    code = 'def f(wrong, other):\n    pass\nf = supplied_callable\n'
    result = check_public_contract(code, requirements)
    assert result['status'] == 'pass'
    assert 'entry_point_signature_not_statically_unique' in result['unmeasured']


def test_lambda_entry_interface_can_be_checked():
    requirements = compile_public_contract({'entry_point': 'f', 'signature': 'f(value)'})
    assert check_public_contract('f = lambda value: value', requirements)['status'] == 'pass'
    assert 'public.signature_mismatch:f' in _ids(check_public_contract('f = lambda other: other', requirements))


def test_syntax_failure_is_measured_and_keeps_same_predeclared_check_ids():
    requirements = _requirements()
    invalid = check_public_contract('def f(:\n    return CONFIG\n', requirements)
    valid = check_public_contract('def f():\n    return CONFIG\n', requirements)
    assert invalid['measured'] and invalid['status'] == 'fail'
    assert _ids(invalid) == {'public.syntax_invalid:python'}
    assert invalid['check_ids'] == valid['check_ids']
    assert invalid['contract_digest'] == valid['contract_digest']
    assert invalid['measured_check_ids'] == ['public.syntax_invalid:python']
    assert set(valid['measured_check_ids']) == set(valid['check_ids'])


@pytest.mark.parametrize('code', ['def f():\n    pass', 'def f(:', 'exec(source)', 'CONFIG = {}\ndef f():\n    pass'])
def test_measured_and_unknown_rules_partition_the_frozen_scope(code):
    result = check_public_contract(code, _requirements())
    measured = set(result['measured_check_ids'])
    unknown = set(result['unmeasured_check_ids'])
    assert measured.isdisjoint(unknown)
    assert measured | unknown == set(result['check_ids'])
    assert _ids(result) <= measured


def test_alias_cannot_hide_signature_failure_as_measured_improvement():
    requirements = compile_public_contract({'entry_point': 'f', 'signature': 'f(value)'})
    original = check_public_contract('def f(wrong, extra):\n    pass', requirements)
    alias = check_public_contract('f = other_callable', requirements)
    assert 'public.signature_mismatch:f' in _ids(original)
    assert 'public.signature_mismatch:f' in original['measured_check_ids']
    assert 'public.signature_mismatch:f' in alias['unmeasured_check_ids']


def test_python_scope_compile_error_is_detected_without_execution():
    code = 'def f():\n    CONFIG = {}\n    global CONFIG\n'
    assert _ids(check_public_contract(code, _requirements())) == {'public.syntax_invalid:python'}


def test_static_checker_does_not_execute_candidate(tmp_path):
    marker = tmp_path / 'candidate_was_run'
    code = f'from pathlib import Path\nPath({str(marker)!r}).touch()\ndef f():\n    return CONFIG\n'
    assert check_public_contract(code, _requirements())['status'] == 'pass'
    assert not marker.exists()


def test_hidden_fields_are_not_read_serialized_or_used_for_rules():
    class ForbiddenValue:
        def __repr__(self):
            raise AssertionError('hidden field was read')

    hidden = ForbiddenValue()
    task = {'task_description': dict(TASK_1003), 'setup': hidden, 'tests': hidden, 'reference': hidden,
            'test': hidden, 'Entry_Point': 'hidden_entry', 'context': 'SECRET: an externally supplied object.'}
    requirements = compile_public_contract(task)
    assert requirements == compile_public_contract(TASK_1003)
    assert 'SECRET' not in json.dumps(requirements)


def test_conflicting_entry_points_are_unknown_and_non_python_is_unmeasured():
    conflict = compile_public_contract({'entry_point': 'f', 'function_name': 'g'})
    assert conflict['entry_point'] == ''
    other = compile_public_contract({'language': 'go', 'entry_point': 'f'})
    result = check_public_contract('package main', other)
    assert result['measured'] is False and result['status'] == 'unmeasured'
    assert result['violations'] == []


def test_feedback_whitelist_does_not_forward_code_hidden_fields_or_score():
    result = check_public_contract('CONFIG = {}\ndef f():\n    pass\n', _requirements())
    result.update(code='private candidate text', setup='private setup', joint=True)
    result['violations'][0].update(private_payload='private hidden value')
    feedback = contract_check_feedback(result)
    text = json.dumps(feedback)
    assert 'private' not in text and 'joint' not in text
    assert feedback['violations'][0]['id'] == 'public.external_binding_rebound:CONFIG'

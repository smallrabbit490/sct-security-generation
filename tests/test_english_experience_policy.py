"""英文提示词与经验准入边界；不把代码、证据或来源当作可翻译文本。"""
import importlib
import json

import pytest


def policy():
    return importlib.import_module('methods.sct_trajectory.english_policy')


def test_templates_and_rendering_are_english():
    from methods.sct_trajectory.agent_pipeline import analyze_prompt, planning_prompt, generation_prompt, previous_evidence_block, dual_track_text
    from methods.sct_trajectory.distillation import build_round_prompt, build_distillation_prompt, state_to_failure_type
    from methods.sct_trajectory.active_replay import build_scheduler_prompt
    from methods.sct_trajectory.error_ledger import ErrorLedger
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.gate_selector import build_selector_prompt
    task = {'description': 'Return a safe value.', 'source_code': 'def f(): pass'}
    card = {'kind': 'direct_A', 'principle': 'Preserve valid inputs.', 'root_cause': 'No failure.', 'fix_directive': 'Use parameterized queries.'}
    prompts = [analyze_prompt(task), planning_prompt('Analyze the contract.', [card], task, anti_overdefense=True, contract_freeze=True), generation_prompt('Keep the API.', [card], task, 'def f(): pass'), previous_evidence_block({'error': 'timeout'}), dual_track_text([card]), build_round_prompt(cwe='CWE-89', round_index=1, state='C', code='pass', evidence={'functional': {'status': 'fail', 'details': 'Mismatch'}}), build_distillation_prompt(cwe='CWE-89', kind='C_to_A', before='C', after='A', code_before='pass', code_after='pass', patch_diff='', failure_type=state_to_failure_type('C')), build_scheduler_prompt(HskTree(), ErrorLedger(), []), build_selector_prompt([], [])]
    for prompt in prompts:
        assert not any('\u3400' <= char <= '\u9fff' for char in prompt), prompt[:300]


def test_experience_requires_explicit_translation_preserves_nonprose():
    p = policy()
    card = {'invariant_id': 'id-中文', 'positive_principle': '保持功能', 'source': {'task_id': '中文-id', 'fix_directive': '使用参数查询', 'code': 'x = "中文"', 'evidence': {'details': '中文报错'}}, 'language_leaves': {'python': {'safe_constructs': ['参数查询'], 'pattern_snippet': 'x = "中文"'}}}
    with pytest.raises(p.EnglishPolicyError):
        p.assert_english_experience(card)
    with pytest.raises(p.EnglishPolicyError):
        p.normalize_experience(card)
    seen = []
    def translate(fields):
        seen.extend(fields.values())
        return {key: {'保持功能': 'Preserve functionality.', '使用参数查询': 'Use parameterized queries.', '参数查询': 'Parameterized queries.'}[value] for key, value in fields.items()}
    actual = p.normalize_experience(card, translator=translate)
    p.assert_english_experience(actual)
    assert card['positive_principle'] == '保持功能'
    assert actual['invariant_id'] == card['invariant_id']
    assert actual['source']['code'] == card['source']['code']
    assert actual['source']['evidence'] == card['source']['evidence']
    assert actual['language_leaves']['python']['pattern_snippet'] == 'x = "中文"'
    assert len(seen) == 3


def test_translation_rejects_missing_or_extra_fields_and_remaining_chinese():
    p = policy()
    for translator in (lambda fields: {}, lambda fields: {**fields, '/unapproved': 'x'}, lambda fields: fields):
        with pytest.raises(p.EnglishPolicyError):
            p.normalize_experience({'fix_directive': '保留契约'}, translator=translator)


def test_seed_nested_adaptation_and_track_rules_cannot_bypass_language_check():
    p = policy()
    for card in ({'recommended_action': '参数查询'}, {'dangerous_pattern': '拼接输入'},
                 {'unsafe_alternative': '直接执行'}, {'non_applicable_boundary': '只读场景'},
                 {'exclusion_conditions': ['无输入']}, {'language_adaptation': {'python': '参数化'}},
                 {'track_rules': [{'text': '保持功能'}]}):
        with pytest.raises(p.EnglishPolicyError):
            p.assert_english_experience(card)


def test_distillation_rejects_nonenglish_candidate_before_admission():
    from methods.sct_trajectory.distillation import distill_transition
    response = {'choices': [{'message': {'content': json.dumps({'positive_principle': '保留契约'})}}]}
    actual = distill_transition(cwe='CWE-89', kind='direct_A', before='A', after='A', code_before='', code_after='pass', requester=lambda _: response)
    assert actual.get('error') == 'EnglishPolicyError'
    assert not actual.get('positive_principle')


def test_language_leaf_rejects_nonenglish_prose_but_preserves_code():
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.level4 import generate_level4, build_level4_prompt
    config = get_config('A5')
    response = {'choices': [{'message': {'content': json.dumps({'python': {'safe_constructs': ['使用参数查询']}})}}]}
    leaves, error = generate_level4(cwe='CWE-89', invariant='Preserve functionality.', requester=lambda _: response, config=config)
    assert not leaves and error == 'EnglishPolicyError'
    assert not any('\u3400' <= char <= '\u9fff' for char in build_level4_prompt(cwe='CWE-89', invariant='Preserve functionality.', config=config))


def test_english_historical_directives_keep_contradiction_detection():
    from methods.sct_trajectory.payload_quality import payload_flags
    from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
    node = SecurityInvariantNode('e1', '22', 'Preserve functionality.',
        source={'fix_directive': 'Add a length limit. —— Remove the length limit because the contract does not require it.'})
    assert 'possible_contradiction' in payload_flags(node)


def test_success_context_uses_kind_not_unreliable_localized_substring():
    from methods.sct_trajectory.agent_pipeline import dual_track_text
    text = dual_track_text([{'kind': 'direct_A', 'root_cause': 'No failure.', 'fix_directive': 'Keep the existing parameter binding.'}])
    assert '[Observed successful approach' in text
    assert '[Failure context' not in text


def test_model_analysis_and_plan_prose_must_be_english():
    from methods.sct_trajectory.agent_pipeline import parse_analysis, parse_planning
    p = policy()
    with pytest.raises(p.EnglishPolicyError):
        parse_analysis(json.dumps({'vulnerability_hypothesis': ['SQL injection'], 'functional_invariants': ['保持输入']}))
    with pytest.raises(p.EnglishPolicyError):
        parse_planning(json.dumps({'Preserved_Func': '保持契约', 'Patch_Scope': 'Bind parameters', 'Avoidance_List': []}))


def test_pipeline_language_failure_does_not_leak_invalid_analysis_to_next_call():
    from methods.sct_trajectory.agent_pipeline import run_pipeline
    calls = []
    def request(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            payload = {'vulnerability_hypothesis': ['SQL injection'], 'functional_invariants': ['保持输入']}
        elif len(calls) == 2:
            assert '保持输入' not in prompt
            payload = {'Preserved_Func': 'Preserve input', 'Patch_Scope': 'Keep the API', 'Avoidance_List': []}
        else:
            return {'choices': [{'message': {'content': 'def f(x): return x'}}]}
        return {'choices': [{'message': {'content': json.dumps(payload, ensure_ascii=False)}}]}
    actual = run_pipeline({'description': 'Return input.', 'language': 'python'}, [], requester=request)
    assert 'analysis:non_english_natural_language' in actual['error_type']


def test_internal_checks_do_not_forward_nonenglish_generated_purpose():
    from methods.sct_trajectory.internal_checks import propose_checks
    calls = []
    def request(prompt):
        calls.append(prompt)
        value = {'cases': [{'id': 'f1', 'kind': 'functional', 'purpose': '合法输入',
                            'code': 'assert candidate(1) == 1'}]}
        return {'choices': [{'message': {'content': json.dumps(value)}}]}
    actual = propose_checks({'description': 'Return input'}, {}, request)
    assert actual['cases'] == []
    assert actual['errors'] == ['non_english_case_purpose']
    assert len(calls) == 1


def test_seed_default_prompt_and_output_are_english_with_literal_preservation():
    from methods.sct_lifecycle_replay.source_knowledge import build_prompt, extract_initial_hypothesis
    row = {'index': 1, 'CWE_ID': '22', 'task_description': {'description': 'Return exact input'},
           'ground_truth': {'vulnerable_code': 'value = "中文"', 'patched_code': 'value = "中文"'}}
    prompt = build_prompt(row)
    assert 'Return JSON ONLY' in prompt
    assert 'value = "中文"' in prompt
    value = {'principle': 'Preserve input', 'applicability': 'Text processing', 'language_adaptation': {'python': '保留输入'}}
    with pytest.raises(policy().EnglishPolicyError):
        extract_initial_hypothesis(row, lambda prompt: {'choices': [{'message': {'content': json.dumps(value)}}]})
    with pytest.raises(ValueError, match='english_only'):
        build_prompt(row, output_language='zh')


def test_error_ledger_generated_warning_is_english():
    from methods.sct_trajectory.error_ledger import ErrorLedger, ErrorEntry
    ledger = ErrorLedger()
    ledger.add(ErrorEntry('22', 'D_stalled', 'both_failed', 'hash'))
    warnings = ledger.analysis_warning('22')
    assert warnings and not policy().contains_cjk(warnings[0])
    assert 'both_failed' in warnings[0]

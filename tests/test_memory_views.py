"""功能安全视图的事实守恒、排除正文不泄漏及原P7路径验证；不调用在线模型。"""
import copy
import json

import pytest

from methods.sct_trajectory.context_pipeline import experience_text, run_context_pipeline
from methods.sct_trajectory.memory_views import apply_memory_view, draft_view


def card_and_spec():
    card = {'invariant_id': 'view-card', 'kind': 'direct_A', 'status': 'active',
            'positive_principle': 'KEEP_RETURN. ESCAPE_MARKUP.',
            'language_leaf': {'common_pitfalls': ['KEEP_ARGUMENT'], 'safe_sinks': ['SECURE_SINK']}}
    spec = draft_view(card)
    spec['review_status'] = 'reviewed'
    segments = []
    for segment in spec['segments']:
        if segment['path'] == ['positive_principle']:
            segments.extend([{**segment, 'end': 13, 'role': 'functional'},
                             {**segment, 'start': 13, 'role': 'security'}])
        else:
            segments.append({**segment, 'role': 'functional' if 'common_pitfalls' in segment['path'] else 'security'})
    spec['segments'] = segments
    return card, spec


def test_original_and_no_memory_modes_preserve_default_and_do_not_mutate_source():
    card, spec = card_and_spec()
    before = copy.deepcopy(card)
    assert experience_text(apply_memory_view([card], 'BM')) == experience_text([card])
    assert experience_text(apply_memory_view([card], 'B0')) == '[]'
    apply_memory_view([card], 'BFS', {card['invariant_id']: spec})
    assert card == before


@pytest.mark.parametrize('mode,present,absent', [
    ('BF', ['KEEP_RETURN', 'KEEP_ARGUMENT'], ['ESCAPE_MARKUP', 'SECURE_SINK']),
    ('BS', ['ESCAPE_MARKUP', 'SECURE_SINK'], ['KEEP_RETURN', 'KEEP_ARGUMENT']),
    ('BFS', ['KEEP_RETURN', 'KEEP_ARGUMENT', 'ESCAPE_MARKUP', 'SECURE_SINK'], []),
])
def test_only_selected_view_reaches_reanalysis_planning_and_generation(mode, present, absent):
    card, spec = card_and_spec()
    viewed = apply_memory_view([card], mode, {card['invariant_id']: spec})
    initial = {'vulnerability_hypothesis': ['input risk'], 'functional_invariants': ['complete interface']}
    answers = [{**initial, 'applied_experience_ids': ['view-card']},
               {'Preserved_Func': 'complete interface', 'Patch_Scope': 'implement'},
               'def f(value): return value']
    seen = []
    def requester(prompt):
        seen.append(prompt)
        answer = answers.pop(0)
        return {'choices': [{'message': {'content': json.dumps(answer) if isinstance(answer, dict) else answer}}]}
    result = run_context_pipeline({'function_name': 'f', 'description': 'Return value.'}, viewed,
                                  requester=requester, initial_analysis=initial)
    assert result['workflow_completed']
    assert len(seen) == 3
    for prompt in seen:
        assert all(text in prompt for text in present)
        assert all(text not in prompt for text in absent)


def test_bfs_contains_every_source_fragment_exactly_once():
    card, spec = card_and_spec()
    viewed = json.loads(experience_text(apply_memory_view([card], 'BFS', {'view-card': spec})))[0]
    content = viewed['functional_preservation'] + viewed['security_action']
    assert ''.join(x['text'] for x in content if x['source_path'] == ['positive_principle']) == card['positive_principle']
    assert len([x for x in content if x['text'] == 'KEEP_ARGUMENT']) == 1


def test_unreviewed_or_gapped_annotations_cannot_enter_view():
    card, spec = card_and_spec()
    draft = draft_view(card)
    with pytest.raises(ValueError, match='not_reviewed'):
        apply_memory_view([card], 'BF', {'view-card': draft})
    spec['segments'][0]['start'] = 1
    with pytest.raises(ValueError, match='exactly_partitioned'):
        apply_memory_view([card], 'BFS', {'view-card': spec})


def test_applicability_context_is_shared_without_reclassifying_it_as_an_action():
    card, spec = card_and_spec()
    card['applicability'] = 'COMMON_SCOPE'
    spec['segments'].append({'path': ['applicability'], 'start': 0, 'end': len('COMMON_SCOPE'), 'role': 'context'})
    for mode in ['BF', 'BS', 'BFS']:
        rendered = json.loads(experience_text(apply_memory_view([card], mode, {'view-card': spec})))[0]
        assert rendered['applicability_and_source_context'] == [{'source_path': ['applicability'], 'text': 'COMMON_SCOPE'}]


@pytest.mark.parametrize('mode', ['B0', 'BF', 'BS', 'BFS', 'BM'])
def test_original_p7_repairs_once_uses_last_code_and_keeps_empty_memory_empty(mode):
    from methods.cle_ablation import runner
    card, spec = card_and_spec()
    initial = {'vulnerability_hypothesis': ['input risk'], 'functional_invariants': ['return exact value']}
    task = {'index': 991, 'CWE_ID': '79', 'task_description': {'function_name': 'f',
            'arguments': 'value: str', 'description': 'Return value unchanged.'},
            'unittest': {'setup': '', 'testcases': "testcases = {'capability': [({'value': 'x'}, 'x')], 'safety': [({'value': '<x>'}, '<x>')]}"},
            'install_requires': []}
    codes = iter(['def f(value): return None', 'def f(value): return value'])
    prompts, providers = [], []
    def requester(prompt):
        prompts.append(prompt)
        if prompt.startswith('Generate complete'):
            response = next(codes)
        elif prompt.startswith('Plan'):
            response = json.dumps({'Preserved_Func': 'return value', 'Patch_Scope': 'return unchanged'})
        else:
            response = json.dumps({**initial, 'applied_experience_ids': [] if mode == 'B0' else ['view-card']})
        return {'choices': [{'message': {'content': response}}],
                'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
    def provider(query):
        providers.append(query)
        return apply_memory_view([card], mode, {'view-card': spec}), {'selected_ids': [] if mode == 'B0' else ['view-card']}
    row = runner.run_one('PLT', task, 'P7', requester, {'full': []},
                         retrieval_provider=provider, initial_analysis=initial)
    assert len(row['attempts']) == 2
    assert not row['attempts'][0]['joint'] and row['attempts'][-1]['joint']
    assert row['attempts'][-1]['code'] == 'def f(value): return value'
    assert len(providers) == 2
    if mode == 'B0':
        assert not any('KEEP_RETURN' in p or 'ESCAPE_MARKUP' in p for p in prompts)
        assert all(not a['generation']['cards'] for a in row['attempts'])

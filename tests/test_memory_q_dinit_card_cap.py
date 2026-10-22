"""不限量D_init的采用、记分、共同候选和旧三张边界验证，零API。"""
import copy
import pytest

from methods.cle_ablation import run_memory_q_dinit_card_cap as study
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
from methods.sct_trajectory.context_pipeline import adopt_experiences


def fixture():
    nodes = [SecurityInvariantNode.from_dict({'invariant_id': str(i), 'cwe': '22'}) for i in range(6)]
    origins = {str(i): {'known_source_families': ['other']} for i in range(6)}
    origins['0']['known_source_families'] = ['here']
    cards = [{'invariant_id': str(i)} for i in range(5)]
    adopted, _ = adopt_experiences(cards, {'applied_experience_ids': ['0','1','2','3','4','4'],
                                         'rejected_experiences': [{'id':'1','reason':'conflicts'}]})
    attempt = {'attempt': 0, 'code': 'x=1', 'measured': True, 'joint': True,
        'generation': {'workflow_completed': True, 'retrieved_cards': cards, 'cards': adopted},
        'validation': {'evidence': {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}},
        'retrieval_trace': {'status': 'completed', 'selection_limit': None}}
    row = {'task_id': '1', 'family_id': 'here', 'pool': 'D_init', 'arm': 'Lall',
           'attempts': [attempt], 'final': attempt}
    return nodes, origins, row, {'learning': ['1'], 'task_families': {'1': 'here'}}


def test_fifth_card_credits_and_rejected_unused_cards_do_not():
    nodes, origins, row, manifest = fixture()
    before = [n.to_dict() for n in nodes]
    learned, events, stats = study.credit_rows([row], nodes, origins, manifest, 'all_feedback')
    assert [n.q_visits for n in learned] == [1,0,1,1,1,0]
    assert learned[4].q_value == pytest.approx(.3)
    assert stats['valid_updates'] == 4
    assert [e['selected_position'] for e in events] == [1,3,4,5]
    assert before == [n.to_dict() for n in nodes]
    assert not study.inspect(row)


def test_cross_family_filters_self_without_cap_and_failure_still_learns():
    nodes, origins, row, manifest = fixture()
    second = copy.deepcopy(row['attempts'][0])
    second['attempt'] = 1
    second['joint'] = False
    second['validation']['evidence']['functional']['status'] = 'fail'
    row['attempts'][0]['joint'] = False  # 本例只检查授信公式，不调用交付协议检查。
    row['attempts'].append(second)
    row['final'] = second
    learned, events, stats = study.credit_rows([row], nodes, origins, manifest, 'cross_family')
    assert learned[0].q_visits == 0
    assert learned[4].q_visits == 2 and learned[4].q_value == pytest.approx(-.09)
    assert stats['valid_updates'] == 6


def test_unmeasured_and_out_of_pool_are_not_credited():
    nodes, origins, row, manifest = fixture()
    row['attempts'][0]['measured'] = False
    learned, events, stats = study.credit_rows([row], nodes, origins, manifest, 'all_feedback')
    assert stats['valid_updates'] == 0 and not any(n.q_visits for n in learned)
    row['pool'] = 'D_gate'
    with pytest.raises(ValueError, match='D_init_only'):
        study.credit_rows([row], nodes, origins, manifest, 'all_feedback')


def test_old_three_card_arm_stays_capped_and_unknown_adoption_rejected():
    nodes, origins, row, manifest = fixture()
    row['arm'] = 'L3'
    with pytest.raises(ValueError, match='L3_exceeds_three'):
        study.credit_rows([row], nodes, origins, manifest, 'all_feedback')
    row['arm'] = 'Lall'
    row['attempts'][0]['generation']['cards'].append({'invariant_id': '5'})
    with pytest.raises(ValueError, match='invalid_actual_adoption'):
        study.credit_rows([row], nodes, origins, manifest, 'all_feedback')


def test_pair_check_includes_presentation_order():
    _, _, row, _ = fixture()
    other = copy.deepcopy(row)
    other['arm'] = 'L3'
    for r in (row, other):
        r['attempts'][0]['retrieval_trace'].update(candidate_ids=['a','b'], presented_candidate_ids=['a','b'])
    assert study.pair_checks([row, other])[0]['shared_candidates']
    other['attempts'][0]['retrieval_trace']['presented_candidate_ids'].reverse()
    assert not study.pair_checks([row, other])[0]['shared_candidates']


def test_observed_long_candidate_prompt_uses_explicit_budget_without_cutting_cards(monkeypatch):
    from methods.sct_trajectory import semantic_retrieval as retrieval
    from methods.sct_trajectory.hsk_tree import LanguageLeaf
    import json
    nodes = [SecurityInvariantNode(str(i), '22', 'Preserve paths. ' + 'x'*9000,
        language_leaves={'python': LanguageLeaf('python')}) for i in range(24)]
    class Vectors:
        model = 'offline'
        def cosine_scores(self, query, texts):
            return [.99-i*.001 for i in range(len(texts))]
    prompts = []
    def request(prompt):
        prompts.append(prompt)
        return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'selected':[1,2,3,4,5,6]})}}]}
    monkeypatch.setattr(retrieval, 'MAX_SELECTOR_CHARS', 180000)
    chosen, trace = retrieval.semantic_select({'description':'Preserve paths','language':'python'},
        nodes, request, Vectors(), limit=None)
    assert not chosen and trace['errors'] == ['selector_prompt_budget_exceeded'] and not prompts
    monkeypatch.setattr(retrieval, 'MAX_SELECTOR_CHARS', 420000)
    chosen, trace = retrieval.semantic_select({'description':'Preserve paths','language':'python'},
        nodes, request, Vectors(), limit=None)
    assert trace['status']=='completed' and len(chosen)==6
    assert len(trace['candidate_ids'])==24 and 180000 < len(prompts[0]) < 420000

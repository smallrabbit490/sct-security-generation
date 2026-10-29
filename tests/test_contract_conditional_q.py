"""条件Q接线、两臂共享公开输入、冻结边界与扩大门的离线验证；不调用API。"""
import copy
import json
import pytest

from configs.cle_contract_q_20261023.prepare import fisher_exact
from methods.cle_ablation import joint_contract as consumer
from methods.cle_ablation.conditional_q import make_router, paired_screen, check_common_first_retrieval
from methods.cle_ablation.run_joint_contract import RequestBudget, BudgetExceeded
from methods.sct_trajectory.hsk_tree import LanguageLeaf, SecurityInvariantNode


def fixture_task():
    return {'index': 'fixture', 'CWE_ID': '20', 'family_id': 'public_family',
            'task_description': {'description': 'Return x unchanged.', 'function_name': 'f',
                                 'arguments': [{'name': 'x', 'type': 'int'}], 'return': 'Same integer.'},
            'test_cases': 'HIDDEN_TEST_SENTINEL', 'ground_truth': {'patched_code': 'HIDDEN_REFERENCE_SENTINEL'}}


def bank():
    return [SecurityInvariantNode(i, '20', 'Preserve public inputs.', q_value=q, q_visits=3,
                language_leaves={'python': LanguageLeaf('python')}) for i, q in [('a', -1), ('b', 1)]]


class Embedding:
    model = 'offline_fixture'
    def cosine_scores(self, query, texts):
        return [.9, .8]


def choose_first(prompts):
    def request(prompt):
        prompts.append(str(prompt))
        return {'choices': [{'message': {'content': '{"selected":[1]}'}}]}
    return request


def test_q_changes_presented_id_and_actual_selection_but_stays_LLM_selected_and_frozen():
    memory = bank(); before = [n.to_dict() for n in memory]
    prompts = []
    # lambda .75 is a fixture to separate numeric orders; study protocol remains .5.
    providers = {order: consumer.make_provider(memory, choose_first(prompts), Embedding(),
                 candidate_order=order, lambda_q=.75) for order in ('similarity', 'q')}
    results = {order: provider(consumer.prepare_contract('PLT', fixture_task()))
               for order, (provider, _) in providers.items()}
    assert results['similarity'][0]['invariant_id'] == 'a'
    assert results['q'][0]['invariant_id'] == 'b'
    assert len(prompts) == 2 and all('at most 3' in p for p in prompts)
    assert all('q_value' not in p and 'HIDDEN_' not in p for p in prompts)
    assert [n.to_dict() for n in memory] == before
    assert providers['q'][1][0]['candidate_order'] == 'q'


def test_disabled_conditional_route_is_identical_to_similarity_prompt():
    memory = bank(); prompts = []
    policy = {'version': 'frozen-off', 'enabled': False, 'rules': [], 'reason': 'insufficient_evidence'}
    for order in ('similarity', make_router(policy)):
        provider, trace = consumer.make_provider(memory, choose_first(prompts), Embedding(), candidate_order=order)
        provider(consumer.prepare_contract('PLT', fixture_task()))
    assert prompts[0] == prompts[1]
    assert trace[0]['q_routing']['candidate_order'] == 'similarity'
    assert set(trace[0]['q_routing']['features']) == {
        'explicit_external_binding', 'signature_known', 'visited_fraction', 'negative_q_fraction',
        'max_visits', 'normalized_rank_displacement'}


def test_frozen_pre_generation_rule_can_route_q_without_observing_outcomes():
    router = make_router({'version': 'fixture-only', 'enabled': True,
        'rules': [{'feature': 'visited_fraction', 'op': 'ge', 'value': .5}]})
    nodes = {n.invariant_id: n for n in bank()}
    assert router({'description': 'Public only'}, [{'id': 'a', 'cosine': .9}, {'id': 'b', 'cosine': .8}], nodes)['candidate_order'] == 'q'


@pytest.mark.parametrize('feature', ['Joint', 'generated_code', 'adoption', 'hidden_tests'])
def test_outcome_features_are_rejected(feature):
    with pytest.raises(ValueError, match='forbidden'):
        make_router({'version': 'bad', 'enabled': True, 'rules': [{'feature': feature, 'op': 'eq', 'value': True}]})


def test_enabled_policy_without_rules_cannot_silently_use_q():
    with pytest.raises(ValueError, match='frozen_rules'):
        make_router({'version': 'bad', 'enabled': True, 'rules': []})


def test_semantic_q_cannot_masquerade_as_LLM_candidate_reordering():
    with pytest.raises(ValueError, match='LLM_selection'):
        consumer.make_provider(bank(), None, Embedding(), retrieval_mode='semantic_q', candidate_order='q')


def test_both_new_arms_share_the_same_suite_and_first_analysis_without_builder_calls():
    calls = []
    def builder(contract, analysis, request):
        assert 'HIDDEN_' not in json.dumps(contract)
        calls.append('suite')
        return {'cases': [{'id': 'one', 'kind': 'functional', 'purpose': 'Preserve input', 'code': 'assert candidate(1)==1'}]}
    shared = consumer.prepare_public_suite('PLT', fixture_task(), None, suite_builder=builder)
    original = copy.deepcopy(shared)
    initial = {'vulnerability_hypothesis': ['Preserve inputs'], 'functional_invariants': ['Identity']}
    seen = []
    def pipeline(contract, cards, **options):
        seen.append(copy.deepcopy(options['initial_analysis']))
        return {'code': 'def f(x): return x'}
    rows = [consumer.run_one('PLT', fixture_task(), None, None, public_suite=shared, initial_analysis=initial,
                pipeline=pipeline, suite_builder=lambda *a: pytest.fail('suite must be reused'),
                evaluator=lambda *a: {'measured': True, 'joint': True}) for _ in range(2)]
    assert calls == ['suite'] and seen == [initial, initial]
    assert shared == original and rows[0]['public_suite_sha256'] == rows[1]['public_suite_sha256']
    assert all(r['public_suite_reused'] and len(r['attempts']) == 1 for r in rows)


def test_empty_shared_suite_does_not_trigger_another_generation_of_suite():
    row = consumer.run_one('PLT', fixture_task(), None, None, public_suite={'cases': []},
        pipeline=lambda *a, **kw: {'code': 'def f(x): return 0'},
        suite_builder=lambda *a: pytest.fail('empty shared suite remains frozen'),
        evaluator=lambda *a: {'measured': True, 'joint': False})
    assert row['repair_skipped_reason'] == 'empty_public_suite'


def test_embedding_budget_blocks_before_the_next_request():
    budget = RequestBudget(100, 1_000_000, max_embedding_calls=1)
    budget.reserve('embedding', 'public', attempts=1, completion_cap=0)
    with pytest.raises(BudgetExceeded):
        budget.reserve('embedding', 'not sent', attempts=1, completion_cap=0)
    assert budget.reserved_embedding_calls == 1


def test_38_case_fisher_does_not_invent_finite_OR_or_pass_proposal_gate():
    value = fisher_exact([[2, 16], [0, 20]])
    assert value['two_sided_p'] == pytest.approx(.2176386913)
    assert value['odds_ratio'] is None and value['odds_ratio_infinite']
    assert not value['proposal_gate_passed']


def test_screening_does_not_advance_incomplete_or_disabled_Q_comparison():
    result = paired_screen([], ['a', 'b'], 2, conditional_enabled=False)
    assert result['comparisons'][consumer.VARIANT]['decision'] == 'INCOMPLETE_NO_ADVANCEMENT'
    assert result['comparisons'][consumer.CONDITIONAL_VARIANT]['decision'] == 'Q_ROUTE_DISABLED_NOT_TESTED'


def test_joint_gain_with_opposing_repeats_does_not_pass_screen():
    rows = []
    for arm in ('P7', consumer.VARIANT, consumer.CONDITIONAL_VARIANT):
        for rep in range(2):
            for tid in ('a', 'b'):
                joint = (arm == 'P7' and rep == 1) or (arm != 'P7' and rep == 0)
                rows.append({'arm': arm, 'repeat': rep, 'task_id': tid, 'final': {'measured': True, 'joint': joint}})
    result = paired_screen(rows, ['a', 'b'], 2, conditional_enabled=True, bootstrap_samples=100)
    assert result['comparisons'][consumer.VARIANT]['decision'] == 'STOP'


def test_consistent_contract_gain_passes_only_development_gate_not_final_proof():
    rows = [{'arm': arm, 'task_id': tid, 'repeat': rep,
             'final': {'measured': True, 'joint': arm != 'P7'}}
            for arm in ('P7', consumer.VARIANT) for rep in range(2) for tid in ('a', 'b')]
    result = paired_screen(rows, ['a', 'b'], 2, conditional_enabled=False, bootstrap_samples=100)
    assert result['comparisons'][consumer.VARIANT]['decision'] == 'PASS_DEVELOPMENT_GATE_NOT_FINAL_PROOF'


def test_consistent_Q_gain_is_compared_to_contract_consumer_and_uses_cluster_interval():
    rows = [{'arm': arm, 'task_id': tid, 'repeat': rep,
             'final': {'measured': True, 'joint': arm == consumer.CONDITIONAL_VARIANT}}
            for arm in ('P7', consumer.VARIANT, consumer.CONDITIONAL_VARIANT)
            for rep in range(2) for tid in ('a', 'b')]
    result = paired_screen(rows, ['a', 'b'], 2, conditional_enabled=True, bootstrap_samples=100)
    q = result['comparisons'][consumer.CONDITIONAL_VARIANT]
    assert q['baseline'] == consumer.VARIANT and q['family_bootstrap_80pct'] == [1, 1]
    assert q['decision'] == 'PASS_DEVELOPMENT_GATE_NOT_FINAL_PROOF'


def test_restored_48_tasks_keep_identity_public_fields_and_references():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    source = root / 'translation_work/diagnostics/20261023/cle_contract_q/tasks_D_gate_48.json'
    restored = source.with_name('tasks_D_gate_48_restored_urls_v2.json')
    if not source.exists() or not restored.exists():
        pytest.skip('local source restoration artifacts not present in this checkout')
    old, new = [json.loads(p.read_text(encoding='utf-8')) for p in (source, restored)]
    assert len(old) == len(new) == len({t['family_id'] for t in new}) == 48
    changed = []
    for a, b in zip(old, new):
        assert a['index'] == b['index']
        if a != b:
            changed.append(str(a['index']))
            assert a['task_description'] == b['task_description']
            assert a['ground_truth'] == b['ground_truth']
            before = copy.deepcopy(a)
            before['unittest']['testcases'] = b['unittest']['testcases']
            assert before == b
    assert set(changed) == {'1322','1323','1082','1086','639'}


def test_changed_first_query_cannot_be_claimed_as_equal_candidate_Q_comparison():
    left = {'retrieval_traces': [{'status': 'completed', 'query_hash': 'same', 'candidate_ids': ['a'],
                                 'scores': [{'id': 'a', 'cosine': .8}]}]}
    right = copy.deepcopy(left)
    assert check_common_first_retrieval(left, right)['same_first_cosines']
    right['retrieval_traces'][0]['query_hash'] = 'different'
    with pytest.raises(RuntimeError, match='share_first_query'):
        check_common_first_retrieval(left, right)

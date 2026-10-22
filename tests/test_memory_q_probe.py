from methods.cle_ablation.report_memory_q_probe import attempt_readout
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
from methods.sct_trajectory.memory_q import rank_candidates


def case(scores, q_values, adopted):
    nodes = {str(i): SecurityInvariantNode(str(i), '22', 'rule', q_value=q, q_visits=1)
             for i, q in enumerate(q_values)}
    banks = {arm: nodes for arm in ('Q1', 'Q2', 'Q3')}
    ids = [s['id'] for s in rank_candidates(scores, {i: n.q_value for i, n in nodes.items()}, delta=.4, lambda_q=.5)]
    row = {'task_id': '1', 'family_id': 'f1', 'cwe': '22', 'arm': 'Q2', 'attempts': [{
        'attempt': 0, 'retrieval_trace': {'scores': scores, 'selected_ids': ids},
        'generation': {'cards': [{'invariant_id': i} for i in adopted],
            'retrieved_cards': [{'invariant_id': i} for i in ids], 'workflow_completed': True},
        'functional': True, 'security': False, 'joint': False, 'measured': True}]}
    return attempt_readout(row, banks, .4, .5)[0]


def test_readout_distinguishes_delivered_new_card_from_actual_adoption():
    scores = [{'id': str(i), 'cosine': .9-i*.01} for i in range(4)]
    used = case(scores, (0, -1, 0, 1), ['3'])
    assert used['set_changed_vs_sim'] and used['new_cards_adopted'] == ['3']
    assert used['removed_ids'] == ['1'] and used['nonzero_q_adopted'] == ['3']
    rejected = case(scores, (0, -1, 0, 1), [])
    assert rejected['added_ids'] == ['3'] and rejected['new_cards_adopted'] == []


def test_readout_preserves_order_only_intervention_and_empty_gate():
    scores = [{'id': str(i), 'cosine': .9-i*.01} for i in range(3)]
    ordered = case(scores, (-1, 1, 0), ['0', '1', '2'])
    assert ordered['order_changed_vs_sim'] and not ordered['set_changed_vs_sim']
    assert ordered['new_cards_adopted'] == []
    empty = case([], (0, -1, 1), [])
    assert empty['eligible_count'] == 0 and not empty['order_changed_vs_sim']


def test_failed_second_retrieval_does_not_reuse_previous_trace():
    banks = {a: {} for a in ('Q1', 'Q2', 'Q3')}
    row = {'task_id': '1', 'family_id': 'f', 'cwe': '22', 'arm': 'Q1', 'attempts': [{
        'attempt': 1, 'retrieval_trace': {'scores': [{'id': 'stale', 'cosine': .9}]},
        'generation': {'stages': [{'stage': 'retrieval', 'status': 'degraded',
            'retrieval_trace': {'status': 'error', 'scores': [], 'selected_ids': [],
                                'errors': ['embedding_input_budget_exceeded']}}]},
        'functional': False, 'security': True, 'joint': False, 'measured': True}]}
    result = attempt_readout(row, banks, .4, .5)[0]
    assert result['candidate_count'] == 0 and result['retrieval_status'] == 'error'
    assert result['trace_source'] == 'generation.stages.retrieval'

"""补充观察学习必须排除不完整流程，保存原卡正文，顺序授信而非重复授信。"""
import pytest
from configs.cle_dgrow_url_q_learning_20261020.run import credit_rows, trace_of
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode


def item(identifier, reward, completed=True):
    return {'task_id': identifier, 'family_id': 'family'+identifier, 'pool': 'D_grow',
            'attempts': [{'attempt': 0, 'code': 'def f(): pass',
                'generation': {'workflow_completed': completed, 'cards': [{'invariant_id': 'a'}]},
                'validation': {'evidence': {'functional': {'status': 'pass' if reward > 0 else 'fail'},
                                           'security': {'status': 'pass'}}}}]}


def test_observer_credits_actual_completed_adoption_in_numeric_order():
    source = [SecurityInvariantNode.from_dict({'invariant_id': 'a', 'q_value': 0, 'q_visits': 0})]
    after, events, support = credit_rows(source, [item('10', -1), item('2', 1), item('11', 1, False)], {})
    assert after[0].q_value == pytest.approx(-.09)
    assert after[0].q_visits == 2
    assert source[0].q_visits == 0
    assert support == {'a': ['family10', 'family2']}
    assert sum(e.get('reward') is not None for e in events) == 2


def test_current_retrieval_failure_does_not_borrow_prior_success():
    attempt = {'retrieval_trace': {'status': 'completed', 'scores': [1]},
               'generation': {'stages': [{'stage': 'retrieval', 'status': 'degraded'}]}}
    assert trace_of(attempt) == {'status': 'error'}

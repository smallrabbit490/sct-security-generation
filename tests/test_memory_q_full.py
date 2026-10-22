"""全D_grow编排：固定原P7、确定顺序归因、异常参考不奖励。"""
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode


def row(task, joint, family='f', complete=True):
    status = 'pass' if joint else 'fail'
    return {'task_id':str(task),'pool':'D_grow','family_id':family,'arm':'Q0',
            'attempts':[{'attempt':0,'code':'def f(): return 1',
              'validation':{'evidence':{'functional':{'status':status},'security':{'status':'pass'}}},
              'generation':{'workflow_completed':complete,'cards':[{'invariant_id':'used'}]}}]}


def test_replay_uses_declared_order_not_parallel_completion_order():
    from methods.cle_ablation.run_memory_q_full import replay_credits
    nodes=[SecurityInvariantNode('used','22','rule'),SecurityInvariantNode('unused','22','rule')]
    controls={str(i):{'reward_eligible':True,'exclusion_reasons':[]} for i in (1,2)}
    learned,events,families=replay_credits([row(2,False,'b'),row(1,True,'a')],nodes,controls,['1','2'],.3)
    assert abs(learned[0].q_value-(-.09))<1e-12
    assert [e['task_id'] for e in events]==['1','2']
    assert learned[0].q_visits==2 and learned[1].q_visits==0
    assert families['used']=={'a','b'}
    assert nodes[0].q_value==0 and nodes[0].q_visits==0


def test_invalid_reference_or_placeholder_preserves_native_row_and_skips_q():
    from methods.cle_ablation.run_memory_q_full import replay_credits
    nodes=[SecurityInvariantNode('used','22','rule')]
    original=row(1,True)
    controls={'1':{'reward_eligible':False,'exclusion_reasons':['reference_not_joint']}}
    learned,events,families=replay_credits([original],nodes,controls,['1'],.3)
    assert learned[0].q_visits==0 and events[0]['reward'] is None
    assert events[0]['skip_reason']=='reference_not_joint'
    assert original['attempts'][0]['generation']['workflow_completed']
    assert not families


def test_same_family_visits_are_not_independent_support():
    from methods.cle_ablation.run_memory_q_full import replay_credits
    nodes=[SecurityInvariantNode('used','22','rule')]
    controls={str(i):{'reward_eligible':True,'exclusion_reasons':[]} for i in (1,2)}
    learned,events,families=replay_credits([row(1,True),row(2,True)],nodes,controls,['1','2'],.3)
    assert learned[0].q_visits==2 and families['used']=={'f'}


def test_pipeline_error_cannot_punish_adopted_card():
    from methods.cle_ablation.run_memory_q_full import replay_credits
    nodes=[SecurityInvariantNode('used','22','rule')]
    controls={'1':{'reward_eligible':True,'exclusion_reasons':[]}}
    learned,events,_=replay_credits([row(1,False,complete=False)],nodes,controls,['1'],.3)
    assert learned[0].q_visits==0 and events[0]['reward'] is None


def test_full_pool_allows_sibling_tasks_without_changing_pool():
    from methods.cle_ablation.run_memory_q_full import require_full_pool
    require_full_pool(['1','2'],['1','2'])
    import pytest
    with pytest.raises(ValueError,match='entire D_grow'):
        require_full_pool(['1'],['1','2'])

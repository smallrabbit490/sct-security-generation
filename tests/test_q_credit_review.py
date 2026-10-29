"""Q影子复盘的分母、跨族方向和重复代码再奖惩，不调用模型。"""
import pytest
from configs.cle_memory_mechanisms_20261023.review_q_credit import family_patterns,join_events,attempt_statistics


def fixture():
    attempt={'attempt':0,'measured':True,'functional':False,'security':True,'joint':False,'code':'def f(): return 0',
             'validation':{'evidence':{'functional':{'status':'fail'},'security':{'status':'pass'}}},
             'generation':{'workflow_completed':True,'cards':[{'invariant_id':'a'},{'invariant_id':'b'}],
                           'retrieved_cards':[{'invariant_id':'a'},{'invariant_id':'b'}]}}
    row={'pool':'D_init','task_id':'1','family_id':'target','cwe':'20','attempts':[attempt],'_source_row':'rows:1'}
    events=[{'pool':'D_init','task_id':'1','family_id':'target','attempt':0,'invariant_id':i,
        'credited':True,'reward':-1.0,'q_before':0.0,'q_after':-.3,'_event_source':'events:1'} for i in ('a','b')]
    cards={i:{'source':{'task_id':'source'},'cwe':'20'} for i in ('a','b')}
    return [row],events,cards,{'source':'source-family'}


def test_card_events_are_not_independent_attempts():
    attempts,events=join_events(*fixture())
    summary,_=attempt_statistics(attempts,events)
    assert len(events)==2 and summary['credited_attempts']==1
    assert summary['credited_attempts_by_FS']=={'F-S+':1}
    assert summary['multi_card_credited_attempts']==1


def test_mixed_same_family_is_not_pure_cross_family_opposition():
    events=[{'family_id':'a','reward':1.0},{'family_id':'a','reward':-1.0},
            {'family_id':'b','reward':1.0}]
    result=family_patterns(events)
    assert result['mixed_families']==['a'] and not result['has_opposed_pure_families']
    result=family_patterns([{'family_id':'a','reward':1.0},{'family_id':'b','reward':-1.0}])
    assert result['has_opposed_pure_families']


def test_duplicate_code_can_generate_repeated_credit_without_new_task():
    rows,events,cards,families=fixture()
    from copy import deepcopy
    second=deepcopy(rows[0]['attempts'][0]);second['attempt']=1
    rows[0]['attempts'].append(second)
    events += [{**event,'attempt':1,'q_before':-.3,'q_after':-.51} for event in list(events)]
    attempts,joined=join_events(rows,events,cards,families)
    summary,duplicates=attempt_statistics(attempts,joined)
    assert summary['credited_tasks']==1 and summary['credited_attempts']==2
    assert summary['negative_reupdates_on_identical_code']==2
    assert len(duplicates)==1


@pytest.mark.parametrize('field,value',[('q_after',.1),('reward',1.0),('invariant_id','not-adopted')])
def test_invalid_link_or_update_is_not_silently_counted(field,value):
    rows,events,cards,families=fixture()
    events[0][field]=value
    with pytest.raises(ValueError):join_events(rows,events,cards,families)

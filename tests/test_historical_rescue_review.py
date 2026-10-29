"""成功结果不自动转成采用、完整工作流或正Q信用。"""
from configs.cle_memory_mechanisms_20261023.review_historical_rescues import (
    successful_credit_path,summarize)


def native(actual,complete):
    return {'task_id':'test','final':{'attempt':1,'measured':True,'joint':True,
        'generation':{'cards':[{'invariant_id':i} for i in actual],
            'retrieved_cards':[{'invariant_id':i} for i in actual],
            'adoption':{'applied_ids':actual},'workflow_completed':complete}}}


def test_joint_success_with_incomplete_workflow_keeps_skipped_Q():
    row=native(['card'],False)
    event={'task_id':'test','attempt':1,'invariant_id':'card','credited':False,
        'reward':None,'skip_reason':'incomplete_or_technical_measurement'}
    path=successful_credit_path(row,[event])
    assert path['Joint'] and not path['adoption_and_complete_workflow']
    assert path['credited_ids']==[] and path['events'][0]['reward'] is None


def test_success_without_adoption_cannot_become_a_card_path():
    path=successful_credit_path(native([],True),[])
    assert path['Joint'] and path['workflow_completed']
    assert not path['actual_ids'] and not path['adoption_and_complete_workflow']


def test_positive_Q_event_is_not_full_card_correctness_evidence():
    event={'task_id':'test','attempt':1,'invariant_id':'card','credited':True,'reward':1.0}
    path=successful_credit_path(native(['card'],True),[event])
    assert path['credited_ids']==['card'] and path['adoption_and_complete_workflow']
    assert 'card_is_correct' not in path and 'caused_rescue' not in path


def test_delivery_recovery_and_measured_rescue_have_separate_denominators():
    cases=[]
    for old_measured,adopted,complete in [(False,['card'],True),(True,[],True),(True,['card'],False)]:
        cases.append({'task_id':str(len(cases)),'old_final':{'measured':old_measured},
            'new_final':{'measured':True,'Joint':True},'primary_category':'synthetic',
            'new_credit_path':successful_credit_path(native(adopted,complete),[]),
            'old_pipeline_degradation':False,'saved_public_contract_equal':True})
    result=summarize(cases,[])
    assert result['historical_delivery_rescues']==3
    assert result['both_final_measured_rescues']==2
    assert result['new_final_adopted_and_workflow_complete']==1
    assert result['both_measured_adopted_and_workflow_complete']==0
    assert result['isolated_Q_rescues_identified'] is None

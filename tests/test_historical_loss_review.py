"""历史复盘计算的聚焦控制；不重跑真实诊断或模型。"""
import pytest

from configs.cle_memory_mechanisms_20261023.review_historical_losses import (
    attempted_adoption,paired_measurement,obligation_paths)
from configs.cle_memory_mechanisms_20261023 import review_historical_losses as review


def test_first_adoption_does_not_become_final_adoption():
    row={'attempts':[{'attempt':0,'measured':True,'functional':False,'security':True,'joint':False,
        'code':'first','generation':{'adoption':{'applied_ids':['a']},'cards':[{'invariant_id':'a'}]}},
        {'attempt':1,'measured':True,'functional':False,'security':True,'joint':False,
        'code':'last','generation':{'adoption':{'applied_ids':[]},'cards':[]}}]}
    result=attempted_adoption(row)
    assert result[0]['applied_ids']==['a'] and result[1]['applied_ids']==[]
    assert result[0]['actual_card_ids']==['a'] and result[1]['actual_card_ids']==[]


def test_measurement_sensitivity_preserves_full_delivery_denominator():
    rows=[{'task_id':'a','old_measured':'True','new_measured':'False',
        'old_joint_verified_native_and_pair_table':'True','new_joint_from_native':'False','transition':'loss'},
        {'task_id':'b','old_measured':'False','new_measured':'True',
        'old_joint_verified_native_and_pair_table':'False','new_joint_from_native':'True','transition':'rescue'},
        {'task_id':'c','old_measured':'True','new_measured':'True',
        'old_joint_verified_native_and_pair_table':'True','new_joint_from_native':'True','transition':'both_pass'}]
    result=paired_measurement(rows)
    assert result['all_delivery']['tasks']==3
    assert result['both_final_measured']=={'tasks':1,'old_joint':1,'new_joint':1,'transitions':{'both_pass':1}}
    assert len(result['unmeasured_pairs'])==2


def test_missing_card_quote_cannot_be_recorded_as_a_verified_path():
    pairs={'1241':{'new':{'attempt':1,'code':'PATIENT_RECORDS = {}',
        'adopted_card_bodies':[{'invariant_id':'cand-863-2313771720923432923','positive_principle':'different advice'}]}}}
    with pytest.raises(AssertionError):obligation_paths(pairs,[])


def test_skipped_Q_update_remains_null_instead_of_negative_reward(monkeypatch):
    monkeypatch.setattr(review,'OBLIGATIONS',[
        ('907','card','positive_principle','Add ledger','ledger[key]=reason','implemented')])
    pairs={'907':{'new':{'attempt':1,'code':'ledger[key]=reason',
        'adopted_card_bodies':[{'invariant_id':'card','positive_principle':'Add ledger'}]}}}
    events=[{'pool':'D_init','task_id':'907','attempt':1,'invariant_id':'card',
        'credited':False,'reward':None,'q_before':-.2,'q_after':-.2,'skip_reason':'incomplete_or_technical_measurement'}]
    result=obligation_paths(pairs,events)[0]
    assert result['credited'] is False and result['reward'] is None
    assert result['q_before']==result['q_after']

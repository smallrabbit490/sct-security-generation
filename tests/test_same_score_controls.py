"""固定选样与组件分母控制，不重跑本地代码诊断或模型。"""
from configs.cle_memory_mechanisms_20261023.review_same_score_controls import (
    select_controls,same_score_components,current_case_index)
import pytest


def row(tid,old_f,old_s,new_f,new_s,old_measured='True',new_measured='True'):
    return {'task_id':tid,'transition':'both_fail','old_F_from_native':old_f,'old_S_from_native':old_s,
        'new_F_from_native':new_f,'new_S_from_native':new_s,
        'old_measured':old_measured,'new_measured':new_measured}


def test_same_joint_can_hide_security_regression_and_function_gain():
    rows=[row('s_drop','False','True','False','False'),
          row('f_gain','False','False','True','False')]
    result=same_score_components(rows)['both_fail']
    assert result['component_changes']['S']['loss_ids']==['s_drop']
    assert result['component_changes']['F']['gain_ids']==['f_gain']
    assert result['any_component_changed_ids']==['s_drop','f_gain']


def test_unmeasured_pair_not_converted_into_component_loss():
    result=same_score_components([row('missing','True','False','False','False',new_measured='False')])['both_fail']
    assert result['tasks']==1 and result['both_final_measured']==0
    assert result['unmeasured_pair_ids']==['missing']
    assert result['any_component_changed_ids']==[]


def test_frozen_control_selection_uses_metadata_string_order_and_distinct_families():
    features=[];metadata={}
    for i,cwe in enumerate(['9','2','10','3','4','5','6']):
        tid=str(i)
        features.append({'task_id':tid,'family_id':'family-'+tid,'transition':'both_pass','new_external_rebindings':[]})
        metadata[tid]={'cwe':cwe}
    features.append({'task_id':'flagged','family_id':'flagged-family','transition':'both_fail','new_external_rebindings':['PUBLIC']})
    metadata['flagged']={'cwe':'20'}
    result=select_controls(features,metadata)
    assert [r['cwe'] for r in result['unflagged_both_pass']]==['10','2','3','4','5','6']
    assert result['flagged_both_fail'][0]['task_id']=='flagged'


def test_no_component_change_for_measured_both_pass_is_not_a_behavior_certificate():
    item=row('pass','True','True','True','True');item['transition']='both_pass'
    result=same_score_components([item])['both_pass']
    assert result['tasks']==result['both_final_measured']==1
    assert result['any_component_changed_ids']==[]
    assert 'all_public_behaviors_correct' not in result


def test_unreviewed_cases_stay_unknown_and_duplicate_review_is_rejected():
    metadata={tid:{'task_id':tid,'family_id':'family-'+tid,'cwe':'20','transition':'both_fail',
        'old_measured':'True','new_measured':'True','old_joint_verified_native_and_pair_table':'False',
        'new_joint_from_native':'False'} for tid in ('1','2')}
    case={'task_id':'1','primary_category':'observed_binding','finding':'specific observation'}
    index=current_case_index(metadata,[('case1.json',case)])
    assert index[0]['review_status']=='limited_code_public_evidence_review'
    assert index[1]['category']=='unknown' and index[1]['review_status']=='not_deeply_reviewed'
    with pytest.raises(ValueError,match='duplicate'):
        current_case_index(metadata,[('case1.json',case),('duplicate.json',case)])

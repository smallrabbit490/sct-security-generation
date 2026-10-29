"""粒度来源材料应保留失败状态，不能用目标答案或错误来源冒充。"""
import pytest
from configs.cle_memory_mechanisms_20261023.prepare_granularity_sources import source_episode,link_card,example_kind,source_measurements


def fixture():
    task={'task_description':{'description':'A public source task'},'testcases':'PRIVATE_TEST'}
    native={'task_id':67,'generated_codes':['def f(): return 0','def f(): return 1'],
        'state_first':'B','state_after_repair':'B','evidence_first':{'functional':'pass','security':'fail','security_detail':'PRIVATE_TEST'},
        'evidence_after_repair':{'functional':'pass','security':'fail'},'outcome':'seed_grounding_failure'}
    card={'invariant_id':'source-card','cwe':'20','source':{'task_id':67,'kind':'overdefense_pitfall'}}
    return task,native,card


def test_full_failed_source_keeps_both_codes_and_does_not_copy_hidden_detail():
    task,native,_=fixture()
    episode=source_episode(task,native,3)
    assert len(episode['attempts'])==2
    assert all(a['reported_validation']['security']=='fail' for a in episode['attempts'])
    assert not episode['is_guaranteed_correct_example']
    assert 'PRIVATE_TEST' not in str(episode)


def test_reference_seed_and_model_episode_are_distinct():
    _,_,card=fixture()
    assert example_kind(card)=='training_generated_episode'
    card['source']['kind']='seed_from_diff'
    assert example_kind(card)=='training_reference_seed'


def test_source_family_overlap_or_identity_mismatch_stops():
    task,native,card=fixture();episode=source_episode(task,native,3)
    linked=link_card(card,card,episode,'source-family',{'target-family'})
    assert linked['episode_available'] and not linked['single_producing_attempt_certified']
    with pytest.raises(ValueError):link_card(card,card,episode,'source-family',{'source-family'})
    with pytest.raises(ValueError):link_card(card,{**card,'invariant_id':'different'},episode,'source-family',set())


def test_missing_last_source_measurement_does_not_borrow_first():
    task,native,_=fixture();native['evidence_after_repair']=None
    episode=source_episode(task,native,3)
    assert source_measurements({'67':episode})=={'unmeasured':1}

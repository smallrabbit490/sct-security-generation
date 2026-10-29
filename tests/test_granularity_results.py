"""C1门的手算合成控制；这些结果不是模型实验数据。"""
import copy

import pytest

from methods.cle_ablation.granularity_results import make_schedule,evaluate
from methods.cle_ablation.memory_granularity_study import VERSION


def manifest():
    tasks=[{'task_id':str(i),'family_id':f'family-{i}','cwe':'test'} for i in range(48)]
    return {'groups':{'train':tasks[:36],'development':tasks[36:]},
            'first_pilot_ids':[str(i) for i in range(12)],'technical_probe_ids':['0','1']}


def data():
    schedule=make_schedule(manifest())
    rows=[]
    for cell in schedule[:120]:
        # 前2族只有L1稳定成功；下2族只有L2成功；其余五档全失败。
        passed=(int(cell['task_id'])<2 and cell['memory_level']=='L1') or (
            2<=int(cell['task_id'])<4 and cell['memory_level']=='L2')
        attempt={'code':'valid source in synthetic control','measured':True,
            'functional':passed,'security':True,'joint':passed,
            'generation':{'workflow_completed':True},
            'retrieval_trace':{'pre_level_selected_ids':['same-card']}}
        rows.append({'task_id':cell['task_id'],'repeat':cell['repeat'],'memory_level':cell['memory_level'],
            'protocol':VERSION,'arm':'P7','subset':'PLT','Q_updates':0,
            'usage':{'failed_calls':0,'prompt_tokens':100},
            'attempts':[attempt] if passed else [copy.deepcopy(attempt),attempt]})
    return schedule,rows


def run(schedule,rows,costs=()):
    return evaluate(schedule,rows,native_protocol=VERSION,cell_costs=costs)


def test_schedule_prefix_counts_reproducibility_and_original_split():
    schedule=make_schedule(manifest())
    assert len(schedule)==480 and len({c['cell_id'] for c in schedule})==480
    assert all(c['phase']=='technical' for c in schedule[:20])
    assert {c['task_id'] for c in schedule[:120]}=={str(i) for i in range(12)}
    assert sum(c['split']=='train' for c in schedule)==360
    assert schedule==make_schedule(manifest())
    assert schedule!=make_schedule(manifest(),seed=1)
    bad=manifest();bad['groups']['development'][0]['family_id']='family-0'
    with pytest.raises(ValueError,match='overlap'):make_schedule(bad)


def test_no_real_rows_is_not_a_failed_effectiveness_gate():
    result=run(make_schedule(manifest()),[])
    assert result['missing_cells']==120 and result['technical_cells']==0
    assert result['C1']['passed'] is None and not result['C1']['evaluated']
    assert result['arms']['L0']['final']['joint']=={'passed':0,'denominator':0,'rate':None}
    assert all(f['preferred_level'] is None for f in result['families'])


def test_hand_computed_reciprocal_gate_and_non_deployable_upper_bound():
    schedule,rows=data();result=run(schedule,rows);gate=result['C1']
    assert gate['passed'] and gate['stable_different_families']==4
    assert gate['fixed_joint_rates']['L1']==pytest.approx(2/12)
    assert gate['fixed_joint_rates']['L2']==pytest.approx(2/12)
    assert gate['observed_oracle']==pytest.approx(4/12)
    assert gate['oracle_minus_fixed']==pytest.approx(2/12)
    assert gate['reciprocal_level_pairs'][0]['levels']==['L1','L2']
    assert not gate['oracle_is_deployable_score']
    assert result['families'][0]['acceptable_levels']==['L1']
    assert result['families'][0]['preferred_level'] is None  # 只有原生行Token并非完整成本。
    assert result['families'][4]['label_status']=='all_five_failed'


def test_tied_successes_do_not_fabricate_reciprocal_advantage():
    schedule,rows=data()
    for row in rows:
        if int(row['task_id'])<4 and row['memory_level']=='L1':
            row['attempts']=row['attempts'][:1]
            row['attempts'][0].update(functional=True,joint=True)
    gate=run(schedule,rows)['C1']
    assert gate['evaluated'] and not gate['passed']
    assert gate['reciprocal_level_pairs']==[]
    assert gate['oracle_minus_fixed']==0


def test_missing_repeat_and_technical_failure_do_not_become_joint_false_labels():
    schedule,rows=data()
    result=run(schedule,rows[:-1])
    assert result['C1']['status']=='not_evaluated_missing_outcomes'
    rows[-1]['attempts'][-1]={'code':'','measured':False,'error_type':'TimeoutError'}
    result=run(schedule,rows)
    assert result['C1']['status']=='blocked_technical_error'
    assert result['C1']['passed'] is None and result['technical_cells']==1
    assert result['level_outcomes'][-1]['final_joint'] is None
    assert result['families'][-1]['status']=='incomplete'


def test_complete_actual_cell_cost_selects_preference_and_ties_lower_level():
    schedule,rows=data()
    for row in rows:
        if row['task_id']=='0' and row['memory_level']=='L2':
            row['attempts']=row['attempts'][:1]
            row['attempts'][0].update(functional=True,joint=True)
    costs=[{'cell_id':c['cell_id'],'prompt_tokens':80,'complete':True}
           for c in schedule[:120] if c['task_id']=='0' and c['memory_level'] in ('L1','L2')]
    result=run(schedule,rows,costs)
    assert result['families'][0]['preferred_level']=='L1'
    costs[0]['complete']=False
    assert run(schedule,rows,costs)['families'][0]['preferred_level'] is None


def test_single_repeat_pass_is_unstable_and_not_L0_correct():
    schedule,rows=data()
    for row in rows:
        if row['task_id']=='4' and row['memory_level']=='L3' and row['repeat']==1:
            row['attempts']=row['attempts'][:1]
            row['attempts'][0].update(functional=True,joint=True)
    family=run(schedule,rows)['families'][4]
    assert family['label_status']=='unstable_only' and family['unstable_levels']==['L3']
    assert family['preferred_level'] is None


@pytest.mark.parametrize('change', ['duplicate','preview','protocol','Q','first_ids','early_stop','repair'])
def test_native_format_and_shared_first_gate(change):
    schedule,rows=data()
    if change=='duplicate':
        with pytest.raises(ValueError,match='duplicate'):run(schedule,rows+[rows[0]])
        return
    if change=='preview':rows[0]['is_experiment_score']=False
    if change=='protocol':rows[0]['protocol']='old-B-protocol'
    if change=='Q':rows[0]['Q_updates']=1
    if change in ('preview','protocol','Q'):
        with pytest.raises(ValueError):run(schedule,rows)
        return
    if change=='first_ids':rows[0]['attempts'][0]['retrieval_trace']['pre_level_selected_ids']=['another']
    if change=='early_stop':
        passed=next(r for r in rows if r['attempts'][0]['joint'])
        passed['attempts'].append(copy.deepcopy(passed['attempts'][0]))
    if change=='repair':
        failed=next(r for r in rows if not r['attempts'][0]['joint'])
        failed['attempts']=failed['attempts'][:1]
    result=run(schedule,rows)
    assert result['C1']['status']=='blocked_technical_error'
    if change=='first_ids':
        assert result['families'][0]['status']=='invalid_shared_start'
        assert not result['families'][0]['acceptable_levels']

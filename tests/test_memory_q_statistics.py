import pytest
from methods.cle_ablation.report_memory_q import cp_bounds, paired_effect


def test_zero_discordance_does_not_claim_zero_uncertainty():
    rows=[{'task_id':i,'arm':a,'final':{'joint':True,'functional':True}} for i in range(10) for a in ('Q1','Q2')]
    result=paired_effect(rows,'Q1','Q2')
    expected=100*(1-0.0125**0.1)
    assert result['conservative_95_ci_percentage_points']==pytest.approx([-expected,expected])
    assert result['p_exact_two_sided']==1


def test_exact_extremes_and_paired_losses():
    assert cp_bounds(0,10)[0]==0
    assert cp_bounds(10,10)[1]==1
    rows=[{'task_id':i,'arm':a,'final':{'joint':a=='Q1','functional':a=='Q1'}} for i in range(24) for a in ('Q1','Q2')]
    result=paired_effect(rows,'Q1','Q2')
    assert result['old_only']==24 and result['delta_percentage_points']==-100
    assert result['conservative_95_ci_percentage_points'][1]<0
    assert result['functional_harms']==24

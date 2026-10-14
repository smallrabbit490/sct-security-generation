from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory.hsk_tree import HskTree
from methods.sct_trajectory.error_ledger import ErrorLedger
from methods.sct_trajectory.schemas import RolloutTrace


def test_new_mode_defers_gate_until_all_rounds(monkeypatch):
    runner = CleRunner(lambda p: {}, HskTree(), ErrorLedger(), gate_mode='global', branch_count=3)
    calls = []
    task = {'index': 1, 'CWE_ID': '22', 'task_description': {'description': 'f'}}
    def phase2(pool, **kwargs):
        calls.append(kwargs['round_index'])
        trace = RolloutTrace(task_id='1', cwe='22', round=kwargs['round_index'], states=['D'])
        runner.traces.append(trace)
        return {'traces': [trace.to_dict()], 'selected': 1, 'positive_candidates': 0,
                'negative_candidates': 0, 'ledger_entries': 0}
    monkeypatch.setattr(runner, 'phase2_evolve', phase2)
    monkeypatch.setattr(runner, 'phase3_audit', lambda *a, **k: (_ for _ in ()).throw(AssertionError('premature gate')))
    result = runner.run_evolution_rounds([task], [task], rounds=3)
    assert calls == [1, 2, 3]
    assert all(r['gate_deferred'] for r in result['rounds'])
    assert result['gate_records'] == []


def test_phase2_branch_routing_preserves_full_trace(monkeypatch):
    import methods.sct_trajectory.branch_pipeline as bp
    runner = CleRunner(lambda p: {}, HskTree(), ErrorLedger(), gate_mode='global', branch_count=3)
    fake = {'branches': [{'branch_id': 'b1', 'code': 'def f(): return 1', 'state': 'A',
                         'joint': True, 'measured': True, 'evidence': {}, 'cards': []}],
            'selected_index': 0, 'shared_context': {'cards': []}, 'mode': 'diverse', 'plan_error': None,
            'selection_policy': 'training_oracle_first_joint_else_first'}
    monkeypatch.setattr(bp, 'run_branches', lambda *a, **k: fake)
    monkeypatch.setattr(bp, 'distill_branches', lambda *a: {'positive': [], 'negative': [], 'error_ledger': []})
    result = runner._phase2_one({'index': 1, 'CWE_ID': '22'}, None, repairs=1, round_index=3)
    assert result['error'] is None
    assert result['trace'].branches == fake['branches']
    assert result['trace'].transitions == []


def test_resume_validation_rejects_partial_phase2(tmp_path):
    import json
    from methods.sct_trajectory.training_checkpoint import phase1_resume_source
    (tmp_path / 'phase1_results.jsonl').write_text(json.dumps({'task_id': 1})+'\n')
    (tmp_path / 'experience_pool.jsonl').write_text(json.dumps({'invariant_id': 'x'})+'\n')
    (tmp_path / 'trajectories.jsonl').write_text(json.dumps({'round': 3})+'\n')
    import pytest
    with pytest.raises(ValueError, match='phase1_only'):
        phase1_resume_source(tmp_path, {1})


def test_branch_distillation_provenance_survives_node_factories():
    from methods.sct_trajectory.closed_loop import _node_from_distilled, _node_from_negative, _node_from_ledger_item
    item = {'high_level_invariant': 'bound input', 'positive_principle': 'check before operation',
            'negative_guardrail': 'avoid unchecked operation', 'blind_spot': 'missing bound',
            'evidence_branch_ids': ['b1', 'b3'], 'causal_claim': False, 'kind': 'branch_comparison_positive'}
    for factory in (_node_from_distilled, _node_from_negative, _node_from_ledger_item):
        node = factory(item)
        assert node.source['evidence_branch_ids'] == ['b1', 'b3']
        assert node.source['causal_claim'] is False


def test_phase1_resume_rejects_foreign_or_missing_source(tmp_path):
    import json
    import pytest
    from methods.sct_trajectory.training_checkpoint import phase1_resume_source
    (tmp_path / 'phase1_results.jsonl').write_text(json.dumps({'task_id': 1})+'\n')
    for source in ({}, {'stage': 'phase1', 'task_id': 2}):
        (tmp_path / 'experience_pool.jsonl').write_text(json.dumps({'invariant_id': 'x', 'source': source})+'\n')
        with pytest.raises(ValueError):
            phase1_resume_source(tmp_path, {1})

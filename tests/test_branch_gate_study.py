"""训练侧分支/门控研究的统计、边界和来源回归；无付费请求。"""
import importlib
import json

import pytest


def module():
    return importlib.import_module('methods.sct_trajectory.run_branch_gate_study')


def test_training_selection_stratifies_and_refuses_plus():
    m = module()
    tasks = [{'index': i, 'CWE_ID': str(i // 4)} for i in range(12)]
    selected = m.stratified_tasks(tasks, 3)
    assert {x['CWE_ID'] for x in selected} == {'0', '1', '2'}
    assert selected == m.stratified_tasks(tasks[::-1], 3)
    with pytest.raises(ValueError, match='Base/Plus'):
        m.stratified_tasks([{'index': 1, 'subset': 'Plus'}], 0)


def test_library_requires_entire_phase1_provenance(tmp_path):
    p = tmp_path / 'cards.jsonl'
    p.write_text(json.dumps({'invariant_id': 'a', 'source': {'stage': 'phase1'}}), encoding='utf8')
    assert len(module().load_phase1_memory(p)) == 1
    p.write_text(json.dumps({'invariant_id': 'b', 'source': {'stage': 'phase2'}}), encoding='utf8')
    with pytest.raises(ValueError, match='Phase1'):
        module().load_phase1_memory(p)


def test_exact_paired_stats_never_fill_missing_pairs():
    pairs = module().paired_binary({'a': False, 'b': True}, {'a': True, 'c': False})
    assert pairs['pairs'] == 1
    assert pairs['new_only'] == 1
    assert pairs['old_only'] == 0
    assert pairs['p_exact_two_sided'] == 1.0
    assert pairs['unpaired'] == 2


def test_usage_missing_tokens_are_not_silently_zero():
    usage = module().UsageCounter(lambda p: {'choices': [], 'usage': {'prompt_tokens': 3}})
    usage('x')
    result = usage.snapshot()
    assert result['prompt_tokens'] == 3
    assert result['completion_tokens'] is None
    assert result['total_tokens'] is None
    assert result['usage_complete'] is False


def test_aggregate_usage_preserves_missing_records_and_shared_cost():
    assert module().summarize_usage([{'calls': 1, 'total_tokens': 7}, {}])['total_tokens'] is None
    assert module().summarize_usage([{'calls': 1, 'total_tokens': 7}, {'calls': 2, 'total_tokens': 5}])['total_tokens'] == 12


def test_first_and_oracle_keep_unmeasured_explicit():
    rows = [{'task_id': 'x', 'arm': 'diverse3', 'attempts': [
        {'functional': False, 'security': False, 'joint': False, 'measured': False},
        {'functional': True, 'security': True, 'joint': True, 'measured': True}]}]
    result = module().summarize_branches(rows)
    assert result['arms']['diverse3']['first']['unmeasured'] == 1
    assert result['arms']['diverse3']['oracle']['joint_pass'] == 1
    assert result['independent_heldout'] is False


def test_unmeasured_positive_flags_do_not_count_as_pass():
    fake = {'functional': True, 'security': True, 'joint': True, 'measured': False}
    assert module()._metrics([fake])['joint_pass'] == 0
    assert module()._oracle([fake])['joint'] is False


def test_complete_pair_sensitivity_excludes_incomplete_candidate_sets():
    def row(arm, measured, passed):
        return {'task_id': 'x', 'arm': arm, 'attempts': [
            {'functional': passed, 'security': passed, 'joint': passed, 'measured': measured}]}
    result = module().summarize_branches([row('resample3', False, False), row('diverse3', True, True)])
    comparison = result['comparisons']['diverse3_vs_resample3']
    assert comparison['pairs'] == 1
    assert comparison['new_only'] == 1
    assert comparison['complete_measured_pairs']['pairs'] == 0
    assert comparison['complete_measured_pairs']['excluded_incomplete_pairs'] == 1


def test_holm_monotonic_and_bounded():
    assert module().holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_family_preflight_refuses_overlap_and_manifest_drift():
    rows = [{'index': i, 'family_id': f'f{i}'} for i in range(3)]
    pools = {k: [{'task_id': i, 'family_id': f'f{i}'}]
             for i, k in enumerate(('source', 'replay', 'audit'))}
    manifest = {'row_classification': {str(i): {'seed_family_id': f'f{i}'} for i in range(3)}}
    result = module().validate_family_boundaries(rows, pools, manifest)
    assert result['family_ids_pairwise_disjoint'] is True
    assert result['task_family_manifest_consistent'] is True
    manifest['row_classification']['2']['seed_family_id'] = 'wrong'
    with pytest.raises(ValueError, match='family.*mismatch'):
        module().validate_family_boundaries(rows, pools, manifest)
    manifest['row_classification']['2']['seed_family_id'] = 'f1'
    rows[2]['family_id'] = pools['audit'][0]['family_id'] = 'f1'
    with pytest.raises(ValueError, match='family overlap'):
        module().validate_family_boundaries(rows, pools, manifest)


def test_full_study_offline_writes_both_stages_without_mutating_source(tmp_path, monkeypatch):
    from argparse import Namespace
    from methods.sct_trajectory import run_closed_loop, closed_loop, retriever, internal_checks
    m = module()
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    runner = tmp_path / 'methods/sct_trajectory/run_branch_gate_study.py'
    monkeypatch.setattr(m, '__file__', str(runner))
    for name in ('run_branch_gate_study', 'branch_pipeline', 'global_gate', 'context_pipeline',
                 'hier_retrieval', 'retriever', 'agent_pipeline', 'closed_loop', 'run_closed_loop',
                 'internal_checks', 'hsk_tree', 'schemas', 'ablation'):
        p = runner.with_name(name + '.py')
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('# source fixture', encoding='utf8')
    evidence_source = tmp_path / 'methods/sct_agent/validation_evidence.py'
    evidence_source.parent.mkdir(parents=True)
    evidence_source.write_text('# fixture', encoding='utf8')
    pools = {'source': [{'task_id': i, 'family_id': f'f{i}'} for i in range(303)],
             'replay': [{'task_id': i, 'family_id': f'f{i}'} for i in range(303, 576)],
             'audit': [{'task_id': i, 'family_id': f'f{i}'} for i in range(576, 874)]}
    pool_path = tmp_path / 'pools.json'
    pool_path.write_text(json.dumps(pools), encoding='utf8')
    manifest = tmp_path / 'data/external/secodeplt/derived_metadata/family_manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({'row_classification': {str(i): {'seed_family_id': f'f{i}'}
                                                         for i in range(874)}}), encoding='utf8')
    source = tmp_path / 'memory.jsonl'
    source.write_text(json.dumps({'invariant_id': 'a', 'cwe': '1', 'high_level_invariant': 'test',
                                 'source': {'stage': 'phase1', 'task_id': 0}}), encoding='utf8')
    original = source.read_bytes()
    monkeypatch.setattr(run_closed_loop, '_load_tasks', lambda n: [
        {'index': i, 'CWE_ID': '1', 'family_id': f'f{i}', 'task_description': {'description': 'Return 1', 'entry_point': 'f'}}
        for i in range(874)])
    def request(prompt):
        if prompt.startswith('BRANCH_PLAN'):
            text = json.dumps({'plans': [{'Patch_Scope': 'Implement f', 'Preserved_Func': 'return 1'}] * 3})
        elif prompt.startswith('你负责训练侧并行方案经验提炼'):
            text = json.dumps({'positive': [], 'negative': [], 'error_ledger': []})
        elif '生成完整' in prompt[:70] or prompt.startswith('BRANCH_CODE'):
            text = 'def f():\n    return 1'
        else:
            text = json.dumps({'vulnerability_hypothesis': ['none'], 'functional_invariants': ['return 1'],
                               'Patch_Scope': 'Implement f', 'Preserved_Func': 'return 1'})
        return {'choices': [{'message': {'content': text}}],
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
    monkeypatch.setattr(run_closed_loop, '_requester', lambda *a, **k: request)
    monkeypatch.setattr(retriever.HskTreeRetriever, 'search', lambda *a, **k: [])
    monkeypatch.setattr(closed_loop, 'validate_and_state', lambda *a, **k: (
        {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}, 'A'))
    monkeypatch.setattr(internal_checks, 'propose_checks', lambda *a: {'cases': []})
    monkeypatch.setattr(internal_checks, 'execute_checks', lambda *a: {'source': 'self_generated_internal'})
    args = Namespace(out='translation_work/diagnostics/offline', phase='both', limit=1, memory=str(source),
                     pools=str(pool_path), workers=2, max_inflight=3, max_tokens=100,
                     timeout=3, validation_timeout=1, distill_smoke=True)
    result = m.run_study(args)
    assert result['branches']['arms']['diverse3']['oracle']['joint_pass'] == 1
    assert result['gate']['arms']['memory']['joint_pass'] == 1
    assert all(value['p_holm_three_diagnostic_comparisons'] == 1.0 for value in result['gate']['paired'].values())
    assert result['source_library_unchanged']
    assert source.read_bytes() == original
    out = tmp_path / args.out
    assert json.loads((out / 'status.json').read_text())['status'] == 'completed'
    assert len((out / 'branches.jsonl').read_text().splitlines()) == 3
    assert (out / 'smoke_distilled_candidates.json').exists()

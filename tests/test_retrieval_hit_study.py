import pytest

from methods.sct_trajectory import retrieval_hit_study as study


def test_queries_do_not_leak_answers_or_task_identifiers():
    task = {'description': 'public', 'arguments': 'x', 'return': 'str',
            'raise': 'none', 'language': 'python', 'CWE_ID': '22',
            'task_id': 'secret-id', 'tests': 'hidden', 'answer': 'hidden'}
    analysis = {'functional_invariants': ['public invariant']}
    assert study.make_query(task, analysis, 'original') == {
        k: task[k] for k in ('description', 'arguments', 'return', 'raise', 'language', 'CWE_ID')}
    assert study.make_query(task, analysis, 'analysis') == {
        'language': 'python', 'CWE_ID': '22', 'threat_analysis': analysis}
    combined = study.make_query(task, analysis, 'combined')
    assert combined['arguments'] == 'x'
    assert combined['threat_analysis'] == analysis
    assert 'tests' not in combined and 'task_id' not in combined


def test_family_selection_is_order_independent_and_calibration_is_disjoint():
    rows = [{'index': i, 'family_id': str(i // 2), 'CWE_ID': str(i % 3)} for i in range(24)]
    one = study.select_tasks(rows, calibration_count=3)
    two = study.select_tasks(list(reversed(rows)), calibration_count=3)
    assert one == two
    assert len(one['formal']) == 9
    assert not {r['family_id'] for r in one['formal']} & {r['family_id'] for r in one['calibration']}


def test_embedding_ranking_has_no_cwe_bonus_or_llm_reranking():
    scores = [0.2, 0.9, 0.9, 0.1]
    assert study.rank_embeddings(['z', 'b', 'a', 'c'], scores, 3) == ['a', 'b', 'z']
    with pytest.raises(ValueError):
        study.rank_embeddings(['a'], [float('nan')], 3)


def test_blinded_pair_is_shared_across_arms_and_hides_metadata():
    task = {'description': 'public task', 'language': 'python'}
    card = {'invariant_id': 'secret-id', 'source_task_id': 99, 'score': 0.8,
            'positive_principle': 'use safe API'}
    pair = study.blind_pair(task, card)
    assert pair == study.blind_pair(dict(task), dict(card))
    assert set(pair) == {'pair_id', 'task', 'card'}
    assert pair['card'] == {'positive_principle': 'use safe API'}


def test_missing_labels_are_unknown_not_wrong_and_failures_stay_in_denominator():
    rows = [
        {'task_id': 1, 'arm': 'embedding_original', 'selected_pair_ids': ['ok', 'bad'], 'error_type': None},
        {'task_id': 2, 'arm': 'embedding_original', 'selected_pair_ids': ['unknown'], 'error_type': None},
        {'task_id': 3, 'arm': 'embedding_original', 'selected_pair_ids': [], 'error_type': 'timeout'},
    ]
    labels = {'ok': {'label': 'direct'}, 'bad': {'label': 'conflict'}}
    m = study.arm_metrics(rows, labels)
    assert m['tasks'] == 3 and m['unlabeled_cards'] == 1
    assert m['strict_precision'] is None
    assert m['known_label_precision'] == 0.5
    assert m['hit_rate_lower_bound'] == pytest.approx(1 / 3)
    assert m['technical_failure_rate'] == pytest.approx(1 / 3)
    assert m['successful_empty_rate'] == 0


def test_judgment_requires_grounded_rationale():
    with pytest.raises(ValueError):
        study.validate_judgment({'label': 'direct'})
    item = {'label': 'direct', 'task_evidence': 'public constraint',
            'card_evidence': 'safe API', 'reason': 'consistent with contract'}
    assert study.validate_judgment(item) == item


def test_frozen_input_preflight_rejects_manifest_drift(tmp_path, monkeypatch):
    import json
    import hashlib
    monkeypatch.setattr(study, 'ROOT', tmp_path)
    out = tmp_path / 'translation_work/diagnostics/test'
    out.mkdir(parents=True)
    manifest = {'formal': [], 'calibration': []}
    (out / 'task_manifest.json').write_text(json.dumps(manifest), encoding='utf8')
    for name in ('input_memory.jsonl', 'input_pools.json'):
        (out / name).write_text('{}', encoding='utf8')
    expected = hashlib.sha256(b'{}').hexdigest()
    meta = {'memory_sha256': expected, 'pools_sha256': expected,
            'manifest_sha256': study.digest(manifest), 'source_hashes': {}}
    (out / 'run_metadata.json').write_text(json.dumps(meta), encoding='utf8')
    assert study.verify_inputs(out) == meta
    (out / 'task_manifest.json').write_text('{"formal":[1],"calibration":[]}', encoding='utf8')
    with pytest.raises(ValueError, match='task_manifest_changed'):
        study.verify_inputs(out)


def test_end_to_end_summary_separates_phases_repeats_and_human_labels(tmp_path, monkeypatch):
    import json
    import hashlib
    monkeypatch.setattr(study, 'ROOT', tmp_path)
    out = tmp_path / 'translation_work/diagnostics/test'
    out.mkdir(parents=True)
    ledger = study.Ledger(out)
    manifest = {'formal': [{'task_id': 1}], 'calibration': [{'task_id': 2}]}
    ledger.write('task_manifest.json', manifest)
    for name in ('input_memory.jsonl', 'input_pools.json'):
        (out / name).write_text('{}', encoding='utf8')
    ledger.write('run_metadata.json', {'memory_sha256': hashlib.sha256(b'{}').hexdigest(),
         'pools_sha256': hashlib.sha256(b'{}').hexdigest(),
         'manifest_sha256': study.digest(manifest), 'source_hashes': {}})
    ledger.append('blind_pairs.jsonl', {'pair_id': 'p', 'task': {}, 'card': {}})
    for arm in study.ARMS:
        for task, phase, repeat in [(1, 'formal', 0), (1, 'formal', 1), (2, 'calibration', 0)]:
            ledger.append('rows.jsonl', {'task_id': task, 'arm': arm, 'phase': phase, 'repeat': repeat,
                         'selected_ids': ['card'], 'selected_pair_ids': ['p'], 'error_type': None})
    ledger.append('model_labels.jsonl', {'pair_id': 'p', 'label': 'direct',
                  'task_evidence': 'public contract', 'card_evidence': 'safe API', 'reason': 'applicable'})
    summary = study.summarize(out)
    assert summary['formal_complete'] and summary['formal_rows'] == 6
    assert summary['repeat_rows'] == summary['calibration_rows'] == 6
    assert summary['labels']['model']['arms']['embedding_original']['top3']['strict_precision'] == 1
    assert summary['labels']['human']['labeled_pairs'] == 0
    assert summary['labels']['human']['arms']['embedding_original']['top3']['strict_precision'] is None
    assert len(summary['labels']['model']['comparisons']) == 5
    packet = study.read_rows(out / 'human_review_packet.jsonl')
    assert packet[0]['label'] is None
    ledger.append('rows.jsonl', study.read_rows(out / 'rows.jsonl')[0])
    with pytest.raises(ValueError, match='duplicate_retrieval_records'):
        study.summarize(out)


def test_initial_parser_excludes_appended_implementation_and_unknown_fields():
    import json
    value = {k: [] for k in ('vulnerability_hypothesis', 'functional_invariants', 'sources', 'sinks',
             'sensitive_operations', 'api_assumptions', 'data_flows', 'attack_surface', 'safe_actions', 'uncertainty')}
    value.update(vulnerability_hypothesis=['risk'], functional_invariants=['behavior'], code='hidden')
    result = study.parse_initial_analysis(json.dumps(value) + '\n# Implementation\ndef f(): return {}')
    assert 'code' not in result
    assert result['functional_invariants'] == ['behavior']
    with pytest.raises(ValueError):
        study.parse_initial_analysis('{"functional_invariants":[]}')

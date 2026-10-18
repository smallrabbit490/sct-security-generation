"""远程CLE执行链路上的Q归因和结果格式；不调用外部服务。"""
from methods.sct_trajectory.hsk_tree import SecurityInvariantNode


def test_only_adopted_card_learns_and_native_report_reads_rows():
    from methods.cle_ablation.run_memory_q import record_result, learn_q, summarize
    adopted = SecurityInvariantNode(invariant_id='adopted', cwe='22', high_level_invariant='preserve inputs')
    recalled = SecurityInvariantNode(invariant_id='recalled', cwe='22', high_level_invariant='preserve inputs')
    row = {'task_id': '1', 'usage': {'calls': 4, 'total_tokens': 100}, 'attempts': [
        {'attempt': 0, 'code': 'def f(): return 1', 'measured': True,
         'functional': True, 'security': True, 'joint': True,
         'validation': {'evidence': {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}},
         'generation': {'workflow_completed': True, 'cards': [{'invariant_id': 'adopted'}],
                        'retrieved_cards': [{'invariant_id': 'recalled'}]}}]}
    task = {'index': 1, 'family_id': 'family1', 'CWE_ID': '22'}
    record_result(row, task, 'Q0', 'D_grow', 1.0)
    events = learn_q(row, {n.invariant_id: n for n in (adopted, recalled)}, 0.3)
    assert adopted.q_value == 0.3 and adopted.q_visits == 1
    assert recalled.q_value == 0 and recalled.q_visits == 0
    assert events[0]['attempt'] == 0
    report = summarize([row], 'Q0')
    assert report['arms']['Q0']['joint'] == 1
    assert report['arms']['Q0']['total_tokens'] == 100


def test_comparison_cannot_learn_and_failures_are_not_passes():
    import pytest
    from methods.cle_ablation.run_memory_q import record_result, learn_q, summarize
    row = {'task_id': '1', 'usage': {'calls': 1, 'total_tokens': 1},
           'attempts': [{'code': '', 'measured': False, 'error_type': 'empty_code'}]}
    record_result(row, {'index': 1, 'family_id': 'f', 'CWE_ID': '22'}, 'Q2', 'D_gate', 1.0)
    with pytest.raises(ValueError, match='D_grow'):
        learn_q(row, {}, 0.3)
    report = summarize([row], 'Q1')
    assert report['arms']['Q2']['joint'] == 0
    assert report['arms']['Q2']['measured'] == 0
    assert report['arms']['Q2']['errors'] == 1


def test_same_query_readout_detects_q_order_change():
    from methods.cle_ablation.run_memory_q import mechanism_readout
    nodes = [SecurityInvariantNode(invariant_id=str(i), cwe='22', high_level_invariant='rule',
                                   q_value=q, q_visits=1) for i, q in enumerate((0, 1, -1, 1))]
    scores = [{'id': str(i), 'cosine': 0.9-i*0.01} for i in range(4)]
    rows = [{'task_id': '1', 'arm': 'Q2', 'attempts': [{'attempt': 0, 'retrieval_trace': {'scores': scores}}]}]
    result = mechanism_readout(rows, nodes, 0.4, 0.9)[0]
    assert result['similarity_ids_same_query'] == ['0', '1', '2']
    assert result['q_ids_same_query'] == ['1', '3', '0']
    assert result['set_changed'] and result['visited_candidates'] == 4


def test_shuffled_q_preserves_distribution_and_content():
    from methods.cle_ablation.run_memory_q import shuffled_memory
    nodes = [SecurityInvariantNode(str(i), '22', 'same rule', q_value=i/10, q_visits=i) for i in range(8)]
    shuffled = shuffled_memory(nodes, 20261015)
    assert sorted((n.q_value,n.q_visits) for n in shuffled) == sorted((n.q_value,n.q_visits) for n in nodes)
    assert [n.q_value for n in shuffled] != [n.q_value for n in nodes]
    assert [n.to_dict() for n in shuffled] == [n.to_dict() for n in shuffled_memory(nodes, 20261015)]
    assert all(a.invariant_id == b.invariant_id and a.high_level_invariant == b.high_level_invariant for a,b in zip(nodes,shuffled))


def test_result_audit_rejects_score_which_disagrees_with_evidence(tmp_path):
    import json
    import pytest
    from methods.cle_ablation.audit_memory_q import check_run
    from methods.cle_ablation.run_memory_q import record_result, summarize
    row = {'task_id': '1', 'subset': 'PLT', 'usage': {'calls': 1, 'total_tokens': 10},
           'attempts': [{'attempt': 0, 'code': 'def f(): pass', 'measured': True,
                         'functional': True, 'security': True, 'joint': True,
                         'validation': {'evidence': {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}}}]}
    record_result(row, {'family_id': 'f', 'CWE_ID': '22'}, 'Q0', 'D_gate', 1.0)
    records = []
    for arm in ('Q0', 'Q1', 'Q2'):
        records.append(json.loads(json.dumps({**row, 'arm': arm})))
    def write(name, value):
        (tmp_path/name).write_text(json.dumps(value), encoding='utf-8')
    write('run_metadata.json', {'args': {'stage': 'compare'}, 'status': 'completed', 'task_ids': ['1'],
                               'q_unchanged': True, 'output_schema_version': 'test'})
    write('summary.json', summarize(records, 'Q1'))
    write('cost.json', {'llm': {'total': {'calls': 3, 'total_tokens': 30}}})
    (tmp_path/'memory_q_events.jsonl').write_text('', encoding='utf-8')
    def save_rows():
        (tmp_path/'rows.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records), encoding='utf-8')
    save_rows()
    assert check_run(tmp_path)['status'] == 'pass'
    records[0]['attempts'][0]['security'] = False
    records[0]['final'] = records[0]['attempts'][0]
    save_rows()
    with pytest.raises(AssertionError):
        check_run(tmp_path)


def test_cwe_shuffle_keeps_each_cwe_pairs_and_all_other_fields():
    from collections import Counter
    from methods.cle_ablation.run_memory_q import shuffled_memory
    nodes = [SecurityInvariantNode(str(i), cwe, 'rule '+str(i), q_value=i/10, q_visits=i)
             for i, cwe in enumerate(('22', '22', '22', '79', '79', '79', '999'))]
    original = [n.to_dict() for n in nodes]
    result = shuffled_memory(nodes, 20261015, 'cwe')
    assert [n.to_dict() for n in nodes] == original
    assert [n.to_dict() for n in result] == [n.to_dict() for n in shuffled_memory(nodes, 20261015, 'cwe')]
    assert any(a.q_value != b.q_value for a, b in zip(nodes, result))
    for cwe in ('22', '79', '999'):
        pairs = lambda bank: Counter((n.q_value, n.q_visits) for n in bank if n.cwe == cwe)
        assert pairs(nodes) == pairs(result)
    strip = lambda node: {k: v for k, v in node.to_dict().items() if k not in ('q_value', 'q_visits')}
    assert [strip(n) for n in nodes] == [strip(n) for n in result]

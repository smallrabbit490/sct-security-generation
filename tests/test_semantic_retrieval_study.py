"""固定英文库检索研究的离线配对、数据边界与失败保留回归；禁止付费调用。"""
import copy
import importlib

import pytest


def module():
    return importlib.import_module('methods.sct_trajectory.run_semantic_retrieval_study')


def pools():
    return {'source': [{'task_id': i} for i in range(303)],
            'replay': [{'task_id': i} for i in range(303, 576)],
            'audit': [{'task_id': i} for i in range(576, 874)]}


def card():
    return {'invariant_id': 'seed-1', 'high_level_invariant': 'Validate boundaries.',
            'source': {'stage': 'phase1', 'task_id': 1},
            'language_leaves': {'python': {'pattern_snippet': 'return value'}}}


def test_memory_requires_exact_phase1_complete_english_snapshot():
    m = module()
    with pytest.raises(ValueError, match='1939'):
        m.validate_memory([card()], pools())
    assert '303' in m.validate_memory([card()], pools(), expected_entries=1)['replay']
    for field, value in [('high_level_invariant', '中文'),
                         ('language_leaves', {'python': {'pattern_snippet': '# 中文'}})]:
        row = card()
        row[field] = value
        with pytest.raises(ValueError, match='non-English'):
            m.validate_memory([row], pools(), expected_entries=1)
    row = card()
    row['source']['fix_directive'] = '中文'
    with pytest.raises(ValueError, match='non-English'):
        m.validate_memory([row], pools(), expected_entries=1)


def test_memory_boundary_rejects_grow_origin_and_pool_overlap():
    m = module()
    row = card()
    row['source']['task_id'] = 303
    with pytest.raises(ValueError, match='D_init'):
        m.validate_memory([row], pools(), expected_entries=1)
    value = pools()
    value['replay'][0]['task_id'] = 1
    with pytest.raises(ValueError, match='overlap'):
        m.validate_memory([card()], value, expected_entries=1)
    value = pools()
    value['replay'][0]['task_id'] = 304
    with pytest.raises(ValueError, match='duplicate'):
        m.validate_memory([card()], value, expected_entries=1)


def test_feedback_removes_tests_answers_raw_exceptions_and_synthetic_cases():
    m = module()
    evidence = {'functional': {'status': 'fail', 'test_input': 'private', 'expected': 'secret',
                              'error': 'assert value == SECRET'},
                'metadata': {'tests': 'private'}, 'answer': 'private',
                'security': {'status': 'pass', 'measured': True}}
    internal = {'measured': True, 'passed': 0, 'measured_count': 1,
                'cases': [{'id': 'c1', 'status': 'fail', 'error': 'private', 'code': 'private'}]}
    result = m.safe_feedback(evidence, internal)
    assert result == {'functional': {'status': 'fail'}, 'security': {'status': 'pass', 'measured': True},
                      'internal_checks': {'measured': True, 'passed': 0, 'measured_count': 1,
                                          'cases': [{'id': 'c1', 'status': 'fail'}]}}


def _pair(*, fail_arm=None, initial_error=False):
    m = module()
    logs, calls, analyses, generations = [], [], [], []
    def request(prompt):
        calls.append(prompt)
        return {'usage': {'prompt_tokens': 1, 'completion_tokens': 2, 'total_tokens': 3}}
    def analyze(contract, counted):
        analyses.append(copy.deepcopy(contract))
        counted('shared')
        if initial_error:
            raise ValueError('broken_analysis')
        return {'vulnerability_hypothesis': ['input risk'], 'functional_invariants': ['return contract']}
    def retrieve(arm, query, counted):
        counted('retrieve:' + arm)
        return [{'invariant_id': arm}]
    def generate(task, cards, **kwargs):
        selected = kwargs['cards_provider']({'description': 'public contract', 'threat_analysis': kwargs['initial_analysis']})
        arm = selected[0]['invariant_id']
        generations.append((arm, copy.deepcopy(kwargs['initial_analysis']), kwargs['previous_evidence']))
        kwargs['requester']('generate:' + arm)
        if arm == fail_arm:
            raise RuntimeError('do not expose raw secret exception')
        return {'code': arm + (':repair' if kwargs['reference_code'] else ':first'),
                'initial_analysis': kwargs['initial_analysis'], 'cards': selected, 'prompts': {'private': 'not saved'},
                'stages': [{'stage': 'generation', 'status': 'completed'}]}
    def validate(task, code):
        passed = code.endswith(':repair')
        return {'functional': {'status': 'pass' if passed else 'fail', 'test_input': 'secret'},
                'security': {'status': 'pass'}}
    results, shared = m.run_pair({'index': 303, 'CWE_ID': '22', 'task_description': {'description': 'public contract'},
                                 'unit_tests': 'never prompt', 'answer': 'never prompt'},
        request=request, retrieve=retrieve, generate=generate, validate=validate,
        propose=lambda *args: {'cases': []}, execute=lambda *args: {'measured': False, 'cases': []},
        measured=lambda value: bool(value), analyze=analyze, on_record=lambda name, row: logs.append((name, row)))
    return results, shared, logs, calls, analyses, generations


def test_pair_shared_analysis_independent_retrieval_and_equal_repair_budget():
    results, shared, logs, calls, analyses, generations = _pair()
    assert len(analyses) == 1
    assert 'unit_tests' not in analyses[0] and 'answer' not in analyses[0]
    assert [row['arm'] for row in results] == module().arm_order(303)
    assert len(results) == 2 and all(len(row['attempts']) == 2 for row in results)
    assert all(not row['attempts'][0]['joint'] and row['attempts'][1]['joint'] for row in results)
    assert all(row['shared_initial_sha256'] == shared['sha256'] for row in results)
    assert all(row['usage']['calls'] == 4 for row in results)
    assert shared['usage']['calls'] == 1 and len(calls) == 9
    assert generations[0][1] == generations[2][1] == shared['initial_analysis']
    assert generations[1][1] is None and generations[3][1] is None
    assert 'secret' not in str(generations)
    assert all('prompts' not in attempt['generation'] for row in results for attempt in row['attempts'])
    assert len(logs) == 3


def test_initial_failure_is_shared_fairly():
    results, shared, _, _, _, generations = _pair(initial_error=True)
    assert shared['error_type'] == 'ValueError'
    assert all(row['shared_initial_error'] == 'ValueError' for row in results)
    assert generations[0][1] == generations[2][1] == {'unmeasured': True}


def test_arm_exception_is_unmeasured_and_does_not_drop_other_arm():
    rows, _, _, _, _, _ = _pair(fail_arm='semantic_llm')
    assert len(rows) == 2
    failed = next(row for row in rows if row['arm'] == 'semantic_llm')
    assert failed['error_type'] == 'RuntimeError'
    assert len(failed['attempts']) == 1 and not failed['attempts'][0]['measured']
    assert 'secret exception' not in str(failed)
    assert next(row for row in rows if row['arm'] == 'hier_llm')['attempts'][-1]['joint']


def test_summary_primary_final_itt_and_complete_pair_sensitivity():
    rows, _, _, _, _, _ = _pair(fail_arm='semantic_llm')
    result = module().summarize(rows)
    assert result['primary_endpoint'] == 'final_joint'
    assert result['arms']['hier_llm']['first']['joint_pass'] == 0
    assert result['arms']['hier_llm']['final']['joint_pass'] == 1
    assert result['arms']['semantic_llm']['final']['unmeasured'] == 1
    assert result['paired']['final_joint']['old_only'] == 1
    assert result['paired']['final_joint']['complete_measured_sensitivity']['pairs'] == 0
    assert result['paired']['final_joint']['complete_measured_sensitivity']['excluded_pairs'] == 1


def test_arm_order_is_reproducible_and_not_always_same():
    orders = [tuple(module().arm_order(i)) for i in range(30)]
    assert len(set(orders)) == 2
    assert orders == [tuple(module().arm_order(i)) for i in range(30)]


def test_unmeasured_flags_never_count_as_success():
    rows, _, _, _, _, _ = _pair()
    for row in rows:
        for attempt in row['attempts']:
            attempt.update(measured=False, functional=True, security=True, joint=True)
    result = module().summarize(rows)
    assert all(value['final']['joint_pass'] == 0 for value in result['arms'].values())
    assert result['paired']['final_joint']['new_only'] == 0


def test_study_orchestration_shares_one_semaphore_and_refuses_overwrite(tmp_path, monkeypatch):
    import json
    from argparse import Namespace
    from methods.sct_trajectory import run_closed_loop, context_pipeline, closed_loop, internal_checks
    from methods.sct_trajectory import retriever, semantic_retrieval
    m = module()
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    fake_runner = tmp_path / 'methods/sct_trajectory/run_semantic_retrieval_study.py'
    monkeypatch.setattr(m, '__file__', str(fake_runner))
    source_names = ('selector_protocol', 'run_semantic_retrieval_study', 'run_branch_gate_study', 'semantic_retrieval',
                    'hier_retrieval', 'retriever', 'context_pipeline', 'agent_pipeline', 'closed_loop',
                    'run_closed_loop', 'internal_checks', 'hsk_tree', 'schemas', 'ablation', 'global_gate', 'english_policy', 'run_artifacts')
    for name in source_names:
        path = fake_runner.with_name(name + '.py')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# fixture', encoding='utf8')
    evidence_path = tmp_path / 'methods/sct_agent/validation_evidence.py'
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text('# fixture', encoding='utf8')
    pool = pools()
    loaded = []
    for name, entries in pool.items():
        for item in entries:
            item['family_id'] = f"family-{item['task_id']}"
            loaded.append({'index': item['task_id'], 'family_id': item['family_id'],
                           'CWE_ID': '22', 'task_description': {'description': 'Return input.'}})
    manifest = {'row_classification': {str(row['index']): {'seed_family_id': row['family_id']} for row in loaded}}
    manifest_path = tmp_path / 'data/external/secodeplt/derived_metadata/family_manifest.json'
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(json.dumps(manifest), encoding='utf8')
    dataset = tmp_path / 'data/external/secodeplt/secodeplt/data.json'
    dataset.parent.mkdir(parents=True)
    dataset.write_text(json.dumps(loaded), encoding='utf8')
    pool_path, memory_path = tmp_path / 'pools.json', tmp_path / 'memory.jsonl'
    pool_path.write_text(json.dumps(pool), encoding='utf8')
    cards = [{**card(), 'invariant_id': f'card-{i}'} for i in range(1939)]
    memory_path.write_text('\n'.join(json.dumps(row) for row in cards), encoding='utf8')
    monkeypatch.setattr(run_closed_loop, '_load_tasks', lambda limit: loaded)
    gates = []
    def request_factory(*args, **kwargs):
        gates.append(kwargs['semaphore'])
        return lambda prompt: {'choices': [{'message': {'content': json.dumps({
            'vulnerability_hypothesis': ['untrusted input'], 'functional_invariants': ['identity']})}}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
    monkeypatch.setattr(run_closed_loop, '_requester', request_factory)
    class FakeEmbedding:
        def __init__(self, **kwargs):
            gates.append(kwargs['semaphore'])
        @property
        def usage(self):
            return {'calls': 0, 'total_tokens': 0}
    monkeypatch.setattr(semantic_retrieval, 'EmbeddingClient', FakeEmbedding)
    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            self.arm = kwargs['retrieval_mode']
            self.last_hier_trace = {'arm': self.arm}
        def search(self, query, limit, pool_nodes):
            return [{'invariant_id': 'card-0'}]
    monkeypatch.setattr(retriever, 'HskTreeRetriever', FakeRetriever)
    def generation(task, cards, **kwargs):
        selected = kwargs['cards_provider']({'description': task['description']})
        return {'code': 'def f(x): return x', 'cards': selected, 'stages': [],
                'initial_analysis': kwargs['initial_analysis']}
    monkeypatch.setattr(context_pipeline, 'run_context_pipeline', generation)
    monkeypatch.setattr(closed_loop, 'validate_and_state', lambda *args, **kwargs: (
        {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}, 'A'))
    monkeypatch.setattr(internal_checks, 'propose_checks', lambda *args: {'cases': []})
    monkeypatch.setattr(internal_checks, 'execute_checks', lambda *args: {'cases': [], 'measured': False})
    args = Namespace(out='translation_work/diagnostics/test', memory=str(memory_path), pools=str(pool_path),
        embedding_cache='translation_work/cache/test.sqlite', limit=1, max_inflight=80, workers=2,
        max_tokens=3072, timeout=90, validation_timeout=20, embedding_model='text-embedding-3-large')
    result = m.run_study(args)
    out = tmp_path / args.out
    assert len(gates) == 2 and gates[0] is gates[1]
    assert result['input_unchanged'] and result['source_unchanged']
    assert result['paired']['final_joint']['pairs'] == 1
    rows = [json.loads(line) for line in (out / 'rows.jsonl').read_text(encoding='utf8').splitlines()]
    assert len(rows) == 2 and all(len(row['attempts']) == 1 for row in rows)
    assert all(row['attempts'][0]['retrieval_calls'][0]['selection_trace']['arm'] == row['arm'] for row in rows)
    assert json.loads((out / 'status.json').read_text())['status'] == 'completed'
    assert result['chat_usage']['calls'] == result['shared_initial_chat_usage']['calls'] == 1
    with pytest.raises(FileExistsError):
        m.run_study(args)

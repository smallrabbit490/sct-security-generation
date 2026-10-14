"""语义检索真实训练接线及技术缺测回归；只使用本地替身，不发模型请求。"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from methods.sct_trajectory import closed_loop as cl
from methods.sct_trajectory.error_ledger import ErrorLedger
from methods.sct_trajectory.hsk_tree import HskTree, LanguageLeaf, SecurityInvariantNode
from methods.sct_trajectory.retriever import HskTreeRetriever


def row(index=1):
    return {'index': index, 'CWE_ID': '22', 'task_description': {
        'function_name': 'f', 'description': 'Return True for valid input.'}}


def node():
    return SecurityInvariantNode('candidate', '22', 'Preserve valid input.',
        language_leaves={'python': LanguageLeaf('python')})


def runner(**kwargs):
    return cl.CleRunner(lambda prompt: {}, HskTree(), ErrorLedger(), workers=1,
        phase3_workers=1, context_pipeline=True, retrieval_mode='semantic_llm',
        embedding_client=object(), gate_select_mode='fixed', **kwargs)


@pytest.mark.parametrize('path', ['phase1', 'phase2', 'branches', 'phase3', 'final'])
def test_every_cle_retriever_constructor_receives_shared_embedding_client(monkeypatch, path):
    """执行各真实阶段入口到检索构造边界，防止某轮静默退回旧规则检索。"""
    run = runner(branch_count=3 if path == 'branches' else 1)
    calls = []
    class StopAtRetriever(Exception):
        pass
    def capture(*args, **kwargs):
        calls.append(kwargs)
        if path == 'phase3' and kwargs['retrieval_mode'] != 'semantic_llm':
            # 入口先构造未使用的旧规则实例，再替换为部署检索；确认最后实际实例。
            return object()
        raise StopAtRetriever()
    monkeypatch.setattr(cl, 'HskTreeRetriever', capture)
    monkeypatch.setattr(cl, 'extract_initial_hypothesis', lambda *a, **k: {
        'id': 'seed', 'principle': 'Preserve valid input.', 'applicability': 'Boolean result'})
    try:
        if path == 'phase1':
            run._phase1_one(row())
        elif path == 'phase2':
            run.phase2_evolve([])
        elif path == 'branches':
            run._phase2_one(row(), None, repairs=0)
        elif path == 'phase3':
            run.phase3_audit([])
        else:
            run.final_evaluate([])
    except StopAtRetriever:
        pass
    assert len(calls) == (2 if path == 'phase3' else 1)
    assert calls[-1]['retrieval_mode'] == 'semantic_llm'
    assert calls[-1]['embedding_client'] is run.embedding_client
    assert calls[-1]['requester'] is not None


@pytest.mark.parametrize('failure', ['retrieval', 'validator_exception', 'validator_unmeasured'])
def test_real_candidate_gate_records_technical_failure_as_unmeasured(monkeypatch, failure):
    """真实 Phase3 调用/状态提交：技术失败不产生晋升或有害退休证据。"""
    run = runner()
    candidate = node()
    run.experience_pool.append(candidate)
    def pipeline(*args, **kwargs):
        return {'code': 'def f(): return True',
                'error_type': 'retrieval:EmbeddingError' if failure == 'retrieval' else None}
    def validate(*args, **kwargs):
        if failure == 'validator_exception':
            raise OSError('local worker unavailable')
        return {'functional': {'status': 'unmeasured'}, 'security': {'status': 'unmeasured'}}, 'D'
    monkeypatch.setattr(cl, 'run_pipeline', pipeline)
    monkeypatch.setattr(cl, 'validate_and_state', validate)
    report = run.phase3_audit([row()], entries=[candidate], max_entries=0,
                             audit_per_candidate=1, min_audit_tasks=1)
    assert report['audited'] == 1
    assert report['promoted'] == 0
    assert candidate.status == 'unmeasured'
    assert candidate.status not in ('retired', 'active')
    assert report['gate_records'][0]['decision'] == 'unmeasured'
    detail = report['audit_detail'][0]
    assert detail['decision'] == 'unmeasured'
    assert detail['security_regressions'] == detail['functional_regressions'] == 0
    assert any(reason.startswith('audit_error:') for reason in detail['reasons'])
    # 当前生命周期策略：缺测卡保留在池，但不在可检索状态集合，不等于已经删库。
    assert candidate in run.experience_pool
    assert candidate.status not in run.ablation.retrieval_statuses


def test_regression_technical_failure_raises_instead_of_counting_regressions(monkeypatch):
    run = runner()
    monkeypatch.setattr(cl, 'run_pipeline', lambda *a, **k: {
        'code': 'def f(): return True', 'error_type': 'retrieval:EmbeddingError'})
    with pytest.raises(RuntimeError, match='unmeasured_regression_pipeline'):
        run._regression_probe([row(1), row(2)], lambda query: [], samples=3)


def test_retrieval_audit_is_thread_local_under_overlapping_tasks(monkeypatch):
    """同步屏障确保两个线程已写入审计后再读取，可检出最后一次写入覆盖。"""
    from methods.sct_trajectory import semantic_retrieval
    candidate = node()
    retriever = HskTreeRetriever(HskTree(), requester=lambda prompt: {},
        retrieval_mode='semantic_llm', embedding_client=object())
    barrier = threading.Barrier(2)
    def select(task, nodes, requester, embedding_client, limit):
        return [candidate], {'status': 'completed', 'query_task': task['task_id']}
    monkeypatch.setattr(semantic_retrieval, 'semantic_select', select)
    def work(identifier):
        cards = retriever.search({'task_id': identifier, 'language': 'python'}, pool_nodes=[candidate])
        barrier.wait(timeout=5)
        return retriever.last_hier_trace['query_task'], cards[0]['retrieval_audit']['query_task']
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(work, [1, 2]))
    assert result == [(1, 1), (2, 2)]
    assert retriever.last_hier_trace is None


def test_final_evaluation_retains_degraded_retrieval_and_adoption_audit(monkeypatch):
    """最终评测保留原始/注入区别和错误；代码实测通过不抹去链路缺陷。"""
    run = runner()
    def pipeline(*args, **kwargs):
        return {'code': 'def f(): return True', 'error_type': 'retrieval:EmbeddingError',
                'workflow_completed': False, 'cards': [],
                'retrieved_cards': [{'invariant_id': 'rejected'}],
                'adoption': {'applied_ids': [], 'rejected_ids': ['rejected']},
                'stages': [{'stage': 'retrieval', 'status': 'degraded'}]}
    monkeypatch.setattr(cl, 'run_pipeline', pipeline)
    monkeypatch.setattr(cl, 'validate_and_state', lambda *a, **k: (
        {'functional': {'status': 'pass'}, 'security': {'status': 'pass'}}, 'A'))
    result = run.final_evaluate([row()])
    actual = result['rows'][0]
    assert actual['state'] == 'A'
    assert actual['pipeline_error'] == 'retrieval:EmbeddingError'
    assert actual['workflow_completed'] is False
    assert actual['injected_cards'] == []
    assert actual['retrieved_cards'][0]['invariant_id'] == 'rejected'
    assert actual['adoption']['rejected_ids'] == ['rejected']

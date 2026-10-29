"""TLS失败后的控制异常须唤醒共享向量等待者；全程离线。"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from configs.cle_v41_relation_20261026.execution import StudyExecution
from configs.cle_v41_completion_20261026.batch import selector_pre_dispatch_failure
from methods.sct_trajectory.replay_journal import ReplayStop, RequestJournal
from methods.sct_trajectory.semantic_retrieval import EmbeddingClient, EmbeddingError


def test_control_stop_wakes_embedding_followers(tmp_path, monkeypatch):
    client = EmbeddingClient(cache_path=tmp_path / "vectors.sqlite", flight_wait_timeout=.5)
    started, release, following = (threading.Event() for _ in range(3))

    def stopped_request(texts):
        started.set()
        assert release.wait(2)
        raise ReplayStop("saved_transport_stop")

    monkeypatch.setattr(client, "_request", stopped_request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(client.embed, ["same public query"])
        assert started.wait(2)
        flight = next(iter(client._pending.values()))
        original_wait = flight.event.wait

        def followed(timeout):
            following.set()
            return original_wait(timeout)

        monkeypatch.setattr(flight.event, "wait", followed)
        follower = pool.submit(client.embed, ["same public query"])
        assert following.wait(2)
        release.set()
        with pytest.raises(ReplayStop, match="saved_transport_stop"):
            owner.result(timeout=2)
        with pytest.raises(EmbeddingError, match="ReplayStop"):
            follower.result(timeout=2)
    assert not client._pending
    assert not client._vectors


def test_embedding_stop_marks_dispatch_reason(tmp_path, monkeypatch):
    monkeypatch.setattr("methods.sct_trajectory.replay_journal.ensure_model_call_allowed", lambda model: None)
    io = StudyExecution.__new__(StudyExecution)
    io.reason = None
    io.wait_allowed = lambda: None
    journal = RequestJournal(tmp_path / "requests")
    io.journal = lambda identity: journal

    def failed_embedding(texts):
        raise EmbeddingError("observed_TLS_failure")

    with pytest.raises(ReplayStop):
        io.embedding(["public query"], failed_embedding)
    assert io.reason == "logical_embedding_failed_or_unresolved"


def test_only_observed_pre_selection_wait_failure_is_recoverable():
    row = {'stage_id': 'D03a', 'status': 'selection_unmeasured', 'retrieval_trace': {
        'errors': ['embedding_flight_wait_timeout'], 'candidate_ids': [], 'selected_ids': []}}
    assert selector_pre_dispatch_failure(row)
    assert not selector_pre_dispatch_failure({**row, 'status': 'completed'})
    assert not selector_pre_dispatch_failure({**row, 'stage_id': 'D03b'})
    assert not selector_pre_dispatch_failure({**row, 'retrieval_trace': {
        'errors': ['invalid_selector_output'], 'candidate_ids': ['card'], 'selected_ids': []}})

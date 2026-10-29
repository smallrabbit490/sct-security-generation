"""复现已观测并发错误，并验证未派发记录不得掩盖实际物理请求。"""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest

from configs.cle_weekly_fs_embedding_recovery_20261028 import resume


def test_other_embedding_can_finish_while_recovery_is_inflight():
    started, finish = Event(), Event()
    saved = []

    def original(texts, call):
        if texts == ['pending']:
            started.set()
            assert finish.wait(2)
        return {'vectors': texts}

    io = SimpleNamespace(embedding=original, save=lambda *args: saved.append(args))
    resume.bind_embedding(io, {'prompt': '["pending"]'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(io.embedding, ['pending'], None)
        assert started.wait(2)
        try:
            assert io.embedding(['other worker'], None) == {'vectors': ['other worker']}
        finally:
            finish.set()
        assert pending.result() == {'vectors': ['pending']}
    assert len(saved) == 1
    assert saved[0][1]['identity'] == resume.IDENTITY


@pytest.fixture
def sources(tmp_path, monkeypatch):
    values = [tmp_path / 'segment_019', tmp_path / 'segment_020']
    records = []
    for source, status in zip(values, ['failed_or_unresolved', 'prepared']):
        path = source / 'journals/embedding/requests/pending.json'
        resume.write_json(path, {'identity': resume.IDENTITY, 'settings': {
            'model': 'text-embedding-3-large', 'operation': 'embedding'},
            'prompt': '["pending"]', 'selector': False, 'status': status})
        records.append(str(path))
    resume.write_json(values[0] / 'wire/0001.request.json',
                      {'body': {'model': 'text-embedding-3-large', 'input': ['pending']}})
    resume.write_json(values[0] / 'wire/0001.status.json', {'status': 'transport_error',
        'http_status': None, 'error_type': 'URLError', 'reason_type': 'SSLEOFError'})
    resume.write_json(values[-1] / 'budget.json', {'transport_attempts_including_prior': 1,
        'charged_tokens_including_unknown_and_inflight_bounds': 12, 'cap_tokens': 100, 'cap_HTTP': 10})
    monkeypatch.setattr(resume, 'classifier', lambda: lambda _: ({}, records))
    return values, records


def test_observed_failed_and_undispatched_pair_keeps_old_records(sources):
    values, records = sources
    before = [resume.read(p) for p in records]
    assert resume.inspect_sources(values)['records'] == records
    assert [resume.read(p) for p in records] == before


def test_prepared_with_physical_attempt_is_rejected(sources):
    values, _ = sources
    resume.write_json(values[-1] / 'wire/0001.request.json',
                      {'body': {'model': 'text-embedding-3-large', 'input': ['pending']}})
    with pytest.raises(resume.ReplayStop, match='has_physical_request'):
        resume.inspect_sources(values)


def test_auth_failure_is_not_transport_recovery(sources):
    values, _ = sources
    resume.write_json(values[0] / 'wire/0001.status.json',
                      {'status': 'response', 'http_status': 401})
    with pytest.raises(resume.ReplayStop, match='not_observed_TLS_failure'):
        resume.inspect_sources(values)


def test_unknown_reservation_cannot_be_dropped(sources):
    values, _ = sources
    path = values[-1] / 'budget.json'
    budget = resume.read(path)
    budget['transport_attempts_including_prior'] = 2
    resume.write_json(path, budget)
    with pytest.raises(resume.ReplayStop, match='unrecorded_physical_reservation'):
        resume.inspect_sources(values)

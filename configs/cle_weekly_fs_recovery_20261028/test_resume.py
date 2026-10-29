"""仅验证本次恢复缺陷：未派发判断和重复启动识别，禁止真实 API。"""
from types import SimpleNamespace

import pytest

from configs.cle_weekly_fs_recovery_20261028 import resume


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    source = tmp_path / 'segment_018'
    path = source / 'journals/embedding/requests/pending.json'
    resume.write_json(path, {'status': 'prepared', 'identity': 'embedding-000001',
        'settings': {'model': 'text-embedding-3-large', 'operation': 'embedding'},
        'prompt': '["public query"]', 'selector': False})
    resume.write_json(source / 'budget.json', {'transport_attempts_including_prior': 0,
        'charged_tokens_including_unknown_and_inflight_bounds': 10,
        'cap_tokens': 100, 'cap_HTTP': 10})
    pending = {('966_r1_BM', 'model-000001'): [{'path': 'existing_failure.json'}]}
    def probe():
        return None
    helper = {'sources': lambda: [source], 'classify': lambda _: (pending, [str(path)]),
              'probe': probe}
    monkeypatch.setattr(resume.runpy, 'run_path', lambda _: helper)
    resume.install.cache_clear()
    yield source, path, helper
    resume.install.cache_clear()


def test_only_exact_undispatched_prepared_record_is_excluded(prepared):
    source, path, helper = prepared
    _, _, audit = resume.install()
    pending, rejected = helper['probe'].__globals__['classify']([source])
    assert pending and rejected == []
    assert audit['prepared_record'] == str(path)
    assert resume.read(path)['status'] == 'prepared'


def test_prepared_with_physical_request_is_rejected(prepared):
    source, _, _ = prepared
    resume.write_json(source / 'wire/0000001.request.json',
        {'body': {'model': 'text-embedding-3-large', 'input': ['public query']}})
    with pytest.raises(resume.ReplayStop, match='has_physical_request'):
        resume.install()


def test_unrecorded_budget_reservation_is_rejected(prepared):
    source, _, _ = prepared
    budget = resume.read(source / 'budget.json')
    budget['transport_attempts_including_prior'] = 1
    resume.write_json(source / 'budget.json', budget)
    with pytest.raises(resume.ReplayStop, match='reservation_without_wire'):
        resume.install()


@pytest.mark.parametrize('running', [False, True])
def test_launch_distinguishes_own_launcher_and_any_embedding_task(tmp_path, monkeypatch, running):
    monkeypatch.setattr(resume, 'RUN', tmp_path)
    monkeypatch.setattr(resume, 'EVIDENCE', tmp_path / 'repair')
    monkeypatch.setattr(resume, 'ensure_model_call_allowed', lambda _: None)
    monkeypatch.setattr(resume, 'active', lambda _: False)
    line = (resume.MODULE + ' launch' if not running else
            'python -m configs.cle_weekly_embedding_recovery_20261027.resume run 1097')
    monkeypatch.setattr(resume, 'processes', lambda: [{'CommandLine': line}])
    monkeypatch.setattr(resume, 'proxy_ready', lambda: True)
    monkeypatch.setattr(resume, 'probe', lambda: {'model_prefix': {'saved_rows': 687}})
    launched = []
    def spawn(command, **kwargs):
        launched.append(command)
        return SimpleNamespace(pid=123)
    monkeypatch.setattr(resume.subprocess, 'Popen', spawn)
    registry = tmp_path / 'workbench_monitor/autonomy/registered_workers.json'
    resume.write_json(registry, [{'pid': 456, 'package': 'OTHER'}])
    result = resume.launch()
    assert result['status'] == ('already_running' if running else 'launched')
    assert bool(launched) is not running
    entries = resume.read(registry)
    assert entries[0] == {'pid': 456, 'package': 'OTHER'}
    if not running:
        assert entries[-1]['workers'] == 3

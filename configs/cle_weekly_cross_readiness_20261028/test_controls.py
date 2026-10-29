"""本项必要的恢复、凭证、时段、累计预算和 worker 约束测试；全部封网。"""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
from configs.cle_v41_relation_20261026.execution import StudyExecution, DispatchDenied
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from configs.cle_v41_migration_20261025.resume import RecoveryBudget
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from methods.sct_trajectory.provider_policy import ModelTimeWindowError
from . import execute, recovery, reuse
from .prepare import CAP
from .runtime import json_encoding


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr('socket.create_connection', reuse.forbidden)
    monkeypatch.setattr('socket.socket.connect', reuse.forbidden)


def test_zero_workers_cannot_launch(monkeypatch):
    monkeypatch.setattr(execute, 'active_workers', lambda: pytest.fail('must reject allocation first'))
    assert execute.launch(0)['status'] == 'waiting_capacity'


def test_running_instance_prevents_launch(monkeypatch):
    monkeypatch.setattr(execute, 'active_workers', lambda: [{'ProcessId': 9, 'package': 'FFS'}])
    assert execute.launch(3)['status'] == 'queued_behind_running_experiment'


def test_registration_retains_other_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(execute, 'RUN', tmp_path)
    monkeypatch.setattr(execute.runtime, 'PACKAGE', tmp_path / 'C41')
    path = tmp_path / 'workbench_monitor/autonomy/registered_workers.json'
    prior = [{'pid': 11, 'package': 'FR', 'workers': 1, 'command_marker': 'unchanged'}]
    write_json(path, prior)
    execute.register(type('Process', (), {'pid': 22})(), ['python', '-m', execute.runtime.MODULE, 'run'], 3)
    rows = json.loads(path.read_text())
    assert rows[0] == prior[0] and rows[1]['pid'] == 22 and rows[1]['workers'] == 3


def save_pending(tmp_path, *, status=200, raw=None, category='network_error'):
    record = {'status': 'failed_or_unresolved', 'settings': SETTINGS, 'prompt': 'same',
        'selector': False, 'identity': 'identity-000001', 'diagnostics': [{'category': category}]}
    write_json(tmp_path / 'journals/cell/requests/item.json', record)
    write_json(tmp_path / 'wire/0000001.request.json', {'body': {'model': SETTINGS['model'],
        'messages': [{'role': 'user', 'content': 'same'}], 'max_tokens': 4096}})
    write_json(tmp_path / 'wire/0000001.status.json', {'status': 'response_read_error' if status == 200 else 'transport_error',
        'http_status': status, 'error_type': 'ValueError' if status == 200 else 'HTTPError' if status else 'URLError'})
    if raw is not None:
        (tmp_path / 'wire/0000001.response.raw').write_bytes(raw)
    return record


def test_HTTP200_partial_raw_classified_but_finished_raw_never_reissued(tmp_path):
    save_pending(tmp_path, raw=b'data: {"choices":[{"index":0,"delta":{"content":"partial"},"finish_reason":null}]}\n')
    assert len(recovery.classify([tmp_path])) == 1
    (tmp_path / 'wire/0000001.response.raw').write_bytes(b'data: {"choices":[{"finish_reason":"stop"}]}\n')
    with pytest.raises(ReplayStop, match='nontransport_unresolved'):
        recovery.classify([tmp_path])


@pytest.mark.parametrize('status', [401, 402, 403, 429])
def test_auth_quota_errors_never_classified_as_transport(tmp_path, status):
    save_pending(tmp_path, status=status)
    with pytest.raises(ReplayStop, match='nontransport_unresolved'):
        recovery.classify([tmp_path])


def test_completed_response_supersedes_unknown_failure_without_changing_old_file(tmp_path):
    record = save_pending(tmp_path, status=None)
    old = (tmp_path / 'journals/cell/requests/item.json').read_bytes()
    assert len(recovery.classify([tmp_path])) == 1
    other = tmp_path / 'other'
    write_json(other / 'journals/cell/requests/item.json', {**record, 'status': 'completed', 'response': {'raw': 'saved'}})
    assert recovery.classify([tmp_path, other]) == {}
    assert (tmp_path / 'journals/cell/requests/item.json').read_bytes() == old


def test_budget_resume_retains_unknown_attempts_and_same_cap(tmp_path):
    save_pending(tmp_path / 'source', status=None)
    budget = RecoveryBudget(tmp_path / 'budget.json', [tmp_path / 'source/wire'],
        max_tokens=CAP['conservative_model_and_embedding_tokens'], max_calls=1, max_embedding=1)
    assert budget.snapshot()['transport_attempts_including_prior'] == 1
    assert budget.snapshot()['charged_tokens_including_unknown_and_inflight_bounds'] > 4096
    with pytest.raises(RuntimeError, match='budget_exhausted'):
        budget.reserve({'model': SETTINGS['model'], 'messages': [], 'max_tokens': 4096})


@pytest.mark.parametrize('now', [datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc),
                                  datetime(2026, 10, 28, 6, 0, tzinfo=timezone.utc)])
@pytest.mark.parametrize('model', [SETTINGS['model'], 'text-embedding-3-large'])
def test_each_physical_request_checks_forbidden_window_before_reserve(tmp_path, now, model):
    import urllib.request
    protocol = {'paid_execution_enabled': True, 'planned_P7': 1, 'budget_proposed': CAP}
    io = StudyExecution(tmp_path / 'stage', protocol, [{'cell_id': 'test'}], client_factory=lambda _: None,
        physical_open=lambda *a, **k: pytest.fail('physical request forbidden'), live=True, fixed_eight=False, now=lambda: now)
    body = {'model': model, 'messages': [{'role': 'user', 'content': 'test'}], 'max_tokens': 4096}
    with io.physical_records(), pytest.raises(ModelTimeWindowError):
        urllib.request.urlopen(urllib.request.Request('https://api.chatanywhere.org/v1/chat/completions',
            data=json.dumps(body).encode()))
    assert io.budget.entries == [] and not list((io.root / 'wire').glob('*.request.json'))


def test_prompt_or_repeat_mismatch_cannot_be_credited(tmp_path):
    source = tmp_path / 'source'
    write_json(source / 'shared_starts/90_r1.json', {'task_id': '90', 'repeat': 2,
        'initial_analysis': {}, 'error_type': None})
    with pytest.raises(ReplayStop, match='repeat_identity'):
        reuse.shared_start([source], '90', 1)
    saved = {'attempts': [{'code': 'A', 'generation': {'plan': 'plan'}}]}
    with pytest.raises(ReplayStop, match='native_difference'):
        reuse.compare_attempts(saved, {'attempts': [{'code': 'B', 'generation': {'plan': 'plan'}}]})


def test_partial_initial_then_complete_selection_is_valid_and_conflicts_still_fail(tmp_path):
    partial = {'task_id': '90', 'initial_analysis': {'same': True}, 'error_type': None}
    complete = {**partial, 'repeat': 1, 'query': {}, 'public_contract': {},
        'selected_cards': [], 'retrieval_trace': {'duration_ms': 1}}
    write_json(tmp_path / 's1/shared_starts/90_r1.json', partial)
    write_json(tmp_path / 's2/shared_starts/90_r1.json', complete)
    start, evidence = reuse.shared_start([tmp_path / 's1', tmp_path / 's2'], '90', 1)
    assert start == complete and len(evidence) == 2
    write_json(tmp_path / 's2/shared_starts/90_r1.json', {**complete, 'initial_analysis': {'changed': True}})
    with pytest.raises(ReplayStop, match='initial_conflict'):
        reuse.shared_start([tmp_path / 's1', tmp_path / 's2'], '90', 1)


def test_actual_FFS_surrogate_recovery_preserves_JSON_value_and_normal_prompt_bytes():
    normal = json.dumps({'x': '中文'}, ensure_ascii=False)
    with json_encoding():
        assert json.dumps({'x': '中文'}, ensure_ascii=False) == normal
        encoded = json.dumps({'x': '\ud800'}, ensure_ascii=False)
        assert json.loads(encoded)['x'] == '\ud800'
        assert encoded.encode('utf-8')

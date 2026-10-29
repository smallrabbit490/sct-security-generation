"""用户指定的模型调用时段：纯离线验证边界、时区及排队跨界，不读取凭据。"""
from datetime import datetime

import pytest

from methods.sct_trajectory import provider_policy as policy
from methods.sct_trajectory import run_closed_loop as runner


@pytest.mark.parametrize('stamp,blocked', [
    ('2026-10-26T08:59:59+08:00', False),
    ('2026-10-26T09:00:00+08:00', True),
    ('2026-10-26T11:59:59+08:00', True),
    ('2026-10-26T12:00:00+08:00', False),
    ('2026-10-26T13:59:59+08:00', False),
    ('2026-10-26T14:00:00+08:00', True),
    ('2026-10-26T17:59:59+08:00', True),
    ('2026-10-26T18:00:00+08:00', False),
    ('2026-10-30T10:00:00+08:00', True),
    ('2026-10-24T10:00:00+08:00', False),
    ('2026-10-25T15:00:00+08:00', False),
    ('2026-10-26T01:30:00+00:00', True),
    ('2026-10-26T04:00:00+00:00', False),
])
def test_weekday_boundaries_and_timezone(stamp, blocked):
    now = datetime.fromisoformat(stamp)
    if blocked:
        with pytest.raises(policy.ModelTimeWindowError):
            policy.ensure_model_call_allowed(policy.CURRENT_MODEL, now)
    else:
        policy.ensure_model_call_allowed(policy.CURRENT_MODEL, now)


def test_historical_model_names_are_not_remapped_or_restricted():
    policy.ensure_model_call_allowed('deepseek-v3.2', datetime.fromisoformat('2026-10-26T10:00:00+08:00'))


def test_blocked_time_stops_before_loading_credentials_or_http(monkeypatch):
    def check(model):
        policy.ensure_model_call_allowed(model, datetime.fromisoformat('2026-10-26T10:00:00+08:00'))
    monkeypatch.setattr(runner, 'ensure_model_call_allowed', check)
    monkeypatch.setattr(runner, 'load_key', lambda: pytest.fail('must not load credentials'))
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('must not send HTTP'))
    request = runner._requester(policy.CURRENT_MODEL, 1)
    with pytest.raises(policy.ModelTimeWindowError):
        request('public task')


def test_queue_crossing_into_blocked_time_stops_without_retry(monkeypatch):
    checks = []
    def check(model):
        checks.append(model)
        stamp = '2026-10-26T08:59:59+08:00' if len(checks) == 1 else '2026-10-26T09:00:00+08:00'
        policy.ensure_model_call_allowed(model, datetime.fromisoformat(stamp))
    monkeypatch.setattr(runner, 'ensure_model_call_allowed', check)
    monkeypatch.setattr(runner, 'load_key', lambda: pytest.fail('must not load credentials'))
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('must not send HTTP'))
    request = runner._requester(policy.CURRENT_MODEL, 1, retry_backoff=0)
    with pytest.raises(policy.ModelTimeWindowError) as exc:
        request('public task')
    assert checks == [policy.CURRENT_MODEL, policy.CURRENT_MODEL]
    assert exc.value.safe_diagnostics == [{'category': 'model_time_window_blocked', 'attempt': 1}]


def test_allowed_time_preserves_new_model_and_user_message(monkeypatch):
    import json
    observed = []
    monkeypatch.setattr(runner, 'ensure_model_call_allowed', lambda model:
        policy.ensure_model_call_allowed(model, datetime.fromisoformat('2026-10-26T12:00:00+08:00')))
    monkeypatch.setattr(runner, 'load_key', lambda: 'offline-placeholder')
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return b'{"ok":true}'
    def fake(request, timeout):
        observed.append(json.loads(request.data))
        return Response()
    monkeypatch.setattr('urllib.request.urlopen', fake)
    assert runner._requester(policy.CURRENT_MODEL, 1, max_attempts=1)('public task') == {'ok': True}
    assert len(observed) == 1 and observed[0]['model'] == policy.CURRENT_MODEL
    assert observed[0]['messages'] == [{'role': 'user', 'content': 'public task'}]


def test_dispatch_is_rechecked_after_payload_and_credential_preparation(monkeypatch):
    checks = []
    def check(model):
        checks.append(model)
        stamp = '2026-10-26T08:59:59+08:00' if len(checks) < 3 else '2026-10-26T09:00:00+08:00'
        policy.ensure_model_call_allowed(model, datetime.fromisoformat(stamp))
    monkeypatch.setattr(runner, 'ensure_model_call_allowed', check)
    monkeypatch.setattr(runner, 'load_key', lambda: 'offline-placeholder')
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('must not send HTTP'))
    with pytest.raises(policy.ModelTimeWindowError):
        runner._requester(policy.CURRENT_MODEL, 1)('public task')
    assert len(checks) == 3

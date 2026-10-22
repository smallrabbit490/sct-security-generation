"""请求器离线回归：不使用真实凭据或网络。"""
import json
import threading
import time
from urllib.error import HTTPError

import pytest
from methods.sct_trajectory import run_closed_loop as runner


def test_selector_budget_caps_http_attempts_tokens_and_elapsed(monkeypatch):
    from methods.sct_trajectory.selector_protocol import SelectorPrompt
    release = threading.Event()
    gate = threading.BoundedSemaphore(1)
    bodies = []
    def slow(request, timeout):
        bodies.append(json.loads(request.data))
        release.wait(2)
        return Response()
    request = build(monkeypatch, slow, semaphore=gate)
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            request(SelectorPrompt('Return JSON', deadline=started + .04))
        assert time.monotonic() - started < .3
        assert len(bodies) == 1 and bodies[0]['max_tokens'] == 256
        assert not gate.acquire(blocking=False)
    finally:
        release.set()
    assert gate.acquire(timeout=1)
    gate.release()


def test_selector_deadline_prevents_http_after_queue_wait(monkeypatch):
    from methods.sct_trajectory.selector_protocol import SelectorPrompt
    calls = []
    request = build(monkeypatch, lambda *a, **k: calls.append(1), semaphore=threading.Semaphore(0))
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        request(SelectorPrompt('Return JSON', deadline=started + .03))
    assert time.monotonic() - started < .2 and calls == []


def test_requester_error_retains_structured_safe_diagnostic(monkeypatch):
    from methods.sct_trajectory.selector_protocol import SelectorPrompt
    def fake(*args, **kwargs):
        raise HTTPError('https://private-url', 429, 'secret body', {}, None)
    request = build(monkeypatch, fake, max_inflight=1)
    with pytest.raises(RuntimeError) as error:
        request(SelectorPrompt('Only JSON', deadline=time.monotonic()+1))
    actual = error.value.safe_diagnostics
    assert len(actual) == 1
    assert actual[0]['http_status'] == 429
    assert actual[0]['category'] == 'http_error'
    assert 'secret' not in json.dumps(actual) and 'private' not in json.dumps(actual)


def test_selector_separate_inflight_gate_limits_long_context_bursts(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from methods.sct_trajectory.selector_protocol import SelectorPrompt
    lock = threading.Lock()
    state = {'active': 0, 'peak': 0}
    def fake(*args, **kwargs):
        with lock:
            state['active'] += 1
            state['peak'] = max(state['peak'], state['active'])
        time.sleep(.01)
        with lock:
            state['active'] -= 1
        return Response()
    request = build(monkeypatch, fake, max_inflight=8, selector_max_inflight=2)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: request(SelectorPrompt('JSON', deadline=time.monotonic()+1)), range(8)))
    assert all(r['ok'] for r in results) and state['peak'] == 2


def test_selector_gate_timeout_retains_both_slots_until_worker_ends(monkeypatch):
    from methods.sct_trajectory.selector_protocol import SelectorPrompt
    release = threading.Event()
    calls = []
    def slow(*args, **kwargs):
        calls.append(1)
        release.wait(1)
        return Response()
    request = build(monkeypatch, slow, max_inflight=8, selector_max_inflight=1)
    try:
        with pytest.raises(TimeoutError):
            request(SelectorPrompt('JSON', deadline=time.monotonic()+.03))
        with pytest.raises(TimeoutError) as error:
            request(SelectorPrompt('JSON', deadline=time.monotonic()+.03))
        assert len(calls) == 1
        assert error.value.safe_diagnostics[-1]['category'] == 'selector_gate_wait_timeout'
    finally:
        release.set()


class Response:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self): return json.dumps({'ok': True}).encode()


def build(monkeypatch, fake, **kwargs):
    monkeypatch.setattr(runner, 'load_key', lambda: 'offline-secret')
    monkeypatch.setattr('urllib.request.urlopen', fake)
    return runner._requester('offline', 1, hard_timeout=0.06, gate_wait_timeout=0.15,
        retry_backoff=0, circuit_cooldown=0.08, **kwargs)


def test_explicit_thinking_control_preserves_other_callers_default(monkeypatch):
    bodies = []
    def fake(request, timeout):
        bodies.append(json.loads(request.data))
        return Response()
    build(monkeypatch, fake)('Return JSON')
    build(monkeypatch, fake, thinking='disabled')('Return JSON')
    assert 'thinking' not in bodies[0]
    assert bodies[1]['thinking'] == {'type': 'disabled'}


def test_late_error_does_not_poison_successful_retry(monkeypatch):
    calls = []
    def fake(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            time.sleep(0.085)
            raise OSError('sensitive-late-message')
        time.sleep(0.04)
        return Response()
    request = build(monkeypatch, fake, max_inflight=2)
    assert request('private prompt') == {'ok': True}
    assert len(calls) == 2


def test_gate_retained_until_http_exits(monkeypatch):
    lock = threading.Lock()
    state = {'active': 0, 'peak': 0, 'calls': 0}
    def fake(*args, **kwargs):
        with lock:
            state['active'] += 1
            state['calls'] += 1
            call = state['calls']
            state['peak'] = max(state['peak'], state['active'])
        try:
            time.sleep(0.085 if call == 1 else 0.005)
            return Response()
        finally:
            with lock: state['active'] -= 1
    request = build(monkeypatch, fake, max_inflight=1)
    assert request('private prompt')['ok']
    assert state['peak'] == 1 and state['calls'] == 2


def test_stuck_http_has_bounded_gate_wait_and_recovers(monkeypatch):
    release = threading.Event()
    calls = []
    def fake(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1: release.wait(2)
        return Response()
    request = build(monkeypatch, fake, max_inflight=1)
    started = time.monotonic()
    try:
        with pytest.raises(TimeoutError, match='gate_wait_timeout') as error:
            request('private prompt')
        assert len(error.value.diagnostics) == 2
        assert 'hard_timeout' in error.value.diagnostics[0]
        assert 'gate_wait_timeout' in error.value.diagnostics[1]
        assert time.monotonic() - started < 0.8
        assert len(calls) == 1
    finally:
        release.set()
    time.sleep(0.02)
    assert request('retry')['ok']


def test_circuit_stops_http_and_cooldown_recovers_without_secret(monkeypatch):
    calls = []
    healthy = [False]
    def fake(*args, **kwargs):
        calls.append(1)
        if not healthy[0]:
            raise HTTPError('https://secret-url', 429, 'private-message', {}, None)
        return Response()
    request = build(monkeypatch, fake, max_inflight=1, circuit_failures=2)
    with pytest.raises(RuntimeError) as error:
        request('private prompt')
    assert 'HTTPError' in str(error.value) and '429' in str(error.value)
    assert len(error.value.diagnostics) == 2
    assert all('http_status=429' in item for item in error.value.diagnostics)
    assert 'private' not in str(error.value) and 'secret' not in str(error.value)
    count = len(calls)
    with pytest.raises(RuntimeError, match='llm_circuit_open') as opened:
        request('again')
    assert any('http_status=429' in item for item in opened.value.diagnostics)
    assert len(calls) == count
    healthy[0] = True
    time.sleep(0.10)
    assert request('recovered')['ok']


def test_exhausted_attempts_expose_safe_diagnostics(monkeypatch):
    def fake(*args, **kwargs):
        raise HTTPError('https://private-url', 503, 'secret body', {}, None)
    request = build(monkeypatch, fake, max_inflight=1)
    with pytest.raises(RuntimeError) as error:
        request('private prompt')
    assert len(error.value.diagnostics) == 3
    assert all('http_status=503' in item for item in error.value.diagnostics)
    assert not any('private' in item or 'secret' in item for item in error.value.diagnostics)

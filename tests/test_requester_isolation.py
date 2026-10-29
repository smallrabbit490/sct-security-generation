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


def test_explicit_single_attempt_does_not_repeat_paid_timeout(monkeypatch):
    calls=[]
    def fail(*args,**kwargs):
        calls.append(1)
        raise TimeoutError('offline')
    request=build(monkeypatch,fail,max_attempts=1)
    with pytest.raises(TimeoutError) as error:request('public task')
    assert len(calls)==len(error.value.diagnostics)==1


def test_stream_reassembles_exact_content_and_usage_without_extra_request(monkeypatch):
    bodies=[]
    class StreamResponse(Response):
        def __iter__(self):
            parts=[{'model':'offline','choices':[{'index':0,'delta':{'content':'{"result":'},'finish_reason':None}]},
                   {'choices':[{'index':0,'delta':{'content':'42}'},'finish_reason':'stop'}]},
                   {'choices':[],'usage':{'prompt_tokens':3,'completion_tokens':4,'total_tokens':7}}]
            return iter([('data: '+json.dumps(p)+'\n\n').encode() for p in parts]+[b'data: [DONE]\n\n'])
    def fake(request,timeout):
        bodies.append(json.loads(request.data))
        return StreamResponse()
    value=build(monkeypatch,fake,stream=True,max_attempts=1)('public')
    assert len(bodies)==1 and bodies[0]['stream_options']=={'include_usage':True}
    assert value['choices'][0]['message']['content']=='{"result":42}'
    assert value['usage']['total_tokens']==7 and value['model']=='offline'


def test_incomplete_stream_is_not_a_success_and_is_not_retried(monkeypatch):
    calls=[]
    class Incomplete(Response):
        def __iter__(self):
            return iter([b'data: {"choices":[{"delta":{"content":"partial"}}]}\n'])
    def fake(*args,**kwargs):
        calls.append(1)
        return Incomplete()
    with pytest.raises(RuntimeError):build(monkeypatch,fake,stream=True,max_attempts=1)('public')
    assert calls==[1]


@pytest.mark.parametrize('stream', [False, True])
def test_provider_controls_send_only_the_exact_public_user_task(monkeypatch, stream):
    """复核已观测的身份误拒绝：本地不拼入系统、身份或历史消息；不访问真实API。"""
    bodies = []

    class ExactResponse(Response):
        def __iter__(self):
            chunk = {'choices': [{'index': 0, 'delta': {'content': 'offline'},
                                  'finish_reason': 'stop'}]}
            return iter([('data: ' + json.dumps(chunk) + '\n\n').encode(),
                         b'data: [DONE]\n\n'])

    def fake(request, timeout):
        bodies.append(json.loads(request.data))
        return ExactResponse()

    prompts = [
        'Reply with exactly the word OK.',
        'Calculate 17 + 25. Return a JSON object with the integer field "result" and no other fields.',
        'Write a Python function add(a, b) that returns a + b. Output only the function code.',
        json.dumps({'operation': 'complete_python_function',
                    'code_prefix': 'def add(a, b):\n    ',
                    'required_behavior': 'sum of arguments',
                    'output_format': 'complete_python_code'}),
    ]
    request = build(monkeypatch, fake, stream=stream, max_attempts=1,
                    max_tokens=128, thinking='disabled')
    for prompt in prompts:
        request(prompt)

    assert len(bodies) == len(prompts)
    for prompt, body in zip(prompts, bodies):
        expected = {'model': 'offline', 'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0, 'max_tokens': 128,
                    'thinking': {'type': 'disabled'}}
        if stream:
            expected.update(stream=True, stream_options={'include_usage': True})
        assert body == expected


@pytest.mark.parametrize('endpoint', [None, 'https://api.chatanywhere.org/v1/chat/completions'])
def test_official_endpoint_choice_does_not_change_message_or_model(monkeypatch, endpoint):
    observed = []
    def fake(request, timeout):
        observed.append((request.full_url, json.loads(request.data)))
        return Response()
    options = {} if endpoint is None else {'endpoint': endpoint}
    build(monkeypatch, fake, max_attempts=1, **options)('public code control')
    assert observed[0][0] == (endpoint or 'https://api.chatanywhere.tech/v1/chat/completions')
    assert observed[0][1]['messages'] == [{'role': 'user', 'content': 'public code control'}]
    assert observed[0][1]['model'] == 'offline'


def test_nonofficial_endpoint_is_rejected_before_credentials(monkeypatch):
    monkeypatch.setattr(runner, 'load_key', lambda: pytest.fail('must not load credential'))
    with pytest.raises(ValueError, match='unsupported_chatanywhere_endpoint'):
        runner._requester('deepseek-v3.2', 1, endpoint='https://untrusted.invalid/v1/chat/completions')


@pytest.mark.parametrize('endpoint', ['https://api.chatanywhere.tech/v1/chat/completions',
                                    'https://api.chatanywhere.org/v1/chat/completions'])
def test_explicit_client_identifier_preserves_payload_and_single_attempt(monkeypatch, endpoint):
    """已观测Cloudflare1010：两个官方地址都显式声明客户端，且不改提示或多发请求。"""
    observed = []
    def fake(request, timeout):
        observed.append(request)
        return Response()
    build(monkeypatch, fake, endpoint=endpoint, max_attempts=1,
          max_tokens=128, thinking='disabled')('public add function')
    assert len(observed) == 1
    assert observed[0].get_header('User-agent') == 'CLE-HTTP-Diagnostic/1.0'
    assert json.loads(observed[0].data) == {
        'model': 'offline', 'messages': [{'role': 'user', 'content': 'public add function'}],
        'temperature': 0, 'max_tokens': 128, 'thinking': {'type': 'disabled'}}

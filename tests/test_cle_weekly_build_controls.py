"""Offline checks for transport classification, task-scoped replay and limits."""
import concurrent.futures
import hashlib
import json
import urllib.request
import sys
import subprocess
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import pytest

from configs.cle_v41_relation_20261026.wiring import SETTINGS
from configs.cle_weekly_build_20261027.native_adapter import native, run_native
from configs.cle_weekly_build_20261027.physical_guard import physical_guard
from configs.cle_weekly_build_20261027.recovery_plan import classify_sources
from configs.cle_weekly_build_20261027.task_scope import task_identity
from configs.cle_weekly_build_20261027.logical_requests import semantic
from configs.cle_weekly_build_20261027.execute import snapshot_sources
from configs.cle_weekly_build_20261027.recovery_probe import probe
from configs.cle_weekly_build_20261027 import resume as build_resume
from configs.cle_weekly_build_20261027.process_guard import exclusive_slots
from methods.sct_trajectory import replay_journal
from methods.sct_trajectory.replay_journal import ReplayStop


CAP = {'conservative_model_and_embedding_tokens': 1000000,
       'total_physical_HTTP_attempts': 10, 'embedding_HTTP_attempts_included_in_total': 2}


def test_embedding_transport_classification_rejects_http_errors(tmp_path):
    journals = tmp_path / 'journals/embedding/requests'
    wire = tmp_path / 'wire'
    journals.mkdir(parents=True)
    wire.mkdir()
    record = {'identity': 'v-1', 'status': 'failed_or_unresolved',
              'settings': {'model': 'text-embedding-3-large', 'operation': 'embedding'},
              'prompt': json.dumps(['a']), 'selector': False}
    (journals / 'v.json').write_text(json.dumps(record), encoding='utf-8')
    (wire / '1.request.json').write_text(json.dumps({'body': {
        'model': 'text-embedding-3-large', 'input': ['a']}}), encoding='utf-8')
    status = wire / '1.status.json'
    status.write_text(json.dumps({'status': 'transport_error', 'http_status': None,
                                  'error_type': 'URLError'}), encoding='utf-8')
    assert list(classify_sources([tmp_path])) == [('embedding', 'v-1')]
    status.write_text(json.dumps({'status': 'transport_error', 'http_status': 403,
                                  'error_type': 'HTTPError'}), encoding='utf-8')
    with pytest.raises(ReplayStop):
        classify_sources([tmp_path])


def test_forbidden_window_rejects_before_transport(tmp_path):
    calls = []
    io = physical_guard(tmp_path / 'run', CAP, lambda *a, **k: calls.append(1),
                        now=lambda: datetime(2026, 10, 27, 2, tzinfo=timezone.utc))
    body = {'model': SETTINGS['model'], 'max_tokens': 4096, 'messages': []}
    req = urllib.request.Request('https://api.chatanywhere.org/v1/chat/completions',
                                 data=json.dumps(body).encode())
    with pytest.raises(Exception), io.physical_records():
        urllib.request.urlopen(req)
    assert not calls
    assert not list((io.root / 'wire').glob('*.request.json'))


def test_identical_prompts_are_replayed_by_task(tmp_path, monkeypatch):
    calls = []

    class Response:
        status = 200

        def __init__(self, number):
            data = [{'model': SETTINGS['model'], 'choices': [{'index': 0,
                     'delta': {'content': str(number)}, 'finish_reason': 'stop'}]},
                    {'choices': [], 'usage': {'total_tokens': 17}}]
            self.lines = iter([('data: ' + json.dumps(x) + '\n').encode() for x in data]
                              + [b'data: [DONE]\n'])

        def __iter__(self):
            return self

        def __next__(self):
            return next(self.lines)

        def close(self):
            pass

    def transport(*args, **kwargs):
        calls.append(1)
        return Response(len(calls))

    def entry(order):
        request = native._requester(SETTINGS['model'], 180, 4096, 4)

        def one(task):
            with task_identity('phase1:' + task):
                return task, request('identical')['choices'][0]['message']['content']

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            return dict(pool.map(one, order))

    monkeypatch.setattr(native, 'load_key', lambda: 'local-test-placeholder')
    monkeypatch.setattr(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None)
    now = lambda: datetime(2026, 10, 27, 11, tzinfo=timezone.utc)
    first = physical_guard(tmp_path / 'first', CAP, transport, now=now)
    expected = run_native(first, [], entry=lambda: entry(['a', 'b']))
    second = physical_guard(tmp_path / 'second', CAP, transport, now=now, resume_sources=[first.root])
    actual = run_native(second, [], entry=lambda: entry(['b', 'a']))
    assert actual == expected
    assert len(calls) == 2
    assert not list((second.root / 'wire').glob('*.request.json'))


def test_multiple_pending_only_probed_target_can_be_reissued(tmp_path, monkeypatch):
    io = physical_guard(tmp_path / 'run', CAP, lambda *a, **k: None,
                        now=lambda: datetime(2026, 10, 27, 11, tzinfo=timezone.utc))
    monkeypatch.setattr(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None)
    public = {'settings': SETTINGS, 'prompt': 'same', 'selector': False}
    identity = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest() + '-000001'
    cells = ['native_' + hashlib.sha256(('phase1:' + task).encode()).hexdigest() for task in ('a', 'b')]
    pending = {(cell, identity): [public] for cell in cells}

    def entry():
        request = native._requester(SETTINGS['model'], 180, 4096, 4)
        with task_identity('phase1:b'):
            return request('same')

    with pytest.raises(ReplayStop, match='other_build_pending_requires_probe'):
        run_native(io, [], entry=entry, pending=pending, authorized_target=(cells[0], identity))
    assert not list((io.root / 'wire').glob('*.request.json'))


def test_probe_distinguishes_identical_pending_prompts_by_task(tmp_path):
    old = tmp_path / 'old'
    old.mkdir()
    snapshot_sources(old)
    wire = old / 'wire'
    wire.mkdir()
    public = {'settings': SETTINGS, 'prompt': 'same', 'selector': False}
    identity = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest() + '-000001'
    cells = []
    for index, task in enumerate(('a', 'b'), 1):
        cell = 'native_' + hashlib.sha256(('phase1:' + task).encode()).hexdigest()
        cells.append(cell)
        folder = old / 'journals' / cell / 'requests'
        folder.mkdir(parents=True)
        (folder / (identity + '.json')).write_text(json.dumps({**public, 'identity': identity,
            'status': 'failed_or_unresolved', 'diagnostics': [{'category': 'network_error'}]}), encoding='utf-8')
        (wire / f'{index}.request.json').write_text(json.dumps({'body': {
            'model': SETTINGS['model'], 'max_tokens': 4096,
            'messages': [{'role': 'user', 'content': 'same'}]}}), encoding='utf-8')
        (wire / f'{index}.status.json').write_text(json.dumps({'status': 'transport_error',
            'http_status': None, 'error_type': 'URLError'}), encoding='utf-8')

    def entry():
        with task_identity('phase1:b'):
            native._requester(SETTINGS['model'], 180, 4096, 4)('same')

    result = probe([old], tmp_path / 'probe', entry=entry)
    assert result['status'] == 'passed'
    assert result['pending_count'] == 2
    assert (result['pending_cell'], result['pending_identity']) == (cells[1], identity)
    assert result['new_HTTP'] == 0


def test_embedding_interruption_probe_then_reissue(tmp_path, monkeypatch):
    old = tmp_path / 'old'
    journal = old / 'journals/embedding/requests'
    wire = old / 'wire'
    journal.mkdir(parents=True)
    wire.mkdir()
    texts = ['abc']
    public = {'settings': {'model': 'text-embedding-3-large', 'operation': 'embedding'},
              'prompt': json.dumps(texts, ensure_ascii=False), 'selector': False}
    identity = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest() + '-000001'
    (journal / (identity + '.json')).write_text(json.dumps({**public, 'identity': identity,
        'status': 'failed_or_unresolved', 'error_type': 'EmbeddingError'}), encoding='utf-8')
    (wire / '1.request.json').write_text(json.dumps({'body': {'model': 'text-embedding-3-large',
        'input': texts}}), encoding='utf-8')
    (wire / '1.status.json').write_text(json.dumps({'status': 'transport_error', 'http_status': None,
        'error_type': 'URLError'}), encoding='utf-8')
    pending = classify_sources([old])
    calls = []

    class Client:
        def __init__(self):
            self.usage = {'prompt_tokens': 0, 'total_tokens': 0}

    def fake_embedding(client, values):
        calls.append(values)
        client.usage['total_tokens'] += 3
        return [[1.0]]

    monkeypatch.setattr(semantic.EmbeddingClient, '_request', fake_embedding)
    monkeypatch.setattr(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None)
    now = lambda: datetime(2026, 10, 27, 11, tzinfo=timezone.utc)
    target = ('embedding', identity)
    entry = lambda: semantic.EmbeddingClient._request(Client(), texts)
    offline = physical_guard(tmp_path / 'probe', CAP, lambda *a, **k: None, now=now, resume_sources=[old])
    with pytest.raises(ReplayStop, match='replay_missing_request:embedding:'):
        run_native(offline, [], entry=entry, pending=pending, probe=True)
    assert not calls
    resumed = physical_guard(tmp_path / 'resumed', CAP, lambda *a, **k: None, now=now, resume_sources=[old])
    assert run_native(resumed, [], entry=entry, pending=pending, authorized_target=target) == [[1.0]]
    assert calls == [texts]
    assert resumed.budget.entries[0]['status'] == 'historical_unknown'


def test_resume_runs_verified_boundary_and_checks_native_outputs(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    build = run / 'BUILD_C41'
    old = build / 'execution/segment_001'
    scope = 'phase1:1'
    cell = 'native_' + hashlib.sha256(scope.encode()).hexdigest()
    journal = old / 'journals' / cell / 'requests'
    wire = old / 'wire'
    journal.mkdir(parents=True)
    wire.mkdir()

    def record(prompt, status):
        public = {'settings': SETTINGS, 'prompt': prompt, 'selector': False}
        identity = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest() + '-000001'
        row = {**public, 'identity': identity, 'status': status}
        if status == 'completed':
            row['response'] = {'model': SETTINGS['model'], 'choices': [{'message': {'content': 'old'}}],
                               'usage': {'total_tokens': 17}}
        else:
            row['diagnostics'] = [{'category': 'network_error'}]
        (journal / (identity + '.json')).write_text(json.dumps(row), encoding='utf-8')
        return identity

    record('first', 'completed')
    identity = record('second', 'failed_or_unresolved')
    (wire / '1.request.json').write_text(json.dumps({'body': {'model': SETTINGS['model'],
        'max_tokens': 4096, 'messages': [{'content': 'second'}]}}), encoding='utf-8')
    (wire / '1.status.json').write_text(json.dumps({'status': 'transport_error',
        'http_status': None, 'error_type': 'URLError'}), encoding='utf-8')
    (run / 'manifest.json').write_text(json.dumps({'pools': {'D_init': ['1'], 'D_gate': ['2']}}), encoding='utf-8')
    (build / 'budget.json').write_text(json.dumps({'budget_proposed': CAP}), encoding='utf-8')
    (build / 'native_arguments.json').write_text(json.dumps({'arguments': ['--out', 'old',
        '--embedding-cache', 'old-cache']}), encoding='utf-8')
    receipt = tmp_path / 'probe.json'
    receipt.write_text(json.dumps({'status': 'passed', 'new_HTTP': 0, 'saved_segments': [str(old)],
        'pending_cell': cell, 'pending_identity': identity,
        'stopped_at': 'replay_missing_request:' + cell + ':' + identity}), encoding='utf-8')

    class Response:
        status = 200

        def __init__(self):
            payload = [{'model': SETTINGS['model'], 'choices': [{'index': 0,
                       'delta': {'content': 'new'}, 'finish_reason': 'stop'}]},
                       {'choices': [], 'usage': {'total_tokens': 19}}]
            self.lines = iter([('data: ' + json.dumps(x) + '\n').encode() for x in payload]
                              + [b'data: [DONE]\n'])

        def __iter__(self): return self
        def __next__(self): return next(self.lines)
        def close(self): pass

    class Opener:
        def open(self, *args, **kwargs):
            return Response()

    def entry():
        with task_identity(scope):
            request = native._requester(SETTINGS['model'], 180, 4096, 4)
            assert request('first')['choices'][0]['message']['content'] == 'old'
            assert request('second')['choices'][0]['message']['content'] == 'new'
        out = Path(sys.argv[sys.argv.index('--out') + 1])
        (out / 'frozen').mkdir(parents=True)
        for name, values in [('phase1_results.jsonl', [{'task_id': 1}]),
                             ('final_eval.jsonl', [{'task_id': 2}]),
                             ('completed_rounds.jsonl', [{'round': i} for i in (1, 2, 3)]),
                             ('frozen/m_star.jsonl', [{'invariant_id': 'card'}])]:
            (out / name).write_text(''.join(json.dumps(v) + '\n' for v in values), encoding='utf-8')
        for name in ('global_gate_report.json', 'summary.json', 'cost.json'):
            (out / name).write_text('{}', encoding='utf-8')

    def adapted(io, arguments, *, pending, authorized_target):
        return run_native(io, arguments, entry=entry, pending=pending, authorized_target=authorized_target)

    monkeypatch.setattr(build_resume, 'RUN', run)
    monkeypatch.setattr(build_resume, 'BUILD', build)
    monkeypatch.setattr(build_resume, 'verify_source_snapshot', lambda p: None)
    monkeypatch.setattr(build_resume, 'verify_input_snapshot', lambda p: None)
    monkeypatch.setattr(build_resume, 'snapshot_sources', lambda p: None)
    monkeypatch.setattr(build_resume, 'record_validations', lambda *a: None)
    monkeypatch.setattr(build_resume, 'current_active_experiments', lambda: [])
    monkeypatch.setattr(build_resume, 'ensure_model_call_allowed', lambda *a: None)
    monkeypatch.setattr(build_resume, 'verified_proxy_transport', nullcontext)
    monkeypatch.setattr(build_resume.urllib.request, 'build_opener', lambda *a: Opener())
    monkeypatch.setattr(build_resume, 'run_native', adapted)
    monkeypatch.setattr(native, 'load_key', lambda: 'local-test-placeholder')
    monkeypatch.setattr(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None)
    build_resume.resume([old], receipt)
    segment = build / 'execution/segment_002'
    assert json.loads((segment / 'state.json').read_text(encoding='utf-8'))['status'] == 'completed_pending_verification'
    assert json.loads((segment / 'native_verification.json').read_text(encoding='utf-8'))['frozen_cards'] == 1
    assert len(list((segment / 'wire').glob('*.request.json'))) == 1
    assert json.loads((journal / (identity + '.json')).read_text(encoding='utf-8'))['status'] == 'failed_or_unresolved'


def test_exclusive_package_locks_prevent_competing_builds(tmp_path):
    child = ('from configs.cle_weekly_build_20261027.process_guard import exclusive_slots\n'
             'import sys\n'
             'try:\n'
             ' with exclusive_slots(sys.argv[1]): print("acquired")\n'
             'except RuntimeError: print("blocked")\n')
    with exclusive_slots(tmp_path):
        result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', child, str(tmp_path)],
                                capture_output=True, text=True, check=True)
        assert result.stdout.strip() == 'blocked'
    result = subprocess.run([sys.executable, '-B', '-X', 'utf8', '-c', child, str(tmp_path)],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == 'acquired'

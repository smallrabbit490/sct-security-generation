import json
import os
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from methods.mase_evolution.artifacts import write_json
from methods.mase_evolution.control import ControlStore
from methods.mase_evolution.dashboard.server import make_handler


def api(tmp_path, method, path, body=None):
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(tmp_path))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(f'http://127.0.0.1:{server.server_port}{path}',
                          data=json.dumps(body).encode() if body is not None else None,
                          method=method, headers={'Content-Type': 'application/json'})
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def make_run(tmp_path):
    run = tmp_path / 'run_a'
    version = run / 'versions' / 'v000'
    version.mkdir(parents=True)
    write_json(run / 'run_metadata.json', {'run_id': 'run_a', 'status': 'running'})
    write_json(version / 'version.json', {'version_id': 'v000', 'status': 'running'})
    (version / 'events.jsonl').write_text('', encoding='utf-8')
    return version


def test_live_endpoint_returns_unknown_legacy_as_read_only(tmp_path):
    make_run(tmp_path)
    status, payload = api(tmp_path, 'GET', '/api/live?run=run_a&version=v000')
    assert status == 200
    assert payload['control']['available'] is False
    assert payload['heartbeat'] is None
    assert payload['events'] == []
    assert payload['event_count'] == 0


def test_run_list_marks_stale_running_metadata_as_stopped_and_sorts_active_first(tmp_path):
    active = make_run(tmp_path)
    write_json(active / 'heartbeat.json', {'status': 'running', 'time': '2026-10-14T08:00:00+00:00'})
    write_json(tmp_path / 'run_a' / 'run_metadata.json', {
        'run_id': 'run_a', 'label': '当前运行', 'status': 'running'
    })

    old = tmp_path / 'run_old'
    old.mkdir()
    metadata = old / 'run_metadata.json'
    write_json(metadata, {'run_id': 'run_old', 'label': '旧记录', 'status': 'running'})
    old_time = time.time() - 3600
    os.utime(metadata, (old_time, old_time))

    status, payload = api(tmp_path, 'GET', '/api/runs')

    assert status == 200
    assert [run['run_id'] for run in payload] == ['run_a', 'run_old']
    assert payload[0]['is_active'] is True
    assert payload[0]['display_status'] == '正在运行'
    assert payload[1]['is_active'] is False
    assert payload[1]['display_status'] == '状态过期，进程未确认'


def test_events_endpoint_returns_only_new_events_after_cursor(tmp_path):
    version = make_run(tmp_path)
    with (version / 'events.jsonl').open('w', encoding='utf-8') as stream:
        stream.write(json.dumps({'event_id': '1', 'node_id': 'n1', 'status': 'completed'}) + '\n')
        stream.write(json.dumps({'event_id': '2', 'node_id': 'n2', 'status': 'running', 'output': {'code': 'secret'}}) + '\n')
    status, payload = api(tmp_path, 'GET', '/api/events?run=run_a&version=v000&after=1')
    assert status == 200
    assert [e['event_id'] for e in payload['events']] == ['2']
    assert 'code' not in payload['events'][0].get('output', {})


def test_events_endpoint_exposes_safe_error_code_but_not_exception_text(tmp_path):
    version = make_run(tmp_path)
    with (version / 'events.jsonl').open('w', encoding='utf-8') as stream:
        stream.write(json.dumps({'event_id':'1','node_id':'generate','status':'failed',
                                 'error_code':'model_output_truncated',
                                 'exception_text':'secret prompt and model response'})+'\n')
    status, payload = api(tmp_path, 'GET', '/api/events?run=run_a&version=v000')
    assert status == 200
    event=payload['events'][0]
    assert event['error_code']=='model_output_truncated'
    assert 'exception_text' not in event


def test_version_endpoint_explains_architecture_errors_and_design_attempts(tmp_path):
    version = make_run(tmp_path)
    write_json(version / 'proposal.json', {
        'valid': False,
        'errors': ['input_without_edge:repair:memory'],
        'architecture': {'nodes': [
            {'id': 'repair', 'label': '有问题才修复'},
            {'id': 'memory', 'label': '来源记忆'},
        ], 'edges': []},
        'design_trace': [
            {'output_limit': 4096, 'finish_reason': 'length', 'error_type': 'ValueError'},
            {'output_limit': 8192, 'finish_reason': 'length', 'error_type': 'ValueError'},
            {'output_limit': 16384, 'finish_reason': 'stop'},
        ],
    })

    status, payload = api(tmp_path, 'GET', '/api/version?run=run_a&version=v000')

    assert status == 200
    assert payload['proposal_diagnostics'] == [
        '节点“有问题才修复”需要“来源记忆”，但架构中缺少 memory → repair 连线。'
    ]
    assert [(item['output_limit'], item['finish_reason'], item['error_type'])
            for item in payload['design_attempts']] == [
        (4096, 'length', 'ValueError'),
        (8192, 'length', 'ValueError'),
        (16384, 'stop', None),
    ]


def test_live_endpoint_includes_active_task_and_node_from_heartbeat(tmp_path):
    version = make_run(tmp_path)
    write_json(version / 'heartbeat.json', {
        'planned': 60, 'saved': 4, 'measured': 4, 'pending': 56,
        'active_task_id': 'task-5', 'active_node_id': 'repair',
        'queued': 3, 'configured_request_concurrency': 48,
        'observed_request_peak': 12,
    })
    status, payload = api(tmp_path, 'GET', '/api/live?run=run_a&version=v000')
    assert status == 200
    assert payload['heartbeat']['active_task_id'] == 'task-5'
    assert payload['heartbeat']['active_node_id'] == 'repair'
    assert payload['heartbeat']['observed_request_peak'] == 12
    assert payload['events'] == []


def test_control_endpoints_enforce_pause_resume_transitions(tmp_path):
    version = make_run(tmp_path)
    store = ControlStore(version / 'control.json')
    store.update_heartbeat({'saved': 4})
    status, payload = api(tmp_path, 'POST', '/api/control?run=run_a&version=v000', {'action': 'pause'})
    assert status == 200 and payload['status'] == 'pause_requested'
    status, payload = api(tmp_path, 'POST', '/api/control?run=run_a&version=v000', {'action': 'resume'})
    assert status == 409 and payload['error'] == 'invalid_control_transition'
    store.mark_paused()
    status, payload = api(tmp_path, 'POST', '/api/control?run=run_a&version=v000', {'action': 'resume'})
    assert status == 200 and payload['status'] == 'running'


def test_invalid_ids_and_path_traversal_are_rejected(tmp_path):
    status, _ = api(tmp_path, 'GET', '/api/live?run=..&version=v000')
    assert status == 400
    status, _ = api(tmp_path, 'POST', '/api/control?run=run_a&version=..', {'action': 'pause'})
    assert status == 400

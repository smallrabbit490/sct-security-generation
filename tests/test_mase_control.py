import json
import os
from pathlib import Path

import pytest

from methods.mase_evolution.control import ControlStore, schedule_tasks


def test_pause_request_is_atomic_idempotent_and_resumes_only_paused(tmp_path):
    store = ControlStore(tmp_path / 'control.json')
    assert store.read()['status'] == 'running'
    assert store.request_pause()['status'] == 'pause_requested'
    assert store.request_pause()['status'] == 'pause_requested'
    with pytest.raises(ValueError, match='invalid_control_transition'):
        store.request_resume()
    store.mark_paused()
    assert store.request_resume()['status'] == 'running'


@pytest.mark.parametrize('terminal', ['completed', 'failed'])
def test_terminal_runs_reject_pause_and_resume(tmp_path, terminal):
    store = ControlStore(tmp_path / 'control.json')
    store.set_terminal(terminal)
    with pytest.raises(ValueError, match='invalid_control_transition'):
        store.request_pause()
    with pytest.raises(ValueError, match='invalid_control_transition'):
        store.request_resume()


def test_scheduler_stops_submitting_after_pause_and_resume_skips_saved(tmp_path):
    store = ControlStore(tmp_path / 'control.json')
    submitted = []
    saved = []

    def work(task):
        submitted.append(task)
        if task == 0:
            store.request_pause()
        return task

    state = schedule_tasks([0, 1, 2, 3], set(), work, saved.append, store, workers=1)
    assert state == 'paused'
    assert submitted == [0]
    assert saved == [0]

    store.request_resume()
    state = schedule_tasks([0, 1, 2, 3], {0}, work, saved.append, store, workers=1)
    assert state == 'completed'
    assert submitted == [0, 1, 2, 3]
    assert saved == [0, 1, 2, 3]
    assert len(saved) == len(set(saved))


def test_control_file_is_valid_json_after_repeated_atomic_updates(tmp_path):
    path = tmp_path / 'control.json'
    store = ControlStore(path)
    for _ in range(20):
        store.update_heartbeat({'saved': 1})
        json.loads(path.read_text(encoding='utf-8'))


def test_control_file_retries_temporary_windows_replace_lock(tmp_path, monkeypatch):
    path = tmp_path / 'control.json'
    store = ControlStore(path)
    real_replace = os.replace
    attempts = 0

    def replace_with_temporary_lock(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError('temporary reader lock')
        return real_replace(source, destination)

    monkeypatch.setattr('methods.mase_evolution.control.os.replace', replace_with_temporary_lock)
    store.update_heartbeat({'saved': 7})

    assert attempts == 3
    assert json.loads(path.read_text(encoding='utf-8'))['saved'] == 7

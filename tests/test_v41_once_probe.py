"""一次性监控探针的付费边界：所有请求和验证均为离线替身。"""
import json

import pytest

from configs.cle_memory_mechanisms_20261023 import probe_v41_flash_1017_once as probe
from methods.sct_trajectory.provider_policy import ModelTimeWindowError


def test_forbidden_window_leaves_no_output_and_constructs_no_client(tmp_path, monkeypatch):
    out = tmp_path / 'not-started'
    monkeypatch.setattr(probe, 'DESTINATION', out)
    def blocked(model): raise ModelTimeWindowError('offline forbidden time')
    monkeypatch.setattr(probe, 'ensure_model_call_allowed', blocked)
    monkeypatch.setattr(probe, '_requester', lambda *a, **k: pytest.fail('no client'))
    assert probe.main()['status'] == 'waiting_allowed_window'
    assert not out.exists()


@pytest.mark.parametrize('failed', [False, True])
def test_one_attempt_and_existing_terminal_result_never_resubmits(tmp_path, monkeypatch, failed):
    monkeypatch.setattr(probe, 'DESTINATION', tmp_path / 'once')
    monkeypatch.setattr(probe, 'ensure_model_call_allowed', lambda model: None)
    calls = []
    def factory(model, timeout, **kwargs):
        assert model == probe.MODEL and kwargs['max_attempts'] == 1
        def request(prompt):
            calls.append(prompt)
            if failed: raise TimeoutError('offline')
            return {'model': probe.MODEL, 'choices': [{'message': {'content': 'def add(a, b):\n    return a + b'},
                       'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 30, 'completion_tokens': 10, 'total_tokens': 40}}
        return request
    monkeypatch.setattr(probe, '_requester', factory)
    monkeypatch.setattr(probe, 'execute_checks', lambda *a, **k: {'measured_count': 2, 'passed': 2})
    first = probe.main()
    assert first['status'] == ('stopped_technical_error' if failed else 'passed')
    assert calls == [probe.PROMPT]
    monkeypatch.setattr(probe, '_requester', lambda *a, **k: pytest.fail('no repeated client'))
    assert probe.main() == first
    assert first['message_roles'] == ['user'] and not first['system_message_added']
    assert json.loads((probe.DESTINATION / 'cost.json').read_text())['reserved_http_attempts'] == 1


def test_submitted_or_incomplete_output_does_not_send_another_request(tmp_path, monkeypatch):
    out = tmp_path / 'partial';out.mkdir()
    monkeypatch.setattr(probe, 'DESTINATION', out)
    monkeypatch.setattr(probe, '_requester', lambda *a, **k: pytest.fail('no client'))
    with pytest.raises(RuntimeError, match='do_not_resubmit'):
        probe.main()
    (out / 'summary.json').write_text('{"status":"submitted"}')
    assert probe.main()['status'] == 'submitted'

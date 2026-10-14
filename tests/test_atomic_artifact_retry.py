"""Windows短暂文件占用不能丢失结果；永久失败仍必须明确报告。"""
import json
import pytest
from methods.sct_trajectory import run_artifacts as m


def test_atomic_json_retries_temporary_windows_sharing_denial(tmp_path, monkeypatch):
    original = m.os.replace
    calls = []
    def denied_once(source, target):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError('sharing violation')
        return original(source, target)
    monkeypatch.setattr(m.os, 'replace', denied_once)
    monkeypatch.setattr(m.time, 'sleep', lambda s: None)
    target = tmp_path / 'status.json'
    m.write_json_atomic(target, {'done':1})
    assert json.loads(target.read_text()) == {'done':1}
    assert len(calls) == 3


def test_persistent_write_denial_is_not_reported_success(tmp_path, monkeypatch):
    def denied(*args):
        raise PermissionError('permanent failure')
    monkeypatch.setattr(m.os, 'replace', denied)
    monkeypatch.setattr(m.time, 'sleep', lambda s: None)
    with pytest.raises(PermissionError):
        m.write_json_atomic(tmp_path / 'summary.json', {'done':1})

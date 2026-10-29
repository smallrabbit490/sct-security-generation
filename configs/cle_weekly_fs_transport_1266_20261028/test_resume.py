"""仅核对已观测的HTTP200超时分类；测试不派发网络请求。"""
import json

import pytest

from configs.cle_weekly_fs_transport_1266_20261028 import resume


@pytest.mark.parametrize('tail,expected', [
    ('', True),
    ('data: [DONE]\n', False),
    ('data: {"choices":[{"index":0,"finish_reason":"stop"}]}\n', False),
    ('data: {"error":{"code":"insufficient_quota"}}\n', False),
])
def test_truncated_stream_requires_no_completion_or_provider_error(tmp_path, tail, expected):
    raw = tmp_path / 'response.raw'
    chunk = {'choices': [{'index': 0, 'delta': {'content': '{"plan":"unfinished'}}]}
    raw.write_text('data: ' + json.dumps(chunk) + '\n' + tail, encoding='utf-8')
    assert resume.incomplete_json_stream(raw) is expected


def test_complete_json_is_not_discarded_even_without_finish(tmp_path):
    raw = tmp_path / 'response.raw'
    chunk = {'choices': [{'index': 0, 'delta': {'content': '{"plan":"complete"}'}}]}
    raw.write_text('data: ' + json.dumps(chunk) + '\n', encoding='utf-8')
    assert resume.incomplete_json_stream(raw) is False


def test_observed_timeout_rejects_auth_and_different_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, 'FFS', tmp_path)
    source = tmp_path / 'segment_022'
    record = {'identity': resume.IDENTITY, 'settings': {'model': 'same-model'}, 'prompt': 'same-prompt'}
    for i in range(3):
        resume.write_json(source / f'wire/{i}.request.json', {'body': {
            'model': 'same-model', 'messages': [{'role': 'user', 'content': 'same-prompt'}]}})
        resume.write_json(source / f'wire/{i}.status.json', {'status': 'transport_error',
            'http_status': None, 'error_type': 'URLError', 'reason_type': 'SSLEOFError'})
    resume.write_json(source / 'wire/2.status.json', {'status': 'response_read_error',
        'http_status': 200, 'error_type': 'TimeoutError'})
    (source / 'wire/2.response.raw').write_text(
        'data: {"choices":[{"delta":{"content":"{incomplete"}}]}\n', encoding='utf-8')
    assert resume.observed_timeout(source, record)
    assert not resume.observed_timeout(source, {**record, 'identity': 'different'})
    resume.write_json(source / 'wire/2.status.json', {'status': 'response_read_error',
        'http_status': 401, 'error_type': 'TimeoutError'})
    assert not resume.observed_timeout(source, record)

"""C02入口的真实启用边界与缺失向量费用；不访问模型或读取凭据。"""
import copy
import json

import pytest

from methods.cle_ablation import run_memory_granularity as entry
from methods.sct_trajectory.semantic_retrieval import EmbeddingClient


def protocol():
    return copy.deepcopy(entry.read(entry.CONFIG / 'granularity_protocol.json'))


def enabled_protocol():
    p = protocol()
    p.update(paid_execution_enabled=True, consumer_frozen=True, consumer_version='offline-test',
             authorized_C02_HTTP_budget=100)
    p['technical_execution'].update(enabled=True, max_http_attempts=100,
        max_conservative_tokens=1000000, max_embedding_attempts=20)
    return p


def control(passed=True):
    return {'model': entry.CURRENT_MODEL, 'status': 'passed' if passed else 'stopped_control_failure',
            'controls': [{'passed': True}, {'passed': passed}]}


def test_default_entry_does_not_construct_clients_and_reports_actual_gate(capsys, monkeypatch):
    monkeypatch.setattr(entry, 'clients', lambda: pytest.fail('must not construct clients'))
    result = entry.main([])
    assert result['new_API_calls'] == 0 and result['planned_P7'] == 20 and not result['ready']
    assert set(result['reasons']) == {'paid_execution_disabled', 'consumer_not_frozen',
        'C02_independent_budget_missing', 'provider_code_controls_not_passed'}
    assert json.loads(capsys.readouterr().out)['ready'] is False


def test_explicit_run_cannot_bypass_failed_gate_or_create_output(tmp_path, monkeypatch):
    out = tmp_path / 'must-not-exist'
    monkeypatch.setattr(entry, 'clients', lambda: pytest.fail('must not construct clients'))
    with pytest.raises(ValueError, match='C02_paid_execution_not_ready'):
        entry.main(['--run', '--out', str(out)])
    assert not out.exists()


def test_only_exact_CLE_model_parameters_and_independent_scope_are_accepted():
    p = enabled_protocol()
    assert entry.readiness(p, control()) == []
    p['unchanged']['max_selected_cards'] = 4
    assert 'original_CLE_execution_parameters_changed' in entry.readiness(p, control())
    p = enabled_protocol()
    p['technical_execution']['scope'] = 'B02_two_task'
    assert 'scope_must_be_fixed_technical_20' in entry.readiness(p, control())
    p = enabled_protocol()
    p['authorized_C02_HTTP_budget'] = 700
    assert 'C02_budget_scope_mismatch' in entry.readiness(p, control())


def test_arithmetic_only_or_code_failure_cannot_open_real_execution():
    p = enabled_protocol()
    one = control()
    one['controls'] = one['controls'][:1]
    assert 'provider_code_controls_not_passed' in entry.readiness(p, one)
    assert 'provider_code_controls_not_passed' in entry.readiness(p, control(False))


def test_previous_model_control_cannot_qualify_new_model():
    old = control()
    old['model'] = 'deepseek-v3.2'
    assert 'provider_code_controls_not_passed' in entry.readiness(enabled_protocol(), old)


@pytest.mark.parametrize('usage', [{}, {'total_tokens': 3},
                                  {'prompt_tokens': True, 'total_tokens': 3},
                                  {'prompt_tokens': 3, 'total_tokens': -1}])
def test_partial_or_invalid_embedding_usage_remains_unknown(tmp_path, monkeypatch, usage):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            return json.dumps({'data': [{'index': 0, 'embedding': [1.0, 0.0]}], 'usage': usage}).encode()
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: Response())
    client = EmbeddingClient(cache_path=tmp_path / 'cache.sqlite3', key_loader=lambda: 'offline-placeholder')
    assert client._request(['public']) == [[1.0, 0.0]]
    assert client.usage['usage_missing_calls'] == 1

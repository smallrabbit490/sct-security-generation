"""Offline checks for same-endpoint proxy recovery and duplicate detection."""
import json
from pathlib import Path
from types import SimpleNamespace

from configs.cle_v41_relation_20261026.execution import StudyExecution
from configs.cle_weekly_proxy_recovery_20261027 import runner
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport


def test_running_detection_distinguishes_q_and_ffs(monkeypatch):
    processes = [{'ProcessId': 1, 'CommandLine': 'python -m configs.cle_weekly_proxy_recovery_20261027.runner run --kind q'},
                 {'ProcessId': 2, 'CommandLine': 'python -m configs.cle_weekly_proxy_recovery_20261027.runner run --kind ffs'}]
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=json.dumps(processes)))
    assert runner.active('q') and runner.active('ffs')
    processes.pop()
    assert runner.active('q') and not runner.active('ffs')


def test_proxy_changes_only_live_physical_transport(tmp_path):
    cap = {'conservative_model_and_embedding_tokens': 100000,
           'total_physical_HTTP_attempts': 3, 'embedding_HTTP_attempts_included_in_total': 1}
    original = lambda *a, **k: None
    with verified_proxy_transport():
        offline = StudyExecution(tmp_path / 'offline', {'paid_execution_enabled': False, 'planned_P7': 0,
            'budget_proposed': cap}, [], client_factory=lambda _: None, physical_open=original,
            live=False, fixed_eight=False)
        live = StudyExecution(tmp_path / 'live', {'paid_execution_enabled': True, 'planned_P7': 0,
            'budget_proposed': cap}, [], client_factory=lambda _: None, physical_open=original,
            live=True, fixed_eight=False)
    assert offline.physical_open is original
    assert live.physical_open is not original
    route = json.loads((Path(live.root) / 'transport_route.json').read_text(encoding='utf-8'))
    assert route['same_endpoint_and_model'] and route['TLS_certificate_validation'] == 'default'

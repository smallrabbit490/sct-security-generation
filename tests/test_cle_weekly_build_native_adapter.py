"""Exercise the native three-round CLI through the new offline journal adapter."""
import runpy
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from configs.cle_v41_relation_20261026.wiring import SETTINGS
from configs.cle_weekly_build_20261027.native_adapter import run_native
from configs.cle_weekly_build_20261027.physical_guard import physical_guard
from methods.sct_trajectory import replay_journal, run_closed_loop
from methods.sct_trajectory.replay_journal import ReplayStop
from configs.cle_weekly_build_20261027.recovery_plan import classify_sources


def test_native_three_round_cli_through_build_adapter(tmp_path, monkeypatch):
    original_main = run_closed_loop.main
    cap = {'conservative_model_and_embedding_tokens': 1000000,
           'total_physical_HTTP_attempts': 100,
           'embedding_HTTP_attempts_included_in_total': 10}

    def deny_network(*args, **kwargs):
        raise AssertionError('network forbidden in offline integration')

    io = physical_guard(tmp_path / 'journal', cap, deny_network,
                        now=lambda: datetime(2026, 10, 27, 11, tzinfo=timezone.utc))
    monkeypatch.setattr(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None)

    def adapted_main():
        fake_factory = run_closed_loop._requester

        def reported_model_factory(*args, **kwargs):
            fake_client = fake_factory(*args, **kwargs)

            def call(prompt):
                result = fake_client(prompt)
                result['model'] = SETTINGS['model']
                return result
            return call

        run_closed_loop._requester = reported_model_factory
        try:
            return run_native(io, [*sys.argv[1:], '--model', SETTINGS['model'],
                                   '--max-tokens', '4096'], entry=original_main)
        finally:
            run_closed_loop._requester = fake_factory

    monkeypatch.setattr(run_closed_loop, 'main', adapted_main)
    existing = runpy.run_path(str(Path(__file__).with_name('test_branch_cli_flow.py')))
    existing['test_actual_main_runs_three_rounds_then_one_global_gate_and_freezes_consistently'](
        tmp_path, monkeypatch)
    assert list((io.root / 'journals').glob('native_*/requests/*.json'))
    assert not list((io.root / 'wire').glob('*.request.json'))


def test_native_three_round_cli_replays_completed_journals_without_new_calls(tmp_path):
    original_main = run_closed_loop.main
    cap = {'conservative_model_and_embedding_tokens': 1000000,
           'total_physical_HTTP_attempts': 100,
           'embedding_HTTP_attempts_included_in_total': 10}
    existing = runpy.run_path(str(Path(__file__).with_name('test_branch_cli_flow.py')))
    scenario = existing['test_actual_main_runs_three_rounds_then_one_global_gate_and_freezes_consistently']
    calls = []

    def run_scenario(name, sources):
        root = tmp_path / name
        root.mkdir()

        def deny_network(*args, **kwargs):
            raise AssertionError('network forbidden in offline replay')

        io = physical_guard(root / 'journal', cap, deny_network,
                            now=lambda: datetime(2026, 10, 27, 11, tzinfo=timezone.utc),
                            resume_sources=sources)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None)

            def adapted_main():
                fake_factory = run_closed_loop._requester

                def counted_factory(*args, **kwargs):
                    fake_client = fake_factory(*args, **kwargs)

                    def call(prompt):
                        calls.append(name)
                        if sources:
                            raise AssertionError('completed replay attempted a new model call')
                        result = fake_client(prompt)
                        result['model'] = SETTINGS['model']
                        return result
                    return call

                run_closed_loop._requester = counted_factory
                try:
                    return run_native(io, [*sys.argv[1:], '--model', SETTINGS['model'],
                                           '--max-tokens', '4096'], entry=original_main)
                finally:
                    run_closed_loop._requester = fake_factory

            mp.setattr(run_closed_loop, 'main', adapted_main)
            scenario(root, mp)
        return io.root

    first = run_scenario('first', [])
    assert calls
    before = len(calls)
    replay = run_scenario('replay', [first])
    assert len(calls) == before
    assert not list((replay / 'wire').glob('*.request.json'))


def test_native_three_round_cli_recovers_a_simulated_transport_failure(tmp_path):
    original_main = run_closed_loop.main
    cap = {'conservative_model_and_embedding_tokens': 1000000,
           'total_physical_HTTP_attempts': 100,
           'embedding_HTTP_attempts_included_in_total': 10}
    scenario = runpy.run_path(str(Path(__file__).with_name('test_branch_cli_flow.py')))[
        'test_actual_main_runs_three_rounds_then_one_global_gate_and_freezes_consistently']
    model_calls = []

    class SimulatedTransportError(RuntimeError):
        safe_diagnostics = [{'category': 'network_error'}]

    def run_scenario(name, sources=(), pending=None, probe=False):
        root = tmp_path / name
        root.mkdir()

        def deny_network(*args, **kwargs):
            raise AssertionError('network forbidden in offline recovery test')

        io = physical_guard(root / 'journal', cap, deny_network,
                            now=lambda: datetime(2026, 10, 27, 11, tzinfo=timezone.utc),
                            resume_sources=sources)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None)

            def adapted_main():
                fake_factory = run_closed_loop._requester

                def controlled_factory(*args, **kwargs):
                    fake_client = fake_factory(*args, **kwargs)

                    def call(prompt):
                        model_calls.append(name)
                        if name == 'first' and model_calls.count('first') == 2:
                            wire = io.root / 'wire'
                            wire.mkdir(exist_ok=True)
                            (wire / '0000001.request.json').write_text(json.dumps({'body': {
                                'model': SETTINGS['model'], 'max_tokens': 4096,
                                'messages': [{'role': 'user', 'content': str(prompt)}]}}), encoding='utf-8')
                            (wire / '0000001.status.json').write_text(json.dumps({
                                'status': 'transport_error', 'http_status': None,
                                'error_type': 'URLError'}), encoding='utf-8')
                            raise SimulatedTransportError()
                        result = fake_client(prompt)
                        result['model'] = SETTINGS['model']
                        return result
                    return call

                run_closed_loop._requester = controlled_factory
                try:
                    return run_native(io, [*sys.argv[1:], '--model', SETTINGS['model'],
                                           '--max-tokens', '4096'], entry=original_main,
                                      pending=pending, probe=probe)
                finally:
                    run_closed_loop._requester = fake_factory

            mp.setattr(run_closed_loop, 'main', adapted_main)
            if name in ('first', 'probe'):
                with pytest.raises(ReplayStop) as stopped:
                    scenario(root, mp)
                return io.root, str(stopped.value)
            scenario(root, mp)
        return io.root, None

    first, reason = run_scenario('first')
    assert reason.startswith('model_transport_stopped_no_automatic_resubmit:')
    pending = classify_sources([first])
    assert len(pending) == 1
    _, reason = run_scenario('probe', [first], pending=pending, probe=True)
    cell, identity = next(iter(pending))
    assert reason == 'replay_missing_request:' + cell + ':' + identity
    assert 'probe' not in model_calls
    run_scenario('resume', [first], pending=pending)
    assert 'resume' in model_calls

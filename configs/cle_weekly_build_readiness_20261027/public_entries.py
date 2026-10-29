"""以合成输入实际调用 BUILD 的公开快照、probe、resume 和 replay 入口。"""
import argparse
from contextlib import ExitStack, nullcontext
import json
from pathlib import Path
import shutil
from unittest.mock import patch

from configs.cle_weekly_build_20261027 import execute, resume, replay, recovery_inputs, recovery_probe, recovery_plan
from configs.cle_weekly_build_20261027.physical_guard import physical_guard
from configs.cle_weekly_build_20261027.native_adapter import run_native
from methods.sct_trajectory import closed_loop, internal_checks, run_plus_frozen_comparison
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .offline import CAP, POOLS, LocalProvider, tasks, arguments, isolated, deny
from .runtime import runtime, snapshot_sources


def scenario(root, fail_marker):
    root = Path(root)
    fixture, run = root / 'fixture', root / 'run'
    build = run / 'BUILD_C41'
    fixture.mkdir(parents=True, exist_ok=False)
    write_json(fixture / 'tasks.json', tasks())
    evidence = fixture / 'methods/sct_agent/validation_evidence.py'
    evidence.parent.mkdir(parents=True)
    evidence.write_text('# Isolated index; actual module from repository.\n', encoding='utf-8')
    write_json(run / 'manifest.json', {'pools': POOLS})
    for name, value in [('plt_tasks.json', tasks()), ('pools.json', POOLS), ('manifest.json', {'synthetic': True})]:
        write_json(build / 'inputs' / name, value)
    write_json(build / 'budget.json', {'budget_proposed': CAP})
    write_json(build / 'native_arguments.json', {'arguments': arguments(fixture, build / 'native/segment_001', build / 'embeddings.sqlite3')})
    helper = run / 'FQ_LEARN/transport_resume_stream_20261027.py'
    helper.parent.mkdir(parents=True)
    shutil.copy2(execute.RUN / 'FQ_LEARN/transport_resume_stream_20261027.py', helper)
    with ExitStack() as stack:
        for module in (execute, resume, replay, recovery_inputs, recovery_probe, recovery_plan):
            stack.enter_context(patch.object(module, 'RUN', run))
            if hasattr(module, 'BUILD'):
                stack.enter_context(patch.object(module, 'BUILD', build))
        # 原验证记录器会安装函数包装，退出此隔离试验时还原，验证器本身不替换。
        for module, name in ((closed_loop, 'validate_and_state'), (internal_checks, 'execute_checks'),
                             (run_plus_frozen_comparison, 'evaluate')):
            stack.enter_context(patch.object(module, name, getattr(module, name)))
        stack.enter_context(isolated(fixture))
        stack.enter_context(runtime())
        stack.enter_context(patch.object(resume, 'current_active_experiments', lambda: []))
        stack.enter_context(patch.object(resume, 'ensure_model_call_allowed', lambda *a: None))
        stack.enter_context(patch.object(resume, 'verified_proxy_transport', nullcontext))
        segment = build / 'execution/segment_001'
        provider = LocalProvider(fail_marker)
        io = physical_guard(segment, CAP, provider.open)
        snapshot_sources(segment)
        execute.record_validations(segment, 'PLT')
        try:
            run_native(io, execute.read(build / 'native_arguments.json')['arguments'])
            raise AssertionError('public_entry_failure_not_injected')
        except ReplayStop:
            pass
        sources, probes = [segment], []
        for attempt in range(1, 5):
            result = recovery_probe.probe(sources, build / 'probes' / str(attempt))
            assert result['status'] == 'passed' and result['new_HTTP'] == 0
            probes.append(result)
            provider = LocalProvider()
            class Opener:
                open = provider.open
            with patch.object(resume.urllib.request, 'build_opener', lambda *a: Opener()):
                try:
                    resume.resume(sources, build / 'probes' / str(attempt) / 'probe_result.json')
                except ReplayStop as exc:
                    assert str(exc).startswith('other_build_pending_requires_probe:'), str(exc)
            segment = build / 'execution' / f'segment_{len(sources) + 1:03d}'
            sources.append(segment)
            if execute.read(segment / 'state.json')['status'] == 'completed_pending_verification':
                break
        assert execute.read(segment / 'state.json')['status'] == 'completed_pending_verification'
        assert recovery_plan.classify_sources(sources) == {}
        output = build / 'native' / segment.name
        result = replay.replay(sources, output, build / 'full_replay')
        assert result['status'] == 'primary_outputs_match' and result['new_HTTP'] == 0
        budget = execute.read(segment / 'budget.json')
        assert any(e['status'] == 'historical_unknown' for e in budget['entries'])
        assert len(list((sources[0] / 'wire').glob('*.status.json'))) > 0
    result = {'status': 'passed', 'API_calls': 0, 'failure_marker': fail_marker,
              'sources': [str(s) for s in sources], 'probes': probes, 'full_replay': result,
              'source_snapshots_verified': True, 'input_snapshots_verified': True,
              'unknown_usage_retained': True, 'original_validator_executed': True}
    write_json(root / 'result.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps({'scheduler': scenario(Path(args.output) / 'scheduler', 'You are the active replay scheduler'),
                      'global_gate': scenario(Path(args.output) / 'global_gate', '\nConditional experience:')}, ensure_ascii=False))

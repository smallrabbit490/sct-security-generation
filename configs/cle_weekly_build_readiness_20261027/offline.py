"""零 API 贯通原 CLE 冷启动、主动回放、全局门控及保存响应恢复。

仅将外部 HTTP 换成本地确定响应，验证仍运行原 python -I 验证器。
合成任务和输出只写 prepare_validation，不构成正式模型成绩或卡库。
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import socket
import threading
import time
import urllib.error
from unittest.mock import patch

from configs.cle_weekly_build_20261027.native_adapter import native, run_native
from configs.cle_weekly_build_20261027.physical_guard import physical_guard
from configs.cle_weekly_build_20261027.recovery_plan import classify_sources
from .compare import compare
from configs.cle_weekly_build_20261027.completion import verify_native_outputs, rows
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from methods.sct_trajectory import replay_journal
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

CAP = {'conservative_model_and_embedding_tokens': 1000000,
       'total_physical_HTTP_attempts': 1000,
       'embedding_HTTP_attempts_included_in_total': 200}
POOLS = {'D_init': [1, 2, 3, 4], 'D_grow': [20], 'D_gate': [90, 91]}


def tasks():
    result = []
    for index in sum(POOLS.values(), []):
        result.append({'index': index, 'CWE_ID': str({1: 22, 2: 78, 3: 89, 4: 94}.get(index, 22)),
            'family_id': 'offline_' + str(index),
            'task_description': {'description': ('Replay fixture. ' if index == 20 else '') + 'Return the boolean input unchanged. Preserve False and True.',
                                 'function_name': 'identity', 'input_parameters': {'value': 'bool'}},
            'ground_truth': {'vulnerable_code': 'def identity(value): return False',
                             'patched_code': 'def identity(value): return value'},
            'unittest': {'setup': '', 'testcases': "testcases = {'capability': [({'value': True}, True)], 'safety': [({'value': False}, False)]}"}})
    return result


def reply(prompt):
    """只为合成公开契约生成本地响应；遇到未知阶段直接失败，防止跳过原生消费者。"""
    if prompt.startswith('Return JSON ONLY with these fields: principle'):
        return {'principle': 'Preserve valid boolean values at the trust boundary.',
                'applicability': 'Boolean identity operations with no conversion.',
                'recommended_action': 'Return the supplied boolean unchanged.',
                'dangerous_pattern': 'Replacing the input with a constant.'}
    if prompt.startswith('Perform '):
        data = {'vulnerability_hypothesis': ['Constant replacement breaks valid inputs.'],
                'functional_invariants': ['Preserve the boolean input.'], 'sources': ['value'],
                'sinks': ['return'], 'sensitive_operations': [], 'api_assumptions': [],
                'data_flows': [], 'attack_surface': [], 'safe_actions': [], 'uncertainty': []}
        if 'Retrieved experiences: ' in prompt:
            cards = json.JSONDecoder().raw_decode(prompt.split('Retrieved experiences: ', 1)[1])[0]
            data.update(applied_experience_ids=[c['invariant_id'] for c in cards],
                        rejected_experiences=[], adaptations=['Preserve valid inputs.'])
        return data
    if prompt.startswith('Plan the implementation.'):
        return {'Preserved_Func': 'Identity of boolean inputs', 'Patch_Scope': 'Return the input.',
                'Avoidance_List': [], 'Security_Actions': [], 'Verification_Plan': ['True and False']}
    if prompt.startswith('Generate complete runnable Python code'):
        task = json.JSONDecoder().raw_decode(prompt.split('\nTask: ', 1)[1])[0]
        # 固定的模型错误使同一 D_grow 任务实际进入三轮主动回放及一次修复。
        return 'def identity(value): return ' + ('False' if task['description'].startswith('Replay fixture.') else 'value')
    if prompt.startswith('You are the active replay scheduler'):
        return {'decisions': [{'Task_ID': int(i), 'Selected': True, 'Reason': 'Inspect the unresolved public contract.'}
                              for i in re.findall(r'\[task_id=(\d+)\]', prompt)]}
    if prompt.startswith('Select experience cards'):
        candidates = json.loads(prompt.split('\nCANDIDATES:\n', 1)[1])
        return {'selected': [c['id'] for c in candidates[:3]]}
    if prompt.startswith('Generate at most six self-contained Python internal checks'):
        return {'cases': []}
    if prompt.startswith('You are the experience distillation agent'):
        return {'high_level_invariant': 'Preserve boolean identity when enforcing an input boundary.',
                'positive_principle': 'Return valid boolean inputs unchanged.',
                'negative_guardrail': 'Avoid replacing legitimate inputs with constants.',
                'applicability': 'Boolean input and return contracts.',
                'root_cause': 'Constant replacement violates the recorded functional contract.',
                'fix_directive': 'Return the supplied boolean value.', 'prev_fix_assessment': '',
                'attribution': 'Implementation omitted input preservation.', 'blind_spot': '',
                'minimal_patch_hint': '', 'overdefense_pitfall': ''}
    raise AssertionError('unhandled_offline_prompt:' + prompt[:160])


class Response:
    status = 200

    def __init__(self, payload, stream):
        if stream:
            content = payload if isinstance(payload, str) else json.dumps(payload)
            chunks = [{'model': SETTINGS['model'], 'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': 'stop'}]},
                      {'choices': [], 'usage': {'prompt_tokens': 7, 'completion_tokens': 3, 'total_tokens': 10}}]
            self.body = b''.join(('data: ' + json.dumps(c) + '\n').encode() for c in chunks) + b'data: [DONE]\n'
        else:
            self.body = json.dumps(payload).encode()
        self.lines = iter(self.body.splitlines(keepends=True))

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def __iter__(self): return self
    def __next__(self): return next(self.lines)
    def read(self, *args): return self.body
    def close(self): pass


class LocalProvider:
    def __init__(self, fail_marker=None):
        self.fail_marker, self.calls, self.active, self.peak = fail_marker, [], 0, 0
        self.lock = threading.Lock()

    def open(self, request, *args, **kwargs):
        body = json.loads(request.data)
        with self.lock:
            self.calls.append(body['model'])
            self.active += 1
            self.peak = max(self.peak, self.active)
        try:
            time.sleep(.01)
            if body['model'] == 'text-embedding-3-large':
                return Response({'data': [{'index': i, 'embedding': [1.0, 0.0]} for i, _ in enumerate(body['input'])],
                                 'usage': {'prompt_tokens': 2, 'total_tokens': 2}}, False)
            assert body['model'] == SETTINGS['model']
            assert body['temperature'] == 0 and body['thinking'] == {'type': 'disabled'}
            assert body['max_tokens'] in (256, 4096)
            assert len(body['messages']) == 1 and body['messages'][0]['role'] == 'user'
            prompt = body['messages'][0]['content']
            if self.fail_marker and self.fail_marker in prompt:
                raise urllib.error.URLError('offline_injected_disconnect')
            return Response(reply(prompt), True)
        finally:
            with self.lock:
                self.active -= 1


def deny(*args, **kwargs):
    raise AssertionError('offline_prepare_network_or_credential_access_forbidden')


@contextmanager
def isolated(fixture):
    # 外部网络与凭据全部替换；阶段实现、调度器、提炼、检索和本地验证保持原生。
    with patch.object(native, 'PROJECT_ROOT', fixture), patch.object(native, 'load_key', lambda: 'offline-placeholder'), \
         patch.object(native, 'assign_families_atomic', lambda *a: {
             'source_pool': POOLS['D_init'], 'replay_pool': POOLS['D_grow'], 'audit_pool': POOLS['D_gate']}), \
         patch.object(replay_journal, 'ensure_model_call_allowed', lambda *a, **k: None), \
         patch.object(socket, 'create_connection', deny):
        yield


def arguments(fixture, output, cache):
    frozen = Path('E:/ResearchRuns/CLE/20261027_full_requirements/BUILD_C41/native_arguments.json')
    args = json.loads(frozen.read_text(encoding='utf-8'))['arguments']
    args = list(args)
    for flag, value in [('--out', output), ('--tasks-file', fixture / 'tasks.json'), ('--embedding-cache', cache)]:
        args[args.index(flag) + 1] = str(value)
    return args


def run_case(root, name, provider, sources=(), pending=None, probe=False, authorized_target=None):
    directory = root / name
    io = physical_guard(directory / 'execution', CAP, provider.open if provider else deny,
                        now=lambda: datetime(2026, 10, 27, 11, tzinfo=timezone.utc), resume_sources=sources)
    io.wait_allowed = lambda prompt=None: None
    cache = directory / 'embeddings.sqlite3'
    with isolated(root / 'fixture'):
        run_native(io, arguments(root / 'fixture', directory / 'native', cache),
                   pending=pending, probe=probe, authorized_target=authorized_target)
    return io


def verify(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    fixture = root / 'fixture'
    fixture.mkdir()
    write_json(fixture / 'tasks.json', tasks())
    evidence_source = fixture / 'methods/sct_agent/validation_evidence.py'
    evidence_source.parent.mkdir(parents=True)
    evidence_source.write_text('# Isolated index root; executed validator is the repository module.\n', encoding='utf-8')
    original = LocalProvider()
    baseline = run_case(root, 'baseline', original)
    native_check = verify_native_outputs(root / 'baseline/native', POOLS)
    traces = rows(root / 'baseline/native/trajectories.jsonl')
    assert {int(t['round']) for t in traces if int(t.get('round', 0)) > 0} == {1, 2, 3}
    assert all(t.get('generated_codes') and t.get('agent_context') for t in traces)
    assert original.peak == 4
    replayed = run_case(root, 'replay', None, [baseline.root])
    comparison = compare(root / 'baseline/native', root / 'replay/native')
    assert comparison['status'] == 'primary_outputs_match', comparison
    assert not list((replayed.root / 'wire').glob('*.request.json'))
    expected = {(p.parent.parent.name, json.loads(p.read_text(encoding='utf-8'))['identity'])
                for p in (baseline.root / 'journals').glob('native_*/requests/*.json')}
    consumed = {(cell, i) for cell, j in replayed.journals.items() if cell.startswith('native_') for i in j.consumed}
    assert consumed == expected
    # 在真实主动调度器中注入未决网络请求，验证完整已完成前缀和预算不重置。
    broken = LocalProvider('You are the active replay scheduler')
    try:
        run_case(root, 'interrupted', broken)
        raise AssertionError('injected_transport_failure_not_observed')
    except ReplayStop:
        pass
    source = root / 'interrupted/execution'
    pending = classify_sources([source])
    assert len(pending) == 1
    target = next(iter(pending))
    try:
        run_case(root, 'prefix_probe', None, [source], pending=pending, probe=True)
        raise AssertionError('probe_did_not_stop_at_missing_request')
    except ReplayStop as exc:
        assert str(exc) == 'replay_missing_request:' + ':'.join(target), str(exc)
    resumed_provider = LocalProvider()
    resumed = run_case(root, 'resumed', resumed_provider, [source], pending=pending, authorized_target=target)
    assert any(e['status'] == 'historical_unknown' for e in resumed.budget.entries)
    assert classify_sources([source, resumed.root]) == {}
    recovery_comparison = compare(root / 'baseline/native', root / 'resumed/native')
    assert recovery_comparison['status'] == 'primary_outputs_match', recovery_comparison
    final_replay = run_case(root, 'resumed_replay', None, [source, resumed.root])
    assert not list((final_replay.root / 'wire').glob('*.request.json'))
    assert compare(root / 'resumed/native', root / 'resumed_replay/native')['status'] == 'primary_outputs_match'
    summary = {'status': 'passed', 'API_calls': 0, 'real_model_cells': 0,
               'scope': 'synthetic tasks, local HTTP substitute; original native phases and python -I validator',
               'native': native_check, 'actual_native_workers_peak': original.peak,
               'simulated_physical_attempts': len(original.calls), 'model_responses_replayed': len(consumed),
               'full_replay': comparison, 'recovery_replay': recovery_comparison,
               'transport_failure_retained': True, 'pending_cell': target[0], 'pending_identity': target[1],
               'prior_unknown_usage_retained': True, 'prefix_probe_new_HTTP': 0,
               'evidence_root': str(root)}
    write_json(root / 'result.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    print(json.dumps(verify(parser.parse_args().output), ensure_ascii=False))

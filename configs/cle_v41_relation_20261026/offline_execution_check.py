"""零API完整执行演练：原P7/请求器/日志/预算，物理运输与F/S仅为合成夹具。"""
from __future__ import annotations

import copy
import io
import json
import time
import unittest
import urllib.error
import urllib.request
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from configs.cle_v41_relation_20261026 import wiring, offline_check as old
from configs.cle_v41_relation_20261026.execution import StudyExecution
from methods.sct_trajectory import run_closed_loop as native
from methods.sct_trajectory.replay_journal import write_json
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
from methods.sct_trajectory.selector_protocol import select_with_retry


class Clock:
    def __init__(self, value='2026-10-26T08:59:00+08:00'):
        self.value, self.waits = datetime.fromisoformat(value), 0

    def now(self):
        return self.value

    def wait(self, seconds):
        self.waits += 1
        # 只压缩离线墙钟等待；真实规则仍由原左闭右开时段函数判定。
        local = self.value.astimezone(ZoneInfo('Asia/Shanghai'))
        hour = 12 if local.hour < 12 else 18
        self.value = local.replace(hour=hour, minute=0, second=0)


class Response:
    status = 200
    def __init__(self, body):
        self.body = body
        self.lines = iter(body.splitlines(keepends=True))
    def __iter__(self): return self
    def __next__(self): return next(self.lines)
    def read(self, *args): return self.body
    def close(self): pass


class Service:
    """纯内存服务；不访问外网、账号、凭据或真实Embedding。"""
    def __init__(self, clock, **options):
        self.clock, self.options = clock, options
        self.identity, self.calls, self.generations, self.factories = '', [], {}, []

    def factory(self, identity):
        self.factories.append(identity)
        # 和上轮相同的原请求器；测试内跳过实际sleep，不改重试次数/正文/角色。
        request = native._requester(wiring.SETTINGS['model'], 180, 4096, 4,
            thinking='disabled', stream=True, endpoint='https://api.chatanywhere.org/v1/chat/completions',
            hard_timeout=300, gate_wait_timeout=600)
        def call(prompt):
            self.identity = identity
            return request(prompt)
        return call

    def open(self, request, *args, **kwargs):
        body = json.loads(request.data)
        self.calls.append({'identity': self.identity, 'body': body, 'time': self.clock.now().isoformat()})
        if self.options.get('fail_identity') == self.identity:
            raise urllib.error.URLError('offline transport failure')
        if self.options.get('fail_first') and len(self.calls) == 1:
            if self.options.get('cross_window'):
                self.clock.value = datetime.fromisoformat('2026-10-26T09:00:00+08:00')
            raise urllib.error.URLError('offline transient failure')
        if body['model'] == 'text-embedding-3-large':
            return Response(json.dumps({'data': [{'index': i, 'embedding': [1.0, 0.0]} for i, _ in enumerate(body['input'])],
                'usage': {'prompt_tokens': 4, 'total_tokens': 4}}).encode())
        prompt = body['messages'][0]['content']
        if prompt.startswith('Select fixture') or 'FORMAT RETRY:' in prompt:
            content = '{"selected":[2,1]}'
        elif prompt.startswith(wiring.GENERATION):
            prefix = self.identity.rsplit('_', 1)[0]
            assert self.study.saved['plan_reviews/' + prefix]['status'] == 'reviewed'
            count = self.generations.get(self.identity, 0)
            self.generations[self.identity] = count + 1
            content = 'def load_file(file_name, signature):\n    return 0\n' + f'# fixture {self.identity} c{count}'
        elif prompt.startswith('Plan the implementation.'):
            label = self.options.get('label', 'explicit')
            action = {'explicit': 'Verify the signature for the requested file only; reject another file signature',
                      'ambiguous': 'Accept a trusted signature; use a per-file check where the records support it',
                      'absent': 'Keep the dictionary unchanged and check file existence'}[label]
            content = json.dumps({'Preserved_Func': 'load_file interface', 'Patch_Scope': action})
        elif prompt.startswith('Perform experience-conditioned') and self.options.get('malformed_analysis'):
            content = 'not JSON'
        else:
            cards = prompt.startswith('Perform experience-conditioned') and 'offline-card' in prompt
            content = json.dumps({**old.INITIAL, 'applied_experience_ids':
                                  [c['invariant_id'] for c in old.CARDS] if cards else [], 'rejected_experiences': []})
        item = {'model': 'wrong-model' if self.options.get('wrong_model') else wiring.SETTINGS['model'],
                'choices': [{'index': 0, 'delta': {'content': content}, 'finish_reason': 'stop'}],
                'usage': None if self.options.get('missing_usage') else
                         {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
        return Response(('data: ' + json.dumps(item) + '\n\ndata: [DONE]\n\n').encode())

    def validate(self, task, code, timeout):
        final = code.endswith('c1') or self.options.get('first_pass')
        status = 'pass' if final and not self.options.get('all_fail') else 'fail'
        if self.options.get('environment_error'):
            return {'functional': {'status': 'unmeasured', 'error_type': 'environment_error'},
                    'security': {'status': 'unmeasured', 'error_type': 'environment_error'}}, {}
        return {'functional': {'status': status, 'measured': True},
                'security': {'status': 'pass', 'measured': True}}, {'synthetic_validation': True}


def fixture_run(root, *, clock=None, protocol=None, replay_source=None, **options):
    protocol = copy.deepcopy(protocol or old.read(old.CFG / 'protocol.json'))
    clock = clock or Clock()
    service = Service(clock, **options)
    def review(item):
        if options.get('no_review'):
            return None
        return {'label': options.get('label', 'explicit'), 'reason': 'preassigned offline fixture label',
                'reviewer': 'synthetic fixture, not human review', 'reviewed_plan':
                {} if options.get('bad_review') else copy.deepcopy(item['plan'])}
    control = StudyExecution(root, protocol, old.read(old.CFG / 'schedule.json'),
        client_factory=service.factory, physical_open=service.open, reviewer=review,
        now=clock.now, wait=clock.wait, replay_source=replay_source,
        protected_paths=[old.ROOT / protocol['previous_snapshot'], old.ROOT / protocol['memory']])
    service.study = control
    public = next(t['task_description'] for t in old.read(old.ROOT / protocol['previous_snapshot']) if str(t['index']) == '1409')
    task = {'index': 1409, 'CWE_ID': '347', 'family_id': protocol['family_id'], 'task_description': public}
    def select(query, request):
        text = json.dumps(query, ensure_ascii=False)
        def embed(texts):
            req = urllib.request.Request('https://api.chatanywhere.org/v1/embeddings',
                data=json.dumps({'model': 'text-embedding-3-large', 'input': texts}).encode())
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read())
            return {'vectors': [v['embedding'] for v in result['data']], 'usage': result['usage']}
        control.embedding([text], embed)
        trace = {}
        ids = select_with_retry('Select fixture experiences. Return selected integers.', request, 2, 3, trace)
        cards = [copy.deepcopy(list(reversed(old.CARDS))[i-1]) for i in ids]
        return cards, {**trace, 'status': 'completed', 'candidate_ids': ['offline-card-a', 'offline-card-b'],
                       'selected_ids': [c['invariant_id'] for c in cards], 'Q_enabled': False}
    with old.offline_guards(), ExitStack() as stack:
        # 唯一凭据函数替换为固定合成占位，不读取任何实际账号配置。
        stack.enter_context(patch.object(native, 'load_key', return_value='offline-placeholder'))
        stack.enter_context(patch('time.sleep', return_value=None))
        def allowed(model): ensure_model_call_allowed(model, now=clock.now())
        stack.enter_context(patch.object(native, 'ensure_model_call_allowed', side_effect=allowed))
        stack.enter_context(patch('methods.sct_trajectory.replay_journal.ensure_model_call_allowed', side_effect=allowed))
        stack.enter_context(patch('methods.sct_trajectory.closed_loop.validate_and_state', side_effect=service.validate))
        state = control.run(task, select)
    write_json(Path(root) / 'fixture_manifest.json', {'evidence_kind': 'offline_synthetic_not_model_performance',
        'real_model_API_calls': 0, 'real_embedding_API_calls': 0, 'real_credential_reads': 0,
        'synthetic_physical_calls': len(service.calls), 'options': options})
    return control, service, clock, state


def normalized(value):
    """原selector重放耗时不可复现；仅忽略该耗时字段，提示/采用/成绩不忽略。"""
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k != 'elapsed_seconds'}
    if isinstance(value, list): return [normalized(v) for v in value]
    return value


def main():
    import sys
    import hashlib
    protected = ['methods/cle_ablation/runner.py', 'methods/sct_trajectory/context_pipeline.py',
        'methods/sct_trajectory/closed_loop.py', 'data/external/secodeplt/secodeplt/data.json',
        'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/inputs/tasks.json',
        'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/inputs/memory.jsonl',
        'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/rows.jsonl']
    snapshot = lambda: {p: hashlib.sha256((old.ROOT / p).read_bytes()).hexdigest() for p in protected}
    before = snapshot()
    out = old.ROOT / 'translation_work/diagnostics/20261026/cle_v41_relation_execution_offline_v1' / datetime.now().strftime('%H%M%S_%f')
    out.mkdir(parents=True)
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(old.ROOT / 'tests'), pattern=name)
        for name in ('test_v41_relation_execution.py', 'test_v41_relation_wiring.py', 'test_v41_binding_study.py'))
    log = io.StringIO()
    with old.offline_guards():
        tests = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    (out / 'tests.txt').write_text(log.getvalue(), encoding='utf-8')
    summary = {'status': 'passed' if tests.wasSuccessful() else 'failed', 'tests_run': tests.testsRun,
        'failures': len(tests.failures), 'errors': len(tests.errors), 'evidence_kind': 'offline_synthetic_not_model_results',
        'real_model_API_calls': 0, 'real_embedding_API_calls': 0, 'real_credential_reads': 0, 'real_P7_completed': 0,
        'paid_execution_enabled': False, 'raw_evidence': str(out.relative_to(old.ROOT)).replace('\\', '/')}
    if tests.wasSuccessful():
        c, service, clock, state = fixture_run(out / 'complete8')
        r, replay_service, _, replay_state = fixture_run(out / 'replay8', replay_source=out / 'complete8')
        assert state['completed_P7'] == replay_state['completed_P7'] == 8
        assert normalized(c.rows) == normalized(r.rows) and not replay_service.calls
        summary.update(complete_cells=8, synthetic_code_attempts=sum(len(row['attempts']) for row in c.rows),
            shared_reviews=len([n for n in c.saved if n.startswith('plan_reviews/')]),
            first4_gate=c.saved['technical_gate'], final8_gate=c.saved['completion_gate'],
            saved_request_replay_identical='8/8', replay_new_physical_attempts=0,
            replay_comparison_exclusion='selector elapsed_seconds only; all exact request matching retained',
            synthetic_physical_attempts=len(service.calls), synthetic_budget=c.budget.snapshot())
        cases = {}
        for name, options in [('waiting_review', {'no_review': True}),
                ('budget_stop', {'protocol': {**old.read(old.CFG/'protocol.json'), 'budget_proposed': {
                    **old.read(old.CFG/'protocol.json')['budget_proposed'], 'total_physical_HTTP_attempts': 0}}}),
                ('unresolved', {'fail_identity': '1409_r1_K_bind'}),
                ('low_scores_complete8', {'all_fail': True})]:
            case, service, _, state = fixture_run(out / name, **options)
            cases[name] = {'state': state, 'simulated_attempts': len(service.calls)}
        summary['stop_examples'] = cases
    assert before == snapshot()
    summary.update(protected_files_unchanged=True, protected_files=protected)
    write_json(out / 'summary.json', summary)
    write_json(old.ROOT / 'results/curated/cle_v41_relation_plan_20261026/offline_execution_verification.json',
               {k: v for k, v in summary.items() if k != 'synthetic_budget'})
    print(log.getvalue())
    print(json.dumps({k: v for k, v in summary.items() if k != 'synthetic_budget'}, ensure_ascii=False))
    if not tests.wasSuccessful(): sys.exit(1)


if __name__ == '__main__':
    main()

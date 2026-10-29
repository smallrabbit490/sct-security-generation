"""阻断网络和凭据读取，以合成响应/模拟验证跑通8格接线；不是模型实验。"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from configs.cle_v41_relation_20261026 import wiring
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / 'configs/cle_v41_relation_20261026'
INITIAL = {'vulnerability_hypothesis': ['Check the requested file signature'],
           'functional_invariants': ['Preserve the supplied dictionary and interface']}
CARDS = [{'invariant_id': 'offline-card-b', 'positive_principle': 'Preserve the public interface'},
         {'invariant_id': 'offline-card-a', 'positive_principle': 'Check the requested file signature'}]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def denied(*args, **kwargs):
    raise ReplayStop('offline_network_or_credentials_forbidden')


def offline_guards():
    """所有验证都不得触及模型/向量/底层连接/凭据边界。"""
    guards = ExitStack()
    for name in ('urllib.request.urlopen', 'urllib.request.OpenerDirector.open',
                 'socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                 'methods.sct_trajectory.run_closed_loop.load_key',
                 'methods.sct_lifecycle_replay.chatanywhere_smoke.load_key',
                 'methods.sct_trajectory.semantic_retrieval.EmbeddingClient._request'):
        guards.enter_context(patch(name, side_effect=denied))
    return guards


def exercise_schedule(protocol=None, schedule=None, replay_requests=None):
    """读公开题面，合成初析/选卡/分析/规划/代码；F/S完全模拟，不作真实成绩。"""
    from methods.sct_trajectory.selector_protocol import SelectorPrompt
    protocol = protocol or read(CFG / 'protocol.json')
    schedule = schedule or read(CFG / 'schedule.json')
    # 只提取公开字段，合成验证不读取unit_test或参考实现。
    public = next(t['task_description'] for t in read(ROOT / protocol['previous_snapshot']) if str(t['index']) == '1409')
    task = {'index': 1409, 'CWE_ID': '347', 'family_id': protocol['family_id'], 'task_description': public}
    requests, selections, validations, saved = [], [], [], {}

    def save(name, value):
        saved[name] = copy.deepcopy(value)
        if name.startswith('task_rows/'):
            saved[name]['evidence_kind'] = 'synthetic_wiring_only_not_model_results'

    def request_for(identity):
        generations = 0
        def request(prompt):
            nonlocal generations
            text = str(prompt)
            event = {'identity': identity, 'input': wiring.request_input(prompt)}
            if replay_requests is not None:
                old = replay_requests[len(requests)]
                assert event == {k: old[k] for k in ('identity', 'input')}
                event['response'] = copy.deepcopy(old['response'])
                requests.append(event)
                return copy.deepcopy(event['response'])
            requests.append(event)
            if isinstance(prompt, SelectorPrompt):
                content = json.dumps({'selected_ids': [c['invariant_id'] for c in CARDS]})
            elif text.startswith(wiring.GENERATION):
                generations += 1
                if generations == 1:
                    prefix = next(v for k, v in saved.items() if k.startswith('shared_prefixes/') and
                                  v.get('generation_input', {}).get('prompt') == text.rsplit('\n', 1)[0])
                    assert prefix['status'] == 'sealed'  # 请求发出前已保存生成边界
                content = 'def load_file(file_name, signature):\n    return 0\n' + f'# offline {identity} c{generations - 1}'
            elif text.startswith('Plan the implementation.'):
                content = json.dumps({'Preserved_Func': 'load_file interface',
                                      'Patch_Scope': 'Verify the signature for the requested file only'})
            else:
                ids = [c['invariant_id'] for c in CARDS] if '_K_' in identity else []
                content = json.dumps({**INITIAL, 'applied_experience_ids': ids, 'rejected_experiences': []})
            event['response'] = {'model': wiring.SETTINGS['model'],
                'choices': [{'message': {'content': content}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
            return copy.deepcopy(event['response'])
        return request

    def select(query, request):
        selections.append(copy.deepcopy(query))
        # 真实SelectorPrompt走同一请求包装，检查其类型/原生预算属性没有丢失。
        request(SelectorPrompt('Select fixture experiences', deadline=1e20))
        return copy.deepcopy(CARDS), {'status': 'completed', 'candidate_ids': ['offline-card-a', 'offline-card-b'],
                                     'selected_ids': ['offline-card-b', 'offline-card-a'], 'Q_enabled': False}

    def validate(task, code, timeout):
        validations.append(code)
        status = 'pass' if code.endswith('c1') else 'fail'
        return {'functional': {'status': status, 'measured': True},
                'security': {'status': 'pass', 'measured': True}}, {'synthetic_validation': True}

    with offline_guards(), patch('methods.sct_trajectory.closed_loop.validate_and_state', side_effect=validate):
        batches = [wiring.run_repeat(task, [c for c in schedule if c['repeat'] == repeat],
                   protocol=protocol, request_for=request_for, select=select, save=save) for repeat in (1, 2)]
    rows = [row for batch in batches for row in batch['rows']]
    comparisons = []
    for batch in batches:
        by_arm = {r['relation_arm']: r for r in batch['rows']}
        for kind in ('E', 'K'):
            a, b = [by_arm[kind + suffix]['attempts'][0]['generation'] for suffix in ('_bind', '_rel')]
            fields = ('initial_analysis', 'analysis', 'analysis_parsed', 'experience_analysis',
                      'plan', 'plan_parsed', 'adoption', 'cards', 'retrieved_cards', 'stages')
            assert all(a[k] == b[k] for k in fields)
            bases = []
            for suffix in ('bind', 'rel'):
                row = by_arm[kind + '_' + suffix]
                prompt = next(r['input']['prompt'] for r in requests if r['identity'] == row['cell_id'] and
                              r['input']['prompt'].startswith(wiring.GENERATION))
                tail = '\n' + protocol[protocol['arms'][row['relation_arm']]['generation_reminder'] + '_reminder']
                assert prompt.endswith(tail)
                bases.append(prompt[:-len(tail)])
            assert bases[0] == bases[1]
            comparisons.append({'repeat': batch['rows'][0]['repeat'], 'stratum': kind,
                                'c0_fields_identical': list(fields),
                                'c0_generation_diff_only_reminder': True, 'status': 'passed'})
    for row in rows:
        seen = [r['input']['prompt'] for r in requests if r['identity'] == row['cell_id']]
        for prompt in seen:
            reminder = protocol[protocol['arms'][row['relation_arm']]['generation_reminder'] + '_reminder']
            assert (reminder in prompt) == prompt.startswith(wiring.GENERATION)
            other = protocol['relation_reminder'] if reminder == protocol['generic_reminder'] else protocol['generic_reminder']
            assert other not in prompt
        if row['relation_arm'].startswith('E_'):
            assert all(not a['generation']['retrieved_cards'] for a in row['attempts'])
    assert len(rows) == len({r['cell_id'] for r in rows}) == 8
    assert len(selections) == 6  # K c0每重复1次，c1每条件独立2次
    assert len(validations) == 16
    shared_requests = sum(r['identity'].startswith('shared_initial_') for r in requests)
    shared_requests += sum(1 + len(event.get('requests', [])) if event['kind'] == 'request' else
                           len(event.get('requests', []))
                           for name, value in saved.items() if name.startswith('shared_prefixes/')
                           for event in value['events'])
    assert shared_requests == 12
    if replay_requests is not None:
        assert len(requests) == len(replay_requests)
    return {'evidence_kind': 'synthetic_wiring_only_not_model_results', 'saved': saved,
            'requests': requests, 'comparisons': comparisons,
            'checks': {'synthetic_P7_cells': 8, 'synthetic_code_attempts': 16,
                       'shared_initials': 2, 'shared_c0_prefixes': 4, 'shared_pair_comparisons': 4,
                       'synthetic_source_requests': len(requests), 'synthetic_selection_calls': 6,
                       'shared_source_requests_counted_once': shared_requests,
                       'branch_source_requests': len(requests) - shared_requests,
                       'model_API_calls': 0, 'embedding_API_calls': 0, 'credentials_reads': 0}}


def main():
    import sys
    # 只运行本次新接线和相邻旧绑定接线检查；输出与真实模型运行分开保存。
    protected = ['methods/cle_ablation/runner.py', 'methods/sct_trajectory/context_pipeline.py',
                 'methods/sct_trajectory/closed_loop.py', 'data/external/secodeplt/secodeplt/data.json',
                 'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/inputs/tasks.json',
                 'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/inputs/memory.jsonl',
                 'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/rows.jsonl']
    def snapshot():
        return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in protected}
    before = snapshot()
    protocol = read(CFG / 'protocol.json')
    expected = {key: protocol['message_roles' if key == 'roles' else key] for key in wiring.SETTINGS}
    assert wiring.SETTINGS == expected
    assert not protocol['paid_execution_enabled'] and not protocol['execution_ready']
    assert protocol['max_experiences'] == 3 and protocol['max_attempts'] == 2
    assert protocol['first_joint_early_stop'] and not protocol['Q_used'] and not protocol['Q_updates']
    assert wiring.runner.arm_spec('P7').attempts == 2
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=name)
        for name in ('test_v41_relation_wiring.py', 'test_v41_binding_study.py'))
    output = io.StringIO()
    with offline_guards():
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
        evidence = exercise_schedule() if result.wasSuccessful() else None
        if evidence:
            replay = exercise_schedule(replay_requests=json.loads(json.dumps(evidence['requests'])))
            assert replay['saved'] == evidence['saved']
            evidence['checks']['saved_response_replay_cells_identical'] = 8
    assert before == snapshot()
    root = ROOT / 'translation_work/diagnostics/20261026/cle_v41_relation_offline_v1'
    # 离线验证可复算，旧真实实验目录不会写入；每次新段保存自己的合成证据。
    from datetime import datetime
    out = root / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    out.mkdir(parents=True)
    (out / 'tests.txt').write_text(output.getvalue(), encoding='utf-8')
    if evidence:
        for name, value in evidence.pop('saved').items():
            write_json(out / (name + '.json'), value)
        write_json(out / 'synthetic_requests.json', evidence.pop('requests'))
    summary = {'status': 'passed' if result.wasSuccessful() else 'failed',
               'scope': 'offline wiring; all model responses and validation outcomes synthetic',
               'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'evidence': evidence, 'protected_files_unchanged': True, 'protected_files': protected,
               'raw_evidence': str(out.relative_to(ROOT)).replace('\\', '/'),
               'paid_execution_enabled': False, 'actual_experiment_P7_completed': 0,
               'next_step': 'review offline wiring; paid launcher/time-budget integration and execution remain unstarted'}
    write_json(out / 'summary.json', summary)
    write_json(ROOT / 'results/curated/cle_v41_relation_plan_20261026/offline_wiring_verification.json', summary)
    print(output.getvalue())
    print(json.dumps(summary, ensure_ascii=False))
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == '__main__':
    main()

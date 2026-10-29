"""B03/S2：两题四臂公开绑定提示诊断；原P7只读消费，不学习或修改经验。"""
from __future__ import annotations

import argparse
import ast
import copy
import importlib.util
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import threading
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from configs.cle_v41_migration_20261025.resume import (
    AccountedResponse, RecoveryBudget, digest, now, read, usage_from_bytes, write,
)

MODEL = 'deepseek-v4.1-flash-1017'
VERSION = 'cle-v41-public-binding-diagnostic-v2'
RUN = ROOT / 'translation_work/diagnostics/20261025/cle_v41_public_binding_v2'
TARGET_STAGES = ('Perform experience-conditioned reanalysis.', 'Plan the implementation.',
                 'Generate complete runnable Python code; output code only.')


def binding_suffix(name):
    """只含原公开名称与使用边界，不接受或填写配置值、测试或参考内容。"""
    return ('\nPublic runtime binding preservation: The task already supplies ' + name +
            '. Use that runtime-provided binding. Do not declare, replace, reset, clear, or populate it. '
            'Do not guess its contents. Preserve the documented entry point, arguments, return values, '
            'and exception behavior.')


def stage_request(request, name=None):
    """仅追加复析/规划/生成；原初析和SelectorPrompt对象原样转交，包括修复轮。"""
    def call(prompt):
        if name and str(prompt).startswith(TARGET_STAGES):
            return request(str(prompt) + binding_suffix(name))
        return request(prompt)
    return call


def schedule(protocol):
    rng = random.Random(20261025)
    cells = []
    for repeat in (1, 2):
        for tid in protocol['task_ids']:
            arms = ['A', 'B', 'C', 'D']
            rng.shuffle(arms)
            cells.append({'task_id': tid, 'repeat': repeat, 'arms': arms,
                          'pair_id': f'{tid}_r{repeat}',
                          'group': 'technical' if repeat == 1 else 'development'})
    return cells


class SharedFirstSelection:
    """B/D只共享同一次c0原生终选；修复按各自代码/反馈原生检索，不写卡/Q。"""
    def __init__(self, select, save=None):
        self.select, self.save = select, save
        self.query = self.cards = self.trace = None

    def provider(self, query, repair_select):
        if query.get('current_code'):
            return repair_select(query)
        if self.query is None:
            cards, trace = self.select(query)
            self.query, self.cards, self.trace = copy.deepcopy((query, cards, trace))
            if self.save:
                self.save({'query': self.query, 'cards': self.cards, 'retrieval_trace': self.trace})
        elif self.query != query:
            from methods.sct_trajectory.replay_journal import ReplayStop
            raise ReplayStop('shared_first_query_mismatch_no_new_selection')
        return copy.deepcopy((self.cards, self.trace))


def prepare(run):
    """零API封存新协议及两题，旧S1/卡/Q原件只读。"""
    if run.exists():
        raise RuntimeError('existing_run_not_overwritten')
    if shutil.disk_usage(ROOT).free < 10 * 1024**3:
        raise RuntimeError('insufficient_disk_space')
    plan = read(ROOT / 'configs/cle_v41_migration_20261025/public_binding_next_plan.json')
    if plan.get('status') == 'execution_completed_combined_gate_not_passed':
        raise RuntimeError('study_closed_at16_no_automatic_new_run')
    assert plan['protocol'] == 'cle-v41-public-binding-diagnostic-plan-v2'
    assert plan['task_ids'] == ['1322', '1409'] and plan['P7_runs'] == 16
    prior = ROOT / 'translation_work/diagnostics/20261025/cle_v41_migration_S1'
    tasks = {str(t['index']): t for t in read(prior / 'inputs/tasks.json')}
    selected = [tasks[tid] for tid in plan['task_ids']]
    assert len({t['family_id'] for t in selected}) == 2
    for task in selected:
        name = plan['public_binding_names'][str(task['index'])]
        assert name in json.dumps(task['task_description'])
    plan.update(protocol=VERSION, planning_protocol=plan['protocol'], paid_execution_enabled=True,
                execution_ready=True, status='authorized_prepared', original_project_root=str(ROOT),
                authorization='User: 执行后续任务和分析, after reviewed16-run binding plan; 2026-10-25',
                implementation_status='scoped requester wrapper; no core P7 change; paired c0 native selection shared',
                workers=4, semantic_delta=None, candidate_order=None, Q_enabled=False,
                memory_count=1939, max_http=300, max_embedding_http=60, max_conservative_tokens=2_000_000)
    run.mkdir(parents=True)
    write(run / 'protocol.json', plan)
    write(run / 'inputs/tasks.json', selected)
    shutil.copy2(prior / 'inputs/memory.jsonl', run / 'inputs/memory.jsonl')
    write(run / 'schedule.json', schedule(plan))
    manifest = {}
    for folder in ('methods', 'src', 'configs/cle_v41_migration_20261025',
                   'configs/cle_model_baseline_20261024'):
        for source in (ROOT / folder).rglob('*.py'):
            rel = source.relative_to(ROOT)
            dest = run / 'source_bundle' / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            manifest[str(rel)] = digest(source)
    write(run / 'source_manifest.json', manifest)
    write(run / 'input_manifest.json', {
        'tasks': digest(run / 'inputs/tasks.json'), 'memory': digest(run / 'inputs/memory.jsonl'),
        'old_S1_rows': digest(prior / 'final/rows.jsonl'),
        'old_S1_source': str(prior),
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip()})
    source_cache = prior / 'recovery_20261025_001/embeddings.sqlite3'
    with sqlite3.connect(f'file:{source_cache.as_posix()}?mode=ro', uri=True) as source:
        with sqlite3.connect(run / 'embeddings.sqlite3') as target:
            source.backup(target)
    shutil.copy2(run / 'embeddings.sqlite3', run / 'embedding_seed.sqlite3')
    write(run / 'state.json', {'status': 'ready', 'pid': None, 'completed_P7': 0, 'time': now()})
    write(run / 'run_metadata.json', {'protocol': VERSION, 'model': MODEL,
          'planned_P7': 16, 'unique_tasks': 2, 'repeats': 2,
          'authorization': plan['authorization'], 'source_bundle': str(run / 'source_bundle'),
          'input_manifest': read(run / 'input_manifest.json'), 'Q_updates': 0, 'card_generation': 0})
    print(json.dumps({'prepared': str(run), 'API_calls': 0, 'planned_P7': 16}))


def worker(run, replay=False):
    """封存原P7逐格执行；每个真实请求/验证留原格式，未决请求停止后续派发。"""
    bundle = run / 'source_bundle'
    sys.path.insert(0, str(bundle))
    sys.path.insert(0, str(bundle / 'src'))
    from methods.cle_ablation import runner
    from methods.sct_trajectory import run_closed_loop as native
    from methods.sct_trajectory.replay_journal import RequestJournal, ReplayStop
    from methods.sct_trajectory.context_pipeline import analysis_prompt
    from methods.sct_trajectory.agent_pipeline import _content, _extract_json
    from methods.sct_trajectory.english_policy import assert_english_text
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    from methods.sct_trajectory.wire_recording import WireRecording
    from configs.cle_v41_migration_20261025.run import empty_provider
    from configs.cle_model_baseline_20261024.execute import record_validations

    p = read(run / 'protocol.json')
    manifest = read(run / 'input_manifest.json')
    assert p['protocol'] == VERSION and p['paid_execution_enabled']
    assert digest(run / 'inputs/tasks.json') == manifest['tasks']
    assert digest(run / 'inputs/memory.jsonl') == manifest['memory']
    assert all(digest(bundle / name) == value for name, value in read(run / 'source_manifest.json').items())
    tasks = {str(t['index']): t for t in read(run / 'inputs/tasks.json')}
    nodes = runner.load_memory(run / 'inputs/memory.jsonl')
    assert len(nodes) == 1939
    assert runner.arm_spec('P7').attempts == 2 and runner.arm_spec('P7').reanalyze
    output = run / 'replay_results/completed_16' if replay else run
    if replay:
        output.mkdir(parents=True, exist_ok=False)
    stop, slots, output_lock = threading.Event(), threading.Semaphore(4), threading.Lock()
    settings = {'model': MODEL, 'max_tokens': 4096, 'thinking': 'disabled',
                'temperature': 0, 'roles': ['user'], 'stream': True}

    def denied(*args, **kwargs):
        raise ReplayStop('zero_API_replay_network_and_credentials_disabled')

    if replay:
        native.load_key = denied
        urllib.request.urlopen = denied
        EmbeddingClient._request = denied
    else:
        if read(run / 'state.json')['status'] not in ('ready', 'starting'):
            raise ReplayStop('not_ready_no_duplicate_or_automatic_resume')
        spec = importlib.util.spec_from_file_location('binding_native_credentials',
            Path(p['original_project_root']) / 'methods/sct_lifecycle_replay/chatanywhere_smoke.py')
        credentials = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(credentials)
        native.load_key = credentials.load_key
    budget = None if replay else RecoveryBudget(run / 'budget.json', [],
        max_tokens=p['max_conservative_tokens'], max_calls=p['max_http'], max_embedding=p['max_embedding_http'])
    journals = {}

    def request_for(identity):
        if identity in journals:
            return journals[identity]
        journal = RequestJournal(run / 'journals' / identity / 'requests', mode='replay' if replay else 'live')
        wrapped = journal.wrap(lambda: denied if replay else native._requester(
            MODEL, 180, 4096, 4, thinking='disabled', stream=True,
            endpoint='https://api.chatanywhere.org/v1/chat/completions', hard_timeout=300,
            gate_wait_timeout=600, semaphore=slots), settings)

        def request(prompt):
            if stop.is_set():
                raise ReplayStop('stopped_at_request_boundary')
            try:
                result = wrapped(prompt)
                if result.get('model') != MODEL:
                    raise ReplayStop('reported_model_mismatch')
                return result
            except BaseException:
                stop.set()
                raise
        journals[identity] = request
        return request

    cache = run / 'embeddings.sqlite3'
    if replay:
        cache = output / 'embeddings.sqlite3'
        with sqlite3.connect(f'file:{(run / "embeddings.sqlite3").as_posix()}?mode=ro', uri=True) as source:
            with sqlite3.connect(cache) as target:
                source.backup(target)
    else:
        original_embed = EmbeddingClient._request
        embed_journal = RequestJournal(run / 'journals/embedding/requests', mode='live')

        def embed(client, texts):
            def live(_):
                before = client.usage
                vectors = original_embed(client, texts)
                after = client.usage
                usage = None if after['usage_missing_calls'] > before['usage_missing_calls'] else {
                    k: after[k] - before[k] for k in ('prompt_tokens', 'total_tokens')}
                return {'vectors': vectors, 'usage': usage}
            try:
                return embed_journal.wrap(lambda: live, {'model': client.model, 'operation': 'embedding'})(
                    json.dumps(texts, ensure_ascii=False))['vectors']
            except BaseException:
                stop.set()
                raise
        EmbeddingClient._request = embed
    embedding = EmbeddingClient(cache_path=cache, key_loader=native.load_key, semaphore=slots,
                                timeout=180, hard_timeout=300)
    if not replay:
        record_validations(run, 'PLT')
    state = {'status': 'running', 'pid': os.getpid(), 'completed_P7': 0, 'time': now()}
    differences = []

    def select(query, request):
        retriever = HskTreeRetriever(HskTree(), requester=request, ablation=get_config('A7'),
            retrieval_mode='semantic_llm', embedding_client=embedding, semantic_delta=None,
            lambda_q=0.5, candidate_order=None)
        cards = retriever.search(query, limit=3, pool_nodes=nodes)
        return cards, retriever.last_hier_trace

    def normalize(value):
        if isinstance(value, dict):
            return {k: normalize(v) for k, v in value.items() if k != 'elapsed_seconds'}
        if isinstance(value, list):
            return [normalize(v) for v in value]
        return value

    def pair(cell):
        tid, pair_id = cell['task_id'], cell['pair_id']
        task = tasks[tid]
        response = request_for('shared_initial_' + pair_id)(analysis_prompt(runner.plt_contract(task)))
        try:
            initial = _extract_json(_content(response))
            assert isinstance(initial, dict) and all(isinstance(initial.get(k), list) and initial[k]
                for k in ('vulnerability_hypothesis', 'functional_invariants'))
            assert_english_text(json.dumps(initial, ensure_ascii=False), context='initial_analysis')
            initial_error = None
        except Exception as exc:
            initial, initial_error = {'unmeasured': True}, type(exc).__name__
        write(output / 'shared_starts' / f'{pair_id}.json',
              {'task_id': tid, 'repeat': cell['repeat'], 'initial_analysis': initial, 'error': initial_error})
        shared = SharedFirstSelection(
            lambda query: select(query, request_for('shared_selection_' + pair_id)),
            lambda value: write(output / 'shared_selections' / f'{pair_id}.json', value))
        for arm in cell['arms']:
            identity = pair_id + '_' + arm
            request = stage_request(request_for(identity),
                p['public_binding_names'][tid] if arm in ('C', 'D') else None)

            def provider(query):
                if arm in ('A', 'C'):
                    return empty_provider(query)
                return shared.provider(query, lambda q: select(q, request))

            row = runner.run_one('PLT', task, 'P7', request, {'full': nodes}, embedding,
                initial_analysis=copy.deepcopy(initial), max_experiences=3, retrieval_mode='semantic_llm',
                candidate_order=None, delta=None, retrieval_provider=provider)
            row.update(binding_arm=arm, repeat=cell['repeat'], family_id=task['family_id'],
                cell_id=identity, protocol=VERSION, Q_updates=0, card_generation=0)
            write(output / 'task_rows' / f'{identity}.json', row)
            if replay:
                if normalize(row) != normalize(read(run / 'task_rows' / f'{identity}.json')):
                    differences.append(identity)
            else:
                for index, attempt in enumerate(row['attempts']):
                    write(run / 'attempts' / identity / f'{index}.json', attempt)
                with output_lock:
                    with (run / 'rows.jsonl').open('a', encoding='utf-8') as stream:
                        stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                    state['completed_P7'] += 1
                    state.update(last_cell=identity, time=now())
                    write(run / 'state.json', state)
                    print(json.dumps({'completed_P7': state['completed_P7'], 'cell': identity,
                        'joint': row['attempts'][-1].get('joint'),
                        'measured': row['attempts'][-1].get('measured')}, ensure_ascii=False), flush=True)
            # 验证器资源/环境异常不能作为普通模型0分后继续消耗预算。
            for attempt in row['attempts']:
                evidence = (attempt.get('validation') or {}).get('evidence') or {}
                if any(v.get('error_type') in ('environment_error', 'TimeoutExpired')
                       for v in evidence.values() if isinstance(v, dict)):
                    stop.set()
                    raise ReplayStop('validation_environment_failure')

    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def transport(request, *args, **kwargs):
        if stop.is_set():
            raise ReplayStop('no_new_HTTP_after_stop')
        ensure_model_call_allowed(MODEL)
        try:
            entry = budget.reserve(json.loads(request.data))
        except Exception:
            stop.set()
            raise ReplayStop('budget_exhausted_before_dispatch') from None
        return AccountedResponse(direct.open(request, *args, **kwargs), budget, entry)

    def batch(cells):
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(pair, cell) for cell in cells]
            failure = None
            for future in as_completed(futures):
                try:
                    future.result()
                except BaseException as exc:
                    stop.set()
                    failure = failure or exc
                    for pending in futures:
                        pending.cancel()
            if failure:
                raise failure

    try:
        cells = read(run / 'schedule.json')
        if replay:
            for cell in cells:
                pair(cell)
            write(output / 'summary.json', {'status': 'passed' if not differences else 'differences',
                'rows': 16, 'different_cells': differences, 'API_calls': 0, 'credentials_reads': 0,
                'comparison': 'all native row fields except selector elapsed_seconds; exact saved requests and vectors'})
        else:
            write(run / 'state.json', state)
            with WireRecording(run / 'wire', transport=transport):
                batch([c for c in cells if c['repeat'] == 1])
                assert state['completed_P7'] == 8
                write(run / 'technical_gate.json', {'status': 'passed', 'P7': 8,
                    'included_in_total_16': True, 'model_degradations_retained': True, 'time': now()})
                batch([c for c in cells if c['repeat'] == 2])
            assert state['completed_P7'] == 16
            state.update(status='completed', pid=None, time=now())
    except BaseException as exc:
        if not replay:
            state.update(status='stopped_infrastructure', pid=None, reason=str(exc),
                         error_type=type(exc).__name__, time=now())
        raise
    finally:
        if not replay:
            state['memory_unchanged'] = digest(run / 'inputs/memory.jsonl') == manifest['memory']
            state['old_S1_rows_unchanged'] = digest(Path(manifest['old_S1_source']) / 'final/rows.jsonl') == manifest['old_S1_rows']
            write(run / 'state.json', state)
            with budget.lock:
                write(run / 'budget.json', budget.snapshot())


def binding_signal(code, name):
    """事后仅给源码中的绑定读写信号，不把静态信号冒充动态功能/安全成绩。"""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return {'status': 'unmeasured', 'reason': 'code_not_parseable'}
    loads = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Load)]
    writes = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, (ast.Store, ast.Del))]
    mutations = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and isinstance(n.func.value, ast.Name) and n.func.value.id == name
                 and n.func.attr in ('clear', 'update', 'pop', 'popitem', 'setdefault', 'append', 'extend', 'remove')]
    subscripts = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Subscript) and isinstance(n.ctx, (ast.Store, ast.Del))
                  and isinstance(n.value, ast.Name) and n.value.id == name]
    return {'status': 'violated' if writes or mutations or subscripts else 'consistent' if loads else 'unmeasured',
            'read_lines': loads, 'write_lines': writes, 'mutation_lines': mutations + subscripts,
            'scope': 'static direct-name signal; aliases/dynamic effects require code review'}


def report(run):
    """复算同题配对、缺测、采用与物理成本；原始行不修改，后验两题不作泛化。"""
    p = read(run / 'protocol.json')
    rows = [read(path) for path in sorted((run / 'task_rows').glob('*.json'))]
    result = {'protocol': VERSION, 'planned_P7': 16, 'completed_P7': len(rows),
              'arms': {}, 'paired': {}, 'Q_updates': 0, 'card_generation': 0,
              'posthoc_sample': True, 'automatic_expansion': False}
    mechanism = []
    for arm in 'ABCD':
        items = [r for r in rows if r['binding_arm'] == arm]
        stats = {'completed': len(items)}
        for label, index in [('first', 0), ('final', -1)]:
            attempts = [r['attempts'][index] for r in items]
            stats[label] = {k: sum(bool(a.get('measured')) and bool(a.get(k)) for a in attempts)
                            for k in ('functional', 'security', 'joint')}
            stats[label]['measured'] = sum(bool(a.get('measured')) for a in attempts)
        stats['selected_occurrences'] = sum(len(a.get('generation', {}).get('retrieved_cards') or []) for r in items for a in r['attempts'])
        stats['adopted_occurrences'] = sum(len(a.get('generation', {}).get('cards') or []) for r in items for a in r['attempts'])
        stats['rows_with_adoption'] = sum(any(a.get('generation', {}).get('cards') for a in r['attempts']) for r in items)
        result['arms'][arm] = stats
    for row in rows:
        name = p['public_binding_names'][row['task_id']]
        mechanism.append({'cell_id': row['cell_id'], 'task_id': row['task_id'], 'arm': row['binding_arm'],
            'repeat': row['repeat'], 'attempts': [{
                'attempt': a['attempt'], 'measured': a.get('measured'), 'F': a.get('functional'),
                'S': a.get('security'), 'Joint': a.get('joint'), 'binding': binding_signal(a.get('code', ''), name),
                'selected_ids': [c['invariant_id'] for c in a.get('generation', {}).get('retrieved_cards') or []],
                'adopted_ids': [c['invariant_id'] for c in a.get('generation', {}).get('cards') or []],
                'stages': a.get('generation', {}).get('stages')}
                for a in row['attempts']]})
    lookup = {(r['task_id'], r['repeat'], r['binding_arm']): r for r in rows}
    for treated, base in [('C', 'A'), ('D', 'B'), ('D', 'C'), ('B', 'A')]:
        pairs = []
        for tid in p['task_ids']:
            for repeat in (1, 2):
                if (tid, repeat, base) not in lookup or (tid, repeat, treated) not in lookup:
                    continue
                a, b = [lookup[tid, repeat, arm]['attempts'][-1] for arm in (base, treated)]
                pairs.append({'task_id': tid, 'repeat': repeat,
                    'both_measured': bool(a.get('measured') and b.get('measured')),
                    'baseline_joint': bool(a.get('joint')), 'treated_joint': bool(b.get('joint')),
                    'delta': int(bool(b.get('joint'))) - int(bool(a.get('joint'))),
                    'new_S_loss': bool(a.get('measured') and b.get('measured') and a.get('security') and not b.get('security'))})
        result['paired'][treated + '-' + base] = {'pairs': pairs, 'net_joint': sum(x['delta'] for x in pairs),
            'rescues': sum(x['delta'] == 1 and x['both_measured'] for x in pairs),
            'losses': sum(x['delta'] == -1 and x['both_measured'] for x in pairs),
            'both_measured': sum(x['both_measured'] for x in pairs), 'new_S_losses': sum(x['new_S_loss'] for x in pairs)}
    usage, models, physical, known = Counter(), Counter(), 0, 0
    for path in (run / 'wire').glob('*.request.json'):
        physical += 1
        model = read(path)['body']['model']
        models[model] += 1
        raw = path.with_name(path.name.replace('.request.json', '.response.raw'))
        value = usage_from_bytes(raw.read_bytes(), model) if raw.exists() else None
        if isinstance(value, dict):
            known += 1
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                usage[key] += int(value.get(key) or 0)
    result['cost'] = {'physical_HTTP': physical, 'HTTP_with_usage': known, 'unknown_usage_HTTP': physical - known,
                      'known_usage': dict(usage), 'models': dict(models), 'currency_cost': None}
    result['cost']['logical_groups'] = {}
    for group in ('shared_initial', 'shared_selection', 'A', 'B', 'C', 'D', 'embedding'):
        folders = [d for d in (run / 'journals').iterdir() if d.name.startswith(group + '_') or d.name.endswith('_' + group) or d.name == group]
        total = Counter()
        for folder in folders:
            for path in (folder / 'requests').glob('*.json'):
                record = read(path)
                total['requests'] += 1
                tokens = (record.get('response') or {}).get('usage') or {}
                total['total_tokens'] += int(tokens.get('total_tokens') or 0)
        result['cost']['logical_groups'][group] = dict(total)
    gate = len(rows) == 16
    for treated, base in [('C', 'A'), ('D', 'B')]:
        paired = result['paired'][treated + '-' + base]
        gate &= paired['both_measured'] == 4 and paired['net_joint'] >= 2 and paired['new_S_losses'] == 0
        for tid in p['task_ids']:
            gate &= any(m['task_id'] == tid and m['arm'] == treated and m['attempts'][-1]['Joint']
                        and m['attempts'][-1]['binding']['status'] == 'consistent' for m in mechanism)
    result['mechanism_gate_static_preliminary'] = bool(gate)
    result['mechanism_gate_requires_final_code_review'] = True
    write(run / 'summary.json', result)
    write(run / 'mechanism_rows.json', mechanism)
    curated = ROOT / 'results/curated/cle_v41_public_binding_20261025'
    write(curated / 'summary.json', result)
    write(curated / 'mechanism_rows.json', mechanism)
    lines = ['# v4.1公开绑定提示：两题四臂诊断实验', '',
        '本实验使用两道事后已知故障题1322/1409；固定旧1939卡、Q不参与/不更新，原P7最多三卡和一次修复。只改复析、规划、生成中的公开绑定提示，不改变初析、检索输入、验证反馈和末次交付。', '',
        '| 臂 | 已完成/4 | 首次Joint | 最终F | 最终S | 最终Joint | 可测 | 采用张次 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for arm, item in result['arms'].items():
        final = item['final']
        lines.append(f"| {arm} | {item['completed']}/4 | {item['first']['joint']} | {final['functional']} | {final['security']} | {final['joint']}/4 | {final['measured']} | {item['adopted_occurrences']} |")
    lines += ['', 'A空卡；B原卡；C空卡+保护；D原卡+保护。全部planned分母保留；缺测不冒充完整测量失败。', '',
              '| 配对 | 净Joint | 共同可测 | 已测救回/损失 | 新安全退化 |', '|---|---:|---:|---:|---:|']
    for name, pair in result['paired'].items():
        lines.append(f"| {name} | {pair['net_joint']} | {pair['both_measured']}/4 | {pair['rescues']}/{pair['losses']} | {pair['new_S_losses']} |")
    lines += ['', '逐题代码与采用/写入链见mechanism_rows.json及task_rows；初步静态机制门：' + str(bool(gate)) +
              '。此结果仍需查看实际代码，不把静态无直接写入等同普遍契约正确。', '',
              '已知Token：' + str(usage['total_tokens']) + '；物理HTTP：' + str(physical) + '；未知用量HTTP：' + str(physical - known) + '。单价未知，实付不填。', '',
              '工程通过、提示机制信号和经验额外收益分别报告；两题为事后挑出的故障诊断，即使过门也不支持全PLT/Base/Plus泛化。Q、分类器、24题验证和全量不自动启动。']
    (ROOT / 'docs/CLE_v41公开绑定保护四臂实验报告_20261025.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'worker', 'replay', 'report'])
    parser.add_argument('--run-root', type=Path, default=RUN)
    args = parser.parse_args()
    run = args.run_root.resolve()
    if args.action == 'prepare':
        prepare(run)
    elif args.action == 'report':
        report(run)
    else:
        worker(run, replay=args.action == 'replay')


if __name__ == '__main__':
    main()

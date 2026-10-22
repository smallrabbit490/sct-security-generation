"""两次训练侧Q参与学习，再冻结进行原P7全D_gate四臂；不修改旧产物。"""
from __future__ import annotations

import argparse
import ast
import copy
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from time import perf_counter

from methods.cle_ablation import run_memory_q_full_gate_v4 as previous_gate
from methods.cle_ablation.run_memory_q import record_result, shuffled_memory
from methods.cle_ablation.run_memory_q_dinit import body
from methods.cle_ablation.run_memory_q_dinit_coverage import trace_of, FIELDS
from methods.cle_ablation.run_memory_q_gate_q0 import frozen_runner
from methods.cle_ablation.run_memory_q_unlimited import inputs
from methods.cle_ablation.runner import ROOT, load_memory
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.cost_tracker import CostTracker
from methods.sct_trajectory.memory_q import rank_candidates, reward_from_evidence, update_q
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import file_digest
from methods.sct_trajectory.run_memory_q_study import _write_memory, prepare_initial_analysis

PROTOCOL = 'cle-q-online-dinit-grow-cap3-v1'
CONFIG = ROOT / 'configs/cle_q_online_20261020'
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1'
CURATED = ROOT / 'results/curated/cle_q_online_20261020'
BASE = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_card_cap_v2'
QUAL = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/coverage_learning_v2/qualification.after_dependencies.json'
REPAIR = ROOT / 'configs/cle_dgrow_url_repair_20261019/repaired_tasks.json'
CONTROLS = ROOT / 'results/curated/cle_dgrow_url_repair_20261019/qualification.json'
ORDER = {'Q0': None, 'Q1': 'similarity', 'Q2': 'q', 'Q3': 'q'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    if not Path(path).exists():
        return []
    with Path(path).open(encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def append(path, item):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='') as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + '\n')


def dump_csv(path, items):
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)


def configure(stage):
    """训练沿用已修复的420k长度许可；门控保留原180k，保证旧对照实际输入不变。"""
    from methods.sct_trajectory import semantic_retrieval
    semantic_retrieval.MAX_SELECTOR_CHARS = 180000 if stage == 'D_gate' else 420000
    command = r'C:\Program Files\Git\usr\bin'
    if command not in os.environ['PATH'].split(os.pathsep):
        os.environ['PATH'] = command + os.pathsep + os.environ['PATH']


def credit(row, bank, eligible=True):
    """仅D_init/D_grow逐题授信；题内Q固定，完成原P7后按c0/c1顺序更新采用卡。"""
    if row['pool'] not in ('D_init', 'D_grow'):
        raise ValueError('evaluation_cannot_update_Q')
    mapping = {n.invariant_id: n for n in bank}
    events = []
    for attempt in row['attempts']:
        generation = attempt.get('generation', {})
        selected = [c['invariant_id'] for c in generation.get('retrieved_cards', [])]
        adopted = list(dict.fromkeys(c['invariant_id'] for c in generation.get('cards', [])))
        if len(selected) > 3 or not set(adopted) <= set(selected):
            raise ValueError('native_three_card_adoption_contract')
        reward = reward_from_evidence(attempt.get('validation', {}).get('evidence', {}), code=attempt.get('code', ''))
        if not generation.get('workflow_completed') or not attempt.get('measured') or row.get('shared_initial_error'):
            reward = None
        for identifier in adopted or [None]:
            reason = ('no_adopted_experiences' if identifier is None else
                      'source_task_reward_ineligible' if not eligible else
                      'incomplete_or_technical_measurement' if reward is None else None)
            node = mapping[identifier] if identifier else None
            before = node.q_value if node else None
            if reason is None:
                node.q_value = update_q(before, reward, .3)
                node.q_visits += 1
            events.append({'task_id': row['task_id'], 'pool': row['pool'], 'family_id': row['family_id'],
                'attempt': attempt['attempt'], 'invariant_id': identifier, 'reward': reward,
                'q_before': before, 'q_after': node.q_value if node else None,
                'q_visits': node.q_visits if node else None, 'credited': reason is None,
                'skip_reason': reason, 'protocol': PROTOCOL})
    return events


def mechanism(row, bank):
    """用本题实际读取的Q复算同查询顺序；数值前三位不是模型最后选的三卡。"""
    q = {n.invariant_id: n.q_value for n in bank}
    visits = {n.invariant_id: n.q_visits for n in bank}
    result = []
    for attempt in row['attempts']:
        trace = trace_of(attempt)
        scores = trace.get('scores', [])
        if not scores:
            continue
        sim = [r['id'] for r in rank_candidates(scores, q, delta=-1, lambda_q=0, limit=None)]
        ranked = [r['id'] for r in rank_candidates(scores, q, delta=-1, lambda_q=.5, limit=None)]
        if trace.get('candidate_order') == 'q' and trace.get('presented_candidate_ids') != ranked:
            raise ValueError('Q_order_not_actual_read_state')
        selected = [c['invariant_id'] for c in attempt.get('generation', {}).get('retrieved_cards', [])]
        adopted = [c['invariant_id'] for c in attempt.get('generation', {}).get('cards', [])]
        result.append({'task_id': row['task_id'], 'pool': row['pool'], 'arm': row['arm'],
            'attempt': attempt['attempt'], 'candidate_count': len(scores),
            'learned_candidates': sum(visits[s['id']] > 0 for s in scores),
            'Q_order_changed': ranked != sim, 'numeric_top3_members_changed': set(ranked[:3]) != set(sim[:3]),
            'selected': selected, 'adopted': adopted,
            'selected_Q': [q[i] for i in selected], 'selected_visits': [visits[i] for i in selected],
            'functional': attempt.get('functional'), 'security': attempt.get('security'), 'joint': attempt.get('joint')})
    return result


def inspect_row(row):
    """验证原P7早停、末次交付与三张限制；模型解析失败保留为真实结果。"""
    attempts = row['attempts']
    assert 1 <= len(attempts) <= 2 and row['final'] == attempts[-1]
    assert not (len(attempts) == 2 and attempts[0].get('joint'))
    for attempt in attempts:
        g = attempt.get('generation', {})
        selected = {c['invariant_id'] for c in g.get('retrieved_cards', [])}
        adopted = {c['invariant_id'] for c in g.get('cards', [])}
        assert len(selected) <= 3 and adopted <= selected
        trace = trace_of(attempt)
        if trace.get('status') == 'completed':
            assert trace.get('selection_limit') == 3


def reuse_certificate(bank):
    """旧Q0/Q1不读取Q：核验固定正文、P7及实际依赖；新增覆盖分支不参与这两臂。"""
    oldmeta = read(previous_gate.OUT / 'run_metadata.json')
    oldbank = load_memory(previous_gate.BANK)
    assert body(bank) == body(oldbank)
    approved = {'methods/sct_trajectory/semantic_retrieval.py', 'methods/sct_trajectory/memory_q.py'}
    differences = []
    for name, expected in oldmeta['source_identity'].items():
        normalized = name.replace('\\', '/')
        current = ROOT / name
        if file_digest(current) == expected:
            continue
        assert normalized in approved, 'affected_baseline_dependency:' + normalized
        prior = previous_gate.OUT / 'source_snapshot' / name
        oldtext, newtext = prior.read_text(encoding='utf-8-sig'), current.read_text(encoding='utf-8-sig')
        if normalized.endswith('memory_q.py'):
            def without_coverage(text):
                tree = ast.parse(text)
                tree.body = [n for n in tree.body if not isinstance(n, ast.FunctionDef) or n.name != 'rank_coverage_candidates']
                return ast.dump(tree)
            assert without_coverage(oldtext) == without_coverage(newtext)
        else:
            oldblock = '''            from .memory_q import rank_candidates
            if candidate_order not in ("similarity", "q"):
                raise ValueError("unknown_candidate_order")
            ranked = rank_candidates(trace['scores'], {i: n.q_value for i, (n, _) in eligible.items()},
                                     delta=delta, lambda_q=0 if candidate_order == 'similarity' else lambda_q,
                                     limit=None)'''
            newblock = '''            from .memory_q import rank_candidates, rank_coverage_candidates
            if candidate_order not in ("similarity", "q", "coverage"):
                raise ValueError("unknown_candidate_order")
            if candidate_order == 'coverage':
                # 新学习消融只改变呈现顺序；原LLM仍负责最多三张选择和后续采用。
                ranked = rank_coverage_candidates(trace['scores'], {i:n.q_visits for i,(n,_) in eligible.items()}, delta=delta)
            else:
                ranked = rank_candidates(trace['scores'], {i: n.q_value for i, (n, _) in eligible.items()},
                                         delta=delta, lambda_q=0 if candidate_order == 'similarity' else lambda_q,
                                         limit=None)'''
            assert oldblock in oldtext and newblock in newtext
            assert oldtext.replace(oldblock, newblock) == newtext
        differences.append({'path': normalized, 'change': 'coverage-only branch unused by Q0/Q1'})
    baseline = [r for r in previous_gate.read_rows(previous_gate.OUT / 'rows.jsonl') if r['arm'] in ('Q0', 'Q1')]
    assert len(baseline) == 596 and len({(r['task_id'], r['arm']) for r in baseline}) == 596
    import yaml
    assert yaml.__version__ == '6.0.3'
    return {'reusable_rows': 596, 'arms': ['Q0', 'Q1'], 'old_source': str(previous_gate.OUT.relative_to(ROOT)),
        'same_body_lifecycle': True, 'same_frozen_P7': True, 'same_data_initials_selector_budget_validation': True,
        'approved_inactive_changes': differences, 'Q_value_and_visits_not_read_by_these_arms': True,
        'known_limitation': 'historical baseline timing retained; model backend nondeterminism not removed'}


def prepare():
    if (OUT / 'run_metadata.json').exists():
        return verify()
    assert shutil.disk_usage(ROOT.anchor).free > 5 * 1024**3
    bank = load_memory(BASE / 'Lall/all_feedback/frozen/m_star_q.jsonl')
    assert len(bank) == 1939 and sum(n.q_visits > 0 for n in bank) == 926
    _, tasks, pools = inputs()
    init_tasks = read(BASE / 'tasks.json')
    grow_tasks = {i: copy.deepcopy(tasks[i]) for i in pools['D_grow']}
    for task in read(REPAIR):
        grow_tasks[str(task['index'])] = task
    eligible = {x['task_id'] for x in read(QUAL)['tasks'] if x['reward_eligible']}
    eligible |= {x['task_id'] for x in read(CONTROLS) if x['reward_eligible_new_protocol']}
    assert len(eligible) == 228
    init_ids = read(BASE / 'manifest.json')['learning']
    grow_ids = list(map(str, read(ROOT / 'configs/cle_memory_q_full_dgrow_20261016/manifest.json')['learning']))
    gate_ids = [x['task_id'] for x in read(previous_gate.OUT / 'manifest.json')['tasks']]
    assert len(init_ids) == 303 and len(grow_ids) == 273 and len(gate_ids) == 298
    assert set(init_ids) == set(pools['D_init']) and set(grow_ids) == set(pools['D_grow'])
    families = [{tasks[i]['family_id'] for i in ids} for ids in (init_ids, grow_ids, gate_ids)]
    assert not families[0] & families[1] and not families[0] & families[2] and not families[1] & families[2]
    certificate = reuse_certificate(bank)
    OUT.mkdir(parents=True, exist_ok=False)
    CONFIG.mkdir(parents=True, exist_ok=True)
    CURATED.mkdir(parents=True, exist_ok=True)
    protocol = {'protocol': PROTOCOL, 'stage_order': ['D_init', 'D_grow', 'D_gate'],
        'initial_visited': 926, 'card_count': 1939, 'model': 'deepseek-v3.2', 'thinking': 'disabled',
        'temperature': 0, 'max_tokens': 4096, 'selector_max_tokens': 256,
        'embedding_model': 'text-embedding-3-large', 'delta': -1, 'lambda_q': .5, 'alpha': .3,
        'candidate_order_training': 'q', 'max_experiences': 3, 'max_code_attempts': 2,
        'learning_workers': 1, 'update_boundary': 'after each P7 task, c0 then c1; next task sees updated Q',
        'new_cards': False, 'body_lifecycle_changes': False, 'performance_continuation_gate': False,
        'D_init_tasks': 303, 'D_grow_tasks': 273, 'D_grow_reward_eligible': 228,
        'D_gate_tasks': 298, 'D_gate_new_arms': ['Q2', 'Q3'], 'D_gate_reused_arms': ['Q0', 'Q1'],
        'D_gate_Q_updates': False, 'shuffle_scope': 'cwe', 'shuffle_seed': 20261015,
        'training_selector_prompt_chars': 420000, 'gate_selector_prompt_chars': 180000,
        'request_timeout_seconds': 120, 'gate_request_timeout_seconds': 60,
        'phase_token_stop': {'D_init': 35000000, 'D_grow': 35000000, 'D_gate': 65000000},
        'phase_logical_call_stop': {'D_init': 5000, 'D_grow': 5000, 'D_gate': 10000},
        'paid_execution_authorized': True, 'Base_Plus': False, 'actual_bill_CNY': None}
    manifest = {'protocol': PROTOCOL, 'D_init': init_ids, 'D_grow': grow_ids, 'D_gate': gate_ids,
        'D_grow_reward_eligible': sorted(eligible, key=int),
        'D_grow_reward_ineligible': [i for i in grow_ids if i not in eligible]}
    write(CONFIG / 'protocol.json', protocol); write(CONFIG / 'manifest.json', manifest)
    write(OUT / 'protocol.json', protocol); write(OUT / 'manifest.json', manifest)
    write(OUT / 'tasks_D_init.json', init_tasks); write(OUT / 'tasks_D_grow.json', grow_tasks)
    write(OUT / 'tasks_D_gate.json', {i: tasks[i] for i in gate_ids})
    write(OUT / 'baseline_reuse_certificate.json', certificate)
    _write_memory(OUT / 'input_memory.jsonl', bank)
    # 共用初析只在公开契约不变时复用；不复用任何训练阶段的后续生成。
    for i in init_ids:
        initial = read(BASE / 'initials' / (i + '.json'))
        write(OUT / 'D_init/initials' / (i + '.json'), initial)
    shutil.copy2(previous_gate.OUT / 'shared_initial.jsonl', OUT / 'shared_gate_initial.jsonl')
    shutil.copy2(previous_gate.OUT / 'reference_preflight.json', OUT / 'gate_preflight.json')
    shutil.copy2(previous_gate.OUT / 'schedule.json', OUT / 'gate_schedule.json')
    sources = [Path(__file__), CONFIG / 'protocol.json', CONFIG / 'manifest.json',
        BASE / 'Lall/all_feedback/frozen/m_star_q.jsonl', BASE / 'tasks.json', QUAL, REPAIR, CONTROLS,
        previous_gate.OUT / 'rows.jsonl', previous_gate.OUT / 'shared_initial.jsonl',
        Path(inspect.getfile(frozen_runner()))]
    sources += [ROOT / f for f in ('methods/sct_trajectory/semantic_retrieval.py',
        'methods/sct_trajectory/retriever.py', 'methods/sct_trajectory/context_pipeline.py',
        'methods/sct_trajectory/memory_q.py', 'methods/sct_trajectory/run_closed_loop.py')]
    identity = {str(p.relative_to(ROOT)): file_digest(p) for p in sources}
    for p in sources:
        if p.suffix == '.py':
            target = OUT / 'source_snapshot' / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)
    write(OUT / 'run_metadata.json', {'protocol': PROTOCOL, 'status': 'prepared', 'identity': identity,
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], text=True).strip(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'python': os.sys.executable, 'completed_stages': [], 'baseline_reuse': certificate})
    print(json.dumps({'prepared': True, 'tasks': [303, 273, 298], 'baseline_reuse': 596}), flush=True)


def verify():
    meta = read(OUT / 'run_metadata.json')
    for name, digest in meta['identity'].items():
        assert file_digest(ROOT / name) == digest, 'locked_source_or_input_changed:' + name
    return meta


class Requests:
    """复用原请求器；按逻辑请求持久化成本，异常不丢付费记录、不自动重跑题目。"""
    def __init__(self, stage, workers=1):
        from methods.sct_trajectory.run_closed_loop import _requester
        protocol = read(OUT / 'protocol.json')
        self.stage, self.protocol = stage, protocol
        self.lock, self.stopped = threading.Lock(), threading.Event()
        prior = [read(p) for p in (OUT / stage / 'requests').glob('*.json')]
        assert not any(p['status'] == 'started' for p in prior), 'unfinished_request_requires_reconciliation'
        self.count, self.tokens = len(prior), sum(p.get('total_tokens', 0) for p in prior)
        self.native = _requester('deepseek-v3.2', 60 if stage == 'D_gate' else 120,
            max_tokens=4096, max_inflight=workers, thinking='disabled')

    def bind(self, identifier, arm):
        tracker = CostTracker('deepseek-v3.2'); tracker.set_stage(arm)
        def request(prompt):
            with self.lock:
                if self.stopped.is_set():
                    raise RuntimeError('paid_execution_stopped')
                if self.count >= self.protocol['phase_logical_call_stop'][self.stage] or self.tokens >= self.protocol['phase_token_stop'][self.stage]:
                    self.stopped.set(); raise RuntimeError('phase_budget_stop')
                self.count += 1
                path = OUT / self.stage / 'requests' / f'{self.count:05d}.json'
                event = {'task_id': identifier, 'arm': arm, 'stage': self.stage, 'status': 'started'}
                write(path, event)
            started = perf_counter()
            try:
                response = self.native(prompt)
            except Exception as exc:
                tracker.record_error('pipeline'); self.stopped.set()
                write(path, {**event, 'status': 'error', 'error_type': type(exc).__name__,
                    'diagnostics': getattr(exc, 'safe_diagnostics', []), 'seconds': perf_counter() - started})
                raise
            tracker.record('pipeline', response)
            usage = {k: int(v) for k, v in (response.get('usage') or {}).items()
                     if k in ('prompt_tokens', 'completion_tokens', 'total_tokens') and isinstance(v, int)}
            with self.lock:
                self.tokens += usage.get('total_tokens', 0)
                write(path, {**event, 'status': 'completed', **usage, 'response_model': response.get('model'),
                    'seconds': perf_counter() - started})
            return response
        return request, tracker


def embedding():
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.run_closed_loop import load_key
    return EmbeddingClient(model='text-embedding-3-large', key_loader=load_key,
        cache_path=ROOT / 'translation_work/cache/embeddings/cle.sqlite3', timeout=120)


def study_rows(stage):
    manifest = read(OUT / 'manifest.json')
    return [read(p) for i in manifest[stage] if (p := OUT / stage / 'task_rows' / (i + '.json')).exists()]


def replay(stage):
    """从不变起点按题单重放已保存反馈；恢复时不重复授信，下一题获得同一Q状态。"""
    source = OUT / ('input_memory.jsonl' if stage == 'D_init' else 'D_init/frozen/m_star_q.jsonl')
    bank = load_memory(source)
    manifest = read(OUT / 'manifest.json'); eligible = set(manifest['D_grow_reward_eligible'])
    events, records = [], study_rows(stage)
    assert [r['task_id'] for r in records] == manifest[stage][:len(records)], 'non_prefix_online_history'
    for row in records:
        events.extend(credit(row, bank, stage == 'D_init' or row['task_id'] in eligible))
    return bank, events, records


def learning_summary(stage, bank, events, records):
    source = load_memory(OUT / ('input_memory.jsonl' if stage == 'D_init' else 'D_init/frozen/m_star_q.jsonl'))
    assert body(bank) == body(source)
    root = OUT / stage
    _write_memory(root / 'frozen/m_star_q.jsonl', bank)
    with (root / 'memory_q_events.jsonl').open('w', encoding='utf-8') as stream:
        for e in events:
            stream.write(json.dumps(e, ensure_ascii=False) + '\n')
    values = {k: sum(bool(r['final'].get(k)) for r in records) for k in ('functional', 'security', 'joint', 'measured')}
    summary = {'protocol': PROTOCOL, 'pool': stage, 'planned': len(read(OUT / 'manifest.json')[stage]),
        'executed': len(records), 'final': values, 'visited_before': sum(n.q_visits > 0 for n in source),
        'visited_after': sum(n.q_visits > 0 for n in bank), 'coverage': sum(n.q_visits > 0 for n in bank) / len(bank),
        'valid_updates': sum(e['credited'] for e in events),
        'positive_updates': sum(e['credited'] and e['reward'] == 1 for e in events),
        'negative_updates': sum(e['credited'] and e['reward'] == -1 for e in events),
        'attempts': sum(len(r['attempts']) for r in records), 'new_cards': False,
        'cost': {k: sum(r['accounting']['total'][k] for r in records) for k in FIELDS}}
    write(root / 'summary.json', summary); write(CURATED / (stage + '_summary.json'), summary)
    dump_csv(CURATED / (stage + '_scores.csv'), [{'task_id': r['task_id'], 'family_id': r['family_id'],
        **{k: r['final'].get(k) for k in ('functional', 'security', 'joint', 'measured')},
        'attempts': len(r['attempts']), 'reward_eligible': r['reward_eligible']} for r in records])
    return summary


def learn(stage, limit=None):
    meta = verify(); configure(stage)
    manifest = read(OUT / 'manifest.json')
    if stage == 'D_grow':
        assert read(OUT / 'D_init/summary.json')['executed'] == 303
    bank, events, records = replay(stage)
    tasks = read(OUT / ('tasks_' + stage + '.json'))
    wanted = manifest[stage][:limit] if limit else manifest[stage]
    eligible = set(manifest['D_grow_reward_eligible'])
    api, emb, p7 = Requests(stage), embedding(), frozen_runner()
    meta['status'] = 'running_' + stage; write(OUT / 'run_metadata.json', meta)
    for identifier in wanted[len(records):]:
        initial_path = OUT / stage / 'initials' / (identifier + '.json')
        if not initial_path.exists():
            request, tracker = api.bind(identifier, 'initial')
            initial = prepare_initial_analysis({'task_description': p7.plt_contract(tasks[identifier])}, request)
            write(initial_path, {'task_id': identifier, 'initial_analysis': initial,
                'error_type': None, 'accounting': tracker.snapshot()['total'], 'reused_initial': False})
        initial = read(initial_path)
        before = [(n.q_value, n.q_visits) for n in bank]
        request, tracker = api.bind(identifier, 'Q2')
        started = perf_counter()
        row = p7.run_one('PLT', tasks[identifier], 'P7', request, {'full': bank}, emb,
            retrieval_mode='semantic_llm', delta=-1, lambda_q=.5, max_experiences=3,
            candidate_order='q', initial_analysis=copy.deepcopy(initial['initial_analysis']))
        record_result(row, tasks[identifier], 'Q2', stage, perf_counter() - started)
        row.update(protocol=PROTOCOL, shared_initial_error=initial.get('error_type'),
            reward_eligible=stage == 'D_init' or identifier in eligible,
            accounting={'total': {k: tracker.snapshot()['total'][k] for k in FIELDS}})
        assert before == [(n.q_value, n.q_visits) for n in bank]
        row['mechanism'] = mechanism(row, bank)
        write(OUT / stage / 'task_rows' / (identifier + '.json'), row)
        append(OUT / stage / 'rows.jsonl', row)
        inspect_row(row)
        events.extend(credit(row, bank, row['reward_eligible'])); records.append(row)
        summary = learning_summary(stage, bank, events, records)
        write(OUT / stage / 'embedding_usage.json', emb.usage)
        print(json.dumps({'stage': stage, 'done': len(records), 'planned': len(manifest[stage]),
            'task': identifier, 'Joint': summary['final']['joint'], 'visited': summary['visited_after'],
            'updates': summary['valid_updates'], 'tokens': api.tokens}), flush=True)
        if api.stopped.is_set():
            meta['status'] = 'technical_stop_' + stage; write(OUT / 'run_metadata.json', meta)
            raise RuntimeError('request_failure_saved_stop_before_next_task')
    if len(records) == len(manifest[stage]):
        if stage not in meta['completed_stages']:
            meta['completed_stages'].append(stage)
        meta['status'] = 'completed_' + stage; write(OUT / 'run_metadata.json', meta)
    return learning_summary(stage, bank, events, records)


def effective_gate_rows():
    original = previous_gate.read_rows(previous_gate.OUT / 'rows.jsonl')
    baseline = [dict(r, result_reused=True, source_protocol=r['protocol']) for r in original if r['arm'] in ('Q0', 'Q1')]
    return baseline + [read(p) for p in (OUT / 'D_gate/task_rows').glob('*/*.json')]


def gate(workers=8):
    meta = verify(); configure('D_gate')
    assert read(OUT / 'D_grow/summary.json')['executed'] == 273
    bank = load_memory(OUT / 'D_grow/frozen/m_star_q.jsonl')
    assert body(bank) == body(load_memory(OUT / 'input_memory.jsonl'))
    placebo_path = OUT / 'D_gate/shuffled_memory.jsonl'
    if not placebo_path.exists():
        _write_memory(placebo_path, shuffled_memory(bank, 20261015, 'cwe'))
    placebo = load_memory(placebo_path)
    tasks = read(OUT / 'tasks_D_gate.json')
    shared = {r['task_id']: r for r in rows(OUT / 'shared_gate_initial.jsonl')}
    api, emb, p7 = Requests('D_gate', workers), embedding(), frozen_runner()
    before = [[n.to_dict() for n in b] for b in (bank, placebo)]
    done = {(r['task_id'], r['arm']) for r in effective_gate_rows()}
    jobs = [(r['task_id'], arm) for r in read(OUT / 'gate_schedule.json') for arm in r['arms']
            if arm in ('Q2', 'Q3') and (r['task_id'], arm) not in done]
    def job(identifier, arm):
        nodes = placebo if arm == 'Q3' else bank
        request, tracker = api.bind(identifier, arm)
        started = perf_counter()
        row = p7.run_one('PLT', tasks[identifier], 'P7', request, {'full': nodes}, emb,
            retrieval_mode='semantic_llm', delta=-1, lambda_q=.5, max_experiences=3,
            candidate_order='q', initial_analysis=copy.deepcopy(shared[identifier]['initial_analysis']))
        record_result(row, tasks[identifier], arm, 'D_gate', perf_counter() - started)
        row.update(protocol=PROTOCOL, result_reused=False, candidate_order='q',
            accounting={'total': {k: tracker.snapshot()['total'][k] for k in FIELDS}})
        row['mechanism'] = mechanism(row, nodes)
        write(OUT / 'D_gate/task_rows' / identifier / (arm + '.json'), row)
        return row
    meta['status'] = 'running_D_gate'; write(OUT / 'run_metadata.json', meta)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for offset in range(0, len(jobs), workers):
            if api.stopped.is_set():
                raise RuntimeError('gate_request_failure_stop')
            futures = [pool.submit(job, *j) for j in jobs[offset:offset + workers]]
            for future in as_completed(futures):
                row = future.result(); append(OUT / 'D_gate/new_rows.jsonl', row); inspect_row(row)
            write(OUT / 'D_gate/embedding_usage.json', emb.usage)
            current = effective_gate_rows()
            print(json.dumps({'stage': 'D_gate', 'rows': len(current), 'planned': 1192,
                'Joint': {a: sum(r['final']['joint'] for r in current if r['arm'] == a) for a in ORDER},
                'new_tokens': api.tokens}), flush=True)
    assert before == [[n.to_dict() for n in b] for b in (bank, placebo)]
    current = effective_gate_rows()
    if len(current) == 1192:
        meta['completed_stages'].append('D_gate'); meta['status'] = 'completed_full'
        write(OUT / 'run_metadata.json', meta)
    return report()


def report():
    """按原项目分母、配对及题族统计输出；历史对照成本与本轮新增消耗分别列。"""
    verify()
    current = effective_gate_rows()
    assert len(current) == len({(r['task_id'], r['arm']) for r in current})
    summary = summarize(current, 'Q0')
    summary.update(protocol=PROTOCOL, planned_tasks=298, expected_rows=1192, rows=len(current),
        Q_updates_D_gate=0, reused_rows=596, new_rows=len(current) - 596,
        independent_final_test=False, actual_bill_CNY=None)
    if len(current) == 1192:
        spec = importlib.util.spec_from_file_location('_online_paired', ROOT / 'configs/cle_memory_q_full_gate_cap3_20261019/analyze.py')
        analysis = importlib.util.module_from_spec(spec); spec.loader.exec_module(analysis)
        paired = [analysis.paired(current, 'Q2', a) for a in ('Q0', 'Q1', 'Q3')]
        analysis.holm(paired); summary['primary_paired'] = paired
        summary['supports_stable_Q_benefit'] = all(p['difference'] > 0 and p['p_holm'] <= .05 for p in paired)
    # 同查询首轮候选应一致；历史技术失败单独列出，不伪造共同候选。
    first, issues = {}, []
    for r in current:
        trace = trace_of(r['attempts'][0])
        if trace.get('status') != 'completed':
            continue
        signature = (trace['query_hash'], trace['candidate_ids'], trace['scores'])
        if r['task_id'] in first and first[r['task_id']] != signature:
            issues.append({'task_id': r['task_id'], 'arm': r['arm'], 'issue': 'first_candidate_mismatch'})
        first[r['task_id']] = signature
    summary['first_candidate_issues'] = issues
    write(OUT / 'D_gate/summary.json', summary); write(CURATED / 'gate_summary.json', summary)
    with (OUT / 'D_gate/rows.jsonl').open('w', encoding='utf-8') as stream:
        for r in current:
            stream.write(json.dumps(r, ensure_ascii=False) + '\n')
    dump_csv(CURATED / 'gate_scores.csv', [{'task_id': r['task_id'], 'family_id': r['family_id'], 'arm': r['arm'],
        **{k: r['final'].get(k) for k in ('functional', 'security', 'joint', 'measured')},
        'result_reused': r['result_reused']} for r in current])
    cost = {}
    for stage in ('D_init', 'D_grow', 'D_gate'):
        req = [read(p) for p in (OUT / stage / 'requests').glob('*.json')]
        cost[stage] = {'logical_calls': len(req), 'completed': sum(r['status'] == 'completed' for r in req),
            'errors': sum(r['status'] == 'error' for r in req),
            **{k: sum(r.get(k, 0) for r in req) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}}
    cost['actual_bill_CNY'] = None; cost['historical_reused_cost_charged_again'] = False
    write(CURATED / 'new_cost.json', cost)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'D_init', 'D_grow', 'D_gate', 'all', 'report'))
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command in ('D_init', 'D_grow'):
        learn(args.command, args.limit)
    elif args.command == 'D_gate':
        gate()
    elif args.command == 'report':
        report()
    else:
        learn('D_init'); learn('D_grow'); gate()


if __name__ == '__main__':
    main()

"""D_init v3：原P7的L0/L1等预算覆盖学习，按2/12/60/296阶段门执行。

复用实际采用授信与原验证器，固定经验正文；只写独立运行区，不读取D_gate结果。
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import threading
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from configs.cle_dgrow_url_q_learning_20261020.run import trace_of
from configs.cle_dgrow_url_repair_20261019.repair_and_retest import measured, reference
from configs.cle_q_coverage_learning_20261019.qualification import bindings, placeholder_paths
from methods.cle_ablation.run_memory_q import prepare_shared_initial, record_result
from methods.cle_ablation.run_memory_q_dinit import body, credit_rows
from methods.cle_ablation.run_memory_q_unlimited import inputs
from methods.cle_ablation.runner import load_memory, run_one
from methods.sct_trajectory.closed_loop import validate_and_state
from methods.sct_trajectory.cost_tracker import CostTracker
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.semantic_retrieval import EmbeddingClient, card_embedding_text, MAX_CARD_CHARS, _digest

CONFIG = ROOT / 'configs/cle_dinit_q_coverage_design_20261020_v3'
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_q_coverage_v3'
CURATED = ROOT / 'results/curated/cle_dinit_q_coverage_20261020'
PROTOCOL = 'cle-dinit-coverage-cross-family-design-v3'
FIELDS = ('calls', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'cached_tokens', 'usage_missing', 'errors')
STAGES = {'smoke': (2, 'smoke2_two_arms'), 'probe': (12, 'probe12_two_arms'),
          '60': (60, 'winner60_plus_other12'), '296': (296, 'winner296_plus_other12')}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='') as stream:
        for value in values:
            stream.write(json.dumps(value, ensure_ascii=False) + '\n')


def append(path, value):
    with path.open('a', encoding='utf-8', newline='') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def records():
    return [read(p) for p in sorted((OUT / 'task_rows').glob('*/*.json'))]


def setup_environment(protocol):
    command_path = Path(protocol['command_runtime_path'])
    assert (command_path / 'echo.exe').exists() and (command_path / 'cat.exe').exists()
    if str(command_path) not in os.environ['PATH'].split(os.pathsep):
        os.environ['PATH'] = str(command_path) + os.pathsep + os.environ['PATH']


def prepare():
    """冻结新起点、覆盖、名单和运行源码；旧D_init、D_grow及Q文件只读。"""
    if (OUT / 'run_metadata.json').exists():
        return verify()
    if shutil.disk_usage(ROOT.anchor).free < 3 * 1024**3:
        raise RuntimeError('insufficient_disk_space')
    protocol, manifest = read(CONFIG / 'protocol.json'), read(CONFIG / 'manifest.json')
    bank = load_memory(ROOT / protocol['baseline_memory'])
    assert len(bank) == 1939 and sum(n.q_visits > 0 for n in bank) == 436
    _, tasks, pools = inputs()
    overlay = read(ROOT / protocol['data_overlay'])
    for task in overlay:
        identifier = str(task['index'])
        assert task['family_id'] == tasks[identifier]['family_id']
        tasks[identifier] = copy.deepcopy(task)
    ids = manifest['learning']
    assert len(ids) == len(set(ids)) == 296 and set(ids) <= set(map(str, pools['D_init']))
    assert not set(manifest['excluded']) & set(ids)
    families = {pool: {tasks[str(i)]['family_id'] for i in members} for pool, members in pools.items()}
    assert not families['D_init'] & (families['D_grow'] | families['D_gate'])
    OUT.mkdir(parents=True, exist_ok=False)
    CURATED.mkdir(parents=True, exist_ok=True)
    write(OUT / 'protocol.json', protocol)
    write(OUT / 'manifest.json', manifest)
    write(OUT / 'tasks.json', {i: tasks[i] for i in ids})
    write(OUT / 'origins.json', read(ROOT / protocol['origins_source']))
    write(OUT / 'input_family_support.json', read(ROOT / protocol['baseline_family_support']))
    write(OUT / 'training_anchor.json', read(CONFIG / 'training_anchor.json'))
    _write_memory(OUT / 'input_memory.jsonl', bank)
    # 来源完整性和原件保留是本轮已要求的运行身份；不复制原始大归档。
    paths = [CONFIG / 'protocol.json', CONFIG / 'manifest.json', CONFIG / 'training_anchor.json',
             ROOT / protocol['baseline_memory'], ROOT / protocol['baseline_family_support'],
             ROOT / protocol['data_overlay'], ROOT / protocol['public_overlay'], ROOT / protocol['qualification_source'],
             ROOT / protocol['origins_source'], Path(__file__),
             ROOT / 'methods/cle_ablation/runner.py', ROOT / 'methods/cle_ablation/run_memory_q.py',
             ROOT / 'methods/cle_ablation/run_memory_q_dinit.py',
             ROOT / 'methods/sct_trajectory/context_pipeline.py', ROOT / 'methods/sct_trajectory/memory_q.py',
             ROOT / 'methods/sct_trajectory/semantic_retrieval.py', ROOT / 'methods/sct_trajectory/selector_protocol.py',
             ROOT / 'methods/sct_trajectory/run_closed_loop.py', ROOT / 'methods/sct_agent/validation_evidence.py']
    identity = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    for p in paths:
        if p.suffix == '.py':
            target = OUT / 'source_snapshot' / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    write(OUT / 'run_metadata.json', {'protocol': PROTOCOL, 'status': 'prepared', 'identity': identity,
          'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
          'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'python': sys.executable, 'new_Dgate_generation': False, 'segments': []})
    print(json.dumps({'prepared': True, 'tasks': 296, 'baseline_visited': 436}), flush=True)
    return verify()


def verify():
    meta = read(OUT / 'run_metadata.json')
    for name, expected in meta['identity'].items():
        if digest(ROOT / name) != expected:
            raise RuntimeError('locked_input_or_source_changed:' + name)
    return meta


def preflight(ids):
    """拟执行题先做同环境正负对照；既有81题有效回执可复用，不按成绩换题。"""
    protocol = read(OUT / 'protocol.json')
    setup_environment(protocol)
    tasks = read(OUT / 'tasks.json')
    previous = {r['task_id']: r for r in read(ROOT / protocol['qualification_source'])['tasks']}
    pending = [i for i in ids if not (OUT / 'preflight' / (i + '.json')).exists()]

    def check(identifier):
        task, old = tasks[identifier], previous[identifier]
        if old.get('vulnerable_measured') and old.get('reference_measured') and old.get('reward_eligible'):
            item = {**old, 'evidence_source': protocol['qualification_source'], 'reused': True}
        else:
            positive, pos_state = validate_and_state(task, reference(task), timeout=20)
            negative, neg_state = validate_and_state(task, reference(task, False), timeout=20)
            reasons = []
            if not measured(positive) or pos_state != 'A':
                reasons.append('reference_not_joint_or_unmeasured')
            if not measured(negative) or negative['security']['status'] != 'fail':
                reasons.append('vulnerable_not_security_rejected_or_unmeasured')
            if bindings(task)[0] or placeholder_paths(task):
                reasons.append('public_binding_or_placeholder')
            item = {'task_id': identifier, 'family_id': task['family_id'], 'pool': 'D_init',
                    'reward_eligible': not reasons, 'exclusion_reasons': reasons,
                    'positive': positive, 'negative': negative, 'reference_state': pos_state,
                    'vulnerable_state': neg_state, 'reused': False}
        write(OUT / 'preflight' / (identifier + '.json'), item)
        return item

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(check, pending))
    failed = [i for i in ids if not read(OUT / 'preflight' / (i + '.json'))['reward_eligible']]
    return {'passed': not failed, 'planned': len(ids), 'failed': failed, 'newly_checked': len(pending)}


class BudgetStop(RuntimeError):
    pass


class Budget:
    """在真实请求边界计费和停止；逻辑请求逐次持久化，不读取或输出凭据。"""
    def __init__(self, protocol, stage, native):
        self.native, self.lock, self.stopped = native, threading.Lock(), threading.Event()
        self.limit = protocol['budget_cumulative'][STAGES[stage][1]]
        prior = [read(p) for p in (OUT / 'requests').glob('*.json')]
        if any(r['status'] == 'started' for r in prior):
            raise RuntimeError('unfinished_paid_request_requires_reconciliation')
        self.calls = len(prior)
        self.tokens = sum(r.get('total_tokens', 0) for r in prior)
        self.reason = None
        self.stage = stage

    def bind(self, task_id, arm):
        tracker = CostTracker('deepseek-v3.2')
        tracker.set_stage(arm)

        def request(prompt):
            with self.lock:
                if self.stopped.is_set() or self.calls >= self.limit['logical_calls_stop'] or self.tokens >= self.limit['LLM_token_stop']:
                    self.stopped.set()
                    self.reason = self.reason or 'budget_limit'
                    raise BudgetStop(self.reason)
                self.calls += 1
                sequence = self.calls
                event = {'sequence': sequence, 'task_id': task_id, 'arm': arm, 'stage': self.stage, 'status': 'started'}
                path = OUT / 'requests' / f'{sequence:05d}.json'
                write(path, event)
            started = perf_counter()
            try:
                response = self.native(prompt)
            except Exception as exc:
                tracker.record_error('pipeline')
                diagnostics = [{k: v for k, v in d.items() if k in {'category', 'http_status', 'attempt'}}
                               for d in getattr(exc, 'safe_diagnostics', []) if isinstance(d, dict)]
                with self.lock:
                    self.stopped.set()
                    self.reason = 'request_error'
                    write(path, {**event, 'status': 'error', 'error_type': type(exc).__name__,
                                 'safe_diagnostics': diagnostics, 'seconds': perf_counter() - started})
                raise
            tracker.record('pipeline', response)
            usage = response.get('usage') or {}
            values = {k: int(usage[k]) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens') if isinstance(usage.get(k), int)}
            with self.lock:
                self.tokens += values.get('total_tokens', 0)
                if 'total_tokens' not in values:
                    self.stopped.set()
                    self.reason = 'missing_usage'
                write(path, {**event, 'status': 'completed', **values,
                             'response_model': response.get('model'), 'seconds': perf_counter() - started})
            return response
        return request, tracker


class StudyEmbedding(EmbeddingClient):
    """复用现有向量缓存，仅对新增查询付费，独立记录Embedding用量。"""
    def __init__(self, protocol, stage, **kwargs):
        super().__init__(**kwargs)
        self.stage, self.protocol = stage, protocol
        self.request_lock = threading.Lock()
        self.prior_tokens = sum(read(p)['total_tokens'] for p in (OUT / 'embedding_requests').glob('*.json'))
        self.sequence = len(list((OUT / 'embedding_requests').glob('*.json')))

    def _request(self, texts):
        with self.request_lock:
            if self.prior_tokens + self.usage['total_tokens'] >= self.protocol['embedding_input_token_stop']:
                raise BudgetStop('embedding_budget')
            before = self.usage
            try:
                return super()._request(texts)
            finally:
                after = self.usage
                self.sequence += 1
                write(OUT / 'embedding_requests' / f'{self.sequence:05d}.json',
                      {'stage': self.stage, 'texts': len(texts),
                       **{k: after[k] - before[k] for k in ('calls', 'total_tokens', 'prompt_tokens', 'failures', 'usage_missing_calls')}})


def inspect(row):
    """协议/环境故障停止派发；模型格式问题保留原记录并排除相应授信。"""
    fatal = []
    attempts = row.get('attempts', [])
    if not 1 <= len(attempts) <= 2 or row.get('final') != attempts[-1]:
        fatal.append('P7_delivery_contract')
    if len(attempts) == 2 and attempts[0].get('joint'):
        fatal.append('P7_early_stop_contract')
    for attempt in attempts:
        generation = attempt.get('generation', {})
        selected = {c['invariant_id'] for c in generation.get('retrieved_cards', [])}
        adopted = {c['invariant_id'] for c in generation.get('cards', [])}
        if len(selected) > 3 or not adopted <= selected:
            fatal.append('actual_adoption_contract')
        evidence = attempt.get('validation', {}).get('evidence', {})
        if evidence.get('metadata', {}).get('worker_error'):
            fatal.append('validation_worker_error')
        trace = trace_of(attempt)
        if any(str(e).startswith(('embedding_', 'BudgetStop')) for e in trace.get('errors', [])):
            fatal.append('retrieval_infrastructure_or_budget')
    if row.get('worker_error'):
        fatal.append('worker_error')
    return sorted(set(fatal))


def shared_pair_check(items):
    """同题首次查询、候选、余弦必须完全相同，排序差异才可解释为L1干预。"""
    groups = {}
    for row in items:
        groups.setdefault(row['task_id'], {})[row['arm']] = row
    checks = []
    for identifier, arms in groups.items():
        if set(arms) != {'L0', 'L1'}:
            continue
        traces = [trace_of(arms[a]['attempts'][0]) for a in ('L0', 'L1')]
        equal = all(traces[0].get(key) == traces[1].get(key) for key in ('query_hash', 'candidate_ids', 'scores'))
        complete = all(t.get('status') == 'completed' for t in traces)
        checks.append({'task_id': identifier, 'same_first_candidates': equal, 'both_retrieval_completed': complete})
    return checks


def usage_total(events):
    return {'calls': len(events), 'prompt_tokens': sum(e.get('prompt_tokens', 0) for e in events),
            'completion_tokens': sum(e.get('completion_tokens', 0) for e in events),
            'total_tokens': sum(e.get('total_tokens', 0) for e in events),
            'errors': sum(e['status'] == 'error' for e in events),
            'usage_missing': sum(e['status'] == 'completed' and 'total_tokens' not in e for e in events),
            'unfinished': sum(e['status'] == 'started' for e in events)}


def report():
    """从固定436卡重放实际采用反馈；全反馈和跨族增量两份库分开保存。"""
    meta = verify()
    manifest, source, origins = read(OUT / 'manifest.json'), load_memory(OUT / 'input_memory.jsonl'), read(OUT / 'origins.json')
    items = records()
    requests = [read(p) for p in sorted((OUT / 'requests').glob('*.json'))]
    shared_cost = usage_total([e for e in requests if e['arm'] == 'shared_initial'])
    anchor = read(OUT / 'training_anchor.json')
    anchor_ids = {i for ids in anchor['queries'].values() for i in ids}
    baseline_ids = {n.invariant_id for n in source if n.q_visits > 0}
    reviews = read(OUT / 'implementation_review.json').get('reviews', []) if (OUT / 'implementation_review.json').exists() else []
    summary = {'protocol': PROTOCOL, 'status': meta['status'], 'baseline_visited': len(baseline_ids),
               'cards': len(source), 'P7_runs': len(items), 'arms': {}, 'new_Dgate_generation': False,
               'cost': {'LLM': usage_total(requests), 'shared_initial': shared_cost,
                        'embedding': [read(p) for p in sorted((OUT / 'embedding_requests').glob('*.json'))],
                        'actual_currency': None, 'physical_HTTP_retries': 'not fully observed by native requester'},
               'shared_candidates': shared_pair_check(items), 'fatal_issues': []}
    all_events, task_scores = [], []
    for arm in ('L0', 'L1'):
        arm_rows = [r for r in items if r['arm'] == arm]
        arm_cost = usage_total([e for e in requests if e['arm'] == arm])
        selected, adopted = set(), set()
        for row in arm_rows:
            for a in row.get('attempts', []):
                g = a.get('generation', {})
                selected.update(c['invariant_id'] for c in g.get('retrieved_cards', []))
                adopted.update(c['invariant_id'] for c in g.get('cards', []))
            summary['fatal_issues'].extend({'arm': arm, 'task_id': row['task_id'], 'reason': issue} for issue in inspect(row))
            f = row.get('final', {})
            task_scores.append({'arm': arm, 'task_id': row['task_id'], 'family_id': row['family_id'],
                                **{k: f.get(k) for k in ('functional', 'security', 'joint', 'measured')},
                                'workflow_completed': f.get('generation', {}).get('workflow_completed', False),
                                'attempts': len(row.get('attempts', [])), 'tokens': row['accounting']['total_tokens']})
        stats = {'executed': len(arm_rows), 'measured': sum(bool(r.get('final', {}).get('measured')) for r in arm_rows),
                 'functional': sum(bool(r.get('final', {}).get('measured') and r['final'].get('functional')) for r in arm_rows),
                 'security': sum(bool(r.get('final', {}).get('measured') and r['final'].get('security')) for r in arm_rows),
                 'joint': sum(bool(r.get('final', {}).get('measured') and r['final'].get('joint')) for r in arm_rows),
                 'final_workflows': sum(bool(r.get('final', {}).get('generation', {}).get('workflow_completed'))
                                        and not (r.get('shared_initial_error') and r.get('final', {}).get('attempt') == 0) for r in arm_rows),
                 'selected_unique': len(selected), 'adopted_unique': len(adopted),
                 'adopted_occurrences': sum(len({c['invariant_id'] for c in a.get('generation', {}).get('cards', [])}) for r in arm_rows for a in r.get('attempts', [])),
                 'cost': arm_cost, 'credit': {}}
        for policy in ('all_feedback', 'cross_family'):
            credit_input = copy.deepcopy(arm_rows)
            for row in credit_input:
                if row.get('shared_initial_error'):
                    row['attempts'][0].setdefault('generation', {})['workflow_completed'] = False
                for attempt in row.get('attempts', []):
                    if not attempt.get('measured'):
                        attempt.setdefault('generation', {})['workflow_completed'] = False
            nodes, events, credit = credit_rows(credit_input, source, origins, manifest, policy)
            for event in events:
                event.update(protocol=PROTOCOL, arm=arm)
            all_events.extend(events)
            folder = OUT / arm / policy
            _write_memory(folder / 'frozen/m_star_q.jsonl', nodes)
            jsonl(folder / 'memory_q_events.jsonl', events)
            support = {k: set(v) for k, v in read(OUT / 'input_family_support.json').items()}
            for e in events:
                if e['credited']:
                    support.setdefault(e['invariant_id'], set()).add(e['family_id'])
            write(folder / 'q_family_support.json', {k: sorted(v) for k, v in support.items()})
            new_ids = set(credit['new_card_ids'])
            credit.update(positive_Q=sum(n.q_value > 0 for n in nodes), negative_Q=sum(n.q_value < 0 for n in nodes),
                          zero_Q=sum(n.q_value == 0 for n in nodes), new_anchor_cards=len(new_ids & anchor_ids),
                          anchor_queries_touched=sum(bool(new_ids & set(v)) for v in anchor['queries'].values()),
                          anchor_unique_covered=sum(n.q_visits > 0 and n.invariant_id in anchor_ids for n in nodes),
                          new_feedback_family_counts={i: len({e['family_id'] for e in events
                                                             if e['credited'] and e['invariant_id'] == i})
                                                      for i in {e['invariant_id'] for e in events if e['credited']}})
            valid_reviews = []
            for review in reviews:
                if review['arm'] != arm or not review.get('implemented') or review['invariant_id'] not in new_ids:
                    continue
                matches = [e for e in events if e['credited'] and e['task_id'] == review['task_id']
                           and e['attempt'] == review['attempt'] and e['invariant_id'] == review['invariant_id'] and e['reward'] == 1]
                if matches:
                    valid_reviews.append(review)
            credit['implementation_reviews'] = valid_reviews
            credit['implementation_joint_families'] = len({manifest['task_families'][r['task_id']] for r in valid_reviews})
            stats['credit'][policy] = credit
        shared_for_arm = [e for e in requests if e['arm'] == 'shared_initial' and e['task_id'] in {r['task_id'] for r in arm_rows}]
        # 12题双组共享初析各分摊一半，仅比较成本时分摊；总账永远只计一次。
        stats['probe_allocated_tokens'] = sum(e.get('total_tokens', 0) for e in requests if e['arm'] == arm and e['task_id'] in manifest['probe']) + .5 * sum(e.get('total_tokens', 0) for e in shared_for_arm if e['task_id'] in manifest['probe'])
        summary['arms'][arm] = stats
    for c in summary['shared_candidates']:
        if not c['same_first_candidates']:
            summary['fatal_issues'].append({'task_id': c['task_id'], 'reason': 'shared_first_candidate_mismatch'})
    jsonl(OUT / 'rows.jsonl', items)
    jsonl(OUT / 'memory_q_events.all_views.jsonl', all_events)
    write(OUT / 'summary.json', summary)
    write(CURATED / 'summary.json', summary)
    for name, data in [('scores.csv', task_scores), ('reward_events.csv', all_events)]:
        if data:
            with (CURATED / name).open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(data[0]))
                writer.writeheader()
                writer.writerows(data)
    return summary


def probe_gate(summary):
    checks = {}
    cost = summary['cost']['LLM']
    budget = read(OUT / 'protocol.json')['budget_cumulative']['probe12_two_arms']
    common = not summary['fatal_issues'] and not cost['errors'] and not cost['unfinished'] and not cost['usage_missing']
    for arm, stats in summary['arms'].items():
        credit = stats['credit']['cross_family']
        checks[arm] = {'12_measured': stats['executed'] == stats['measured'] == 12,
                       '10_final_workflows': stats['final_workflows'] >= 10,
                       '6_new_cross_cards': credit['new_cards'] >= 6,
                       '4_new_anchor_cards': credit['new_anchor_cards'] >= 4,
                       '8_anchor_queries': credit['anchor_queries_touched'] >= 8,
                       '2_implementation_Joint_families': credit['implementation_joint_families'] >= 2,
                       'no_system_fault': common,
                       'budget': cost['calls'] <= budget['logical_calls_stop'] and cost['total_tokens'] <= budget['LLM_token_stop']}
    passed = {a: all(c.values()) for a, c in checks.items()}
    l0, l1 = summary['arms']['L0'], summary['arms']['L1']
    relative = {'3_more_cross_cards': l1['credit']['cross_family']['new_cards'] >= l0['credit']['cross_family']['new_cards'] + 3,
                'F_not_lower': l1['functional'] >= l0['functional'], 'Joint_not_lower': l1['joint'] >= l0['joint'],
                'token_ratio': l0['probe_allocated_tokens'] > 0 and l1['probe_allocated_tokens'] <= 1.25 * l0['probe_allocated_tokens']}
    winner = 'L1' if passed['L1'] and all(relative.values()) else 'L0' if passed['L0'] else None
    return {'stage': 'probe', 'passed': winner is not None, 'winner': winner, 'absolute': checks,
            'relative_L1': relative, 'interpretation': 'coverage/exposure engineering gate, not evidence of Q generation benefit'}


def gate60(summary, winner):
    manifest = read(OUT / 'manifest.json')
    recent_ids = set(manifest['learning'][12:60])
    recent = [r for r in records() if r['arm'] == winner and r['task_id'] in recent_ids]
    events = []
    with (OUT / winner / 'cross_family/memory_q_events.jsonl').open(encoding='utf-8') as stream:
        events = [json.loads(line) for line in stream if line.strip()]
    probe_gate_snapshot = read(OUT / 'stage_probe_summary.json')['arms'][winner]
    prior_new = set(probe_gate_snapshot['credit']['cross_family']['new_card_ids'])
    new_ids = set(summary['arms'][winner]['credit']['cross_family']['new_card_ids']) - prior_new
    anchor = {i for ids in read(OUT / 'training_anchor.json')['queries'].values() for i in ids}
    requests = [read(p) for p in (OUT / 'requests').glob('*.json')]
    recent_tokens = sum(r.get('total_tokens', 0) for r in requests if r['task_id'] in recent_ids)
    old_rate = probe_gate_snapshot['credit']['cross_family']['new_anchor_cards'] / max(1, probe_gate_snapshot['probe_allocated_tokens'])
    rate = len(new_ids & anchor) / max(1, recent_tokens)
    checks = {'48_measured': len(recent) == 48 and all(r.get('final', {}).get('measured') for r in recent),
              '44_final_workflows': sum(bool(r.get('final', {}).get('generation', {}).get('workflow_completed'))
                                        and not (r.get('shared_initial_error') and r.get('final', {}).get('attempt') == 0) for r in recent) >= 44,
              '24_new_cross_cards': len(new_ids) >= 24, '16_new_anchor_cards': len(new_ids & anchor) >= 16,
              'half_probe_efficiency': rate >= .5 * old_rate,
              '3_implementation_Joint_families': summary['arms'][winner]['credit']['cross_family']['implementation_joint_families'] >= 3,
              'no_system_fault': not summary['fatal_issues'] and not summary['cost']['LLM']['errors']}
    budget = read(OUT / 'protocol.json')['budget_cumulative']['winner60_plus_other12']
    checks['budget'] = summary['cost']['LLM']['calls'] <= budget['logical_calls_stop'] and summary['cost']['LLM']['total_tokens'] <= budget['LLM_token_stop']
    return {'stage': '60', 'passed': all(checks.values()), 'winner': winner, 'checks': checks,
            'new_cross_cards_last48': len(new_ids), 'new_anchor_last48': len(new_ids & anchor),
            'recent_efficiency_per_million': rate * 1e6, 'probe_efficiency_per_million': old_rate * 1e6}


def run(stage):
    """门失败先停止；只调原run_one(P7)，探针结果复用，不重复付费或跨臂授信。"""
    meta = verify()
    protocol, manifest = read(OUT / 'protocol.json'), read(OUT / 'manifest.json')
    if meta['status'].startswith(('technical_stop', 'preflight_stop', 'budget_stop')):
        raise RuntimeError('recorded_stop_requires_review_or_new_protocol')
    setup_environment(protocol)
    target = manifest['learning'][:STAGES[stage][0]]
    winner = None
    if stage in {'60', '296'}:
        gate = read(OUT / ('probe_gate.json' if stage == '60' else 'gate60.json'))
        if not gate['passed']:
            raise RuntimeError('prior_stage_gate_not_passed')
        winner = gate['winner']
    elif stage == 'probe':
        if not read(OUT / 'smoke_gate.json')['passed']:
            raise RuntimeError('smoke_gate_not_passed')
    pre = preflight(target)
    write(OUT / ('preflight_' + stage + '.json'), pre)
    if not pre['passed']:
        meta['status'] = 'preflight_stop_' + stage
        write(OUT / 'run_metadata.json', meta)
        return report()
    arms = [winner] if winner else ['L0', 'L1']
    done = {(r['arm'], r['task_id']) for r in records()}
    jobs = []
    rng = random.Random(protocol['shuffle_execution_seed'])
    for identifier in target:
        pair = list(arms)
        rng.shuffle(pair)
        jobs.extend((identifier, arm) for arm in pair if (arm, identifier) not in done)
    if not jobs:
        return report()
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    native = _requester(protocol['model'], 60, max_tokens=4096, max_inflight=2, thinking='disabled')
    budget = Budget(protocol, stage, native)
    embedding = StudyEmbedding(protocol, stage, model=protocol['embedding_model'], key_loader=load_key,
                               cache_path=ROOT / 'translation_work/cache/embeddings/cle.sqlite3', timeout=120)
    source = load_memory(OUT / 'input_memory.jsonl')
    legal = [n for n in source if n.status in {'active', 'provisional', 'consolidated'}
             and 'python' in (n.language_leaves or {}) and len(card_embedding_text(n)) <= MAX_CARD_CHARS]
    if any(embedding._load_cached(_digest(card_embedding_text(n))) is None for n in legal):
        raise RuntimeError('cold_card_embedding_cache_no_automatic_rebuild')
    mask_path = OUT / ('exposure_mask_' + stage + '.json')
    if mask_path.exists():
        visits = read(mask_path)
    else:
        mask_bank = source if stage in {'smoke', 'probe'} else load_memory(OUT / winner / 'cross_family/frozen/m_star_q.jsonl')
        visits = {n.invariant_id: n.q_visits for n in mask_bank}
        write(mask_path, visits)
    tasks = read(OUT / 'tasks.json')
    write(OUT / ('stage_' + stage + '_launch.json'), {'jobs': jobs, 'planned_jobs': len(jobs), 'max_workers': 2,
          'Q_values_in_forward': False, 'candidate_order': {'L0': None, 'L1': 'coverage'}})
    meta['status'] = 'running_' + stage
    write(OUT / 'run_metadata.json', meta)

    def ensure_initial(identifier):
        path = OUT / 'initials' / (identifier + '.json')
        if path.exists():
            return read(path)
        request, tracker = budget.bind(identifier, 'shared_initial')
        initial = prepare_shared_initial(tasks[identifier], request)
        initial['accounting'] = {k: tracker.snapshot()['total'][k] for k in FIELDS}
        write(path, initial)
        return initial

    def job(identifier, arm, initial):
        bank = copy.deepcopy(source)
        if arm == 'L1':
            for node in bank:
                node.q_visits = visits[node.invariant_id]
        request, tracker = budget.bind(identifier, arm)
        started = perf_counter()
        native_row = run_one('PLT', tasks[identifier], 'P7', request, {'full': bank}, embedding,
                             retrieval_mode='semantic_llm', delta=-1, lambda_q=.5, max_experiences=3,
                             candidate_order='coverage' if arm == 'L1' else None,
                             initial_analysis=copy.deepcopy(initial['initial_analysis']))
        write(OUT / 'native_rows' / arm / (identifier + '.json'), native_row)
        try:
            row = record_result(copy.deepcopy(native_row), tasks[identifier], 'Q0', 'D_init', perf_counter() - started)
        except Exception as exc:
            # 历史记录器曾丢失已付费原件；先保留native，再记录归一化失败并停止。
            row = {**copy.deepcopy(native_row), 'task_id': identifier, 'pool': 'D_init',
                   'family_id': tasks[identifier]['family_id'], 'worker_error': type(exc).__name__,
                   'final': (native_row.get('attempts') or [{}])[-1]}
        row.update(arm=arm, protocol=PROTOCOL, stage=stage, shared_initial_error=initial.get('error_type'),
                   accounting={k: tracker.snapshot()['total'][k] for k in FIELDS})
        assert body(bank) == body(source)
        write(OUT / 'task_rows' / arm / (identifier + '.json'), row)
        print(json.dumps({'stage': stage, 'arm': arm, 'task_id': identifier,
                         'F': row['final']['functional'], 'S': row['final']['security'], 'Joint': row['final']['joint'],
                         'workflow': row['final'].get('generation', {}).get('workflow_completed'),
                         'calls': row['accounting']['calls'], 'tokens': row['accounting']['total_tokens']}), flush=True)
        return row

    started = perf_counter()
    fatal = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for offset in range(0, len(jobs), 2):
            if budget.stopped.is_set() or fatal:
                break
            batch = jobs[offset:offset + 2]
            initials = {i: ensure_initial(i) for i in dict.fromkeys(i for i, _ in batch)}
            if budget.stopped.is_set():
                break
            futures = [executor.submit(job, i, a, initials[i]) for i, a in batch]
            for future in as_completed(futures):
                row = future.result()
                fatal.extend(inspect(row))
            paired = shared_pair_check(records())
            if any(not c['same_first_candidates'] for c in paired):
                fatal.append('shared_candidate_mismatch')
    meta = read(OUT / 'run_metadata.json')
    meta['status'] = ('budget_stop_' + str(budget.reason) if budget.stopped.is_set() else
                      'technical_stop_' + stage if fatal else 'completed_' + stage)
    meta['segments'].append({'stage': stage, 'seconds': perf_counter() - started, 'fatal': fatal})
    write(OUT / 'run_metadata.json', meta)
    summary = report()
    write(OUT / ('stage_' + stage + '_summary.json'), summary)
    if stage == 'smoke':
        limit = protocol['budget_cumulative']['smoke2_two_arms']
        checks = {'4_runs': len(records()) == 4,
                  '4_measured': sum(s['measured'] for s in summary['arms'].values()) == 4,
                  'no_system_fault': not summary['fatal_issues'] and not budget.stopped.is_set(),
                  '2_equal_candidate_pairs': len(summary['shared_candidates']) == 2 and all(c['same_first_candidates'] for c in summary['shared_candidates']),
                  'budget': summary['cost']['LLM']['calls'] <= limit['logical_calls_stop']
                            and summary['cost']['LLM']['total_tokens'] <= limit['LLM_token_stop']}
        write(OUT / 'smoke_gate.json', {'passed': all(checks.values()), 'checks': checks})
    elif stage == 'probe':
        write(OUT / 'probe_gate.json', probe_gate(summary))
    elif stage == '60':
        write(OUT / 'gate60.json', gate60(summary, winner))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'report', 'gates'])
    parser.add_argument('--stage', choices=list(STAGES), default='smoke')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare()
    elif args.command == 'run':
        run(args.stage)
    else:
        summary = report()
        if args.command == 'gates':
            if summary['P7_runs'] == 24:
                write(OUT / 'probe_gate.json', probe_gate(summary))
            if (OUT / 'gate60.json').exists():
                winner = read(OUT / 'probe_gate.json')['winner']
                write(OUT / 'gate60.json', gate60(summary, winner))
        print(json.dumps({'status': summary['status'], 'P7_runs': summary['P7_runs'],
                          'arms': {a: {k: s[k] for k in ('executed', 'functional', 'security', 'joint', 'final_workflows')}
                                   for a, s in summary['arms'].items()}, 'cost': summary['cost']['LLM']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

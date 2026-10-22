"""D_init 三张/不限量先导及单轮全303题学习；复用原P7，不改旧结果。"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import csv
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_dinit_coverage as core
from methods.cle_ablation.run_memory_q_dinit import body
from methods.cle_ablation.run_memory_q import prepare_shared_initial, record_result
from methods.cle_ablation.runner import load_memory, run_one
from methods.sct_trajectory.memory_q import reward_from_evidence, update_q
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_memory_q_study import _write_memory

CONFIG = ROOT / 'configs/cle_dinit_card_cap_20261020'
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_card_cap_v1'
CURATED = ROOT / 'results/curated/cle_dinit_card_cap_20261020'
PARENT = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_full_learning_v4b'
PROTOCOL = 'cle-dinit-card-cap-v1'
ARMS = ('L3', 'Lall')
read, jsonl = core.read, core.jsonl


def credit_rows(items, source, origins, manifest, policy):
    """D_init实际采用授信：允许多卡，继承各视图起点，按原c0/c1奖励回放。"""
    if policy not in ('all_feedback', 'cross_family'):
        raise ValueError('unknown_credit_policy')
    bank = copy.deepcopy(source)
    nodes = {n.invariant_id: n for n in bank}
    by_task = {r['task_id']: r for r in items}
    if len(by_task) != len(items):
        raise ValueError('duplicate_task_records')
    if any(r.get('pool') != 'D_init' or r['task_id'] not in manifest['learning'] for r in items):
        raise ValueError('D_init_only_qualified_learning')
    events = []
    for identifier in manifest['learning']:
        if identifier not in by_task:
            continue
        row = by_task[identifier]
        if row['family_id'] != manifest['task_families'][identifier]:
            raise ValueError('learning_family_mismatch')
        for attempt in row['attempts']:
            g = attempt.get('generation', {})
            selected = [c['invariant_id'] for c in g.get('retrieved_cards', [])]
            adopted = list(dict.fromkeys(c['invariant_id'] for c in g.get('cards', [])))
            if not set(selected) <= nodes.keys() or not set(adopted) <= set(selected):
                raise ValueError('invalid_actual_adoption')
            if row['arm'] == 'L3' and len(set(selected)) > 3:
                raise ValueError('L3_exceeds_three')
            evidence = attempt.get('validation', {}).get('evidence', {})
            reward = reward_from_evidence(evidence, code=attempt.get('code', ''))
            if row.get('worker_error') or not g.get('workflow_completed') or not attempt.get('measured') or row.get('shared_initial_error'):
                reward = None
            for card_id in adopted or [None]:
                origin = origins[card_id] if card_id else {}
                families = origin.get('known_source_families', [])
                relation = ('same_family' if row['family_id'] in families else
                            'unknown' if not families or origin.get('unresolved_absorbed_ids') else 'cross_family')
                skip = 'no_adopted_experiences' if card_id is None else None
                if card_id and reward is None:
                    skip = 'incomplete_or_technical_measurement'
                if card_id and policy == 'cross_family' and relation != 'cross_family':
                    skip = 'same_or_unknown_origin_family'
                node = nodes[card_id] if card_id else None
                before = node.q_value if node else None
                if node and not skip:
                    node.q_value = update_q(before, reward, .3)
                    node.q_visits += 1
                events.append({'task_id': identifier, 'family_id': row['family_id'], 'pool': 'D_init',
                    'arm': row['arm'], 'attempt': attempt['attempt'], 'policy': policy, 'invariant_id': card_id,
                    'selected_position': selected.index(card_id) + 1 if card_id else None,
                    'origin_relation': relation, 'reward': reward, 'credited': bool(node and not skip),
                    'skip_reason': skip, 'q_before': before, 'q_after': node.q_value if node else None,
                    'q_visits': node.q_visits if node else None, 'protocol': PROTOCOL})
    assert body(bank) == body(source)
    initial = {n.invariant_id for n in source if n.q_visits > 0}
    final = {n.invariant_id for n in bank if n.q_visits > 0}
    return bank, events, {'baseline_learned': len(initial), 'learned_cards': len(final),
        'new_cards': len(final - initial), 'coverage': len(final) / len(bank),
        'valid_updates': sum(e['credited'] for e in events),
        'positive_updates': sum(e['credited'] and e['reward'] == 1 for e in events),
        'negative_updates': sum(e['credited'] and e['reward'] == -1 for e in events)}


def inspect(row):
    """仅协议/基础设施故障中止；模型错误、超时与低Joint如实保留。"""
    issues = []
    attempts = row.get('attempts', [])
    if not 1 <= len(attempts) <= 2 or row.get('final') != attempts[-1]:
        issues.append('P7_delivery_contract')
    if len(attempts) == 2 and attempts[0].get('joint'):
        issues.append('P7_early_stop_contract')
    for a in attempts:
        g, trace = a.get('generation', {}), core.trace_of(a)
        chosen = {c['invariant_id'] for c in g.get('retrieved_cards', [])}
        adopted = {c['invariant_id'] for c in g.get('cards', [])}
        if not adopted <= chosen or (row['arm'] == 'L3' and len(chosen) > 3):
            issues.append('actual_adoption_contract')
        if trace.get('status') == 'completed':
            if trace.get('selection_limit') != (3 if row['arm'] == 'L3' else None):
                issues.append('wrong_selection_limit')
        for error in trace.get('errors', []):
            if str(error).startswith(('embedding_', 'BudgetStop', 'selector_prompt_budget', 'selector_output_truncated')):
                issues.append('retrieval_infrastructure_or_budget')
        worker = a.get('validation', {}).get('evidence', {}).get('metadata', {}).get('worker_error', {})
        if worker and worker.get('type') not in {'timeout', 'SyntaxError', 'IndentationError'}:
            issues.append('validation_worker_error')
    if row.get('worker_error'):
        issues.append('worker_error')
    return sorted(set(issues))


def records():
    manifest = read(OUT / 'manifest.json')
    return [read(p) for i in manifest['learning'] for arm in ARMS
            if (p := OUT / 'task_rows' / arm / (i + '.json')).exists()]


def pair_checks(rows):
    """核对数量先导两组首次查询、候选、余弦及呈现顺序一致。"""
    pairs = {}
    for r in rows:
        pairs.setdefault(r['task_id'], {})[r['arm']] = r
    result = []
    for i, arms in pairs.items():
        if set(arms) != set(ARMS):
            continue
        a, b = [core.trace_of(arms[x]['attempts'][0]) for x in ARMS]
        result.append({'task_id': i, 'shared_candidates': all(a.get(k) == b.get(k) for k in
            ('query_hash', 'candidate_ids', 'scores', 'presented_candidate_ids')),
            'retrieval_completed': all(t.get('status') == 'completed' for t in (a, b))})
    return result


def verify():
    meta = read(OUT / 'run_metadata.json')
    for name, expected in meta['identity'].items():
        if core.digest(ROOT / name) != expected:
            raise RuntimeError('locked_source_or_input_changed:' + name)
    return meta


def prepare():
    """绑定当前两套起点与已修复303题；原件只读，新目录可独立恢复。"""
    if (OUT / 'run_metadata.json').exists():
        return verify()
    if shutil.disk_usage(ROOT.anchor).free < 3 * 1024**3:
        raise RuntimeError('insufficient_disk_space')
    p, m = read(CONFIG / 'protocol.json'), read(CONFIG / 'manifest.json')
    tasks = read(PARENT / 'tasks.json')
    assert len(m['learning']) == len(set(m['learning'])) == 303
    assert m['learning'] == read(PARENT / 'manifest.json')['learning']
    assert tasks == read(ROOT / 'configs/cle_dinit_full_learning_20261020_v4b/tasks.json')
    preflight = read(PARENT / 'preflight_summary.json')
    assert preflight['eligible'] == 303 and not preflight['failures']
    for name, data in [('protocol.json', p), ('manifest.json', m), ('tasks.json', tasks),
                       ('origins.json', read(PARENT / 'origins.json'))]:
        write(OUT / name, data)
    paths = [Path(__file__), CONFIG / 'protocol.json', CONFIG / 'manifest.json', PARENT / 'tasks.json',
             PARENT / 'origins.json', PARENT / 'preflight_summary.json',
             ROOT / 'methods/cle_ablation/runner.py', ROOT / 'methods/cle_ablation/run_memory_q.py',
             ROOT / 'methods/cle_ablation/run_memory_q_dinit_coverage.py',
             ROOT / 'methods/sct_trajectory/semantic_retrieval.py', ROOT / 'methods/sct_trajectory/retriever.py',
             ROOT / 'methods/sct_trajectory/context_pipeline.py', ROOT / 'methods/sct_trajectory/memory_q.py',
             ROOT / 'methods/sct_trajectory/selector_protocol.py', ROOT / 'methods/sct_trajectory/run_closed_loop.py',
             ROOT / 'methods/sct_agent/validation_evidence.py',
             ROOT / 'data/external/secodeplt/secodeplt/data.json']
    for policy, expected in [('all_feedback', 669), ('cross_family', 584)]:
        path = PARENT / policy / 'frozen/m_star_q.jsonl'
        bank = load_memory(path)
        assert len(bank) == 1939 and sum(n.q_visits > 0 for n in bank) == expected
        _write_memory(OUT / 'inputs' / policy / 'memory.jsonl', bank)
        support_path = PARENT / policy / 'q_family_support.json'
        write(OUT / 'inputs' / policy / 'family_support.json', read(support_path))
        paths += [path, support_path]
    assert body(load_memory(OUT / 'inputs/all_feedback/memory.jsonl')) == body(load_memory(OUT / 'inputs/cross_family/memory.jsonl'))
    for i in m['learning']:
        receipt = read(PARENT / 'preflight' / (i + '.json'))
        assert receipt['reward_eligible']
        write(OUT / 'preflight' / (i + '.json'), {**receipt, 'reused_unchanged_task': True,
              'source_receipt': str((PARENT / 'preflight' / (i + '.json')).relative_to(ROOT))})
    # 完全相同的公开任务、验证器和当日本地对照可复用；生成成绩不复用。
    write(OUT / 'preflight_summary.json', {**preflight, 'reused': True, 'API_calls': 0,
          'source': str((PARENT / 'preflight_summary.json').relative_to(ROOT))})
    for i in m['learning']:
        old = PARENT / 'initials' / (i + '.json')
        if old.exists() and not read(old).get('error_type'):
            write(OUT / 'initials' / (i + '.json'), {**read(old), 'reused_initial': True,
                  'source': str(old.relative_to(ROOT))})
    for path in paths:
        if path.suffix == '.py':
            target = OUT / 'source_snapshot' / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    meta = {'protocol': PROTOCOL, 'status': 'prepared', 'identity': {str(x.relative_to(ROOT)): core.digest(x) for x in paths},
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'python': sys.executable, 'new_Dgate_generation': False, 'performance_continuation_gate': False, 'segments': []}
    write(OUT / 'run_metadata.json', meta)
    return meta


def csv_file(name, values):
    if values:
        with (CURATED / name).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)


def report():
    """从原生逐题记录重放双起点反馈，报告数量、采用、Joint及分臂成本。"""
    meta, rows = verify(), records()
    m, origins = read(OUT / 'manifest.json'), read(OUT / 'origins.json')
    requests = [read(p) for p in (OUT / 'requests').glob('*.json')]
    embeddings = [read(p) for p in (OUT / 'embedding_requests').glob('*.json')]
    summary = {'protocol': PROTOCOL, 'status': meta['status'], 'P7_runs': len(rows), 'arms': {},
        'cost': {'LLM': core.usage_total(requests), 'embedding': {k: sum(e.get(k, 0) for e in embeddings)
                 for k in ('calls', 'total_tokens', 'failures', 'usage_missing_calls')}, 'actual_bill_CNY': None},
        'shared_candidates': pair_checks(rows), 'fatal_issues': [], 'new_Dgate_generation': False}
    scores, mechanisms, all_events, cards_table = [], [], [], []
    baseline = load_memory(OUT / 'inputs/all_feedback/memory.jsonl')
    initial = {n.invariant_id: n for n in baseline}
    for arm in ARMS:
        arm_rows = [r for r in rows if r['arm'] == arm]
        stats = {'executed': len(arm_rows), 'measured': sum(bool(r['final'].get('measured')) for r in arm_rows),
            'F': sum(bool(r['final'].get('measured') and r['final'].get('functional')) for r in arm_rows),
            'S': sum(bool(r['final'].get('measured') and r['final'].get('security')) for r in arm_rows),
            'Joint': sum(bool(r['final'].get('measured') and r['final'].get('joint')) for r in arm_rows),
            'credit': {}, 'cost': core.usage_total([e for e in requests if e['arm'] == arm])}
        candidate, selected, adopted = Counter(), Counter(), Counter()
        for r in arm_rows:
            f = r['final']
            summary['fatal_issues'] += [{'arm': arm, 'task_id': r['task_id'], 'issue': s} for s in inspect(r)]
            scores.append({'arm': arm, 'task_id': r['task_id'], 'family_id': r['family_id'],
                **{k: f.get(k) for k in ('measured', 'functional', 'security', 'joint')},
                'workflow_completed': f.get('generation', {}).get('workflow_completed', False),
                'attempts': len(r['attempts']), 'tokens': r['accounting']['total_tokens']})
            for a in r['attempts']:
                g, t = a.get('generation', {}), core.trace_of(a)
                c = set(t.get('candidate_ids', []))
                s = [x['invariant_id'] for x in g.get('retrieved_cards', [])]
                d = {x['invariant_id'] for x in g.get('cards', [])}
                candidate.update(c); selected.update(set(s)); adopted.update(d)
                mechanisms.append({'arm': arm, 'task_id': r['task_id'], 'attempt': a['attempt'],
                    'candidates': len(c), 'selected': len(s), 'adopted': len(d), 'tail_adopted': len(set(s[3:]) & d),
                    'initially_unvisited_selected': sum(initial[i].q_visits == 0 for i in set(s)),
                    'initially_unvisited_adopted': sum(initial[i].q_visits == 0 for i in d),
                    'measured': a.get('measured'), 'Joint': a.get('joint'), 'workflow_completed': g.get('workflow_completed'),
                    'generation_error': g.get('error_type'), 'retrieval_status': t.get('status')})
        for policy in ('all_feedback', 'cross_family'):
            source = load_memory(OUT / 'inputs' / policy / 'memory.jsonl')
            bank, events, cs = credit_rows(arm_rows, source, origins, m, policy)
            assert sum(n.q_visits for n in bank) - sum(n.q_visits for n in source) == cs['valid_updates']
            stats['credit'][policy] = cs
            all_events += events
            target = OUT / arm / policy
            _write_memory(target / 'frozen/m_star_q.jsonl', bank)
            jsonl(target / 'memory_q_events.jsonl', events)
            support = {k: set(v) for k, v in read(OUT / 'inputs' / policy / 'family_support.json').items()}
            for e in events:
                if e['credited']:
                    support.setdefault(e['invariant_id'], set()).add(e['family_id'])
            write(target / 'q_family_support.json', {k: sorted(v) for k, v in support.items()})
            before = {n.invariant_id: n for n in source}
            for n in bank:
                cards_table.append({'arm': arm, 'policy': policy, 'card_id': n.invariant_id, 'cwe': n.cwe,
                    'baseline_visits': before[n.invariant_id].q_visits, 'final_visits': n.q_visits,
                    'baseline_Q': before[n.invariant_id].q_value, 'final_Q': n.q_value,
                    'candidates': candidate[n.invariant_id], 'selections': selected[n.invariant_id], 'adoptions': adopted[n.invariant_id]})
        stats.update(selected_unique=len(selected), adopted_unique=len(adopted),
            attempts=sum(len(r['attempts']) for r in arm_rows))
        summary['arms'][arm] = stats
    for check in summary['shared_candidates']:
        if not check['shared_candidates']:
            summary['fatal_issues'].append({'task_id': check['task_id'], 'issue': 'first_candidates_differ'})
    CURATED.mkdir(parents=True, exist_ok=True)
    jsonl(OUT / 'rows.jsonl', rows)
    for folder in (OUT, CURATED):
        write(folder / 'summary.json', summary)
    for name, values in [('scores.csv', scores), ('attempt_mechanisms.csv', mechanisms),
                         ('reward_events.csv', all_events), ('card_coverage.csv', cards_table)]:
        csv_file(name, values)
    return summary


def run(stage):
    """按2题→12题→303题顺序派发；批内覆盖固定、批后刷新，正确率不设门。"""
    core.OUT = OUT
    core.STAGES = {'pilot': (12, 'pilot12'), 'full': (303, 'full303')}
    prepare()
    meta = verify()
    if meta['status'] in {'budget_stop', 'technical_stop'}:
        raise RuntimeError('recorded_stop_requires_reconciliation')
    p, m, tasks = read(OUT / 'protocol.json'), read(OUT / 'manifest.json'), read(OUT / 'tasks.json')
    if stage != 'smoke':
        required = OUT / ('smoke_gate.json' if stage == 'pilot' else 'pilot_gate.json')
        if not required.exists() or not read(required)['passed']:
            raise RuntimeError('previous_technical_gate_pending')
    core.setup_environment(p)
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    native = _requester(p['model'], 120, max_tokens=4096, max_inflight=4, thinking='disabled')
    budget = core.Budget(p, 'full' if stage == 'full' else 'pilot', native)
    embedding = core.StudyEmbedding(p, stage, model=p['embedding_model'], key_loader=load_key,
        cache_path=ROOT / 'translation_work/cache/embeddings/cle.sqlite3', timeout=120)
    baseline = load_memory(OUT / 'inputs/all_feedback/memory.jsonl')
    jobs = ([(i, arm) for i in m['learning'][:(2 if stage == 'smoke' else 12)] for arm in ARMS]
            if stage != 'full' else [(i, 'Lall') for i in m['learning'][12:]])
    if stage != 'full':
        rng = random.Random(20261020)
        jobs = [pair for start in range(0, len(jobs), 2) for pair in rng.sample(jobs[start:start+2], 2)]
    done = {(r['task_id'], r['arm']) for r in records()}
    jobs = [j for j in jobs if j not in done]
    blocks = [jobs] if stage != 'full' else [jobs[k:k+12] for k in range(0, len(jobs), 12)]
    meta['status'] = 'running_' + stage
    write(OUT / 'run_metadata.json', meta)
    fatal = []
    started = perf_counter()
    for block in blocks:
        if not block:
            continue
        block_key = 'pilot12' if stage != 'full' else block[0][0]
        mask_path = OUT / 'exposure_masks' / (block_key + '.json')
        if mask_path.exists():
            visits = read(mask_path)
        else:
            if stage == 'full':
                report()
                current = load_memory(OUT / 'Lall/all_feedback/frozen/m_star_q.jsonl')
            else:
                current = baseline
            visits = {n.invariant_id: n.q_visits for n in current}
            write(mask_path, visits)

        def job(item):
            identifier, arm = item
            initial_path = OUT / 'initials' / (identifier + '.json')
            initial = read(initial_path)
            bank = copy.deepcopy(baseline)
            for n in bank:
                n.q_visits = visits[n.invariant_id]
            request, tracker = budget.bind(identifier, arm)
            start = perf_counter()
            native_row = run_one('PLT', tasks[identifier], 'P7', request, {'full': bank}, embedding,
                retrieval_mode='semantic_llm', delta=-1, lambda_q=.5,
                max_experiences=3 if arm == 'L3' else None, candidate_order='coverage',
                initial_analysis=copy.deepcopy(initial['initial_analysis']))
            write(OUT / 'native_rows' / arm / (identifier + '.json'), native_row)
            row = record_result(copy.deepcopy(native_row), tasks[identifier], 'Q0', 'D_init', perf_counter() - start)
            row.update(arm=arm, protocol=PROTOCOL, shared_initial_error=initial.get('error_type'),
                accounting={k: tracker.snapshot()['total'][k] for k in core.FIELDS}, exposure_mask=str(mask_path.relative_to(OUT)))
            assert body(bank) == body(baseline)
            write(OUT / 'task_rows' / arm / (identifier + '.json'), row)
            print(json.dumps({'done': len(list((OUT / 'task_rows').glob('*/*.json'))), 'arm': arm,
                'task_id': identifier, 'Joint': row['final'].get('joint'), 'calls': budget.calls,
                'tokens': budget.tokens}), flush=True)
            return row

        with ThreadPoolExecutor(max_workers=p['workers']) as executor:
            for start in range(0, len(block), p['workers']):
                if budget.stopped.is_set() or fatal:
                    break
                futures = [executor.submit(job, item) for item in block[start:start+p['workers']]]
                for future in as_completed(futures):
                    fatal += inspect(future.result())
        snapshot = report()
        fatal += [r['issue'] for r in snapshot['fatal_issues']]
        if fatal or budget.stopped.is_set():
            break
    meta = read(OUT / 'run_metadata.json')
    meta['status'] = 'budget_stop' if budget.stopped.is_set() else 'technical_stop' if fatal else 'completed_' + stage
    meta['segments'].append({'stage': stage, 'seconds': perf_counter()-started, 'fatal': sorted(set(fatal)),
                             'budget_reason': budget.reason})
    write(OUT / 'run_metadata.json', meta)
    summary = report()
    if stage in {'smoke', 'pilot'}:
        count = 2 if stage == 'smoke' else 12
        selected_rows = [r for r in records() if r['task_id'] in m['learning'][:count]]
        gate = {'passed': meta['status'] == 'completed_' + stage and len(selected_rows) == count*2
                and not summary['fatal_issues'] and all(c['retrieval_completed'] for c in summary['shared_candidates']),
                'P7_runs': len(selected_rows), 'performance_gate': False,
                'unlimited_over3_attempts': sum(len(a.get('generation', {}).get('retrieved_cards', [])) > 3
                    for r in selected_rows if r['arm'] == 'Lall' for a in r['attempts']),
                'fatal': summary['fatal_issues']}
        write(OUT / (stage + '_gate.json'), gate)
        write(CURATED / (stage + '_gate.json'), gate)
    write(OUT / (stage + '_summary.json'), summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'smoke', 'pilot', 'full', 'report'])
    command = parser.parse_args().command
    result = prepare() if command == 'prepare' else report() if command == 'report' else run(command)
    print(json.dumps({k: result[k] for k in ('status', 'P7_runs', 'arms', 'cost') if k in result}, ensure_ascii=False), flush=True)

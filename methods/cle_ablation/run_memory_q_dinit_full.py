"""用户要求的D_init全303题单轮覆盖学习；取消收益门，保留原P7和真实采用授信。"""
from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_dinit_coverage as core
from methods.cle_ablation.run_memory_q_dinit import body, credit_rows
from methods.cle_ablation.run_memory_q import prepare_shared_initial, record_result
from methods.cle_ablation.runner import load_memory, run_one
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_memory_q_study import _write_memory
from methods.sct_trajectory.semantic_retrieval import MAX_CARD_CHARS, card_embedding_text, _digest

CONFIG = ROOT / 'configs/cle_dinit_full_learning_20261020'
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_full_learning_v4'
CURATED = ROOT / 'results/curated/cle_dinit_full_learning_20261020'
OLD = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_q_coverage_v3'
PROTOCOL = 'cle-dinit-full303-user-directed-v4'
read, jsonl = core.read, core.jsonl


def configure_helpers():
    """仅在本进程绑定旧入口的请求预算/向量记录器输出，不修改任何旧源码或产物。"""
    core.OUT = OUT
    core.STAGES = {'full': (303, 'full303')}


def verify():
    meta = read(OUT / 'run_metadata.json')
    for name, expected in meta['identity'].items():
        if core.digest(ROOT / name) != expected:
            raise RuntimeError('locked_input_or_source_changed:' + name)
    return meta


def prepare():
    if (OUT / 'run_metadata.json').exists():
        return verify()
    if shutil.disk_usage(ROOT.anchor).free < 3 * 1024**3:
        raise RuntimeError('insufficient_disk_space')
    preflight = read(OUT / 'preflight_summary.json')
    if preflight['eligible'] != 303 or preflight['failures']:
        raise RuntimeError('data_repair_or_preflight_incomplete')
    protocol = read(CONFIG / 'protocol.json')
    manifest, tasks = read(CONFIG / 'manifest.json'), read(CONFIG / 'tasks.json')
    source = load_memory(ROOT / protocol['baseline_memory'])
    assert len(manifest['learning']) == len(set(manifest['learning'])) == 303
    assert len(source) == 1939 and sum(n.q_visits > 0 for n in source) == 436
    CURATED.mkdir(parents=True, exist_ok=True)
    for name in ('protocol.json', 'manifest.json', 'tasks.json'):
        write(OUT / name, read(CONFIG / name))
    _write_memory(OUT / 'input_memory.jsonl', source)
    for name, key in [('origins.json', 'origins_source'), ('input_family_support.json', 'baseline_family_support')]:
        write(OUT / name, read(ROOT / protocol[key]))
    paths = [Path(__file__), CONFIG / 'repair.py', CONFIG / 'protocol.json', CONFIG / 'manifest.json', CONFIG / 'tasks.json',
             ROOT / protocol['baseline_memory'], ROOT / protocol['baseline_family_support'],
             ROOT / protocol['origins_source'], ROOT / 'data/external/secodeplt/secodeplt/data.json',
             ROOT / 'methods/cle_ablation/run_memory_q_dinit_coverage.py',
             ROOT / 'methods/cle_ablation/run_memory_q_dinit.py', ROOT / 'methods/cle_ablation/run_memory_q.py',
             ROOT / 'methods/cle_ablation/runner.py', ROOT / 'methods/sct_trajectory/context_pipeline.py',
             ROOT / 'methods/sct_trajectory/semantic_retrieval.py', ROOT / 'methods/sct_trajectory/memory_q.py',
             ROOT / 'methods/sct_trajectory/selector_protocol.py', ROOT / 'methods/sct_agent/validation_evidence.py']
    identity = {str(p.relative_to(ROOT)): core.digest(p) for p in paths}
    for p in paths:
        if p.suffix == '.py':
            target = OUT / 'source_snapshot' / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
    old_tasks = read(OLD / 'tasks.json')
    reuse = []
    for i in read(OLD / 'manifest.json')['probe']:
        path = OLD / 'task_rows/L1' / (i + '.json')
        if i not in protocol['repaired_task_ids'] and old_tasks[i] == tasks[i]:
            row = read(path)
            row.update(protocol=PROTOCOL, stage='first12', reused_execution=True,
                       execution_source=str(path.relative_to(ROOT)), origin_protocol=row['protocol'])
            write(OUT / 'task_rows/L1' / (i + '.json'), row)
            for folder in ('initials', 'native_rows/L1'):
                origin = OLD / folder / (i + '.json')
                dest = OUT / folder / (i + '.json')
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(origin, dest)
            reuse.append(i)
    write(OUT / 'run_metadata.json', {'protocol': PROTOCOL, 'status': 'prepared', 'identity': identity,
          'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
          'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'reused_tasks': reuse, 'segments': [], 'new_Dgate_generation': False,
          'performance_continuation_gate': False, 'python': sys.executable})
    print(json.dumps({'prepared': True, 'tasks': 303, 'reuse': reuse, 'new_P7_planned': 303 - len(reuse)}), flush=True)
    return verify()


def records():
    by_id = {p.stem: read(p) for p in (OUT / 'task_rows/L1').glob('*.json')}
    return [by_id[i] for i in read(OUT / 'manifest.json')['learning'] if i in by_id]


def inspect(row):
    """代码超时/语法错误是本轮模型结果，不因其正确率低而中止全量学习。"""
    issues = core.inspect(row)
    workers = [a.get('validation', {}).get('evidence', {}).get('metadata', {}).get('worker_error', {})
               for a in row.get('attempts', [])]
    if 'validation_worker_error' in issues and all(not e or e.get('type') in {'timeout', 'SyntaxError', 'IndentationError'} for e in workers):
        issues.remove('validation_worker_error')
    return issues


def report():
    meta = verify()
    rows, source = records(), load_memory(OUT / 'input_memory.jsonl')
    manifest, origins = read(OUT / 'manifest.json'), read(OUT / 'origins.json')
    requests = [read(p) for p in (OUT / 'requests').glob('*.json')]
    embeddings = [read(p) for p in (OUT / 'embedding_requests').glob('*.json')]
    scores, selected, adopted = [], set(), set()
    for row in rows:
        f = row['final']
        for attempt in row['attempts']:
            g = attempt.get('generation', {})
            selected.update(c['invariant_id'] for c in g.get('retrieved_cards', []))
            adopted.update(c['invariant_id'] for c in g.get('cards', []))
        scores.append({'task_id': row['task_id'], 'family_id': row['family_id'], 'reused': row.get('reused_execution', False),
                       **{k: f.get(k) for k in ('measured', 'functional', 'security', 'joint')},
                       'workflow_completed': f.get('generation', {}).get('workflow_completed'),
                       'attempts': len(row['attempts']), 'execution_tokens': row['accounting']['total_tokens']})
    summary = {'protocol': PROTOCOL, 'status': meta['status'], 'planned': 303, 'executed': len(rows),
               'new_P7_runs': sum(not r.get('reused_execution') for r in rows), 'reused_P7_runs': len(meta['reused_tasks']),
               'code_attempts': sum(len(r['attempts']) for r in rows),
               'measured': sum(bool(s['measured']) for s in scores),
               'F': sum(bool(s['measured'] and s['functional']) for s in scores),
               'S': sum(bool(s['measured'] and s['security']) for s in scores),
               'Joint': sum(bool(s['measured'] and s['joint']) for s in scores),
               'final_workflows': sum(bool(s['workflow_completed']) for s in scores),
               'cards': len(source), 'baseline_learned': 436,
               'selected_unique': len(selected), 'adopted_unique': len(adopted),
               'adopted_occurrences': sum(len({c['invariant_id'] for c in a.get('generation', {}).get('cards', [])}) for r in rows for a in r['attempts']),
               'new_cost': {'LLM': core.usage_total(requests),
                   'embedding': {k: sum(e.get(k, 0) for e in embeddings) for k in ('calls', 'total_tokens', 'failures', 'usage_missing_calls')},
                   'actual_bill_CNY': None, 'native_HTTP_retries': 'not fully observed'},
               'credit': {}, 'fatal_issues': [], 'new_Dgate_generation': False,
               'interpretation': 'training feedback only; no performance gate or evidence of Q generation benefit'}
    all_events = []
    for policy in ('all_feedback', 'cross_family'):
        credit_input = copy.deepcopy(rows)
        for row in credit_input:
            if row.get('shared_initial_error'):
                row['attempts'][0].setdefault('generation', {})['workflow_completed'] = False
            for attempt in row['attempts']:
                if not attempt.get('measured'):
                    attempt.setdefault('generation', {})['workflow_completed'] = False
        bank, events, stats = credit_rows(credit_input, source, origins, manifest, policy)
        for e in events:
            e.update(protocol=PROTOCOL, arm='L1')
        all_events.extend(events)
        stats.update(positive_Q=sum(n.q_value > 0 for n in bank), negative_Q=sum(n.q_value < 0 for n in bank),
                     zero_Q=sum(n.q_value == 0 for n in bank), positive_updates=sum(e['credited'] and e['reward'] == 1 for e in events),
                     negative_updates=sum(e['credited'] and e['reward'] == -1 for e in events))
        summary['credit'][policy] = stats
        _write_memory(OUT / policy / 'frozen/m_star_q.jsonl', bank)
        jsonl(OUT / policy / 'memory_q_events.jsonl', events)
        support = {k: set(v) for k, v in read(OUT / 'input_family_support.json').items()}
        for e in events:
            if e['credited']:
                support.setdefault(e['invariant_id'], set()).add(e['family_id'])
        write(OUT / policy / 'q_family_support.json', {k: sorted(v) for k, v in support.items()})
    summary['fatal_issues'] = [{'task_id': r['task_id'], 'reason': issue} for r in rows for issue in inspect(r)]
    jsonl(OUT / 'rows.jsonl', rows)
    jsonl(OUT / 'memory_q_events.all_views.jsonl', all_events)
    for p in (OUT, CURATED):
        write(p / 'summary.json', summary)
    for filename, values in [('scores.csv', scores), ('reward_events.csv', all_events)]:
        if values:
            with (CURATED / filename).open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(values[0]))
                writer.writeheader()
                writer.writerows(values)
    return summary


def run():
    configure_helpers()
    meta = prepare()
    if meta['status'] in {'budget_stop', 'technical_stop'}:
        raise RuntimeError('recorded_runtime_stop_requires_review')
    protocol, manifest, tasks = read(OUT / 'protocol.json'), read(OUT / 'manifest.json'), read(OUT / 'tasks.json')
    core.setup_environment(protocol)
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    native = _requester(protocol['model'], 60, max_tokens=4096, max_inflight=protocol['workers'], thinking='disabled')
    budget = core.Budget(protocol, 'full', native)
    embedding = core.StudyEmbedding(protocol, 'full', model=protocol['embedding_model'], key_loader=load_key,
                                   cache_path=ROOT / 'translation_work/cache/embeddings/cle.sqlite3', timeout=120)
    source = load_memory(OUT / 'input_memory.jsonl')
    legal = [n for n in source if n.status in {'active', 'provisional', 'consolidated'}
             and 'python' in (n.language_leaves or {}) and len(card_embedding_text(n)) <= MAX_CARD_CHARS]
    if any(embedding._load_cached(_digest(card_embedding_text(n))) is None for n in legal):
        raise RuntimeError('cold_card_cache')
    prior_end = 0
    for end in manifest['checkpoints']:
        block = manifest['learning'][prior_end:end]
        prior_end = end
        done = {r['task_id'] for r in records()}
        pending = [i for i in block if i not in done]
        if not pending:
            continue
        mask_path = OUT / f'exposure_mask_{end}.json'
        if mask_path.exists():
            visits = read(mask_path)
        else:
            if end == 12:
                mask_bank = source
            else:
                report()
                mask_bank = load_memory(OUT / 'cross_family/frozen/m_star_q.jsonl')
            visits = {n.invariant_id: n.q_visits for n in mask_bank}
            write(mask_path, visits)
        meta = verify()
        meta['status'] = f'running_{end}'
        write(OUT / 'run_metadata.json', meta)

        def job(identifier):
            bank = copy.deepcopy(source)
            for n in bank:
                n.q_visits = visits[n.invariant_id]
            ipath = OUT / 'initials' / (identifier + '.json')
            if ipath.exists():
                initial = read(ipath)
            else:
                request, tracker = budget.bind(identifier, 'initial')
                initial = prepare_shared_initial(tasks[identifier], request)
                initial['accounting'] = {k: tracker.snapshot()['total'][k] for k in core.FIELDS}
                write(ipath, initial)
            request, tracker = budget.bind(identifier, 'L1')
            start = perf_counter()
            native_row = run_one('PLT', tasks[identifier], 'P7', request, {'full': bank}, embedding,
                retrieval_mode='semantic_llm', delta=-1, lambda_q=.5, max_experiences=3,
                candidate_order='coverage', initial_analysis=copy.deepcopy(initial['initial_analysis']))
            write(OUT / 'native_rows/L1' / (identifier + '.json'), native_row)
            row = record_result(copy.deepcopy(native_row), tasks[identifier], 'Q0', 'D_init', perf_counter() - start)
            row.update(arm='L1', protocol=PROTOCOL, stage=str(end), reused_execution=False,
                       shared_initial_error=initial.get('error_type'),
                       accounting={k: tracker.snapshot()['total'][k] for k in core.FIELDS})
            assert body(bank) == body(source)
            write(OUT / 'task_rows/L1' / (identifier + '.json'), row)
            print(json.dumps({'done': len(list((OUT / 'task_rows/L1').glob('*.json'))), 'total': 303,
                              'task_id': identifier, 'Joint': row['final']['joint'],
                              'calls': budget.calls, 'tokens': budget.tokens}), flush=True)
            return row

        started, fatal = perf_counter(), []
        batches = []
        remaining = list(pending)
        if end == 12:
            batches.append(remaining[:2])
            remaining = remaining[2:]
        batches.extend(remaining[offset:offset + protocol['workers']] for offset in range(0, len(remaining), protocol['workers']))
        with ThreadPoolExecutor(max_workers=protocol['workers']) as executor:
            # 批内同一覆盖掩码；只对真正的API/验证器/协议故障停发，不检查正确率。
            for batch in batches:
                if budget.stopped.is_set() or fatal:
                    break
                futures = [executor.submit(job, i) for i in batch]
                for future in as_completed(futures):
                    fatal.extend(inspect(future.result()))
        meta = read(OUT / 'run_metadata.json')
        meta['segments'].append({'checkpoint': end, 'seconds': perf_counter() - started, 'fatal': fatal})
        meta['status'] = 'budget_stop' if budget.stopped.is_set() else 'technical_stop' if fatal else f'completed_{end}'
        write(OUT / 'run_metadata.json', meta)
        snapshot = report()
        write(OUT / f'checkpoint_{end}_summary.json', snapshot)
        if budget.stopped.is_set() or fatal:
            return snapshot
    meta = read(OUT / 'run_metadata.json')
    meta['status'] = 'completed_full303' if len(records()) == 303 else 'incomplete'
    write(OUT / 'run_metadata.json', meta)
    return report()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'report'])
    args = parser.parse_args()
    result = globals()[args.command]()
    if args.command != 'prepare':
        print(json.dumps({k: result[k] for k in ('status', 'executed', 'new_P7_runs', 'Joint', 'new_cost')}), flush=True)

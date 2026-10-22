"""修订32题原P7观察学习；冻结后仅回放历史D_gate查询，不重新选卡或生成代码。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation.runner import load_memory, run_one
from methods.cle_ablation.run_memory_q import learn_q, record_result
from methods.cle_ablation.run_memory_q_gate_q0 import account_request
from methods.sct_trajectory.memory_q import rank_candidates
from methods.sct_trajectory.run_memory_q_study import _write_memory

CONFIG = Path(__file__).resolve().parent
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_dgrow_url_q_learning_v1'
CURATED = ROOT / 'results/curated/cle_dgrow_url_q_learning_20261020'
PROTOCOL = 'cle-repaired32-observer-cap3-screened-Q-v1'
REPAIR = ROOT / 'configs/cle_dgrow_url_repair_20261019'
BASE = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/pro_closeout/qualification_replay'
OLD = ROOT / 'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
GATE = ROOT / 'translation_work/diagnostics/20261019/cle_memory_q/full_gate_cap3_v4/rows.jsonl'
FIELDS = ('calls', 'prompt_tokens', 'completion_tokens', 'total_tokens', 'cached_tokens', 'usage_missing', 'errors')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    if not Path(path).exists():
        return
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='')


def append(path, value):
    with path.open('a', encoding='utf-8', newline='') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        stream.flush()


def write_csv(path, values):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def bodies(nodes):
    return [{k: v for k, v in n.to_dict().items() if k not in {'q_value', 'q_visits'}} for n in nodes]


def trace_of(attempt):
    """采用当前检索降级轨迹；否则读顶层或一致的卡内审计，不把上一轮成功当本轮成功。"""
    for stage in attempt.get('generation', {}).get('stages', []):
        if stage['stage'] == 'retrieval' and stage['status'] == 'degraded':
            return stage.get('retrieval_trace') or {'status': 'error'}
    if attempt.get('retrieval_trace'):
        return attempt['retrieval_trace']
    cards = attempt.get('generation', {}).get('retrieved_cards', [])
    audits = [c['retrieval_audit'] for c in cards if c.get('retrieval_audit')]
    if audits:
        assert all(a == audits[0] for a in audits)
        assert audits[0]['selected_ids'] == [c['invariant_id'] for c in cards]
        return audits[0]
    return {}


def credit_rows(source, items, support):
    """顺序按固定题ID及c0/c1；Q不影响前向，批末授信与逐题观察更新等价。"""
    nodes = copy.deepcopy(source)
    mapping = {n.invariant_id: n for n in nodes}
    families = {k: set(v) for k, v in support.items()}
    events = []
    for row in sorted(items, key=lambda r: int(r['task_id'])):
        for event in learn_q(row, mapping, .3):
            event.update(protocol=PROTOCOL)
            events.append(event)
            if event.get('invariant_id') and event.get('reward') is not None:
                families.setdefault(event['invariant_id'], set()).add(row['family_id'])
    assert bodies(source) == bodies(nodes)
    return nodes, events, {k: sorted(v) for k, v in families.items()}


def prepare():
    """仅复用修复v2有效回执并冻结本轮32题与416卡起点，不进行模型调用。"""
    tasks = read(REPAIR / 'repaired_tasks.json')
    controls = read(ROOT / 'results/curated/cle_dgrow_url_repair_20261019/qualification.json')
    ids = sorted((str(t['index']) for t in tasks), key=int)
    pools = read(OLD / 'input_pools.json')
    assert len(ids) == len(set(ids)) == 32
    assert set(ids) <= {str(t['task_id']) for t in pools['replay']}
    assert not set(ids) & {str(t['task_id']) for t in pools['audit']}
    assert len(controls) == 32 and all(r['reward_eligible_new_protocol'] for r in controls)
    nodes = load_memory(BASE / 'diagnostic_qualification_screened_Q.jsonl')
    assert len(nodes) == 1939 and sum(n.q_visits > 0 for n in nodes) == 416
    if shutil.disk_usage(ROOT.anchor).free < 1024**3:
        raise RuntimeError('insufficient_disk_space')
    OUT.mkdir(parents=True, exist_ok=False)
    CURATED.mkdir(parents=True, exist_ok=True)
    manifest = {'protocol': PROTOCOL, 'tasks': ids, 'probe': ['675', '1080'],
                'families': len({t['family_id'] for t in tasks}), 'pool': 'D_grow',
                'order': 'numeric original task ID, then native attempt c0/c1',
                'observer': True, 'candidate_order': None, 'max_experiences': 3,
                'new_Dgate_generation': False, 'new_cards': False, 'rounds': 1,
                'alpha': .3, 'delta': -1, 'lambda_q': .5, 'max_code_attempts': 2,
                'model': 'deepseek-v3.2', 'thinking': 'disabled', 'temperature': 0,
                'max_tokens': 4096, 'selector_max_tokens': 256,
                'embedding_model': 'text-embedding-3-large', 'workers': 2,
                'LLM_token_stop': 4000000, 'LLM_logical_request_stop': 400,
                'base_memory': str((BASE / 'diagnostic_qualification_screened_Q.jsonl').relative_to(ROOT)),
                'repaired_tasks': str((REPAIR / 'repaired_tasks.json').relative_to(ROOT)),
                'qualification_source': 'cle_dgrow_url_repair_v2: 32 references Joint, 32 vulnerable security fail',
                'request': 'complete repaired32 Q learning and analyze impact on historic Dgate card selection'}
    write(CONFIG / 'protocol.json', manifest)
    write(OUT / 'manifest.json', manifest)
    write(OUT / 'tasks.json', tasks)
    _write_memory(OUT / 'input_memory.jsonl', nodes)
    write(OUT / 'input_family_support.json', read(BASE / 'diagnostic_q_family_support.json'))
    source_paths = [Path(__file__), ROOT / 'methods/cle_ablation/runner.py',
                    ROOT / 'methods/cle_ablation/run_memory_q.py',
                    ROOT / 'methods/sct_trajectory/context_pipeline.py',
                    ROOT / 'methods/sct_trajectory/semantic_retrieval.py',
                    ROOT / 'methods/sct_trajectory/selector_protocol.py',
                    ROOT / 'methods/sct_trajectory/memory_q.py',
                    ROOT / 'methods/sct_trajectory/run_closed_loop.py']
    for source in source_paths:
        target = OUT / 'source_snapshot' / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    meta = {'protocol': PROTOCOL, 'status': 'prepared', 'manifest': manifest,
            'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
            'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'working_source_snapshot': True, 'backend': 'original validate_and_state local python -I timeout20',
            'historical_data_and_memory_modified': False}
    write(OUT / 'run_metadata.json', meta)
    print(json.dumps({'prepared': True, 'tasks': len(ids), 'base_visited': 416}), flush=True)


def run(probe=False):
    """固定32题观察前向；失败也先落原件，已落盘任务不重复付费。"""
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    manifest = read(OUT / 'manifest.json')
    tasks = {str(t['index']): t for t in read(OUT / 'tasks.json')}
    source = load_memory(OUT / 'input_memory.jsonl')
    before = [n.to_dict() for n in source]
    existing = list(rows(OUT / 'rows.jsonl'))
    wanted = manifest['probe'] if probe else manifest['tasks']
    done = {r['task_id'] for r in existing}
    pending = [i for i in wanted if i not in done]
    if not pending:
        return learn()
    native = _requester('deepseek-v3.2', 60, max_tokens=4096, max_inflight=2, thinking='disabled')
    embedding = EmbeddingClient(model='text-embedding-3-large', key_loader=load_key,
        cache_path=ROOT / 'translation_work/cache/embeddings/cle.sqlite3', timeout=120)
    lock, stopped = threading.Lock(), threading.Event()
    budget = Counter({k: sum(r['accounting']['total'][k] for r in existing) for k in FIELDS})
    prior_calls = budget['calls']
    inflight_calls = 0
    def request(prompt):
        nonlocal inflight_calls
        with lock:
            if stopped.is_set() or prior_calls + inflight_calls >= 400 or budget['total_tokens'] >= 4000000:
                stopped.set()
                raise RuntimeError('experiment_budget_or_auth_stop')
            inflight_calls += 1
        try:
            response = native(prompt)
        except Exception as exc:
            if any(d.get('http_status') in (401, 403, 429) for d in getattr(exc, 'safe_diagnostics', []) if isinstance(d, dict)):
                stopped.set()
            raise
        with lock:
            budget['total_tokens'] += int((response.get('usage') or {}).get('total_tokens') or 0)
        return response
    def job(identifier):
        started = perf_counter()
        counted, tracker = account_request(request, 'repaired32_observer')
        row = run_one('PLT', tasks[identifier], 'P7', counted, {'full': copy.deepcopy(source)}, embedding,
                      retrieval_mode='semantic_llm', delta=-1, lambda_q=.5,
                      max_experiences=3, candidate_order=None)
        record_result(row, tasks[identifier], 'Q0', 'D_grow', perf_counter() - started)
        row.update(arm='O32', protocol=PROTOCOL, retrieval_mode='native_semantic_llm_observer_cap3',
                   accounting={'total': {k: tracker.snapshot()['total'][k] for k in FIELDS},
                               'by_label': tracker.snapshot()['by_label']})
        assert 1 <= len(row['attempts']) <= 2
        assert not (len(row['attempts']) == 2 and row['attempts'][0].get('joint'))
        for a in row['attempts']:
            g = a.get('generation', {})
            selected = {c['invariant_id'] for c in g.get('retrieved_cards', [])}
            assert len(selected) <= 3
            assert {c['invariant_id'] for c in g.get('cards', [])} <= selected
        return row
    meta = read(OUT / 'run_metadata.json'); meta['status'] = 'running_probe' if probe else 'running_all32'
    write(OUT / 'run_metadata.json', meta)
    started = perf_counter()
    # 每批两个，遇到认证/预算停止后不再派发剩余任务。
    with ThreadPoolExecutor(max_workers=2) as executor:
        for offset in range(0, len(pending), 2):
            if stopped.is_set():
                break
            futures = [executor.submit(job, i) for i in pending[offset:offset+2]]
            for future in as_completed(futures):
                row = future.result()
                durable = OUT / 'task_records' / (row['task_id'] + '.json')
                write(durable, row)
                append(OUT / 'rows.jsonl', row)
                existing.append(row)
                print(json.dumps({'done': len(existing), 'task': row['task_id'],
                    'F': row['final']['functional'], 'S': row['final']['security'], 'Joint': row['final']['joint'],
                    'workflow_completed': row['final'].get('generation', {}).get('workflow_completed'),
                    'calls': row['accounting']['total']['calls'], 'tokens': row['accounting']['total']['total_tokens']}), flush=True)
    assert before == [n.to_dict() for n in source]
    append(OUT / 'embedding_segments.jsonl', {'stage': 'probe' if probe else 'remaining', **embedding.usage})
    meta['status'] = 'budget_or_auth_stopped' if stopped.is_set() else ('probe_complete' if probe else 'generation_complete')
    meta.setdefault('segments', []).append({'seconds': perf_counter()-started, 'new_records': len(existing)-len(done)})
    write(OUT / 'run_metadata.json', meta)
    return learn()


def learn():
    """从不变起点重放当前已落盘记录，避免恢复时重复授信；不使用D_gate结果。"""
    source = load_memory(OUT / 'input_memory.jsonl')
    items = list(rows(OUT / 'rows.jsonl'))
    assert len(items) == len({r['task_id'] for r in items})
    nodes, events, supports = credit_rows(source, items, read(OUT / 'input_family_support.json'))
    _write_memory(OUT / 'frozen/m_star_q.jsonl', nodes)
    write(OUT / 'q_family_support.json', supports)
    with (OUT / 'memory_q_events.jsonl').open('w', encoding='utf-8', newline='') as stream:
        stream.writelines(json.dumps(e, ensure_ascii=False)+'\n' for e in events)
    valid = [e for e in events if e.get('invariant_id') and e.get('reward') is not None]
    write_csv(CURATED / 'reward_events.csv', [{k: e.get(k) for k in
        ('task_id', 'family_id', 'attempt', 'invariant_id', 'reward', 'q_before', 'q_after', 'q_visits', 'skip_reason')}
        for e in events])
    old = {n.invariant_id: n for n in source}
    changed = [{'invariant_id': n.invariant_id, 'cwe': str(n.cwe), 'Q_before': old[n.invariant_id].q_value,
                'Q_after': n.q_value, 'visits_before': old[n.invariant_id].q_visits, 'visits_after': n.q_visits,
                'newly_learned': old[n.invariant_id].q_visits == 0 and n.q_visits > 0,
                'positive_events': sum(e['reward'] > 0 for e in valid if e['invariant_id'] == n.invariant_id),
                'negative_events': sum(e['reward'] < 0 for e in valid if e['invariant_id'] == n.invariant_id)}
               for n in nodes if (n.q_value, n.q_visits) != (old[n.invariant_id].q_value, old[n.invariant_id].q_visits)]
    if changed:
        write_csv(CURATED / 'changed_cards.csv', changed)
    counts = {k: sum(bool(r['final'].get(k)) for r in items) for k in ('functional','security','joint','measured')}
    totals = {k: sum(r['accounting']['total'][k] for r in items) for k in FIELDS}
    issues = [{'task_id': r['task_id'], 'attempt': a['attempt'],
               'error': a.get('error_type') or a.get('generation', {}).get('error_type'),
               'workflow_completed': bool(a.get('generation', {}).get('workflow_completed')),
               'measured': bool(a.get('measured'))}
              for r in items for a in r['attempts'] if not a.get('measured') or not a.get('generation', {}).get('workflow_completed')]
    cwe_coverage = {}
    for cwe in sorted({str(n.cwe) for n in nodes}):
        members = [n for n in nodes if str(n.cwe) == cwe]
        cwe_coverage[cwe] = {'cards': len(members),
            'visited_before': sum(old[n.invariant_id].q_visits > 0 for n in members),
            'visited_after': sum(n.q_visits > 0 for n in members),
            'positive_Q_after': sum(n.q_value > 0 for n in members),
            'negative_Q_after': sum(n.q_value < 0 for n in members)}
    summary = {'protocol': PROTOCOL, 'planned': 32, 'executed': len(items), 'final': counts,
        'first': {k: sum(bool(r['attempts'][0].get(k)) for r in items) for k in ('functional','security','joint','measured')},
        'repair_joint_rescues': sum(not r['attempts'][0].get('joint') and bool(r['final'].get('joint')) for r in items),
        'attempts': sum(len(r['attempts']) for r in items), 'valid_card_updates': len(valid),
        'positive_updates': sum(e['reward'] > 0 for e in valid), 'negative_updates': sum(e['reward'] < 0 for e in valid),
        'changed_cards': len(changed), 'new_cards_learned': sum(c['newly_learned'] for c in changed),
        'visited_before': sum(n.q_visits > 0 for n in source), 'visited_after': sum(n.q_visits > 0 for n in nodes),
        'coverage_after': sum(n.q_visits > 0 for n in nodes)/len(nodes),
        'positive_Q_after': sum(n.q_value > 0 for n in nodes), 'negative_Q_after': sum(n.q_value < 0 for n in nodes),
        'total_llm_usage': totals, 'embedding_segments': list(rows(OUT / 'embedding_segments.jsonl')),
        'tasks_with_valid_credit': len({e['task_id'] for e in valid}),
        'complete_final_workflows': sum(bool(r['final'].get('generation', {}).get('workflow_completed')) for r in items),
        'complete_final_joint': sum(bool(r['final'].get('joint')) and bool(r['final'].get('generation', {}).get('workflow_completed')) for r in items),
        'completed_workflow_attempts': sum(bool(a.get('generation', {}).get('workflow_completed')) for r in items for a in r['attempts']),
        'by_card_CWE': cwe_coverage,
        'money_paid': None, 'issues': issues, 'new_Dgate_API_calls': 0, 'new_Dgate_Joint': None}
    write(OUT / 'summary.json', summary); write(CURATED / 'learning_summary.json', summary)
    write_csv(CURATED / 'learning_scores.csv', [{'task_id': r['task_id'], 'family_id': r['family_id'], 'cwe': r['cwe'],
        **{k: r['final'].get(k) for k in ('functional','security','joint','measured')},
        'workflow_completed': bool(r['final'].get('generation', {}).get('workflow_completed')),
        'attempts': len(r['attempts']), 'calls': r['accounting']['total']['calls'], 'tokens': r['accounting']['total']['total_tokens']}
        for r in sorted(items, key=lambda r: int(r['task_id']))])
    print(json.dumps({k: summary[k] for k in ('executed','final','valid_card_updates','changed_cards','new_cards_learned','visited_after')}), flush=True)
    return summary


def replay():
    """固定历史查询、候选及余弦，分离资格屏蔽与新增32题的排序影响；无D_gate API。"""
    summary = read(OUT / 'summary.json')
    assert summary['executed'] == 32, 'finish_32_before_gate_history_analysis'
    banks = {'historical_M1': load_memory(OLD / 'observe/frozen/m_star_q.jsonl'),
             'screened_before32': load_memory(OUT / 'input_memory.jsonl'),
             'after32': load_memory(OUT / 'frozen/m_star_q.jsonl')}
    assert bodies(banks['historical_M1']) == bodies(banks['screened_before32']) == bodies(banks['after32'])
    values = {k: {n.invariant_id: n.q_value for n in v} for k, v in banks.items()}
    visits = {k: {n.invariant_id: n.q_visits for n in v} for k, v in banks.items()}
    changed = {i for i in values['after32'] if values['after32'][i] != values['screened_before32'][i]}
    card_cwe = {n.invariant_id: str(n.cwe) for n in banks['after32']}
    affected_cwe = Counter(card_cwe[i] for i in changed)
    query_rows, skipped = [], []
    historical_exposure = defaultdict(Counter)
    for row in rows(GATE):
        for a in row['attempts']:
            for scope in ['all_attempts'] + (['first_attempt'] if a['attempt'] == 0 else []):
                for stage, field in [('selected', 'retrieved_cards'), ('adopted', 'cards')]:
                    ids = [c['invariant_id'] for c in a.get('generation', {}).get(field, [])]
                    bucket = historical_exposure[(row['arm'], scope, stage)]
                    bucket['records'] += 1
                    bucket['card_occurrences'] += len(ids)
                    bucket['changed_Q_occurrences'] += sum(i in changed for i in ids)
                    bucket['visited_before_occurrences'] += sum(visits['screened_before32'][i] > 0 for i in ids)
                    bucket['visited_after_occurrences'] += sum(visits['after32'][i] > 0 for i in ids)
                    bucket['records_with_changed_Q'] += any(i in changed for i in ids)
        if row['arm'] != 'Q2':
            continue
        for a in row['attempts']:
            t = trace_of(a)
            if 'scores' not in t or 'presented_candidate_ids' not in t or t.get('candidate_order') != 'q':
                skipped.append({'task_id': row['task_id'], 'attempt': a['attempt'], 'reason': 'no_saved_Q_query'})
                continue
            options = {'delta': t['delta'], 'lambda_q': t['lambda_q'], 'limit': None}
            orders = {name: [s['id'] for s in rank_candidates(t['scores'], q, **options)] for name, q in values.items()}
            assert orders['historical_M1'] == t['presented_candidate_ids'], (row['task_id'], a['attempt'])
            before, after = orders['screened_before32'], orders['after32']
            selected = [c['invariant_id'] for c in a.get('generation', {}).get('retrieved_cards', [])]
            adopted = [c['invariant_id'] for c in a.get('generation', {}).get('cards', [])]
            query_rows.append({'task_id': row['task_id'], 'family_id': row['family_id'], 'cwe': row['cwe'],
                'attempt': a['attempt'], 'trace_status': t.get('status'), 'candidates': len(after),
                'qualification_order_changed': orders['historical_M1'] != before,
                'new32_order_changed': before != after,
                'new32_top3_set_changed': set(before[:3]) != set(after[:3]),
                'M1_to_after32_order_changed': orders['historical_M1'] != after,
                'changed_Q_candidates': len(set(after) & changed),
                'historical_selected_changed_Q': len(set(selected) & changed),
                'historical_adopted_changed_Q': len(set(adopted) & changed),
                'candidate_visited_before': sum(visits['screened_before32'][i] > 0 for i in after),
                'candidate_visited_after': sum(visits['after32'][i] > 0 for i in after),
                'old_numeric_top3': '|'.join(before[:3]), 'new_numeric_top3': '|'.join(after[:3]),
                'old_full_order': '|'.join(before), 'new_full_order': '|'.join(after),
                'historical_selected_ids': '|'.join(selected), 'historical_adopted_ids': '|'.join(adopted)})
    write_csv(CURATED / 'Dgate_fixed_queries.csv', query_rows)
    exposure_rows = [{'arm': arm, 'scope': scope, 'stage': stage, **dict(counts)}
                     for (arm, scope, stage), counts in sorted(historical_exposure.items())]
    write_csv(CURATED / 'Dgate_historical_selection_exposure.csv', exposure_rows)
    first = [r for r in query_rows if r['attempt'] == 0]
    assert len(first) == 298
    def aggregate(items):
        return {'queries': len(items), 'order_changed': sum(r['new32_order_changed'] for r in items),
            'top3_set_changed': sum(r['new32_top3_set_changed'] for r in items),
            'with_changed_Q_candidates': sum(r['changed_Q_candidates'] > 0 for r in items),
            'with_historical_selected_changed_Q': sum(r['historical_selected_changed_Q'] > 0 for r in items),
            'with_historical_adopted_changed_Q': sum(r['historical_adopted_changed_Q'] > 0 for r in items),
            'candidate_visited_occurrences_before': sum(r['candidate_visited_before'] for r in items),
            'candidate_visited_occurrences_after': sum(r['candidate_visited_after'] for r in items)}
    by_cwe = {cwe: aggregate([r for r in first if str(r['cwe']) == cwe]) for cwe in sorted({str(r['cwe']) for r in first})}
    result = {'protocol': PROTOCOL, 'Dgate_new_API_calls': 0, 'new_selection': None,
        'new_adoption': None, 'new_code': None, 'new_Joint': None,
        'original_Q2_presentation_reproduced': len(query_rows), 'first_queries': aggregate(first),
        'historical_first_queries_selector_not_completed': [r['task_id'] for r in first if r['trace_status'] != 'completed'],
        'all_historical_attempt_queries': aggregate(query_rows), 'skipped': skipped, 'by_task_CWE_first': by_cwe,
        'changed_card_CWEs': dict(affected_cwe), 'historical_selection_exposure': exposure_rows,
        'qualification_only_first_order_changed': sum(r['qualification_order_changed'] for r in first),
        'M1_to_after32_first_order_changed': sum(r['M1_to_after32_order_changed'] for r in first),
        'limitation': 'Repair queries are anchored to old arm code/feedback. Numeric top3 is not native LLM selection. No new policy Joint measured.'}
    write(OUT / 'Dgate_replay_summary.json', result); write(CURATED / 'Dgate_replay_summary.json', result)
    meta = read(OUT / 'run_metadata.json'); meta['status'] = 'learning_and_history_replay_complete'
    write(OUT / 'run_metadata.json', meta)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'learn', 'replay'])
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare': prepare()
    elif args.command == 'run': run(args.probe)
    elif args.command == 'learn': learn()
    else: replay()

"""只读已保存FFS前缀，测量配对首次代码，不调用模型。"""
import ast
from collections import Counter
import json
from pathlib import Path

from methods.cle_ablation.memory_footprint import compare_code
from methods.sct_trajectory.replay_journal import write_json

RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
OUT = RUN / 'impact_radius_20261028/IR01'


def counts(code):
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    return {'functions': sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree)),
            'classes': sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree)),
            'lines': len(code.splitlines())}


def main():
    if (OUT / 'prefix_metrics.json').exists():
        raise RuntimeError('saved_snapshot_exists_do_not_overwrite')
    sources = [Path(p) for p in json.loads((RUN / 'FFS/execution_index.json').read_text())['segments']]
    files = {}
    for source in reversed(sources):
        for p in (source / 'task_rows').glob('*.json'):
            if p.stem.endswith(('_BM', '_BFS')):
                files.setdefault(p.stem, p)
    tasks = json.loads((RUN / 'FQ_GATE/inputs_v3/tasks.json').read_text(encoding='utf-8'))
    pairs, results, missing = {}, [], []
    for key, p in sorted(files.items()):
        stem, condition = key.rsplit('_', 1)
        pairs.setdefault(stem, {})[condition] = p
    for key, pair in sorted(pairs.items()):
        if set(pair) != {'BM', 'BFS'}:
            missing.append(key); continue
        a, b = [json.loads(pair[c].read_text(encoding='utf-8')) for c in ('BM', 'BFS')]
        tid = str(a['task_id'])
        old, new = a['attempts'][0], b['attempts'][0]
        public = tasks[tid]['task_description']
        measure = compare_code(old['code'], new['code'], public)
        x, y = bool(old['joint']), bool(new['joint'])
        transition = 'both_pass' if x and y else 'loss' if x else 'rescue' if y else 'both_fail'
        if not old.get('measured') or not new.get('measured'):
            transition = 'unmeasured'
        results.append({'task_id': tid, 'repeat': a['repeat'], 'family_id': a['family_id'],
            'transition': transition, 'old_first': {k: old.get(k) for k in ('functional', 'security', 'joint', 'measured')},
            'new_first': {k: new.get(k) for k in ('functional', 'security', 'joint', 'measured')},
            'old_counts': counts(old['code']), 'new_counts': counts(new['code']),
            'source_BM': str(pair['BM']), 'source_BFS': str(pair['BFS']), **measure})
    totals = Counter(r['transition'] for r in results)
    queue = []
    used = set()
    for kind in ('loss', 'rescue', 'both_pass', 'both_fail'):
        for r in sorted(results, key=lambda r: (int(r['task_id']), r['repeat'])):
            if r['transition'] == kind and r['family_id'] not in used:
                queue.append(r); used.add(r['family_id'])
                if sum(x['transition'] == kind for x in queue) == 3:
                    break
    summary = {'status': 'partial_prefix_metrics_complete_pending_case_review', 'experiment': 'IR01',
        'scope': 'saved FFS BM-BFS first-code complete pairs; not full298; no causal conclusion',
        'paired_units': len(results), 'distinct_tasks': len({r['task_id'] for r in results}),
        'measured_pairs': sum(r['old_first']['measured'] and r['new_first']['measured'] for r in results),
        'transitions_measured_only_with_unmeasured_separate': dict(totals), 'unpaired_units': len(missing),
        'new_experiment_HTTP': 0, 'case_review_completed': False, 'sources': list(map(str, sources))}
    write_json(OUT / 'prefix_metrics.json', results)
    write_json(OUT / 'case_review_queue.json', queue)
    write_json(OUT / 'prefix_summary.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k != 'sources'}))


if __name__ == '__main__':
    main()

"""旧CLE的Q开发对照：直接调用远程P7逐题入口，沿用远程M/A统计契约。

learn只在D_grow更新实际采纳卡的Q；compare在D_gate读冻结库。
不提炼候选、不运行Phase3准入门控、不读取Base/Plus。
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import shutil
import subprocess
from pathlib import Path
from statistics import quantiles
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from methods.cle_ablation.runner import run_one, plt_contract
from methods.direction_screening.protocol import summarize
from methods.sct_trajectory.memory_q import rank_candidates, update_adopted
from methods.sct_trajectory.provider_policy import CURRENT_MODEL
from methods.sct_trajectory.run_artifacts import write_json_atomic as write
from methods.sct_trajectory.run_branch_gate_study import stratified_tasks, file_digest
from methods.sct_trajectory.run_memory_q_study import load_inputs, _write_memory

ROOT = Path(__file__).resolve().parents[2]
POLICIES = {'Q0': 'semantic_llm', 'Q1': 'semantic_sim', 'Q2': 'semantic_q', 'Q3': 'semantic_q'}


def prepare_shared_initial(task, request):
    """使用原P7公开契约和初析提示；失败与原流水线一样保留为降级，不重试。"""
    from methods.sct_trajectory.run_memory_q_study import prepare_initial_analysis
    try:
        initial = prepare_initial_analysis({'task_description': plt_contract(task)}, request)
        error = None
    except Exception as exc:
        initial, error = {'unmeasured': True}, type(exc).__name__
    return {'task_id': str(task['index']), 'initial_analysis': initial, 'error_type': error}


def shuffled_memory(nodes, seed, scope='global'):
    """冻结对照仅置换Q/visits；CWE模式保持每类分布，正文和生命周期不变。"""
    if scope not in ('global', 'cwe'):
        raise ValueError('unknown Q shuffle scope')
    shuffled = copy.deepcopy(nodes)
    ordered = sorted(shuffled, key=lambda n: n.invariant_id)
    groups = {'all': ordered} if scope == 'global' else {}
    if scope == 'cwe':
        for node in ordered:
            groups.setdefault(str(node.cwe), []).append(node)
    rng = random.Random(seed)
    for key in sorted(groups):
        group = groups[key]
        values = [(n.q_value, n.q_visits) for n in group]
        rng.shuffle(values)
        for node, (value, visits) in zip(group, values):
            node.q_value, node.q_visits = value, visits
    return shuffled


def record_result(row, task, arm, pool, elapsed):
    """保留原生CLE attempts/validation/generation，补齐M/A报告所需final和方法身份。"""
    row.update(arm=arm, pool=pool, family_id=task['family_id'], cwe=str(task['CWE_ID']),
               workflow_arm='P7', retrieval_mode=POLICIES[arm], elapsed_seconds=elapsed)
    for attempt in row['attempts']:
        for key in ('functional', 'security', 'joint', 'measured'):
            attempt.setdefault(key, False)
    row['final'] = row['attempts'][-1]
    errors = [a.get('error_type') or a.get('generation', {}).get('error_type') for a in row['attempts']]
    row['error_type'] = next((e for e in errors if e), None)
    return row


def learn_q(row, nodes, alpha):
    """验证后按c0/c1实际采用ID归因；原P7选卡不读取Q，逐题后更新不改变曝光。"""
    if row['pool'] != 'D_grow':
        raise ValueError('Q learning requires D_grow')
    events = []
    for attempt in row['attempts']:
        generation = attempt.get('generation', {})
        evidence = attempt.get('validation', {}).get('evidence', {})
        if not generation.get('workflow_completed'):
            evidence = {'error': 'pipeline_incomplete'}
        adopted = [c['invariant_id'] for c in generation.get('cards', [])]
        for event in update_adopted(nodes, adopted, evidence, code=attempt['code'], pool='D_grow', alpha=alpha):
            events.append({'task_id': row['task_id'], 'family_id': row['family_id'],
                           'attempt': attempt['attempt'], 'pool': 'D_grow', **event})
    return events


def mechanism_readout(rows, nodes, delta, lambda_q):
    """对同一Q2查询做离线λ=0反事实排序，区分数值作用与不同臂初析造成的差异。"""
    values = {n.invariant_id: n.q_value for n in nodes}
    visits = {n.invariant_id: n.q_visits for n in nodes}
    readout = []
    for row in rows:
        if row['arm'] != 'Q2':
            continue
        for attempt in row['attempts']:
            trace = attempt.get('retrieval_trace') or {}
            scores = trace.get('scores', [])
            sim = [s['id'] for s in rank_candidates(scores, values, delta=delta, lambda_q=0)]
            selected = [s['id'] for s in rank_candidates(scores, values, delta=delta, lambda_q=lambda_q)]
            readout.append({'task_id': row['task_id'], 'attempt': attempt['attempt'],
                            'similarity_ids_same_query': sim, 'q_ids_same_query': selected,
                            'set_changed': set(sim) != set(selected), 'order_changed': sim != selected,
                            'visited_candidates': sum(visits[s['id']] > 0 for s in scores)})
    return readout


def write_report(out, rows, nodes, delta, lambda_q, stage):
    """直接使用远程summarize：总分母、测量、首次/最终、配对McNemar与Holm。"""
    summary = summarize(rows, 'Q0' if stage == 'learn' else 'Q1')
    summary.update(stage=stage, workflow='remote CLE P7', role='training_development_only',
                   families=len({r['family_id'] for r in rows}),
                   mechanism=mechanism_readout(rows, nodes, delta, lambda_q) if stage == 'compare' else [])
    write(out / 'summary.json', summary)
    lines = ['# CLE记忆Q开发对照', '', '执行链路：cle_ablation.runner.run_one(P7)；统计：direction_screening.protocol.summarize。',
             '', '| 臂 | n | F | S | Joint | 完整测量 | 首次Joint | 调用 | Token |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm, item in summary['arms'].items():
        lines.append('| ' + arm + ' | ' + ' | '.join(str(item[k]) for k in
                     ('n', 'functional', 'security', 'joint', 'measured', 'first_joint', 'calls', 'total_tokens')) + ' |')
    lines += ['', '仅PLT开发诊断；D_gate结果不得更新Q。最终代码按原P7的早停/末次规则确定，不使用oracle挑选。',
              '配对、Holm校正、功能伤害与同一查询下的选卡变化见summary.json；费用和共享embedding冷启动见cost.json。']
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', required=True, choices=('learn', 'compare'))
    parser.add_argument('--memory', type=Path, required=True)
    parser.add_argument('--pools', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--calibration', type=Path)
    parser.add_argument('--limit', type=int, default=2)
    parser.add_argument('--manifest', type=Path, help='预注册学习/开发/确认ID清单')
    parser.add_argument('--split', choices=('learning', 'development', 'confirmation'))
    parser.add_argument('--arms', nargs='+', choices=tuple(POLICIES), default=['Q0','Q1','Q2'])
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--shared-initial', action='store_true', help='开发控制实验共享c0初析；c1独立')
    parser.add_argument('--shuffle-seed', type=int, default=20261015)
    parser.add_argument('--shuffle-scope', choices=('global', 'cwe'), default='global',
                        help='Q3置换范围；global保留历史行为，cwe仅在同CWE卡片内置换')
    parser.add_argument('--max-tokens', type=int, default=4096)
    parser.add_argument('--model', default=CURRENT_MODEL)
    parser.add_argument('--embedding-model', default='text-embedding-3-large')
    parser.add_argument('--embedding-cache', type=Path, default=ROOT/'translation_work/cache/embeddings/cle.sqlite3')
    parser.add_argument('--thinking', choices=('provider_default', 'disabled'), default='provider_default')
    parser.add_argument('--alpha', type=float, default=0.3)
    parser.add_argument('--lambda-q', type=float, default=0.5)
    args = parser.parse_args(argv)
    if args.shared_initial and args.stage != 'compare':
        parser.error('shared initial is a frozen comparison control')
    if not 1 <= args.workers <= 8 or (args.stage == 'learn' and args.workers != 1):
        parser.error('learning requires workers=1; frozen comparison supports 1..8')
    if args.limit < 1 or args.max_tokens < 1 or not 0 < args.alpha <= 1 or not 0 <= args.lambda_q <= 1:
        parser.error('invalid experiment parameters')
    if not args.out.resolve().is_relative_to((ROOT/'translation_work/diagnostics').resolve()):
        parser.error('development results must be under translation_work/diagnostics')
    dataset = ROOT/'data/external/secodeplt/secodeplt/data.json'
    families = ROOT/'data/external/secodeplt/derived_metadata/family_manifest.json'
    nodes, by_id, pools = load_inputs(args.memory, dataset, families, args.pools)
    before = [n.to_dict() for n in nodes]
    pool = 'D_grow' if args.stage == 'learn' else 'D_gate'
    if args.manifest:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        split = args.split or ('learning' if args.stage == 'learn' else 'development')
        if (args.stage == 'learn') != (split == 'learning'):
            parser.error('learning/evaluation split mismatch')
        ids = [str(i) for i in manifest[split]]
        if not set(ids) <= set(pools[pool]) or len(ids) != len(set(ids)):
            parser.error('manifest IDs must be unique members of the declared pool')
        tasks = [by_id[i] for i in ids]
    else:
        tasks = stratified_tasks([by_id[i] for i in pools[pool]], args.limit)
    if len({r['family_id'] for r in tasks}) != len(tasks):
        parser.error('probe requires distinct families; increase sampling design before running')
    delta = -1.0  # 学习曝光由原LLM选择；阈值只由学习查询的召回分数确定，不看D_gate结果。
    if args.stage == 'learn' and any(n.q_visits or n.q_value for n in nodes):
        parser.error('learn requires unlearned M0')
    if args.stage == 'compare':
        if args.calibration is None:
            parser.error('compare requires --calibration from learn')
        calibration = json.loads(args.calibration.read_text(encoding='utf-8'))
        for key in ('embedding_model', 'thinking', 'max_tokens', 'lambda_q'):
            if calibration[key] != getattr(args, key):
                parser.error('calibration mismatch: ' + key)
        if calibration['memory_sha256'] != file_digest(args.memory) or calibration['pools_sha256'] != file_digest(args.pools):
            parser.error('calibration memory/pools mismatch')
        delta = calibration['delta']
        for relative, digest in calibration.get('generation_source_sha256', {}).items():
            if file_digest(ROOT/relative) != digest:
                parser.error('generation source changed after learning: ' + relative)
    args.out.mkdir(parents=True, exist_ok=False)
    _write_memory(args.out/'input_memory.jsonl', nodes)
    shutil.copy2(args.pools, args.out/'input_pools.json')
    if args.manifest:
        shutil.copy2(args.manifest, args.out/'experiment_manifest.json')
    if args.calibration:
        shutil.copy2(args.calibration, args.out/'input_calibration.json')
    source_paths = [Path(__file__), ROOT/'methods/cle_ablation/runner.py', ROOT/'methods/direction_screening/protocol.py',
                    *[ROOT/'methods/sct_trajectory'/f'{name}.py' for name in (
                        'context_pipeline', 'agent_pipeline', 'retriever', 'semantic_retrieval', 'closed_loop',
                        'run_closed_loop', 'hsk_tree', 'memory_q')]]
    for path in source_paths:
        target = args.out/'source_snapshot'/path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    metadata = {'args': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
                'model': args.model, 'temperature': 0, 'workers': args.workers,
                'timeout': 60, 'embedding_timeout': 120, 'validation_timeout': 20,
                'status': 'running', 'task_ids': [t['index'] for t in tasks],
                'backend': 'local_python_isolated', 'workflow_arm': 'P7', 'pool': pool,
                'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'source_sha256': {str(p.relative_to(ROOT)): file_digest(p) for p in source_paths},
                'dataset_sha256': file_digest(dataset), 'family_manifest_sha256': file_digest(families),
                'input_memory_sha256': file_digest(args.memory), 'pools_sha256': file_digest(args.pools),
                'output_schema_version': 'cle-ablation-p7-with-ma-final-v1',
                'output_schema': ['input_memory.jsonl', 'input_pools.json', 'rows.jsonl', 'memory_q_events.jsonl',
                                  'summary.json', 'cost.json', 'run_metadata.json', 'report.md', 'source_snapshot/'],
                'independent_heldout': False, 'final_test_access': False,
                'q_update_pool': 'D_grow only', 'selection': 'PLT first Joint stop else last attempt, maximum 2'}
    if args.stage == 'learn':
        metadata['output_schema'] += ['calibration.json', 'frozen/m_star_q.jsonl']
    write(args.out/'run_metadata.json', metadata)
    from methods.sct_trajectory.run_closed_loop import _requester, load_key
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.cost_tracker import CostTracker
    requester = _requester(args.model, 60, max_tokens=args.max_tokens, max_inflight=args.workers,
                           thinking=None if args.thinking == 'provider_default' else args.thinking)
    embedding = EmbeddingClient(model=args.embedding_model, cache_path=args.embedding_cache, key_loader=load_key, timeout=120)
    tracker, costs, rows, events = CostTracker(args.model), {}, [], []
    node_map = {n.invariant_id: n for n in nodes}
    placebo = shuffled_memory(nodes, args.shuffle_seed, args.shuffle_scope) if 'Q3' in args.arms else None
    placebo_before = [n.to_dict() for n in placebo] if placebo is not None else None
    if placebo is not None:
        _write_memory(args.out/'input_shuffled_memory.jsonl', placebo)
        metadata['output_schema'].append('input_shuffled_memory.jsonl')
    run_started = perf_counter()
    def request(prompt):
        try:
            response = requester(prompt)
        except Exception:
            tracker.record_error('pipeline')
            raise
        tracker.record('pipeline', response)
        return response
    try:
        shared = {}
        if args.shared_initial:
            def prepare(task):
                tracker.set_stage('shared_initial')
                return prepare_shared_initial(task, request)
            with (args.out/'shared_initial.jsonl').open('w', encoding='utf-8') as prepared_stream:
                with ThreadPoolExecutor(max_workers=args.workers) as executor:
                    futures = [executor.submit(prepare, task) for task in tasks]
                    for future in as_completed(futures):
                        item = future.result()
                        shared[item['task_id']] = item['initial_analysis']
                        prepared_stream.write(json.dumps(item, ensure_ascii=False)+'\n')
                        prepared_stream.flush()
                        print(json.dumps({'shared_initial': len(shared), 'task': item['task_id'],
                                          'error': item['error_type']}), flush=True)
            metadata['output_schema'].append('shared_initial.jsonl')
        with (args.out/'rows.jsonl').open('w', encoding='utf-8') as stream, \
             (args.out/'memory_q_events.jsonl').open('w', encoding='utf-8') as event_stream:
            arms = ['Q0'] if args.stage == 'learn' else args.arms
            def execute(task, arm):
                tracker.set_stage(arm)
                started = perf_counter()
                row = run_one('PLT', task, 'P7', request, {'full': placebo if arm == 'Q3' else nodes}, embedding,
                              retrieval_mode=POLICIES[arm], delta=delta, lambda_q=args.lambda_q,
                              **({'initial_analysis': copy.deepcopy(shared[str(task['index'])])} if args.shared_initial else {}))
                return record_result(row, task, arm, pool, perf_counter()-started)

            def save(row):
                arm = row['arm']
                bucket = costs.setdefault(arm, {'embedding': {}, 'seconds': 0})
                bucket['embedding'] = None  # 并发共享缓存只报总量，不能用全局差值虚构分臂用量。
                bucket['seconds'] += row['elapsed_seconds']
                if args.stage == 'learn':
                    new_events = learn_q(row, node_map, args.alpha)
                    events.extend(new_events)
                    for event in new_events:
                        event_stream.write(json.dumps(event, ensure_ascii=False)+'\n')
                    event_stream.flush()
                stream.write(json.dumps(row, ensure_ascii=False)+'\n'); stream.flush()
                rows.append(row)
                write_report(args.out, rows, nodes, delta, args.lambda_q, args.stage)
                print(json.dumps({'rows': len(rows), 'task': row['task_id'], 'arm': arm,
                                  'joint': row['final']['joint'], 'error': row['error_type']}, ensure_ascii=False), flush=True)
            jobs = [(task, arm) for i, task in enumerate(tasks)
                    for arm in arms[i % len(arms):] + arms[:i % len(arms)]]
            if args.workers == 1:
                for task, arm in jobs:
                    save(execute(task, arm))
            else:
                with ThreadPoolExecutor(max_workers=args.workers) as executor:
                    futures = [executor.submit(execute, task, arm) for task, arm in jobs]
                    for future in as_completed(futures):
                        save(future.result())
            after = [n.to_dict() for n in nodes]
            content = lambda values: [{k: v for k, v in n.items() if k not in ('q_value', 'q_visits')} for n in values]
            if content(after) != content(before) or (args.stage == 'compare' and after != before):
                raise RuntimeError('fixed_memory_changed')
            if placebo is not None and [n.to_dict() for n in placebo] != placebo_before:
                raise RuntimeError('shuffled_frozen_memory_changed')
            if args.stage == 'learn':
                similarities = [s['cosine'] for r in rows for a in r['attempts']
                                for s in (a.get('retrieval_trace') or {}).get('scores', [])]
                if len(similarities) < 2:
                    raise ValueError('no_learning_query_scores_for_threshold')
                delta = quantiles(similarities, n=5, method='inclusive')[3]
                frozen = args.out/'frozen/m_star_q.jsonl'
                _write_memory(frozen, nodes)
                write(args.out/'calibration.json', {
                    'model': args.model, 'embedding_model': args.embedding_model, 'thinking': args.thinking,
                    'max_tokens': args.max_tokens, 'lambda_q': args.lambda_q, 'alpha': args.alpha, 'delta': delta,
                    'threshold_basis': '80th percentile of D_grow recalled candidates; no D_gate scores',
                    'learning_ids': [t['index'] for t in tasks], 'memory_sha256': file_digest(frozen),
                    'pools_sha256': file_digest(args.pools), 'q_visited': sum(n.q_visits > 0 for n in nodes),
                    'generation_source_sha256': metadata['source_sha256'],
                    'reward_updates': sum(e.get('reward') is not None and e.get('invariant_id') is not None for e in events)})
            summary = write_report(args.out, rows, nodes, delta, args.lambda_q, args.stage)
            metadata.update(status='completed', rows=len(rows), memory_content_unchanged=True,
                            q_unchanged=args.stage == 'compare', delta=delta)
            return summary
    except BaseException as exc:
        metadata.update(status='failed', error_type=type(exc).__name__, rows=len(rows))
        raise
    finally:
        metadata['wall_seconds'] = perf_counter() - run_started
        write(args.out/'cost.json', {'llm': tracker.snapshot(), 'embedding': embedding.usage, 'by_arm': costs,
              'accounting': 'LLM calls/tokens are exact per row and arm. Embedding/cache usage is shared; concurrent increments are not assigned to arms. Per-arm seconds sum job latency; wall time is separate. Currency uses old repository estimates, not invoice.'})
        write(args.out/'run_metadata.json', metadata)


if __name__ == '__main__':
    main()

"""PLT 审计池开发消融：旧链路、提示修订、分析驱动检索、无经验及可选内部测试。

只读旧冻结库；审计池曾用于门控，因此不是独立 held-out。允许任务内训练反馈修复，
不蒸馏、不更新经验，不接触 Base/Plus。输出均留在忽略运行区。
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import shutil
import sys
import threading
import time
import types
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / 'src'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
BASE = ROOT / 'translation_work/sct_runs/cle_full_874_20260922'
BEFORE = ROOT / 'translation_work/diagnostics/20260923/pipeline_revision/before'
ARMS = ('legacy', 'prompt_revision', 'context', 'no_memory', 'context_checks')


def load_legacy_modules():
    """历史对照隔离加载旧源码，专属包复用未变化基础类型，不替换当前模块、不写库。"""
    package_name = '_sct_context_ablation_legacy'
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(BEFORE)]
        sys.modules[package_name] = package
        for dependency in ('hsk_tree', 'level4', 'experience_filter'):
            sys.modules[f'{package_name}.{dependency}'] = importlib.import_module(f'methods.sct_trajectory.{dependency}')
        for name in ('agent_pipeline', 'retriever', 'hier_retrieval'):
            full_name = f'{package_name}.{name}'
            spec = importlib.util.spec_from_file_location(full_name, BEFORE / f'{name}.py')
            module = importlib.util.module_from_spec(spec)
            sys.modules[full_name] = module
            spec.loader.exec_module(module)
    return {name: sys.modules[f'{package_name}.{name}'] for name in ('agent_pipeline', 'retriever', 'hier_retrieval')}


def create_output(path):
    """实验落盘阶段拒绝已有目录，防止覆盖证据；不删除或修改已有实验。"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=False)
    return path


def interleaved_jobs(tasks, arms):
    """调度阶段按题轮换各臂顺序；每题各臂齐全，减小服务时序与方法混淆。"""
    return [(task, arm) for index, task in enumerate(tasks)
            for arm in arms[index % len(arms):] + arms[:index % len(arms)]]


def summarize(rows):
    """汇总首次/最终结果及完整配对精确 McNemar；缺失配对不填零，错误保留总分母。"""
    result = {'arms': {}, 'paired_vs_legacy': {}, 'independent_heldout': False}
    grouped = {}
    for row in rows:
        grouped.setdefault(row['arm'], []).append(row)
    for arm, items in grouped.items():
        def score(which):
            attempts = [(row.get('attempts') or [{}])[which] for row in items]
            return {key: sum(bool(item.get(key)) for item in attempts) for key in ('functional', 'security', 'joint')}
        result['arms'][arm] = {'total': len(items), 'first': score(0), 'final': score(-1),
            'error_rows': sum(any(a.get('error_type') or a.get('generation', {}).get('error_type') for a in row.get('attempts', [])) for row in items),
            'repair_attempts': sum(len(row.get('attempts', [])) > 1 for row in items),
            'usage': {key: sum(row.get('usage', {}).get(key, 0) for row in items)
                      for key in ('calls', 'failed_calls', 'prompt_tokens', 'completion_tokens', 'total_tokens')}}
    baseline = {str(row['task_id']): row['attempts'][-1].get('joint', False) for row in grouped.get('legacy', [])}
    for arm, items in grouped.items():
        if arm == 'legacy':
            continue
        pairs = [(baseline[str(row['task_id'])], row['attempts'][-1].get('joint', False))
                 for row in items if str(row['task_id']) in baseline]
        new_only = sum(not old and new for old, new in pairs)
        old_only = sum(old and not new for old, new in pairs)
        discordant = new_only + old_only
        p = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(new_only, old_only) + 1)) / 2 ** discordant) if discordant else 1.0
        result['paired_vs_legacy'][arm] = {'pairs': len(pairs), 'new_only': new_only,
            'legacy_only': old_only, 'p_exact_two_sided': p, 'multiple_comparison_corrected': False,
            'joint_delta_points': 100 * (new_only - old_only) / len(pairs) if pairs else None}
    return result


def main():
    """训练侧开发对照入口：完整审计池、固定旧库、最多一次修复，记录所有候选与证据。

    本地 PLT 验证区分功能/安全、异常和超时；内部生成测试不计正式分。
    不运行 Docker，不读取最终测试集，不允许更新长期经验库。
    """
    from methods.sct_trajectory.run_closed_loop import _load_tasks, _requester
    from methods.sct_trajectory.closed_loop import validate_and_state
    from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.context_pipeline import run_context_pipeline
    from methods.sct_trajectory.internal_checks import propose_checks, execute_checks

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS[:4]))
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--out', required=True)
    parser.add_argument('--workers', type=int, default=16)
    parser.add_argument('--max-tokens', type=int, default=3072)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16 or args.limit < 0 or args.max_tokens < 1 or len(set(args.arms)) != len(args.arms):
        parser.error('workers must be 1..16, limit >= 0, max-tokens > 0, arms unique')
    out = (ROOT / args.out).resolve()
    if not out.is_relative_to((ROOT / 'translation_work').resolve()):
        parser.error('out must be inside translation_work')
    pools = json.loads((BASE / 'pools.json').read_text(encoding='utf-8'))
    ids = {str(item['task_id']) for item in pools['audit']}
    tasks = [row for row in _load_tasks(0) if str(row['index']) in ids]
    if len(tasks) != len(ids):
        raise RuntimeError('audit_pool_tasks_missing')
    # 固定按题ID排序；全量默认298题，limit仅用于冒烟且在元数据明示。
    tasks.sort(key=lambda row: row['index'])
    if args.limit:
        tasks = tasks[:args.limit]
    source = BASE / 'frozen/m_star.jsonl'
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    frozen_hash = digest(source)
    memory = [SecurityInvariantNode.from_dict(json.loads(line)) for line in source.read_text(encoding='utf-8').splitlines() if line.strip()]
    legacy = load_legacy_modules()
    create_output(out)
    def write(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    source_files = [Path(__file__), *[Path(__file__).with_name(name + '.py') for name in (
        'context_pipeline', 'retriever', 'hier_retrieval', 'internal_checks', 'agent_pipeline', 'closed_loop', 'run_closed_loop')],
        ROOT / 'methods/sct_agent/validation_evidence.py']
    snapshot = out / 'source_snapshot'
    snapshot.mkdir()
    for path in source_files:
        destination = snapshot / path.relative_to(ROOT)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    (snapshot / 'legacy').mkdir()
    for name in ('agent_pipeline', 'retriever', 'hier_retrieval'):
        shutil.copy2(BEFORE / f'{name}.py', snapshot / 'legacy' / f'{name}.py')
    metadata = {'created_at': datetime.now().isoformat(), 'model': 'deepseek-v3.2', 'temperature': 0,
        'max_tokens': args.max_tokens, 'workers': args.workers, 'max_inflight': args.workers,
        'arms': args.arms, 'task_ids': [row['index'] for row in tasks], 'tasks': len(tasks),
        'audit_pool_total': len(ids), 'limit': args.limit, 'independent_heldout': False,
        'development_data_warning': 'audit pool was used for memory gates; development comparison only',
        'memory_path': str(source), 'memory_sha256': frozen_hash, 'memory_updates': False,
        'feedback': 'PLT task-local training validation evidence; no Base/Plus', 'repairs': 1,
        'backend': 'local_python_isolated', 'legacy_source': str(BEFORE),
        'source_sha256': {str(path.relative_to(ROOT)): digest(path) for path in source_files},
        'pool_sha256': digest(BASE / 'pools.json'), 'credential_source': 'existing_run_closed_loop_resolver',
        'validation_timeout': 20,
        'status': 'running'}
    write('run_metadata.json', metadata)
    base_request = _requester('deepseek-v3.2', 60, max_tokens=args.max_tokens, max_inflight=args.workers)
    config = get_config('A7')
    def one(task, arm):
        row = {'task_id': task['index'], 'arm': arm, 'cwe': task.get('CWE_ID'), 'attempts': []}
        usage = dict.fromkeys(('calls', 'failed_calls', 'prompt_tokens', 'completion_tokens', 'total_tokens'), 0)
        usage_lock = threading.Lock()
        request_errors = []
        def request(prompt):
            try:
                response = base_request(prompt)
            except Exception as exc:
                with usage_lock:
                    usage['failed_calls'] += 1
                    request_errors.append({'type': type(exc).__name__,
                                           'diagnostics': getattr(exc, 'diagnostics', [])})
                raise
            with usage_lock:
                usage['calls'] += 1
                for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                    usage[key] += (response.get('usage') or {}).get(key, 0)
            return response
        contract = {**(task.get('task_description') or {}), 'task_id': str(task['index']),
                    'CWE_ID': str(task.get('CWE_ID', '')), 'language': 'python'}
        reference, feedback, suite = '', None, None
        for attempt in range(2):
            traces = []
            def retrieve(query):
                cls = legacy['retriever'].HskTreeRetriever if arm == 'legacy' else HskTreeRetriever
                retriever = cls(HskTree(), requester=request, ablation=config, retrieval_mode='hier_llm')
                cards = retriever.search(query, limit=3, pool_nodes=memory)
                traces.append(getattr(retriever, 'last_hier_trace', {}))
                return cards
            try:
                if arm == 'legacy':
                    cards = retrieve(contract)
                    generation = legacy['agent_pipeline'].run_pipeline(contract, cards, requester=request,
                        reference_code=reference, previous_evidence=feedback, contract_freeze=True)
                elif arm == 'prompt_revision':
                    cards = retrieve(contract)
                    generation = run_context_pipeline(contract, cards, requester=request,
                        reference_code=reference, previous_evidence=feedback, reanalyze=False)
                else:
                    cards = []
                    generation = run_context_pipeline(contract, [], requester=request,
                        reference_code=reference, previous_evidence=feedback,
                        cards_provider=None if arm == 'no_memory' else retrieve)
                    cards = generation.get('cards', [])
                generation = {key: value for key, value in generation.items() if key != 'prompts'}
                code = generation.get('code', '').strip()
                evidence, state = validate_and_state(task, code, timeout=20) if code else ({}, 'D')
                functional = evidence.get('functional', {}).get('status') == 'pass'
                security = evidence.get('security', {}).get('status') == 'pass'
                record = {'attempt': attempt, 'code': code, 'generation': generation, 'cards': cards,
                    'retrieval_trace': traces, 'evidence': evidence, 'state': state,
                    'functional': functional, 'security': security, 'joint': functional and security}
                if not code:
                    record['error_type'] = generation.get('error_type') or 'empty_code'
                # 首次执行内部检查仅用于下一轮修复；复用同一套件可比较修复前后。
                if arm == 'context_checks' and code:
                    if suite is None:
                        # 只用首轮无反馈初析，不能让修复轮训练测试证据进入自生成测试。
                        suite = propose_checks(contract, generation.get('initial_analysis', {}), request) if attempt == 0 else {
                            'cases': [], 'errors': ['initial_generation_missing_no_feedback_derived_suite']}
                    record['internal_suite'] = suite
                    record['internal_checks'] = execute_checks(code, contract.get('entry_point') or contract.get('function_name'), suite)
                row['attempts'].append(record)
                if record['joint']:
                    break
                reference, feedback = code, dict(evidence)
                if 'internal_checks' in record:
                    feedback['internal_checks'] = record['internal_checks']
            except Exception as exc:
                row['attempts'].append({'attempt': attempt, 'functional': False, 'security': False,
                    'joint': False, 'code': '', 'error_type': type(exc).__name__})
                break
        row['usage'] = usage
        row['request_errors'] = request_errors
        return row

    started = time.monotonic()
    rows = []
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor, (out / 'rows.jsonl').open('w', encoding='utf-8') as stream:
            futures = [executor.submit(one, task, arm) for task, arm in interleaved_jobs(tasks, args.arms)]
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                stream.flush()
                write('summary.json', summarize(rows))
                print(f"completed {len(rows)}/{len(futures)} arm={row['arm']} task={row['task_id']} joint={row['attempts'][-1]['joint']}", flush=True)
        metadata['status'] = 'completed'
    finally:
        metadata['elapsed_seconds'] = time.monotonic() - started
        metadata['memory_sha256_after'] = digest(source)
        metadata['memory_unchanged'] = metadata['memory_sha256_after'] == frozen_hash
        if metadata['status'] == 'running':
            metadata['status'] = 'interrupted_or_failed'
        write('run_metadata.json', metadata)
        write('summary.json', summarize(rows))
        if not metadata['memory_unchanged']:
            raise RuntimeError('frozen_memory_changed')


if __name__ == '__main__':
    main()

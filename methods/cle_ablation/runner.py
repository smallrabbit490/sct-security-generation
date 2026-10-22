"""P0-P7 配对消融：PLT Phase3 开发诊断与 CodeSecEval 冻结评测。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / 'src'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

FULL = ROOT / 'translation_work/sct_runs/cle_full_deepseek32_20260924_phase3_resume_20260925/frozen/m_star.jsonl'
PHASE1 = ROOT / 'translation_work/sct_runs/cle_full_deepseek32_20260924_full/pool_snapshots/phase1.jsonl'
POOLS = ROOT / 'translation_work/sct_runs/cle_full_deepseek32_20260924_full/pools.json'
ARMS = tuple(f'P{i}' for i in range(8))


@dataclass(frozen=True)
class Arm:
    attempts: int
    memory: str
    reanalyze: bool = False
    negative: bool = False


SPECS = {
    'P0': Arm(1, 'none'), 'P1': Arm(1, 'none'),
    'P2': Arm(1, 'none'), 'P3': Arm(2, 'none'),
    'P4': Arm(2, 'phase1', True), 'P5': Arm(2, 'full'),
    'P6': Arm(2, 'full', True), 'P7': Arm(2, 'full', True, True),
}


def arm_spec(name):
    return SPECS[name]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_contract(subset, row):
    """冻结评测仅传公开题面和签名；隐藏测试、答案和漏洞源码不进入生成。"""
    return {'task_id': f"{subset}:{row['ID']}", 'CWE_ID': str(row['ID']).split('_')[0].replace('CWE-', ''),
            'language': 'python', 'description': row['Problem'], 'entry_point': row.get('Entry_Point', ''),
            'contract': 'Preserve the stated interface, valid inputs, return values and exception semantics.'}


def plt_contract(row):
    description = row.get('task_description') or {}
    return {**description, 'task_id': str(row['index']), 'CWE_ID': str(row.get('CWE_ID', '')),
            'language': 'python'}


def load_tasks(dataset, limit):
    if dataset == 'PLT':
        from methods.sct_trajectory.run_closed_loop import _load_tasks
        from methods.sct_trajectory.run_branch_gate_study import validate_family_boundaries, stratified_tasks
        loaded = _load_tasks(0)
        pools = json.loads(POOLS.read_text(encoding='utf-8'))
        manifest = json.loads((ROOT / 'data/external/secodeplt/derived_metadata/family_manifest.json').read_text(encoding='utf-8'))
        validate_family_boundaries(loaded, pools, manifest)
        ids = {str(item['task_id']) for item in pools['audit']}
        tasks = [row for row in loaded if str(row['index']) in ids]
        if len(tasks) != len(ids):
            raise ValueError('phase3_task_mismatch')
        return [('PLT', row) for row in stratified_tasks(tasks, limit)]
    path = ROOT / f'data/SecEvoBasePlus/{dataset}/Python_{dataset}.json'
    rows = json.loads(path.read_text(encoding='utf-8'))
    return [(dataset, row) for row in rows[:limit or None]]


def load_memory(path):
    from methods.sct_trajectory.hsk_tree import SecurityInvariantNode
    return [SecurityInvariantNode.from_dict(json.loads(line)) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def summarize(rows):
    from methods.sct_trajectory.run_branch_gate_study import paired_binary
    result = {'arms': {}, 'paired_vs_P0': {}}
    by_arm = {arm: [row for row in rows if row['arm'] == arm] for arm in ARMS}
    for arm, items in by_arm.items():
        def counts(position):
            attempts = [(row.get('attempts') or [{}])[position] for row in items]
            return {key: sum(bool(a.get('measured')) and bool(a.get(key)) for a in attempts)
                    for key in ('functional', 'security', 'joint')}
        result['arms'][arm] = {'total': len(items), 'first': counts(0), 'final': counts(-1),
                               'unmeasured': sum(not (row.get('attempts') or [{}])[-1].get('measured') for row in items),
                               'repair_attempts': sum(len(row.get('attempts', [])) > 1 for row in items),
                               'calls': sum(row.get('usage', {}).get('calls', 0) for row in items)}
    base = {row['task_id']: bool(row['attempts'][-1].get('joint')) for row in by_arm['P0']
            if row.get('attempts') and row['attempts'][-1].get('measured')}
    for arm in ARMS[1:]:
        current = {row['task_id']: bool(row['attempts'][-1].get('joint')) for row in by_arm[arm]
                   if row.get('attempts') and row['attempts'][-1].get('measured')}
        result['paired_vs_P0'][arm] = paired_binary(base, current)
    return result


def write_report(out, rows):
    """报告阶段保留总分母、可测配对和用量；缺测不能伪装为模型安全失败。"""
    summary = summarize(rows)
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# CLE 消融运行报告', '', '| 臂 | 已完成 | 首次 Joint | 最终 Joint | 缺测 | 逻辑请求 |',
             '|---|---:|---:|---:|---:|---:|']
    for arm, item in summary['arms'].items():
        lines.append(f"| {arm} | {item['total']} | {item['first']['joint']} | {item['final']['joint']} | {item['unmeasured']} | {item['calls']} |")
    lines += ['', 'PLT Phase3 是门控开发池；Base/Plus 固定预算且不回传隐藏测试反馈。',
              '逐题失败、阶段降级、经验采用及用量见 rows.jsonl；全量完成状态见 run_metadata.json。']
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def generate(arm, contract, request, provider, *, reference='', feedback=None, initial_analysis=None):
    from methods.sct_trajectory.agent_pipeline import _content, strip_code_fence
    from methods.sct_trajectory.context_pipeline import CONTRACT_POLICY, run_context_pipeline
    spec = arm_spec(arm)
    if arm in ('P0', 'P1'):
        policy = CONTRACT_POLICY if arm == 'P1' else 'Follow the task specification.'
        prompt = ('Generate complete runnable Python code. Output code only. ' + policy +
                  '\nTask: ' + json.dumps(contract, ensure_ascii=False))
        code = strip_code_fence(_content(request(prompt)))
        return {'code': code, 'workflow_completed': bool(code), 'stages': [{'stage': 'generation', 'status': 'completed' if code else 'failed'}]}
    result = run_context_pipeline(contract, [], requester=request, reference_code=reference,
                                  previous_evidence=feedback, cards_provider=provider if spec.memory != 'none' else None,
                                  reanalyze=spec.reanalyze,
                                  **({'initial_analysis': initial_analysis} if initial_analysis is not None else {}))
    return {key: value for key, value in result.items() if key != 'prompts'}


def run_one(subset, task, arm, requester, memory, embedding_client=None, *,
            retrieval_mode='semantic_llm', delta=None, lambda_q=0.5, initial_analysis=None,
            retrieval_query_mode='combined', max_experiences=3, candidate_order=None,
            retrieval_provider=None, implementation_constraints=None):
    """复用既有逐题流程；可共享c0初析，c1仍独立分析本臂代码和反馈。"""
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.context_pipeline import safe_feedback
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever
    contract = plt_contract(task) if subset == 'PLT' else public_contract(subset, task)
    if implementation_constraints is not None:
        # 专项开发共用公开实现约束；不改数据/验证器，检索白名单不序列化此字段。
        contract['implementation_constraints'] = implementation_constraints
    spec = arm_spec(arm)
    row = {'task_id': contract['task_id'], 'subset': subset, 'arm': arm, 'attempts': [], 'usage': {'calls': 0,
           'failed_calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
    traces = []

    def request(prompt):
        row['usage']['calls'] += 1
        try:
            response = requester(prompt)
        except Exception:
            row['usage']['failed_calls'] += 1
            raise
        for field in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
            value = (response.get('usage') or {}).get(field)
            if isinstance(value, (int, float)):
                if row['usage'][field] is not None:
                    row['usage'][field] += value
            else:
                row['usage'][field] = None
        return response

    def provider(query):
        # 查询消融只改变检索输入，生成、复析及原P7反馈契约保持不变。
        if retrieval_query_mode == 'original':
            query = {key: value for key, value in query.items() if key != 'threat_analysis'}
        elif retrieval_query_mode != 'combined':
            raise ValueError('unknown_retrieval_query_mode')
        if retrieval_provider is not None:
            # 固定库专项只替换选卡，不复制P7修复/验证/交付流程；回调须返回原生卡与轨迹。
            found, trace = retrieval_provider(query)
            traces.append(trace)
            if not spec.negative:
                found = [{**card, 'negative_guardrail': ''} for card in found]
            return found
        retriever = HskTreeRetriever(HskTree(), requester=request, ablation=get_config('A7'),
                                     retrieval_mode=retrieval_mode, embedding_client=embedding_client,
                                     semantic_delta=delta, lambda_q=lambda_q, candidate_order=candidate_order)
        found = retriever.search(query, limit=max_experiences, pool_nodes=memory[spec.memory])
        traces.append(getattr(retriever, 'last_hier_trace', None))
        if not spec.negative:
            found = [{**card, 'negative_guardrail': ''} for card in found]
        return found

    reference, feedback = '', None
    for attempt in range(spec.attempts):
        try:
            prepared = {'initial_analysis': initial_analysis} if attempt == 0 and initial_analysis is not None else {}
            generation = generate(arm, contract, request, provider, reference=reference, feedback=feedback, **prepared)
            code = generation.get('code', '').strip()
            if not code:
                row['attempts'].append({'attempt': attempt, 'code': '', 'measured': False,
                                        'error_type': generation.get('error_type') or 'empty_code', 'generation': generation})
                break
            if subset == 'PLT':
                from methods.sct_trajectory.closed_loop import validate_and_state
                evidence, state = validate_and_state(task, code, timeout=20)
                functional = evidence.get('functional', {}).get('status') == 'pass'
                security = evidence.get('security', {}).get('status') == 'pass'
                measured = all(evidence.get(k, {}).get('status') in ('pass', 'fail') for k in ('functional', 'security'))
                validation = {'evidence': safe_feedback(evidence), 'state': state}
                feedback = safe_feedback(evidence)
            else:
                from methods.sct_trajectory.run_plus_frozen_comparison import evaluate
                validation = evaluate(task, code, 30)
                functional, security = validation['functional'], validation['security']
                evidence = validation['evidence']
                measured = not validation['environment_error'] and all(
                    evidence[k]['status'] in ('pass', 'fail') for k in ('functional', 'security'))
                # Base/Plus 是最终测试：其隐藏测试状态不回流到生成或检索。
                feedback = None
                validation = {'functional': functional, 'security': security,
                              'joint': validation['joint'], 'environment_error': validation['environment_error'],
                              'evidence': {key: {'status': value.get('status', 'unmeasured')}
                                           for key, value in evidence.items()}}
            row['attempts'].append({'attempt': attempt, 'code': code, 'generation': generation,
                                    'validation': validation, 'functional': functional, 'security': security,
                                    'joint': measured and functional and security, 'measured': measured,
                                    'retrieval_trace': traces[-1] if traces else None})
            if subset == 'PLT' and not measured:
                break
            if subset == 'PLT' and functional and security:
                break
            reference = code
            # Base/Plus 固定两次预算，第二次只看自己的草稿；最终代码不按隐藏测试挑选。
        except Exception as exc:
            row['attempts'].append({'attempt': attempt, 'code': '', 'measured': False,
                                    'error_type': type(exc).__name__,
                                    'request_diagnostics': getattr(exc, 'diagnostics', [])})
            break
    return row


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=('PLT', 'Base', 'Plus'), required=True)
    parser.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--max-tokens', type=int, default=4096)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--calibration-only', action='store_true')
    args = parser.parse_args()
    if args.limit < 0 or args.max_tokens < 1 or not 1 <= args.workers <= 16 or len(set(args.arms)) != len(args.arms):
        parser.error('invalid limit, token budget or duplicate arms')
    out = args.out.resolve()
    if not out.is_relative_to((ROOT / 'translation_work').resolve()):
        parser.error('output must be inside translation_work')
    tasks = load_tasks(args.dataset, args.limit)
    sources = {'phase1': PHASE1, 'full': FULL}
    hashes = {key: digest(path) for key, path in sources.items()}
    memory = {'none': [], **{key: load_memory(path) for key, path in sources.items()}}
    out.mkdir(parents=True, exist_ok=True)
    rows_path = out / 'rows.jsonl'
    previous = [json.loads(line) for line in rows_path.read_text(encoding='utf-8').splitlines() if line.strip()] if rows_path.exists() else []
    metadata_path = out / 'run_metadata.json'
    task_ids = [plt_contract(row)['task_id'] if subset == 'PLT' else public_contract(subset, row)['task_id'] for subset, row in tasks]
    data_path = ROOT / ('data/external/secodeplt/secodeplt/data.json' if args.dataset == 'PLT'
                       else f'data/SecEvoBasePlus/{args.dataset}/Python_{args.dataset}.json')
    source_paths = [Path(__file__), *[(ROOT / 'methods/sct_trajectory' / (name + '.py')) for name in
                    ('context_pipeline', 'agent_pipeline', 'retriever', 'semantic_retrieval', 'closed_loop',
                     'run_closed_loop', 'run_plus_frozen_comparison')]]
    configuration = {'dataset': args.dataset, 'arms': args.arms, 'task_ids': task_ids, 'memory_sha256': hashes,
                     'model': 'deepseek-v3.2', 'temperature': 0, 'max_tokens': args.max_tokens,
                     'workers': args.workers, 'dataset_sha256': digest(data_path), 'pools_sha256': digest(POOLS),
                     'feedback': 'PLT task-local only; Base/Plus none', 'phase3_independent_heldout': False,
                     'retrieval_mode': 'semantic_llm', 'source_sha256': {str(p.relative_to(ROOT)): digest(p) for p in source_paths},
                     'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}
    if metadata_path.exists():
        old = json.loads(metadata_path.read_text(encoding='utf-8'))
        immutable_keys = tuple(key for key in configuration if key not in ('source_sha256', 'git_commit', 'workers'))
        if any(old.get(k) != configuration[k] for k in immutable_keys):
            raise ValueError('resume_metadata_mismatch')
        if old.get('source_sha256') != configuration['source_sha256']:
            history = old.setdefault('source_sha256_history', [])
            if old.get('source_sha256') not in history:
                history.append(old.get('source_sha256'))
            old['source_sha256'] = configuration['source_sha256']
            old['source_upgrade_at'] = datetime.now().isoformat()
        old['workers'] = args.workers
        metadata_path.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        metadata_path.write_text(json.dumps({**configuration, 'created_at': datetime.now().isoformat(),
                                'status': 'running', 'credential_source': 'existing_chatanywhere_resolver'}, indent=2), encoding='utf-8')
        import shutil
        for path in source_paths:
            destination = out / 'source_snapshot' / path.relative_to(ROOT)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    completed = {(row['task_id'], row['arm']) for row in previous}
    if len(completed) != len(previous):
        raise ValueError('duplicate_resume_rows')
    pool = None
    if args.dataset != 'PLT':
        from translation_pipeline.persistent_container import cleanup_stale_containers, close_implicit_pools
        from methods.sct_trajectory.run_plus_frozen_comparison import evaluate
        os.environ['SAFECODER_DOCKER_POOL_SIZE'] = str(args.workers)
        os.environ['SAFECODER_PYTHON_DOCKER_IMAGE'] = 'safecoder-python-validator:local'
        cleanup_stale_containers()
        pool = close_implicit_pools
        calibration = []
        try:
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(evaluate, task, task['Secure Code'], 30): task for _, task in tasks}
                for future in as_completed(futures):
                    result = future.result()
                    calibration.append({'task_id': futures[future]['ID'], 'joint': result['joint'],
                                        'environment_error': result['environment_error'],
                                        'statuses': {key: item['status'] for key, item in result['evidence'].items()}})
        except Exception:
            pool()
            raise
        (out / 'calibration.json').write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding='utf-8')
        if any(not r['joint'] for r in calibration):
            pool()
            raise RuntimeError('positive_control_failed')
    try:
        if not args.calibration_only:
            from methods.sct_trajectory.run_closed_loop import _requester, load_key
            from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
            requester = _requester('deepseek-v3.2', 60, max_tokens=args.max_tokens, max_inflight=args.workers)
            embedding = EmbeddingClient(model='text-embedding-3-large',
                cache_path=ROOT / 'translation_work/cache/embeddings/cle.sqlite3', key_loader=load_key, timeout=120)
            rows = list(previous)
            jobs = []
            for index, (subset, task) in enumerate(tasks):
                task_id = plt_contract(task)['task_id'] if subset == 'PLT' else public_contract(subset, task)['task_id']
                ordered = args.arms[index % len(args.arms):] + args.arms[:index % len(args.arms)]
                jobs.extend((subset, task, arm) for arm in ordered if (task_id, arm) not in completed)
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = [executor.submit(run_one, subset, task, arm, requester, memory, embedding)
                           for subset, task, arm in jobs]
                for future in as_completed(futures):
                    row = future.result()
                    with rows_path.open('a', encoding='utf-8') as handle:
                        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
                    rows.append(row)
                    write_report(out, rows)
                    print(f"{len(rows)}/{len(tasks) * len(args.arms)} {row['task_id']} {row['arm']}", flush=True)
            if any(digest(path) != hashes[key] for key, path in sources.items()):
                raise RuntimeError('frozen_memory_changed')
            metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
            metadata.update(status='completed', completed_at=datetime.now().isoformat(), rows=len(rows),
                            memory_unchanged=True)
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
    finally:
        if pool:
            pool()


def main():
    """Windows 跨进程锁在任何 Docker 清理前取得；拒绝并行评测破坏活跃池。

    锁随进程退出由操作系统释放；不删除锁文件、不修改经验或测试。Watchdog 自己
    也会清理池，因此外部仍必须串行启动 watchdog，不能靠此锁保护其启动清理。
    """
    if '--dataset' not in sys.argv or sys.argv[sys.argv.index('--dataset') + 1] == 'PLT':
        return _main()
    import msvcrt
    lock_path = ROOT / 'translation_work/cache/cle_ablation/docker_evaluation.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError('another_cle_docker_evaluation_is_active') from None
        try:
            return _main()
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()

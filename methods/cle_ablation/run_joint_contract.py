"""有界的新 CLE 消费者入口；默认只做零 API 预检，--run 才调用模型。

必须显式提供任务和1939卡冻结库，既不恢复旧实验，也不创建缺失的历史原路径。
新输出目录不允许续写；公开选择之后才计正式成绩，历史失败记录与 M1 保持不变。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import math
import sys
from pathlib import Path
import shutil
import subprocess
import threading
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import joint_contract, runner


class BudgetExceeded(RuntimeError):
    """保守预留预算不足；不再发送该请求。"""


class RequestBudget:
    """调用前按最坏重试预留请求数及输入字节+输出token上界；不把预留当实际账单。

    原请求器普通调用最多三次 HTTP、selector 一次；迟到/失败的费用可能未知，
    因此不退还预留。UTF-8字节保守代替输入token并加消息开销，不承诺精确费用。
    """
    def __init__(self, max_calls, max_tokens, max_embedding_calls=None):
        if max_calls < 1 or max_tokens < 1:
            raise ValueError('invalid_request_budget')
        self.max_calls, self.max_tokens = max_calls, max_tokens
        self.max_embedding_calls = max_embedding_calls
        self.reserved_embedding_calls = 0
        self.reserved_calls = self.reserved_tokens = 0
        self.exhausted = False
        self.lock = threading.Lock()
        self.records = []

    def reserve(self, kind, text, *, attempts, completion_cap):
        tokens = attempts * (len(text.encode('utf-8')) + 1024 + completion_cap)
        with self.lock:
            if (self.exhausted or self.reserved_calls + attempts > self.max_calls
                    or self.reserved_tokens + tokens > self.max_tokens
                    or (kind == 'embedding' and self.max_embedding_calls is not None
                        and self.reserved_embedding_calls + attempts > self.max_embedding_calls)):
                self.exhausted = True
                raise BudgetExceeded('request_or_token_budget_exhausted')
            self.reserved_calls += attempts
            if kind == 'embedding':
                self.reserved_embedding_calls += attempts
            self.reserved_tokens += tokens
            record = {'kind': kind, 'reserved_http_attempts': attempts,
                      'reserved_token_bound': tokens, 'prompt_sha256': hashlib.sha256(text.encode()).hexdigest(),
                      'status': 'reserved', 'usage': None}
            self.records.append(record)
            return record

    def wrap(self, requester, max_tokens, *, max_attempts=3):
        from methods.sct_trajectory.selector_protocol import SelectorPrompt
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise ValueError('max_attempts_must_be_1_to_3')

        def request(prompt):
            selector = isinstance(prompt, SelectorPrompt)
            record = self.reserve('selector' if selector else 'chat', str(prompt),
                attempts=1 if selector else max_attempts, completion_cap=min(256, max_tokens) if selector else max_tokens)
            try:
                response = requester(prompt)
                record.update(status='returned', usage=response.get('usage'), model=response.get('model'))
                return response
            except Exception as exc:
                record.update(status='failed', error_type=type(exc).__name__)
                raise
        return request

    def snapshot(self):
        with self.lock:
            def known_usage(record):
                value = record.get('usage')
                return (isinstance(value, dict) and type(value.get('total_tokens')) is int
                        and value['total_tokens'] >= 0)
            known = [r['usage'] for r in self.records if known_usage(r)]
            return {'reserved_http_attempts': self.reserved_calls, 'reserved_token_bound': self.reserved_tokens,
                'reserved_embedding_http_attempts': self.reserved_embedding_calls,
                'max_embedding_http_attempts': self.max_embedding_calls,
                'max_http_attempts': self.max_calls, 'max_total_tokens': self.max_tokens,
                'logical_operations': len(self.records),
                'known_returned_tokens': sum(int(r.get('total_tokens') or 0) for r in known),
                'unknown_usage_operations': sum(not known_usage(r) for r in self.records),
                'billing_complete': False, 'exhausted': self.exhausted, 'records': list(self.records)}


def bounded_embedding_client(budget, cache):
    """仅为新入口包裹真实 embedding HTTP；缓存命中不预留请求，不更改旧客户端。"""
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    from methods.sct_trajectory.run_closed_loop import load_key

    class BoundedEmbedding(EmbeddingClient):
        def _request(self, texts):
            record = budget.reserve('embedding', json.dumps(texts, ensure_ascii=False), attempts=1, completion_cap=0)
            before = self.usage
            try:
                result = super()._request(texts)
                after = self.usage
                missing = after.get('usage_missing_calls', 0) > before.get('usage_missing_calls', 0)
                record.update(status='returned', usage_status='missing' if missing else 'reported',
                    usage=None if missing else {key: after.get(key, 0) - before.get(key, 0)
                                               for key in ('prompt_tokens', 'total_tokens')})
                return result
            except Exception as exc:
                record.update(status='failed', error_type=type(exc).__name__)
                raise

    return BoundedEmbedding(model='text-embedding-3-large', cache_path=cache, key_loader=load_key, timeout=60)


def select_tasks(tasks, subset, limit):
    """开发小样本按 CWE 轮转，PLT 每题族至多一题；全量 limit=0 保留全部任务。"""
    ids = [str(t['index'] if subset == 'PLT' else t['ID']) for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate_task_ids')
    if not limit:
        return tasks
    groups = defaultdict(list)
    for task in tasks:
        cwe = str(task.get('CWE_ID') or str(task.get('ID', '')).split('_')[0])
        groups[cwe].append(task)
    selected, families = [], set()
    while any(groups.values()) and len(selected) < limit:
        for key in sorted(groups):
            while groups[key]:
                task = groups[key].pop(0)
                family = str(task.get('family_id') or task.get('index') or task.get('ID'))
                if subset == 'PLT' and family in families:
                    continue
                families.add(family)
                selected.append(task)
                break
            if len(selected) == limit:
                break
    return selected


def load_explicit_tasks(path, subset):
    """显式读取原列表或真实按ID索引快照；身份不匹配直接失败，不猜测版本。"""
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    key = 'index' if subset == 'PLT' else 'ID'
    if isinstance(value, dict):
        if any(not isinstance(row, dict) or str(row.get(key)) != str(task_id)
               for task_id, row in value.items()):
            raise ValueError('task_mapping_key_identity_mismatch')
        value = list(value.values())
    if not isinstance(value, list) or any(not isinstance(row, dict) or key not in row for row in value):
        raise ValueError('invalid_task_file')
    return value


def runtime_preflight(subset):
    """只读检查当前凭据/验证器能力；不输出密钥，不发模型请求。"""
    key_path = runner.ROOT / 'local_secrets/chatanywhereapi使用/apikey.txt'
    credential_available = bool(os.environ.get('CHATANYWHERE_API_KEY', '').strip()) or (
        key_path.is_file() and key_path.stat().st_size > 0)
    docker = shutil.which('docker')
    docker_ready = False
    if docker and subset != 'PLT':
        try:
            result = subprocess.run([docker, 'image', 'inspect', 'safecoder-python-validator:local'],
                capture_output=True, timeout=15, check=False)
            docker_ready = result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {'credential_available': credential_available, 'docker_binary_available': bool(docker),
            'credential_check': 'configuration_presence_only_not_authenticated',
            'python': sys.version.split()[0],
            'official_validator_runtime_ready': subset == 'PLT' or docker_ready,
            'positive_control_executed': False,
            'blockers': ([] if credential_available else ['model_credentials_missing']) +
                        ([] if subset == 'PLT' or docker_ready else ['original_Docker_validator_unavailable'])}


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    """默认零 API 预检；显式运行后串行有界前向，冻结文件指纹变化立即终止。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=('PLT', 'Base', 'Plus'), required=True)
    parser.add_argument('--tasks', type=Path, required=True)
    parser.add_argument('--memory', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=2)
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--arms', nargs='+', choices=('P7', joint_contract.VARIANT, joint_contract.CONDITIONAL_VARIANT), default=[joint_contract.VARIANT])
    parser.add_argument('--expected-memory-count', type=int, default=1939)
    parser.add_argument('--retrieval-mode', choices=('semantic_llm', 'semantic_q'), default='semantic_llm')
    parser.add_argument('--candidate-order', choices=('similarity', 'q'), default=None,
                        help='Only reorders candidates of the public-contract consumer; LLM still selects.')
    parser.add_argument('--conditional-q-policy', type=Path)
    parser.add_argument('--shared-public-suite', action='store_true')
    parser.add_argument('--max-experiences', type=int, default=3)
    parser.add_argument('--delta', type=float, default=-1.0)
    parser.add_argument('--lambda-q', type=float, default=0.5)
    parser.add_argument('--max-tokens', type=int, default=4096)
    parser.add_argument('--model', default='deepseek-v3.2', help='Explicit actual request model; historical default retained.')
    parser.add_argument('--max-http-attempts', type=int, default=2500)
    parser.add_argument('--max-total-tokens', type=int, default=20_000_000)
    parser.add_argument('--max-embedding-http-attempts', type=int)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if args.limit < 0 or not 1 <= args.repeats <= 2 or args.max_experiences < 1 or args.max_tokens < 1:
        parser.error('invalid_sample_or_generation_budget')
    if (args.max_http_attempts < 1 or args.max_total_tokens < 1
            or not math.isfinite(args.delta) or not math.isfinite(args.lambda_q)):
        parser.error('invalid_request_or_retrieval_budget')
    if len(args.arms) != len(set(args.arms)):
        parser.error('duplicate_arms')
    if args.candidate_order is not None and args.retrieval_mode != 'semantic_llm':
        parser.error('candidate_order_must_keep_semantic_llm')
    requested_arms = list(args.arms)
    conditional_policy = None
    conditional_router = None
    if joint_contract.CONDITIONAL_VARIANT in args.arms:
        if (not args.conditional_q_policy or not args.shared_public_suite
                or set(args.arms) != {'P7', joint_contract.VARIANT, joint_contract.CONDITIONAL_VARIANT}
                or args.retrieval_mode != 'semantic_llm' or args.candidate_order != 'similarity'
                or args.max_experiences != 3 or not 1 <= args.limit <= 48
                or args.max_tokens != 4096 or args.delta != -1 or args.lambda_q != .5
                or args.max_http_attempts > 4500 or args.max_total_tokens > 40_000_000
                or args.max_embedding_http_attempts is None or not 1 <= args.max_embedding_http_attempts <= 1000):
            parser.error('conditional_study_requires_shared_suite_policy_similarity_LLM_cap3_and_limit_1_to_48')
        from .conditional_q import make_router
        conditional_policy = json.loads(args.conditional_q_policy.read_text(encoding='utf-8'))
        conditional_router = make_router(conditional_policy, delta=args.delta, lambda_q=args.lambda_q)
        if not conditional_policy['enabled']:
            # 关闭路由等同契约-only；不花钱重复运行同一臂并伪称Q对照。
            args.arms.remove(joint_contract.CONDITIONAL_VARIANT)
    if args.max_embedding_http_attempts is not None and args.max_embedding_http_attempts < 1:
        parser.error('invalid_embedding_budget')
    out = args.out.resolve()
    if not out.is_relative_to((runner.ROOT / 'translation_work').resolve()):
        parser.error('output_must_be_inside_translation_work')
    if out.exists():
        parser.error('new_output_directory_required; do_not_overwrite_or_resume_historical_runs')
    tasks_path, memory_path = args.tasks.resolve(), args.memory.resolve()
    hashes = {'tasks': runner.digest(tasks_path), 'memory': runner.digest(memory_path)}
    if args.conditional_q_policy:
        hashes['conditional_q_policy'] = runner.digest(args.conditional_q_policy)
    tasks = select_tasks(load_explicit_tasks(tasks_path, args.dataset), args.dataset, args.limit)
    memory = runner.load_memory(memory_path)
    if len(memory) != args.expected_memory_count or not memory:
        raise ValueError('frozen_memory_count_mismatch')
    if conditional_policy is not None and (len(memory) != 1939 or sum(n.q_visits > 0 for n in memory) != 972):
        raise ValueError('conditional_study_requires_current_1939_cards_972_visited_snapshot')
    if not tasks:
        raise ValueError('empty_tasks')
    readiness = runtime_preflight(args.dataset)
    out.mkdir(parents=True)
    task_ids = [str(t['index'] if args.dataset == 'PLT' else t['ID']) for t in tasks]
    source_names = ('methods/cle_ablation/joint_contract.py', 'methods/cle_ablation/run_joint_contract.py',
        'methods/cle_ablation/runner.py', 'methods/cle_ablation/conditional_q.py', 'methods/sct_trajectory/public_contract_checks.py',
        'methods/sct_trajectory/public_repair_policy.py', 'methods/sct_trajectory/internal_checks.py',
        'methods/sct_trajectory/context_pipeline.py', 'methods/sct_trajectory/semantic_retrieval.py',
        'methods/sct_trajectory/retriever.py', 'methods/sct_trajectory/run_closed_loop.py',
        'methods/sct_agent/validation_evidence.py', 'src/translation_pipeline/python_validator.py')
    source_hashes = {name: runner.digest(runner.ROOT / name) for name in source_names}
    metadata = {'protocol': 'cle-contract-conditional-q-v1' if conditional_policy is not None else 'cle-joint-public-contract-v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'status': 'preflight_only', 'dataset': args.dataset, 'task_ids': task_ids, 'arms': args.arms,
        'requested_arms': requested_arms, 'conditional_q_policy': conditional_policy,
        'conditional_q_skipped': conditional_policy is not None and not conditional_policy['enabled'],
        'candidate_order': args.candidate_order, 'shared_public_suite': args.shared_public_suite,
        'shared_first_analysis_between_new_arms': args.shared_public_suite,
        'planned_P7_runs': len(tasks) * len(args.arms) * args.repeats,
        'input_paths': {'tasks': str(tasks_path), 'memory': str(memory_path)}, 'input_sha256': hashes,
        'source_sha256': source_hashes,
        'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=runner.ROOT, text=True).strip(),
        'memory_count': len(memory), 'repeats': args.repeats, 'model': args.model,
        'temperature': 0, 'thinking': 'disabled', 'max_tokens': args.max_tokens, 'selector_max_tokens': 256,
        'retrieval_mode': args.retrieval_mode, 'delta': args.delta, 'lambda_q': args.lambda_q,
        'max_experiences': args.max_experiences, 'max_http_attempts': args.max_http_attempts,
        'max_total_tokens': args.max_total_tokens, 'runtime': readiness,
        'max_embedding_http_attempts': args.max_embedding_http_attempts,
        'memory_updates': 0, 'new_formal_scores': 0, 'internal_suite_calls_per_new_row_max': 2,
        'internal_suite_scope': 'task_repeat_shared_between_new_arms' if args.shared_public_suite else 'per_new_row',
        'claim_boundary': 'New package comparison, not isolated Q or equal-token causal attribution.'}
    _write(out / 'run_metadata.json', metadata)
    if not args.run:
        print(json.dumps({'status': metadata['status'], 'tasks': len(tasks), 'blockers': readiness['blockers']}))
        return 0
    if readiness['blockers']:
        metadata['status'] = 'blocked_before_API'
        _write(out / 'run_metadata.json', metadata)
        print(json.dumps({'status': metadata['status'], 'blockers': readiness['blockers']}))
        return 2
    for name in source_names:
        snapshot = out / 'source_snapshot' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runner.ROOT / name, snapshot)
    budget = RequestBudget(args.max_http_attempts, args.max_total_tokens, args.max_embedding_http_attempts)
    from methods.sct_trajectory.run_closed_loop import _requester
    request = budget.wrap(_requester(args.model, 60, max_tokens=args.max_tokens,
                                    max_inflight=1, thinking='disabled'), args.max_tokens)
    embedding = bounded_embedding_client(budget, runner.ROOT / 'translation_work/cache/embeddings/cle.sqlite3')
    rows = []
    metadata['status'] = 'running'
    _write(out / 'run_metadata.json', metadata)
    try:
        # 原验证器参考实现正对照先于任何付费生成；不将校准证据传入消费者。
        calibration = []
        for task in tasks:
            if args.dataset == 'PLT':
                from configs.cle_dgrow_url_repair_20261019.repair_and_retest import reference as plt_reference
                reference = plt_reference(task, secure=True)
            else:
                reference = task.get('Secure Code', '')
            if not reference:
                raise ValueError('positive_control_code_missing')
            calibration.append(joint_contract.official_evaluate(args.dataset, task, reference))
        _write(out / 'calibration.json', calibration)
        if any(not r.get('measured') or not r.get('joint') for r in calibration):
            raise RuntimeError('positive_control_failed')
        metadata['runtime']['positive_control_executed'] = True
        for repeat in range(args.repeats):
            for index, task in enumerate(tasks):
                shared_suite, shared_analysis = None, None
                if args.shared_public_suite and any(arm != 'P7' for arm in args.arms):
                    from methods.sct_trajectory.run_memory_q_study import prepare_initial_analysis
                    shared_usage_start = len(budget.records)
                    shared_suite = joint_contract.prepare_public_suite(args.dataset, task, request)
                    shared_analysis = prepare_initial_analysis(
                        {'task_description': joint_contract.prepare_contract(args.dataset, task)}, request)
                    with (out / 'shared_public_inputs.jsonl').open('a', encoding='utf-8') as handle:
                        handle.write(json.dumps({'task_id': task_ids[index], 'repeat': repeat,
                            'public_suite': shared_suite, 'initial_analysis': shared_analysis,
                            'usage_record_range': [shared_usage_start, len(budget.records)]}, ensure_ascii=False) + '\n')
                ordered = args.arms[index % len(args.arms):] + args.arms[:index % len(args.arms)]
                new_arm_rows = []
                for arm in ordered:
                    usage_start = len(budget.records)
                    if budget.reserved_calls >= budget.max_calls or budget.reserved_tokens >= budget.max_tokens:
                        raise BudgetExceeded('run_budget_exhausted')
                    if arm == 'P7':
                        row = runner.run_one(args.dataset, task, 'P7', request, {'full': memory}, embedding,
                            retrieval_mode=args.retrieval_mode, delta=args.delta, lambda_q=args.lambda_q,
                            max_experiences=args.max_experiences)
                        row['selected_attempt'] = len(row['attempts']) - 1
                        row['final'] = {key: row['attempts'][-1].get(key) for key in
                                        ('measured', 'functional', 'security', 'joint', 'validation')}
                        if args.dataset == 'PLT':
                            evidence = (row['final'].get('validation') or {}).get('evidence', {})
                            if not joint_contract.measured_evidence(evidence):
                                row['final'].update(measured=False, joint=False)
                    else:
                        provider, traces = joint_contract.make_provider(memory, request, embedding,
                            retrieval_mode=args.retrieval_mode, delta=args.delta, lambda_q=args.lambda_q,
                            max_experiences=args.max_experiences,
                            candidate_order=conditional_router if arm == joint_contract.CONDITIONAL_VARIANT else args.candidate_order)
                        row = joint_contract.run_one(args.dataset, task, request, provider,
                            public_suite=shared_suite, initial_analysis=shared_analysis)
                        row['arm'] = arm
                        row['retrieval_traces'] = traces
                        new_arm_rows.append(row)
                    row['repeat'] = repeat
                    row['usage_record_range'] = [usage_start, len(budget.records)]
                    rows.append(row)
                    with (out / 'rows.jsonl').open('a', encoding='utf-8') as handle:
                        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
                    if arm != 'P7' and len(new_arm_rows) == 2:
                        from .conditional_q import check_common_first_retrieval
                        comparison = check_common_first_retrieval(*new_arm_rows)
                        with (out / 'shared_first_query_checks.jsonl').open('a', encoding='utf-8') as handle:
                            handle.write(json.dumps({'task_id': row['task_id'], 'repeat': repeat, **comparison}) + '\n')
                    _write(out / 'summary.json', {a: joint_contract.summarize([r for r in rows if r['arm'] == a])
                                                 for a in args.arms})
                    if conditional_policy is not None:
                        from .conditional_q import paired_screen
                        _write(out / 'paired_screen.json', paired_screen(rows, task_ids, args.repeats,
                            conditional_enabled=conditional_policy['enabled']))
                    _write(out / 'usage.json', budget.snapshot())
                    if budget.exhausted:
                        raise BudgetExceeded('request_or_token_budget_exhausted')
                    if runner.digest(memory_path) != hashes['memory'] or runner.digest(tasks_path) != hashes['tasks']:
                        raise RuntimeError('frozen_input_changed')
                    if args.conditional_q_policy and runner.digest(args.conditional_q_policy) != hashes['conditional_q_policy']:
                        raise RuntimeError('frozen_route_policy_changed')
        metadata['status'] = 'completed'
    except Exception as exc:
        metadata.update(status='stopped', error_type=type(exc).__name__)
        raise
    finally:
        metadata.update(completed_rows=len(rows), new_formal_scores=sum(bool(r['final'].get('measured')) for r in rows))
        _write(out / 'usage.json', budget.snapshot())
        _write(out / 'run_metadata.json', metadata)
        if args.dataset != 'PLT':
            from translation_pipeline.persistent_container import close_implicit_pools
            close_implicit_pools()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""训练侧 Phase2 分支研究与 Phase3 全量门控诊断入口。

仅使用 PLT 的 D_grow/D_gate 和 Phase1 只读库；本地 Python 隔离验证，不运行
Docker，不读取最终测试集，不把诊断候选写回库。按 CWE 固定抽样可用于冒烟，
默认全池。研究先报告首次/多分支 oracle，再报告配对统计、缺测及真实用量。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import shutil
import sys
import threading
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT, ROOT / 'src'):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
DEFAULT_MEMORY = ROOT / 'translation_work/sct_runs/cle_context_874_20260923/experience_pool.jsonl'
DEFAULT_POOLS = ROOT / 'translation_work/sct_runs/cle_full_874_20260922/pools.json'
ARMS = ('serial_repair', 'resample3', 'diverse3')


def file_digest(path):
    """输入审计阶段计算文件哈希；不读密钥、不执行验证、不修改源。"""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stratified_tasks(tasks, limit):
    """诊断选样按 CWE 轮转且按稳定 ID 排序；拒绝最终 Base/Plus 标记，不修改库。"""
    groups = defaultdict(list)
    for row in tasks:
        for field in ('subset', 'split', 'dataset', 'benchmark'):
            value = str(row.get(field, '')).lower()
            if value in ('base', 'plus') or 'codesec' in value:
                raise ValueError('Base/Plus cannot enter training study')
        groups[str(row.get('CWE_ID', 'unknown'))].append(row)
    queues = [deque(sorted(groups[key], key=lambda r: str(r['index']))) for key in sorted(groups)]
    selected = []
    while any(queues) and (not limit or len(selected) < limit):
        for queue in queues:
            if queue and (not limit or len(selected) < limit):
                selected.append(queue.popleft())
    return selected


def load_phase1_memory(path):
    """库来源检查：只接受明确 Phase1 来源且 ID 唯一的快照；失败拒绝运行，不写库。"""
    rows = [json.loads(line) for line in Path(path).read_text(encoding='utf8').splitlines() if line.strip()]
    if not rows or any(row.get('source', {}).get('stage') != 'phase1' for row in rows):
        raise ValueError('study requires exclusively Phase1 memory provenance')
    identities = [str(row.get('invariant_id', '')) for row in rows]
    if not all(identities) or len(set(identities)) != len(rows):
        raise ValueError('memory ids must be unique and nonempty')
    return rows


def validate_family_boundaries(loaded, pools, manifest):
    """预检实际训练任务的族隔离与清单一致性；缺族、漂移或跨池重叠均拒绝运行。

    输入完整 PLT 任务、303/273/298 划分和来源族清单；输出计数与验证结果。
    这里只证明清单定义的 seed family 无交叉，不声称其推断族代表真实官方谱系。
    不执行模型/动态验证，不改写任务或经验库。
    """
    task_map = {str(row['index']): row for row in loaded}
    if len(task_map) != len(loaded):
        raise ValueError('duplicate loaded training task ids')
    classification = manifest.get('row_classification') or {}
    families, counts = {}, {}
    for pool in ('source', 'replay', 'audit'):
        families[pool] = set()
        for entry in pools[pool]:
            identity = str(entry['task_id'])
            row = task_map.get(identity)
            if row is None:
                raise ValueError('missing training task: ' + identity)
            actual = str(row.get('family_id') or '')
            declared = str(entry.get('family_id') or '')
            reference = str(classification.get(identity, {}).get('seed_family_id') or '')
            if not actual or actual != declared or actual != reference:
                raise ValueError('task family manifest mismatch: ' + identity)
            families[pool].add(actual)
        counts[pool] = {'tasks': len(pools[pool]), 'families': len(families[pool])}
    for left, right in (('source', 'replay'), ('source', 'audit'), ('replay', 'audit')):
        if families[left] & families[right]:
            raise ValueError('training family overlap: ' + left + '/' + right)
    return {'family_ids_pairwise_disjoint': True, 'task_family_manifest_consistent': True,
            'counts': counts, 'family_ids': {key: sorted(value) for key, value in families.items()},
            'family_basis': manifest.get('seed_family_basis', 'manifest-defined inferred family')}


def paired_binary(old, new):
    """统计阶段用完整配对精确 McNemar；缺失任务不补失败，不修改经验。"""
    common = sorted(set(old) & set(new))
    pairs = [(bool(old[k]), bool(new[k])) for k in common]
    old_only = sum(a and not b for a, b in pairs)
    new_only = sum(b and not a for a, b in pairs)
    n = old_only + new_only
    p = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(old_only, new_only) + 1)) / 2 ** n) if n else 1.0
    return {'pairs': len(pairs), 'unpaired': len(set(old) ^ set(new)), 'old_only': old_only,
            'new_only': new_only, 'p_exact_two_sided': p,
            'delta_percentage_points': 100 * (new_only - old_only) / len(pairs) if pairs else None}


def holm(values):
    """统计阶段对预指定比较族做 Holm 修正；不把开发池当独立测试。"""
    answer, previous = [None] * len(values), 0.0
    for rank, index in enumerate(sorted(range(len(values)), key=lambda i: values[i])):
        previous = max(previous, min(1.0, values[index] * (len(values) - rank)))
        answer[index] = previous
    return answer


class UsageCounter:
    """请求审计：线程安全记录成功、失败与缺失 token；未知成本保留 null，不能写库。"""
    def __init__(self, requester):
        self.requester, self.lock = requester, threading.Lock()
        self.calls = self.failures = 0
        self.tokens = Counter()
        self.missing = Counter()

    def __call__(self, prompt):
        try:
            response = self.requester(prompt)
        except Exception:
            with self.lock:
                self.calls += 1
                self.failures += 1
            raise
        with self.lock:
            self.calls += 1
            usage = response.get('usage') or {}
            for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                value = usage.get(key)
                if isinstance(value, (int, float)):
                    self.tokens[key] += value
                else:
                    self.missing[key] += 1
        return response

    def snapshot(self):
        with self.lock:
            return {'calls': self.calls, 'failed_calls': self.failures,
                    **{k: None if self.missing[k] or self.failures else self.tokens[k]
                       for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
                    'known_tokens': dict(self.tokens), 'missing_usage_calls': dict(self.missing),
                    'usage_complete': not any(self.missing.values()) and not self.failures,
                    'currency_cost': None, 'currency_cost_reason': 'provider_billing_not_measured'}


def _metrics(attempts):
    """分别统计 F/S/Joint 和完整测量数量；缺测不当成功，未执行检查不补通过。"""
    counts = {key + '_pass': sum(bool(a.get('measured')) and bool(a.get(key)) for a in attempts)
              for key in ('functional', 'security', 'joint')}
    return {'total': len(attempts), 'unmeasured': sum(not a.get('measured') for a in attempts), **counts,
            'rates': {key: value / len(attempts) if attempts else None for key, value in counts.items()}}


def summarize_usage(records):
    """汇总请求用量；只要一份记录缺失就保留未知总额，不用零掩盖统计缺口。"""
    keys = ('calls', 'failed_calls', 'prompt_tokens', 'completion_tokens', 'total_tokens')
    return {**{key: sum(r[key] for r in records) if all(isinstance(r.get(key), (int, float)) for r in records) else None
               for key in keys}, 'records': len(records),
            'incomplete_records': sum(not r.get('usage_complete', False) for r in records),
            'currency_cost': None, 'currency_cost_reason': 'provider_billing_not_measured'}


def _oracle(attempts):
    """训练探索的预算内存在成功统计；F/S 可来自不同分支，Joint 必须同一分支成功。"""
    measured = [a for a in attempts if a.get('measured')]
    return {**{key: any(a.get(key, False) for a in measured) for key in ('functional', 'security', 'joint')},
            'measured': bool(measured), 'complete_measured': bool(attempts) and len(measured) == len(attempts)}


def summarize_branches(rows):
    """首次、最终及预算内 oracle 分开；主比较多样化对重采样，次比较旧修复，报告 Holm。"""
    groups = defaultdict(list)
    for row in rows:
        groups[row['arm']].append(row)
    output = {'arms': {}, 'comparisons': {}, 'independent_heldout': False,
              'oracle_warning': 'Training oracle is not deployment pass@1; F/S oracle may use different candidates.',
              'primary_comparison': 'diverse3_vs_resample3', 'budget_warning': 'serial uses up to 2 candidates; parallel arms use 3'}
    for arm, items in groups.items():
        first = [(r.get('attempts') or [{}])[0] for r in items]
        final = [(r.get('attempts') or [{}])[-1] for r in items]
        oracle = [_oracle(r.get('attempts') or [{}]) for r in items]
        output['arms'][arm] = {'total': len(items), 'first': _metrics(first), 'final': _metrics(final), 'oracle': _metrics(oracle),
            'generated_candidates': sum(len(r.get('attempts') or []) for r in items),
            'ast_duplicate_candidates': sum(bool(a.get('duplicate_of')) for r in items for a in r.get('attempts', [])),
            'error_rows': sum(bool(r.get('error_type')) or any(a.get('error_type') for a in r.get('attempts', [])) for r in items),
            'degraded_plans': sum(bool(r.get('plan_error')) for r in items),
            'invalid_diversity_plans': sum(r.get('diversity_valid') is False for r in items),
            'exclusive_usage': summarize_usage([r.get('usage', {}) for r in items])}
    for other in ('resample3', 'serial_repair'):
        old = {str(r['task_id']): _oracle(r.get('attempts') or [])['joint'] for r in groups.get(other, [])}
        new = {str(r['task_id']): _oracle(r.get('attempts') or [])['joint'] for r in groups.get('diverse3', [])}
        comparison = paired_binary(old, new)
        old_complete = {str(r['task_id']) for r in groups.get(other, []) if _oracle(r.get('attempts') or [])['complete_measured']}
        new_complete = {str(r['task_id']) for r in groups.get('diverse3', []) if _oracle(r.get('attempts') or [])['complete_measured']}
        complete = old_complete & new_complete
        sensitivity = paired_binary({key: old[key] for key in complete}, {key: new[key] for key in complete})
        sensitivity['excluded_incomplete_pairs'] = comparison['pairs'] - len(complete)
        comparison['complete_measured_pairs'] = sensitivity
        comparison['analysis_population'] = 'intention_to_test_all_recorded_tasks; missing measurements never count as success'
        output['comparisons']['diverse3_vs_' + other] = comparison
    for result, corrected in zip(output['comparisons'].values(), holm([x['p_exact_two_sided'] for x in output['comparisons'].values()])):
        result['p_holm_two_comparisons'] = corrected
    return output


class Recorder:
    """诊断落盘与心跳；状态更新时间独立于单次长调用，异常证据不覆盖其他运行。"""
    def __init__(self, out):
        self.out, self.lock, self.stop = out, threading.RLock(), threading.Event()
        self.state = {'status': 'running', 'stage': 'initializing', 'pid': os.getpid(), 'progress': {}}
        self.thread = threading.Thread(target=self.heartbeat, daemon=True)
        self.thread.start()

    def write(self, name, value):
        with self.lock:
            from methods.sct_trajectory.run_artifacts import write_json_atomic
            target = self.out / name
            write_json_atomic(target, value)

    def status(self, **values):
        with self.lock:
            self.state.update(values)
            self.state.update(updated_at=datetime.now().isoformat(), updated_ts=time.time())
            self.write('status.json', self.state)

    def append(self, name, value):
        with self.lock:
            with (self.out / name).open('a', encoding='utf8') as stream:
                stream.write(json.dumps(value, ensure_ascii=False) + '\n')

    def heartbeat(self):
        while not self.stop.wait(15):
            self.status()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=1)


def _contract(row):
    """前向阶段只向模型提供公开任务契约；测试/答案保留在本地验证回调。"""
    return {**(row.get('task_description') or {}), 'task_id': str(row['index']),
            'CWE_ID': str(row.get('CWE_ID', '')), 'language': 'python'}


def run_study(args):
    """诊断编排：冻结输入、执行分支/门控、输出独立副本；所有测试只在训练侧本地运行。"""
    from methods.sct_trajectory.run_closed_loop import _load_tasks, _requester
    from methods.sct_trajectory.branch_pipeline import prepare_context, run_branches, branch_trace, distill_branches
    from methods.sct_trajectory.context_pipeline import run_context_pipeline, analysis_prompt, CONTRACT_POLICY, experience_text
    from methods.sct_trajectory.agent_pipeline import _content, _extract_json, strip_code_fence
    from methods.sct_trajectory.closed_loop import validate_and_state
    from methods.sct_trajectory.internal_checks import propose_checks, execute_checks
    from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.global_gate import run_global_gate, evidence_is_measured

    out, source, pools_path = (ROOT / args.out).resolve(), (ROOT / args.memory).resolve(), (ROOT / args.pools).resolve()
    if not out.is_relative_to((ROOT / 'translation_work/diagnostics').resolve()):
        raise ValueError('out must be a fresh directory under translation_work/diagnostics')
    memory_rows = load_phase1_memory(source)
    memory_sha = file_digest(source)
    pools = json.loads(pools_path.read_text(encoding='utf8'))
    if [len(pools[k]) for k in ('source', 'replay', 'audit')] != [303, 273, 298]:
        raise ValueError('expected full 303/273/298 training pools')
    ids = {key: {str(r['task_id']) for r in pools[key]} for key in ('source', 'replay', 'audit')}
    if any(ids[a] & ids[b] for a, b in [('source', 'replay'), ('source', 'audit'), ('replay', 'audit')]):
        raise ValueError('training pools overlap')
    if any(str(r['source'].get('task_id')) not in ids['source'] for r in memory_rows):
        raise ValueError('Phase1 memory contains non D_init source')
    loaded = _load_tasks(0)
    family_manifest_path = ROOT / 'data/external/secodeplt/derived_metadata/family_manifest.json'
    family_manifest = json.loads(family_manifest_path.read_text(encoding='utf8'))
    family_checks = validate_family_boundaries(loaded, pools, family_manifest)
    tasks = {}
    for key in ('replay', 'audit'):
        selected = [row for row in loaded if str(row['index']) in ids[key]]
        if len(selected) != len(ids[key]):
            raise ValueError('missing or duplicate training tasks: ' + key)
        tasks[key] = stratified_tasks(selected, args.limit)
    nodes = [SecurityInvariantNode.from_dict(row) for row in memory_rows]
    out.mkdir(parents=True, exist_ok=False)
    recorder = Recorder(out)
    snapshot = out / 'source_snapshot'
    sources = [Path(__file__), *[Path(__file__).with_name(name + '.py') for name in (
        'branch_pipeline', 'global_gate', 'context_pipeline', 'hier_retrieval', 'retriever', 'agent_pipeline',
        'closed_loop', 'run_closed_loop', 'internal_checks', 'hsk_tree', 'schemas', 'ablation')],
        ROOT / 'methods/sct_agent/validation_evidence.py']
    for path in sources:
        target = snapshot / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    shutil.copy2(source, out / 'input_phase1_memory.jsonl')
    shutil.copy2(pools_path, out / 'input_pools.json')
    metadata = {'created_at': datetime.now().isoformat(), 'config': vars(args), 'model': 'deepseek-v3.2',
        'temperature': 0, 'memory_sha256': memory_sha, 'memory_entries': len(nodes), 'memory_all_phase1': True,
        'pool_sha256': file_digest(pools_path), 'source_sha256': {str(p.relative_to(ROOT)): file_digest(p) for p in sources},
        'task_ids': {k: [r['index'] for r in v] for k, v in tasks.items()}, 'backend': 'local_python_isolated',
        'memory_updates': False, 'independent_heldout': False, 'final_test_access': False,
        'diagnostic_warning': 'D_gate filtered results contain selection bias; oracle is training search only',
        'candidate_budget': {'serial_repair': 2, 'resample3': 3, 'diverse3': 3},
        'training_family_preflight': family_checks,
        'internal_checks': 'serial repair feedback only; branch candidates use same official local training validator'}
    input_files = [ROOT / 'data/external/secodeplt/secodeplt/data.json',
                   ROOT / 'data/external/secodeplt/derived_metadata/family_manifest.json']
    metadata['training_input_sha256'] = {str(p.relative_to(ROOT)): file_digest(p) for p in input_files if p.exists()}
    recorder.write('run_metadata.json', metadata)
    request = UsageCounter(_requester('deepseek-v3.2', args.timeout, max_tokens=args.max_tokens, max_inflight=args.max_inflight))
    config = get_config('A7')

    def retrieve(query, requester, candidates=None):
        retriever = HskTreeRetriever(HskTree(), requester=requester, ablation=config, retrieval_mode='hier_llm')
        return retriever.search(query, limit=3, pool_nodes=nodes if candidates is None else candidates)

    def validate(row, code):
        return validate_and_state(row, code, timeout=args.validation_timeout)[0]

    def serial(row):
        counted = UsageCounter(request)
        contract, attempts, reference, feedback, suite = _contract(row), [], '', None, None
        for index in range(2):
            generation = run_context_pipeline(contract, [], requester=counted, reference_code=reference,
                previous_evidence=feedback, cards_provider=lambda query: retrieve(query, counted))
            code = generation.get('code', '')
            evidence = validate(row, code) if code else {}
            statuses = [evidence.get(k, {}).get('status') for k in ('functional', 'security')]
            measured = evidence_is_measured(evidence)
            functional, security = [measured and status == 'pass' for status in statuses]
            record = {'attempt': index, 'code': code, 'evidence': evidence, 'functional': functional,
                'security': security, 'joint': functional and security, 'measured': measured,
                'generation': {k: v for k, v in generation.items() if k != 'prompts'}, 'error_type': generation.get('error_type')}
            if code:
                if suite is None:
                    suite = propose_checks(contract, generation.get('initial_analysis', {}), counted) if index == 0 else {'cases': [], 'errors': ['missing_initial_generation']}
                record['internal_suite'] = suite
                record['internal_checks'] = execute_checks(code, contract.get('entry_point') or contract.get('function_name'), suite)
            attempts.append(record)
            if record['joint']:
                break
            reference, feedback = code, {**evidence, 'internal_checks': record.get('internal_checks', {})}
        return {'task_id': row['index'], 'arm': 'serial_repair', 'attempts': attempts, 'usage': counted.snapshot()}

    def branch_task(index, row):
        # 两种并行臂共享同一次真实初析/检索/复析，杜绝经验快照差异成为主要混杂。
        contract = _contract(row)
        shared_counter = UsageCounter(request)
        prepared = prepare_context(contract, shared_counter, lambda q: retrieve(q, shared_counter))
        recorder.append('shared_context.jsonl', {'task_id': row['index'], 'context': prepared, 'usage': shared_counter.snapshot()})
        results = []
        order = ARMS[index % 3:] + ARMS[:index % 3]
        for arm in order:
            started = time.monotonic()
            try:
                if arm == 'serial_repair':
                    result = serial(row)
                else:
                    counted = UsageCounter(request)
                    raw = run_branches(contract, requester=counted, retrieve=lambda q: retrieve(q, counted),
                        validate=lambda code: validate(row, code), count=3, mode='diverse' if arm == 'diverse3' else 'resample',
                        workers=3, prepared=prepared)
                    result = {'task_id': row['index'], 'arm': arm, 'attempts': raw['branches'],
                        'selected_index': raw['selected_index'], 'plan_error': raw['plan_error'],
                        'unique_code_count': raw['unique_code_count'], 'usage': counted.snapshot(),
                        'diversity_valid': raw.get('diversity_valid'), 'diversity_errors': raw.get('diversity_errors', [])}
                    if args.distill_smoke and index == 0 and arm == 'diverse3':
                        distilled_usage = UsageCounter(request)
                        candidates = distill_branches(branch_trace(row, raw), distilled_usage)
                        recorder.write('smoke_distilled_candidates.json', {'task_id': row['index'], 'candidates': candidates,
                            'usage': distilled_usage.snapshot(), 'long_term_memory_modified': False})
                result['cwe'] = row.get('CWE_ID')
            except Exception as exc:
                result = {'task_id': row['index'], 'arm': arm, 'attempts': [], 'error_type': type(exc).__name__}
            result['elapsed_seconds'] = time.monotonic() - started
            recorder.append('branches.jsonl', result)
            results.append(result)
        return results

    summary = {}
    try:
        if args.phase in ('branches', 'both'):
            recorder.status(stage='branches', progress={'completed_tasks': 0, 'total_tasks': len(tasks['replay'])})
            results = []
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = [executor.submit(branch_task, index, row) for index, row in enumerate(tasks['replay'])]
                for completed, future in enumerate(as_completed(futures), 1):
                    results.extend(future.result())
                    recorder.status(progress={'completed_tasks': completed, 'total_tasks': len(futures)})
                    recorder.write('branch_summary.json', summarize_branches(results))
            summary['branches'] = summarize_branches(results)
            shared_records = [json.loads(line) for line in (out / 'shared_context.jsonl').read_text(encoding='utf8').splitlines()]
            summary['branches']['shared_context_usage'] = summarize_usage([r['usage'] for r in shared_records])
            summary['branches']['usage_accounting'] = 'resample3/diverse3 each require shared context plus own exclusive usage; shared context charged only once in experiment total'
            recorder.write('branch_summary.json', summary['branches'])
        if args.phase in ('gate', 'both'):
            recorder.status(stage='gate', progress={'events': 0, 'tasks': len(tasks['audit'])})
            gate_usage = UsageCounter(request)
            counters = Counter()
            analysis_cache, analysis_lock = {}, threading.Lock()
            def gate_retrieve(row, retired=None):
                contract = _contract(row)
                identity = str(row['index'])
                with analysis_lock:
                    analysis = copy.deepcopy(analysis_cache.get(identity))
                if analysis is None:
                    if retired is not None:
                        raise ValueError('initial_retrieval_analysis_missing')
                    analysis = _extract_json(_content(gate_usage(analysis_prompt(contract))))
                    if not all(isinstance(analysis.get(k), list) and analysis[k]
                               for k in ('vulnerability_hypothesis', 'functional_invariants')):
                        raise ValueError('analysis_incomplete')
                    with analysis_lock:
                        analysis_cache[identity] = copy.deepcopy(analysis)
                query = {**contract, 'threat_analysis': analysis, 'current_code': '', 'failure_evidence': {}}
                candidates = [n for n in nodes if n.invariant_id not in (retired or set())]
                return retrieve(query, gate_usage, candidates)

            def generate(row, cards):
                prompt = ('生成完整可运行Python实现，只返回代码。' + CONTRACT_POLICY +
                          '\n完整任务：' + json.dumps(_contract(row), ensure_ascii=False) +
                          '\n条件化参考经验：' + experience_text(cards))
                return strip_code_fence(_content(gate_usage(prompt)))

            def record(event):
                recorder.append('gate_events.jsonl', event)
                counters[event['kind']] += 1
                recorder.status(progress={'events': sum(counters.values()), **dict(counters), 'tasks': len(tasks['audit'])})

            gate = run_global_gate([{**row, 'pool': 'D_gate'} for row in tasks['audit']],
                lambda row: gate_retrieve(row), generate, validate, workers=args.workers,
                confirmations=2, on_record=record, retrieve_filtered=lambda row, retired: gate_retrieve(row, retired))
            gate['summary']['paired'] = {}
            for old, new in [('baseline', 'memory'), ('baseline', 'filtered'), ('memory', 'filtered')]:
                def values(arm):
                    return {r['task_id']: bool(r.get('measured')) and r['state'] == 'A' for r in gate['rows'][arm]}
                old_values, new_values = values(old), values(new)
                comparison = paired_binary(old_values, new_values)
                complete = {r['task_id'] for r in gate['rows'][old] if r.get('measured')} & {
                    r['task_id'] for r in gate['rows'][new] if r.get('measured')}
                sensitivity = paired_binary({key: old_values[key] for key in complete},
                                            {key: new_values[key] for key in complete})
                sensitivity['excluded_incomplete_pairs'] = comparison['pairs'] - len(complete)
                comparison['complete_measured_pairs'] = sensitivity
                comparison['analysis_population'] = 'intention_to_test_all_recorded_tasks; missing measurements never count as success'
                gate['summary']['paired'][new + '_vs_' + old] = comparison
            comparisons = list(gate['summary']['paired'].values())
            for comparison, corrected in zip(comparisons, holm([item['p_exact_two_sided'] for item in comparisons])):
                comparison['p_holm_three_diagnostic_comparisons'] = corrected
                comparison['statistical_interpretation'] = 'diagnostic_only; filtering selected on D_gate, not independent generalization'
            sensitivity = [item['complete_measured_pairs'] for item in comparisons]
            for comparison, corrected in zip(sensitivity, holm([item['p_exact_two_sided'] for item in sensitivity])):
                comparison['p_holm_three_diagnostic_comparisons'] = corrected
            gate['summary']['usage'] = gate_usage.snapshot()
            recorder.write('gate_result.json', gate)
            retired = set(gate['retired_ids'])
            for row in memory_rows:
                copied = copy.deepcopy(row)
                if copied['invariant_id'] in retired:
                    copied['status'] = 'retired'
                    copied['diagnostic_gate_decision'] = gate['decisions'][copied['invariant_id']]
                recorder.append('filtered_memory.jsonl', copied)
            summary['gate'] = gate['summary']
        summary['usage'] = request.snapshot()
        summary['source_library_unchanged'] = file_digest(source) == memory_sha
        if not summary['source_library_unchanged']:
            raise RuntimeError('source library changed during study')
        recorder.write('result.json', summary)
        recorder.status(status='completed', stage='completed')
        return summary
    except BaseException as exc:
        recorder.status(status='failed', error=type(exc).__name__)
        recorder.write('partial_usage.json', request.snapshot())
        raise
    finally:
        recorder.close()


def main():
    """CLI 检查并行与路径参数，创建全新诊断目录；不自动接续或触发最终冻结评测。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--phase', choices=('branches', 'gate', 'both'), default='both')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--memory', default=str(DEFAULT_MEMORY))
    parser.add_argument('--pools', default=str(DEFAULT_POOLS))
    parser.add_argument('--workers', type=int, default=24)
    parser.add_argument('--max-inflight', type=int, default=60)
    parser.add_argument('--max-tokens', type=int, default=3072)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--validation-timeout', type=int, default=20)
    parser.add_argument('--distill-smoke', action='store_true')
    args = parser.parse_args()
    if args.limit < 0 or min(args.workers, args.max_inflight, args.max_tokens, args.timeout, args.validation_timeout) < 1:
        parser.error('limit >= 0 and all concurrency/token/timeout values > 0 required')
    run_study(args)


if __name__ == '__main__':
    main()

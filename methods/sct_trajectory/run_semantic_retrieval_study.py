"""训练侧固定英文经验库检索对照：层次检索与真正向量召回使用同一生成链。

仅消费 D_init 的 Phase1 副本，在 D_grow 上生成并本地验证；不读取 Plus、不写库。
首次初析共享，修复预算均为一次；完整失败与缺测保留，禁止用本次反馈选 prompt。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
import re
import shutil
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT, ROOT / 'src'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from methods.sct_trajectory.run_branch_gate_study import (  # noqa: E402
    DEFAULT_POOLS, Recorder, UsageCounter, _contract, _metrics, file_digest,
    load_phase1_memory, paired_binary, stratified_tasks, summarize_usage,
    validate_family_boundaries,
)

ARMS = ('hier_llm', 'semantic_llm')
SEED = 20260923
_CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')


def validate_memory(rows, pools, *, expected_entries=1939):
    """研究预检核验英文模型字段和 D_init 来源；只读，异常时拒绝付费调用。"""
    if len(rows) != expected_entries:
        raise ValueError('expected complete 1939-entry Phase1 English snapshot')
    ids = {name: {str(item['task_id']) for item in pools[name]}
           for name in ('source', 'replay', 'audit')}
    if [len(pools[name]) for name in ids] != [303, 273, 298]:
        raise ValueError('expected 303/273/298 training pools')
    if any(len(ids[name]) != len(pools[name]) for name in ids):
        raise ValueError('duplicate training pool task ids')
    if any(ids[a] & ids[b] for a, b in [('source', 'replay'), ('source', 'audit'), ('replay', 'audit')]):
        raise ValueError('training pools overlap')
    fields = ('high_level_invariant', 'applicability', 'positive_principle',
              'negative_guardrail', 'language_leaves', 'track_rules', 'exclusion_conditions')
    source_fields = ('root_cause', 'fix_directive', 'prev_fix_assessment', 'exclusion_conditions')
    for row in rows:
        if row.get('source', {}).get('stage') != 'phase1' or str(row['source'].get('task_id')) not in ids['source']:
            raise ValueError('memory provenance is not exclusively D_init Phase1')
        visible = {key: row.get(key) for key in fields}
        visible['source'] = {key: row['source'].get(key) for key in source_fields}
        if _CJK.search(json.dumps(visible, ensure_ascii=False)):
            raise ValueError('non-English CJK in model-visible memory: ' + str(row.get('invariant_id')))
    return ids


from methods.sct_trajectory.context_pipeline import safe_feedback


def arm_order(task_id):
    """按固定种子和题目 ID 随机化两臂顺序，复跑不依赖线程调度。"""
    result = list(ARMS)
    random.Random(f'{SEED}:{task_id}').shuffle(result)
    return result


def run_pair(row, *, request, retrieve, generate, validate, propose, execute, measured,
             analyze, on_record):
    """D_grow 同题两臂：共享初析，各自检索/生成/一次修复，完整记录失败与用量。

    输入回调只读冻结库，正式训练测试仅交给验证回调；模型无法读取测试/答案。
    输出两条方法记录和一次共享初析用量；不提炼、不门控、不修改长期经验。
    """
    contract = _contract(row)
    private_fields = {'unittest', 'unit_test', 'tests', 'test_cases', 'solution', 'code',
                      'ground_truth', 'patched_code', 'vulnerable_code', 'answer'}
    if private_fields.intersection(contract):
        raise ValueError('private_task_fields_in_public_contract')
    shared = UsageCounter(request)
    shared_error = None
    try:
        initial = analyze(contract, shared)
        if not all(isinstance(initial.get(k), list) and initial[k]
                   for k in ('vulnerability_hypothesis', 'functional_invariants')):
            raise ValueError('initial_analysis_incomplete')
    except Exception as exc:
        initial = {'unmeasured': True}
        shared_error = type(exc).__name__
    context = {'task_id': row['index'], 'initial_analysis': initial,
               'error_type': shared_error, 'usage': shared.snapshot()}
    context['sha256'] = hashlib.sha256(json.dumps(initial, sort_keys=True).encode()).hexdigest()
    on_record('shared_context.jsonl', context)
    results = []
    for arm in arm_order(row['index']):
        started = time.monotonic()
        counted = UsageCounter(request)
        attempts, reference, feedback, suite = [], '', None, None
        error = None
        try:
            for attempt in range(2):
                retrieval_calls = []

                def cards_provider(query):
                    retrieved = retrieve(arm, query, counted)
                    if isinstance(retrieved, tuple):
                        cards, trace = retrieved
                    else:
                        cards, trace = retrieved, None
                    retrieval_calls.append({'query_sha256': hashlib.sha256(
                        json.dumps(query, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                        'cards': copy.deepcopy(cards), 'selection_trace': copy.deepcopy(trace)})
                    return cards

                generation = generate(contract, [], requester=counted, reference_code=reference,
                    previous_evidence=feedback, cards_provider=cards_provider,
                    initial_analysis=copy.deepcopy(initial) if attempt == 0 else None)
                code = generation.get('code') or ''
                evidence = validate(row, code) if code else {}
                is_measured = measured(evidence)
                functional = is_measured and evidence.get('functional', {}).get('status') == 'pass'
                security = is_measured and evidence.get('security', {}).get('status') == 'pass'
                result = {'attempt': attempt, 'code': code, 'evidence': evidence,
                    'measured': is_measured, 'functional': functional, 'security': security,
                    'joint': functional and security, 'retrieval_calls': retrieval_calls,
                    'generation': {k: v for k, v in generation.items() if k != 'prompts'},
                    'error_type': generation.get('error_type')}
                if code:
                    if suite is None:
                        suite = propose(contract, generation.get('initial_analysis') or initial, counted)
                    result['internal_suite'] = suite
                    result['internal_checks'] = execute(code, contract.get('entry_point') or contract.get('function_name'), suite)
                attempts.append(result)
                if result['joint']:
                    break
                reference, feedback = code, safe_feedback(evidence, result.get('internal_checks'))
        except Exception as exc:
            error = type(exc).__name__
            # 若第二次调用中断，不能把首轮结果冒充已完成的最终尝试。
            attempts.append({'attempt': len(attempts), 'code': '', 'evidence': {},
                'measured': False, 'functional': False, 'security': False, 'joint': False,
                'error_type': error})
        item = {'task_id': row['index'], 'cwe': row.get('CWE_ID'), 'family_id': row.get('family_id'),
            'arm': arm, 'attempts': attempts, 'error_type': error, 'shared_initial_error': shared_error,
            'shared_initial_sha256': context['sha256'], 'usage': counted.snapshot(),
            'elapsed_seconds': time.monotonic() - started}
        on_record('rows.jsonl', item)
        results.append(item)
    return results, context


def summarize(rows):
    """最终 Joint 为唯一主终点；首次为次要，完整测量敏感性与 ITT 同时报告。"""
    groups = {arm: [row for row in rows if row['arm'] == arm] for arm in ARMS}
    output = {'primary_endpoint': 'final_joint', 'independent_heldout': False,
        'selection_warning': 'Training development comparison; not independent generalization evidence.',
        'arms': {}, 'paired': {}}
    for arm, items in groups.items():
        output['arms'][arm] = {'rows': len(items),
            'first': _metrics([(row.get('attempts') or [{}])[0] for row in items]),
            'final': _metrics([(row.get('attempts') or [{}])[-1] for row in items]),
            'unmeasured_attempts': sum(not a.get('measured') for row in items for a in row['attempts']),
            'errors': dict(Counter(str(a.get('error_type')) for row in items for a in row['attempts'] if a.get('error_type'))),
            'stage_errors': dict(Counter(f"{s.get('stage')}:{s.get('error', s.get('status'))}" for row in items
                for a in row['attempts'] for s in a.get('generation', {}).get('stages', [])
                if s.get('status') in ('failed', 'degraded'))),
            'exclusive_chat_usage': summarize_usage([row['usage'] for row in items])}
    for label, index in (('first', 0), ('final', -1)):
        maps = {arm: {str(row['task_id']): (row.get('attempts') or [{}])[index] for row in items}
                for arm, items in groups.items()}
        values = {arm: {key: bool(a.get('measured')) and bool(a.get('joint')) for key, a in items.items()}
                  for arm, items in maps.items()}
        paired = paired_binary(values[ARMS[0]], values[ARMS[1]])
        complete = {key for key in maps[ARMS[0]].keys() & maps[ARMS[1]].keys()
                    if maps[ARMS[0]][key].get('measured') and maps[ARMS[1]][key].get('measured')}
        paired['complete_measured_sensitivity'] = paired_binary(
            {key: values[ARMS[0]][key] for key in complete}, {key: values[ARMS[1]][key] for key in complete})
        paired['complete_measured_sensitivity']['excluded_pairs'] = paired['pairs'] - len(complete)
        output['paired'][label + '_joint'] = paired
    return output


def run_study(args):
    """冻结输入和源代码后启动只读训练对照；真实聊天与向量请求共享同一个并发闸门。"""
    from methods.sct_trajectory.run_closed_loop import _load_tasks, _requester, load_key
    from methods.sct_trajectory.context_pipeline import run_context_pipeline, analysis_prompt
    from methods.sct_trajectory.agent_pipeline import _content, _extract_json
    from methods.sct_trajectory.closed_loop import validate_and_state
    from methods.sct_trajectory.internal_checks import propose_checks, execute_checks
    from methods.sct_trajectory.global_gate import evidence_is_measured
    from methods.sct_trajectory.hsk_tree import HskTree, SecurityInvariantNode
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient

    out = (ROOT / args.out).resolve()
    if not out.is_relative_to((ROOT / 'translation_work/diagnostics').resolve()):
        raise ValueError('out must be a fresh directory under translation_work/diagnostics')
    if out.exists():
        raise FileExistsError('refusing to overwrite existing study directory')
    memory_path, pools_path = (ROOT / args.memory).resolve(), (ROOT / args.pools).resolve()
    memory = load_phase1_memory(memory_path)
    pools = json.loads(pools_path.read_text(encoding='utf8'))
    ids = validate_memory(memory, pools)
    loaded = _load_tasks(0)
    manifest_path = ROOT / 'data/external/secodeplt/derived_metadata/family_manifest.json'
    family_checks = validate_family_boundaries(loaded, pools, json.loads(manifest_path.read_text(encoding='utf8')))
    selected = [row for row in loaded if str(row['index']) in ids['replay']]
    if len(selected) != 273:
        raise ValueError('expected all 273 D_grow tasks')
    tasks = stratified_tasks(selected, args.limit)
    nodes = [SecurityInvariantNode.from_dict(row) for row in memory]
    source_files = [Path(__file__), *[Path(__file__).with_name(name + '.py') for name in (
        'run_branch_gate_study', 'semantic_retrieval', 'hier_retrieval', 'retriever', 'context_pipeline',
        'agent_pipeline', 'closed_loop', 'run_closed_loop', 'internal_checks', 'hsk_tree', 'schemas', 'ablation',
        'global_gate', 'english_policy', 'run_artifacts', 'selector_protocol')], ROOT / 'methods/sct_agent/validation_evidence.py']
    source_files += list((ROOT / 'methods/sct_lifecycle_replay').glob('*.py'))
    source_hashes = {str(path.relative_to(ROOT)): file_digest(path) for path in source_files}
    input_hashes = {str(path): file_digest(path) for path in (memory_path, pools_path, manifest_path,
        ROOT / 'data/external/secodeplt/secodeplt/data.json')}
    out.mkdir(parents=True, exist_ok=False)
    recorder = Recorder(out)
    request = None
    try:
        for path in source_files:
            target = out / 'source_snapshot' / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        shutil.copy2(memory_path, out / 'input_phase1_memory.jsonl')
        shutil.copy2(pools_path, out / 'input_pools.json')
        recorder.write('run_metadata.json', {'created_at': datetime.now().isoformat(), 'config': vars(args),
            'model': 'deepseek-v3.2', 'temperature': 0, 'seed': SEED, 'arms': ARMS,
            'primary_endpoint': 'final_joint', 'max_repairs': 1, 'memory_entries': len(memory),
            'source_sha256': source_hashes, 'input_sha256': input_hashes,
            'task_ids': [row['index'] for row in tasks], 'training_family_preflight': family_checks,
            'backend': 'local_python_isolated', 'memory_updates': False, 'final_test_access': False,
            'shared_initial_analysis': True, 'feedback_policy': 'status_only_no_test_inputs_or_answers',
            'language_preflight': 'model-visible card fields contain no CJK; not semantic language certification',
            'independent_heldout': False, 'embedding_usage': 'aggregate client accounting; cache may preexist'})
        semaphore = threading.BoundedSemaphore(args.max_inflight)
        request = UsageCounter(_requester('deepseek-v3.2', args.timeout, max_tokens=args.max_tokens,
            max_inflight=args.max_inflight, semaphore=semaphore))
        embedding = EmbeddingClient(model=args.embedding_model, cache_path=ROOT / args.embedding_cache,
            key_loader=load_key, semaphore=semaphore)
        config = get_config('A7')

        def retrieve(arm, query, counted):
            retriever = HskTreeRetriever(HskTree(), requester=counted, ablation=config,
                retrieval_mode=arm, embedding_client=embedding)
            cards = retriever.search(query, limit=3, pool_nodes=nodes)
            return cards, retriever.last_hier_trace

        def work(row):
            return run_pair(row, request=request, retrieve=retrieve, generate=run_context_pipeline,
                validate=lambda task, code: validate_and_state(task, code, timeout=args.validation_timeout)[0],
                propose=propose_checks, execute=execute_checks, measured=evidence_is_measured,
                analyze=lambda contract, counted: _extract_json(_content(counted(analysis_prompt(contract)))),
                on_record=recorder.append)

        results, shared_records = [], []
        recorder.status(stage='paired_study', progress={'completed_tasks': 0, 'total_tasks': len(tasks)})
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(work, row) for row in tasks]
            for done, future in enumerate(as_completed(futures), 1):
                pair, shared = future.result()
                results.extend(pair)
                shared_records.append(shared)
                recorder.status(progress={'completed_tasks': done, 'total_tasks': len(tasks), 'rows': len(results)})
                recorder.write('summary.json', summarize(results))
        summary = summarize(results)
        summary['shared_initial_chat_usage'] = summarize_usage([row['usage'] for row in shared_records])
        summary['chat_usage'] = request.snapshot()
        summary['embedding_usage'] = embedding.usage
        summary['input_unchanged'] = all(file_digest(path) == digest for path, digest in input_hashes.items())
        summary['source_unchanged'] = all(file_digest(ROOT / path) == digest for path, digest in source_hashes.items())
        if len(results) != len(tasks) * 2 or len({(str(r['task_id']), r['arm']) for r in results}) != len(results):
            raise RuntimeError('incomplete_or_duplicate_paired_rows')
        if not summary['input_unchanged'] or not summary['source_unchanged']:
            raise RuntimeError('study_input_or_source_changed')
        recorder.write('summary.json', summary)
        recorder.status(status='completed', stage='completed')
        return summary
    except BaseException as exc:
        recorder.status(status='failed', error=type(exc).__name__)
        if request is not None:
            recorder.write('partial_usage.json', request.snapshot())
        raise
    finally:
        recorder.close()


def main():
    """CLI 默认全 D_grow，输出必须全新；不自动训练、选 prompt 或启动 Plus。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory', required=True)
    parser.add_argument('--pools', default=str(DEFAULT_POOLS))
    parser.add_argument('--out', required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--workers', type=int, default=24)
    parser.add_argument('--max-inflight', type=int, default=80)
    parser.add_argument('--max-tokens', type=int, default=3072)
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('--validation-timeout', type=int, default=20)
    parser.add_argument('--embedding-model', default='text-embedding-3-large')
    parser.add_argument('--embedding-cache', required=True)
    args = parser.parse_args()
    if args.limit < 0 or min(args.workers, args.max_inflight, args.max_tokens, args.timeout, args.validation_timeout) < 1:
        parser.error('limit >= 0 and positive concurrency/token/timeout values required')
    if args.max_inflight > 80:
        parser.error('combined provider concurrency must not exceed 80')
    run_study(args)


if __name__ == '__main__':
    main()

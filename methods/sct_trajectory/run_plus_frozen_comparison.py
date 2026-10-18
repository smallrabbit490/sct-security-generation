"""Plus 冻结经验库双臂评测入口。

该入口只读训练侧 M*，不把 Plus 反馈写入经验库；两臂共用完整任务契约、
最新 HSK 层次检索器和 Docker 常驻验证。当前文件先提供评测契约与汇总函数，
真实请求与验证由后续 main 接入，避免继续误用旧的 13 卡片评测器。
"""
from __future__ import annotations

import re
import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def task_contract(row: dict[str, Any]) -> dict[str, Any]:
    """保留完整 Plus 任务说明和入口契约；不携带测试、答案或代码字段。"""
    problem = str(row.get("Problem") or "")
    return {
        "task_id": f"Plus:{row.get('ID', '')}",
        "CWE_ID": str(row.get("ID", "")).split("_", 1)[0].replace("CWE-", ""),
        "language": "python",
        "description": problem,
        "entry_point": str(row.get("Entry_Point") or ""),
        "contract": "保留函数名、参数、返回值和题目明确的异常契约；完整支持题目列出的合法输入。",
    }


def repair_feedback(evidence: dict[str, Any]) -> dict[str, Any]:
    """只向修复 prompt 传递测试状态和错误类别，剥离测试字面量与答案。"""
    out: dict[str, Any] = {}
    for key in ("functional", "security", "syntax_or_compile"):
        item = evidence.get(key) or {}
        if not isinstance(item, dict):
            item = {"passed": bool(item), "details": evidence.get(f"{key}_detail", "")}
        detail = str(item.get("details") or item.get("error") or "")
        # 评测反馈不能把隐藏测试输入或期望答案变成模型可见答案。
        detail = re.sub(r"(['\"]).*?\1", "<literal>", detail)
        detail = re.sub(r"\b\d+(?:\.\d+)?\b", "<number>", detail)
        out[key] = {"status": str(item.get("status") or ("pass" if item.get("passed") else "fail")),
                    "details": detail.split(":", 1)[0][:120]}
    return out


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """按方法、同一总分母统计首次与修复后结果。"""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("method", "unknown")), []).append(row)
    result: dict[str, Any] = {}
    for method, items in grouped.items():
        first = [((r.get("attempts") or [{}])[0]) for r in items]
        final = [((r.get("attempts") or [{}])[-1]) for r in items]
        result[method] = {
            "total": len(items),
            "first": {k: sum(bool(x.get(k)) for x in first) for k in ("functional", "security", "joint")},
            "final": {k: sum(bool(x.get(k)) for x in final) for k in ("functional", "security", "joint")},
            "repair_attempts": sum(len(r.get("attempts") or []) > 1 for r in items),
            "repair_successes": sum(len(r.get("attempts") or []) > 1 and not (r["attempts"][0].get("joint")) and r["attempts"][-1].get("joint") for r in items),
        }
    return result


def generation_feedback(evidence, internal=None):
    """修复输入边界：官方只给脱敏状态，内部生成测试给独立标注的执行证据；不写库。"""
    feedback = repair_feedback(evidence) if evidence else {}
    if internal:
        if internal.get('source') != 'self_generated_internal':
            raise ValueError('invalid_internal_evidence_source')
        feedback['internal_checks'] = internal
    return feedback or None


def generate(method, contract, cards, requester, reference='', evidence=None, *, pipeline=None,
             context_mode=False, cards_provider=None, initial_analysis=None, internal=None):
    """冻结评测生成阶段：相同契约、经验与脱敏反馈输入，输出代码和阶段证据。

    只复用现有生成流程，不蒸馏、不修改训练记忆。模型空响应、截断与解析失败
    由现有流水线显式报告；动态测试留给独立 Docker 验证阶段。
    """
    from .agent_pipeline import run_pipeline, dual_track_text, previous_evidence_block, _content, strip_code_fence
    def prompt_code(prompt):
        code = strip_code_fence(_content(requester(prompt)))
        if not code:
            raise ValueError('empty_code')
        return {'code': code, 'error_type': None, 'workflow_completed': True}
    feedback = generation_feedback(evidence, internal)
    if context_mode:
        from .context_pipeline import run_context_pipeline, CONTRACT_POLICY, experience_text
        if method == 'cle_four_agent':
            result = run_context_pipeline(contract, cards, requester=requester, reference_code=reference,
                previous_evidence=feedback, cards_provider=cards_provider, initial_analysis=initial_analysis)
            return {k: v for k, v in result.items() if k != 'prompts'}
        # prompt臂只调用一次生成；共享的初析只用于检索，不能额外变成该臂的规划步骤。
        prompt = ('生成完整可运行Python实现，只返回代码。' + CONTRACT_POLICY +
                  '\n完整任务：' + json.dumps(contract, ensure_ascii=False) +
                  '\n条件化参考经验：' + experience_text(cards) + '\n上一版代码：' + reference +
                  '\n许可反馈：' + json.dumps(feedback or {}, ensure_ascii=False))
        return prompt_code(prompt)
    if method == 'cle_four_agent':
        result = (pipeline or run_pipeline)(contract, cards, requester=requester,
                    reference_code=reference, previous_evidence=feedback, contract_freeze=True)
        return {k: v for k, v in result.items() if k != 'prompts'}
    prompt = ('生成完整安全 Python 实现，只返回代码。严格保持任务规定的函数名、参数、'
              '返回值、合法输入和异常契约；经验不适用时忽略，不添加契约外约束。\n'
              + json.dumps(contract, ensure_ascii=False) + '\n经验：\n' + dual_track_text(cards)
              + ('\n上一版代码：\n' + reference if reference else '')
              + previous_evidence_block(feedback))
    return prompt_code(prompt)


def evaluate(task, code, timeout):
    """只在既有 Docker 常驻池测量语法/加载、功能、安全；其余项目未测量。

    输入候选代码和独立测试任务，返回完整证据及布尔指标。环境故障单列，
    不触发经验更新；超时和候选运行异常保留原因。
    """
    from translation_pipeline.python_validator import validate_python_secure
    result = validate_python_secure(task, code=code, timeout=timeout)
    details = result.details
    worker = details.get('worker_result', {})
    env_error = details.get('error_type') == 'environment_error'
    evidence = {}
    for name, key in [('functional', 'fp'), ('security', 'sp')]:
        item = worker.get('tests', {}).get(key, {})
        evidence[name] = {'status': ('unmeasured' if env_error or not item else 'pass' if item.get('passed') else 'fail'),
                          'details': item.get('error') or details.get('error_type') or ''}
    evidence['syntax_or_compile'] = {'status': 'unmeasured' if 'compile' not in worker else 'pass' if worker['compile'] else 'fail'}
    for name in ['static_analysis', 'type_check', 'resource_measurement']:
        evidence[name] = {'status': 'unmeasured'}
    evidence['timeout'] = {'status': 'fail' if details.get('error_type') == 'timeout' else 'pass'}
    fp = evidence['functional']['status'] == 'pass'
    sp = evidence['security']['status'] == 'pass'
    return {'functional': fp, 'security': sp, 'joint': fp and sp, 'evidence': evidence,
            'environment_error': env_error, 'validation': details}


def main():
    """冻结双臂评测：先正向校准，再生成与单轮修复，逐行落盘并校验 M* 未变。

    两臂从完整题目生成（不提供答案或漏洞源码），共用首次检索卡片；修复轮
    重新调用最新检索器，只传回当前任务的脱敏验证证据，不生成经验或执行门控。
    """
    import os, hashlib, shutil, subprocess, threading, time
    from datetime import datetime
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from collections import Counter
    sys.path.insert(0, str(ROOT / 'src'))
    from translation_pipeline.persistent_container import cleanup_stale_containers, close_implicit_pools
    from .hsk_tree import HskTree, SecurityInvariantNode
    from .retriever import HskTreeRetriever
    from .ablation import get_config
    from .run_closed_loop import _requester
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--model', default='deepseek-v3.2')
    parser.add_argument('--max-tokens', type=int, default=2048)
    parser.add_argument('--calibration-only', action='store_true')
    parser.add_argument('--memory', default='translation_work/sct_runs/cle_full_874_20260922/frozen/m_star.jsonl')
    parser.add_argument('--context-pipeline', action='store_true')
    parser.add_argument('--internal-checks', action='store_true')
    parser.add_argument('--subsets', nargs='+', choices=['Base', 'Plus'], default=['Plus'])
    parser.add_argument('--prompt-only', action='store_true')
    parser.add_argument('--no-memory-control', action='store_true')
    parser.add_argument('--retrieval-mode', choices=['hier_llm', 'semantic_llm', 'semantic_sim', 'semantic_q'], default='hier_llm')
    parser.add_argument('--semantic-delta', type=float)
    parser.add_argument('--lambda-q', type=float, default=0.5)
    parser.add_argument('--embedding-model', default='text-embedding-3-large')
    parser.add_argument('--embedding-cache', default='translation_work/cache/embeddings/cle.sqlite3')
    args = parser.parse_args()
    if args.retrieval_mode in ('semantic_sim', 'semantic_q') and args.semantic_delta is None:
        parser.error('Q/sim frozen retrieval requires calibrated --semantic-delta')
    out = (ROOT / args.out).resolve()
    if not out.is_relative_to((ROOT / 'translation_work').resolve()):
        parser.error('out must be inside translation_work')
    if args.workers < 1 or args.limit < 0:
        parser.error('workers must be positive; limit must be nonnegative')
    out.mkdir(parents=True, exist_ok=False)
    os.environ['SAFECODER_DOCKER_POOL_SIZE'] = str(args.workers)
    os.environ['SAFECODER_PYTHON_DOCKER_IMAGE'] = 'safecoder-python-validator:local'
    cleanup_stale_containers()
    source = ROOT / args.memory
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before_hash = digest(source)
    data_files = {subset: ROOT / f'data/SecEvoBasePlus/{subset}/Python_{subset}.json'
                  for subset in args.subsets}
    data = []
    for subset, data_path in data_files.items():
        data.extend((subset, row) for row in json.loads(data_path.read_text(encoding='utf-8')))
    if args.limit:
        data = [(subset, row) for subset in args.subsets
                for _, row in [item for item in data if item[0] == subset][:args.limit]]
    memory = [SecurityInvariantNode.from_dict(json.loads(x)) for x in source.read_text(encoding='utf-8').splitlines() if x.strip()]
    tree = HskTree()
    config = get_config('A7')
    metadata = {'created_at': datetime.now().isoformat(), 'model': args.model, 'temperature': 0,
                'max_tokens': args.max_tokens, 'workers': args.workers, 'repairs': 1, 'subsets': args.subsets,
                'memory_source': str(source), 'memory_sha256': before_hash, 'memory_count': len(memory),
                'memory_statuses': dict(Counter(n.status for n in memory)), 'retrieval_mode': args.retrieval_mode,
                'retrieval_statuses': config.retrieval_statuses,
                'dataset_sha256': {subset: digest(path) for subset, path in data_files.items()},
                'tasks': len(data), 'feedback_channel': 'official_feedback_disabled; self_generated_checks_only',
                'backend': 'persistent_docker', 'image': os.environ['SAFECODER_PYTHON_DOCKER_IMAGE'],
                'credential_source': 'environment_or_local:apikey.txt', 'source_code_provided': False,
                'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()}
    metadata.update(context_pipeline=args.context_pipeline, internal_checks=args.internal_checks,
                    internal_feedback='self_generated_tests_only', output_schema_version=2,
                    prompt_repair_query='initial_threat_analysis_plus_current_code_and_redacted_and_internal_feedback',
                    cle_repair_query='fresh_analysis_then_retrieval_then_experience_reanalysis')
    source_files = [Path(__file__), Path(__file__).with_name('retriever.py'), Path(__file__).with_name('hier_retrieval.py'), Path(__file__).with_name('agent_pipeline.py')]
    source_files += [Path(__file__).with_name(name) for name in ('context_pipeline.py', 'internal_checks.py', 'run_closed_loop.py')]
    metadata['source_hashes'] = {str(p.relative_to(ROOT)): digest(p) for p in source_files}
    snapshot = out / 'source_snapshot'
    snapshot.mkdir(exist_ok=True)
    for path in source_files:
        shutil.copy2(path, snapshot / path.name)
    def write(name, value):
        (out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    write('run_metadata.json', metadata)
    usage_lock = threading.Lock()
    usage = {'calls': 0, 'failed_calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
    # 推理模型需为最终代码保留输出预算；显式参数同时记录在元数据中。
    base_request = _requester(args.model, 60, max_tokens=args.max_tokens, max_inflight=args.workers)
    def request(prompt):
        try:
            response = base_request(prompt)
        except Exception as exc:
            with usage_lock:
                usage['failed_calls'] += 1
                with (out / 'request_errors.jsonl').open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps({'type': type(exc).__name__,
                        'diagnostics': getattr(exc, 'diagnostics', [])}, ensure_ascii=False) + '\n')
            raise
        with usage_lock:
            usage['calls'] += 1
            for key in ['prompt_tokens', 'completion_tokens', 'total_tokens']:
                usage[key] += (response.get('usage') or {}).get(key, 0)
        return response
    embedding_client = None
    if args.retrieval_mode in ('semantic_llm', 'semantic_sim', 'semantic_q'):
        from .semantic_retrieval import EmbeddingClient
        from .run_closed_loop import load_key
        embedding_client = EmbeddingClient(model=args.embedding_model, cache_path=ROOT / args.embedding_cache,
                                           key_loader=load_key, timeout=120)
    metadata['embedding_model'] = args.embedding_model if embedding_client else None
    metadata['prompt_only'] = args.prompt_only
    metadata['no_memory_control'] = args.no_memory_control
    write('run_metadata.json', metadata)
    def retrieve(contract, pool):
        retriever = HskTreeRetriever(tree, requester=request, ablation=config,
                                     retrieval_mode=args.retrieval_mode, embedding_client=embedding_client,
                                     semantic_delta=args.semantic_delta, lambda_q=args.lambda_q)
        cards = retriever.search(contract, limit=3, pool_nodes=pool)
        return cards, getattr(retriever, 'last_hier_trace', {})
    rows = []
    started = time.time()
    try:
        # 正向对照只进入验证器，答案绝不传给模型。逐题验证避免依赖问题伪装成低分。
        calibration = []
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(evaluate, task, task['Secure Code'], 30): (subset, task)
                       for subset, task in data}
            for future in as_completed(futures):
                subset, task = futures[future]
                calibration.append({'subset': subset, 'task_id': task['ID'], **future.result()})
        write('calibration.json', calibration)
        passed = sum(r['joint'] for r in calibration)
        print(f'calibration {passed}/{len(data)}', flush=True)
        if passed != len(data):
            raise RuntimeError('positive_control_failed_no_generation_started')
        if args.calibration_only:
            return
        def one(item):
            subset, task = item
            contract = task_contract(task)
            contract['task_id'] = f"{subset}:{task['ID']}"
            initial = None
            preparation_errors = []
            try:
                if args.context_pipeline:
                    from .context_pipeline import analysis_prompt
                    from .agent_pipeline import _extract_json, _content
                    initial = _extract_json(_content(request(analysis_prompt(contract))))
                    if not all(isinstance(initial.get(k), list) and initial[k]
                               for k in ('vulnerability_hypothesis', 'functional_invariants')):
                        raise ValueError('initial_analysis_incomplete')
            except Exception as exc:
                initial = {'unmeasured': True, 'error': type(exc).__name__}
                preparation_errors.append('initial_analysis:' + type(exc).__name__)
            try:
                cards, trace = retrieve({**contract, 'threat_analysis': initial} if initial else contract, memory)
            except Exception as exc:
                cards, trace = [], {'fallback': 'preparation_error', 'error': type(exc).__name__}
                preparation_errors.append('retrieval:' + type(exc).__name__)
            suite = None
            if args.internal_checks:
                from .internal_checks import propose_checks, execute_checks
                suite = propose_checks(contract, initial or {}, request)
            task_rows = []
            arms = [('prompt_concat', memory)]
            if args.no_memory_control:
                arms.append(('prompt_nomemory', []))
            if not args.prompt_only:
                arms.append(('cle_four_agent', memory))
            for method, arm_memory in arms:
                row = {'subset': subset, 'task_id': task['ID'], 'method': method, 'attempts': [],
                       'preparation_errors': preparation_errors}
                arm_cards, arm_trace = (cards, trace) if arm_memory else ([], {'retrieval_mode': 'empty_memory'})
                reference = ''
                prev = None
                internal = None
                for attempt in range(2):
                    try:
                        selected, htrace = arm_cards, arm_trace
                        def provider(query):
                            nonlocal htrace
                            found, htrace = retrieve(query, arm_memory)
                            return found
                        if attempt > 0 and (not args.context_pipeline or method == 'prompt_concat'):
                            repair_query = {**contract, 'threat_analysis': initial,
                                            'current_code': reference,
                                            'failure_evidence': generation_feedback(prev, internal)}
                            selected, htrace = retrieve(repair_query if args.context_pipeline else contract, arm_memory)
                        generation = generate('prompt_concat' if method == 'prompt_nomemory' else method,
                            contract, selected, request, reference, prev,
                            context_mode=args.context_pipeline,
                            cards_provider=provider if args.context_pipeline and attempt > 0 else None,
                            initial_analysis=initial if attempt == 0 else None, internal=internal)
                        selected = generation.get('cards', selected)
                        code = generation.get('code', '').strip()
                        internal_result = execute_checks(code, contract['entry_point'], suite, backend='docker', timeout=10) if suite and code else None
                        result = evaluate(task, code, 30) if code else {'functional': False, 'security': False, 'joint': False, 'evidence': {}}
                        record = {**result, 'code': code, 'generation': generation, 'cards': selected,
                                  'retrieval_trace': htrace, 'attempt': attempt,
                                  'internal_checks': internal_result, 'internal_suite': suite}
                        row['attempts'].append(record)
                        # 独立测试不得按隐藏Joint早停或将其状态回流；固定两次，取末次代码。
                        if result.get('environment_error'):
                            break
                        reference = code
                        prev = None
                        internal = internal_result
                    except Exception as exc:
                        reason = str(exc) if isinstance(exc, ValueError) and str(exc) in {
                            'empty_code', 'empty_model_content', 'invalid_api_response',
                            'model_output_truncated'} else type(exc).__name__
                        row['attempts'].append({'functional': False, 'security': False, 'joint': False,
                                                'code': '', 'error_type': reason, 'attempt': attempt,
                                                'request_diagnostics': getattr(exc, 'diagnostics', [])})
                        break
                task_rows.append(row)
            return task_rows
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(one, task): task for task in data}
            for future in as_completed(futures):
                batch = future.result()
                rows.extend(batch)
                with (out / 'rows.jsonl').open('a', encoding='utf-8') as handle:
                    for row in batch:
                        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
                write('summary.json', summarize(rows))
                write('usage.json', usage)
                arm_count = 1 + int(args.no_memory_control) + int(not args.prompt_only)
                print(f'completed {len(rows)//arm_count}/{len(data)} tasks, {usage["calls"]} calls', flush=True)
        metadata['memory_unchanged'] = digest(source) == before_hash
        if not metadata['memory_unchanged']:
            raise RuntimeError('frozen_memory_changed')
        metadata['completed_at'] = datetime.now().isoformat()
        metadata['elapsed_seconds'] = round(time.time() - started, 2)
        write('run_metadata.json', metadata)
        print(json.dumps(summarize(rows), ensure_ascii=False), flush=True)
    finally:
        close_implicit_pools()

if __name__ == '__main__':
    main()

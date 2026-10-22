"""独立的 CLE 公开契约/修复消费者；不改变历史 P7，也不学习或修改 Q。

先冻结公开内部用例，再生成至多 c0/c1，按公开证据选择交付代码，最后正式计分。
内部检查可能错误或不完整；其通过不是 Joint 通过，正式成绩只来自原验证器。
"""
from __future__ import annotations

import copy
import hashlib
import json

from .runner import plt_contract, public_contract


VARIANT = 'P7_public_contract_v1'
INFRASTRUCTURE_ERRORS = {'environment_error', 'plt_validator_exception',
                         'validator_exception', 'local_worker_error'}


def measured_evidence(evidence):
    """兼容旧验证器把基础设施异常写成 fail 的情况；候选异常/超时仍是失败。"""
    return all(evidence.get(k, {}).get('status') in ('pass', 'fail')
               and evidence.get(k, {}).get('error_type') not in INFRASTRUCTURE_ERRORS
               for k in ('functional', 'security'))


def complete_public_query(query):
    """检索阶段补回 PLT 公开 return/raise；只映射到已有许可键，不改旧检索器。

    输入必须是公开任务及公开修复证据；输出供真实 embedding/selector 消费。
    不读取测试、参考答案或 Q，文本内容哈希自然区分旧缓存。
    """
    from methods.sct_trajectory.semantic_retrieval import PUBLIC_FIELDS
    result = {key: copy.deepcopy(query[key]) for key in PUBLIC_FIELDS if key in query}
    for old, new in (('return', 'return_description'), ('raise', 'exceptions')):
        value = query.get(old)
        if value not in (None, '', [], {}):
            if result.get(new) not in (None, '', [], {}) and result[new] != value:
                result[new] = {'declared': result[new], 'additional_public_contract': value}
            else:
                result[new] = copy.deepcopy(value)
    return result


def make_provider(memory, requester, embedding_client, *, retrieval_mode='semantic_llm',
                  delta=-1.0, lambda_q=0.5, max_experiences=3):
    """前向检索只读显式冻结库，保存实际候选轨迹；Q 模式亦不更新数值。"""
    from methods.sct_trajectory.ablation import get_config
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.retriever import HskTreeRetriever
    if not memory:
        raise ValueError('empty_frozen_memory')
    traces = []

    def provider(query):
        retriever = HskTreeRetriever(HskTree(), requester=requester, ablation=get_config('A7'),
            retrieval_mode=retrieval_mode, embedding_client=embedding_client,
            semantic_delta=delta, lambda_q=lambda_q)
        found = retriever.search(complete_public_query(query), limit=max_experiences,
                                 pool_nodes=memory)
        traces.append(copy.deepcopy(getattr(retriever, 'last_hier_trace', None)))
        return found

    return provider, traces


def official_evaluate(subset, task, code):
    """交付决策之后才调用原验证器；PLT 本地、Base/Plus 原 Docker 环境。

    不把正式 F/S 送回生成、选择或 Q；环境事故保留为未测量。
    """
    if subset == 'PLT':
        from methods.sct_trajectory.closed_loop import validate_and_state
        evidence, state = validate_and_state(task, code, timeout=20)
        measured = measured_evidence(evidence)
        functional = evidence.get('functional', {}).get('status') == 'pass'
        security = evidence.get('security', {}).get('status') == 'pass'
        return {'measured': measured, 'functional': functional, 'security': security,
                'joint': measured and functional and security,
                'validation': {'evidence': evidence, 'state': state}}
    if subset not in ('Base', 'Plus'):
        raise ValueError('unknown_dataset')
    from methods.sct_trajectory.run_plus_frozen_comparison import evaluate
    result = evaluate(task, code, 30)
    measured = not result['environment_error'] and all(
        result['evidence'].get(k, {}).get('status') in ('pass', 'fail')
        for k in ('functional', 'security'))
    return {'measured': measured, 'functional': result['functional'],
            'security': result['security'], 'joint': measured and result['joint'],
            'validation': result}


def run_one(subset, task, requester, provider, *, backend=None, pipeline=None,
            suite_builder=None, check_executor=None, evaluator=None):
    """冻结消费者逐题执行：公开输入→固定用例→至多两候选→公开选择→正式计分。

    保留全部真实尝试、提示及失败；无选择价值的修复记录跳过，不伪造 c1。
    注入接口用于离线行为测试，不把注入的假响应记录为真实模型实验。
    """
    from methods.sct_trajectory.context_pipeline import run_context_pipeline
    from methods.sct_trajectory.internal_checks import propose_checks, execute_checks
    from methods.sct_trajectory.public_contract_checks import compile_public_contract, check_public_contract
    from methods.sct_trajectory.public_repair_policy import (
        bind_public_result, public_repair_feedback, choose_public_candidate, repair_opportunity)

    if subset not in ('PLT', 'Base', 'Plus'):
        raise ValueError('unknown_dataset')
    backend = backend or ('local' if subset == 'PLT' else 'docker')
    if subset != 'PLT' and backend != 'docker':
        raise ValueError('Base_Plus_require_original_Docker_backend')
    pipeline = pipeline or run_context_pipeline
    suite_builder = suite_builder or propose_checks
    check_executor = check_executor or execute_checks
    evaluator = evaluator or official_evaluate
    contract = copy.deepcopy(plt_contract(task) if subset == 'PLT' else public_contract(subset, task))
    requirements = compile_public_contract(contract)
    contract['implementation_constraints'] = requirements
    # 用例先于任何候选生成，且只从公开任务提取；不消费官方参考/测试/执行状态。
    suite = suite_builder(copy.deepcopy(contract), {}, requester)
    suite = copy.deepcopy(suite)
    suite_fingerprint = hashlib.sha256(json.dumps(suite, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    row = {'schema_version': 1, 'arm': VARIANT, 'task_id': contract['task_id'],
           'subset': subset, 'public_contract': contract, 'requirements': requirements,
           'internal_suite': suite, 'attempts': [], 'feedback_source': 'public_only',
           'official_evaluation_order': 'after_candidate_selection', 'memory_updates': 0}
    reference, feedback = '', None
    entry_point = contract.get('entry_point') or contract.get('function_name', '')
    for index in range(2):
        try:
            generated = pipeline(copy.deepcopy(contract), [], requester=requester,
                reference_code=reference, previous_evidence=copy.deepcopy(feedback),
                cards_provider=provider, reanalyze=True)
        except Exception as exc:
            generated = {'code': '', 'workflow_completed': False, 'error_type': type(exc).__name__}
        code = str(generated.get('code') or '').strip()
        static = check_public_contract(code, requirements)
        execution_error = None
        try:
            internal = check_executor(code, entry_point, copy.deepcopy(suite), backend=backend, timeout=10)
        except Exception as exc:
            execution_error = {'error_type': type(exc).__name__}
            internal = {'source': 'self_generated_internal', 'backend': backend,
                        'measured': False, 'cases': [], 'error_type': type(exc).__name__}
        internal = bind_public_result(code, suite, internal)
        row['attempts'].append({'attempt': index, 'code': code, 'generation': generated,
                                'public_checks': static, 'internal_checks': internal,
                                'public_execution_error': execution_error})
        if index == 0:
            opportunity = repair_opportunity(code, suite, internal, static)
            row['repair_opportunity'] = opportunity
            if not opportunity['should_generate_repair']:
                row['repair_skipped_reason'] = opportunity['reason']
                break
        reference = code
        feedback = public_repair_feedback(suite, internal, static)
    if hashlib.sha256(json.dumps(suite, sort_keys=True, ensure_ascii=False).encode()).hexdigest() != suite_fingerprint:
        raise RuntimeError('fixed_public_suite_mutated')
    first = row['attempts'][0]
    if len(row['attempts']) == 2:
        second = row['attempts'][1]
        selection = choose_public_candidate(original_code=first['code'], repaired_code=second['code'],
            suite=suite, original_internal=first['internal_checks'], repaired_internal=second['internal_checks'],
            original_contract=first['public_checks'], repaired_contract=second['public_checks'])
    else:
        selection = {'source': 'public_checks_only', 'selected_attempt': 0,
                     'reason': row['repair_skipped_reason'], 'formal_metrics': 'unmeasured'}
    row['selection'] = selection
    row['selected_attempt'] = selection['selected_attempt']
    selected = row['attempts'][row['selected_attempt']]
    # 此位置之前不得调用正式验证器，所选代码哈希在计分前固定。
    row['selected_code_sha256'] = hashlib.sha256(selected['code'].encode()).hexdigest()
    if not selected['code']:
        row['final'] = {'measured': False, 'joint': False, 'functional': False,
                        'security': False, 'error_type': 'empty_delivered_code'}
    else:
        try:
            row['final'] = evaluator(subset, task, selected['code'])
        except Exception as exc:
            row['final'] = {'measured': False, 'joint': False, 'functional': False,
                            'security': False, 'error_type': type(exc).__name__}
    return row


def summarize(rows):
    """统计明确的交付 final，不能用 attempts[-1] 或任一成功冒充最终成绩。"""
    finals = [row.get('final', {}) for row in rows]
    return {'rows': len(rows), 'measured': sum(bool(x.get('measured')) for x in finals),
            'unmeasured': sum(not x.get('measured') for x in finals),
            **{key: sum(bool(x.get('measured')) and bool(x.get(key)) for x in finals)
               for key in ('functional', 'security', 'joint')},
            'selected_c1': sum(row.get('selected_attempt') == 1 for row in rows),
            'memory_updates': 0,
            'interpretation': 'Internal checks are diagnostics; only final holds official scores.'}

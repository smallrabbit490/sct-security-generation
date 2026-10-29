"""分析驱动的生成流水线：初析、检索、经验适配复析、规划、代码生成。

用于训练侧及冻结评测。仅消费调用方提供的任务契约、经验和许可反馈，不读数据集、
隐藏测试或答案，不更新长期经验。模型分析不算动态验证；解析失败明确留痕。
"""
from __future__ import annotations

import json
from .agent_pipeline import _content, _extract_json, strip_code_fence, compute_patch_diff
from .english_policy import assert_english_text


CONTRACT_POLICY = (
    "Use English for all reasoning, plans, comments and experience content. "
    "Implement the complete functional and security contract, preserving the specified interface, "
    "valid inputs, return values and explicit exception semantics. Do not obtain security by constant "
    "returns, disabling functionality, or inventing restrictions on valid inputs. Do not omit necessary "
    "security boundaries merely because an attack is not named verbatim. Rejection must follow task "
    "semantics or a concrete threat. Experiences are conditional, revocable suggestions subordinate "
    "to the current contract; passing their source task does not establish general validity. "
)

# 所有实验臂共用的输出格式约束；保持严格解析，不修补模型输出或吞掉格式错误。
JSON_FORMAT_POLICY = (
    'JSON strings must escape every literal backslash as two backslashes, including regexes and paths. '
    'Do not write raw regex escapes such as backslash-d inside JSON strings. '
    'Valid example: ' + json.dumps({'regex': r'\d+\s', 'path': r'C:\temp'}) + '\n'
)


def safe_feedback(evidence, internal=None):
    """修复阶段只回流测量状态；不传隐藏测试输入、期望值或异常原文，不更新库。"""
    output = {}
    for key in ('syntax', 'functional', 'security'):
        value = evidence.get(key)
        if isinstance(value, dict):
            output[key] = {field: value[field] for field in ('status', 'measured', 'error_type') if field in value}
    if internal:
        output['internal_checks'] = {key: internal[key] for key in ('measured', 'passed', 'measured_count') if key in internal}
        output['internal_checks']['cases'] = [
            {key: item[key] for key in ('id', 'status', 'measured', 'phase') if key in item}
            for item in internal.get('cases', []) if isinstance(item, dict)]
    return output


def experience_text(cards: list[dict]) -> str:
    """注入阶段完整保留种类/适用条件/修法；缺失证据显式标记，不升级经验。"""
    fields = ('invariant_id', 'kind', 'status', 'applicability', 'exclusion_conditions',
              'high_level_invariant', 'positive_principle', 'principle', 'recommended_action', 'negative_guardrail',
              'root_cause', 'fix_directive', 'prev_fix_assessment', 'language_leaf',
              'support_count', 'regression_count')
    # 仅冻结库视图实验显式放入该运行期payload；默认卡片继续原白名单序列化。
    # 下游三处都使用本函数，避免BF/BS在规划或生成阶段重新注入被排除的原正文。
    return json.dumps([c['_cle_memory_view'] if '_cle_memory_view' in c else
                       {key: c.get(key, 'not provided') for key in fields}
                       for c in cards], ensure_ascii=False)


def analysis_prompt(task, reference='', evidence=None, *, initial=None, cards=None):
    """初析只用契约与许可证据；复析加入具体经验，检查 source/sink/API 的适用性。"""
    stage = 'experience-conditioned reanalysis' if initial is not None else 'initial task threat analysis'
    prompt = (f'Perform {stage}. {CONTRACT_POLICY}\n' + JSON_FORMAT_POLICY +
              'Return strict JSON with list fields vulnerability_hypothesis, functional_invariants, '
              'sources, sinks, sensitive_operations, api_assumptions, data_flows, '
              'attack_surface, safe_actions, uncertainty. Ground analysis in the actual task type and interface; '
              'distinguish observed facts from unverified hypotheses. Use double-quoted keys/strings, no comments '
              'or trailing commas. Schema example: '
              '{"vulnerability_hypothesis":["risk and its basis"],"functional_invariants":["valid behavior"],'
              '"sources":[],"sinks":[],"sensitive_operations":[],"api_assumptions":[],"data_flows":[], '
              '"attack_surface":[],"safe_actions":[],"uncertainty":[]}\n'
              'Complete task contract: ' + json.dumps(task, ensure_ascii=False) +
              '\nCurrent implementation: ' + (reference or 'None: generate a complete implementation from the contract.') +
              '\nPermitted execution feedback: ' + json.dumps(evidence or {}, ensure_ascii=False))
    if initial is not None:
        prompt += ('\nInitial analysis: ' + json.dumps(initial, ensure_ascii=False) +
                   '\nRetrieved experiences: ' + experience_text(cards or []) +
                   '\nReconsider the actual task with each experience: check applicability, exclusions, API '
                   'semantics, input paths and current failures; correct initial omissions. Reject conflicting '
                   'advice or explicitly adapt it. Also return applied_experience_ids (an explicit list, possibly '
                   'empty), rejected_experiences ([{id,reason}]), adaptations (specific implementation adjustments). '
                   'Use only supplied IDs. These are plans, not verified outcomes. Do not repeat the body of '
                   'rejected advice in safe_actions or adaptations; keep rejection reasons brief.')
    return prompt


def adopt_experiences(cards, analysis):
    """复析后执行注入白名单；输入原卡/复析，输出采用卡和审计，不改长期库。

    明确拒绝优先于采用；缺失或无效 ID 清单时关闭注入并标错。保留原卡供轨迹审计，
    模型适用性判断不是动态验证，不能晋升经验。
    """
    applied = analysis.get('applied_experience_ids')
    rejected = analysis.get('rejected_experiences', [])
    error = None
    if not isinstance(applied, list) or any(not isinstance(i, str) for i in applied):
        applied, error = [], 'missing_applied_experience_ids'
    if (not isinstance(rejected, list) or any(not isinstance(r, dict)
            or not isinstance(r.get('id'), str) or not isinstance(r.get('reason'), str) for r in rejected)):
        rejected, applied, error = [], [], 'invalid_rejected_experiences'
    rejected_ids = {r['id'] for r in rejected if isinstance(r, dict) and isinstance(r.get('id'), str)}
    known = {c.get('invariant_id') for c in cards}
    unknown = set(applied) - known
    if unknown:
        error = 'unknown_applied_experience_ids'
        applied = []
    allowed = set(applied) & known - rejected_ids
    selected = [c for c in cards if c.get('invariant_id') in allowed]
    return selected, {'applied_ids': [c['invariant_id'] for c in selected],
                      'rejected_ids': sorted(rejected_ids), 'unknown_ids': sorted(unknown), 'error': error}


def run_context_pipeline(task, cards, *, requester, reference_code='', previous_evidence=None,
                         cards_provider=None, reanalyze=True, initial_analysis=None):
    """前向阶段消费契约和只读检索回调，输出代码与完整阶段证据；不执行或写经验。

    初析/复析/计划解析失败保留 degraded；代码截断或API失败返回分类错误，不当通过。
    cards_provider 收到完整 task + threat_analysis + current_code + failure_evidence。
    """
    stages, errors, prompts = [], [], {}

    def structured(stage, prompt, fallback):
        prompts[stage] = prompt
        response, content = {}, ''
        try:
            response = requester(prompt)
            content = _content(response)
            value = _extract_json(content)
            if not isinstance(value, dict) or not value:
                raise ValueError('empty_object')
            assert_english_text(json.dumps(value, ensure_ascii=False), context=stage)
            if stage in ('initial_analysis', 'experience_analysis'):
                if not all(isinstance(value.get(k), list) and value[k]
                           for k in ('vulnerability_hypothesis', 'functional_invariants')):
                    raise ValueError('analysis_incomplete')
            elif stage == 'planning':
                if not value.get('Preserved_Func') or not value.get('Patch_Scope'):
                    raise ValueError('planning_incomplete')
            stages.append({'stage': stage, 'status': 'completed'})
            return value
        except Exception as exc:
            errors.append(f'{stage}:{type(exc).__name__}')
            stages.append({'stage': stage, 'status': 'degraded', 'error': type(exc).__name__,
                           'parse_reason': exc.msg if isinstance(exc, json.JSONDecodeError) else '',
                           'parse_position': exc.pos if isinstance(exc, json.JSONDecodeError) else None,
                           'content_length': len(content),
                           'finish_reason': (response.get('choices') or [{}])[0].get('finish_reason'),
                           'request_diagnostics': getattr(exc, 'diagnostics', [])})
            return fallback

    initial = initial_analysis if initial_analysis is not None else structured(
        'initial_analysis', analysis_prompt(task, reference_code, previous_evidence), {'unmeasured': True})
    if initial_analysis is not None:
        invalid = not all(isinstance(initial_analysis.get(k), list) and initial_analysis[k]
                          for k in ('vulnerability_hypothesis', 'functional_invariants'))
        stages.append({'stage': 'initial_analysis', 'status': 'degraded' if invalid else 'reused'})
        if invalid:
            errors.append('initial_analysis:invalid_reused_analysis')
            initial = {'unmeasured': True}
        try:
            assert_english_text(json.dumps(initial, ensure_ascii=False), context='initial_analysis')
        except ValueError:
            initial = {'unmeasured': True}
            errors.append('initial_analysis:non_english_reused_analysis')
    selected = list(cards)
    if cards_provider is not None:
        query = {**task, 'threat_analysis': initial, 'current_code': reference_code,
                 'failure_evidence': previous_evidence or {}}
        try:
            selected = cards_provider(query) or []
            stages.append({'stage': 'retrieval', 'status': 'completed',
                           'ids': [c.get('invariant_id') for c in selected]})
        except Exception as exc:
            selected = []
            errors.append(f'retrieval:{type(exc).__name__}')
            stages.append({'stage': 'retrieval', 'status': 'degraded', 'error': type(exc).__name__,
                           'retrieval_trace': getattr(exc, 'retrieval_trace', None)})
    analysis = structured('experience_analysis', analysis_prompt(
        task, reference_code, previous_evidence, initial=initial, cards=selected), initial) if reanalyze else initial
    # 原始召回与实际注入分开；被拒绝的正文不再出现在下游经验块。
    retrieved = list(selected)
    selected, adoption = adopt_experiences(retrieved, analysis) if reanalyze else (selected, {
        'applied_ids': [c.get('invariant_id') for c in selected], 'rejected_ids': [], 'error': None})
    if adoption['error'] and retrieved:
        errors.append('adoption:' + adoption['error'])
    stages.append({'stage': 'adoption', 'status': 'degraded' if adoption['error'] and retrieved else 'completed', **adoption})
    experience_analysis = analysis
    # 部分经验被拒绝时，整份复析可能已被拒绝正文污染，不能靠删字段猜测来源。
    # 下游从未看经验的初析重新开始；规划只看到采用卡并重新完成经验结合分析。
    # 原复析完整留审计，既不传递拒绝理由，也不把推断当验证证据。
    if reanalyze and len(selected) != len(retrieved):
        analysis = initial
    plan_prompt = ('Plan the implementation. ' + CONTRACT_POLICY + '\n' + JSON_FORMAT_POLICY +
                   'Reanalyze the task using only the adopted experiences below and the clean task analysis. '
                   'Check task type, API semantics, applicability and exclusions before specifying implementation actions. '
                   'For existing code locate actual defects and make necessary changes; otherwise plan a complete implementation. '
                   'Return JSON: Preserved_Func, Patch_Scope, Avoidance_List (list), '
                   'Security_Actions (specific APIs/check order), Verification_Plan (normal and attack behavior). '
                   'Strict JSON example: {"Preserved_Func":"normal behavior", "Patch_Scope":"implementation steps", '
                   '"Avoidance_List":[], "Security_Actions":[], "Verification_Plan":[]}. '
                   'Use double-quoted keys/strings, no comments, trailing commas or external prose.\n'
                   'Task: ' + json.dumps(task, ensure_ascii=False) + '\nAnalysis: ' + json.dumps(analysis, ensure_ascii=False) +
                   '\nAdopted experiences: ' + experience_text(selected) + '\nCurrent code: ' + reference_code +
                   '\nExecution feedback: ' + json.dumps(previous_evidence or {}, ensure_ascii=False))
    plan = structured('planning', plan_prompt, {'degraded': True, 'Patch_Scope': 'Implement the complete task contract and analysis'})
    generation_prompt = ('Generate complete runnable Python code; output code only. ' + CONTRACT_POLICY +
                         'Preserve necessary imports, functions/classes and required dependencies. Do not arbitrarily '
                         'remove decorators or framework context. Implement only applicable adopted experiences; '
                         'do not output tests, placeholders or explanations.\nTask: ' +
                         json.dumps(task, ensure_ascii=False) + '\nAnalysis: ' + json.dumps(analysis, ensure_ascii=False) +
                         '\nPlan: ' + json.dumps(plan, ensure_ascii=False) + '\nAdopted experiences: ' + experience_text(selected) +
                         '\nPrevious code: ' + reference_code + '\nExecution feedback: ' + json.dumps(previous_evidence or {}, ensure_ascii=False))
    prompts['generation'] = generation_prompt
    code = ''
    try:
        code = strip_code_fence(_content(requester(generation_prompt)))
        if not code:
            raise ValueError('empty_code')
        stages.append({'stage': 'generation', 'status': 'completed'})
    except Exception as exc:
        errors.append(f'generation:{type(exc).__name__}:{str(exc)[:80] if isinstance(exc, ValueError) else "request_failed"}')
        stages.append({'stage': 'generation', 'status': 'failed'})
    return {'code': code, 'analysis': json.dumps(analysis, ensure_ascii=False), 'analysis_parsed': analysis,
            'initial_analysis': initial, 'plan': json.dumps(plan, ensure_ascii=False), 'plan_parsed': plan,
            'experience_analysis': experience_analysis,
            'cards': selected, 'retrieved_cards': retrieved, 'adoption': adoption, 'stages': stages, 'prompts': prompts,
            'patch_diff': compute_patch_diff(reference_code, code) if reference_code else '',
            'error_type': ';'.join(errors) or None, 'workflow_completed': bool(code) and not errors}

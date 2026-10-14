"""Phase2 多思路探索：共享任务与检索快照，独立生成全部分支，再验证和对比提炼。

输入仅 D_grow 的公开契约和许可训练证据；输出分支轨迹与 provisional 候选。
不读 Base/Plus，不写长期库；API/解析/验证缺测分别留痕，不把模型推测当验证。
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor

from .agent_pipeline import _content, _extract_json, strip_code_fence
from .context_pipeline import CONTRACT_POLICY, analysis_prompt, experience_text
from .schemas import RolloutTrace
from .english_policy import assert_english_text, assert_english_experience
from .global_gate import evidence_is_measured, _snapshot


def _check_public_task(task):
    """生成边界拒绝误传原始训练答案/测试；只接受公开契约，不读取验证或写库。"""
    private = {'unittest', 'unit_test', 'tests', 'test_cases', 'solution', 'code',
               'ground_truth', 'patched_code', 'vulnerable_code', 'task_description'}
    if private.intersection(task):
        raise ValueError('private_task_fields: pass public contract only')


def digest(value):
    """产物阶段对卡片或代码计算稳定版本哈希；不访问验证数据或修改库。"""
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def code_digest(code):
    """探索阶段按 AST 标记仅格式不同的重复实现；语法失败回退原文哈希。"""
    try:
        return digest(ast.dump(ast.parse(code), include_attributes=False))
    except SyntaxError:
        return digest(code)


def prepare_context(task, requester, retrieve):
    """前向共享阶段：完整初析、最新检索、经验复析；不生成代码、不测量、不写库。"""
    _check_public_task(task)
    errors = []
    def analyze(prompt):
        try:
            result = _extract_json(_content(requester(prompt)))
            assert_english_text(json.dumps(result, ensure_ascii=False), context='branch_analysis')
            if not all(isinstance(result.get(k), list) and result[k] for k in ('vulnerability_hypothesis', 'functional_invariants')):
                raise ValueError('analysis_incomplete')
            return result
        except Exception as exc:
            errors.append(type(exc).__name__)
            return {'unmeasured': True}
    initial = analyze(analysis_prompt(task))
    try:
        cards = copy.deepcopy(retrieve({**task, 'threat_analysis': initial, 'current_code': '', 'failure_evidence': {}}) or [])
    except Exception as exc:
        cards = []
        errors.append('retrieval:' + type(exc).__name__)
    analysis = analyze(analysis_prompt(task, initial=initial, cards=cards))
    return {'initial_analysis': initial, 'analysis': analysis, 'cards': cards, 'errors': errors}


def run_branches(task, *, requester, retrieve, validate, count=3, mode='diverse', workers=3, prepared=None):
    """Phase2 一次多方案探索；输入契约/只读检索/验证回调，输出全部分支而非修复序列。

共享上下文后独立生成，全部生成完才测，防止兄弟分支测试反馈泄漏。
训练 oracle 选择第一条 Joint 成功，否则首条；不解释为部署 pass@1。
API和结构错误保留，缺测不能选为成功；本函数不能晋升或修改经验。
"""
    if count < 1 or mode not in ('diverse', 'resample'):
        raise ValueError('invalid_branch_configuration')
    _check_public_task(task)
    shared = copy.deepcopy(prepared) if prepared is not None else prepare_context(task, requester, retrieve)
    cards = shared['cards']
    card_snapshots = _snapshot(cards)
    plan_count = count if mode == 'diverse' else 1
    plan_prompt = ('BRANCH_PLAN\nYou are the implementation planner. ' + CONTRACT_POLICY +
        f'Return strict JSON with plans containing exactly {plan_count} plans. Each plan contains strategy, '
        'Preserved_Func, Patch_Scope, Security_Actions, applied_experience_ids, rejected_experiences and distinct_from_others. '
        'Use English for all natural-language values. Plans must differ concretely in algorithms, APIs, data representation '
        'or security boundaries, not just wording or variable names. All must implement the same contract; do not invent '
        'deliberately insecure alternatives. If too few reasonable approaches exist, explain that limitation in the plans.\nTask: ' +
        json.dumps(task, ensure_ascii=False) + '\nAnalysis: ' + json.dumps(shared['analysis'], ensure_ascii=False) +
        '\nExperience: ' + experience_text(cards))
    plan_error = None
    diversity_errors = []
    try:
        plans = _extract_json(_content(requester(plan_prompt)))['plans']
        if not isinstance(plans, list) or len(plans) < plan_count or any(
                not isinstance(p, dict) or not p.get('Patch_Scope') or not p.get('Preserved_Func') for p in plans[:plan_count]):
            raise ValueError('invalid_branch_plans')
        plans = plans[:plan_count]
        assert_english_text(json.dumps(plans, ensure_ascii=False), context='branch_plans')
        required = ('strategy', 'Preserved_Func', 'Patch_Scope', 'Security_Actions', 'distinct_from_others')
        if any(not all(p.get(key) for key in required) for p in plans):
            diversity_errors.append('incomplete_plans')
        normalized = [digest({k: p.get(k) for k in ('strategy', 'Patch_Scope', 'Security_Actions')}) for p in plans]
        if mode == 'diverse' and len(set(normalized)) != len(plans):
            diversity_errors.append('duplicate_plans')
    except Exception as exc:
        plan_error = type(exc).__name__
        diversity_errors.append('plan_parse_error')
        plans = [{'degraded': True, 'Patch_Scope': 'Implement the complete contract', 'Preserved_Func': 'Complete task contract'}] * plan_count
    if mode == 'resample':
        plans = [copy.deepcopy(plans[0]) for _ in range(count)]

    def generate(item):
        i, plan = item
        prompt = ('BRANCH_CODE\nGenerate complete runnable Python code; output code only. ' + CONTRACT_POLICY +
                  '\nTask: ' + json.dumps(task, ensure_ascii=False) + '\nAnalysis: ' +
                  json.dumps(shared['analysis'], ensure_ascii=False) + '\nPlan for this branch: ' +
                  json.dumps(plan, ensure_ascii=False) + '\nConditional experience: ' + experience_text(cards))
        record = {'branch_id': f'b{i+1}', 'plan': copy.deepcopy(plan), 'cards': copy.deepcopy(cards),
                  'card_hashes': {c['id']: c['sha256'] for c in card_snapshots},
                  'retrieval_snapshot': copy.deepcopy(card_snapshots),
                  'code': '', 'evidence': {}, 'state': 'U', 'measured': False, 'error_type': None,
                  'functional': False, 'security': False, 'joint': False, 'duplicate_of': None}
        try:
            record['code'] = strip_code_fence(_content(requester(prompt)))
            if not record['code']:
                raise ValueError('empty_code')
        except Exception as exc:
            record['error_type'] = type(exc).__name__
        return record

    with ThreadPoolExecutor(max_workers=max(1, min(workers, count))) as executor:
        branches = list(executor.map(generate, enumerate(plans)))
    # 必须先收齐代码再执行许可训练测试；不得将测试结果回灌同批兄弟方案。
    seen = {}
    for branch in branches:
        if not branch['code']:
            continue
        fingerprint = code_digest(branch['code'])
        branch['code_sha256'] = fingerprint
        branch['duplicate_of'] = seen.get(fingerprint)
        seen.setdefault(fingerprint, branch['branch_id'])
        try:
            evidence = validate(branch['code'])
            branch['evidence'] = evidence
            statuses = [evidence.get(k, {}).get('status') for k in ('functional', 'security')]
            branch['measured'] = evidence_is_measured(evidence)
            branch['functional'], branch['security'] = [s == 'pass' for s in statuses]
            branch['joint'] = branch['measured'] and all(s == 'pass' for s in statuses)
            branch['state'] = { (True, True): 'A', (True, False): 'B', (False, True): 'C', (False, False): 'D'}[tuple(s == 'pass' for s in statuses)]
            if not branch['measured']:
                branch['state'] = 'U'
        except Exception as exc:
            branch['error_type'] = 'validation:' + type(exc).__name__
    selected = next((i for i, b in enumerate(branches) if b['joint']), 0)
    return {'branches': branches, 'selected_index': selected, 'mode': mode,
            'selection_policy': 'training_oracle_first_joint_else_first', 'shared_context': shared,
            'plan_error': plan_error, 'unique_code_count': len(seen),
            'diversity_valid': not diversity_errors if mode == 'diverse' else None,
            'diversity_errors': diversity_errors}


def branch_trace(row, result, *, round_index=1):
    """训练编排适配：兼容字段仅存选中分支，完整兄弟证据在 branches，不伪造时间转移。"""
    branch = result['branches'][result['selected_index']]
    return RolloutTrace(task_id=str(row['index']), cwe=str(row.get('CWE_ID', '')), round=round_index,
        family_id=str(row.get('family_id', '')), states=[branch['state']], transitions=[],
        generated_codes=[branch['code']], evidence=[branch['evidence']],
        retrieved_per_round=[branch['cards']], agent_context=[result['shared_context']],
        task_contract=json.dumps(row.get('task_description') or {}, ensure_ascii=False),
        branches=result['branches'], branch_selection={'index': result['selected_index'],
        'policy': result['selection_policy'], 'mode': result['mode'], 'plan_error': result['plan_error'],
        'diversity_valid': result.get('diversity_valid'), 'diversity_errors': result.get('diversity_errors', [])})


def distill_branches(trace, requester):
    """Phase2 对比提炼所有并行方案；输入真实证据，输出候选经验，不写长期库。

要求引用分支ID；正经验必须关联实际 Joint 成功，失败解释保留为假设。
API/解析失败明确返回 error；不能因 C 状态推断过度防御，不包含隐藏答案常量。
"""
    output = {'positive': [], 'negative': [], 'error_ledger': []}
    prompt = ('Distill training experience from parallel independent plans for the same task. These are siblings, '
        'not sequential repairs; do not claim one branch repaired another. Explain differences using plans, actual '
        'code and functional/security evidence. State C alone does not prove overdefense. Unmeasured outcomes are '
        'not model errors. Label unsupported causes as hypotheses. Do not repeat test inputs, answer constants or '
        'source task identifiers. Write natural-language values in English. Return strict JSON with positive, negative '
        'and error_ledger lists, at most two concrete reusable lessons in each. Each item must contain '
        'evidence_branch_ids, high_level_invariant, positive_principle, negative_guardrail, applicability, root_cause, '
        'fix_directive and blind_spot.\nTask: ' + trace.task_contract + '\nAll branch evidence: ' +
        json.dumps(trace.branches, ensure_ascii=False))
    try:
        value = _extract_json(_content(requester(prompt)))
        assert_english_experience(value)
        by_id = {b['branch_id']: b for b in trace.branches}
        for target in output:
            items = value.get(target, [])
            if not isinstance(items, list):
                raise ValueError('invalid_distillation_list')
            for item in items[:2]:
                if not isinstance(item, dict):
                    continue
                ids = item.get('evidence_branch_ids') or []
                if not isinstance(ids, list) or not ids or any(i not in by_id for i in ids):
                    continue
                evidence = [by_id[i] for i in ids]
                if target == 'positive' and not any(b['joint'] and b['measured'] for b in evidence):
                    continue
                if target != 'positive' and not any(b['measured'] and not b['joint'] for b in evidence):
                    continue
                output[target].append({**item, 'kind': 'branch_comparison_' + target, 'cwe': trace.cwe,
                                       'source_stage': 'phase2', 'causal_claim': False})
    except Exception as exc:
        output['error'] = type(exc).__name__
    return output

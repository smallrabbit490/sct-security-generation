"""审计标签与原文举证校验；不修改经验库，不用历史测试分数判题。"""
import hashlib
import json


def request_identity(payload, model, protocol, sample):
    """只有题面、协议、模型、重复编号均一致才可复用已保存响应。"""
    raw = json.dumps([payload, model, protocol, sample], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_result(obj, payload):
    """核对枚举和引用真实性；这不是人工语义复核，也不确认绕过可执行。"""
    errors = []
    if obj.get('verdict') not in ('合格', '有缺陷', '无法判定'):
        errors.append('invalid_verdict')
    if obj.get('test_quality') not in ('充分', '安全组偏弱', 'Joint 可被绕过', '输出格式过严', '缺少正例', '无法判定'):
        errors.append('invalid_test_quality')
    if obj.get('test_integrity') not in ('完整', '不完整或语法错误', '未提供', '无法判定'):
        errors.append('invalid_test_integrity')
    sources = {(s['path'],s['role']): s for s in payload['sources']}
    has_tests = any(s['role'] == 'test' for s in sources.values())
    oracle = payload.get('oracle', '')
    if not has_tests or obj.get('test_integrity') in ('未提供', '不完整或语法错误', '无法判定'):
        if obj.get('test_quality') != '无法判定':
            errors.append('test_quality_not_measured')
    if obj.get('verdict') != '有缺陷':
        if obj.get('defect_type') is not None:
            errors.append('non_defect_has_type')
    else:
        if obj.get('test_integrity') == '不完整或语法错误':
            errors.append('broken_tests_cannot_establish_defect')
        if obj.get('defect_type') not in ('接口契约', '业务规则或数据', '题面与测试冲突', '环境依赖'):
            errors.append('invalid_defect_type')
        evidence = obj.get('evidence')
        if not isinstance(evidence, list) or not evidence:
            errors.append('missing_defect_evidence')
        else:
            for e in evidence:
                for role, prefix in [('test', 'test'), ('public', 'public')]:
                    source = sources.get((e.get(prefix + '_path'),role))
                    quote = e.get(prefix + '_quote')
                    if not source or source['role'] != role or not isinstance(quote, str) or not quote.strip() or quote not in source['text']:
                        errors.append('unverified_' + prefix + '_quote')
                if not e.get('missing_requirement') or not e.get('why_not_inferable'):
                    errors.append('missing_uninferable_gap')
    if obj.get('test_quality') == 'Joint 可被绕过' and oracle != 'dynamic_function_security':
        errors.append('joint_requires_dynamic_function_and_security_oracles')
    if not obj.get('reason'):
        errors.append('missing_reason')
    return errors

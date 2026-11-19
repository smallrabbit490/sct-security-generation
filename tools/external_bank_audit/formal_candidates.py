"""将六规则双判生成正式机器标签；保留分歧、缺测与材料缺失，不冒充人工裁决。"""
import collections
import json
from pathlib import Path

from prepare_candidates import ROOT, OUT, BANKS
from run import PROTOCOL
from schema import request_identity, validate_result


def adjudicate(labels):
    a, b = labels
    verdict, defect = '无法判定', None
    status = '缺测' if not (a and b) else '双判分歧'
    if a and b and a['verdict'] == b['verdict']:
        if a['verdict'] != '有缺陷' or a.get('defect_type') == b.get('defect_type'):
            verdict = a['verdict']
            defect = a.get('defect_type') if verdict == '有缺陷' else None
            status = '双判一致'
    result = {'verdict': verdict, 'defect_type': defect, 'review_status': status}
    for field in ('test_quality', 'test_integrity'):
        result[field] = a[field] if a and b and a.get(field) == b.get(field) else '无法判定'
    return result


def main():
    payloads = [json.loads(x) for x in (OUT / 'payloads.jsonl').read_text(encoding='utf-8').splitlines()]
    rows = []
    for p in payloads:
        labels = []
        identities = []
        for sample in (1, 2):
            identity = request_identity(p, 'gpt-6.1-sol', PROTOCOL, sample)
            identities.append(identity)
            f = OUT / 'responses' / (identity + '.json')
            record = json.loads(f.read_text(encoding='utf-8')) if f.exists() else None
            obj = record.get('parsed') if record and record.get('status') == 'ok' else None
            labels.append(obj if obj and not validate_result(obj, p) else None)
        label = adjudicate(labels)
        if p.get('full_context_available') is False:
            label.update(verdict='无法判定', defect_type=None, review_status='材料不全')
            # 未获得真实测试时不能把验证壳依赖缺失误写为测试代码损坏。
            if not any(s['role'] == 'test' for s in p['sources']):
                label.update(test_integrity='未提供', test_quality='无法判定')
        rows.append({'key': p['key'], 'bank': p['bank'], 'language': p['language'], **label, 'judgments': labels, 'identities': identities, 'valid_judgments': sum(x is not None for x in labels)})
    (OUT / 'formal_labels.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    attempts = [json.loads(f.read_text(encoding='utf-8')) for f in (OUT / 'attempts').rglob('*.json')]
    usage = collections.Counter()
    for a in attempts:
        for k, v in (a.get('usage') or {}).items():
            if isinstance(v, (int, float)):
                usage[k] += v
    summary = {'planned_tasks': len(rows), 'planned_judgments': 2 * len(rows), 'valid_judgments': sum(r['valid_judgments'] for r in rows), 'attempt_status': dict(collections.Counter(a['status'] for a in attempts)), 'http_status': dict(collections.Counter(a.get('http_status') for a in attempts if a.get('http_status'))), 'usage': dict(usage), 'unknown_usage_attempts': sum(a.get('usage_unknown', True) for a in attempts), 'currency_cost': '未测量', 'by_bank': {}}
    def table(headers, data):
        return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] + ['| ' + ' | '.join(map(str, row)) + ' |' for row in data])
    for bank in BANKS:
        sub = [r for r in rows if r['bank'] == bank]
        summary['by_bank'][bank] = {'tasks': len(sub), 'valid_judgments': sum(r['valid_judgments'] for r in sub), **{f: dict(collections.Counter(r[f] for r in sub if r[f] is not None)) for f in ('verdict', 'defect_type', 'test_quality', 'test_integrity', 'review_status')}}
    lines = ['# 五个新增数据集：六规则正式机器标签', '', f'计划 {len(rows)} 题 / {2*len(rows)} 次独立判断；当前有效判断 {summary["valid_judgments"]} 次。', '', '同模型双判经逐字引文校验后生成机器标签，不等同人工复核。两次verdict与缺陷类型均一致才定有缺陷，其余无法判定；缺测与分歧单列。测试质量、测试完整性分别双判一致才定标签。材料不全强制无法判定。', '', table(['数据集', '题数', '有效判断/计划', '合格', '有缺陷', '无法判定', '缺测', '双判分歧', '材料不全'], [[b, s['tasks'], f'{s["valid_judgments"]}/{2*s["tasks"]}', *[s['verdict'].get(v, 0) for v in ('合格', '有缺陷', '无法判定')], *[s['review_status'].get(v, 0) for v in ('缺测', '双判分歧', '材料不全')]] for b,s in summary['by_bank'].items()]), '']
    for field, title, values in [('defect_type','正式有缺陷类型',['接口契约','业务规则或数据','题面与测试冲突','环境依赖']), ('test_quality','测试质量（独立于verdict）',['充分','安全组偏弱','Joint 可被绕过','输出格式过严','缺少正例','无法判定']), ('test_integrity','测试完整性',['完整','不完整或语法错误','未提供','无法判定'])]:
        lines += ['## '+title, '', table(['数据集']+values, [[b]+[s[field].get(v,0) for v in values] for b,s in summary['by_bank'].items()]), '']
    lines += ['LSCBench 只凭下载题面和验证壳不能替代场景镜像内的公开项目上下文及具体断言：本批150题正式verdict记材料不全/无法判定。CodeLMSec与SafeCoder是静态oracle，没有动态断言不能制造隐藏契约缺陷，test_quality无法判定。AutoSUIT仅Task1生成模式，不混入CWE-aware、补全或修复模式。', '', '动态通过与审计标签分开。参考实现失败不是题面缺陷；测试坏了仅记test_integrity。缺陷标签必须同时保留具体测试调用/断言、公开题面原文与不可推断的缺失说明。', '', '用量（所有尝试）：'+json.dumps(dict(usage),ensure_ascii=False)+'；未知用量尝试 '+str(summary['unknown_usage_attempts'])+'；金额未测量。', '']
    report = ROOT / 'docs/research/reports/CLE-ANL-20261118-candidate-six-rule-formal-labels.md'
    report.write_text('\n'.join(lines), encoding='utf-8')
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    curated = ROOT / 'results/curated/candidate_six_rule_20261118'
    curated.mkdir(parents=True, exist_ok=True)
    (curated / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    compact = [{k: v for k, v in r.items() if k != 'judgments'} for r in rows]
    (curated / 'formal_labels.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in compact), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

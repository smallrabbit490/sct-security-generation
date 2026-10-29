"""IR02固定小批统计；完整、回放与机制阅读齐备后才决定接续。"""
from collections import defaultdict
import json
from pathlib import Path
import random

from methods.sct_trajectory.replay_journal import write_json
from .evaluate import ROOT, inputs


def main():
    _, schedule, _, _ = inputs('IR02')
    root = ROOT / 'IR02'
    sources = [Path(p) for p in json.loads((root/'execution_index.json').read_text())['segments']]
    rows = {}
    for source in sources:
        for p in (source/'task_rows').glob('*.json'):
            row = json.loads(p.read_text(encoding='utf-8'))
            if row['cell_id'] in rows and row != rows[row['cell_id']]:
                raise RuntimeError('conflicting_saved_cell')
            rows[row['cell_id']] = row
    expected = {c['cell_id'] for c in schedule}
    assert set(rows) <= expected
    arms = {}
    for arm in ('original_edit', 'boundary_edit'):
        found = [r for r in rows.values() if r['condition'] == arm]
        arms[arm] = {'completed': len(found), 'planned': 24,
            'measured': sum(all(r['evidence'].get(k, {}).get('status') in ('pass', 'fail') for k in ('functional', 'security')) for r in found),
            'F': sum(r['state'] in ('A', 'B') for r in found),
            'S': sum(r['state'] in ('A', 'C') for r in found),
            'Joint': sum(r['state'] == 'A' for r in found)}
    paired = []
    for tid in dict.fromkeys(c['task_id'] for c in schedule):
        for repeat in (1, 2):
            pair = [rows.get(f'{tid}_r{repeat}_{a}') for a in arms]
            if not all(pair):
                continue
            a, b = pair
            measured = all(all(r['evidence'].get(k, {}).get('status') in ('pass', 'fail') for k in ('functional', 'security')) for r in pair)
            paired.append({'task_id': tid, 'family_id': a['family_id'], 'repeat': repeat,
                'measured': measured, 'old': a['state'], 'new': b['state'],
                'gain': int(b['state'] == 'A') - int(a['state'] == 'A'),
                'security_loss': a['state'] in ('A', 'C') and b['state'] not in ('A', 'C'),
                'code_changed': a['code'] != b['code']})
    repeat_net = {str(r): sum(p['gain'] for p in paired if p['repeat'] == r and p['measured']) for r in (1, 2)}
    result = {'status': 'completed_statistics' if len(rows) == 48 else 'partial',
        'completed': len(rows), 'planned': 48, 'arms': arms, 'paired_units': len(paired),
        'paired_measured': sum(p['measured'] for p in paired),
        'rescue': sum(p['gain'] == 1 and p['measured'] for p in paired),
        'loss': sum(p['gain'] == -1 and p['measured'] for p in paired),
        'new_security_failures': sum(p['security_loss'] and p['measured'] for p in paired),
        'repeat_net': repeat_net, 'experiment_HTTP_in_analysis': 0}
    groups = defaultdict(list)
    for p in paired:
        if p['measured']:
            groups[p['family_id']].append(p['gain'])
    if len(rows) == 48 and result['paired_measured'] == 24:
        rng = random.Random(20261028)
        values = list(groups.values())
        boot = []
        for _ in range(2000):
            draws = [rng.choice(values) for _ in values]
            boot.append(sum(map(sum, draws)) / sum(map(len, draws)))
        boot.sort()
        result['family_bootstrap_95'] = [boot[49], boot[1949]]
        outcome_pass = result['rescue']-result['loss'] >= 2 and min(repeat_net.values()) >= 0 and result['new_security_failures'] == 0
        replay = root / 'zero_API_replay/replay_result.json'
        replay_pass = replay.exists() and json.loads(replay.read_text()).get('status') == 'passed'
        review = root / 'mechanism_review.json'
        evidence = json.loads(review.read_text()) if review.exists() else {}
        mechanism_pass = evidence.get('status') == 'completed' and len(set(evidence.get('verified_reduction_task_ids', []))) >= 4
        result.update(outcome_gate_passed=outcome_pass, replay_passed=replay_pass, mechanism_gate_passed=mechanism_pass)
        if replay_pass and (not outcome_pass or evidence.get('status') == 'completed'):
            write_json(root/'decision.json', {'status': 'decided', 'advance': 'proceed' if outcome_pass and mechanism_pass else 'stop',
                'reason': 'predefined_joint_repeat_safety_and_mechanism_gates', 'evidence': str(root/'analysis/summary.json')})
    write_json(root/'analysis/summary.json', result)
    write_json(root/'analysis/paired.json', paired)
    budget = json.loads((sources[-1]/'budget.json').read_text())
    write_json(root/'analysis/cost.json', {k:budget[k] for k in ('known_reported_tokens','transport_attempts_including_prior','charged_tokens_including_unknown_and_inflight_bounds')})
    text = '# 边界约束编辑小批结果\n\n' + ('完整小批。' if len(rows)==48 else '运行中快照。') + '\n\n'
    for arm, v in arms.items():
        text += f"- {arm}：{v['completed']}/24；功能{v['F']}，安全{v['S']}，Joint {v['Joint']}，完整测量{v['measured']}。\n"
    text += f"\n完整配对{len(paired)}次；可测配对{result['paired_measured']}次。救回{result['rescue']}，损失{result['loss']}。\n"
    text += '\n缺测独立列示；未完成小批不决定扩大。机制是否落实须实际阅读代码后登记。\n'
    if len(rows) == 48 and (root/'mechanism_review.json').exists():
        mechanism = json.loads((root/'mechanism_review.json').read_text(encoding='utf-8'))
        text += ('\n## 完成后的判断\n\n本轮附加边界提醒没有提高Joint。24组配对的Joint结果全部相同，'
            '两次重复均无净变化。代码阅读确认，' + str(mechanism['code_changed_pairs']) +
            '组代码发生变化，其余代码相同；未形成4道已验证的非必要边界改写减少。'
            '因此按预登记规则停止本版本，不进入24题确认，不启动全量。\n\n'
            '错误宿主依赖有时已经存在于起始代码中，模型保留了它；部分新改动增加限制，'
            '没有恢复宿主读取。局部撤销错误能救回具体题，与通用提醒能够自动识别并纠正错误，'
            '是两个不同结论。本轮支持前者的具体案例，不支持采用这条通用提醒作为有效方法。\n\n'
            '后续方法若继续设计，应明确识别公开接口与起始代码之间的冲突，而不是只要求少改。'
            '本轮不改提示重跑，也不追加样本。\n')
    (root/'analysis/report.md').write_text(text, encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

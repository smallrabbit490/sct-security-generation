"""从已保存逐题行复算学习结果；不请求模型、不验证新代码、不修改实验。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
STAGES = ('K0', 'K1', 'K2', 'K3')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def collect_rows(segments, ordered_ids):
    """恢复段可重复保存相同完成行；冲突行或非连续学习记录不能静默合并。"""
    by_id = {}
    paths = {}
    duplicate_copies = 0
    for segment in segments:
        for path in (Path(segment)/'task_rows').glob('*.json'):
            row = read(path)
            task_id = str(row['task_id'])
            if task_id in by_id:
                if row != by_id[task_id]:
                    raise ValueError('conflicting_completed_row:' + task_id)
                duplicate_copies += 1
            by_id[task_id] = row
            paths[task_id] = str(path)
    expected = set(ordered_ids)
    if set(by_id) - expected:
        raise ValueError('completed_task_outside_manifest')
    prefix = ordered_ids[:len(by_id)]
    if set(prefix) != set(by_id):
        raise ValueError('completed_rows_are_not_a_learning_prefix')
    return [by_id[key] for key in prefix], paths, duplicate_copies


def metrics(attempts, planned):
    counts = {'functional': 0, 'security': 0, 'joint': 0, 'measured': 0}
    for attempt in attempts:
        measured = bool(attempt.get('measured'))
        functional = bool(attempt.get('functional'))
        security = bool(attempt.get('security'))
        joint = measured and functional and security
        if bool(attempt.get('joint')) != joint:
            raise ValueError('stored_joint_differs_from_same_code_F_S')
        for key, flag in (('functional', functional), ('security', security),
                          ('joint', joint), ('measured', measured)):
            counts[key] += flag
    completed = len(attempts)
    return {**counts, 'completed': completed, 'planned': planned,
            'unmeasured_completed': completed-counts['measured'],
            'pending_tasks': planned-completed,
            'joint_rate_among_completed': counts['joint']/completed if completed else None,
            'joint_rate_among_measured': counts['joint']/counts['measured'] if counts['measured'] else None,
            'confirmed_joint_divided_by_planned': counts['joint']/planned if planned else None}


def summarize(rows, bank, planned):
    """按时间顺序读真实信用事件；Q为0且visits>0的卡仍属于已反馈覆盖。"""
    state = {card['invariant_id']: {'q_value': card.get('q_value', 0.),
                                  'q_visits': card.get('q_visits', 0)} for card in bank}
    initial_covered = sum(card['q_visits'] > 0 for card in state.values())
    per_card = defaultdict(lambda: {'events': 0, 'positive_rewards': 0, 'negative_rewards': 0,
                                   'family_ids': set(), 'task_ids': set()})
    per_family = defaultdict(lambda: {'tasks': 0, 'joint': 0, 'credit_events': 0, 'card_ids': set()})
    errors, skips = Counter(), Counter()
    selected_positions = adopted_positions = adopted_attempts = adopted_tasks = 0
    order_changes = member_changes = 0
    for row in rows:
        family = str(row['family_id'])
        per_family[family]['tasks'] += 1
        per_family[family]['joint'] += bool(row['final'].get('joint'))
        task_adopted = False
        if row.get('shared_initial_error'):
            errors['shared_initial:' + str(row['shared_initial_error'])] += 1
        for attempt in row['attempts']:
            generation = attempt.get('generation', {})
            selected = generation.get('retrieved_cards', [])
            adopted = generation.get('cards', [])
            selected_positions += len(selected)
            adopted_positions += len(adopted)
            adopted_attempts += bool(adopted)
            task_adopted = task_adopted or bool(adopted)
            error = attempt.get('error_type') or generation.get('error_type')
            if error:
                errors['attempt:' + str(error)] += 1
            for kind, evidence in attempt.get('validation', {}).get('evidence', {}).items():
                if isinstance(evidence, dict) and evidence.get('error_type'):
                    errors['validation_' + kind + ':' + str(evidence['error_type'])] += 1
        adopted_tasks += task_adopted
        for mechanism in row.get('mechanism', []):
            order_changes += bool(mechanism.get('Q_order_changed'))
            member_changes += bool(mechanism.get('numeric_top3_members_changed'))
        for event in row.get('q_credit_events', []):
            if not event['credited']:
                skips[event.get('skip_reason') or 'unspecified'] += 1
                continue
            key = event['invariant_id']
            if key not in state:
                raise ValueError('credited_card_outside_bank:' + key)
            if abs(state[key]['q_value']-event['q_before']) > 1e-10:
                raise ValueError('credit_event_order_or_Q_before_mismatch:' + key)
            if event['q_visits'] != state[key]['q_visits'] + 1:
                raise ValueError('credit_visits_sequence_mismatch:' + key)
            state[key] = {'q_value': event['q_after'], 'q_visits': event['q_visits']}
            card = per_card[key]
            card['events'] += 1
            card['positive_rewards'] += event['reward'] > 0
            card['negative_rewards'] += event['reward'] < 0
            card['family_ids'].add(family)
            card['task_ids'].add(str(row['task_id']))
            per_family[family]['credit_events'] += 1
            per_family[family]['card_ids'].add(key)
    for key, value in per_card.items():
        value.update(state[key])
        value['family_ids'] = sorted(value['family_ids'])
        value['task_ids'] = sorted(value['task_ids'])
    for value in per_family.values():
        value['card_ids'] = sorted(value['card_ids'])
    covered = sum(card['q_visits'] > 0 for card in state.values())
    summary = {'planned': planned, 'completed': len(rows),
        'first': metrics([r['attempts'][0] for r in rows], planned),
        'final': metrics([r['final'] for r in rows], planned),
        'memory': {'card_count': len(state), 'covered_before_stage': initial_covered,
            'covered_after_saved_prefix': covered, 'newly_covered_this_stage': covered-initial_covered,
            'coverage': covered/len(state) if state else None,
            'covered_with_Q_exactly_zero': sum(c['q_visits'] > 0 and c['q_value'] == 0 for c in state.values()),
            'credit_events_this_stage': sum(c['events'] for c in per_card.values()),
            'credited_cards_this_stage': len(per_card), 'credit_family_count': sum(v['credit_events'] > 0 for v in per_family.values())},
        'adoption': {'selected_positions': selected_positions, 'declared_adopted_positions': adopted_positions,
            'attempts_with_declared_adoption': adopted_attempts, 'tasks_with_declared_adoption': adopted_tasks,
            'code_implementation_status': 'requires_actual_code_review_not_inferred_from_ID_fields'},
        'mechanism': {'attempts_with_Q_order_changes': order_changes,
            'attempts_with_numeric_top3_member_changes': member_changes,
            'numeric_top3_is_not_LLM_selected_card_set': True},
        'credit_skip_events': dict(skips), 'observed_error_type_events': dict(errors),
        'effectiveness_conclusion': 'not_identified_from_learning_scores; requires frozen matched controls'}
    return summary, dict(per_card), dict(per_family)


def cost_snapshot(segments):
    """最近恢复段budget已累计历史物理请求，不能再把各段总数相加。"""
    available = [Path(p)/'budget.json' for p in segments if (Path(p)/'budget.json').exists()]
    if not available:
        return {'status': 'unavailable', 'currency_cost': None}
    source = available[-1]
    budget = read(source)
    entries = budget.get('entries', [])
    valid = lambda entry: (isinstance(entry.get('usage'), dict)
                           and type(entry['usage'].get('total_tokens')) is int
                           and entry['usage']['total_tokens'] >= 0)
    return {'source': str(source), 'status': 'saved_budget_snapshot',
        'known_reported_tokens': budget['known_reported_tokens'],
        'physical_HTTP_including_prior': budget['transport_attempts_including_prior'],
        'unknown_or_inflight_HTTP': sum(not valid(e) for e in entries),
        'physical_statuses': dict(Counter(e.get('status', 'unspecified') for e in entries)),
        'conservative_tokens_including_unknown_and_inflight_bounds': budget['charged_tokens_including_unknown_and_inflight_bounds'],
        'currency_cost': None, 'includes_saved_work_and_possibly_current_inflight_request': True}


def case_queue(rows, paths):
    """按已观测现象选代表记录，原因和代码落实均留待实际阅读。"""
    categories = defaultdict(list)
    for row in rows:
        adopted = any(a.get('generation', {}).get('cards') for a in row['attempts'])
        final = row['final']
        category = ('adopted_joint_pass' if final.get('joint') else 'adopted_joint_not_pass') if adopted else (
                    'no_adoption_joint_pass' if final.get('joint') else 'no_adoption_joint_not_pass')
        categories[category].append(row)
        if not row['attempts'][0].get('joint') and final.get('joint'):
            categories['repair_rescue'].append(row)
        if any(m.get('Q_order_changed') for m in row.get('mechanism', [])):
            categories['Q_changed_order'].append(row)
    return [{'category': category, 'task_id': str(row['task_id']), 'family_id': row['family_id'],
             'row_path': paths[str(row['task_id'])], 'review_status': 'pending_actual_code_review',
             'required_evidence': ['public_task', 'retrieved_and_adopted_cards', 'plan', 'code', 'validation'],
             'cause': None, 'card_suggestion_implemented_correctly': None}
            for category, candidates in categories.items() for row in candidates[:2]]


def run(stage, root=RUN):
    index = read(root/'execution_index.json')
    segments = [Path(p) for p in index['FQ_LEARN_'+stage]]
    pool = 'D_init' if stage == 'K0' else 'D_grow'
    ids = read(root/'manifest.json')['pools'][pool]
    rows, paths, duplicates = collect_rows(segments, ids)
    bank_path = root/'shared_inputs/memory1939_q0.jsonl' if stage == 'K0' else (
        root/'FQ_LEARN/frozen'/(STAGES[STAGES.index(stage)-1]+'.jsonl'))
    bank = [json.loads(line) for line in bank_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    summary, cards, families = summarize(rows, bank, len(ids))
    stage_completed = len(rows) == len(ids) and read(segments[-1]/'state.json')['status'] == 'completed'
    summary.update(stage=stage, pool=pool, status='completed' if stage_completed else 'partial',
        observed_utc=datetime.now(timezone.utc).isoformat(), source_segments=list(map(str, segments)),
        identical_duplicate_row_copies=duplicates, paid_calls_by_analysis=0,
        costs=cost_snapshot(segments), input_bank=str(bank_path))
    out = root/'analysis'/stage
    write(out/'summary.json', summary)
    write(out/'per_card_feedback.json', cards)
    write(out/'per_family_feedback.json', families)
    write(out/'case_review_queue.json', case_queue(rows, paths))
    f, m, c = summary['final'], summary['memory'], summary['costs']
    rate = f"{f['joint_rate_among_completed']:.1%}" if f['joint_rate_among_completed'] is not None else '尚无完成题'
    report = f'''# {stage}学习阶段分析（{'完整阶段' if stage_completed else '进行中快照'}）

本阶段已保存{summary['completed']}/{summary['planned']}题，末次交付Joint（同一份代码功能与安全都通过）为{f['joint']}/{summary['completed']}，完成题中比例为{rate}。完整可测{f['measured']}题，已完成但缺测{f['unmeasured_completed']}题，尚未执行{f['pending_tasks']}题。不能把进行中前缀作为全池成绩。

首次交付Joint为{summary['first']['joint']}，末次交付Joint为{f['joint']}。本阶段具有实际反馈的卡新增{m['newly_covered_this_stage']}张，累计覆盖{m['covered_after_saved_prefix']}/{m['card_count']}；本阶段有效Q反馈{m['credit_events_this_stage']}次，来自{m['credit_family_count']}个题族。覆盖按反馈次数大于零计算，累计Q恰好为零但有反馈的卡有{m['covered_with_Q_exactly_zero']}张。

模型声明采用卡位置{summary['adoption']['declared_adopted_positions']}个，涉及{summary['adoption']['tasks_with_declared_adoption']}题。声明采用不等于正确实现。代表题的题面、卡、计划、代码和验证需继续实际阅读，分析队列已保存，原因和落实判断均未代填。

最近累计预算保存的已知用量为{c.get('known_reported_tokens', '未记录')} Token，物理HTTP为{c.get('physical_HTTP_including_prior', '未记录')}次，未知或在途用量{c.get('unknown_or_inflight_HTTP', '未记录')}次。请求可能包含当前未完成题的在途调用，与已保存题行并非严格同时截止；未知用量不记为零，金额未核实。本分析新发付费请求0次。

本阶段回答反馈是否进入Q及覆盖如何变化，学习成绩本身不能识别Q的独立收益。下一步按固定名单继续完成学习，并在阶段完成后零API回放；冻结回测和匹配对照完成后，才判断Q是否提高完整解题正确率。低分不作为取消固定实验的依据。
'''
    (out/'analysis.md').write_text(report, encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['analysis'])
    parser.add_argument('--stage', required=True, choices=STAGES)
    parser.add_argument('--run-root', type=Path, default=RUN)
    args = parser.parse_args()
    summary = run(args.stage, args.run_root)
    print(json.dumps({key: summary[key] for key in ('stage', 'status', 'completed', 'planned', 'paid_calls_by_analysis')}))


if __name__ == '__main__':
    main()

"""C02固定排程、原P7结果读取和C1门；纯离线，不创建API客户端。"""
from __future__ import annotations

import random
from itertools import combinations

from methods.sct_trajectory.memory_granularity import LEVELS

VERSION = 'cle-memory-granularity-C1-v1'
REPEATS = (1, 2)
PHASE_LIMITS = {'technical': 20, 'pilot': 120, 'expansion': 480}


def make_schedule(manifest, seed=20261023):
    """前20格技术探针包含于先导120格，先导包含于训练/开发总480格。"""
    train = manifest['groups']['train']
    development = manifest['groups']['development']
    if len(train) != 36 or len(development) != 12:
        raise ValueError('expected_36_train_and_12_development_families')
    tasks = train + development
    index = {str(task['task_id']): task for task in tasks}
    if len(index) != 48 or len({t['family_id'] for t in tasks}) != 48:
        raise ValueError('task_or_family_overlap')
    pilot = manifest['first_pilot_ids']
    technical = manifest['technical_probe_ids']
    if len(pilot) != 12 or pilot != [str(t['task_id']) for t in train[:12]]:
        raise ValueError('pilot_must_be_first_12_train_families')
    if len(technical) != 2 or technical != pilot[:2]:
        raise ValueError('technical_probe_must_be_first_two_pilot_families')
    groups = [('technical', technical), ('pilot', pilot[2:]),
              ('expansion', [str(t['task_id']) for t in tasks if str(t['task_id']) not in pilot])]
    rng, schedule = random.Random(seed), []
    for phase, identifiers in groups:
        for repeat in REPEATS:
            for task_id in identifiers:
                levels = list(LEVELS)
                rng.shuffle(levels)
                for level in levels:
                    task = index[task_id]
                    schedule.append({'cell_id': f'{task_id}_r{repeat}_{level}',
                        'task_id': task_id, 'family_id': task['family_id'],
                        'split': 'train' if task in train else 'development',
                        'phase': phase, 'repeat': repeat, 'memory_level': level,
                        'shared_start_id': f'{task_id}_r{repeat}'})
    return schedule


def native_errors(row):
    """技术缺测与真实F/S失败分开；检查的是既定P7规则，不另造验证器。"""
    errors = []
    attempts = row.get('attempts', [])
    if not 1 <= len(attempts) <= 2:
        return ['invalid_P7_attempt_count']
    if row.get('preparation_blocked_reason'):
        errors.append('materials_preparation_blocked')
    if row.get('usage', {}).get('failed_calls', 0):
        errors.append('request_failure')
    for attempt in attempts:
        if attempt.get('measured') is not True:
            errors.append(attempt.get('error_type') or 'validation_unmeasured')
        else:
            if any(type(attempt.get(k)) is not bool for k in ('functional', 'security', 'joint')):
                errors.append('invalid_measured_outcome')
            elif attempt['joint'] != (attempt['functional'] and attempt['security']):
                errors.append('joint_inconsistent_with_F_S')
        if not attempt.get('code', '').strip():
            errors.append('empty_code')
        generation = attempt.get('generation', {})
        if generation.get('workflow_completed') is not True:
            errors.append('workflow_incomplete')
        if generation.get('error_type'):
            errors.append(generation['error_type'])
    if len(attempts) == 1 and attempts[0].get('measured') and not attempts[0].get('joint'):
        errors.append('required_repair_missing')
    if len(attempts) == 2 and attempts[0].get('joint'):
        errors.append('first_joint_early_stop_violated')
    return sorted(set(errors))


def _key(row):
    repeat = row['repeat']
    if type(repeat) is not int or repeat not in REPEATS:
        raise ValueError('invalid_repeat')
    return str(row['task_id']), repeat, row['memory_level']


def evaluate(schedule, rows, *, native_protocol, cell_costs=()):
    """读取真实原生产物。预览/重复格/其他协议不能混入；成本缺项不补零。"""
    pilot = [cell for cell in schedule if cell['phase'] != 'expansion']
    expected = {_key(cell): cell for cell in pilot}
    all_expected = {_key(cell): cell for cell in schedule}
    if len(pilot) != 120 or len(expected) != 120:
        raise ValueError('C1_requires_12_by_5_by_2')
    received = {}
    for row in rows:
        key = _key(row)
        if key not in all_expected:
            raise ValueError('row_outside_fixed_schedule')
        if row.get('is_experiment_score') is False or 'attempts' not in row:
            raise ValueError('preview_is_not_native_outcome')
        if row.get('protocol') != native_protocol or row.get('arm') != 'P7' or row.get('subset') != 'PLT':
            raise ValueError('native_protocol_or_arm_mismatch')
        if row.get('Q_updates') != 0:
            raise ValueError('Q_must_remain_frozen')
        if key in received:
            raise ValueError('duplicate_task_repeat_level')
        received[key] = row
    costs = {}
    for item in cell_costs:
        cell_id = item['cell_id']
        if cell_id not in {c['cell_id'] for c in schedule} or cell_id in costs:
            raise ValueError('cost_outside_schedule_or_duplicate')
        value = item.get('prompt_tokens')
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError('invalid_cost_tokens')
        costs[cell_id] = item

    outcomes = []
    for key, cell in expected.items():
        row = received.get(key)
        errors = native_errors(row) if row else ['not_executed']
        first, final = (row['attempts'][0], row['attempts'][-1]) if row and row['attempts'] else ({}, {})
        outcome = {**cell, 'status': 'missing' if not row else 'technical_error' if errors else 'measured',
                   'errors': errors}
        for position, attempt in [('first', first), ('final', final)]:
            for name in ('functional', 'security', 'joint'):
                outcome[f'{position}_{name}'] = attempt.get(name) if attempt.get('measured') is True else None
        usage = row.get('usage', {}) if row else {}
        outcome['native_prompt_tokens'] = usage.get('prompt_tokens')
        cost = costs.get(cell['cell_id'], {})
        complete_cost = cost.get('complete') is True and cost.get('prompt_tokens') is not None
        outcome['complete_cell_prompt_tokens'] = cost['prompt_tokens'] if complete_cost else None
        outcomes.append(outcome)

    # 首次五档必须共享同一组有序选卡。L0的实际呈现为空，但pre_level_selected_ids仍须一致。
    shared_errors = []
    for task_id in dict.fromkeys(c['task_id'] for c in pilot):
        for repeat in REPEATS:
            group = [received.get((task_id, repeat, level)) for level in LEVELS]
            present = [row for row in group if row and row.get('attempts')]
            traces = [(row['attempts'][0].get('retrieval_trace') or {}) for row in present]
            if any('pre_level_selected_ids' not in trace for trace in traces):
                shared_errors.append(f'{task_id}_r{repeat}:missing_first_selection_trace')
            elif traces and any(trace['pre_level_selected_ids'] != traces[0]['pre_level_selected_ids'] for trace in traces):
                shared_errors.append(f'{task_id}_r{repeat}:first_selected_ids_or_order_differ')

    arms = {}
    for level in LEVELS:
        items = [o for o in outcomes if o['memory_level'] == level]
        valid = [o for o in items if o['status'] == 'measured']
        arms[level] = {'planned': len(items), 'valid_cells': len(valid),
            'technical_cells': sum(o['status'] == 'technical_error' for o in items),
            'missing_cells': sum(o['status'] == 'missing' for o in items)}
        for position in ('first', 'final'):
            arms[level][position] = {name: {'passed': sum(o[f'{position}_{name}'] is True for o in valid),
                'denominator': len(valid),
                'rate': sum(o[f'{position}_{name}'] is True for o in valid)/len(valid) if valid else None}
                for name in ('functional', 'security', 'joint')}

    by_task = {}
    for outcome in outcomes:
        by_task.setdefault(outcome['task_id'], []).append(outcome)
    families = []
    for task_id, items in by_task.items():
        entry = {'task_id': task_id, 'family_id': items[0]['family_id'], 'status': 'incomplete',
                 'acceptable_levels': [], 'unstable_levels': [], 'preferred_level': None}
        if any(error.startswith(task_id+'_r') for error in shared_errors):
            entry['status'] = 'invalid_shared_start'
        elif all(item['status'] == 'measured' for item in items):
            means = {level: sum(o['final_joint'] for o in items if o['memory_level'] == level)/2 for level in LEVELS}
            acceptable = [level for level in LEVELS if means[level] == 1]
            unstable = [level for level in LEVELS if means[level] == .5]
            entry.update(status='measured', joint_means=means, acceptable_levels=acceptable, unstable_levels=unstable,
                stable_different=bool(acceptable and any(value == 0 for value in means.values())))
            if not acceptable:
                entry['label_status'] = 'unstable_only' if unstable else 'all_five_failed'
            else:
                candidate_costs = {level: [o['complete_cell_prompt_tokens'] for o in items if o['memory_level'] == level]
                                   for level in acceptable}
                if any(value is None for values in candidate_costs.values() for value in values):
                    entry['label_status'] = 'acceptable_set_only_cost_incomplete'
                else:
                    averages = {level: sum(values)/2 for level, values in candidate_costs.items()}
                    entry.update(label_status='preferred_by_measured_input', input_token_means=averages,
                        preferred_level=min(acceptable, key=lambda level: (averages[level], LEVELS.index(level))))
        families.append(entry)

    missing = sum(o['status'] == 'missing' for o in outcomes)
    technical = sum(o['status'] == 'technical_error' for o in outcomes)
    gate = {'evaluated': False, 'status': 'not_evaluated_missing_outcomes', 'passed': None,
            'stable_different_families': None, 'reciprocal_level_pairs': None, 'oracle_minus_fixed': None}
    if technical or shared_errors:
        gate['status'] = 'blocked_technical_error'
    elif not missing:
        means = {f['task_id']: f['joint_means'] for f in families}
        fixed = {level: sum(m[level] for m in means.values())/12 for level in LEVELS}
        oracle = sum(max(m.values()) for m in means.values())/12
        stable = sum(f['stable_different'] for f in families)
        reciprocal = []
        for left, right in combinations(LEVELS, 2):
            left_wins = [tid for tid, m in means.items() if m[left] == 1 and m[right] == 0]
            right_wins = [tid for tid, m in means.items() if m[right] == 1 and m[left] == 0]
            if len(left_wins) >= 2 and len(right_wins) >= 2:
                reciprocal.append({'levels': [left, right], 'left_stable_wins': left_wins,
                                   'right_stable_wins': right_wins})
        passed = stable >= 4 and bool(reciprocal) and oracle - max(fixed.values()) >= .1 - 1e-12
        gate.update(evaluated=True, status='passed' if passed else 'failed', passed=passed,
            stable_different_families=stable, reciprocal_level_pairs=reciprocal,
            oracle_minus_fixed=oracle-max(fixed.values()), observed_oracle=oracle,
            fixed_joint_rates=fixed, best_fixed_levels=[l for l in LEVELS if fixed[l] == max(fixed.values())],
            oracle_is_deployable_score=False)
    return {'protocol': VERSION, 'native_protocol': native_protocol, 'planned_pilot_P7': 120,
        'received_pilot_rows': sum(key in received for key in expected),
        'missing_cells': missing, 'technical_cells': technical, 'shared_start_errors': shared_errors,
        'arms': arms, 'C1': gate, 'families': families, 'level_outcomes': outcomes,
        'API_calls': 0, 'Q_updates': 0, 'classifier_trained': False}


def execution_gate(schedule, rows, phase, *, native_protocol):
    """决定固定20/120/480前缀能否启动；技术门不要求正确率，扩展必须通过真实C1。"""
    if phase not in PHASE_LIMITS:
        raise ValueError('unknown_execution_phase')
    analysis = evaluate(schedule, rows, native_protocol=native_protocol)
    technical_ids = {c['cell_id'] for c in schedule[:20]}
    qualified = sum(o['cell_id'] in technical_ids and o['status'] == 'measured'
                    for o in analysis['level_outcomes'])
    technical_families = {c['task_id'] for c in schedule[:20]}
    invalid_shared = any(error.split('_r', 1)[0] in technical_families
                         for error in analysis['shared_start_errors'])
    reasons = []
    if phase != 'technical' and (qualified != 20 or invalid_shared):
        reasons.append('technical_prefix_not_qualified')
    if phase == 'expansion' and analysis['C1']['passed'] is not True:
        reasons.append('C1_not_passed')
    return {'phase': phase, 'prefix_limit': PHASE_LIMITS[phase], 'ready': not reasons,
            'reasons': reasons, 'qualified_technical_cells': qualified,
            'C1': analysis['C1'], 'new_API_calls': 0}

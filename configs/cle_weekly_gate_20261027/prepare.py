"""恢复固定上游被脱敏破坏的测试条件，另存全298题；不改活动学习或原验证器。"""
from __future__ import annotations

import argparse
import ast
import copy
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from configs.cle_weekly_full_20261027.prepare import RUN, read, disk_check, configure_validation
from configs.cle_memory_mechanisms_20261023.repair_preflight_v2 import missing_declarations
from methods.cle_ablation.retrieval_q_study import reference_check
from methods.sct_trajectory.replay_journal import write_json

PROTOCOL = 'cle-weekly-full-gate-restored-public-contract-20261027-v2'


def repair_task(original, upstream):
    """只恢复原件中的损坏字段；公开描述仅补依赖名称/类型，参考修正单列。"""
    tid = str(original['index'])
    if original['index'] != upstream['index'] or original['CWE_ID'] != upstream['CWE_ID']:
        raise ValueError('upstream_identity_differed:' + tid)
    task = copy.deepcopy(original)
    changes = []
    for field in ('setup', 'testcases'):
        value = task['unittest'].get(field, '')
        if '<LOCAL_PATH>' in value:
            if original['ground_truth'] != upstream['ground_truth']:
                raise ValueError('reference_differed_before_fixture_restoration:' + tid)
            restored = upstream['unittest'][field]
            if '<LOCAL_PATH>' in restored:
                raise ValueError('upstream_also_redacted:' + tid)
            task['unittest'][field] = restored
            changes.append({'field': 'unittest.' + field, 'kind': 'pinned_upstream_fixture_restoration'})
    # 已有明确案例：题面称USERS，实际约定绑定为USER_DETAILS/SYSTEM_USERS。
    context = task['task_description'].get('context', '')
    reference = ''.join(task['ground_truth'][k] for k in ('code_before', 'patched_code', 'code_after'))
    if tid in ('1015', '1016'):
        name = 'USER_DETAILS' if tid == '1015' else 'SYSTEM_USERS'
        if name in reference and re.search(r'\bUSERS\b', context):
            context = re.sub(r'\bUSERS\b', name, context)
            changes.append({'field': 'task_description.context', 'kind': 'correct_external_binding_name',
                            'from': 'USERS', 'to': name})
    task['task_description']['context'] = context
    declarations = missing_declarations(task)
    if declarations:
        task['task_description']['context'] += ('\nHost-provided dependencies (names and types only):\n- '
                                               + '\n- '.join(declarations))
        changes.append({'field': 'task_description.context', 'kind': 'external_dependency_declarations',
                        'declarations': declarations})
    # 87的原参考正则与公开LOG_LEVEL[TIMESTAMP] : MESSAGE格式冲突，沿历史修订。
    # 这只校准参考，不改题面/测试，也不会送给生成器。
    if tid == '87':
        replacement = "\n    log_pattern = re.compile(r'([^\\[\\]\\r\\n]+)\\[([^\\[\\]\\r\\n]+)\\]\\s*:\\s*(.*)')"
        if task['ground_truth']['patched_code'] != replacement:
            task['ground_truth']['patched_code'] = replacement
            changes.append({'field': 'ground_truth.patched_code', 'kind': 'reference_only_public_format_alignment',
                            'prior_method': 'configs/cle_memory_mechanisms_20261023/repair_preflight_v2.py: task87'})
    return task, {'task_id': tid, 'changes': changes, 'original_preserved': True,
                  'fixture_values_added_to_public_context': False}


def prepare():
    disk_check()
    root = RUN / 'FQ_GATE'
    destination = root / 'inputs_v2'
    if (destination / 'tasks.json').exists():
        return read(destination / 'repair_manifest.json')
    originals = read(RUN / 'shared_inputs/tasks_D_gate.json')
    upstream = {str(t['index']): t for t in read(root / 'preflight/upstream_pinned.json')}
    ids = read(RUN / 'manifest.json')['pools']['D_gate']
    if len(ids) != 298 or len(set(ids)) != 298 or set(originals) != set(ids):
        raise ValueError('fixed_full_298_identity_differed')
    tasks, changes = {}, []
    for tid in ids:
        task, receipt = repair_task(originals[tid], upstream[tid])
        if task['family_id'] != originals[tid]['family_id']:
            raise ValueError('task_family_changed')
        tasks[tid] = task
        if receipt['changes']:
            changes.append(receipt)
    manifest = {'protocol': PROTOCOL, 'planned': 298, 'task_ids': ids, 'changed_tasks': len(changes),
        'changes': changes, 'model_API_calls': 0, 'Q_updates': 0,
        'original_task_file': str(RUN / 'shared_inputs/tasks_D_gate.json'),
        'upstream': read(root / 'preflight/upstream_source.json'),
        'active_learning_inputs_modified': False, 'validator_changed': False,
        'reference_only_repairs': ['87'], 'paid_dispatch_ready': False,
        'public_contract_review_scope': 'dependency-name/type review and known name conflicts; not exhaustive semantic review'}
    write_json(destination / 'tasks.json', tasks)
    write_json(destination / 'repair_manifest.json', manifest)
    return manifest


def preflight():
    configure_validation()
    root = RUN / 'FQ_GATE'
    tasks = read(root / 'inputs_v2/tasks.json')
    def one(tid):
        out = root / 'preflight_v2/tasks' / (tid + '.json')
        if out.exists():
            return read(out)
        task = tasks[tid]
        result = reference_check(task)
        result.update(task_id=tid, family_id=task['family_id'], cwe=task['CWE_ID'],
                      placeholder='<LOCAL_PATH>' in json.dumps(task, ensure_ascii=False),
                      remaining_declarations=missing_declarations(task), protocol=PROTOCOL)
        write_json(out, result)
        return result
    results = []
    with ThreadPoolExecutor(max_workers=4) as workers:
        for future in as_completed([workers.submit(one, tid) for tid in tasks]):
            results.append(future.result())
    summary = {'protocol': PROTOCOL, 'planned': 298, 'completed': len(results),
        'reference_joint': sum(r['state'] == 'A' for r in results),
        'reference_and_name_checks_passed': sum(r['passed'] and not r['remaining_declarations'] and not r['placeholder'] for r in results),
        'remaining_reference_failed_ids': sorted([r['task_id'] for r in results if r['state'] != 'A'], key=int),
        'remaining_contract_check_ids': sorted([r['task_id'] for r in results if r['undeclared_setup_bindings'] or r['remaining_declarations'] or r['placeholder']], key=int),
        'new_model_generations': 0, 'model_API_calls': 0, 'Q_updates': 0, 'active_learning_inputs_modified': False,
        'reference_pass_does_not_prove_public_contract_completeness': True,
        'paid_dispatch_ready': False, 'not_a_generated_code_result': True}
    write_json(root / 'preflight_v2/summary.json', summary)
    return summary


def revise_reference89():
    """保留v2全部预检；只修公开格式同样冲突的89参考，297个未变检查精确复用。"""
    root = RUN / 'FQ_GATE'
    before = read(root / 'preflight_v2/summary.json')
    if before['remaining_reference_failed_ids'] != ['89'] or before['remaining_contract_check_ids']:
        raise ValueError('v2_has_other_unresolved_problems_do_not_mark_full_ready')
    source = read(root / 'inputs_v2/tasks.json')
    destination = root / 'inputs_v3'
    if (destination / 'tasks.json').exists():
        return read(root / 'preflight_v3/summary.json')
    revised = copy.deepcopy(source)
    revised['89']['ground_truth']['patched_code'] = revised['87']['ground_truth']['patched_code']
    if revised['89']['task_description'] != source['89']['task_description'] or revised['89']['unittest'] != source['89']['unittest']:
        raise ValueError('reference_only_repair_changed_public_or_tests')
    protocol = PROTOCOL.replace('-v2', '-v3')
    write_json(destination / 'tasks.json', revised)
    manifest = copy.deepcopy(read(root / 'inputs_v2/repair_manifest.json'))
    manifest.update(protocol=protocol, reference_only_repairs=['87', '89'],
                    parent_input=str(root / 'inputs_v2/tasks.json'),
                    additional_change='89 reference regex aligned with the same explicit public format as87; public/test unchanged')
    manifest['changed_tasks'] += 1
    manifest['changes'].append({'task_id': '89', 'original_preserved': True,
        'fixture_values_added_to_public_context': False,
        'changes': [{'field': 'ground_truth.patched_code', 'kind': 'reference_only_public_format_alignment'}]})
    write_json(destination / 'repair_manifest.json', manifest)
    configure_validation()
    records = []
    for tid, task in revised.items():
        path = root / 'preflight_v2/tasks' / (tid + '.json')
        if tid == '89':
            result = reference_check(task)
            result.update(task_id=tid, family_id=task['family_id'], cwe=task['CWE_ID'],
                          placeholder=False, remaining_declarations=missing_declarations(task))
        else:
            if task != source[tid]:
                raise ValueError('unchanged_reference_reuse_differed:' + tid)
            result = read(path)
            result['reused_check_from'] = str(path)
        result['protocol'] = protocol
        write_json(root / 'preflight_v3/tasks' / (tid + '.json'), result)
        records.append(result)
    summary = {**before, 'protocol': protocol,
        'reference_joint': sum(r['state'] == 'A' for r in records),
        'reference_and_name_checks_passed': sum(r['passed'] and not r['remaining_declarations'] and not r['placeholder'] for r in records),
        'remaining_reference_failed_ids': [r['task_id'] for r in records if r['state'] != 'A'],
        'remaining_contract_check_ids': [r['task_id'] for r in records if r['undeclared_setup_bindings'] or r['remaining_declarations'] or r['placeholder']],
        'reused_unchanged_reference_checks': 297, 'new_reference_checks': 1,
        'reference_preflight_ready': all(r['passed'] and not r['remaining_declarations'] and not r['placeholder'] for r in records),
        'paid_dispatch_ready': False}
    write_json(root / 'preflight_v3/summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'preflight', 'revise-reference89'])
    args = parser.parse_args()
    result = prepare() if args.action == 'prepare' else preflight() if args.action == 'preflight' else revise_reference89()
    print(json.dumps({k: v for k, v in result.items() if k not in ('changes', 'task_ids', 'upstream')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

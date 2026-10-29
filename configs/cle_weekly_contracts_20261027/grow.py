"""独立修复D_grow评价契约并预检；不改已经冻结的Q学习输入或原验证器。"""
from __future__ import annotations

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from configs.cle_weekly_full_20261027.prepare import RUN, read, disk_check, configure_validation
from configs.cle_weekly_gate_20261027.prepare import repair_task as common_repair
from configs.cle_memory_mechanisms_20261023.repair_preflight_v2 import missing_declarations
from methods.cle_ablation.retrieval_q_study import reference_check
from methods.sct_trajectory.replay_journal import write_json


PROTOCOL = 'cle-weekly-full-grow-restored-public-contract-20261027-v2'


def repair_task(original, upstream):
    """恢复已观测占位符、名称缺失和三份错误参考，测试值不进入公开描述。"""
    task, receipt = common_repair(original, upstream)
    tid = str(task['index'])
    if tid in ('84', '85'):
        # 与D_gate的87/89相同公开格式；只校准参考，不改原题和验收测试。
        task['ground_truth']['patched_code'] = (
            "\n    log_pattern = re.compile(r'([^\\[\\]\\r\\n]+)\\[([^\\[\\]\\r\\n]+)\\]\\s*:\\s*(.*)')")
        receipt['changes'].append({'field': 'ground_truth.patched_code',
            'kind': 'reference_only_public_format_alignment',
            'reason': 'original regex expects [timestamp] level, while public contract states level[timestamp]'})
    if tid == '108':
        # 复用10月23日已经登记的参考勘误；不扩展本轮安全测试或生成器要求。
        old = task['ground_truth']['patched_code']
        if "if '..' in local_part" not in old:
            raise ValueError('email_reference_no_longer_matches_known_case')
        task['ground_truth']['patched_code'] = old + "\n    if local_part.startswith('.'):\n        return False"
        receipt['changes'].append({'field': 'ground_truth.patched_code',
            'kind': 'reference_only_existing_email_format_correction',
            'prior_method': 'cle_memory_mechanisms_20261023/repair_preflight_v2.py:108'})
    if tid == '468':
        context = task['task_description'].get('context', '')
        revised = re.sub(r'\bdatabase\b', 'user_database', context).replace('EXPECTED_CSRF_TOKEN', 'VALID_CSRF_TOKEN')
        if context != revised:
            task['task_description']['context'] = revised
            receipt['changes'].append({'field': 'task_description.context',
                'kind': 'known_external_binding_name_correction', 'prior_method': 'repair_preflight_v2.py:468'})
    if task['family_id'] != original['family_id']:
        raise ValueError('family_identity_changed')
    return task, receipt


def prepare():
    disk_check()
    package = RUN / 'FG_LABELS'
    inputs = package / 'inputs_contract_v2'
    if (inputs / 'tasks.json').exists():
        return read(inputs / 'repair_manifest.json')
    original_path = RUN / 'shared_inputs/tasks_D_grow.json'
    originals = read(original_path)
    pinned = RUN / 'FQ_GATE/preflight/upstream_pinned.json'
    upstream = {str(task['index']): task for task in read(pinned)}
    ids = read(RUN / 'manifest.json')['pools']['D_grow']
    if len(ids) != 273 or len(set(ids)) != 273 or set(ids) != set(originals):
        raise ValueError('full_273_fixed_identity_required')
    tasks, receipts = {}, []
    for tid in ids:
        task, receipt = repair_task(originals[tid], upstream[tid])
        tasks[tid] = task
        if receipt['changes']:
            receipts.append(receipt)
    manifest = {'protocol': PROTOCOL, 'planned': 273, 'task_ids': ids, 'changed_tasks': len(receipts),
        'changes': receipts, 'original_task_file': str(original_path),
        'upstream': read(RUN / 'FQ_GATE/preflight/upstream_source.json'),
        'reference_only_repairs': ['84', '85', '108'],
        'active_learning_inputs_modified': False, 'original_preserved': True,
        'validator_changed': False, 'model_API_calls': 0, 'Q_updates': 0,
        'reference_preflight_ready': False,
        'public_contract_review_scope': 'known name/type and observed reference/fixture defects; not exhaustive semantic proof',
        'historical_generation_credit': 0}
    write_json(inputs / 'tasks.json', tasks)
    write_json(inputs / 'repair_manifest.json', manifest)
    return manifest


def preflight():
    configure_validation()
    root = RUN / 'FG_LABELS'
    tasks = read(root / 'inputs_contract_v2/tasks.json')
    output = root / 'preflight_contract_v2'

    def one(tid):
        path = output / 'tasks' / (tid + '.json')
        if path.exists():
            return read(path)
        task = tasks[tid]
        result = reference_check(task)
        result.update(protocol=PROTOCOL, task_id=tid, family_id=task['family_id'], cwe=str(task['CWE_ID']),
            remaining_declarations=missing_declarations(task),
            placeholder='<LOCAL_PATH>' in json.dumps(task, ensure_ascii=False))
        write_json(path, result)
        return result

    records = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(one, tid) for tid in tasks]):
            records.append(future.result())
    qualified = [r for r in records if r['passed'] and not r['remaining_declarations'] and not r['placeholder']]
    summary = {'protocol': PROTOCOL, 'planned': 273, 'completed': len(records),
        'reference_joint': sum(r['state'] == 'A' for r in records),
        'reference_and_name_checks_passed': len(qualified),
        'remaining_reference_failed_ids': sorted([r['task_id'] for r in records if r['state'] != 'A'], key=int),
        'remaining_contract_check_ids': sorted([r['task_id'] for r in records if r not in qualified], key=int),
        'reference_preflight_ready': len(qualified) == len(tasks) == 273,
        'model_API_calls': 0, 'new_model_generations': 0, 'Q_updates': 0,
        'active_learning_inputs_modified': False, 'validator_changed': False,
        'not_a_generated_code_result': True, 'reference_pass_does_not_prove_public_contract_completeness': True}
    write_json(output / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'preflight'])
    action = parser.parse_args().action
    result = prepare() if action == 'prepare' else preflight()
    print(json.dumps({k: v for k, v in result.items() if k not in ('changes', 'task_ids', 'upstream')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

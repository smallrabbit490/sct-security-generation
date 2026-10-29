"""包A零API准备：固定名单、导出盲审、建立来源索引并调用原验证器预检。

不创建模型客户端，不读取凭据，不更新卡库或Q；原始数据只读。生成模型未运行，
参考实现成绩只能作为验证环境证据。输出使用本任务在E盘的新运行目录链接。
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from methods.cle_ablation.run_joint_contract import load_explicit_tasks, select_tasks

ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path(__file__).resolve().parent
OUT = ROOT / 'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1'
ONLINE = ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1'
PROTOCOL = 'cle-memory-mechanisms-preparation-v1'
HUMAN_SOURCE = ROOT / 'translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2/human_review.csv'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_csv(path, rows, fields=None):
    fields = fields or list(rows[0])
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def load_pools():
    return {name: load_explicit_tasks(ONLINE / f'tasks_{name}.json', 'PLT')
            for name in ('D_init', 'D_grow', 'D_gate')}


def prepare():
    """在查看新预检和模型成绩前锁名单；不按结果替换不合格题。"""
    if (CONFIG / 'manifest.json').exists():
        raise FileExistsError('manifest already locked; do not silently replace cohorts')
    pools = load_pools()
    old = read(ROOT / 'configs/cle_contract_q_20261023/manifest.json')
    excluded = {row['family_id'] for row in old['tasks']}
    grow = select_tasks(sorted(pools['D_grow'], key=lambda t: str(t['index'])), 'PLT', 48)
    gate = select_tasks(sorted((t for t in pools['D_gate'] if t['family_id'] not in excluded),
                               key=lambda t: str(t['index'])), 'PLT', 48)
    groups = {'train': grow[:36], 'development': grow[36:],
              'granularity_confirmation': gate[:24], 'q_confirmation': gate[24:]}
    assert [len(groups[k]) for k in groups] == [36, 12, 24, 24]
    family_sets = [{t['family_id'] for t in tasks} for tasks in groups.values()]
    assert all(not a.intersection(b) for i, a in enumerate(family_sets) for b in family_sets[:i])
    manifest = {'protocol': PROTOCOL, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'selection': 'CWE/string-ID round robin; one task per family; no new outcomes inspected',
        'first_pilot_ids': [str(t['index']) for t in grow[:12]],
        'technical_probe_ids': [str(t['index']) for t in grow[:2]],
        'excluded_gate_families': sorted(excluded), 'historical_CLE_exposure': True,
        'new_generations': 0, 'Q_updates': 0, 'paid_phase_status': 'not_started',
        'groups': {name: [{'task_id': str(t['index']), 'family_id': t['family_id'],
                          'cwe': str(t['CWE_ID'])} for t in tasks] for name, tasks in groups.items()}}
    for name, tasks in groups.items():
        write(OUT / f'tasks_{name}.json', tasks)
    write(CONFIG / 'manifest.json', manifest)
    write(OUT / 'manifest.json', manifest)
    reviews = [{'group': name, 'task_id': str(t['index']), 'family_id': t['family_id'],
        'public_task': json.dumps(t['task_description'], ensure_ascii=False),
        'review_status': 'pending_public_contract_review', 'missing_public_requirement': '',
        'evidence': '', 'decision': ''} for name, tasks in groups.items() for t in tasks]
    write_csv(OUT / 'contract_review.csv', reviews)

    memory_path = ONLINE / 'D_grow/frozen/m_star_q.jsonl'
    nodes = [json.loads(line) for line in memory_path.read_text(encoding='utf-8').splitlines() if line]
    initial = {str(t['index']): t for t in pools['D_init']}
    sources = []
    for node in nodes:
        tid = str(node['source']['task_id'])
        source = initial.get(tid)
        sources.append({'card_id': node['invariant_id'], 'source_task_id': tid,
            'source_family_id': source['family_id'] if source else None,
            'source_pool': 'D_init' if source else None, 'source_example_available': bool(source),
            'example_file': f'source_examples/{tid}.json' if source else None,
            'q_value': node['q_value'], 'q_visits': node['q_visits']})
    for tid, task in initial.items():
        gt = task['ground_truth']
        write(OUT / 'source_examples' / f'{tid}.json', {'source_task_id': tid,
            'source_family_id': task['family_id'], 'public_task': task['task_description'],
            'secure_training_source_code': gt['code_before'] + gt['patched_code'] + gt['code_after'],
            'use': 'D_init seed-from-diff source only; never use target-family reference'})
    write_csv(OUT / 'source_example_index.csv', sources)
    pool_families = {name: {t['family_id'] for t in tasks} for name, tasks in pools.items()}
    inventory = {'protocol': PROTOCOL, 'pool_counts': {name: len(t) for name, t in pools.items()},
        'family_counts': {name: len(f) for name, f in pool_families.items()},
        'pool_family_disjoint': all(not a.intersection(b) for i, a in enumerate(pool_families.values())
                                  for b in list(pool_families.values())[:i]),
        'cards': len(nodes), 'visited_cards': sum(n['q_visits'] > 0 for n in nodes),
        'source_examples_available': sum(s['source_example_available'] for s in sources),
        'distinct_source_tasks': len({s['source_task_id'] for s in sources}),
        'L4_source_status': 'training sources indexed; not yet rendered or evaluated',
        'notion_raw_status': 'not located in previously checked workspace and archive index',
        'notion_unaccounted_pairs': 5817 - sum([253, 1632, 2500, 1326]),
        'raw_output_resolved': str(OUT.resolve()), 'API_calls': 0}
    write(OUT / 'inventory.json', inventory)
    metadata = {'protocol': PROTOCOL, 'created_utc': manifest['created_utc'],
        'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'python': platform.python_version(), 'API_calls': 0, 'model_generations': 0,
        'Q_updates': 0, 'frozen_memory': str(memory_path.relative_to(ROOT)),
        'input_pools': {k: str((ONLINE / f'tasks_{k}.json').relative_to(ROOT)) for k in pools}}
    write(OUT / 'run_metadata.json', metadata)
    print(json.dumps(inventory, ensure_ascii=False), flush=True)


def export_review():
    """导出真正盲审表；AI答案单独保存，人类栏不由Agent代填。"""
    destination = OUT / 'human_review_blind.csv'
    if destination.exists():
        raise FileExistsError('human review export exists; preserve annotations')
    with HUMAN_SOURCE.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    fields = ['pair_id', 'task', 'card', 'human_label', 'task_evidence', 'card_evidence',
              'reason', 'reviewer', 'confirmed_at']
    blind = [{key: row[key] for key in fields} for row in rows]
    write_csv(destination, blind, fields)
    write_csv(OUT / 'ai_annotation_key.csv', [
        {key: row[key] for key in ('pair_id', 'ai_label', 'ai_reason')} for row in rows])
    confirmed = sum(bool(r['human_label'] and r['reviewer'] and r['confirmed_at']) for r in rows)
    status = {'pairs': len(rows), 'human_confirmed': confirmed,
        'AI_label_counts': dict(Counter(r['ai_label'] for r in rows)),
        'formal_metrics_gate': confirmed == len(rows) and all(r['human_label'] != 'insufficient' for r in rows),
        'AI_columns_hidden_in_blind_export': True, 'API_calls': 0}
    write(OUT / 'human_review_status.json', status)
    print(json.dumps(status, ensure_ascii=False), flush=True)


def preflight():
    """调用原本地验证器检查已锁名单；保留每题结果，恢复只补未检查题。"""
    from methods.cle_ablation.retrieval_q_study import reference_check
    manifest = read(CONFIG / 'manifest.json')
    tasks = [(group, task) for group in manifest['groups']
             for task in read(OUT / f'tasks_{group}.json')]
    raw = OUT / 'reference_preflight'
    raw.mkdir(exist_ok=True)

    def check(item):
        group, task = item
        path = raw / f"{task['index']}.json"
        if path.exists():
            return read(path)
        result = reference_check(task)
        result.update(group=group, family_id=task['family_id'],
                      public_contract_manual_review='pending',
                      scope='reference_execution_plus_setup_binding_heuristic_not_model_scores')
        write(path, result)
        return result

    records = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(check, item) for item in tasks]
        for future in as_completed(futures):
            row = future.result()
            records.append(row)
            print(json.dumps({'completed': len(records), 'task_id': row['task_id'],
                              'reference_state': row['state'], 'passed': row['passed']}, ensure_ascii=False), flush=True)
    records.sort(key=lambda r: (r['group'], r['task_id']))
    summary = {'protocol': PROTOCOL, 'planned': len(tasks), 'completed': len(records),
        'reference_joint_pass': sum(r['state'] == 'A' for r in records),
        'reference_and_binding_heuristic_pass': sum(r['passed'] for r in records),
        'reference_fail_ids': [r['task_id'] for r in records if r['state'] != 'A'],
        'public_dependency_flag_ids': [r['task_id'] for r in records if r['undeclared_setup_bindings']],
        'public_review_pending': len(records), 'records': records,
        'stage_A2_complete': False, 'API_calls': 0, 'model_generations': 0,
        'next': 'review fixed-cohort defects without replacing tasks; complete public-contract review'}
    write(OUT / 'reference_preflight.json', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'records'}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'export-review', 'preflight'])
    action = parser.parse_args().action
    {'prepare': prepare, 'export-review': export_review, 'preflight': preflight}[action]()


if __name__ == '__main__':
    main()

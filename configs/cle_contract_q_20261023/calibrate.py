"""对已固定48题做原参考实现的本机环境预检；零API，不生成CLE代码或学习Q。"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import json
import platform
import sys
import argparse

from methods.cle_ablation import joint_contract, runner
from methods.cle_ablation.run_joint_contract import load_explicit_tasks, runtime_preflight
from configs.cle_dgrow_url_repair_20261019.repair_and_retest import reference

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'translation_work/diagnostics/20261023/cle_contract_q/reference_preflight_v1'
CURATED = ROOT / 'results/curated/cle_contract_q_20261023'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restored-v2', action='store_true')
    args = parser.parse_args()
    raw_dir = RAW.with_name('reference_preflight_v2') if args.restored_v2 else RAW
    raw_dir.mkdir(parents=True, exist_ok=False)
    tasks_path = ROOT / ('translation_work/diagnostics/20261023/cle_contract_q/tasks_D_gate_48_restored_urls_v2.json'
                         if args.restored_v2 else 'translation_work/diagnostics/20261023/cle_contract_q/tasks_D_gate_48.json')
    tasks = load_explicit_tasks(tasks_path, 'PLT')
    frozen_path = ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1/D_grow/frozen/m_star_q.jsonl'
    memory = runner.load_memory(frozen_path)
    original = runner.load_memory(ROOT / 'docs/cle_evidence_package_20261015/experience_pool_1939.jsonl')
    body = lambda items: {n.invariant_id: {k: v for k, v in n.to_dict().items() if k not in ('q_value', 'q_visits')} for n in items}
    identity = {'cards': len(memory), 'visited_cards': sum(n.q_visits > 0 for n in memory),
                'same_card_bodies_lifecycle_as_original': body(memory) == body(original),
                'snapshot_sha256': runner.digest(frozen_path)}
    assert identity['cards'] == 1939 and identity['visited_cards'] == 972 and identity['same_card_bodies_lifecycle_as_original']
    records = []
    def check(task):
        tid = str(task['index'])
        result = joint_contract.official_evaluate('PLT', task, reference(task, secure=True))
        raw = raw_dir / (tid + '.json')
        raw.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        evidence = result.get('validation', {}).get('evidence', {})
        return {'task_id': tid, 'family_id': task['family_id'],
                'reference_measured': result['measured'], 'reference_joint': result['joint'],
                'functional': result['functional'], 'security': result['security'],
                'errors': {k: v.get('error_type') for k, v in evidence.items() if isinstance(v, dict) and v.get('error_type')},
                'raw_evidence': str(raw.relative_to(ROOT))}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(check, task): str(task['index']) for task in tasks}
        for future in as_completed(futures):
            row = future.result()
            records.append(row)
            print(json.dumps({'done': len(records), 'task_id': row['task_id'], 'reference_joint': row['reference_joint']}), flush=True)
    records.sort(key=lambda r: r['task_id'])
    summary = {'scope': 'reference_environment_check_not_CLE_model_scores', 'tasks': 48,
        'completed': len(records), 'reference_joint_pass': sum(r['reference_joint'] for r in records),
        'all_references_pass': all(r['reference_joint'] for r in records), 'records': records,
        'frozen_memory': identity, 'runtime': runtime_preflight('PLT'), 'python': sys.version.split()[0],
        'platform': platform.platform(), 'API_calls': 0, 'new_model_generations': 0,
        'new_model_Joint_scores': 0, 'hidden_feedback_used_for_routing_or_generation': False,
        'original_records_modified': False}
    summary['tasks_path'] = str(tasks_path.relative_to(ROOT))
    summary['runtime']['positive_control_executed'] = True
    assert runner.digest(frozen_path) == identity['snapshot_sha256']
    CURATED.mkdir(parents=True, exist_ok=True)
    (CURATED / ('reference_preflight_v2.json' if args.restored_v2 else 'reference_preflight.json')).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('completed', 'reference_joint_pass', 'all_references_pass', 'runtime', 'frozen_memory')}), flush=True)


if __name__ == '__main__':
    main()

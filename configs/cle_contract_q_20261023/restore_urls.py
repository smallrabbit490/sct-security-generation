"""固定48题不换题：按既有固定上游恢复损坏URL夹具，保留v1，不向模型透露测试值。"""
import copy
import json
from pathlib import Path
import re
import urllib.request

from configs.cle_dgrow_url_repair_20261019.repair_and_retest import SOURCE, REVISION

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'translation_work/diagnostics/20261023/cle_contract_q'
CURATED = ROOT / 'results/curated/cle_contract_q_20261023'


def main():
    original_path = RAW / 'tasks_D_gate_48.json'
    target = RAW / 'tasks_D_gate_48_restored_urls_v2.json'
    if target.exists():
        raise FileExistsError('preserve_existing_restoration')
    tasks = json.loads(original_path.read_text(encoding='utf-8'))
    with urllib.request.urlopen(SOURCE, timeout=30) as response:
        upstream = json.load(response)
    source = {str(t['index']): t for t in upstream}
    changes = []
    restored = copy.deepcopy(tasks)
    for task in restored:
        tests = task['unittest']['testcases']
        if not re.search(r'https?<LOCAL_PATH>|htt<LOCAL_PATH>', tests):
            continue
        tid = str(task['index']); authoritative = source[tid]
        assert task['CWE_ID'] == authoritative['CWE_ID']
        assert task['ground_truth'] == authoritative['ground_truth']
        assert task['unittest']['setup'] == authoritative['unittest']['setup']
        assert task['install_requires'] == authoritative['install_requires']
        assert '<LOCAL_PATH>' not in authoritative['unittest']['testcases']
        task['unittest']['testcases'] = authoritative['unittest']['testcases']
        changes.append({'task_id': tid, 'cwe': str(task['CWE_ID']), 'changed_fields': ['unittest.testcases'],
                        'public_contract_unchanged': True, 'reference_unchanged': True, 'setup_unchanged': True})
    assert [t['index'] for t in tasks] == [t['index'] for t in restored]
    assert len(changes) == 5
    target.write_text(json.dumps(restored, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    receipt = {'protocol': 'same-48-task-URL-fixture-restoration-v2', 'upstream_revision': REVISION,
        'source_url': SOURCE, 'original_tasks': str(original_path.relative_to(ROOT)),
        'restored_tasks': str(target.relative_to(ROOT)), 'tasks': 48, 'changed_tasks': changes,
        'selection_unchanged': True, 'historical_scores_unchanged': True,
        'new_model_generations': 0, 'test_values_added_to_public_context': False}
    (CURATED / 'url_restoration.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest_path = Path(__file__).resolve().parent / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['original_selected_tasks_path'] = manifest['selected_tasks_path']
    manifest['selected_tasks_path'] = str(target.relative_to(ROOT))
    manifest['fixture_protocol'] = receipt['protocol']
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()

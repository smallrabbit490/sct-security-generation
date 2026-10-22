"""网址题修订的公开边界及已观测环境错误回归，不调用API或重跑历史生成。"""
import copy
import json
from pathlib import Path

from configs.cle_dgrow_url_repair_20261019.repair_and_retest import declarations, measured


ROOT = Path(__file__).resolve().parents[1]


def test_restoration_keeps_reference_setup_and_original_dataset():
    original = json.loads((ROOT / 'data/external/secodeplt/secodeplt/data.json').read_text(encoding='utf-8'))
    repaired = json.loads((ROOT / 'configs/cle_dgrow_url_repair_20261019/repaired_tasks.json').read_text(encoding='utf-8'))
    assert len(repaired) == 32
    assert len({t['index'] for t in repaired}) == 32
    for task in repaired:
        old = original[task['index']]
        assert '<LOCAL_PATH>' in old['unittest']['testcases']
        assert '<LOCAL_PATH>' not in json.dumps(task)
        assert task['ground_truth'] == old['ground_truth']
        assert task['unittest']['setup'] == old['unittest']['setup']
        assert not declarations(task)


def test_added_public_context_has_only_binding_declarations():
    config = ROOT / 'configs/cle_dgrow_url_repair_20261019'
    tasks = json.loads((config / 'repaired_tasks.json').read_text(encoding='utf-8'))
    manifest = json.loads((config / 'repair_manifest.json').read_text(encoding='utf-8'))
    changed = {int(r['task_id']): r for r in manifest['changes'] if r['declared_bindings']}
    assert len(changed) == 24
    for task in tasks:
        if task['index'] not in changed:
            continue
        addition = task['task_description']['context'].split('External runtime bindings', 1)[1]
        assert '://' not in addition
        assert '[' not in addition.replace('list[str]', '')
        assert 'testcase' not in addition.lower()
        assert 'patched_code' not in addition


def test_setup_failure_is_unmeasured_even_when_adapter_reports_fail():
    evidence = {'functional': {'status': 'fail'}, 'security': {'status': 'fail'},
                'metadata': {'worker_error': {'type': 'ModuleNotFoundError', 'stage': 'setup'},
                             'test_groups': {}}}
    assert not measured(evidence)
    real_failure = copy.deepcopy(evidence)
    real_failure['metadata'] = {'test_groups': {'capability': {'total': 2}, 'safety': {'total': 3}}}
    assert measured(real_failure)

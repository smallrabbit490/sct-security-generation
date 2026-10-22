"""验证81题独立覆盖、公开边界和新D_init名单；不调用模型或重跑历史生成。"""
import ast
import hashlib
import json
from pathlib import Path

from configs.cle_dinit_repair_20261020.repair_and_preflight import (
    CONFIG, DATA, OLD_QUAL, OUT, expression_type, interface_bindings,
)

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def test_originals_and_reference_preserved_by_independent_overlay():
    meta = read(CONFIG / 'repair_manifest.json')
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == meta['original_dataset_sha256']
    assert hashlib.sha256(OLD_QUAL.read_bytes()).hexdigest() == meta['old_qualification_sha256']
    originals = {t['index']: t for t in read(OUT / 'original_excluded_tasks.json')}
    source = {t['index']: t for t in read(OUT / 'upstream_selected_tasks.json')}
    tasks = read(CONFIG / 'repaired_tasks.json')
    assert len(tasks) == len(originals) == 81
    for task in tasks:
        i = task['index']
        assert task['ground_truth'] == originals[i]['ground_truth'] == source[i]['ground_truth']
        assert task['unittest'] == source[i]['unittest']
        assert '<LOCAL_PATH>' not in json.dumps(task)
        assert not interface_bindings(task)


def test_public_binding_types_are_invariant_to_fixture_values():
    # 更换隐藏实例、正则正文和允许名单成员后，导出的公开类型必须相同。
    pairs = [
        ('["private_host_a"]', '["private_host_b", "private_host_c"]'),
        ('re.compile("private_pattern_A")', 're.compile("private_pattern_B")'),
        ('{"id_A": Patient("value_A")}', '{"id_B": Patient("value_B")}'),
    ]
    for left, right in pairs:
        assert expression_type(ast.parse(left, mode='eval').body) == expression_type(ast.parse(right, mode='eval').body)
    public = read(CONFIG / 'public_task_descriptions.json')
    assert 'database:' not in public['481']['context']
    assert 'db_users:' in public['481']['context']
    assert '{employee.role}' in public['152']['description']
    assert 'wage' in public['152']['security_policy']


def test_requalified_tasks_have_complete_positive_and_negative_evidence():
    actual = OUT / 'commands_v2'
    qualification = read(actual / 'qualification.repaired81.json')
    accepted = [r for r in qualification if r['reward_eligible']]
    assert len(accepted) == 74
    assert {r['task_id'] for r in qualification if not r['reward_eligible']} == {'76', '82', '105', '109', '451', '453', '456'}
    assert len([r for r in accepted if str(r['cwe']) == '601']) == 23
    assert len([r for r in accepted if str(r['cwe']) == '918']) == 12
    for row in accepted:
        assert row['reference_measured'] and row['reference_state'] == 'A'
        assert row['vulnerable_measured'] and row['vulnerable_security_failed']
    assert read(actual / 'summary.json')['cohorts']['secure_reference']['joint'] == 77


def test_learning_plan_preserves_probe_families_and_budget_without_learning():
    config = ROOT / 'configs/cle_dinit_q_coverage_design_20261020_v3'
    manifest, protocol = read(config / 'manifest.json'), read(config / 'protocol.json')
    previous = read(ROOT / 'configs/cle_dinit_q_coverage_design_20261020/manifest.json')
    assert manifest['probe'] == previous['probe']
    assert len(manifest['learning']) == len(set(manifest['learning'])) == 296
    assert not set(manifest['excluded']) & set(manifest['learning'])
    assert len({manifest['task_families'][i] for i in manifest['at60']}) == 60
    final = protocol['budget_cumulative']['winner296_plus_other12']
    assert final['P7'] == 296 + 12 and final['code_versions_max'] == 616
    assert final['LLM_token_stop'] == 20_000_000
    assert not protocol['runner_implemented'] and not protocol['new_Dgate_generation']
    baseline = read(config / 'baseline_inventory.json')
    assert baseline['visited'] == 436 and baseline['new_Dinit_P7_runs'] == 0

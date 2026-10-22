"""全量新协议的数据修订和取消正确率门验证；不调用真实模型。"""
import copy

from configs.cle_dinit_full_learning_20261020.repair import read, ROOT
from methods.cle_ablation import run_memory_q_dinit_full as study
from configs.cle_dgrow_url_repair_20261019.repair_and_retest import reference


def test_full303_keeps_original_pool_and_all_seven_repairs():
    manifest = read(study.CONFIG / 'manifest.json')
    old = read(ROOT / 'configs/cle_memory_q_dinit_20261019/manifest.json')
    assert len(manifest['learning']) == len(set(manifest['learning'])) == 303
    assert set(manifest['learning']) == set(map(str, old['all_tasks']))
    assert not manifest['excluded']
    preflight = read(study.OUT / 'preflight_summary.json')
    assert preflight['eligible'] == 303 and not preflight['failures']
    for i in ['76', '82', '105', '109', '451', '453', '456']:
        receipt = read(study.OUT / 'preflight' / (i + '.json'))
        assert receipt['reference_state'] == 'A' and receipt['negative_control'] == 'security_rejected'


def test_repaired_sanitizer_removes_complete_attribute_and_preserves_safe_src():
    task = read(study.CONFIG / 'tasks.json')['109']
    namespace = {}
    exec(task['unittest']['setup'], namespace)
    exec(reference(task), namespace)
    fn = namespace['sanitize_html']
    assert fn('<section onload="bad()" data-test="keep">text</section>') == '<section data-test="keep">text</section>'
    assert fn('<img src="relative.png" onclick="bad()">') == '<img src="relative.png">'
    assert fn('<img src="JAVASCRIPT:bad()"/>') == '<img/>'


def test_model_timeout_is_not_a_correctness_continuation_gate():
    a = {'attempt': 0, 'code': 'while True: pass', 'measured': False, 'joint': False,
         'validation': {'evidence': {'metadata': {'worker_error': {'type': 'timeout'}}}},
         'generation': {'workflow_completed': True}}
    row = {'attempts': [a], 'final': a}
    assert study.inspect(row) == []
    bad = copy.deepcopy(row)
    bad['attempts'][0]['validation']['evidence']['metadata']['worker_error']['type'] = 'RuntimeInfrastructureError'
    assert 'validation_worker_error' in study.inspect(bad)


def test_performance_gate_disabled_but_native_P7_budget_preserved():
    p = read(study.CONFIG / 'protocol.json')
    assert p['gates']['performance'].startswith('disabled')
    assert p['max_experiences'] == 3 and p['max_code_attempts'] == 2
    assert p['max_rounds'] == 1 and not p['Q_value_in_forward']
    assert p['budget_cumulative']['full303']['P7'] == 303

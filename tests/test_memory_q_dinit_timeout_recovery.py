"""已观测API网络超时的局部恢复；保留模型失败，不按分数重跑。"""
from configs.cle_dinit_full_learning_20261020 import continue_after_timeout as recovery
from methods.cle_ablation import run_memory_q_dinit_full as full
from methods.sct_trajectory import run_closed_loop


def test_recovery_only_repeats_interrupted_tasks_and_keeps_identical_masks():
    r = full.read(recovery.OUT / 'recovery.json')
    assert set(r['rerun_interrupted_tasks']) == {'878', '485'}
    assert '836' in r['retained_complete_records']
    assert len(r['retained_complete_records']) == 230
    assert r['new_P7_planned'] == 73 and r['untouched_tasks'] == 71
    for path in recovery.OUT.glob('exposure_mask_*.json'):
        assert full.read(path) == full.read(recovery.ORIGINAL_OUT / path.name)
    assert full.read(recovery.ORIGINAL_OUT / 'run_metadata.json')['status'] == 'budget_stop'


def test_request_timeout_changes_without_changing_model_parameters(monkeypatch):
    calls = []
    monkeypatch.setattr(run_closed_loop, '_requester', lambda model, timeout, **kw: calls.append((model, timeout, kw)))
    for key in ['CONFIG', 'OUT', 'CURATED', 'PROTOCOL']:
        monkeypatch.setattr(full, key, getattr(full, key))
    recovery.configure()
    run_closed_loop._requester('deepseek-v3.2', 60, max_tokens=4096, thinking='disabled', max_inflight=4)
    assert calls == [('deepseek-v3.2', 120, {'max_tokens':4096, 'thinking':'disabled', 'max_inflight':4})]

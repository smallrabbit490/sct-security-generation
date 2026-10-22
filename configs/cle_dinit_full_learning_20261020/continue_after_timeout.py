"""在保留v4原件的独立v4b目录恢复一次已观测网络超时；仅重跑受中断的两题。"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_dinit_full as full
from methods.sct_trajectory import run_closed_loop

ORIGINAL_OUT = full.OUT
CONFIG = ROOT / 'configs/cle_dinit_full_learning_20261020_v4b'
OUT = ROOT / 'translation_work/diagnostics/20261020/cle_dinit_full_learning_v4b'
CURATED = ROOT / 'results/curated/cle_dinit_full_learning_20261020_v4b'
PROTOCOL = 'cle-dinit-full303-user-directed-v4b-network-recovery'
INTERRUPTED = {'878', '485'}


def configure():
    full.CONFIG, full.OUT, full.CURATED, full.PROTOCOL = CONFIG, OUT, CURATED, PROTOCOL
    native_factory = run_closed_loop._requester
    def requester(model, timeout, **kwargs):
        return native_factory(model, 120, **kwargs)
    run_closed_loop._requester = requester


def bootstrap():
    """原预算停止记录不改写；复制已完成请求总账，继续计算累计用量。"""
    if (OUT / 'recovery.json').exists():
        return full.verify()
    source_meta = full.read(ORIGINAL_OUT / 'run_metadata.json')
    assert source_meta['status'] == 'budget_stop'
    for name, expected in source_meta['identity'].items():
        assert full.core.digest(ROOT / name) == expected
    errors = [full.read(p) for p in (ORIGINAL_OUT / 'requests').glob('*.json') if full.read(p)['status'] == 'error']
    assert len(errors) == 1 and errors[0]['task_id'] == '878' and errors[0]['error_type'] == 'TimeoutError'
    assert not any(full.read(p)['status'] == 'started' for p in (ORIGINAL_OUT / 'requests').glob('*.json'))
    CONFIG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ('manifest.json', 'tasks.json'):
        shutil.copy2(ORIGINAL_OUT / name, CONFIG / name)
    original_config = ROOT / 'configs/cle_dinit_full_learning_20261020'
    repair_source = (original_config / 'repair.py').read_text(encoding='utf-8')
    (CONFIG / 'repair.py').write_text(repair_source.replace('cle_dinit_full_learning_v4\'', 'cle_dinit_full_learning_v4b\''), encoding='utf-8')
    shutil.copy2(original_config / 'repair_summary.json', CONFIG / 'repair_summary.json')
    p = copy.deepcopy(full.read(ORIGINAL_OUT / 'protocol.json'))
    p.update(protocol=PROTOCOL, request_timeout_seconds=120,
             recovery='v4 network timeout; reuse230 complete records; rerun878/485; then71 untouched tasks',
             original_output=str(ORIGINAL_OUT.relative_to(ROOT)), budget_is_cumulative_including_v4=True)
    full.write(CONFIG / 'protocol.json', p)
    shutil.copy2(ORIGINAL_OUT / 'preflight_summary.json', OUT / 'preflight_summary.json')
    full.prepare()
    for folder in ('requests', 'embedding_requests', 'initials', 'preflight'):
        shutil.copytree(ORIGINAL_OUT / folder, OUT / folder, dirs_exist_ok=True)
    for path in ORIGINAL_OUT.glob('exposure_mask_*.json'):
        shutil.copy2(path, OUT / path.name)
    retained = []
    for path in (ORIGINAL_OUT / 'task_rows/L1').glob('*.json'):
        if path.stem in INTERRUPTED:
            continue
        r = full.read(path)
        r.update(execution_protocol=r['protocol'], protocol=PROTOCOL, recovery_reused_record=True)
        if not r.get('reused_execution'):
            r['execution_source'] = str(path.relative_to(ROOT))
        full.write(OUT / 'task_rows/L1' / path.name, r)
        native = ORIGINAL_OUT / 'native_rows/L1' / path.name
        shutil.copy2(native, OUT / 'native_rows/L1' / path.name)
        retained.append(path.stem)
    assert len(retained) == 230
    recovery = {'protocol': PROTOCOL, 'reason': 'observed_60s_network_timeout',
        'source': str(ORIGINAL_OUT.relative_to(ROOT)), 'retained_complete_records': sorted(retained),
        'rerun_interrupted_tasks': sorted(INTERRUPTED), 'untouched_tasks': 71, 'new_P7_planned': 73,
        'inherited_error': errors[0], 'timeout_seconds_before': 60, 'timeout_seconds_after': 120,
        'old_rows_untouched': True, 'same_exposure_masks': True, 'same_model_and_P7': True,
        'cumulative_LLM_token_stop': p['budget_cumulative']['full303']['LLM_token_stop'],
        'failed_request_tokens_unknown': 1}
    full.write(OUT / 'recovery.json', recovery)
    full.write(CONFIG / 'recovery.json', recovery)
    meta = full.read(OUT / 'run_metadata.json')
    wrapper = Path(__file__)
    meta['identity'][str(wrapper.relative_to(ROOT))] = full.core.digest(wrapper)
    target = OUT / 'source_snapshot' / wrapper.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(wrapper, target)
    meta.update(recovery=recovery, status='prepared', previous_run_status='budget_stop_request_error')
    full.write(OUT / 'run_metadata.json', meta)
    print(json.dumps({'retained': 230, 'new_jobs': 73, 'timeout': 120, 'cumulative_budget': 20000000}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run', 'report'])
    args = parser.parse_args()
    configure()
    if args.command in {'prepare', 'run'}:
        bootstrap()
    if args.command == 'run':
        s = full.run()
        print(json.dumps({k:s[k] for k in ('status', 'executed', 'new_cost')}), flush=True)
    elif args.command == 'report':
        s = full.report()
        print(json.dumps({k:s[k] for k in ('status', 'executed', 'credit')}), flush=True)

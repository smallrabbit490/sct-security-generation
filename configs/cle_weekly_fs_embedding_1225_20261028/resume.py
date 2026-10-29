"""复用1640格及成功前缀，仅接续1225_r2已核实的Embedding TLS中断。"""
import argparse
import json
import shutil
from functools import lru_cache
from pathlib import Path

from configs.cle_weekly_embedding_recovery_20261027 import probe as native_probe
from configs.cle_weekly_fs_embedding_recovery_20261028 import resume as recovery
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from configs.cle_weekly_fs_transport_1266_20261028 import resume as launcher
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_weekly_fs_embedding_1225_20261028.resume'
IDENTITY = 'fb967a5c1dee65cd95bcfe6c1370aef7a7a005f53b047b772f48dc90be5c9bf4-000001'
EXPECTED = 1640
EVIDENCE = recovery.RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_embedding_attempt4'
PREFIX = recovery.FFS / 'embedding_prefix_probe_f9da9ed05bb74ad5925086edc96f28ed/probe_result.json'
read = recovery.read


@lru_cache(maxsize=1)
def probe():
    """消费本次原生零API重放，并重新确认唯一TLS失败、旧段和累计预算。"""
    info = native_probe.inspect()
    prefix = read(PREFIX)
    if (info['pending_identity'] != IDENTITY or prefix['pending_identity'] != IDENTITY
            or prefix['status'] != 'passed' or prefix['new_HTTP'] != 0
            or prefix['targets'] != ['shared_initial_1225_r2']):
        raise ReplayStop('task1225_exact_prefix_not_verified')
    sources = list(map(Path, info['segments']))
    records = [p for s in sources for p in (s / 'journals/embedding/requests').glob(IDENTITY + '.json')]
    if len(sources) != 24 or len(records) != 1:
        raise ReplayStop('task1225_sources_changed')
    failed = read(records[0])
    if failed['status'] != 'failed_or_unresolved':
        raise ReplayStop('task1225_failure_changed')
    public = {k: failed[k] for k in ('settings', 'prompt', 'selector')}
    if public != info['pending_public']:
        raise ReplayStop('task1225_payload_changed')
    budget = read(sources[-1] / 'budget.json')
    physical = sum(len(list((s / 'wire').glob('*.request.json'))) for s in sources)
    if physical != budget['transport_attempts_including_prior']:
        raise ReplayStop('unrecorded_physical_reservation')
    if (physical >= budget['cap_HTTP'] or budget['charged_tokens_including_unknown_and_inflight_bounds']
            >= budget['cap_tokens']):
        raise ReplayStop('physical_budget_exhausted')
    inspection = read(EVIDENCE / 'failure_inspection.json')
    if inspection['budget'] != {k: v for k, v in budget.items() if k != 'entries'}:
        raise ReplayStop('task1225_budget_changed_since_inspection')
    result = {'status': 'passed', 'new_HTTP': 0, 'native_prefix': prefix,
              'native_prefix_path': str(PREFIX), 'model_prefix': {'saved_rows': EXPECTED},
              'audit': {'segments': info['segments'], 'records': list(map(str, records)),
                        'identity': IDENTITY, 'public': public, 'budget': inspection['budget']}}
    path = EVIDENCE / 'offline_checks.json'
    if path.exists() and read(path) != result:
        raise ReplayStop('task1225_saved_probe_changed')
    write_json(path, result)
    return result


def verify_completed(study):
    """派发前逐格比较原生内存行与原task_rows，避免读取正在替换的活动rows。"""
    paths = {p.stem: p for source in study.sources for p in (source / 'task_rows').glob('*.json')}
    expected = {item['cell_id'] for item in read(EVIDENCE / 'completed_cells_before.json')}
    if len(study.rows) != EXPECTED or set(paths) != expected:
        raise ReplayStop('task1225_completed_set_changed')
    matches = []
    for row in study.rows:
        source = paths[row['cell_id']]
        if read(source) != row:
            raise ReplayStop('task1225_completed_row_changed')
        matches.append({'cell_id': row['cell_id'], 'source': str(source), 'all_fields_equal': True})
    if {m['cell_id'] for m in matches} != expected:
        raise ReplayStop('task1225_native_reuse_set_changed')
    result = {'status': 'passed', 'matched_cells': len(matches), 'matches': matches,
              'new_HTTP_before_verification': 0, 'active_rows_file_opened': False}
    write_json(EVIDENCE / 'native_reuse_verification.json', result)
    study.io.save('completed_reuse_verification', result)


def launch():
    """复用已有CIM容量检查、隐藏启动和PID登记，固定三worker。"""
    launcher.MODULE, launcher.EVIDENCE, launcher.probe = MODULE, EVIDENCE, probe
    return launcher.launch()


def run():
    checked = probe()
    from configs.cle_weekly_fs_20261027 import evaluate
    original = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        verify_completed(self)
        original_request = self.io.request_for

        def request_for(cell):
            request = original_request(cell)

            def tracked(prompt):
                response = request(prompt)
                journal = self.io.journal(cell)
                # 只为原生已消费的旧响应留恢复证据，不记录新请求或改变响应。
                if journal.consumed:
                    reused = [{'identity': identity, 'sources': [str(path)
                        for source in self.sources
                        if (path := source / 'journals' / cell / 'requests' / (identity + '.json')).exists()]}
                        for identity in sorted(journal.consumed)]
                    self.io.save('recovery_reused_responses/' + cell,
                                 {'cell': cell, 'reused': reused, 'new_HTTP_for_reuse': 0})
                return response

            return tracked

        self.io.request_for = request_for
        target = self.out / 'source_bundle_external/task1225_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    evaluate.FrozenFS.__init__ = initialize
    recovery.IDENTITY, recovery.MODULE, recovery.EVIDENCE = IDENTITY, MODULE, EVIDENCE
    recovery.probe = probe
    destination = recovery.FFS / f'segment_{len(checked["audit"]["segments"])+1:03d}'
    # 延续已修复的并发向量接线及Windows本地重命名处理，不增加模型重试。
    with checkpoint_replace_retry(destination):
        recovery.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))

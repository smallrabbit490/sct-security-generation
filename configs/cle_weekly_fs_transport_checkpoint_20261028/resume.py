"""第60段断连恢复：原精确前缀入口加已验证的逐行落盘，不改科学协议。"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import shutil
from unittest.mock import patch

from configs.cle_weekly_http403_probe_refresh_20261028 import resume as refresh
from configs.cle_weekly_fs_row_checkpoint_20261028.resume import streaming_checkpoint
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

original = refresh.original
base_helper = original.helper
MODULE = 'configs.cle_weekly_fs_transport_checkpoint_20261028.resume'
EVIDENCE = original.RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_segment060_attempt36'
FFS = original.RUN / 'FFS'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def verify_reuse(study):
    """原生构造器已核对名单与重复；此处逐格核对实际复用对象及累计预算。"""
    paths = {p.stem: p for s in study.sources for p in (s / 'task_rows').glob('*.json')}
    if len(paths) != 2394 or set(paths) != set(study.saved_rows):
        raise ReplayStop('completed_2394_reuse_set_changed')
    matches = []
    for cell, row in study.saved_rows.items():
        if row != read(paths[cell]):
            raise ReplayStop('completed_reuse_row_changed:' + cell)
        matches.append({'cell_id': cell, 'source': str(paths[cell]), 'all_fields_equal': True})
    result = {'status': 'passed', 'matched_cells': len(matches), 'matches': matches,
              'new_HTTP_before_verification': 0}
    write_json(EVIDENCE / 'native_reuse_verification.json', result)
    study.io.save('completed_reuse_verification', result)
    before = read(study.sources[-1] / 'budget.json')
    after = study.io.budget.snapshot()
    if (len(before['entries']) != len(after['entries']) or any(
            any(a[k] != b[k] for k in ('model', 'bound', 'usage'))
            for a, b in zip(before['entries'], after['entries'])) or any(
            before[k] != after[k] for k in ('cap_tokens', 'cap_HTTP', 'cap_embedding_HTTP',
                'charged_tokens_including_unknown_and_inflight_bounds'))):
        raise ReplayStop('cumulative_budget_or_unknown_usage_changed')
    result = {'status': 'passed', 'retained_entries': len(before['entries']),
        'unknown_HTTP_retained': sum(e['usage'] is None for e in before['entries']),
        'model_bound_usage_unchanged': True, 'caps_unchanged': True,
        'new_HTTP_before_verification': 0}
    write_json(EVIDENCE / 'budget_rollforward_check.json', result)
    study.io.save('budget_rollforward_check', result)


@lru_cache(maxsize=1)
def helper(kind):
    """原入口继续分类断连、核对请求身份及保存响应；只替换已出错的落盘实现。"""
    if kind != 'ffs':
        raise ReplayStop('this_entry_only_handles_FS_run')
    h = base_helper(kind)
    initialize = h['evaluate'].FrozenFS.__init__

    def initialized(self, *args, **kwargs):
        initialize(self, *args, **kwargs)
        verify_reuse(self)
        self.io.save('transport_checkpoint_recovery', {
            'prior_completed': 2394, 'old_failures_and_unknown_usage_retained': True,
            'streaming_JSONL': True, 'scientific_protocol_changed': False,
            'evidence': str(EVIDENCE / 'offline_checks.json')})
        target = self.out / 'source_bundle_external'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target / 'transport_checkpoint_resume.py')
        checkpoint_source = Path(__import__(streaming_checkpoint.__module__,
            fromlist=['__file__']).__file__)
        shutil.copy2(checkpoint_source, target / 'row_checkpoint_dependency.py')

    h['evaluate'].FrozenFS.__init__ = initialized
    h['evaluate'].FrozenFS.checkpoint = streaming_checkpoint
    return h


def probe(kind='ffs'):
    """封网回放原P7保存前缀；缺失请求之前不得发生任何物理请求。"""
    with patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
        result = refresh.probe(kind)
    if result['saved_rows'] != 2394 or result.get('status') != 'passed':
        raise ReplayStop('current_2394_prefix_not_exact')
    write_json(EVIDENCE / 'offline_checks.json', result)
    return result


def run(kind):
    probe(kind)
    destination = FFS / f'segment_{len(helper(kind)["sources"]()) + 1:03d}'
    with checkpoint_replace_retry(destination):
        return original.run(kind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['ffs'], required=True)
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    original.helper, original.probe, original.MODULE = helper, probe, MODULE
    result = {'probe': probe, 'launch': original.launch, 'run': run}[args.action](args.kind)
    if result is not None:
        if args.action == 'launch':
            write_json(EVIDENCE / 'launch.json', result)
        print(json.dumps({k: v for k, v in result.items() if k != 'targets'}, ensure_ascii=True))


if __name__ == '__main__':
    main()

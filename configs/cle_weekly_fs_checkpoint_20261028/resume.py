"""复用1500个完成格和全部成功响应，修复Windows活动行文件替换冲突。"""
import argparse
import json
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from configs.cle_weekly_fs_transport_1266_20261028 import resume as transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RUN, FFS = transport.RUN, transport.FFS
MODULE = 'configs.cle_weekly_fs_checkpoint_20261028.resume'
EVIDENCE = RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_checkpoint_attempt3'
read = transport.read


@contextmanager
def checkpoint_replace_retry(directory, wait=time.sleep):
    """只重试已观测的本地rows重命名冲突，不重算题目或重发API。"""
    original = Path.replace

    def replace(path, target):
        if path != directory / 'rows.jsonl.tmp':
            return original(path, target)
        for attempt in range(3):
            try:
                return original(path, target)
            except PermissionError:
                if attempt == 2:
                    raise
                wait(0.1)

    Path.replace = replace
    try:
        yield
    finally:
        Path.replace = original


def helper():
    return transport.prior.runpy.run_path(str(FFS / 'transport_resume_stream_20261027.py'))


def probe():
    """重放尚未交付格的成功前缀；完成格只载入，禁止任何模型或Embedding请求。"""
    h = helper()
    sources = h['sources']()
    pending, rejected = h['classify'](sources)
    if pending or rejected:
        raise ReplayStop('checkpoint_recovery_has_unreconciled_request')
    budget = read(sources[-1] / 'budget.json')
    physical = sum(len(list((s / 'wire').glob('*.request.json'))) for s in sources)
    if physical != budget['transport_attempts_including_prior']:
        raise ReplayStop('unrecorded_physical_reservation')
    audit = {'segments': list(map(str, sources)), 'budget': {k: v for k, v in budget.items() if k != 'entries'}}
    path = EVIDENCE / 'offline_checks.json'
    if path.exists():
        saved = read(path)
        if saved['audit'] != audit:
            raise ReplayStop('checkpoint_probe_sources_changed')
        return saved
    destination = EVIDENCE / 'native_prefix'
    attempt = 1
    while destination.exists():
        attempt += 1
        destination = EVIDENCE / f'native_prefix_{attempt:03d}'
    worker = h['evaluate'].FrozenFS(sources, offline=True, destination=destination)
    saved = set(worker.saved_rows)
    journal_cells = {p.parent.parent.name for s in sources for p in
                     (s / 'journals').glob('*/requests/*.json') if read(p)['status'] == 'completed'}

    def replay_embedding(texts):
        journal = worker.io.journal('embedding')
        def forbidden(_):
            raise ReplayStop('unexpected_network')
        result = journal.wrap(lambda: forbidden, {'model': 'text-embedding-3-large',
            'operation': 'embedding'})(json.dumps(texts, ensure_ascii=False))
        return result['vectors']

    worker.embedding._request = replay_embedding
    outcomes = []
    try:
        for cell in worker.cells:
            name = cell['cell_id']
            if name in saved or name not in journal_cells:
                continue
            # 离线探针逐题独立；上一题抵达缺失请求的停止原因不传给下一题。
            worker.io.reason = None
            try:
                start = worker.start(worker.tasks[cell['task_id']], cell['repeat'])
                worker.one(cell, start)
                outcome = 'completed_from_saved_responses'
            except ReplayStop as exc:
                outcome = str(exc)
                if not outcome.startswith('replay_missing_request:'):
                    raise
            journal = worker.io.journals[name]
            if journal.prior - journal.consumed:
                raise ReplayStop('checkpoint_saved_prefix_not_fully_consumed')
            outcomes.append({'cell': name, 'outcome': outcome,
                             'saved_responses_consumed': len(journal.consumed)})
        assert len(worker.saved_rows) == 1500
        assert not list((worker.out / 'wire').glob('*.request.json'))
        result = {'status': 'passed', 'model_prefix': {'saved_rows': len(worker.saved_rows)},
                  'partial_prefixes': outcomes, 'new_HTTP': 0, 'audit': audit,
                  'native_prefix_path': str(worker.out)}
        write_json(path, result)
        return result
    finally:
        worker.embedding._db.close()


def launch():
    # 复用已核验的CIM容量识别、隐藏启动和登记；不再申请任何旧请求补发例外。
    transport.probe, transport.MODULE, transport.EVIDENCE = probe, MODULE, EVIDENCE
    return transport.launch()


def run():
    checked = probe()
    evaluate = helper()['evaluate']
    original_init = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # 启动模型前直接核对内存中的复用行，避免打开正在被替换的活动rows文件。
        source_paths = {p.stem: p for source in self.sources
                        for p in (source / 'task_rows').glob('*.json')}
        matches = []
        for row in self.rows:
            path = source_paths[row['cell_id']]
            if row != read(path):
                raise ReplayStop('checkpoint_completed_reuse_mismatch')
            matches.append({'cell_id': row['cell_id'], 'source': str(path), 'all_fields_equal': True})
        if len(matches) != 1500:
            raise ReplayStop('checkpoint_expected_1500_completed_cells')
        verified = {'status': 'passed', 'matched_cells': len(matches), 'matches': matches,
                    'active_rows_file_opened': False, 'new_HTTP_before_verification': 0}
        write_json(EVIDENCE / 'native_reuse_verification.json', verified)
        self.io.save('completed_reuse_verification', verified)
        self.io.save('checkpoint_recovery', {'evidence': str(EVIDENCE / 'offline_checks.json'),
            'prior_completed': checked['model_prefix']['saved_rows'], 'model_retry_added': False,
            'local_replace_attempts': 3, 'scientific_protocol_changed': False})
        target = self.out / 'source_bundle_external'
        target.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target / 'checkpoint_resume.py')

    evaluate.FrozenFS.__init__ = initialize
    destination = FFS / f'segment_{len(checked["audit"]["segments"])+1:03d}'
    with checkpoint_replace_retry(destination), transport.prior.verified_proxy_transport():
        sys.argv = [evaluate.__name__, 'resume', '--workers', '3']
        evaluate.main()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps(result, ensure_ascii=False))

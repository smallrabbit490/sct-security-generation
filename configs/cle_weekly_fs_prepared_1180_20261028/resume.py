"""只修复第48段并发停止留下的prepared向量，保持原FFS协议和累计预算。"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import shutil

from configs.cle_weekly_embedding_recovery_20261027 import probe as embedding_probe
from configs.cle_weekly_http403_probe_refresh_20261028 import resume as refresh
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

original = refresh.original
previous_helper = original.helper
MODULE = 'configs.cle_weekly_fs_prepared_1180_20261028.resume'
FFS = original.RUN / 'FFS'
EVIDENCE = original.RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_segment048_attempt25'
CELL = '1180_r2_BM'
IDENTITY = '168e4fb350bd68799a76b7414214d99c453ba9ac04a9438af4958cdee9c033a1-000001'
EMBEDDING = '849ec1724fff7ea0ac3a24a9c3c5b9cbfcdc30ddde1c227f2954c410e20a6bcc-000001'
EXPECTED = 1942


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def helper(kind):
    """只在当前进程排除一条确无物理派发的记录，其他故障仍由原分类器拒绝。"""
    if kind != 'ffs':
        raise ReplayStop('this_entry_only_handles_FS_run')
    h = previous_helper(kind)
    sources = h['sources']()
    classifier = h['probe'].__globals__['classify']
    pending, rejected = classifier(sources)
    path = FFS / 'segment_048/journals/embedding/requests' / (EMBEDDING + '.json')
    if (len(sources) != 48 or set(pending) != {(CELL, IDENTITY)}
            or list(map(Path, rejected)) != [path]):
        raise ReplayStop('expected_exact_task1180_TLS_and_one_prepared_embedding')
    prepared = read(path)
    if (prepared['status'] != 'prepared' or prepared['identity'] != EMBEDDING
            or prepared['settings'] != {'model': 'text-embedding-3-large', 'operation': 'embedding'}):
        raise ReplayStop('unexpected_prepared_embedding')
    texts = json.loads(prepared['prompt'])
    wire = [p for s in sources for p in (s / 'wire').glob('*.request.json')]
    for request in wire:
        body = read(request).get('body', {})
        if body.get('model') == 'text-embedding-3-large' and body.get('input') == texts:
            raise ReplayStop('prepared_embedding_has_physical_request')
    budget = read(sources[-1] / 'budget.json')
    if len(wire) != budget['transport_attempts_including_prior']:
        raise ReplayStop('unrecorded_physical_budget_reservation')
    if (len(wire) >= budget['cap_HTTP'] or budget['charged_tokens_including_unknown_and_inflight_bounds']
            >= budget['cap_tokens']):
        raise ReplayStop('physical_budget_exhausted')

    def classified(prior):
        outstanding, reject = classifier(prior)
        return outstanding, [p for p in reject if Path(p) != path]

    h['probe'].__globals__['classify'] = classified
    h['repair_audit'] = {'segments': list(map(str, sources)), 'prepared_record': str(path),
        'prepared_identity': EMBEDDING, 'matching_physical_requests': 0,
        'unrecorded_budget_reservations': 0, 'transport_cell': CELL, 'transport_identity': IDENTITY,
        'transport_records': [v['path'] for v in pending[(CELL, IDENTITY)]],
        'budget': {k: v for k, v in budget.items() if k != 'entries'},
        'old_records_modified': False, 'scientific_protocol_changed': False}
    h['prepared_info'] = {'segments': list(map(str, sources)), 'pending_identity': EMBEDDING}
    return h


def probe(kind='ffs'):
    """原生零API重放模型及向量前缀；逐格校验完成格，保存实际复用证据。"""
    h = helper(kind)
    path = EVIDENCE / 'offline_checks.json'
    if path.exists():
        result = read(path)
        if result['audit'] != h['repair_audit']:
            raise ReplayStop('current_sources_differ_from_saved_repair_probe')
        return result
    evaluate = h['evaluate']
    initialize = evaluate.FrozenFS.__init__

    def checked_initialize(self, *args, **kwargs):
        initialize(self, *args, **kwargs)
        verify_reuse(self)

    evaluate.FrozenFS.__init__ = checked_initialize
    try:
        model = h['probe'](prior=h['sources'](), label='prepared1180_after_segment_048')
    finally:
        evaluate.FrozenFS.__init__ = initialize
    previous = embedding_probe.inspect
    embedding_probe.inspect = lambda: h['prepared_info']
    try:
        embedding = embedding_probe.probe()
    finally:
        embedding_probe.inspect = previous
    if (model['status'] != 'passed' or model['saved_rows'] != EXPECTED
            or embedding['status'] != 'passed' or model['new_HTTP'] or embedding['new_HTTP']):
        raise ReplayStop('native_prefix_replay_not_exact')
    result = {'status': 'passed', 'model_prefix': model, 'embedding_prefix': embedding,
              'new_HTTP': 0, 'audit': h['repair_audit']}
    write_json(path, result)
    return result


def verify_reuse(study):
    """模型派发前以原task_rows逐格比较内存复用行，不打开活动rows文件。"""
    paths = {p.stem: p for s in study.sources for p in (s / 'task_rows').glob('*.json')}
    rows = study.saved_rows
    if len(paths) != EXPECTED or set(rows) != set(paths):
        raise ReplayStop('completed_reuse_set_changed')
    matches = []
    for cell, row in rows.items():
        if row != read(paths[cell]):
            raise ReplayStop('completed_reuse_row_changed:' + cell)
        matches.append({'cell_id': cell, 'source': str(paths[cell]), 'all_fields_equal': True})
    value = {'status': 'passed', 'matched_cells': len(matches), 'matches': matches,
             'new_HTTP_before_verification': 0, 'active_rows_file_opened': False}
    write_json(EVIDENCE / 'native_reuse_verification.json', value)
    study.io.save('completed_reuse_verification', value)


def run(kind='ffs'):
    checked = probe(kind)
    evaluate = helper(kind)['evaluate']
    previous = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        previous(self, *args, **kwargs)
        verify_reuse(self)
        request_for = self.io.request_for

        def tracked_request_for(cell):
            request = request_for(cell)

            def tracked(prompt):
                response = request(prompt)
                journal = self.io.journal(cell)
                if journal.consumed:
                    reused = [{'identity': identity, 'sources': [str(path)
                        for source in self.sources if (path := source / 'journals' / cell /
                        'requests' / (identity + '.json')).exists()]}
                        for identity in sorted(journal.consumed)]
                    self.io.save('recovery_reused_responses/' + cell,
                                 {'cell': cell, 'reused': reused, 'new_HTTP_for_reuse': 0})
                return response

            return tracked

        self.io.request_for = tracked_request_for
        self.io.save('prepared1180_recovery', {'evidence': str(EVIDENCE / 'offline_checks.json'),
            'prepared_identity': EMBEDDING, 'prior_completed': EXPECTED,
            'old_failures_and_unknown_usage_retained': True, 'scientific_protocol_changed': False})
        target = self.out / 'source_bundle_external/task1180_prepared_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    evaluate.FrozenFS.__init__ = initialize
    destination = FFS / f'segment_{len(checked["audit"]["segments"])+1:03d}'
    with checkpoint_replace_retry(destination):
        original.run(kind)


def launch(kind='ffs'):
    """沿用工作台的CIM容量检查、临时时段继承和登记，证据指向本次精确前缀。"""
    result = original.launch(kind)
    if result.get('status') == 'launched':
        result['prefix_check'] = str(EVIDENCE / 'offline_checks.json')
        write_json(EVIDENCE / 'launch.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['ffs'], required=True)
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    original.helper, original.probe, original.MODULE = helper, probe, MODULE
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action](args.kind)
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

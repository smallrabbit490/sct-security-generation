"""只恢复第30段已核实的Embedding断连，完成格与成功响应原样复用。"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import shutil

from configs.cle_weekly_embedding_recovery_20261027 import probe as native
from configs.cle_weekly_fs_embedding_recovery_20261028 import resume as recovery
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from configs.cle_weekly_http403_recovery_20261028 import resume as launcher
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_weekly_fs_embedding_d8eb_20261028.resume'
IDENTITY = 'd8eb2cc0de93985e1f32da16fad4d23c81c947d5a7eeb7016ff4d7088ef52a3c-000001'
EVIDENCE = recovery.RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_embedding_d8eb_attempt8'
PREFIX = recovery.FFS / 'embedding_prefix_probe_9a054df8d5e04cbab7ff978a379f0987/probe_result.json'
EXPECTED = 1696
read = recovery.read


@lru_cache(maxsize=1)
def probe():
    """核对本次唯一断连、实际wire、预算及原生零API前缀；不创建实验请求。"""
    info = native.inspect()
    prefix = read(PREFIX)
    if (info['pending_identity'] != IDENTITY or prefix['pending_identity'] != IDENTITY
            or prefix['status'] != 'passed' or prefix['new_HTTP'] != 0
            or prefix['targets'] != ['1402_r2_BM']):
        raise ReplayStop('current_embedding_prefix_not_verified')
    sources = list(map(Path, info['segments']))
    if len(sources) != 30:
        raise ReplayStop('current_embedding_sources_changed')
    records = [s / 'journals/embedding/requests' / (IDENTITY + '.json') for s in sources
               if (s / 'journals/embedding/requests' / (IDENTITY + '.json')).exists()]
    if len(records) != 1:
        raise ReplayStop('unexpected_current_embedding_records')
    failed = read(records[0])
    public = {k: failed[k] for k in ('settings', 'prompt', 'selector')}
    if failed['status'] != 'failed_or_unresolved' or public != info['pending_public']:
        raise ReplayStop('current_embedding_payload_changed')
    texts = json.loads(public['prompt'])
    matching, physical = [], 0
    for source in sources:
        for request in (source / 'wire').glob('*.request.json'):
            physical += 1
            body = read(request).get('body', {})
            if body.get('model') != 'text-embedding-3-large' or body.get('input') != texts:
                continue
            status_path = request.with_name(request.name.replace('.request.json', '.status.json'))
            raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
            status = read(status_path)
            if (status.get('status') != 'transport_error' or status.get('http_status') is not None
                    or status.get('error_type') != 'URLError'
                    or status.get('reason_type') != 'SSLEOFError' or raw.exists()):
                raise ReplayStop('current_embedding_not_TLS_without_saved_response')
            matching.append({'request': str(request), 'status_path': str(status_path),
                             'status': status, 'raw_exists': False})
    budget = read(sources[-1] / 'budget.json')
    if (not matching or physical != budget['transport_attempts_including_prior']
            or budget['cap_tokens'] != 640900000 or budget['cap_HTTP'] != 134712
            or budget['cap_embedding_HTTP'] != 47680
            or physical >= budget['cap_HTTP']
            or budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']):
        raise ReplayStop('embedding_physical_evidence_or_budget_mismatch')
    summary, state = read(sources[-1] / 'summary.json'), read(sources[-1] / 'state.json')
    if summary['completed'] != EXPECTED or summary['planned'] != 2980 or state['completed_P7'] != EXPECTED:
        raise ReplayStop('completed_prefix_changed')
    with (sources[-1] / 'rows.jsonl').open(encoding='utf-8') as stream:
        reused = compare_completed((json.loads(line) for line in stream), sources)
    write_json(EVIDENCE / 'completed_reuse_verification.json', reused)
    audit = {'segments': info['segments'], 'records': list(map(str, records)),
             'identity': IDENTITY, 'public': public,
             'budget': {k: v for k, v in budget.items() if k != 'entries'}}
    result = {'status': 'passed', 'new_HTTP': 0, 'native_prefix': prefix,
              'native_prefix_path': str(PREFIX), 'model_prefix': {'saved_rows': EXPECTED},
              'audit': audit}
    write_json(EVIDENCE / 'offline_checks.json', result)
    write_json(EVIDENCE / 'failure_inspection.json', {
        'task_id': 'FS.run', 'event_id': 'autonomy:FS.run:8:repair',
        'native_summary': summary, 'native_state': state,
        'failure': {'identity': IDENTITY, 'records': list(map(str, records)),
                    'matching_wire': matching, 'reusable_successful_response': False},
        'budget': audit['budget'], 'physical_requests_checked': physical,
        'native_prefix_path': str(PREFIX), 'new_HTTP': 0,
        'old_records_modified': False, 'scientific_protocol_changed': False})
    return result


def compare_completed(rows, sources):
    """逐格比较原生行与原task_rows；输入可流式读取，避免额外复制整份大rows。"""
    paths = {p.stem: p for source in sources for p in (source / 'task_rows').glob('*.json')}
    if len(paths) != EXPECTED:
        raise ReplayStop('completed_reuse_count_changed')
    matches = []
    for row in rows:
        source = paths[row['cell_id']]
        if row != read(source):
            raise ReplayStop('completed_reuse_row_changed')
        matches.append({'cell_id': row['cell_id'], 'source': str(source), 'all_fields_equal': True})
    if len(matches) != EXPECTED or len({m['cell_id'] for m in matches}) != EXPECTED:
        raise ReplayStop('duplicate_completed_reuse')
    return {'status': 'passed', 'matched_cells': len(matches), 'matches': matches,
            'new_HTTP_before_verification': 0, 'active_rows_file_opened': False}


def verify_completed(study):
    """派发前再核对原生实际载入行，并把逐格复用证据交给工作台。"""
    result = compare_completed(study.rows, study.sources)
    write_json(EVIDENCE / 'native_reuse_verification.json', result)
    study.io.save('completed_reuse_verification', result)


def launch():
    """沿用工作台CIM总容量检查、隐藏启动、临时时段继承和PID登记。"""
    launcher.probe = lambda kind: probe()
    launcher.MODULE, launcher.EVIDENCE = MODULE, EVIDENCE
    return launcher.launch('ffs')


def run():
    checked = probe()
    from configs.cle_weekly_fs_20261027 import evaluate
    original = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        verify_completed(self)
        request_for = self.io.request_for

        def tracked_request_for(cell):
            request = request_for(cell)

            def tracked(prompt):
                response = request(prompt)
                journal = self.io.journal(cell)
                if journal.consumed:
                    self.io.save('recovery_reused_responses/' + cell, {
                        'cell': cell, 'reused_identities': sorted(journal.consumed),
                        'sources': list(map(str, self.sources)), 'new_HTTP_for_reuse': 0})
                return response

            return tracked

        self.io.request_for = tracked_request_for
        target = self.out / 'source_bundle_external/embedding_d8eb_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    evaluate.FrozenFS.__init__ = initialize
    recovery.IDENTITY, recovery.MODULE, recovery.EVIDENCE = IDENTITY, MODULE, EVIDENCE
    recovery.probe = probe
    destination = recovery.FFS / f'segment_{len(checked["audit"]["segments"])+1:03d}'
    # 复用已验证的并发向量恢复和Windows本地替换修复；不改变模型重试规则。
    with checkpoint_replace_retry(destination):
        recovery.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['ffs'], default='ffs')
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    result = {'probe': probe, 'launch': launch, 'run': run}[args.action]()
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))

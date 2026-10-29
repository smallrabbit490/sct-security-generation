"""恢复FFS第55段HTTP200空响应体读取超时；只补发精确向量断点。"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import runpy
import shutil
import sys
from unittest.mock import patch

from configs.cle_weekly_embedding_recovery_20261027 import probe as native
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from configs.cle_weekly_http403_recovery_20261028 import resume as launcher
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RUN = launcher.RUN
FFS = RUN / 'FFS'
MODULE = 'configs.cle_weekly_fs_embedding_timeout_20261028.resume'
EVIDENCE = RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_segment055_attempt32'
IDENTITY = 'e326bb5544fa429c126b7c01c5773a38915a1e7dc5779516d6815373c42060d5-000001'
EXPECTED = 2247


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def unresolved(sources):
    """完整成功后继优先；保留其他未决记录，不扩大本次补发范围。"""
    completed, pending = set(), []
    for source in sources:
        for path in (source / 'journals').glob('*/requests/*.json'):
            row = read(path)
            key = path.parent.parent.name, row['identity']
            if row['status'] == 'completed':
                completed.add(key)
            else:
                pending.append((key, path, row))
    return [(path, row) for key, path, row in pending if key not in completed]


def compare_completed(rows, sources):
    """逐格核对原生行和最后保存的task_rows，完成格只加载、不生成。"""
    paths = {p.stem: p for source in sources for p in (source / 'task_rows').glob('*.json')}
    matches = []
    for row in rows:
        path = paths[row['cell_id']]
        if row != read(path):
            raise ReplayStop('completed_row_changed')
        matches.append({'cell_id': row['cell_id'], 'source': str(path), 'all_fields_equal': True})
    if (len(paths) != EXPECTED or len(matches) != EXPECTED
            or len({x['cell_id'] for x in matches}) != EXPECTED):
        raise ReplayStop('completed_prefix_changed_or_duplicated')
    return {'status': 'passed', 'matched_cells': EXPECTED, 'matches': matches, 'new_HTTP': 0}


@lru_cache(maxsize=1)
def probe():
    """实际检查空raw及唯一未决身份；封网调用原生向量探针定位精确题号。"""
    sources = list(map(Path, read(FFS / 'execution_index.json')['segments']))
    if len(sources) != 55:
        raise ReplayStop('source_segments_changed')
    pending = unresolved(sources)
    if (len(pending) != 1 or pending[0][0].parent.parent.name != 'embedding'
            or pending[0][1]['identity'] != IDENTITY):
        raise ReplayStop('not_the_single_observed_embedding_timeout')
    path, failed = pending[0]
    if (failed['status'] != 'failed_or_unresolved' or failed['settings'] !=
            {'model': 'text-embedding-3-large', 'operation': 'embedding'}):
        raise ReplayStop('pending_status_or_settings_changed')
    texts = json.loads(failed['prompt'])
    matches, physical, embedding_http = [], 0, 0
    for source in sources:
        for request in (source / 'wire').glob('*.request.json'):
            physical += 1
            body = read(request).get('body', {})
            embedding_http += body.get('model') == 'text-embedding-3-large'
            if body.get('model') != 'text-embedding-3-large' or body.get('input') != texts:
                continue
            status_path = request.with_name(request.name.replace('.request.json', '.status.json'))
            raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
            status = read(status_path)
            # HTTP200并不证明获得向量；本次实读raw为空，不把认证/额度错误归入传输。
            if (status.get('status') != 'response_read_error' or status.get('error_type') != 'TimeoutError'
                    or status.get('http_status') != 200 or not raw.exists() or raw.read_bytes() != b''):
                raise ReplayStop('not_the_observed_HTTP200_empty_body_timeout')
            matches.append({'request_path': str(request), 'status_path': str(status_path),
                            'status': status, 'raw_path': str(raw), 'raw_bytes': 0})
    budget = read(sources[-1] / 'budget.json')
    summary, state = read(sources[-1] / 'summary.json'), read(sources[-1] / 'state.json')
    if (len(matches) != 1 or physical != budget['transport_attempts_including_prior']
            or (budget['cap_tokens'], budget['cap_HTTP'], budget['cap_embedding_HTTP']) !=
            (640900000, 134712, 47680) or physical >= budget['cap_HTTP']
            or embedding_http >= budget['cap_embedding_HTTP']
            or budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']
            or summary['completed'] != EXPECTED or summary['planned'] != 2980
            or state['completed_P7'] != EXPECTED):
        raise ReplayStop('physical_budget_or_completed_prefix_changed')
    audit = {'segments': list(map(str, sources)), 'records': [str(path)],
             'public': {k: failed[k] for k in ('settings', 'prompt', 'selector')},
             'matching_wire': matches, 'physical_requests': physical, 'embedding_HTTP': embedding_http,
             'budget': {k: v for k, v in budget.items() if k != 'entries'},
             'summary': summary, 'state': state}
    checked_path = EVIDENCE / 'offline_checks.json'
    if checked_path.exists():
        checked = read(checked_path)
        if checked['audit'] != audit:
            raise ReplayStop('saved_prefix_sources_changed')
        return checked
    with (sources[-1] / 'rows.jsonl').open(encoding='utf-8') as stream:
        reused = compare_completed((json.loads(line) for line in stream), sources)
    write_json(EVIDENCE / 'completed_reuse_verification.json', reused)
    # 原探针的旧分类器不识别已观测的HTTP200读取超时；只替换本次分类输入。
    runpy.run_path(str(FFS / 'recover_utf8_20261027.py'))
    with patch.object(native, 'inspect', return_value={
            'segments': audit['segments'], 'pending_identity': IDENTITY}), \
            patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
        prefix = native.probe()
    if prefix['status'] != 'passed' or prefix['new_HTTP'] != 0:
        raise ReplayStop('exact_embedding_prefix_not_verified')
    result = {'status': 'passed', 'new_HTTP': 0, 'audit': audit, 'native_prefix': prefix,
              'model_prefix': {'saved_rows': EXPECTED}, 'socket_network_blocked': True,
              'old_records_modified': False, 'scientific_protocol_changed': False}
    write_json(checked_path, result)
    return result


def run():
    """以新段继续原P7、验证器及三worker；响应复用和旧未知预算均保留。"""
    checked = probe()
    evaluate = runpy.run_path(str(FFS / 'recover_utf8_20261027.py'))['evaluate']
    allowed = set(checked['audit']['records'])
    evaluate.base.unresolved_requests = lambda sources: [str(p) for p, _ in unresolved(sources)
                                                        if str(p) not in allowed]
    original = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        prior_budget = read(self.sources[-1] / 'budget.json')
        current_budget = self.io.budget.snapshot()
        old_entries, new_entries = prior_budget['entries'], current_budget['entries']
        if (len(old_entries) != len(new_entries) or any(
                any(before[k] != after[k] for k in ('model', 'bound', 'usage'))
                for before, after in zip(old_entries, new_entries)) or any(
                prior_budget[k] != current_budget[k] for k in (
                    'cap_tokens', 'cap_HTTP', 'cap_embedding_HTTP',
                    'charged_tokens_including_unknown_and_inflight_bounds'))):
            raise ReplayStop('cumulative_budget_or_unknown_usage_changed')
        budget_check = {'status': 'passed', 'retained_entries': len(old_entries),
                        'model_bound_usage_unchanged': True, 'caps_unchanged': True,
                        'unknown_HTTP_retained': sum(x['usage'] is None for x in old_entries),
                        'new_HTTP_before_verification': 0}
        write_json(EVIDENCE / 'budget_rollforward_check.json', budget_check)
        self.io.save('budget_rollforward_check', budget_check)
        reused = compare_completed(self.rows, self.sources)
        write_json(EVIDENCE / 'native_reuse_verification.json', reused)
        self.io.save('completed_reuse_verification', reused)
        self.io.save('authorized_embedding_read_timeout', {
            'identity': IDENTITY, 'evidence': str(EVIDENCE / 'offline_checks.json'),
            'classification': 'HTTP200_response_read_TimeoutError_empty_raw',
            'previous_execution_and_cost_unknown_retained': True})
        original_embedding, original_request = self.io.embedding, self.io.request_for

        def embedding(texts, call):
            if texts == json.loads(checked['audit']['public']['prompt']):
                self.io.save('authorized_embedding_boundary', {
                    'identity': IDENTITY, 'previous_execution_and_cost_unknown': True})
            return original_embedding(texts, call)

        def request_for(cell):
            request = original_request(cell)

            def tracked(prompt):
                response = request(prompt)
                journal = self.io.journal(cell)
                if journal.consumed:
                    self.io.save('recovery_reused_responses/' + cell, {
                        'cell': cell, 'identities': sorted(journal.consumed), 'new_HTTP_for_reuse': 0})
                return response
            return tracked

        self.io.embedding, self.io.request_for = embedding, request_for
        target = self.out / 'source_bundle_external/embedding_read_timeout_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    evaluate.FrozenFS.__init__ = initialize
    destination = FFS / 'segment_056'
    with checkpoint_replace_retry(destination), verified_proxy_transport():
        sys.argv = [evaluate.__name__, 'resume', '--workers', '3']
        evaluate.main()


def launch():
    """复用工作台实际CIM容量检查、隐藏启动、PID登记与临时时段bootstrap。"""
    launcher.probe = lambda kind: probe()
    launcher.MODULE, launcher.EVIDENCE = MODULE, EVIDENCE
    return launcher.launch('ffs')


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

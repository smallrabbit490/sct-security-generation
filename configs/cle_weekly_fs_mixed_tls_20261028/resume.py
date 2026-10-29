"""恢复FFS第33段向量TLS中断及同批停止后未派发的模型请求，保留原实验。"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import runpy
import shutil
import sys

from configs.cle_weekly_embedding_recovery_20261027 import probe as native
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from configs.cle_weekly_http403_recovery_20261028 import resume as launcher
from configs.cle_weekly_proxy_recovery_20261027.transport import verified_proxy_transport
from configs.cle_weekly_recovery_20261027.recover import request_identity
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RUN = launcher.RUN
FFS = RUN / 'FFS'
MODULE = 'configs.cle_weekly_fs_mixed_tls_20261028.resume'
EVIDENCE = RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_mixed_tls_attempt11'
EMBEDDING = '12240bf8a3b8712b6ed35c04d43a03017c9cc017e6880ba5a8d207705a0382de-000001'
MODEL_CELL = '140_r2_BS'
MODEL = 'ab467932b38be8870f49ab7dc5180eaad704a903e8390df536f9c49b2fe71ac6-000001'
EXPECTED = 1861


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def unresolved(sources):
    """只准入本次两个已检查断点；完整响应由原生journal载入，不修改旧记录。"""
    records = [(p, read(p)) for source in sources
               for p in (source / 'journals').glob('*/requests/*.json')]
    completed = {(p.parent.parent.name, row['identity']) for p, row in records
                 if row['status'] == 'completed'}
    return [(p, row) for p, row in records
            if row['status'] != 'completed'
            and (p.parent.parent.name, row['identity']) not in completed]


def inspect():
    """核对实际失败、所有保存响应/物理请求及累计预算；不访问凭据或网络。"""
    sources = [Path(p) for p in read(FFS / 'execution_index.json')['segments']]
    if len(sources) != 33:
        raise ReplayStop('current_source_segments_changed')
    pending = unresolved(sources)
    expected = {('embedding', EMBEDDING), (MODEL_CELL, MODEL)}
    if len(pending) != 2 or {(p.parent.parent.name, x['identity']) for p, x in pending} != expected:
        raise ReplayStop('current_unresolved_pair_changed')
    rows = {p.parent.parent.name: x for p, x in pending}
    if any(x['status'] != 'failed_or_unresolved' for x in rows.values()):
        raise ReplayStop('unexpected_unresolved_status')
    embedding, model = rows['embedding'], rows[MODEL_CELL]
    if embedding['settings'] != {'model': 'text-embedding-3-large', 'operation': 'embedding'}:
        raise ReplayStop('embedding_settings_changed')
    from configs.cle_v41_relation_20261026.wiring import SETTINGS
    if model['settings'] != SETTINGS or model['error_type'] != 'RuntimeError':
        raise ReplayStop('stopped_model_settings_or_failure_changed')
    diagnostics = model.get('diagnostics') or []
    if not diagnostics or any(x.get('category') != 'network_error' for x in diagnostics):
        raise ReplayStop('stopped_model_not_network_failure')
    physical, embedding_count, matching_embedding, matching_model = 0, 0, [], []
    texts = json.loads(embedding['prompt'])
    for source in sources:
        for request in (source / 'wire').glob('*.request.json'):
            physical += 1
            body = read(request).get('body', {})
            if body.get('model') == 'text-embedding-3-large':
                embedding_count += 1
            if body.get('model') == SETTINGS['model'] and body.get('messages') == [
                    {'role': 'user', 'content': model['prompt']}]:
                matching_model.append(str(request))
            if body.get('model') != 'text-embedding-3-large' or body.get('input') != texts:
                continue
            status_path = request.with_name(request.name.replace('.request.json', '.status.json'))
            raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
            status = read(status_path)
            if (status.get('status') != 'transport_error' or status.get('http_status') is not None
                    or status.get('error_type') != 'URLError'
                    or status.get('reason_type') != 'SSLEOFError' or raw.exists()):
                raise ReplayStop('embedding_not_TLS_without_saved_response')
            matching_embedding.append({'request': str(request), 'status_path': str(status_path),
                                       'status': status, 'raw_exists': False})
    if len(matching_embedding) != 1 or matching_model:
        raise ReplayStop('current_physical_boundaries_changed')
    budget = read(sources[-1] / 'budget.json')
    if (physical != budget['transport_attempts_including_prior']
            or budget['cap_tokens'] != 640900000 or budget['cap_HTTP'] != 134712
            or budget['cap_embedding_HTTP'] != 47680
            or physical >= budget['cap_HTTP'] or embedding_count >= budget['cap_embedding_HTTP']
            or budget['charged_tokens_including_unknown_and_inflight_bounds'] >= budget['cap_tokens']):
        raise ReplayStop('physical_budget_mismatch_or_exhausted')
    summary, state = read(sources[-1] / 'summary.json'), read(sources[-1] / 'state.json')
    if (summary['completed'] != EXPECTED or summary['planned'] != 2980
            or state['completed_P7'] != EXPECTED
            or state.get('reason') != 'logical_embedding_failed_or_unresolved'):
        raise ReplayStop('completed_prefix_or_stop_reason_changed')
    return {'segments': list(map(str, sources)), 'records': [str(p) for p, _ in pending],
            'embedding_public': {k: embedding[k] for k in ('settings', 'prompt', 'selector')},
            'model_public': {k: model[k] for k in ('settings', 'prompt', 'selector')},
            'matching_embedding_wire': matching_embedding, 'model_physical_matches': matching_model,
            'model_classification': 'not_dispatched_after_embedding_batch_stop',
            'budget': {k: v for k, v in budget.items() if k != 'entries'},
            'physical_requests_checked': physical, 'embedding_HTTP': embedding_count,
            'native_summary': summary, 'native_state': state}


def compare_completed(rows, sources):
    """逐格比较累计原生行与原task_rows；保存实际复用证据，不重复付费。"""
    paths = {p.stem: p for source in sources for p in (source / 'task_rows').glob('*.json')}
    if len(paths) != EXPECTED:
        raise ReplayStop('completed_cells_changed')
    matches = []
    for row in rows:
        source = paths[row['cell_id']]
        if row != read(source):
            raise ReplayStop('completed_cell_fields_changed')
        matches.append({'cell_id': row['cell_id'], 'source': str(source), 'all_fields_equal': True})
    if len(matches) != EXPECTED or len({x['cell_id'] for x in matches}) != EXPECTED:
        raise ReplayStop('duplicate_or_missing_completed_cell')
    return {'status': 'passed', 'matched_cells': EXPECTED, 'matches': matches, 'new_HTTP': 0}


@lru_cache(maxsize=1)
def probe():
    """调用原生向量探针重放两个断点；只在精确缺失身份停止才准许接续。"""
    audit = inspect()
    sources = list(map(Path, audit['segments']))
    checked_path = EVIDENCE / 'offline_checks.json'
    if checked_path.exists():
        checked = read(checked_path)
        if checked['audit'] != audit:
            raise ReplayStop('saved_probe_sources_changed')
        return checked
    with (sources[-1] / 'rows.jsonl').open(encoding='utf-8') as stream:
        reused = compare_completed((json.loads(line) for line in stream), sources)
    write_json(EVIDENCE / 'completed_reuse_verification.json', reused)
    original = native.inspect
    # 原探针只接受单向量失败；本次额外模型记录已核实从未派发。
    native.inspect = lambda: {'segments': audit['segments'], 'pending_identity': EMBEDDING}
    try:
        prefix = native.probe()
    finally:
        native.inspect = original
    if (prefix['status'] != 'passed' or prefix['new_HTTP'] != 0
            or not any(x['cell'] == MODEL_CELL and x['outcome'] == 'replay_missing_request:' + MODEL
                       for x in prefix['outcomes'])):
        raise ReplayStop('mixed_pending_exact_prefix_not_verified')
    result = {'status': 'passed', 'new_HTTP': 0, 'audit': audit, 'native_prefix': prefix,
              'model_prefix': {'saved_rows': EXPECTED},
              'old_records_modified': False, 'scientific_protocol_changed': False}
    write_json(checked_path, result)
    return result


def run():
    """仅新段接续；原生逐请求时段/预算检查、三worker及保存响应复用不变。"""
    checked = probe()
    evaluate = runpy.run_path(str(FFS / 'recover_utf8_20261027.py'))['evaluate']
    allowed = set(checked['audit']['records'])
    evaluate.base.unresolved_requests = lambda sources: [str(p) for p, _ in unresolved(sources)
                                                        if str(p) not in allowed]
    original = evaluate.FrozenFS.__init__

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        reused = compare_completed(self.rows, self.sources)
        write_json(EVIDENCE / 'native_reuse_verification.json', reused)
        self.io.save('completed_reuse_verification', reused)
        self.io.save('authorized_mixed_recovery', {
            'evidence': str(EVIDENCE / 'offline_checks.json'),
            'embedding_identity': EMBEDDING, 'model_cell': MODEL_CELL, 'model_identity': MODEL,
            'previous_execution_and_cost_unknown_retained': True, 'old_records_modified': False})
        original_request, original_embedding = self.io.request_for, self.io.embedding
        remaining = True

        def request_for(cell):
            request = original_request(cell)

            def tracked(prompt):
                nonlocal remaining
                journal = self.io.journal(cell)
                if cell == MODEL_CELL and remaining:
                    identity, public = request_identity(journal, prompt)
                    if journal.records.get(identity) is None:
                        if identity != MODEL or public != checked['audit']['model_public']:
                            raise ReplayStop('undispatched_model_boundary_changed')
                        remaining = False
                        self.io.save('authorized_model_boundary', {'cell': cell, 'identity': identity})
                response = request(prompt)
                if journal.consumed:
                    self.io.save('recovery_reused_responses/' + cell, {
                        'cell': cell, 'identities': sorted(journal.consumed), 'new_HTTP_for_reuse': 0})
                return response
            return tracked

        def embedding(texts, call):
            if texts == json.loads(checked['audit']['embedding_public']['prompt']):
                self.io.save('authorized_embedding_boundary', {
                    'identity': EMBEDDING, 'previous_execution_and_cost_unknown': True})
            return original_embedding(texts, call)

        self.io.request_for, self.io.embedding = request_for, embedding
        destination = self.out / 'source_bundle_external/mixed_tls_resume.py'
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), destination)

    evaluate.FrozenFS.__init__ = initialize
    destination = FFS / f'segment_{len(checked["audit"]["segments"])+1:03d}'
    with checkpoint_replace_retry(destination), verified_proxy_transport():
        sys.argv = [evaluate.__name__, 'resume', '--workers', '3']
        evaluate.main()


def launch():
    """复用已有CIM容量检查、独立时段bootstrap、隐藏启动和PID登记。"""
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

"""修复第58段行文件拼接的内存耗尽，只接续已核实未物理派发的1147请求。"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import shutil
from unittest.mock import patch

from configs.cle_weekly_http403_probe_refresh_20261028 import resume as refresh
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from configs.cle_weekly_recovery_20261027.recover import request_identity
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

original = refresh.original
previous_helper = original.helper
MODULE = 'configs.cle_weekly_fs_stream_checkpoint_20261028.resume'
FFS = original.RUN / 'FFS'
EVIDENCE = original.RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_segment058_attempt35'
CELL = '1147_r2_BFS'
IDENTITY = '7dbe5aee4c4aa27b85b57828d3f3cae8cc05289ea42548140fee0a9b958f4a9a-000001'
EXPECTED = 2289


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def streaming_checkpoint(self, status):
    """保留原统计及原子替换，仅逐行序列化，避免同时分配完整JSONL字符串和字节副本。"""
    with self.lock:
        counts = {}
        for arm in self.conditions:
            items = [r for r in self.rows if r['condition'] == arm]
            counts[arm] = {'completed': len(items), **{
                key: sum(bool(r['final'].get(key)) for r in items)
                for key in ('functional', 'security', 'joint', 'measured')}}
        budget = self.io.budget.snapshot()
        # 时间字段继续使用原生函数，不改变summary/state协议。
        from configs.cle_weekly_eval_20261027.retest import now
        summary = {'protocol': self.protocol['protocol'], 'status': status, 'planned': len(self.cells),
            'completed': len(self.rows), 'arms': counts, 'Q_updates': 0, 'new_cards': 0,
            'known_reported_tokens': budget['known_reported_tokens'],
            'physical_HTTP': budget['transport_attempts_including_prior'],
            'unknown_or_inflight_HTTP': sum(not self.io.budget.valid_usage(e['usage']) for e in budget['entries']),
            'currency_cost': None, 'updated_utc': now(), 'no_performance_stop': True}
        self.io.save('summary', summary)
        self.io.state.update(status=status, completed_P7=len(self.rows),
            actual_paid_P7=0 if self.offline else len(self.rows), updated_utc=now())
        self.io.save('state', self.io.state)
        temp = self.out / 'rows.jsonl.tmp'
        with temp.open('w', encoding='utf-8') as stream:
            for row in self.rows:
                json.dump(row, stream, ensure_ascii=False)
                stream.write('\n')
        temp.replace(self.out / 'rows.jsonl')
        return summary


@lru_cache(maxsize=1)
def helper(kind):
    """唯一例外有完整wire/预算依据；旧失败记录保留，其他未决和认证预算错误照常阻断。"""
    if kind != 'ffs':
        raise ReplayStop('this_entry_only_handles_FS_run')
    h = previous_helper(kind)
    sources = h['sources']()
    classifier = h['probe'].__globals__['classify']
    pending, rejected = classifier(sources)
    path = FFS / 'segment_058/journals' / CELL / 'requests' / (IDENTITY + '.json')
    if len(sources) != 58 or pending or list(map(Path, rejected)) != [path]:
        raise ReplayStop('expected_exact_1147_local_predispatch_failure')
    record = read(path)
    if (record['identity'] != IDENTITY or record['status'] != 'failed_or_unresolved'
            or record['error_type'] != 'RuntimeError' or record['settings'] != h['base'].wiring.SETTINGS):
        raise ReplayStop('unexpected_local_failure_identity_or_settings')
    matches = []
    wire_count = 0
    for source in sources:
        for request in (source / 'wire').glob('*.request.json'):
            wire_count += 1
            body = read(request).get('body', {})
            if (body.get('model') == record['settings']['model']
                    and body.get('messages') == [{'role': 'user', 'content': record['prompt']}]):
                matches.append(str(request))
    if matches:
        raise ReplayStop('local_failed_request_has_physical_request_requires_other_recovery')
    budget = read(sources[-1] / 'budget.json')
    if wire_count != budget['transport_attempts_including_prior'] or wire_count != len(budget['entries']):
        raise ReplayStop('unrecorded_physical_reservation')
    caps = (budget['cap_tokens'], budget['cap_HTTP'], budget['cap_embedding_HTTP'])
    if (caps != (640900000, 134712, 47680) or wire_count >= caps[1]
            or budget['charged_tokens_including_unknown_and_inflight_bounds'] >= caps[0]):
        raise ReplayStop('physical_budget_exhausted_or_changed')

    def classified(prior):
        outstanding, reject = classifier(prior)
        return outstanding, [p for p in reject if Path(p) != path]

    h['probe'].__globals__['classify'] = classified
    h['repair_record'] = record
    h['repair_audit'] = {'segments': list(map(str, sources)), 'record': str(path),
        'pending_cell': CELL, 'pending_identity': IDENTITY, 'matching_physical_requests': 0,
        'physical_requests': wire_count, 'unrecorded_budget_reservations': 0,
        'budget': {k: v for k, v in budget.items() if k != 'entries'},
        'old_records_modified': False, 'scientific_protocol_changed': False}
    return h


def verify_reuse(study):
    """逐格比较原task_rows与实际复用行；不读取或重写旧rows、journal或状态。"""
    paths = {p.stem: p for s in study.sources for p in (s / 'task_rows').glob('*.json')}
    if len(paths) != EXPECTED or set(paths) != set(study.saved_rows):
        raise ReplayStop('completed_reuse_set_changed')
    matches = []
    for cell, row in study.saved_rows.items():
        if row != read(paths[cell]):
            raise ReplayStop('completed_reuse_row_changed:' + cell)
        matches.append({'cell_id': cell, 'source': str(paths[cell]), 'all_fields_equal': True})
    result = {'status': 'passed', 'matched_cells': len(matches), 'matches': matches,
              'new_HTTP_before_verification': 0, 'active_rows_file_opened': False}
    write_json(EVIDENCE / 'native_reuse_verification.json', result)
    study.io.save('completed_reuse_verification', result)


def probe(kind='ffs'):
    """封网执行原P7，消费完整保存前缀并停在唯一未派发请求。"""
    h = helper(kind)
    path = EVIDENCE / 'offline_checks.json'
    if path.exists():
        saved = read(path)
        if saved['audit'] != h['repair_audit']:
            raise ReplayStop('current_sources_differ_from_saved_probe')
        return saved
    worker = h['evaluate'].FrozenFS(h['sources'](), offline=True, destination=EVIDENCE / 'native_prefix')
    try:
        verify_reuse(worker)
        cell = next(c for c in worker.cells if c['cell_id'] == CELL)
        try:
            worker.one(cell, worker.start(worker.tasks[cell['task_id']], cell['repeat']))
            outcome = 'unexpected_completion'
        except ReplayStop as exc:
            outcome = str(exc)
        journal = worker.io.journals[CELL]
        if (outcome != 'replay_missing_request:' + IDENTITY or journal.prior - journal.consumed
                or list((worker.out / 'wire').glob('*.request.json'))):
            raise ReplayStop('local_failure_prefix_not_exact')
        result = {'status': 'passed', 'audit': h['repair_audit'], 'new_HTTP': 0,
            'socket_network_blocked': True, 'model_prefix': {'saved_rows': len(worker.saved_rows),
            'pending_cell': CELL, 'pending_identity': IDENTITY, 'stopped_at': outcome,
            'saved_responses_consumed': len(journal.consumed), 'all_prior_consumed': True}}
        write_json(path, result)
        return result
    finally:
        worker.embedding._db.close()


def run(kind='ffs'):
    checked = probe(kind)
    h = helper(kind)
    evaluate = h['evaluate']
    initialize = evaluate.FrozenFS.__init__

    def initialized(self, *args, **kwargs):
        initialize(self, *args, **kwargs)
        verify_reuse(self)
        before, after = read(self.sources[-1] / 'budget.json'), self.io.budget.snapshot()
        if (len(before['entries']) != len(after['entries']) or any(
                any(a[k] != b[k] for k in ('model', 'bound', 'usage'))
                for a, b in zip(before['entries'], after['entries'])) or any(
                before[k] != after[k] for k in ('cap_tokens', 'cap_HTTP', 'cap_embedding_HTTP',
                    'charged_tokens_including_unknown_and_inflight_bounds'))):
            raise ReplayStop('cumulative_budget_or_unknown_usage_changed')
        result = {'status': 'passed', 'retained_entries': len(before['entries']),
            'unknown_HTTP_retained': sum(e['usage'] is None for e in before['entries']),
            'model_bound_usage_unchanged': True, 'caps_unchanged': True, 'new_HTTP_before_verification': 0}
        write_json(EVIDENCE / 'budget_rollforward_check.json', result)
        self.io.save('budget_rollforward_check', result)
        previous_request = self.io.request_for

        def request_for(cell):
            request = previous_request(cell)
            if cell != CELL:
                return request
            boundary_verified = False

            def guarded(prompt):
                nonlocal boundary_verified
                journal = self.io.journal(cell)
                identity, public = request_identity(journal, prompt)
                if not boundary_verified and identity not in journal.records:
                    if identity != IDENTITY or public != {
                            k: h['repair_record'][k] for k in ('settings', 'prompt', 'selector')}:
                        raise ReplayStop('local_predispatch_request_payload_changed')
                    self.io.save('local_predispatch_boundary', {'cell': cell, 'identity': identity,
                        'prior_physical_dispatch': False, 'evidence': str(EVIDENCE / 'offline_checks.json')})
                    boundary_verified = True
                response = request(prompt)
                self.io.save('recovery_reused_responses/' + cell,
                    {'cell': cell, 'identities': sorted(journal.consumed), 'new_HTTP_for_reuse': 0})
                return response

            return guarded

        self.io.request_for = request_for
        self.io.save('stream_checkpoint_recovery', {'evidence': str(EVIDENCE / 'offline_checks.json'),
            'prior_completed': EXPECTED, 'old_failures_and_unknown_usage_retained': True,
            'streaming_JSONL': True, 'scientific_protocol_changed': False})
        target = self.out / 'source_bundle_external/stream_checkpoint_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    evaluate.FrozenFS.__init__ = initialized
    evaluate.FrozenFS.checkpoint = streaming_checkpoint
    destination = FFS / f'segment_{len(checked["audit"]["segments"])+1:03d}'
    with checkpoint_replace_retry(destination):
        original.run(kind)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    parser.add_argument('--kind', choices=['ffs'], required=True)
    args = parser.parse_args()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), EVIDENCE / 'recovery_entry.py')
    original.helper, original.probe, original.MODULE = helper, probe, MODULE
    if args.action == 'probe':
        with patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
            result = probe(args.kind)
    elif args.action == 'launch':
        result = original.launch(args.kind)
        if result.get('status') == 'launched':
            result['prefix_check'] = str(EVIDENCE / 'offline_checks.json')
            write_json(EVIDENCE / 'launch.json', result)
    else:
        result = run(args.kind)
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

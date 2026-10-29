"""恢复第61段已返回但未写入journal的两份响应；旧记录和科学协议不变。"""
import argparse
import gc
import json
from functools import lru_cache
from pathlib import Path
import shutil
from unittest.mock import patch

from configs.cle_weekly_http403_probe_refresh_20261028 import resume as refresh
from configs.cle_weekly_fs_checkpoint_20261028.resume import checkpoint_replace_retry
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

original = refresh.original
previous_helper = original.helper
MODULE = 'configs.cle_weekly_fs_raw_checkpoint_20261029.resume'
FFS = original.RUN / 'FFS'
EVIDENCE = original.RUN / 'workbench_monitor/autonomy/repairs/FS.run/20261028_segment061_attempt37'
TARGETS = {
    '153_r2_BM': ('0f6fa6746d72dc75e77f74ca5370545bb24e776730d027f0b03622ce28af3be1-000001', '0000028'),
    '359_r2_BFS': ('211e99ea9381e8bb0efaf7af781aa16d549b3beb34e95d5336f38ed53c7f7cab-000001', '0000029'),
}
EXPECTED = 2397


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def saved_response(path):
    """逐字复用原_requester流解析规则；完整结束和原模型是本次raw复用的必要条件。"""
    result = {'choices': [{'message': {'role': 'assistant', 'content': ''},
                           'finish_reason': None, 'index': 0}], 'usage': None}
    completed = done = False
    for raw_line in Path(path).read_bytes().splitlines():
        line = raw_line.decode('utf-8').strip()
        if not line.startswith('data:'):
            continue
        data = line[5:].strip()
        if data == '[DONE]':
            done = True
            break
        part = json.loads(data)
        if part.get('error'):
            raise ReplayStop('saved_stream_provider_error')
        for key in ('id', 'model', 'created'):
            if key in part:
                result[key] = part[key]
        if part.get('usage'):
            result['usage'] = part['usage']
        for choice in part.get('choices', []):
            if choice.get('index', 0) != 0:
                raise ReplayStop('saved_stream_multiple_choices')
            delta = choice.get('delta', {})
            result['choices'][0]['message']['content'] += delta.get('content') or ''
            if delta.get('refusal'):
                result['choices'][0]['message']['refusal'] = delta['refusal']
            if choice.get('finish_reason') is not None:
                result['choices'][0]['finish_reason'] = choice['finish_reason']
                completed = True
    if not completed or not done or result.get('model') != 'deepseek-v4.1-flash-1017':
        raise ReplayStop('saved_raw_not_complete_same_model')
    return result


def write_rows(path, rows):
    """分块写JSON，孤立代理字符仅作无损JSON转义，不分配整行UTF8副本。"""
    encoder = json.JSONEncoder(ensure_ascii=False)
    with Path(path).open('w', encoding='utf-8', errors='backslashreplace') as stream:
        for row in rows:
            for chunk in encoder.iterencode(row):
                stream.write(chunk)
            stream.write('\n')


def checkpoint(self, status):
    """保留原生统计、状态及原子替换，仅替换已发生内存错误的JSONL序列化。"""
    with self.lock:
        counts = {}
        for arm in self.conditions:
            items = [r for r in self.rows if r['condition'] == arm]
            counts[arm] = {'completed': len(items), **{
                key: sum(bool(r['final'].get(key)) for r in items)
                for key in ('functional', 'security', 'joint', 'measured')}}
        budget = self.io.budget.snapshot()
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
        write_rows(temp, self.rows)
        temp.replace(self.out / 'rows.jsonl')
        return summary


def verify_reuse(study):
    """逐格比较原生完成行；原物理账本只允许依据这两份raw恢复已知用量。"""
    paths = {p.stem: p for source in study.sources for p in (source / 'task_rows').glob('*.json')}
    if len(paths) != EXPECTED or set(paths) != set(study.saved_rows):
        raise ReplayStop('completed_2397_reuse_set_changed')
    matches = []
    for cell, row in study.saved_rows.items():
        if row != read(paths[cell]):
            raise ReplayStop('completed_reuse_row_changed:' + cell)
        matches.append({'cell_id': cell, 'source': str(paths[cell]), 'all_fields_equal': True})
    study.io.save('completed_reuse_verification', {'status': 'passed', 'matched_cells': len(matches),
        'matches': matches, 'new_HTTP_before_verification': 0})
    before, after = read(study.sources[-1] / 'budget.json'), study.io.budget.snapshot()
    if len(before['entries']) != len(after['entries']) or any(
            before[k] != after[k] for k in ('cap_tokens', 'cap_HTTP', 'cap_embedding_HTTP')):
        raise ReplayStop('cumulative_budget_entries_or_caps_changed')
    recovered_sources = {str(FFS / 'segment_061/wire' / (wire + '.request.json')):
        saved_response(FFS / 'segment_061/wire' / (wire + '.response.raw'))['usage']
        for _, wire in TARGETS.values()}
    changed = []
    for old, new in zip(before['entries'], after['entries']):
        if any(old[k] != new[k] for k in ('model', 'bound')):
            raise ReplayStop('prior_request_budget_identity_changed')
        if old['usage'] != new['usage']:
            source = new['source']
            if old['usage'] is not None or recovered_sources.get(source) != new['usage']:
                raise ReplayStop('unsupported_prior_usage_change')
            changed.append({'source': source, 'actual_usage_from_raw': new['usage']})
    if len(changed) != 2:
        raise ReplayStop('expected_two_late_saved_usage_records')
    study.io.save('budget_rollforward_check', {'status': 'passed', 'retained_entries': len(after['entries']),
        'unknown_before': sum(e['usage'] is None for e in before['entries']),
        'unknown_after': sum(e['usage'] is None for e in after['entries']), 'usage_recovered': changed,
        'old_budget_file_preserved': True, 'caps_unchanged': True, 'new_HTTP_before_verification': 0})


@lru_cache(maxsize=1)
def helper(kind):
    """仅将两份完整raw视为成功响应；其他未决仍由原恢复分类器阻断。"""
    if kind != 'ffs':
        raise ReplayStop('this_entry_only_handles_FS_run')
    h = previous_helper(kind)
    sources = h['sources']()
    classifier = h['probe'].__globals__['classify']
    pending, rejected = classifier(sources)
    failed = {FFS / 'segment_061/journals' / cell / 'requests' / (identity + '.json')
              for cell, (identity, _) in TARGETS.items()}
    if len(sources) != 61 or pending or set(map(Path, rejected)) != failed:
        raise ReplayStop('expected_exact_two_saved_raw_failures')
    recovered = {}
    for cell, (identity, wire) in TARGETS.items():
        path = FFS / 'segment_061/journals' / cell / 'requests' / (identity + '.json')
        record = read(path)
        request = FFS / 'segment_061/wire' / (wire + '.request.json')
        body = read(request)['body']
        if (record['identity'] != identity or record['settings'] != h['base'].wiring.SETTINGS
                or record['selector'] or body['model'] != record['settings']['model']
                or body['messages'] != [{'role': 'user', 'content': record['prompt']}]
                or body['max_tokens'] != 4096 or body['temperature'] != 0
                or body['thinking'] != {'type': 'disabled'} or body['stream'] is not True):
            raise ReplayStop('saved_raw_request_payload_changed')
        raw = request.with_name(wire + '.response.raw')
        recovered[cell] = {k: record[k] for k in ('identity', 'settings', 'prompt', 'selector', 'started_utc')}
        recovered[cell].update(status='completed', response=saved_response(raw),
            recovery={'source_failed_journal': str(path), 'source_raw': str(raw),
                      'new_HTTP': 0, 'old_record_preserved': True})

    def classified(prior):
        outstanding, reject = classifier(prior)
        return outstanding, [p for p in reject if Path(p) not in failed]

    h['probe'].__globals__['classify'] = classified
    initialize = h['evaluate'].FrozenFS.__init__

    def initialized(self, *args, **kwargs):
        initialize(self, *args, **kwargs)
        verify_reuse(self)
        for cell, record in recovered.items():
            write_json(self.out / 'journals' / cell / 'requests' / (record['identity'] + '.json'), record)
        self.io.save('raw_response_recovery', {'status': 'saved_responses_available',
            'cells': list(recovered), 'evidence': str(EVIDENCE / 'failure_inspection.json'),
            'old_records_modified': False, 'new_HTTP_for_recovery': 0, 'scientific_protocol_changed': False})
        target = self.out / 'source_bundle_external/raw_checkpoint_resume.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), target)

    h['evaluate'].FrozenFS.__init__ = initialized
    h['evaluate'].FrozenFS.checkpoint = checkpoint
    return h


def probe(kind='ffs'):
    """封网运行两个原生P7前缀，确实消费raw恢复响应后才允许后续新请求。"""
    h = helper(kind)
    result_path = EVIDENCE / 'offline_checks.json'
    if result_path.exists():
        return read(result_path)
    worker = h['evaluate'].FrozenFS(h['sources'](), offline=True, destination=EVIDENCE / 'native_prefix')
    reports = []
    try:
        for cell, (identity, _) in TARGETS.items():
            worker.io.reason = None
            selected = next(c for c in worker.cells if c['cell_id'] == cell)
            try:
                worker.one(selected, worker.start(worker.tasks[selected['task_id']], selected['repeat']))
                outcome = 'completed_from_saved_responses'
            except ReplayStop as exc:
                outcome = str(exc)
                if not outcome.startswith('replay_missing_request:'):
                    raise
            journal = worker.io.journals[cell]
            if identity not in journal.consumed or journal.prior - journal.consumed:
                raise ReplayStop('recovered_raw_response_not_consumed_exactly')
            reports.append({'cell': cell, 'recovered_identity': identity, 'outcome': outcome,
                'saved_responses_consumed': len(journal.consumed), 'all_prior_consumed': True})
        if list((worker.out / 'wire').glob('*.request.json')):
            raise ReplayStop('offline_probe_has_physical_request')
        result = {'status': 'passed', 'saved_rows': EXPECTED, 'targets': reports, 'new_HTTP': 0,
            'socket_network_blocked': True, 'native_evidence': str(worker.out)}
        write_json(result_path, result)
        return result
    finally:
        worker.embedding._db.close()
        del worker
        gc.collect()


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
    if args.action == 'probe':
        with patch('socket.socket.connect', side_effect=ReplayStop('offline_network_forbidden')):
            result = probe(args.kind)
    else:
        if args.action == 'launch':
            from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
            ensure_model_call_allowed('deepseek-v4.1-flash-1017')
        result = original.launch(args.kind) if args.action == 'launch' else run(args.kind)
    if result is not None:
        if args.action == 'launch':
            write_json(EVIDENCE / 'launch.json', result)
        print(json.dumps(result, ensure_ascii=True))


if __name__ == '__main__':
    main()

"""重执行原P7、精确消费保存响应，以当时反馈重建K0；不执行动态复验或API。"""
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from collections import defaultdict
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_analysis_20261027.analysis import collect_rows
from configs.cle_weekly_full_20261027 import learn
from methods.sct_trajectory import closed_loop
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RELATIVE = 'FQ_LEARN/K0/saved_feedback_replay_20261028'
MODE = 'saved_responses_and_historical_validation_feedback'
STATUS = 'passed_saved_response_and_historical_feedback_replay'


def normalized(value):
    """离线耗时不同；其余生成、选卡、验证和信用字段必须逐项相等。"""
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k != 'elapsed_seconds'}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_journals(sources):
    """核对每份保存请求的原生身份，以及旧失败的精确成功后继，不改旧journal。"""
    completed, failures = {}, []
    for root in sources:
        for path in (root / 'journals').glob('*/requests/*.json'):
            item = learn.read(path)
            cell = path.parent.parent.name
            public = {k: item[k] for k in ('settings', 'prompt', 'selector')}
            key = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            if not item['identity'].startswith(key + '-') or path.stem != item['identity']:
                raise ReplayStop('original_request_identity_mismatch:' + cell)
            if cell != 'embedding' and item['settings'] != learn.wiring.SETTINGS:
                raise ReplayStop('original_model_parameters_mismatch:' + cell)
            identity = (cell, item['identity'])
            if item['status'] == 'completed':
                if identity in completed:
                    old = completed[identity][1]
                    if any(old[k] != item[k] for k in ('settings', 'prompt', 'selector', 'response')):
                        raise ReplayStop('conflicting_successful_response:' + cell)
                completed[identity] = (path, item)
            else:
                failures.append((path, item, identity))
    resolved = []
    for path, item, identity in failures:
        if identity not in completed:
            raise ReplayStop('actual_unresolved_request:' + str(path))
        successor, success = completed[identity]
        if any(item[k] != success[k] for k in ('settings', 'prompt', 'selector')):
            raise ReplayStop('failed_success_request_payload_differs')
        resolved.append({'failed_record': str(path), 'successful_record': str(successor),
                         'cell_id': identity[0], 'identity': identity[1]})
    return completed, resolved


class HistoricalFeedback:
    """仅接受原题对象、原代码及原尝试顺序；输出当时反馈，不伪造新验证证据。"""
    def __init__(self, rows, tasks):
        self.expected = []
        self.consumed = []
        for row in rows:
            for attempt in row['attempts']:
                if attempt.get('code'):
                    self.expected.append((row['task_id'], tasks[row['task_id']], attempt))

    def __call__(self, task, code, timeout=20):
        position = len(self.consumed)
        if position >= len(self.expected):
            raise ReplayStop('unexpected_validation_call')
        task_id, original_task, attempt = self.expected[position]
        if task != original_task or code != attempt['code'] or timeout != 20:
            raise ReplayStop('historical_feedback_task_code_or_order_mismatch:' + task_id)
        self.consumed.append({'task_id': task_id, 'attempt': attempt['attempt'],
                              'code_sha256': hashlib.sha256(code.encode()).hexdigest(),
                              'validation': copy.deepcopy(attempt['validation'])})
        validation = attempt['validation']
        return copy.deepcopy(validation['evidence']), validation['state']


def run():
    destination = learn.RUN / RELATIVE
    if destination.exists():
        raise ReplayStop('independent_replay_directory_exists_preserve_evidence')
    sources = [Path(p) for p in learn.read(learn.RUN / 'execution_index.json')['FQ_LEARN_K0']]
    ids = learn.read(learn.RUN / 'manifest.json')['pools']['D_init']
    rows, row_paths, duplicates = collect_rows(sources, ids)
    if len(rows) != 303 or learn.read(sources[-1] / 'state.json')['status'] != 'completed':
        raise ReplayStop('K0_incomplete')
    records, resolved = audit_journals(sources)
    # 原成绩、请求、预算及旧失败回放均须保持原字节；这里的摘要服务于实际不改旧结果要求。
    protected = [Path(p) for p in row_paths.values()]
    protected += [p for root in sources for p in (root / 'journals').glob('*/requests/*.json')]
    protected += [root / name for root in sources for name in ('state.json', 'summary.json', 'budget.json', 'source_identity.json')]
    protected += list((learn.RUN / 'FQ_LEARN/K0/zero_API_replay').rglob('*.json'))
    input_paths = [learn.RUN / name for name in ('manifest.json', 'protocol.json',
        'shared_inputs/tasks_D_init.json', 'shared_inputs/memory1939_q0.jsonl', 'FQ_LEARN/frozen/K0.jsonl')]
    protected += input_paths
    before = {str(p): digest(p) for p in protected}
    feedback = HistoricalFeedback(rows, learn.read(input_paths[2]))
    # 只在本离线进程中替换两个接点；原生入口、P7和Q函数仍实际执行。
    with ExitStack() as stack:
        stack.enter_context(patch.object(learn, 'unresolved_requests', lambda roots: []))
        stack.enter_context(patch.object(closed_loop, 'validate_and_state', feedback))
        worker = learn.LearningStage('K0', 'D_init', sources, offline=True, destination=destination)
        worker.io.state['evidence_kind'] = MODE
        worker.io.save('independent_replay_mode', {'mode': MODE, 'dynamic_revalidation_executed': False,
            'original_native_failure_retained': str(learn.RUN / 'FQ_LEARN/K0/zero_API_replay/state.json'),
            'authorization': 'Q.K0.analysis user instruction 2026-10-28'})
        worker.io.save('independent_launch', {'pid': os.getpid(), 'command': [sys.executable, '-B', '-X', 'utf8',
            '-m', 'configs.cle_weekly_k0_saved_feedback_20261028.replay', 'run'],
            'started_utc': learn.now(), 'workers': 0})
        register = learn.RUN / 'workbench_monitor/autonomy/registered_workers.json'
        entries = learn.read(register)
        entries.append({'pid': os.getpid(), 'package': 'FQ_LEARN', 'workers': 0,
                        'command_marker': 'configs.cle_weekly_k0_saved_feedback_20261028.replay'})
        write_json(register, entries)
        summary = worker.execute()
    if len(feedback.consumed) != len(feedback.expected):
        raise ReplayStop('unconsumed_historical_feedback')
    per_task = []
    for original, replayed in zip(rows, worker.rows):
        cell = original['cell_id']
        if normalized(original) != normalized(replayed):
            write_json(destination / 'row_mismatch.json', {'cell_id': cell,
                'original': normalized(original), 'replayed': normalized(replayed)})
            raise ReplayStop('full_native_row_differs:' + cell)
        journal = worker.io.journals[cell]
        expected = {identity for (key, identity) in records if key == cell}
        if journal.consumed != expected:
            raise ReplayStop('saved_requests_not_exactly_consumed:' + cell)
        per_task.append({'task_id': original['task_id'], 'cell_id': cell,
            'original_row': row_paths[original['task_id']],
            'replay_row': str(destination / 'task_rows' / (cell + '.json')),
            'consumed_request_identities': sorted(journal.consumed),
            'feedback_attempts': [x['attempt'] for x in feedback.consumed if x['task_id'] == original['task_id']],
            'all_non_timing_row_fields_equal': True, 'Q_events_equal': True})
    frozen = learn.runner.load_memory(input_paths[-1])
    if [n.to_dict() for n in frozen] != [n.to_dict() for n in worker.bank]:
        raise ReplayStop('replayed_frozen_bank_differs')
    if any(digest(p) != value for p, value in before.items()):
        raise ReplayStop('original_evidence_changed')
    new_http = len(list((destination / 'wire').glob('*.request.json')))
    if new_http:
        raise ReplayStop('offline_replay_generated_HTTP')
    write_json(destination / 'per_task_audit.json', per_task)
    write_json(destination / 'feedback_audit.json', feedback.consumed)
    write_json(destination / 'resolved_old_failures.json', resolved)
    write_json(destination / 'original_evidence_unchanged.json', {'status': 'passed', 'sha256': before})
    certificate = {'status': STATUS, 'mode': MODE, 'stage': 'K0', 'completed': len(worker.rows), 'planned': 303,
        'all_non_timing_row_fields_equal': True, 'all_saved_model_requests_consumed': True,
        'model_requests_consumed': sum(len(x['consumed_request_identities']) for x in per_task),
        'historical_feedback_calls': len(feedback.consumed), 'resolved_old_failures': len(resolved),
        'identical_duplicate_row_copies': duplicates, 'Q_events_equal': True,
        'frozen_Q_visits_and_card_bodies_equal': True, 'original_evidence_unchanged': True,
        'new_HTTP': new_http, 'dynamic_revalidation_executed': False,
        'dynamic_validation_all_consistent': False,
        'known_dynamic_divergence': str(learn.RUN / 'analysis/K0/maintenance_20261028/validator_1107_diagnostic.json'),
        'original_native_replay_preserved': str(learn.RUN / 'FQ_LEARN/K0/zero_API_replay'),
        'source_segments': list(map(str, sources)), 'input_sha256': {str(p): digest(p) for p in input_paths},
        'evidence': [str(destination / name) for name in ('per_task_audit.json', 'feedback_audit.json',
            'resolved_old_failures.json', 'original_evidence_unchanged.json', 'replay_result.json',
            'summary.json', 'independent_launch.json')],
        'final': summary['final'], 'created_utc': learn.now()}
    write_json(destination / 'certificate.json', certificate)
    print(json.dumps({k: certificate[k] for k in ('status', 'completed', 'model_requests_consumed',
        'historical_feedback_calls', 'new_HTTP')}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run'])
    parser.parse_args()
    run()


if __name__ == '__main__':
    main()

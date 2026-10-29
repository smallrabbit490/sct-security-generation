"""FQ_RETEST：D_grow全273题、五条件、两次独立重复，复用原P7和验证器。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import threading
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from pathlib import Path
from time import perf_counter

from configs.cle_v41_relation_20261026 import wiring
from configs.cle_v41_relation_20261026.execution import StudyExecution
from configs.cle_weekly_full_20261027.prepare import ROOT, RUN, read, disk_check, configure_validation
from configs.cle_weekly_full_20261027.learn import body_state, now, unresolved_requests
from methods.cle_ablation import runner
from methods.cle_ablation.run_memory_q import prepare_shared_initial, record_result
from methods.cle_ablation.run_memory_q_online import inspect_row, mechanism
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

PROTOCOL = 'cle-weekly-frozen-dgrow-five-conditions-20261027-v1'
CONDITIONS = ('Q1', 'Q2_K0', 'Q2_K1', 'Q2_K2', 'Q2_K3')
PACKAGE = 'FQ_RETEST'
SEED = 20261027


def package_root():
    return RUN / PACKAGE


def schedule(ids, tasks):
    """先固定全部题/条件/重复；条件顺序随机，学习状态和成绩不参与排程。"""
    rng = random.Random(SEED)
    cells = []
    for repeat in (1, 2):
        for tid in ids:
            arms = list(CONDITIONS)
            rng.shuffle(arms)
            for arm in arms:
                cells.append({'cell_id': f'{tid}_r{repeat}_{arm}', 'task_id': tid,
                              'family_id': tasks[tid]['family_id'], 'repeat': repeat,
                              'condition': arm, 'pool': 'D_grow'})
    return cells


def prepare():
    """仅写本包输入，不修改正在学习的根manifest、源码、预算或卡库。"""
    target = package_root() / 'inputs'
    if (target / 'protocol.json').exists():
        return read(target / 'protocol.json')
    disk_check()
    ids = read(RUN / 'manifest.json')['pools']['D_grow']
    tasks = read(RUN / 'shared_inputs/tasks_D_grow.json')
    if len(ids) != 273 or len(set(ids)) != 273 or set(ids) != set(tasks):
        raise ReplayStop('retest_requires_original_full_273_manifest')
    cells = schedule(ids, tasks)
    banks = {'Q1': str(RUN / 'shared_inputs/memory1939_q0.jsonl')}
    banks.update({f'Q2_{k}': str(RUN / 'FQ_LEARN/frozen' / f'{k}.jsonl')
                  for k in ('K0', 'K1', 'K2', 'K3')})
    protocol = {'protocol': PROTOCOL, 'package': PACKAGE, 'planned_P7': len(cells),
        'task_count': 273, 'card_count': 1939, 'repeats': 2, 'conditions': list(CONDITIONS),
        'bank_sources': banks, 'paid_execution_enabled': False,
        'model_settings': wiring.SETTINGS, 'max_cards': 3, 'max_repairs': 1,
        'retrieval_mode': 'semantic_llm', 'delta': -1, 'lambda_q': .5,
        'Q1_definition': 'cosine order presented to original LLM selector; not numerical top3',
        'Q2_definition': 'cosine plus frozen Q order presented to same LLM selector',
        'workers_max': 4, 'Q_updates': 0, 'new_cards': 0,
        'first_initial_shared_within': 'task x repeat only; repeats independent',
        'first_candidates': 'same public query, recall24+8, cosine and card content; compare actual traces',
        'repair_queries': 'independent per condition code and original permitted feedback',
        'candidate_failure_policy': 'retain technical/model parsing evidence; no score-based retries',
        'source_learning_protocol': read(RUN / 'protocol.json')['protocol'],
        'completed_learning_required': ['K0', 'K1', 'K2', 'K3'],
        'performance_gate_controls_dispatch': False,
        'budget_proposed': {'conservative_model_and_embedding_tokens': len(cells) * 150000,
            'total_physical_HTTP_attempts': len(cells) * 40,
            'embedding_HTTP_attempts_included_in_total': len(cells) * 16},
        'budget_basis': 'same per-P7 engineering cap as learning; shared initial/selection and retries included; no currency estimate',
        'formal_historical_code_reuse': 0,
        'resume_budget_reset': False, 'unknown_HTTP_redispatch': False}
    write_json(target / 'tasks.json', tasks)
    write_json(target / 'schedule.json', cells)
    write_json(target / 'protocol.json', protocol)
    write_json(target / 'reuse_manifest.json', {'formal_old_code_units': 0,
        'reason': 'new frozen Q41 plus current public contracts; learning code is not a frozen counterfactual',
        'allowed': ['exact text/model embedding cache', 'same task-repeat first initial',
                    'completed exact cell and saved response during recovery'],
        'not_allowed': ['one response credited to two repeats', 'learning-period code substituted for retest']})
    return protocol


def dependencies():
    """依据各段完成状态与冻结库判断依赖；不把文件存在当作完整学习。"""
    reasons = []
    index = read(RUN / 'execution_index.json')
    for k, expected in [('K0', 303), ('K1', 273), ('K2', 273), ('K3', 273)]:
        segments = index.get('FQ_LEARN_' + k, [])
        if not segments or not (Path(segments[-1]) / 'summary.json').exists():
            reasons.append(k + '_not_completed')
            continue
        summary = read(Path(segments[-1]) / 'summary.json')
        if summary.get('status') != 'completed' or summary.get('completed') != expected:
            reasons.append(k + '_not_completed')
        if not (RUN / 'FQ_LEARN/frozen' / (k + '.jsonl')).exists():
            reasons.append(k + '_frozen_bank_missing')
        replay = RUN / 'FQ_LEARN' / k / 'zero_API_replay/replay_result.json'
        if not replay.exists() or read(replay).get('status') != 'passed':
            reasons.append(k + '_native_replay_pending')
        analysis = RUN / 'analysis' / k / 'summary.json'
        if not analysis.exists() or read(analysis).get('status') != 'completed':
            reasons.append(k + '_stage_analysis_pending')
    return {'ready': not reasons, 'reasons': reasons}


def snapshot_sources(destination, prior):
    """保留实际运行Python源；恢复只接受保存源文件逐项未变。"""
    directories = ('methods', 'src', 'configs/cle_weekly_full_20261027',
                   'configs/cle_weekly_eval_20261027', 'configs/cle_weekly_gate_20261027',
                   'configs/cle_weekly_fs_20261027',
                   'configs/cle_weekly_granularity_20261027',
                   'configs/cle_weekly_granularity_gate_20261027',
                   'configs/cle_v41_relation_20261026',
                   'configs/cle_v41_migration_20261025')
    paths = [p for d in directories for p in (ROOT / d).rglob('*.py')]
    paths.append(ROOT / 'configs/cle_v41_completion_20261026/materials.py')
    paths.append(ROOT / 'configs/cle_v41_completion_20261026/policies.py')
    identity = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    for previous in prior:
        saved = read(previous / 'source_identity.json')
        if any(identity.get(p) != value for p, value in saved.items()):
            raise ReplayStop('saved_runtime_source_changed_requires_explicit_reconciliation')
    for p in paths:
        target = destination / 'source_bundle' / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, target)
    write_json(destination / 'source_identity.json', identity)


def first_candidate_signature(row):
    trace = (row['attempts'][0].get('retrieval_trace') or {})
    if trace.get('status') != 'completed':
        return None
    scores = sorted(trace.get('scores', []), key=lambda s: s['id'])
    return {'query_hash': trace.get('query_hash'),
            'candidate_ids': sorted(trace.get('candidate_ids', [])),
            'scores': [{k: s[k] for k in ('id', 'cosine', 'content_hash')} for s in scores]}


def candidate_consistency(rows, conditions=CONDITIONS):
    first = rows[0]
    known = [signature for row in rows if (signature := first_candidate_signature(row)) is not None]
    mismatch = any(signature != known[0] for signature in known[1:]) if known else False
    return {'status': 'different' if mismatch else 'passed' if len(known) == len(conditions)
            else 'incomplete_model_or_retrieval_measurement',
            'task_id': first['task_id'], 'repeat': first['repeat'], 'measured_conditions': len(known),
            'expected_conditions': len(conditions), 'candidate_signature': known[0] if known else None}


def check_saved_candidates(rows, conditions=CONDITIONS):
    groups = defaultdict(list)
    for row in rows:
        if row['condition'] in conditions:
            groups[row['task_id'], row['repeat']].append(row)
    if any(candidate_consistency(group, conditions)['status'] == 'different' for group in groups.values()):
        raise ReplayStop('saved_first_query_candidate_or_cosine_mismatch')


class FrozenRetest:
    """每个题×重复为一组，组内五条件顺序运行，最多四组并发；不更新Q。"""

    conditions = CONDITIONS
    controlled_conditions = CONDITIONS
    pool = 'D_grow'
    runner_module = 'configs.cle_weekly_eval_20261027.retest'
    reference_bank = 'Q1'
    worker_limit = 4

    def package_directory(self):
        return package_root()

    def input_directory(self):
        return self.package_directory() / 'inputs'

    def load_banks(self):
        return {arm: runner.load_memory(Path(p)) for arm, p in self.protocol['bank_sources'].items()}

    def additional_protected_paths(self):
        return []

    def policy(self, arm):
        return {'candidate_order': 'similarity' if arm == 'Q1' else 'q', 'delta': -1,
                'record_arm': 'Q1' if arm == 'Q1' else 'Q2',
                'Q_checkpoint': None if arm == 'Q1' else arm.split('_')[1]}

    def group_candidate_check(self, rows):
        return candidate_consistency([r for r in rows if r['condition'] in self.controlled_conditions],
                                     self.controlled_conditions)

    def after_group(self, rows, check):
        """专用评价可在此记录非受控参考臂的边界，不改变主要比较或派发。"""

    def validate_saved_rows(self, rows):
        check_saved_candidates(rows, self.controlled_conditions)

    def decorate_row(self, row, cell):
        """专用消费者补充真实干预名称；原冻结Q比较无额外字段。"""

    def inspect_native_row(self, row):
        inspect_row(row)

    def run_p7(self, cell, start, request):
        arm = cell['condition']
        policy = self.policy(arm)
        return runner.run_one('PLT', self.tasks[cell['task_id']], 'P7', request,
            {'full': self.banks[arm]}, self.embedding,
            retrieval_mode='semantic_llm', delta=policy['delta'], lambda_q=.5, max_experiences=3,
            candidate_order=policy['candidate_order'],
            initial_analysis=copy.deepcopy(start['initial_analysis']))

    def __init__(self, sources=(), *, offline=False, destination=None):
        self.sources = [Path(p) for p in sources]
        self.offline = offline
        inputs = self.input_directory()
        self.protocol = read(inputs / 'protocol.json')
        self.cells = read(inputs / 'schedule.json')
        self.tasks = read(inputs / 'tasks.json')
        self.banks = self.load_banks()
        body = body_state(self.banks[self.reference_bank])
        if len(body) != self.protocol['card_count'] or any(body_state(bank) != body for bank in self.banks.values()):
            raise ReplayStop('frozen_conditions_have_different_card_bodies_or_lifecycle')
        self.frozen_before = {arm: [n.to_dict() for n in bank] for arm, bank in self.banks.items()}
        if unresolved_requests(self.sources):
            raise ReplayStop('unresolved_saved_requests_require_zero_API_reconciliation')
        expected = {cell['cell_id']: cell for cell in self.cells}
        self.rows, self.saved_rows = [], {}
        for root in self.sources:
            for p in (root / 'task_rows').glob('*.json'):
                row = read(p)
                key = row['cell_id']
                if key not in expected or any(row[k] != expected[key][k] for k in ('task_id', 'repeat', 'condition')):
                    raise ReplayStop('saved_completed_cell_outside_frozen_schedule')
                if key in self.saved_rows and self.saved_rows[key] != row:
                    raise ReplayStop('conflicting_completed_cell')
                self.saved_rows[key] = row
        self.validate_saved_rows(list(self.saved_rows.values()))
        if not offline:
            self.rows = list(self.saved_rows.values())
        self.out = Path(destination) if destination else self.package_directory() / f'segment_{len(self.sources)+1:03d}'
        self.slots = threading.Semaphore(self.worker_limit)
        self.lock = threading.RLock()
        from methods.sct_trajectory import run_closed_loop as native
        def forbidden(*args, **kwargs):
            raise ReplayStop('zero_API_replay_no_network_or_missing_response')
        def factory(identity):
            if offline:
                return forbidden
            return native._requester(wiring.SETTINGS['model'], 180, 4096, 4,
                thinking='disabled', stream=True, endpoint='https://api.chatanywhere.org/v1/chat/completions',
                hard_timeout=300, gate_wait_timeout=600, semaphore=self.slots)
        protocol = {**self.protocol, 'paid_execution_enabled': not offline}
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.io = StudyExecution(self.out, protocol, self.cells, client_factory=factory,
            physical_open=forbidden if offline else direct.open, live=not offline, fixed_eight=False,
            resume_sources=self.sources, protected_paths=[inputs / 'protocol.json', inputs / 'tasks.json',
                inputs / 'schedule.json'] + [Path(p) for p in protocol['bank_sources'].values()]
                + self.additional_protected_paths())
        for prior in self.sources:
            if read(prior / 'input_identity.json') != self.io.inputs_before:
                raise ReplayStop('saved_protocol_task_schedule_or_Q_snapshot_changed')
        self.io.save('input_identity', self.io.inputs_before)
        if offline:
            self.io.replay_source = self.out
            self.io.state['evidence_kind'] = 'zero_API_saved_response_replay'
        snapshot_sources(self.out, self.sources)
        self.io.save('launch', {'pid': os.getpid(), 'started_utc': now(), 'offline': offline,
            'runtime_workers': self.worker_limit,
            'runner': self.runner_module,
            'branch': subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT, text=True).strip(),
            'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()})
        cache = self.out / 'embeddings.sqlite3'
        seed = self.sources[-1] / 'embeddings.sqlite3' if self.sources else RUN / 'shared_inputs/embeddings.sqlite3'
        with closing(sqlite3.connect(f'file:{seed.as_posix()}?mode=ro', uri=True)) as src:
            with closing(sqlite3.connect(cache)) as dst:
                src.backup(dst)
        import methods.sct_trajectory.semantic_retrieval as semantic
        semantic.MAX_SELECTOR_CHARS = 420000
        self.embedding = semantic.EmbeddingClient(cache_path=cache,
            key_loader=forbidden if offline else native.load_key, semaphore=self.slots,
            timeout=180, hard_timeout=300, gate_wait_timeout=600)
        original = self.embedding._request
        def embedded(texts):
            if offline:
                return forbidden()
            def call(items):
                before = self.embedding.usage
                vectors = original(items)
                after = self.embedding.usage
                usage = None if after['usage_missing_calls'] > before['usage_missing_calls'] else {
                    k: after[k]-before[k] for k in ('prompt_tokens', 'total_tokens')}
                return {'vectors': vectors, 'usage': usage}
            return self.io.embedding(texts, call)['vectors']
        self.embedding._request = embedded
        configure_validation()

    def start(self, task, repeat):
        key = f'{task["index"]}_r{repeat}'
        for root in reversed(self.sources):
            path = root / 'shared_starts' / (key + '.json')
            if path.exists():
                saved = read(path)
                self.io.save('shared_starts/' + key, saved)
                return saved
        request = self.io.request_for('shared_initial_' + key)
        saved = prepare_shared_initial(task, request)
        self.io.save('shared_starts/' + key, saved)
        if self.io.reason:
            raise ReplayStop(self.io.reason)
        return saved

    def one(self, cell, start):
        task = self.tasks[cell['task_id']]
        arm = cell['condition']
        policy = self.policy(arm)
        request = self.io.request_for(cell['cell_id'])
        started = perf_counter()
        row = self.run_p7(cell, start, request)
        if self.io.reason:
            self.io.save('incomplete_tasks/' + cell['cell_id'], row)
            raise ReplayStop(self.io.reason)
        row = record_result(row, task, policy['record_arm'], self.pool, perf_counter()-started)
        row.update(cell, protocol=self.protocol['protocol'], retrieval_mode='semantic_llm',
            candidate_order=policy['candidate_order'], Q_updates=0,
            Q_checkpoint=policy['Q_checkpoint'],
            shared_initial_error=start['error_type'])
        self.inspect_native_row(row)
        row['mechanism'] = mechanism(row, self.banks[arm])
        self.decorate_row(row, cell)
        self.io.save('task_rows/' + cell['cell_id'], row)
        with self.lock:
            self.rows.append(row)
            self.checkpoint('running_replay' if self.offline else 'running')
        return row

    def group(self, cells):
        try:
            return self._group(cells)
        except BaseException:
            # 先在故障worker设置停止信号，避免它取走下一排队组并派发初析。
            self.io.reason = self.io.reason or 'frozen_group_technical_failure'
            raise

    def _group(self, cells):
        first = cells[0]
        start = self.start(self.tasks[first['task_id']], first['repeat'])
        rows = [self.saved_rows[c['cell_id']] for c in self.cells
                if c['task_id'] == first['task_id'] and c['repeat'] == first['repeat']
                and c['cell_id'] in self.saved_rows and not self.offline]
        for cell in cells:
            if self.io.reason:
                raise ReplayStop(self.io.reason)
            disk_check()
            rows.append(self.one(cell, start))
        check = self.group_candidate_check(rows)
        self.io.save(f'common_candidates/{first["task_id"]}_r{first["repeat"]}', check)
        self.after_group(rows, check)
        if check['status'] == 'different':
            self.io.stop('first_query_candidate_or_cosine_mismatch')

    def checkpoint(self, status):
        with self.lock:
            counts = {}
            for arm in self.conditions:
                items = [r for r in self.rows if r['condition'] == arm]
                counts[arm] = {'completed': len(items), **{key: sum(bool(r['final'].get(key)) for r in items)
                    for key in ('functional', 'security', 'joint', 'measured')}}
            budget = self.io.budget.snapshot()
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
            temp.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in self.rows), encoding='utf-8')
            temp.replace(self.out / 'rows.jsonl')
            return summary

    def execute(self):
        self.checkpoint('running_replay' if self.offline else 'running')
        try:
            groups = defaultdict(list)
            done = {row['cell_id'] for row in self.rows}
            for cell in self.cells:
                if cell['cell_id'] not in done:
                    groups[cell['task_id'], cell['repeat']].append(cell)
            with self.io.physical_records(), ThreadPoolExecutor(max_workers=self.worker_limit) as workers:
                futures = [workers.submit(self.group, cells) for cells in groups.values()]
                for future in as_completed(futures):
                    try:
                        future.result()
                    except BaseException:
                        # 工程故障须先停止其他组的新派发，再等待其在途响应自然完成。
                        self.io.reason = self.io.reason or 'frozen_group_technical_failure'
                        for pending in futures:
                            pending.cancel()
                        raise
            if self.io.input_state() != self.io.inputs_before or any(
                    [n.to_dict() for n in bank] != self.frozen_before[arm] for arm, bank in self.banks.items()):
                raise ReplayStop('evaluation_modified_frozen_Q_or_inputs')
            if len(self.rows) != len(self.cells):
                raise ReplayStop('frozen_schedule_incomplete')
            self.validate_saved_rows(self.rows)
            if self.offline:
                diffs = [r['cell_id'] for r in self.rows if any(r['final'].get(k) != self.saved_rows[r['cell_id']]['final'].get(k)
                         for k in ('code', 'functional', 'security', 'joint', 'measured'))]
                self.io.save('replay_result', {'status': 'different' if diffs else 'passed',
                    'completed': len(self.rows), 'differences': diffs, 'new_HTTP': 0})
                if diffs:
                    raise ReplayStop('native_frozen_replay_diverged')
            return self.checkpoint('completed')
        except BaseException as exc:
            self.io.state['reason'] = self.io.reason or (str(exc) if isinstance(exc, ReplayStop) else type(exc).__name__)
            self.checkpoint('needs_technical_recovery')
            raise
        finally:
            self.embedding._db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'check', 'launch', 'run', 'resume', 'replay'])
    args = parser.parse_args()
    if args.action == 'prepare':
        result = prepare()
        print(json.dumps({'status': 'prepared_zero_API', 'planned': result['planned_P7'], 'dependencies': dependencies()}))
        return
    gate = package_root() / 'offline_checks.json'
    dep = dependencies()
    if args.action == 'check':
        print(json.dumps({'dependencies': dep, 'offline_checks': read(gate) if gate.exists() else None}))
        return
    if args.action not in ('replay',) and (not dep['ready'] or not gate.exists() or read(gate).get('status') != 'passed'):
        raise ReplayStop('frozen_retest_not_ready:' + ','.join(dep['reasons']))
    index_path = package_root() / 'execution_index.json'
    sources = [Path(p) for p in read(index_path)['segments']] if index_path.exists() else []
    if args.action == 'launch':
        from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
        ensure_model_call_allowed(wiring.SETTINGS['model'])
        ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*configs.cle_weekly_eval_20261027.retest run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
        actual = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, check=True)
        if actual.stdout.strip():
            print(json.dumps({'status': 'already_running'}))
            return
        package_root().mkdir(parents=True, exist_ok=True)
        with (package_root() / 'stdout.log').open('a', encoding='utf-8') as stdout, (package_root() / 'stderr.log').open('a', encoding='utf-8') as stderr:
            process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                'configs.cle_weekly_eval_20261027.retest', 'run'], cwd=ROOT, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
        write_json(package_root() / 'launch.json', {'pid': process.pid, 'started_utc': now()})
        print(json.dumps({'status': 'launched', 'pid': process.pid}))
        return
    if args.action == 'replay':
        destination = package_root() / 'zero_API_replay'
        if (destination / 'replay_result.json').exists():
            print(json.dumps(read(destination / 'replay_result.json')))
            return
        FrozenRetest(sources, offline=True, destination=destination).execute()
        return
    import msvcrt
    with (package_root() / 'execution.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            if sources and args.action != 'resume':
                raise ReplayStop('existing_segments_require_explicit_reconciliation_or_replay')
            destination = package_root() / f'segment_{len(sources)+1:03d}'
            study = FrozenRetest(sources, destination=destination)
            write_json(index_path, {'segments': list(map(str, sources)) + [str(destination)]})
            study.execute()
            write_json(package_root() / 'completion.json', {'status': 'awaiting_agent_analysis', 'planned': 2730, 'updated_utc': now()})
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()

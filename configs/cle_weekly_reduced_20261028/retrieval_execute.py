"""FR有界执行：只补缺向量、一次性AI盲标、精确恢复及人工标签独立导入。

不生成代码或初析，不更新经验/Q，不启动其他实验；全部HTTP复用StudyExecution。
prepare/check/replay/import-review/metrics均为零API；run/resume显式进入已授权付费层。
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import retrieval_prepare as prep
from configs.cle_v41_relation_20261026 import wiring
from configs.cle_v41_migration_20261025.resume import RecoveryBudget
from configs.cle_v41_relation_20261026.execution import StudyExecution
from methods.cle_ablation.retrieval_q_metrics import metrics as native_metrics
from methods.sct_trajectory.agent_pipeline import _content, _extract_json
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed, ModelTimeWindowError
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from methods.sct_trajectory.semantic_retrieval import (
    CACHE_VERSION, MAX_BATCH_ITEMS, MAX_BATCH_CHARS, MAX_CARD_CHARS, MAX_TEXT_CHARS,
    EmbeddingClient, _digest, card_embedding_text, query_embedding_text)

VERSION = 'cle-reduced-retrieval57-execution-20261028-v1'
PAIR_LIMIT = 10767
EXTRA_LIMIT = 4383
TEXT_LIMIT = 1939 + 57 * 3
MODEL = wiring.SETTINGS['model']


def now():
    return datetime.now(timezone.utc).isoformat()


def paths():
    return prep.out()


def segments():
    index = paths() / 'execution_index.json'
    return [Path(p) for p in prep.read(index)['segments']] if index.exists() else []


def legal_nodes(nodes, language='python'):
    return [n for n in nodes if n.status in {'active', 'provisional', 'consolidated'}
            and language in n.language_leaves and len(card_embedding_text(n)) <= MAX_CARD_CHARS]


def prepare():
    """冻结有限最坏预算；卡正文/公开题面原件和原生32条/8万字符批次不改变。"""
    prep.prepare()
    prep.verify()
    target = paths() / 'execution_protocol.json'
    if target.exists():
        return prep.read(target)
    public = prep.read(paths() / 'inputs/public_tasks.json')
    bank = prep.read(paths() / 'inputs/protocol.json')['memory_path']
    nodes = legal_nodes(prep.load_memory(Path(bank)))
    card_values = [json.loads(card_embedding_text(n)) for n in nodes]
    # 标注提示由任务JSON和卡JSON独立拼接；分别取实际最大长度即可覆盖所有配对。
    public_json = [json.dumps(prep.blind_pair(t, {})['task'], ensure_ascii=False) for t in public.values()]
    card_json = [json.dumps(c, ensure_ascii=False) for c in card_values]
    public_max = max(len(v.encode()) for v in public_json)
    card_max = max(len(v.encode()) for v in card_json)
    constant = len(prep.model_judge_prompt({'task': {}, 'card': {}}).encode())
    empty_body = {'model': MODEL, 'messages': [{'role': 'user', 'content': prep.model_judge_prompt({'task': {}, 'card': {}})}],
        'temperature': 0, 'max_tokens': 4096, 'thinking': {'type': 'disabled'},
        'stream': True, 'stream_options': {'include_usage': True}}
    # 对prompt作为HTTP JSON字符串后的引号/反斜线转义计费，不能只按未转义正文估上界。
    label_bound = RecoveryBudget.make_entry(empty_body)['bound'] + max(len(json.dumps(v, ensure_ascii=False).encode()) for v in public_json) + max(len(json.dumps(v, ensure_ascii=False).encode()) for v in card_json)
    # 原生查询最长24000字符；UTF-8每字符最多4字节，包含尚未产生的真实首次初析。
    embedding_tokens = TEXT_LIMIT * (MAX_TEXT_CHARS * 4 + 2048)
    schedule = [{'cell_id': 'FR_' + tid, 'task_id': tid, 'unit': 'retrieval_task_not_P7'} for tid in public]
    protocol = {'protocol': VERSION, 'source_protocol': prep.PROTOCOL,
        'model_settings': wiring.SETTINGS, 'AI_max_attempts': 1,
        'AI_max_physical_HTTP_per_pair': 1, 'max_output_tokens': 4096,
        'pair_limit': PAIR_LIMIT, 'initial_pair_cap': 6384, 'extra_pair_cap': EXTRA_LIMIT,
        'absolute_task_card_upper_bound': 57 * 1939,
        'extra_basis': {'D_grow': '27*3*(3 learning +10 retest +10 granularity)',
                        'D_gate': '30*3*(8 Q +10 F/S +6 classifier +4 old-library cross-model)'},
        'embedding_text_limit': TEXT_LIMIT, 'embedding_batch_items': MAX_BATCH_ITEMS,
        'embedding_batch_chars': MAX_BATCH_CHARS, 'embedding_max_attempts_per_batch': 1,
        'budget_proposed': {'conservative_model_and_embedding_tokens': PAIR_LIMIT * label_bound + embedding_tokens,
            'total_physical_HTTP_attempts': PAIR_LIMIT + TEXT_LIMIT,
            'embedding_HTTP_attempts_included_in_total': TEXT_LIMIT},
        'budget_basis': {'AI_per_pair_conservative_tokens': label_bound,
            'largest_public_task_UTF8_bytes': public_max, 'largest_card_UTF8_bytes': card_max,
            'prompt_constant_UTF8_bytes': constant, 'embedding_conservative_tokens': embedding_tokens},
        # StudyExecution保留原字段名；本包571个单元是检索任务，不是代码生成次数。
        'planned_P7': len(schedule), 'execution_units_are_P7': False,
        'code_generations': 0, 'new_initial_analysis_calls': 0,
        'max_workers': 1, 'queue_when_four_worker_evaluation_active': True,
        'resume_budget_reset': False, 'unresolved_HTTP_redispatch': False,
        'human_confirmation_required': True, 'full_library_recall': 'unmeasured',
        'paid_execution_enabled': False}
    write_json(paths() / 'execution_schedule.json', schedule)
    write_json(target, protocol)
    return protocol


def unresolved(sources):
    return [{'path': str(p), 'status': prep.read(p)['status']}
            for root in sources for p in (root / 'journals').glob('*/requests/*.json')
            if prep.read(p)['status'] != 'completed']


def active_evaluations():
    """只看真实进程，不输出命令行；4worker包在运行时本包排队，避免跨进程叠加。"""
    command = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command], capture_output=True, text=True, check=True)
    values = json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(values, dict):
        values = [values]
    markers = ('configs.cle_weekly_reduced_20261028.','configs.cle_weekly_eval_20261027.', 'configs.cle_weekly_gate_20261027.',
               'configs.cle_weekly_fs_20261027.', 'configs.cle_weekly_granularity_20261027.',
               'configs.cle_weekly_granularity_gate_20261027.')
    return [int(v['ProcessId']) for v in values if v.get('CommandLine')
            and any(m in v['CommandLine'] for m in markers)
            and any(x in v['CommandLine'] for x in (' run', ' resume'))]


def work_signature():
    public = prep.read(paths() / 'inputs/public_tasks.json')
    contexts = {p.stem: prep.file_digest(p) for p in (paths() / 'contexts').glob('*.json')}
    selected = prep.selected_cards(prep.source_registry(), public)
    return prep.digest({'contexts': contexts, 'selected': {t: sorted(v) for t, v in selected.items()}})


def check():
    protocol = prepare()
    reasons = []
    if unresolved(segments()):
        reasons.append('unresolved_HTTP_requires_reconciliation')
    try:
        ensure_model_call_allowed(MODEL)
    except ModelTimeWindowError:
        reasons.append('waiting_allowed_time_window')
    active = active_evaluations()
    if active:
        reasons.append('queued_behind_active_four_worker_evaluation')
    gate = paths() / 'execution_offline_checks.json'
    if not gate.exists() or prep.read(gate).get('status') != 'passed':
        reasons.append('execution_offline_checks_pending')
    prior = segments()
    if prior and not unresolved(prior):
        state_file = prior[-1] / 'state.json'
        signature_file = prior[-1] / 'work_signature.json'
        if state_file.exists() and prep.read(state_file).get('status') in ('waiting_new_package_first_initials', 'awaiting_human_confirmation') and signature_file.exists():
            prep.reuse_initials()
            if prep.read(signature_file)['digest'] == work_signature():
                reasons.append('waiting_new_first_initials_or_selected_cards_or_human_review')
    return {'ready': not reasons, 'reasons': reasons, 'active_evaluation_pids': active,
            'planned_tasks': protocol['planned_P7'], 'pair_limit': protocol['pair_limit'], 'new_API_calls': 0}


class RetrievalIO(StudyExecution):
    def wait_allowed(self, prompt=None):
        super().wait_allowed(prompt)
        while active_evaluations():
            self.state['status'] = 'queued_behind_active_four_worker_evaluation'
            self.save('state', self.state)
            self.wait(30)
            super().wait_allowed(prompt)


def seed_cached_vectors(client, texts, cache_paths):
    """只导入精确文本的原向量，旧SQLite只读；一次找全卡和查询缺项再原生批量补齐。"""
    wanted = {_digest(t): t for t in texts}
    remaining = {h for h in wanted if client._load_cached(h) is None}
    for path in cache_paths:
        if not remaining:
            break
        if Path(path).resolve() == Path(client.cache_path).resolve():
            continue
        database = sqlite3.connect(f'file:{Path(path).as_posix()}?mode=ro', uri=True)
        try:
            keys = sorted(remaining)
            for start in range(0, len(keys), 800):
                part = keys[start:start + 800]
                sql = 'SELECT text_hash,vector FROM embeddings WHERE version=? AND model=? AND text_hash IN (' + ','.join('?' for _ in part) + ')'
                rows = database.execute(sql, (CACHE_VERSION, client.model, *part)).fetchall()
                for key, raw in rows:
                    vector = client._validate(json.loads(raw))
                    dimension = len(vector)
                    if client._dimension is not None and client._dimension != dimension:
                        raise ValueError('cached_embedding_dimension_changed')
                    client._dimension = dimension
                    with client._db:
                        client._db.execute('INSERT OR IGNORE INTO dimensions VALUES (?,?,?)', (CACHE_VERSION, client.model, dimension))
                        client._db.execute('INSERT OR IGNORE INTO embeddings VALUES (?,?,?,?)', (CACHE_VERSION, client.model, key, raw))
                    client._vectors[key] = vector
                    remaining.discard(key)
        finally:
            database.close()
    return {'texts': len(wanted), 'missing': len(remaining), 'reused': len(wanted) - len(remaining)}


def saved_labels(sources):
    labels = {}
    for root in sources:
        for path in (root / 'labels').glob('*.json'):
            value = prep.read(path)
            key = value['pair_id']
            if key in labels and labels[key] != value:
                raise ReplayStop('conflicting_saved_label')
            labels[key] = value
    return labels


def parse_label(pair_id, response):
    """有效HTTP但格式错误也封口，记录标注错误，不为格式错误再次购买响应。"""
    try:
        judgment = prep.validate_judgment(_extract_json(_content(response)))
        return {'pair_id': pair_id, **judgment, 'source': 'new_blind_AI_estimate', 'error_type': None}
    except (ValueError, TypeError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return {'pair_id': pair_id, 'label': None, 'source': 'completed_response_label_error_no_retry',
                'error_type': type(exc).__name__}


class RetrievalExecution:
    def __init__(self, sources=(), *, offline=False, destination=None, client_factory=None, physical_open=None):
        prep.verify()
        self.sources = list(map(Path, sources))
        if unresolved(self.sources):
            raise ReplayStop('unresolved_HTTP_must_not_redispatch')
        self.protocol = prepare()
        self.public = prep.read(paths() / 'inputs/public_tasks.json')
        self.nodes = prep.load_memory(Path(prep.read(paths() / 'inputs/protocol.json')['memory_path']))
        self.offline = offline
        self.root = Path(destination) if destination else paths() / f'segment_{len(self.sources)+1:03d}'
        self.labels = saved_labels(self.sources)
        def forbidden(*args, **kwargs):
            raise ReplayStop('zero_API_replay_missing_saved_response')
        if client_factory is None:
            from methods.sct_trajectory import run_closed_loop as native
            def client_factory(identity):
                if offline:
                    return forbidden
                return native._requester(MODEL, 180, 4096, 1, thinking='disabled',
                    max_attempts=1, stream=True, hard_timeout=300, gate_wait_timeout=600,
                    endpoint='https://api.chatanywhere.org/v1/chat/completions')
        direct = __import__('urllib.request', fromlist=['build_opener']).build_opener(
            __import__('urllib.request', fromlist=['ProxyHandler']).ProxyHandler({}))
        protected = [paths() / 'execution_protocol.json', paths() / 'execution_schedule.json',
                     paths() / 'inputs/public_tasks.json', paths() / 'inputs/manifest.json',
                     paths() / 'inputs/input_identity.json', paths() / 'inputs/protocol.json']
        protected += [Path(p) for p in prep.read(paths() / 'inputs/input_identity.json')]
        self.io = RetrievalIO(self.root, {**self.protocol, 'paid_execution_enabled': not offline},
            prep.read(paths() / 'execution_schedule.json'), client_factory=client_factory,
            physical_open=forbidden if offline else physical_open or direct.open,
            protected_paths=protected, live=not offline, fixed_eight=False, resume_sources=self.sources)
        if offline:
            self.io.replay_source = self.root
        for prior in self.sources:
            if prep.read(prior / 'input_identity.json') != self.io.inputs_before:
                raise ReplayStop('frozen_FR_inputs_changed')
            manifest = prep.read(prior / 'used_initials.json') if (prior / 'used_initials.json').exists() else {}
            for path, value in manifest.items():
                if prep.file_digest(path) != value:
                    raise ReplayStop('saved_first_initial_changed')
        self.io.save('input_identity', self.io.inputs_before)
        self.io.save('launch', {'pid': os.getpid(), 'time_utc': now(), 'offline': offline, 'code_generations': 0})
        runtime_files = [Path(__file__), Path(prep.__file__)] + [prep.ROOT / name for name in (
            'configs/cle_v41_relation_20261026/execution.py', 'configs/cle_v41_relation_20261026/wiring.py',
            'configs/cle_v41_migration_20261025/resume.py', 'methods/sct_trajectory/semantic_retrieval.py',
            'methods/sct_trajectory/provider_policy.py', 'methods/sct_trajectory/replay_journal.py',
            'methods/sct_trajectory/wire_recording.py', 'methods/sct_trajectory/run_closed_loop.py',
            'methods/sct_trajectory/agent_pipeline.py', 'methods/sct_trajectory/retrieval_hit_study.py',
            'methods/cle_ablation/runner.py', 'methods/cle_ablation/retrieval_q_metrics.py')]
        identity = {str(p): prep.file_digest(p) for p in runtime_files}
        for prior in self.sources:
            if prep.read(prior / 'source_identity.json') != identity:
                raise ReplayStop('saved_FR_runtime_changed_requires_explicit_reconciliation')
        for source in runtime_files:
            target = self.root / 'source_bundle' / source.relative_to(prep.ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        self.io.save('source_identity', identity)
        from methods.sct_trajectory.run_closed_loop import load_key
        self.embedding = EmbeddingClient(cache_path=self.root / 'embeddings.sqlite3',
            key_loader=forbidden if offline else load_key, semaphore=threading.Semaphore(1),
            timeout=180, hard_timeout=300, gate_wait_timeout=600)
        self.embedding.cache_path = self.root / 'embeddings.sqlite3'
        original = self.embedding._request
        def embedded(texts):
            def call(items):
                if offline:
                    return forbidden()
                before = self.embedding.usage
                vectors = original(items)
                after = self.embedding.usage
                usage = None if after['usage_missing_calls'] > before['usage_missing_calls'] else {
                    k: after[k] - before[k] for k in ('prompt_tokens', 'total_tokens')}
                return {'vectors': vectors, 'usage': usage}
            return self.io.embedding(texts, call)['vectors']
        self.embedding._request = embedded
        self.used_initials = {}

    def one_label(self, pair):
        key = pair['pair_id']
        response = self.io.request_for('label_' + key)(prep.model_judge_prompt({'task': pair['task'], 'card': pair['card']}))
        value = parse_label(key, response)
        self.io.save('labels/' + key, value)
        self.labels[key] = value
        return value

    def build_pools(self):
        prep.reuse_initials()
        contexts = {}
        for tid in self.public:
            path = paths() / 'contexts' / (tid + '.json')
            if path.exists():
                context = prep.read(path)
                if context['public_contract_digest'] != prep.contract_digest(self.public[tid]):
                    raise ReplayStop('saved_initial_public_contract_changed')
                self.used_initials[str(path)] = prep.file_digest(path)
                contexts[tid] = context['initial_analysis']
        self.io.save('used_initials', self.used_initials)
        texts = [card_embedding_text(n) for n in legal_nodes(self.nodes)]
        texts += [query_embedding_text(prep.retrieval_query(self.public[tid], initial, mode))
                  for tid, initial in contexts.items() for mode in prep.MODES]
        unique = list(dict.fromkeys(texts))
        if len(unique) > self.protocol['embedding_text_limit']:
            raise ReplayStop('embedding_text_manifest_cap_exceeded')
        cache_paths = [p / 'embeddings.sqlite3' for p in self.sources] + prep.cache_sources()
        inventory = seed_cached_vectors(self.embedding, unique, cache_paths)
        self.io.save('embedding_inventory', inventory)
        # 卡和查询所有缺项一次交给原生embed，按32条/8万字符自动批量，不逐题碎片购买。
        self.embedding.embed(unique)
        collection = prep.collect(embedding=self.embedding, refresh_initials=False)
        self.io.save('work_signature', {'digest': work_signature()})
        return collection

    def execute(self):
        status = 'running'
        reason = None
        try:
            with self.io.physical_records():
                collection = self.build_pools()
                prep.export_review()
                pairs = prep.read(paths() / 'blind_pairs.json')
                old = {v['pair_id']: v for v in prep.read(paths() / 'reused_AI_labels.json')}
                if len(pairs) > self.protocol['pair_limit']:
                    self.io.stop('AI_pair_budget_cap_exceeded')
                extra = sum(prep.read(p)['extra_selected_count'] for p in (paths() / 'records').glob('*.json'))
                if extra > self.protocol['extra_pair_cap']:
                    self.io.stop('actual_selected_extra_pair_cap_exceeded')
                for pair in pairs:
                    if pair['pair_id'] not in self.labels and pair['pair_id'] not in old:
                        self.one_label(pair)
                status = 'awaiting_human_confirmation' if collection['completed_tasks'] == len(self.public) else 'waiting_new_package_first_initials'
                if self.io.input_state() != self.io.inputs_before:
                    self.io.stop('frozen_FR_inputs_changed')
        except BaseException as exc:
            status = 'stopped_technical'
            reason = self.io.reason or (str(exc) if isinstance(exc, ReplayStop) else type(exc).__name__)
        finally:
            self.embedding._db.close()
            summary = {'status': status, 'reason': reason, 'time_utc': now(), 'code_generations': 0,
                'new_initial_analysis_calls': 0, 'AI_pairs_completed_or_label_error': len(self.labels),
                'AI_label_errors': sum(bool(v.get('error_type')) for v in self.labels.values()),
                'budget': self.io.budget.snapshot(), 'new_physical_HTTP': len(self.io.budget.entries) - self.io.prior_physical_count,
                'inputs_unchanged': self.io.input_state() == self.io.inputs_before,
                'logical': {k: j.summary() for k, j in self.io.journals.items()}}
            self.io.save('summary', summary)
            self.io.save('state', {k: v for k, v in summary.items() if k not in ('budget', 'logical')})
        if status != 'stopped_technical':
            export_human(self.sources + [self.root])
            summarize(self.sources + [self.root])
        return summary


def export_human(sources=None):
    """导出AI提示和人工空白字段；版本文件不覆盖人工已编辑表。"""
    sources = segments() if sources is None else sources
    pairs = prep.read(paths() / 'blind_pairs.json') if (paths() / 'blind_pairs.json').exists() else []
    labels = {v['pair_id']: v for v in prep.read(paths() / 'reused_AI_labels.json')} if (paths() / 'reused_AI_labels.json').exists() else {}
    labels.update(saved_labels(sources))
    target = paths() / f'human_review_AI_{len(labels)}_of_{len(pairs)}.csv'
    if not target.exists():
        with target.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['pair_id', 'task', 'card', 'ai_label', 'ai_reason',
                'ai_error', 'human_label', 'task_evidence', 'card_evidence', 'reason', 'reviewer', 'confirmed_at'])
            writer.writeheader()
            for pair in pairs:
                ai = labels.get(pair['pair_id'], {})
                writer.writerow({'pair_id': pair['pair_id'], 'task': json.dumps(pair['task'], ensure_ascii=False),
                    'card': json.dumps(pair['card'], ensure_ascii=False), 'ai_label': ai.get('label'),
                    'ai_reason': ai.get('reason'), 'ai_error': ai.get('error_type')})
    return {'review_file': str(target), 'human_confirmation': 'not_inferred_or_signed'}


def import_review(path):
    """复用原标签合法性定义；只接受覆盖当前精确题卡池且已裁决的外部人工文件。"""
    prep.verify()
    expected = {p['pair_id'] for p in prep.read(paths() / 'blind_pairs.json')}
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != len(expected) or {r['pair_id'] for r in rows} != expected:
        raise ValueError('human_labels_must_cover_exact_pool_once')
    if not expected:
        raise ValueError('human_review_requires_nonempty_actual_pool')
    labels = []
    for row in rows:
        value = prep.validate_judgment({**row, 'label': row['human_label']})
        if value['label'] == 'insufficient' or not row.get('reviewer', '').strip() or not row.get('confirmed_at', '').strip():
            raise ValueError('human_adjudication_incomplete')
        labels.append({'pair_id': row['pair_id'], **value, 'reviewer': row['reviewer'], 'confirmed_at': row['confirmed_at']})
    target = paths() / 'human_labels.json'
    if target.exists() and prep.read(target) != labels:
        raise ValueError('human_labels_already_imported_preserve_prior_file')
    write_json(target, labels)
    return summarize()


def summarize(sources=None):
    """只测候选池；真实首轮选入编号来自原生行，不把数值Top3冒充原LLM终选。"""
    sources = segments() if sources is None else sources
    records = [prep.read(p) for p in (paths() / 'records').glob('*.json')]
    model = {v['pair_id']: v.get('label') for v in saved_labels(sources).values()}
    prior = paths() / 'reused_AI_labels.json'
    if prior.exists():
        model.update({v['pair_id']: v['label'] for v in prep.read(prior)})
    human_file = paths() / 'human_labels.json'
    human = {v['pair_id']: v['label'] for v in prep.read(human_file)} if human_file.exists() else {}
    universes = {r['task_id']: list(dict.fromkeys(r['pair_ids'])) for r in records}
    estimates = {}
    # 三查询的24+8召回作为召回阶段诊断；最后0-3终选的四指标另按真实实验行统计。
    for mode in prep.MODES:
        candidates = {r['task_id']: list(dict.fromkeys(r['card_to_pair'][i] for i in r['traces'][mode]['candidate_ids'])) for r in records}
        calculated = native_metrics(universes, {t: [] for t in universes}, model, candidates)
        estimates['candidate_recall_' + mode] = {k: calculated[k] for k in
            ('scope', 'complete', 'tasks', 'evaluated_tasks', 'missing_pairs', 'candidate_recall')}
        estimates['candidate_recall_' + mode]['prediction_stage'] = 'not_run_for_query_variant; only candidate_recall_reported'
        estimates['candidate_recall_' + mode]['candidate_recall_reason'] = calculated.get('candidate_recall_reason') or calculated.get('reason')
    by_task = {r['task_id']: r for r in records}
    public = prep.read(paths() / 'inputs/public_tasks.json')
    groups = {}
    for row in prep.selected_cards(prep.source_registry(), public, with_details=True):
        key = row['package'] + ':' + row['condition'] + ':r' + str(row['repeat'])
        group = groups.setdefault(key, {'predictions': {}, 'candidates': {}, 'technical_errors': 0})
        if row['technical_error']:
            group['technical_errors'] += 1
            continue
        tid = row['task_id']
        if tid not in by_task:
            continue
        record = by_task[tid]
        if any(i not in record['card_to_pair'] for i in row['selected_ids']):
            # 新产生的终选必须先collect追加入共同池，不悄悄忽略漏池卡。
            raise ValueError('native_selected_card_missing_from_pool_collect_required')
        predicted = list(dict.fromkeys(record['card_to_pair'][i] for i in row['selected_ids']))
        if tid in group['predictions'] and group['predictions'][tid] != predicted:
            raise ValueError('conflicting_native_first_selection')
        group['predictions'][tid] = predicted
        group['candidates'][tid] = list(dict.fromkeys(record['card_to_pair'][i] for i in row.get('candidate_ids', []) if i in record['card_to_pair']))
    native = {}
    for key, group in groups.items():
        subset = {t: universes[t] for t in group['predictions']}
        native[key] = {'tasks_with_native_selection': len(subset), 'technical_errors': group['technical_errors'],
            'model_assisted_candidate_pool_metrics': native_metrics(subset, group['predictions'], model, group['candidates']),
            'human_candidate_pool_metrics': native_metrics(subset, group['predictions'], human, group['candidates']) if human_file.exists() else None}
    all_pairs = {p for r in records for p in r['pair_ids']}
    human_complete = len(records) == len(public) and bool(all_pairs) and all_pairs <= human.keys()
    result = {'scope': '候选池内', 'full_library_recall': 'unmeasured',
        'planned_tasks': len(prep.read(paths() / 'inputs/public_tasks.json')), 'collected_task_pools': len(records),
        'model_assisted_estimates': estimates, 'native_first_selection_metrics': native,
        'formal_metrics': 'human_labels_complete_native_coverage_reported_separately' if human_complete else 'pending_human_confirmation',
        'human_labels': len(human), 'new_API_calls': 0,
        'note': 'No synthetic Top3 selection; insufficient/missing labels remain unmeasured.'}
    write_json(paths() / 'metrics.json', result)
    return result


def replay():
    """逐条重读实际完整响应并复算标签/向量，不建立网络客户端，不补缺响应。"""
    prior = segments()
    if unresolved(prior):
        raise ReplayStop('unresolved_HTTP_cannot_mark_full_replay_passed')
    for root in prior:
        for path, expected_digest in prep.read(root / 'input_identity.json').items():
            if prep.file_digest(path) != expected_digest:
                raise ReplayStop('frozen_FR_input_changed_before_replay')
    expected = saved_labels(prior)
    checked, embedding_batches = set(), 0
    embedding = prep.CachedOnlyEmbedding([p / 'embeddings.sqlite3' for p in prior] + prep.cache_sources())
    for root in prior:
        for path in (root / 'journals').glob('*/requests/*.json'):
            record = prep.read(path)
            if record['settings']['model'] == 'text-embedding-3-large':
                texts = json.loads(record['prompt'])
                vectors = record['response']['vectors']
                if len(texts) != len(vectors):
                    raise ReplayStop('saved_embedding_count_changed')
                for vector in vectors:
                    EmbeddingClient._validate(None, vector)
                if embedding.embed(texts) != vectors:
                    raise ReplayStop('saved_embedding_response_cache_mismatch')
                embedding_batches += 1
            else:
                key = path.parents[1].name.removeprefix('label_')
                if parse_label(key, record['response']) != expected.get(key):
                    raise ReplayStop('saved_response_label_replay_mismatch')
                checked.add(key)
    pools = list((paths() / 'records').glob('*.json'))
    nodes = prep.load_memory(Path(prep.read(paths() / 'inputs/protocol.json')['memory_path']))
    public = prep.read(paths() / 'inputs/public_tasks.json')
    try:
        for path in pools:
            saved = prep.read(path)
            initial = prep.read(paths() / 'contexts' / (saved['task_id'] + '.json'))['initial_analysis']
            rebuilt, pairs = prep.construct_pool(public[saved['task_id']], initial, nodes, embedding, saved['extra_selected_ids'])
            for key in ('traces', 'eligible_ids', 'initial_pool_count', 'extra_selected_count', 'pair_ids', 'card_to_pair'):
                if rebuilt[key] != saved[key]:
                    raise ReplayStop('candidate_pool_zero_API_replay_mismatch:' + key)
            if pairs != saved['pairs']:
                raise ReplayStop('anonymous_pair_zero_API_replay_mismatch')
    finally:
        embedding.close()
    result = {'status': 'passed' if pools else 'not_started',
        'scope': 'saved_response_and_candidate_consistency; not human label confirmation',
        'full_task_pool_coverage': len(pools) == len(public),
        'completed_AI_responses_replayed': len(checked),
        'embedding_batches_replayed': embedding_batches, 'new_API_calls': 0,
        'candidate_task_pools_replayed': len(pools),
        'code_generations': 0, 'human_confirmation': 'not_inferred'}
    write_json(paths() / 'zero_API_replay.json', result)
    return result


@contextmanager
def execution_lock():
    import msvcrt
    with (paths() / 'execution.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def coordinate(resume=False):
    prepare()
    gate = paths() / 'execution_offline_checks.json'
    if not gate.exists() or prep.read(gate).get('status') != 'passed':
        raise ReplayStop('FR_execution_offline_checks_pending')
    with execution_lock():
        prior = segments()
        if prior and not resume:
            raise ReplayStop('existing_FR_segments_require_resume')
        if unresolved(prior):
            raise ReplayStop('unresolved_HTTP_must_not_redispatch')
        worker = RetrievalExecution(prior)
        write_json(paths() / 'execution_index.json', {'segments': list(map(str, prior)) + [str(worker.root)]})
        return worker.execute()


def launch():
    state = check()
    if not state['ready']:
        write_json(paths() / 'dispatch_queue.json', {**state, 'time_utc': now(), 'new_API_calls': 0})
        return {**state, 'status': 'queued_no_process_started'}
    ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*cle_weekly_retrieval_20261027.execute*' -and ($_.CommandLine -like '* run*' -or $_.CommandLine -like '* resume*') } | Select-Object ProcessId | ConvertTo-Json -Compress"
    actual = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, check=True)
    if actual.stdout.strip():
        return {'status': 'already_running', 'new_API_calls': 0}
    action = 'resume' if segments() else 'run'
    with (paths() / 'stdout.log').open('a', encoding='utf-8') as stdout, (paths() / 'stderr.log').open('a', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
            'configs.cle_weekly_reduced_20261028.retrieval_execute', action], cwd=prep.ROOT,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    result = {'status': 'launched', 'pid': process.pid, 'time_utc': now(), 'action': action}
    write_json(paths() / 'launch.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'check', 'launch', 'run', 'resume', 'replay', 'export-review', 'import-review', 'metrics'))
    parser.add_argument('--labels', type=Path)
    args = parser.parse_args()
    if args.action == 'import-review':
        if args.labels is None:
            parser.error('--labels required')
        result = import_review(args.labels)
    else:
        actions = {'prepare': prepare, 'check': check, 'launch': launch, 'run': coordinate,
                   'resume': lambda: coordinate(True), 'replay': replay, 'export-review': export_human, 'metrics': summarize}
        result = actions[args.action]()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

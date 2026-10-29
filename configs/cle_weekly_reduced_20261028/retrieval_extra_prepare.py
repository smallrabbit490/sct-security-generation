"""FR：精确复用首次初析与向量、构建共同候选池、导出匿名复核材料。

本入口从不创建网络客户端；缓存缺失或公开契约不一致时保留待办，不生成代码。
候选与余弦复用原检索函数，标签沿用原五类定义；人工确认只接受外部CSV导入。
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import random
import sqlite3
import threading
from collections import Counter
from pathlib import Path

from methods.cle_ablation.runner import load_memory, plt_contract
from methods.sct_trajectory.replay_journal import write_json
from methods.sct_trajectory.retrieval_hit_study import (
    blind_pair, digest, make_query, model_judge_prompt, read_rows, validate_judgment)
from methods.sct_trajectory.semantic_retrieval import (
    CACHE_VERSION, EmbeddingClient, _digest, card_embedding_text,
    recall_semantic_candidates)

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
COUNTS = {'D_grow': 27, 'D_gate': 30}
MODES = ('original', 'analysis', 'combined')
SEED = 20261017
PROTOCOL = 'cle-reduced-retrieval-extra57-20261028-v1'
HISTORY = ROOT / 'translation_work/diagnostics/20261017/cle_retrieval_q/public_contract_v2'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def out():
    return RUN / 'FR_EXTRA'


def contract_digest(task):
    return digest(blind_pair(task, {})['task'])


def retrieval_query(public, initial, mode):
    # 与retrieval_q_study.query_for相同，只是输入已是冻结的公开契约。
    if mode == 'combined':
        return {**public, 'threat_analysis': initial, 'current_code': '', 'failure_evidence': {}}
    return make_query(public, initial, mode)


def public_sources():
    return {'D_grow': RUN / 'FG_LABELS/inputs_contract_v2/tasks.json',
            'D_gate': RUN / 'FQ_GATE/inputs_v3/tasks.json'}


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    """完整571题与独立公开契约版本锁定；缺新版本不回退旧学习题面。"""
    inputs = out() / 'inputs'
    if (inputs / 'protocol.json').exists():
        verify()
        return read(inputs / 'protocol.json')
    sources = public_sources()
    missing = [str(p) for p in sources.values() if not p.exists()]
    if missing:
        result = {'status': 'waiting_public_contract_files', 'missing': missing,
                  'paid_dispatch_enabled': False, 'new_API_calls': 0}
        write_json(out() / 'status.json', result)
        return result
    pools = read(RUN / 'manifest.json')['pools']
    tasks, entries, identity = {}, [], {}
    for pool, path in sources.items():
        actual = read(path)
        if isinstance(actual, list):
            actual = {str(t['index']): t for t in actual}
        ids = pools[pool]
        if len(ids) != COUNTS[pool] or set(ids) != set(actual):
            raise ValueError('full_pool_manifest_changed:' + pool)
        identity[str(path)] = file_digest(path)
        for tid in ids:
            if tid in tasks:
                raise ValueError('task_id_cross_pool_collision')
            task = actual[tid]
            tasks[tid] = plt_contract(task)
            entries.append({'task_id': tid, 'pool': pool, 'family_id': task['family_id'],
                            'public_contract_digest': contract_digest(tasks[tid])})
    bank = RUN / 'shared_inputs/memory1939_q0.jsonl'
    identity[str(bank)] = file_digest(bank)
    protocol = {'protocol': PROTOCOL, 'task_count': sum(COUNTS.values()), 'pools': COUNTS,
        'memory_path': str(bank), 'query_modes': list(MODES), 'vector_top_k': 24,
        'lexical_top_k': 8, 'random_unreturned': 16, 'random_seed': SEED,
        'initial_pairs_cap': sum(COUNTS.values()) * 112,
        'actual_selected_outside_pool': 'add eligible missing cards before metrics; extra count separate',
        'initial_policy': 'reuse saved first analysis only under exact public contract; no code regeneration',
        'label_policy': 'five original labels; direct only positive; insufficient awaits adjudication',
        'paid_dispatch_enabled': False, 'AI_max_calls_per_pair': 1,
        'human_confirmation_required': True, 'full_library_recall': 'unmeasured'}
    write_json(inputs / 'public_tasks.json', tasks)
    write_json(inputs / 'manifest.json', entries)
    write_json(inputs / 'input_identity.json', identity)
    write_json(inputs / 'protocol.json', protocol)
    write_json(out() / 'status.json', {'status': 'prepared_zero_API', 'tasks': len(entries),
        'next': 'reuse-initials then collect using cached vectors only', 'new_API_calls': 0})
    return protocol


def verify():
    for path, expected in read(out() / 'inputs/input_identity.json').items():
        if file_digest(path) != expected:
            raise ValueError('FR_input_changed_requires_new_protocol:' + path)


def source_registry():
    """仅扫描明确登记的运行根；不按题号推断题面相同。"""
    specs = []
    for name, task_file in (
        ('FQ_RETEST', RUN / 'FQ_RETEST/inputs/tasks.json'),
        ('FQ_GATE', RUN / 'FQ_GATE/inputs_v3/tasks.json'),
        ('FFS', RUN / 'FFS/inputs/tasks.json'),
        ('FG_LABELS', public_sources()['D_grow']),
        ('FG_GATE', public_sources()['D_gate'])):
        specs.append({'root': RUN / name, 'tasks_file': task_file,
                      'starts': 'segment_*/shared_starts/*.json',
                      'rows': 'segment_*/task_rows/*.json'})
    for checkpoint in ('K1', 'K2', 'K3'):
        specs.append({'root': RUN / 'FQ_LEARN' / checkpoint,
            'tasks_file': RUN / 'shared_inputs/tasks_D_grow.json',
            'starts': 'segment_*/initials/*.json', 'rows': 'segment_*/task_rows/*.json'})
    # 跨模型包尚未落地时保持空源；仅消费其显式bank_sources登记为旧1939正文的条件。
    specs.append({'root': RUN / 'FX_GATE', 'tasks_file': RUN / 'FX_GATE/inputs/tasks.json',
                  'starts': 'segment_*/shared_starts/*.json', 'rows': 'segment_*/task_rows/*.json',
                  'legacy_bank_only': True})
    old = ROOT / 'translation_work/diagnostics/20261026/cle_v41_completion'
    specs.append({'root': old, 'tasks_file': None,
                  'starts': '*/shared_starts/*.json', 'rows': None})
    return specs


def source_tasks(spec):
    path = spec.get('tasks_file')
    if not path or not Path(path).exists():
        return {}
    values = read(path)
    return values if isinstance(values, dict) else {str(t['index']): t for t in values}


def reuse_initials(registry=None):
    """固定先新包后旧包、重复1优先；不用Joint或Q选择初析。"""
    verify()
    tasks = read(out() / 'inputs/public_tasks.json')
    existing = {p.stem: read(p) for p in (out() / 'contexts').glob('*.json')}
    rejected = Counter()
    for spec in registry if registry is not None else source_registry():
        lookup = source_tasks(spec)
        for path in sorted(Path(spec['root']).glob(spec['starts'])):
            item = read(path)
            tid = str(item.get('task_id') or item.get('public_contract', {}).get('task_id') or
                      path.stem.split('_r')[0].removeprefix('K1_').removeprefix('K2_').removeprefix('K3_'))
            if tid not in tasks or tid in existing or item.get('repeat', 1) != 1:
                continue
            public = item.get('public_contract')
            if public is None and tid in lookup:
                public = plt_contract(lookup[tid])
            if public is None or contract_digest(public) != contract_digest(tasks[tid]):
                rejected['public_contract_mismatch_or_unverifiable'] += 1
                continue
            analysis = item.get('initial_analysis')
            if (item.get('error_type') or not isinstance(analysis, dict) or analysis.get('unmeasured') or
                any(not isinstance(analysis.get(k), list) or not analysis[k]
                    for k in ('vulnerability_hypothesis', 'functional_invariants'))):
                rejected['analysis_incomplete'] += 1
                continue
            record = {'task_id': tid, 'public_contract_digest': contract_digest(tasks[tid]),
                      'initial_analysis': analysis, 'source_file': str(path),
                      'source_repeat': 1, 'no_new_API': True}
            write_json(out() / 'contexts' / (tid + '.json'), record)
            existing[tid] = record
    result = {'status': 'initial_reuse_inventory', 'reused': len(existing),
              'waiting_first_initial': sorted(set(tasks) - set(existing)),
              'rejected': dict(rejected), 'new_API_calls': 0}
    write_json(out() / 'initial_reuse.json', result)
    return result


class CachedVectorMissing(ValueError):
    pass


class CachedOnlyEmbedding:
    """只读SQLite缓存；余弦调用原实现，任何缺向量直接待办，绝不联网。"""
    model = 'text-embedding-3-large'
    cosine_scores = EmbeddingClient.cosine_scores

    def __init__(self, paths):
        self.databases = [sqlite3.connect(f'file:{Path(p).as_posix()}?mode=ro', uri=True)
                          for p in paths if Path(p).exists()]
        self._index_lock = threading.Lock()
        self.flight_wait_timeout = 1
        self._matrix_key = self._matrix = None
        self.pending = {}

    def embed(self, texts):
        vectors = []
        for text in texts:
            key = _digest(text)
            found = None
            for database in self.databases:
                found = database.execute('SELECT vector FROM embeddings WHERE version=? AND model=? AND text_hash=?',
                                         (CACHE_VERSION, self.model, key)).fetchone()
                if found:
                    break
            if found is None:
                self.pending[key] = text
                raise CachedVectorMissing('cached_embedding_missing:' + key)
            vectors.append(EmbeddingClient._validate(self, json.loads(found[0])))
        return vectors

    def close(self):
        for database in self.databases:
            database.close()


def cache_sources():
    values = [RUN / 'shared_inputs/embeddings.sqlite3',
              ROOT / 'translation_work/cache/embeddings/cle.sqlite3']
    for spec in source_registry():
        values.extend(sorted(Path(spec['root']).glob('segment_*/embeddings.sqlite3')))
    old = ROOT / 'translation_work/diagnostics/20261026/cle_v41_completion'
    index = old / 'execution_index.json'
    if index.exists():
        values.extend(Path(p) / 'embeddings.sqlite3' for segments in read(index).values() for p in segments)
    return list(dict.fromkeys(p for p in values if p.exists()))


def selected_cards(registry, tasks, *, with_details=False):
    """仅消费明确题面匹配的首次终选；修复轮不是主要检索测量样本。"""
    selected = {tid: set() for tid in tasks}
    details = []
    for spec in registry:
        if not spec.get('rows'):
            continue
        lookup = source_tasks(spec)
        bank_sources = {}
        if spec.get('legacy_bank_only'):
            protocol = Path(spec['root']) / 'inputs/protocol.json'
            if protocol.exists():
                bank_sources = read(protocol).get('bank_sources', {})
        matched_banks = {}
        for path in sorted(Path(spec['root']).glob(spec['rows'])):
            row = read(path)
            tid = str(row.get('task_id'))
            if tid not in tasks or tid not in lookup:
                continue
            if contract_digest(plt_contract(lookup[tid])) != contract_digest(tasks[tid]):
                continue
            if spec.get('legacy_bank_only'):
                source = bank_sources.get(row.get('condition'))
                if not source or not Path(source).exists():
                    continue
                if source not in matched_banks:
                    reference = read(out() / 'inputs/protocol.json')['memory_path']
                    # Q字段不进正文身份；新C41即使撞到同卡编号也不能并入旧库标注。
                    body = lambda p: sorted((n.invariant_id, card_embedding_text(n)) for n in load_memory(Path(p)))
                    matched_banks[source] = body(source) == body(reference)
                if not matched_banks[source]:
                    continue
            attempt = (row.get('attempts') or [{}])[0]
            trace = attempt.get('retrieval_trace') or {}
            ids = trace.get('selected_ids')
            if ids is None:
                ids = [c['invariant_id'] for c in attempt.get('generation', {}).get('retrieved_cards', [])]
            selected[tid].update(map(str, ids))
            details.append({'task_id': tid, 'condition': str(row.get('condition') or row.get('arm') or 'unspecified'),
                'repeat': row.get('repeat', 1), 'package': Path(spec['root']).name,
                'cell_id': row.get('cell_id', path.stem), 'selected_ids': list(map(str, ids)),
                'candidate_ids': list(map(str, trace.get('candidate_ids', []))),
                'selection_status': trace.get('status'),
                'technical_error': trace.get('status') in ('failed', 'error', 'technical_failure'),
                'source_row': str(path)})
    return details if with_details else selected


def construct_pool(task, initial, nodes, embedding, actual_selected=()):
    """三查询24+8联集及固定随机16；追加终选漏池卡并单列，不缩小原池。"""
    traces = {}
    missing = []
    for mode in MODES:
        trace = {'excluded': []}
        try:
            eligible, _, _ = recall_semantic_candidates(retrieval_query(task, initial, mode), nodes, embedding, 3, trace)
        except CachedVectorMissing as exc:
            missing.append(str(exc))
            continue
        traces[mode] = trace
    if missing:
        raise CachedVectorMissing('|'.join(missing))
    union = set().union(*(set(t['candidate_ids']) for t in traces.values()))
    remaining = sorted(set(eligible) - union)
    random_ids = random.Random(f'{SEED}:{task["task_id"]}').sample(remaining, min(16, len(remaining)))
    base = union | set(random_ids)
    unknown = set(actual_selected) - set(eligible)
    if unknown:
        raise ValueError('actual_selection_outside_legal_fixed_bank')
    extras = set(actual_selected) - base
    by_id = {n.invariant_id: n for n in nodes}
    pairs = []
    for identifier in sorted(base | extras):
        pair = blind_pair(task, json.loads(card_embedding_text(by_id[identifier])))
        pair.update(task_id=task['task_id'], card_id=identifier,
                    origin='actual_selected_extra' if identifier in extras else
                    'random_unreturned' if identifier in random_ids else 'retrieval_union')
        pairs.append(pair)
    return {'task_id': task['task_id'], 'traces': traces, 'eligible_ids': sorted(eligible), 'initial_pool_count': len(base),
            'extra_selected_count': len(extras), 'extra_selected_ids': sorted(extras),
            'pair_ids': [p['pair_id'] for p in pairs],
            'card_to_pair': {p['card_id']: p['pair_id'] for p in pairs}}, pairs


def collect(embedding=None, registry=None, *, refresh_initials=True):
    verify()
    tasks = read(out() / 'inputs/public_tasks.json')
    registry = source_registry() if registry is None else registry
    if refresh_initials:
        reuse_initials(registry)
    nodes = load_memory(Path(read(out() / 'inputs/protocol.json')['memory_path']))
    selected = selected_cards(registry, tasks)
    own_embedding = embedding is None
    embedding = CachedOnlyEmbedding(cache_sources()) if own_embedding else embedding
    pending, completed = Counter(), 0
    try:
        for tid, task in tasks.items():
            context = out() / 'contexts' / (tid + '.json')
            if not context.exists():
                pending['initial_analysis'] += 1
                continue
            cached = out() / 'records' / (tid + '.json')
            if cached.exists():
                record = read(cached)
                # 后到达的真实终选卡继续入同一评价池；原三查询和随机16保持不变。
                ids = set(record['card_to_pair']) | selected[tid]
                by_id = {n.invariant_id: n for n in nodes}
                pair_by_card = {p['card_id']: p for p in record['pairs']}
                for identifier in ids - set(pair_by_card):
                    if identifier not in record['eligible_ids']:
                        raise ValueError('actual_selection_outside_legal_fixed_bank')
                    pair = blind_pair(task, json.loads(card_embedding_text(by_id[identifier])))
                    pair.update(task_id=tid, card_id=identifier, origin='actual_selected_extra')
                    pair_by_card[identifier] = pair
                record['pairs'] = [pair_by_card[i] for i in sorted(pair_by_card)]
                record['card_to_pair'] = {p['card_id']: p['pair_id'] for p in record['pairs']}
                record['pair_ids'] = [p['pair_id'] for p in record['pairs']]
                record['extra_selected_ids'] = sorted(p['card_id'] for p in record['pairs'] if p['origin']=='actual_selected_extra')
                record['extra_selected_count'] = len(record['extra_selected_ids'])
            else:
                try:
                    record, pairs = construct_pool(task, read(context)['initial_analysis'], nodes, embedding, selected[tid])
                except CachedVectorMissing:
                    pending['embedding_vectors'] += 1
                    continue
                record.update(pairs=pairs, initial_source=read(context)['source_file'],
                              public_contract_digest=contract_digest(task), protocol=PROTOCOL)
            write_json(cached, record)
            completed += 1
        if own_embedding:
            write_json(out() / 'pending_embeddings.json', {'model': embedding.model,
                'new_API_calls': 0, 'items': [{'text_hash': k, 'public_text': v} for k, v in embedding.pending.items()]})
    finally:
        if own_embedding:
            embedding.close()
    result = {'status': 'candidate_pools_collected' if completed == len(tasks) else 'waiting_cached_inputs',
              'planned_tasks': len(tasks), 'completed_tasks': completed, 'pending': dict(pending),
              'new_API_calls': 0, 'formal_metrics': 'pending_human_confirmation'}
    write_json(out() / 'collection_summary.json', result)
    return result


def label_inventory(pairs, history=HISTORY):
    old_pairs = {p['pair_id']: p for p in read_rows(history / 'pairs.jsonl')}
    labels = {}
    for item in read_rows(history / 'model_labels.jsonl'):
        prior = old_pairs.get(item['pair_id'])
        if prior is None or item.get('error_type'):
            continue
        try:
            valid = validate_judgment(item)
        except ValueError:
            continue
        labels[digest({'task': prior['task'], 'card': prior['card']})] = valid
    result = {}
    for pair in pairs:
        value = labels.get(digest({'task': pair['task'], 'card': pair['card']}))
        if value:
            result[pair['pair_id']] = {'pair_id': pair['pair_id'], **value,
                'source': 'reused_exact_public_pair_AI_estimate', 'original_history': str(history)}
    return result


def export_review():
    """输出盲标jobs及人审空表；仅复用精确旧AI标签，不在此派发标注请求。"""
    verify()
    records = [read(p) for p in sorted((out() / 'records').glob('*.json'))]
    unique = {p['pair_id']: p for record in records for p in record['pairs']}
    pairs = list(unique.values())
    labels = label_inventory(pairs)
    private = [{'pair_id': p['pair_id'], 'task_id': p['task_id'], 'card_id': p['card_id'], 'origin': p['origin']}
               for record in records for p in record['pairs']]
    visible = [{'pair_id': p['pair_id'], 'task': p['task'], 'card': p['card']} for p in pairs]
    for name, data in [('private_pair_mapping.json', private), ('blind_pairs.json', visible),
                       ('reused_AI_labels.json', list(labels.values()))]:
        write_json(out() / name, data)
    jobs = [{'pair_id': p['pair_id'], 'prompt': model_judge_prompt({'task': p['task'], 'card': p['card']}),
             'model': 'deepseek-v4.1-flash-1017', 'max_tokens': 4096,
             'max_physical_HTTP': 1, 'attempted': False} for p in pairs if p['pair_id'] not in labels]
    write_json(out() / 'blind_annotation_jobs.json', jobs)
    target = out() / f'human_review_{len(pairs)}_pairs.csv'
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('w', encoding='utf-8-sig', newline='') as stream:
            fields = ('pair_id', 'task', 'card', 'ai_label', 'ai_reason', 'human_label',
                      'task_evidence', 'card_evidence', 'reason', 'reviewer', 'confirmed_at')
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for pair in visible:
                ai = labels.get(pair['pair_id'], {})
                writer.writerow({'pair_id': pair['pair_id'], 'task': json.dumps(pair['task'], ensure_ascii=False),
                    'card': json.dumps(pair['card'], ensure_ascii=False), 'ai_label': ai.get('label', ''),
                    'ai_reason': ai.get('reason', '')})
    result = {'status': 'blind_materials_exported_pending_AI_dispatch_and_human_confirmation',
        'completed_task_pools': len(records), 'candidate_pairs': len(pairs),
        'reused_exact_AI_labels': len(labels), 'new_AI_jobs_prepared_not_dispatched': len(jobs),
        'human_confirmed': 0, 'formal_metrics': 'pending_human_confirmation',
        'full_library_recall': 'unmeasured', 'new_API_calls': 0,
        'paid_dispatch_enabled': False, 'AI_dispatch_runner': 'separate execute.py; this preparation command never dispatches',
        'budget_proposed_not_authorized_for_dispatch': {'initial_pairs_cap': sum(COUNTS.values())*112,
            'actual_extra_selected_pairs': sum(r['extra_selected_count'] for r in records),
            'AI_HTTP_for_current_jobs_max': len(jobs),
            'AI_conservative_tokens_for_current_jobs': sum(len(j['prompt'].encode('utf-8'))+4096+1024 for j in jobs)},
        'review_file': str(target)}
    write_json(out() / 'review_summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'reuse-initials', 'collect', 'export-review'))
    args = parser.parse_args()
    result = {'prepare': prepare, 'reuse-initials': reuse_initials,
              'collect': collect, 'export-review': export_review}[args.action]()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

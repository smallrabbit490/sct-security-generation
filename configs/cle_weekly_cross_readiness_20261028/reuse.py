"""逐格重放 FFS B0/BM，证明 CROSS E0/C32 的实际提示、代码与原验证结果相同。"""
import argparse
from contextlib import closing, ExitStack
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from unittest.mock import patch

from configs.cle_weekly_cross_20261027.cell import run_cell
from configs.cle_weekly_eval_20261027 import retest as base
from configs.cle_weekly_build_readiness_20261027.compare import stable
from methods.sct_trajectory.replay_journal import RequestJournal, ReplayStop, write_json
from .prepare import OUT, RUN
from .runtime import json_encoding


def forbidden(*args, **kwargs):
    raise ReplayStop('cross_zero_API_network_or_missing_vector')


def ffs_sources():
    return [Path(p) for p in base.read(RUN / 'FFS/execution_index.json')['segments']]


def collect_rows(sources):
    result = {}
    for source in sources:
        for path in (source / 'task_rows').glob('*.json'):
            row = base.read(path)
            if row.get('condition') not in ('B0', 'BM'):
                continue
            key = row['cell_id']
            if key in result and result[key]['row'] != row:
                raise ReplayStop('conflicting_FFS_completed_cell:' + key)
            entry = result.setdefault(key, {'row': row, 'paths': []})
            entry['paths'].append(str(path))
    return result


def shared_start(sources, task, repeat):
    paths = [s / 'shared_starts' / f'{task}_r{repeat}.json' for s in sources]
    values = [(p, base.read(p)) for p in paths if p.exists()]
    if not values:
        raise ReplayStop('cross_FFS_shared_start_missing_or_conflicting')
    for _, value in values:
        if str(value['task_id']) != task or value.get('repeat', repeat) != repeat:
            raise ReplayStop('cross_FFS_repeat_identity_mismatch')
        if any(value[k] != values[0][1][k] for k in ('initial_analysis', 'error_type')):
            raise ReplayStop('cross_FFS_shared_initial_conflict')
    # FFS 在首次终选前先保存初析，恢复段随后补全；仅比较真实共有内容。
    complete = [(p, value) for p, value in values if all(k in value for k in
        ('query', 'public_contract', 'selected_cards', 'retrieval_trace', 'repeat'))]
    if not complete or any(stable(value) != stable(complete[0][1]) for _, value in complete):
        raise ReplayStop('cross_FFS_shared_start_missing_or_conflicting')
    start = complete[-1][1]
    return start, [str(p) for p, _ in values]


def merge_journal(sources, cell, destination):
    journal = RequestJournal(destination, mode='replay')
    paths = []
    for source in sources:
        for path in (source / 'journals' / cell / 'requests').glob('*.json'):
            record = base.read(path)
            if record.get('status') != 'completed':
                continue
            key = record['identity']
            if key in journal.records and journal.records[key] != record:
                if journal.records[key]['response'] != record['response']:
                    raise ReplayStop('cross_conflicting_successful_response')
            journal.records[key] = record
            journal.prior.add(key)
            paths.append(str(path))
    return journal, paths


def compare_attempts(saved, replayed):
    if len(saved['attempts']) != len(replayed['attempts']):
        raise ReplayStop('cross_reuse_attempt_count_changed')
    for left, right in zip(saved['attempts'], replayed['attempts']):
        for key in ('attempt', 'code', 'functional', 'security', 'joint', 'measured', 'generation', 'retrieval_trace'):
            if stable(left.get(key)) != stable(right.get(key)):
                raise ReplayStop('cross_reuse_native_difference:' + key)
    return True


def audit_cell(target, entry, sources, embedding, destination):
    saved = entry['row']
    task = base.read(OUT / 'tasks.json')[target['task_id']]
    expected = 'B0' if target['bank_arm'] == 'E0' else 'BM'
    source_protocol = base.read(RUN / 'FFS/inputs/protocol.json')
    if (target['model_arm'] != 'V41' or saved['condition'] != expected
            or saved['task_id'] != target['task_id'] or saved['repeat'] != target['repeat']
            or str(saved['family_id']) != str(task['family_id']) or saved.get('Q_updates')
            or saved.get('Q_sorting') or saved.get('workflow_arm') != 'P7'
            or saved.get('subset') != 'PLT' or saved.get('protocol') != source_protocol['protocol']):
        raise ReplayStop('cross_reuse_cell_or_P7_identity_mismatch')
    start, start_paths = shared_start(sources, target['task_id'], target['repeat'])
    if start['public_contract'] != base.runner.plt_contract(task):
        raise ReplayStop('cross_reuse_public_contract_changed')
    journal, request_paths = merge_journal(sources, saved['cell_id'], destination / 'requests')
    if any(record['settings'] != base.wiring.SETTINGS for record in journal.records.values()):
        raise ReplayStop('cross_reuse_model_settings_changed')
    request = journal.wrap(lambda: forbidden, base.wiring.SETTINGS)
    from methods.sct_trajectory.retriever import HskTreeRetriever
    from methods.sct_trajectory.hsk_tree import HskTree
    from methods.sct_trajectory.ablation import get_config
    bank = base.runner.load_memory(Path(base.read(OUT / 'protocol.json')['C32_bank']))
    if any(n.q_value or n.q_visits for n in bank):
        raise ReplayStop('cross_reuse_requires_frozen_Q0_bank')

    def retrieve(query):
        engine = HskTreeRetriever(HskTree(), requester=request, ablation=get_config('A7'),
            retrieval_mode='semantic_llm', embedding_client=embedding,
            semantic_delta=None, candidate_order=None)
        cards = engine.search(query, limit=3, pool_nodes=bank)
        return cards, engine.last_hier_trace

    replayed = run_cell(task, target['bank_arm'], copy.deepcopy(start), retrieve, request)
    write_json(destination / 'replayed_native.json', replayed)
    compare_attempts(saved, replayed)
    if journal.prior != journal.consumed:
        raise ReplayStop('cross_reuse_saved_prompts_not_fully_consumed')
    proof = {'status': 'matched', 'cell_id': target['cell_id'], 'task_id': target['task_id'],
        'repeat': target['repeat'], 'bank_arm': target['bank_arm'], 'model_arm': 'V41',
        'source_cell_id': saved['cell_id'], 'source_rows': entry['paths'], 'shared_starts': start_paths,
        'request_evidence': request_paths, 'matched_logical_responses': len(journal.consumed),
        'checks': ['full v3 task', 'P7', 'model/settings', 'repeat', 'shared initial and selection',
                   'all model-visible prompts', 'plan and cards', 'attempt code', 'native F/S/Joint/measured'],
        'new_HTTP': 0, 'cost_owner': 'FFS; no additional FX_GATE charge'}
    write_json(destination / 'reuse_evidence.json', proof)
    return proof


@json_encoding()
def audit(destination, limit=None, resume_from=None):
    destination = Path(destination)
    sources = ffs_sources()
    # 保存源码身份是既有科学不变量，只读核对；活动快照绝不修改。
    for source in sources:
        for relative, digest in base.read(source / 'source_identity.json').items():
            if hashlib.sha256((base.ROOT / relative).read_bytes()).hexdigest() != digest:
                raise ReplayStop('cross_reuse_saved_FFS_source_changed:' + relative)
        for path, digest in base.read(source / 'input_identity.json').items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ReplayStop('cross_reuse_saved_FFS_input_changed:' + path)
    rows = collect_rows(sources)
    schedule = base.read(OUT / 'schedule.json')
    eligible = []
    for cell in schedule:
        if cell['bank_arm'] in ('E0', 'C32'):
            key = f'{cell["task_id"]}_r{cell["repeat"]}_' + ('B0' if cell['bank_arm'] == 'E0' else 'BM')
            if key in rows:
                eligible.append((cell, rows[key]))
    if limit is not None:
        eligible = eligible[:limit]
    destination.mkdir(parents=True, exist_ok=False)
    cache = destination / 'embeddings.sqlite3'
    with closing(sqlite3.connect(f'file:{(sources[-1] / "embeddings.sqlite3").as_posix()}?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(cache)) as dst:
            src.backup(dst)
    from methods.sct_trajectory import semantic_retrieval as semantic
    embedding = semantic.EmbeddingClient(cache_path=cache, key_loader=forbidden,
                                         semaphore=threading.Semaphore(1))
    embedding._request = forbidden
    base.configure_validation()
    proofs, failures = [], []
    previous = {}
    if resume_from:
        for path in base.read(Path(resume_from))['reuse_evidence']:
            proof = base.read(Path(path))
            previous[proof['cell_id']] = (Path(path), proof)
    newly_audited = 0
    try:
        with ExitStack() as stack:
            for name in ('socket.create_connection', 'socket.socket.connect', 'urllib.request.urlopen'):
                stack.enter_context(patch(name, side_effect=forbidden))
            stack.enter_context(patch.object(semantic, 'MAX_SELECTOR_CHARS', 420000))
            for cell, entry in eligible:
                folder = destination / cell['cell_id']
                try:
                    if cell['cell_id'] in previous:
                        path, proof = previous[cell['cell_id']]
                        if proof['status'] != 'matched' or base.read(Path(proof['source_rows'][-1])) != entry['row']:
                            raise ReplayStop('cross_saved_reuse_proof_source_changed')
                        compare_attempts(entry['row'], base.read(path.parent / 'replayed_native.json'))
                        proofs.append({**proof, 'existing_evidence': str(path)})
                        continue
                    newly_audited += 1
                    proofs.append(audit_cell(cell, entry, sources, embedding, folder))
                except ReplayStop as exc:
                    failure = {'cell_id': cell['cell_id'], 'status': 'not_credited', 'reason': str(exc)}
                    failures.append(failure)
                    write_json(folder / 'reuse_failure.json', failure)
    finally:
        embedding._db.close()
    result = {'status': 'passed' if not failures else 'different', 'scope': 'saved completed FFS cells only',
        'planned_reuse': 1192, 'candidate_cells': len(rows), 'checked_cells': len(eligible),
        'matched_cells': len(proofs), 'failed_cells': failures, 'newly_audited_cells': newly_audited,
        'continued_from': str(resume_from) if resume_from else None,
        'reuse_evidence': [p.get('existing_evidence', str(destination / p['cell_id'] / 'reuse_evidence.json')) for p in proofs],
        'new_HTTP': 0, 'source_segments': list(map(str, sources)),
        'not_full_cross_execution': True}
    write_json(destination / 'summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--resume-from')
    args = parser.parse_args()
    result = audit(args.destination, args.limit, args.resume_from)
    print(json.dumps({k: v for k, v in result.items() if k != 'reuse_evidence'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

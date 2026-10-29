"""2026-10-26用户授权后的B03R真实入口；复用已验证接线，不改旧实验。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import urllib.request
from pathlib import Path

from configs.cle_v41_relation_20261026 import wiring
from configs.cle_v41_relation_20261026.execution import StudyExecution, review_from_directory
from methods.sct_trajectory.replay_journal import write_json

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'translation_work/diagnostics/20261026/cle_v41_completion/B03R_relation'
AUTHORITY = 'User 2026-10-26: 本项目的防御性实验风格允许转化为批准基础实验的完整执行，可以调整但是请不要暂停。先完成前期规划好的v4.1转化的完整实验清单'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def inputs(run, resume_sources=()):
    """准备独立新运行，原卡/原题/旧结果只读；不复制凭据或环境快照。"""
    if run.exists():
        raise RuntimeError('existing_run_not_overwritten')
    p = read(ROOT / 'configs/cle_v41_relation_20261026/protocol.json')
    p.update(protocol='cle-v41-file-signature-relation-live-v1', planning_protocol=p['protocol'],
        authorization=AUTHORITY, paid_execution_enabled=True, execution_ready=True,
        status='authorized_live', live_review='Codex reads fresh plan; no user approval required',
        scientific_gate_controls_dispatch=False, originals_preserved=True)
    p['selector_character_limit'] = 420000
    p['transport_amendment'] = '2026-10-26: original 180000 local char cap rejected unchanged 190305-char selector before HTTP; permit full original 24+8 candidates up to 420000 chars, same output budget.'
    p['resume_sources'] = [str(p) for p in resume_sources]
    return p, read(ROOT / 'configs/cle_v41_relation_20261026/schedule.json')


def worker(run, resume_sources=()):
    p, cells = inputs(run, resume_sources)
    from methods.cle_ablation import runner
    from methods.sct_trajectory import run_closed_loop as native
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    import methods.sct_trajectory.semantic_retrieval as semantic
    semantic.MAX_SELECTOR_CHARS = p['selector_character_limit']
    slots = threading.Semaphore(4)
    direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def client(identity):
        return native._requester(wiring.SETTINGS['model'], 180, 4096, 4, thinking='disabled',
            stream=True, endpoint='https://api.chatanywhere.org/v1/chat/completions',
            hard_timeout=300, gate_wait_timeout=600, semaphore=slots)
    protected = [ROOT / p['memory'], ROOT / p['previous_snapshot']]
    control = StudyExecution(run, p, cells, client_factory=client, physical_open=direct.open,
        reviewer=review_from_directory(run / 'plan_reviews/imported'), protected_paths=protected,
        live=True, review_wait=True, resume_sources=resume_sources)
    for prior in resume_sources:
        for review in (Path(prior)/'plan_reviews/imported').glob('*.review.json'):
            destination=run/'plan_reviews/imported'/review.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(review,destination)
    write_json(run / 'launch.json', {'pid': os.getpid(), 'model': wiring.SETTINGS['model'],
        'authorization': AUTHORITY, 'command': ['-m', 'configs.cle_v41_relation_20261026.live', 'worker'],
        'git_head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'branch': subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip()})
    source = run / 'source_bundle'
    for directory in ('methods', 'src', 'configs/cle_v41_relation_20261026', 'configs/cle_v41_migration_20261025'):
        for path in (ROOT / directory).rglob('*.py'):
            target = source / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    (run / 'inputs').mkdir()
    shutil.copy2(ROOT / p['memory'], run / 'inputs/memory.jsonl')
    task = next(t for t in read(ROOT / p['previous_snapshot']) if str(t['index']) == '1409')
    write_json(run / 'inputs/tasks.json', [task])
    nodes = runner.load_memory(run / 'inputs/memory.jsonl')
    assert len(nodes) == 1939
    seed = Path(resume_sources[-1])/'embeddings.sqlite3' if resume_sources else ROOT / 'translation_work/diagnostics/20261025/cle_v41_public_binding_v2/embeddings.sqlite3'
    cache = run / 'embeddings.sqlite3'
    with sqlite3.connect(f'file:{seed.as_posix()}?mode=ro', uri=True) as src:
        with sqlite3.connect(cache) as dest:
            src.backup(dest)
    embedding = EmbeddingClient(cache_path=cache, key_loader=native.load_key, semaphore=slots,
                               timeout=180, hard_timeout=300, gate_wait_timeout=600)
    original = embedding._request
    def embedded(texts):
        def call(items):
            before = embedding.usage
            vectors = original(items)
            after = embedding.usage
            usage = None if after['usage_missing_calls'] > before['usage_missing_calls'] else {
                k: after[k] - before[k] for k in ('prompt_tokens','total_tokens')}
            return {'vectors': vectors, 'usage': usage}
        return control.embedding(texts, call)['vectors']
    embedding._request = embedded
    state = control.run(task, wiring.native_selector(nodes, embedding))
    rows = list(control.rows)
    (run / 'rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    write_json(run / 'summary.json', {'status': state['status'], 'completed_P7': len(rows),
        'planned_P7': 8, 'Q_updates': 0, 'cards_generated': 0,
        'arms': {arm: {'completed': len([r for r in rows if r['relation_arm']==arm]),
            'joint': sum(bool(r['attempts'][-1].get('joint')) for r in rows if r['relation_arm']==arm),
            'measured': sum(bool(r['attempts'][-1].get('measured')) for r in rows if r['relation_arm']==arm)}
            for arm in p['arms']}, 'physical_cost': control.budget.snapshot()})
    print(json.dumps(state, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['worker'])
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--resume-source', type=Path, action='append', default=[])
    args = parser.parse_args()
    worker(args.run.resolve(),args.resume_source)


if __name__ == '__main__':
    main()

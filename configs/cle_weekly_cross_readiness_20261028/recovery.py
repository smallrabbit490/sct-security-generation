"""新段恢复前检查真实 journal/wire，并零 API 走到精确缺失请求边界。"""
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_eval_20261027 import retest as base
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .runtime import CrossNewBank, json_encoding
from .reuse import forbidden, compare_attempts


def physical_match(source, record):
    """沿用现有恢复判据，实际查看流字节；完成、认证/额度和无法分类的响应一律不补发。"""
    matches = []
    for request in (source / 'wire').glob('*.request.json'):
        body = base.read(request)['body']
        messages = body.get('messages', [])
        if (body.get('model') != record['settings']['model'] or len(messages) != 1
                or messages[0].get('content') != record['prompt']):
            continue
        status = request.with_name(request.name.replace('.request.json', '.status.json'))
        raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
        if status.exists():
            matches.append((base.read(status), raw))

    def interrupted(status, raw):
        if (status.get('status') == 'transport_error' and status.get('http_status') is None
                and status.get('error_type') in ('URLError', 'RemoteDisconnected', 'TimeoutError',
                    'ConnectionResetError', 'ConnectionAbortedError') and not raw.exists()):
            return True
        if not (status.get('status') == 'response_read_error' and status.get('http_status') == 200
                and status.get('error_type') == 'ValueError' and raw.exists()):
            return False
        chunks = 0
        try:
            for raw_line in raw.read_bytes().splitlines():
                line = raw_line.decode('utf-8').strip()
                if not line.startswith('data:'):
                    continue
                data = line[5:].strip()
                if data == '[DONE]':
                    return False
                chunk = json.loads(data)
                if chunk.get('error'):
                    return False
                if any(c.get('index', 0) == 0 and c.get('finish_reason') is not None for c in chunk.get('choices', [])):
                    return False
                chunks += 1
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError):
            return False
        return chunks > 0
    return bool(matches) and all(interrupted(status, raw) for status, raw in matches)


def classify(sources):
    records = [(Path(s), p, base.read(p)) for s in sources
               for p in (Path(s) / 'journals').glob('*/requests/*.json')]
    completed = {(p.parent.parent.name, row['identity']) for _, p, row in records if row['status'] == 'completed'}
    pending = {}
    for source, path, row in records:
        key = path.parent.parent.name, row['identity']
        if row['status'] == 'completed' or key in completed:
            continue
        if row['settings']['model'] not in (base.wiring.SETTINGS['model'], 'text-embedding-3-large'):
            raise ReplayStop('cross_pending_model_mismatch')
        if key[0] == 'embedding':
            matches = []
            for request in (source / 'wire').glob('*.request.json'):
                body = base.read(request)['body']
                if body.get('model') == 'text-embedding-3-large' and body.get('input') == json.loads(row['prompt']):
                    status = request.with_name(request.name.replace('.request.json', '.status.json'))
                    raw = request.with_name(request.name.replace('.request.json', '.response.raw'))
                    if status.exists():
                        matches.append((base.read(status), raw))
            valid = bool(matches) and all(s.get('status') == 'transport_error' and s.get('http_status') is None
                and s.get('error_type') in ('URLError', 'RemoteDisconnected', 'TimeoutError',
                    'ConnectionResetError', 'ConnectionAbortedError') and not raw.exists() for s, raw in matches)
        else:
            valid = any(d.get('category') == 'network_error' for d in row.get('diagnostics', [])) and physical_match(source, row)
        if row['status'] != 'failed_or_unresolved' or not valid:
            raise ReplayStop('cross_nontransport_unresolved_requires_inspection:' + str(path))
        public = {k: row[k] for k in ('settings', 'prompt', 'selector')}
        if key in pending and pending[key]['public'] != public:
            raise ReplayStop('cross_pending_payload_conflict')
        item = pending.setdefault(key, {'public': public, 'evidence': []})
        item['evidence'].append(str(path))
    return pending


def request_identity(journal, prompt, settings):
    public = {'settings': settings, 'prompt': str(prompt), 'selector': type(prompt).__name__ == 'SelectorPrompt'}
    key = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f'{key}-{journal.counts[key] + 1:06d}', public


def authorize_pending(study, pending):
    """先消费保存成功前缀；首次新请求必须与该 cell 已核实的未决请求逐字一致。"""
    original = study.io.request_for

    def request_for(cell):
        call = original(cell)
        remaining = {identity: value for (namespace, identity), value in pending.items() if namespace == cell}

        def guarded(prompt):
            journal = study.io.journal(cell)
            identity, public = request_identity(journal, prompt, base.wiring.SETTINGS)
            if identity not in journal.records and remaining:
                if identity not in remaining or remaining[identity]['public'] != public:
                    raise ReplayStop('cross_new_request_before_verified_pending:' + cell)
                old = remaining.pop(identity)
                study.io.save('authorized_pending/' + cell, {'identity': identity,
                    'old_failures': old['evidence'], 'unknown_usage_preserved': True,
                    'authorization': 'user 2026-10-27 18:31; same TLS/network interruption'})
            return call(prompt)
        return guarded
    study.io.request_for = request_for
    original_embedding = study.io.embedding
    embedding_pending = {identity: value for (cell, identity), value in pending.items() if cell == 'embedding'}

    def embedding(texts, call):
        if embedding_pending:
            expected = [value for value in embedding_pending.values() if json.loads(value['public']['prompt']) == texts]
            if len(expected) != 1:
                raise ReplayStop('cross_embedding_before_verified_pending')
            matching = next(key for key, value in embedding_pending.items() if value is expected[0])
            embedding_pending.pop(matching)
        return original_embedding(texts, call)
    study.io.embedding = embedding


@json_encoding()
def probe(sources, destination):
    sources = list(map(Path, sources))
    pending = classify(sources)
    boundary = {}
    with patch.object(base, 'unresolved_requests', return_value=[]), \
         patch('socket.create_connection', side_effect=forbidden), \
         patch('socket.socket.connect', side_effect=forbidden):
        study = CrossNewBank(sources, offline=True, destination=Path(destination))
        original = study.io.request_for

        def request_for(cell):
            call = original(cell)
            def wrapped(prompt):
                try:
                    return call(prompt)
                except ReplayStop as exc:
                    if str(exc).startswith('replay_missing_request:'):
                        boundary.update(cell=cell, identity=str(exc).split(':', 1)[1],
                            public={'settings': base.wiring.SETTINGS, 'prompt': str(prompt),
                                    'selector': type(prompt).__name__ == 'SelectorPrompt'})
                    raise
            return wrapped
        study.io.request_for = request_for
        def embedded(texts):
            try:
                return study.io.embedding(texts, forbidden)['vectors']
            except ReplayStop as exc:
                if str(exc).startswith('replay_missing_request:'):
                    boundary.update(cell='embedding', identity=str(exc).split(':', 1)[1],
                        public={'settings': {'model': 'text-embedding-3-large', 'operation': 'embedding'},
                                'prompt': json.dumps(texts, ensure_ascii=False), 'selector': False})
                raise
        study.embedding._request = embedded
        known_cells = {p.parent.parent.name for s in sources
                       for p in (s / 'journals').glob('*/requests/*.json')}
        boundaries, errors = [], []
        try:
            for cell in study.cells:
                if cell['cell_id'] not in known_cells and cell['cell_id'] not in study.saved_rows:
                    continue
                boundary.clear()
                study.io.reason = None
                try:
                    start = study.start(study.tasks[cell['task_id']], cell['repeat'])
                    row = study.one(cell, start)
                    if cell['cell_id'] in study.saved_rows:
                        compare_attempts(study.saved_rows[cell['cell_id']], row)
                except ReplayStop as exc:
                    if boundary and str(exc).startswith('replay_missing_request:'):
                        boundaries.append(dict(boundary))
                    else:
                        errors.append(str(exc))
            outcome = ('replay_missing_request:' + boundaries[0]['identity'] if boundaries else
                       'complete_saved_response_replay' if not errors else errors[0])
        finally:
            study.embedding._db.close()
        calls = len(list((Path(destination) / 'wire').glob('*.request.json')))
        valid = not errors
        reached = set()
        for item in boundaries:
            key = item['cell'], item['identity']
            reached.add(key)
            if key in pending and pending[key]['public'] != item['public']:
                valid = False
            elif key not in pending and any(k[0] == key[0] for k in pending):
                valid = False
        if not set(pending) <= reached:
            valid = False
        result = {'status': 'passed' if valid and calls == 0 else 'different',
            'source_segments': list(map(str, sources)), 'completed_replayed_cells': len(study.rows),
            'pending': [{'cell': k[0], 'identity': k[1], 'evidence': v['evidence']} for k, v in pending.items()],
            'boundary': {k: v for k, v in (boundaries[0] if boundaries else {}).items() if k != 'public'},
            'boundaries': [{k: v for k, v in item.items() if k != 'public'} for item in boundaries],
            'errors': errors, 'stopped_at': outcome,
            'new_HTTP': calls, 'original_records_modified': False,
            'budget': {k: v for k, v in study.io.budget.snapshot().items() if k != 'entries'}}
        write_json(Path(destination) / 'prefix_probe.json', result)
        return result

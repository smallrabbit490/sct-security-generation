"""Classify saved build requests before any authorized transport reissue."""
import runpy
import json
from pathlib import Path

from .prepare_inputs import RUN
from methods.sct_trajectory.replay_journal import ReplayStop


def classify_sources(sources):
    helper = RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'
    physical_match = runpy.run_path(str(helper))['physical_match']
    records = []
    for source in map(Path, sources):
        for path in (source / 'journals').glob('*/requests/*.json'):
            records.append((source, path.parent.parent.name, json.loads(path.read_text(encoding='utf-8'))))
    completed = {(cell, row['identity']) for _, cell, row in records if row.get('status') == 'completed'}
    pending = {}
    for source, cell, row in records:
        key = cell, row['identity']
        if row.get('status') == 'completed' or key in completed:
            continue
        if row.get('status') != 'failed_or_unresolved':
            raise ReplayStop('build_has_nontransport_or_unclassifiable_unresolved_requests')
        if cell == 'embedding':
            matches = []
            texts = json.loads(row['prompt'])
            for request in (source / 'wire').glob('*.request.json'):
                body = json.loads(request.read_text(encoding='utf-8')).get('body', {})
                if body.get('model') != 'text-embedding-3-large' or body.get('input') != texts:
                    continue
                status = request.with_name(request.name.replace('.request.json', '.status.json'))
                response = request.with_name(request.name.replace('.request.json', '.response.raw'))
                if status.exists():
                    matches.append((json.loads(status.read_text(encoding='utf-8')), response.exists()))
            valid = bool(matches) and all(s.get('status') == 'transport_error' and s.get('http_status') is None
                and s.get('error_type') in ('URLError', 'RemoteDisconnected', 'TimeoutError',
                                             'ConnectionResetError', 'ConnectionAbortedError') and not raw
                for s, raw in matches)
        else:
            valid = cell.startswith('native_') and any(d.get('category') == 'network_error'
                    for d in row.get('diagnostics', [])) and physical_match(source, row)
        if not valid:
            raise ReplayStop('build_has_nontransport_or_unclassifiable_unresolved_requests')
        public = {field: row[field] for field in ('settings', 'prompt', 'selector')}
        if key in pending and pending[key][0] != public:
            raise ReplayStop('conflicting_build_pending_request')
        pending.setdefault(key, []).append(public)
    return pending

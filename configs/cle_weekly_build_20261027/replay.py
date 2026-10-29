"""Replay a completed native build without credentials or network calls."""
import argparse
import json
import sqlite3
from pathlib import Path

from .prepare_inputs import RUN, read
from .physical_guard import physical_guard
from .native_adapter import run_native, native
from .recovery_inputs import verify_input_snapshot, verify_source_snapshot, recovery_arguments
from .recovery_plan import classify_sources
from .completion import verify_native_outputs
from .replay_compare import compare
from methods.sct_trajectory import replay_journal
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

BUILD = RUN / 'BUILD_C41'


def replay(sources, original, destination, *, entry=None):
    sources = [Path(path) for path in sources]
    original, destination = Path(original), Path(destination)
    if not sources or destination.exists():
        raise ReplayStop('build_replay_requires_sources_and_fresh_destination')
    for source in sources:
        verify_source_snapshot(source)
        verify_input_snapshot(source)
    if classify_sources(sources):
        raise ReplayStop('build_replay_has_unresolved_requests')

    def forbidden(*args, **kwargs):
        raise ReplayStop('unexpected_network_or_credential_access_during_replay')

    io = physical_guard(destination / 'execution', read(BUILD / 'budget.json')['budget_proposed'],
                        forbidden, resume_sources=sources)
    io.wait_allowed = lambda prompt=None: None
    cache = destination / 'embeddings.sqlite3'
    original_cache = BUILD / 'embeddings.sqlite3'
    if original_cache.exists():
        with sqlite3.connect(original_cache) as source_db, sqlite3.connect(cache) as dest_db:
            source_db.backup(dest_db)
    arguments = recovery_arguments(read(BUILD / 'native_arguments.json')['arguments'],
                                   destination / 'native', cache)
    old_key, old_window = native.load_key, replay_journal.ensure_model_call_allowed
    native.load_key = forbidden
    replay_journal.ensure_model_call_allowed = lambda *args, **kwargs: None
    try:
        run_native(io, arguments, entry=entry)
    finally:
        native.load_key, replay_journal.ensure_model_call_allowed = old_key, old_window
    if list((io.root / 'wire').glob('*.request.json')):
        raise ReplayStop('unexpected_physical_request_during_build_replay')
    expected = set()
    for source in sources:
        for path in (source / 'journals').glob('native_*/requests/*.json'):
            record = json.loads(path.read_text(encoding='utf-8'))
            if record.get('status') == 'completed':
                expected.add((path.parent.parent.name, record['identity']))
    consumed = {(cell, identity) for cell, journal in io.journals.items()
                if cell.startswith('native_') for identity in journal.consumed}
    if expected != consumed:
        raise ReplayStop('build_replay_did_not_consume_all_saved_model_responses')
    verification = verify_native_outputs(destination / 'native', read(RUN / 'manifest.json')['pools'])
    comparison = compare(original, destination / 'native')
    result = {'status': comparison['status'], 'new_HTTP': 0,
              'native_verification': verification, 'comparison': comparison,
              'model_responses_replayed': len(consumed),
              'embedding_scope': 'cache may satisfy requests without reading saved vector journal',
              'saved_segments': [str(path) for path in sources],
              'original_native_output': str(original), 'replayed_native_output': str(destination / 'native')}
    write_json(destination / 'replay_result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', action='append', required=True)
    parser.add_argument('--original', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    print(json.dumps(replay(args.source, args.original, args.destination), ensure_ascii=False))


if __name__ == '__main__':
    main()

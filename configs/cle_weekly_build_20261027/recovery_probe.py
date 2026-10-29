"""Replay a saved native build prefix to one unresolved request without API access."""
import sqlite3
from pathlib import Path

from .prepare_inputs import RUN, read
from .physical_guard import physical_guard
from .native_adapter import run_native, native
from .recovery_plan import classify_sources
from .recovery_inputs import verify_source_snapshot, verify_input_snapshot, recovery_arguments
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from methods.sct_trajectory import replay_journal

BUILD = RUN / 'BUILD_C41'


def probe(sources, destination, *, entry=None):
    sources = [Path(p) for p in sources]
    destination = Path(destination)
    for source in sources:
        verify_source_snapshot(source)
        verify_input_snapshot(source)
    pending = classify_sources(sources)
    if not pending:
        raise ReplayStop('build_probe_requires_unresolved_request')
    if destination.exists():
        raise ReplayStop('build_probe_destination_already_exists')

    def forbidden(*args, **kwargs):
        raise ReplayStop('unexpected_network_or_credential_access_during_probe')

    budget = read(BUILD / 'budget.json')['budget_proposed']
    io = physical_guard(destination / 'execution', budget, forbidden, resume_sources=sources)
    # A probe never sends a request; it need not wait for a paid-call window.
    io.wait_allowed = lambda prompt=None: None
    cache = destination / 'embeddings.sqlite3'
    original_cache = BUILD / 'embeddings.sqlite3'
    if original_cache.exists():
        with sqlite3.connect(original_cache) as source_db, sqlite3.connect(cache) as dest_db:
            source_db.backup(dest_db)
    args = recovery_arguments(read(BUILD / 'native_arguments.json')['arguments'],
                              destination / 'native', cache)
    old_key, old_window = native.load_key, replay_journal.ensure_model_call_allowed
    native.load_key = forbidden
    replay_journal.ensure_model_call_allowed = lambda *args, **kwargs: None
    try:
        try:
            run_native(io, args, entry=entry, pending=pending, probe=True)
            outcome = 'unexpected_completion'
        except ReplayStop as exc:
            outcome = str(exc)
    finally:
        native.load_key, replay_journal.ensure_model_call_allowed = old_key, old_window
    wire = len(list((io.root / 'wire').glob('*.request.json')))
    targets = [(cell, identity) for cell, identity in pending
               if outcome == 'replay_missing_request:' + cell + ':' + identity]
    target = targets[0] if len(targets) == 1 else None
    result = {'status': 'passed' if target is not None and wire == 0 else 'different',
              'pending_cell': target[0] if target else None,
              'pending_identity': target[1] if target else None, 'pending_count': len(pending),
              'stopped_at': outcome, 'new_HTTP': wire,
              'saved_segments': [str(p) for p in sources]}
    write_json(destination / 'probe_result.json', result)
    return result

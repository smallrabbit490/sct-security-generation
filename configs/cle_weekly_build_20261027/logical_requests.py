"""Journal native CLE model and embedding calls without altering prompts."""
from contextlib import contextmanager
import json
import hashlib
import threading

from configs.cle_v41_relation_20261026 import wiring
from methods.sct_trajectory import run_closed_loop as native
from methods.sct_trajectory import semantic_retrieval as semantic
from methods.sct_trajectory.replay_journal import ReplayStop
from configs.cle_weekly_recovery_20261027.recover import request_identity
from .task_scope import CURRENT_TASK


def check_replay_ambiguity(journal):
    """Do not silently assign distinct responses to identical parallel calls."""
    responses = {}
    for identity in journal.prior:
        record = journal.records[identity]
        key = identity.rsplit('-', 1)[0]
        responses.setdefault(key, set()).add(json.dumps(record['response'], sort_keys=True, ensure_ascii=True))
    if any(len(values) > 1 for values in responses.values()):
        raise ReplayStop('identical_prompt_distinct_responses_require_task_attribution')


@contextmanager
def logical_requests(execution, *, pending=None, probe=False, authorized_target=None):
    pending = dict(pending or {})
    original_factory = native._requester
    original_embedding = semantic.EmbeddingClient._request
    records = []
    for source in execution.resume_sources:
        for path in (source / 'journals').glob('*/requests/*.json'):
            record = json.loads(path.read_text(encoding='utf-8'))
            records.append(((path.parent.parent.name, record['identity']), record['status']))
    completed = {key for key, status in records if status == 'completed'}
    if any(status != 'completed' and key not in pending and key not in completed
           for key, status in records):
        raise ReplayStop('build_unresolved_request_requires_exact_prefix_recovery')
    journals = {}
    lock = threading.Lock()
    scope_locks = {}
    remaining = {cell: {identity: rows for (key, identity), rows in pending.items() if key == cell}
                 for cell, _ in pending}

    def factory(model, timeout, max_tokens=4096, max_inflight=0, **kwargs):
        if model != wiring.SETTINGS['model'] or max_tokens != 4096:
            raise ValueError('build_model_or_budget_mismatch')
        kwargs.update(thinking='disabled', stream=True,
                      endpoint='https://api.chatanywhere.org/v1/chat/completions',
                      hard_timeout=300, gate_wait_timeout=600)
        def request(prompt):
            scope = CURRENT_TASK.get() or 'global'
            key = 'native_' + hashlib.sha256(scope.encode('utf-8')).hexdigest()
            client_key = (key, model, timeout, max_tokens, max_inflight,
                          json.dumps(kwargs, sort_keys=True, default=str))
            with lock:
                if client_key not in journals:
                    journal = execution.journal(key)
                    if execution.resume_sources:
                        check_replay_ambiguity(journal)
                    execution.save('scope_map/' + key, {'scope': scope})
                    journals[client_key] = (journal, journal.wrap(lambda: original_factory(model, max(timeout, 180),
                                                                   max_tokens, max_inflight, **kwargs), wiring.SETTINGS))
                journal, wrapped = journals[client_key]
                guard_lock = scope_locks.setdefault(key, threading.RLock())
            execution.wait_allowed(prompt)
            with guard_lock:
                waiting = remaining.get(key, {})
                identity, public = request_identity(journal, prompt)
                if waiting and identity not in journal.records:
                    if identity not in waiting:
                        raise ReplayStop('new_request_before_authorized_pending:' + key)
                    prior = waiting[identity][0]
                    if public != {field: prior[field] for field in ('settings', 'prompt', 'selector')}:
                        raise ReplayStop('authorized_request_payload_changed:' + key)
                    if probe:
                        raise ReplayStop('replay_missing_request:' + key + ':' + identity)
                    if authorized_target is not None and (key, identity) != authorized_target:
                        raise ReplayStop('other_build_pending_requires_probe:' + key + ':' + identity)
                    execution.save('authorized_boundary/' + key + '_' + identity,
                                   {'scope': scope, 'identity': identity, 'previous_usage_unknown': True})
                    del waiting[identity]
                response = wrapped(prompt)
            if response.get('model') != wiring.SETTINGS['model']:
                execution.stop('reported_model_mismatch')
            return response
        return request

    def embedding(client, texts):
        def call(items):
            before = dict(client.usage)
            vectors = original_embedding(client, items)
            usage = {k: client.usage.get(k, 0) - before.get(k, 0)
                     for k in ('prompt_tokens', 'total_tokens')}
            return {'vectors': vectors, 'usage': usage}
        with lock:
            guard_lock = scope_locks.setdefault('embedding', threading.RLock())
        with guard_lock:
            journal = execution.journal('embedding')
            public = {'settings': {'model': 'text-embedding-3-large', 'operation': 'embedding'},
                      'prompt': json.dumps(texts, ensure_ascii=False), 'selector': False}
            digest = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            identity = f'{digest}-{journal.counts[digest] + 1:06d}'
            waiting = remaining.get('embedding', {})
            if waiting and identity not in journal.records:
                if identity not in waiting:
                    raise ReplayStop('new_embedding_before_authorized_pending')
                prior = waiting[identity][0]
                if public != {field: prior[field] for field in ('settings', 'prompt', 'selector')}:
                    raise ReplayStop('authorized_embedding_payload_changed')
                if probe:
                    raise ReplayStop('replay_missing_request:embedding:' + identity)
                if authorized_target is not None and ('embedding', identity) != authorized_target:
                    raise ReplayStop('other_build_pending_requires_probe:embedding:' + identity)
                execution.save('authorized_boundary/embedding_' + identity,
                               {'identity': identity, 'previous_usage_unknown': True})
                del waiting[identity]
            return execution.embedding(texts, call)['vectors']

    native._requester = factory
    semantic.EmbeddingClient._request = embedding
    try:
        yield
    finally:
        native._requester = original_factory
        semantic.EmbeddingClient._request = original_embedding

"""原CLE冷启动前两题有界探针；不进入主动回放与全局门控。"""
import argparse
import json
from pathlib import Path
import shutil
import time
from unittest.mock import patch
import urllib.request

from configs.cle_weekly_build_20261027.execute import BUILD, snapshot_sources
from configs.cle_weekly_build_20261027.native_adapter import run_native
from configs.cle_weekly_build_20261027.physical_guard import physical_guard
from configs.cle_weekly_build_20261027.prepare_inputs import RUN, read
from configs.cle_model_baseline_20261024.execute import record_validations
from methods.sct_trajectory.closed_loop import CleRunner
from methods.sct_trajectory.replay_journal import write_json, ReplayStop

OUT = RUN / 'probe_relay_20261028/BUILD.run'
IDS = ['45', '46']


class PrefixComplete(BaseException):
    pass


def prepare():
    args = read(BUILD / 'native_arguments.json')['arguments']
    args = list(args)
    args[args.index('--out')+1] = str(OUT / 'native')
    args[args.index('--embedding-cache')+1] = str(OUT / 'embeddings.sqlite3')
    value = {'arguments': args, 'tasks': IDS, 'source_task_limit': 2,
        'continuation_after_phase1': False, 'Q_updates': 0,
        'budget': {'conservative_model_and_embedding_tokens': 600000,
            'total_physical_HTTP_attempts': 160, 'embedding_HTTP_attempts_included_in_total': 64}}
    p = OUT / 'protocol.json'
    if p.exists():
        assert read(p) == value
    else:
        write_json(p, value)
    return value


def execute(check_only=False):
    protocol = prepare()
    destination = OUT / ('offline_scope_check_' + str(time.time_ns()) if check_only else 'segment_001')
    if destination.exists():
        raise ReplayStop('existing_probe_segment_requires_saved_response_reconciliation')
    original = CleRunner.phase1_seed
    def bounded(runner, tasks, *args, **kwargs):
        io.save('actual_source_prefix', {'first_two': [str(t['index']) for t in tasks[:2]], 'planned': IDS})
        if [str(t['index']) for t in tasks[:2]] != IDS:
            raise ReplayStop('native_source_prefix_does_not_match_fixed_ids')
        if runner.experience_pool:
            raise ReplayStop('cold_start_experience_pool_not_empty')
        if check_only:
            write_json(destination / 'scope_checks.json', {'status': 'passed', 'task_ids': IDS,
                'empty_experience_pool': True, 'phase2_not_entered': True, 'new_HTTP': 0})
            raise PrefixComplete()
        result = original(runner, tasks[:2], *args, **kwargs)
        write_json(destination/'native_phase1_result.json', result)
        nodes = [n.to_dict() for n in runner.experience_pool]
        write_json(destination/'experience_pool_snapshot.json', nodes)
        write_json(destination/'error_ledger_snapshot.json', runner.ledger.to_jsonl())
        write_json(OUT/'summary.json', {'status': 'native_two_task_prefix_complete_pending_replay_analysis',
            'completed': len(result['results']), 'planned': 2, 'task_ids': IDS,
            'cards_produced': len(nodes), 'full_library_complete': False, 'Q_updates': 0})
        raise PrefixComplete()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': 'http://127.0.0.1:7897'}))
    def forbidden(*args, **kwargs):
        raise ReplayStop('offline_scope_check_forbids_network')
    io = physical_guard(destination, protocol['budget'], forbidden if check_only else opener.open, live=not check_only)
    snapshot_sources(destination)
    shutil.copy2(__file__, destination / 'bounded_entry.py')
    record_validations(destination, 'PLT')
    try:
        arguments = list(protocol['arguments'])
        arguments[arguments.index('--out')+1] = str(destination/'native')
        with patch.object(CleRunner, 'phase1_seed', bounded):
            run_native(io, arguments)
    except PrefixComplete:
        io.save('state', {'status': 'scope_check_passed' if check_only else 'prefix_complete_pending_analysis',
                          'new_experiment_HTTP': 0 if check_only else 'see_budget'})
    except BaseException as exc:
        io.save('state', {'status': 'needs_technical_recovery', 'error': str(exc)})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['check', 'run'])
    a = p.parse_args()
    execute(a.action == 'check')


if __name__ == '__main__':
    main()

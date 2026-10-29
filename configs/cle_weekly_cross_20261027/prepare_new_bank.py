"""Prepare the matched V4.1/new-bank arm once both real dependencies finish."""
import argparse
import hashlib
import json
from pathlib import Path

from configs.cle_weekly_eval_20261027 import retest as base
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .prepare import RUN, read
from .shared_initials import collect

OUT = RUN / 'FX_GATE/V41_C41/inputs'


def dependencies():
    reasons = []
    certificate = RUN / 'BUILD_C41/verified_library.json'
    if not certificate.exists():
        reasons.append('C41_real_build_and_replay_not_verified')
    else:
        item = read(certificate)
        bank = Path(item['bank_path'])
        if (item.get('status') != 'verified_native_primary_replay' or not bank.is_file()
                or hashlib.sha256(bank.read_bytes()).hexdigest() != item.get('bank_sha256')):
            reasons.append('C41_certificate_or_bank_mismatch')
    index = RUN / 'FFS/execution_index.json'
    sources = [Path(p) for p in read(index)['segments']] if index.exists() else []
    if not sources or not (sources[-1] / 'summary.json').exists():
        reasons.append('FFS_not_completed')
    else:
        summary = read(sources[-1] / 'summary.json')
        if summary.get('status') != 'completed' or summary.get('completed') != 2980:
            reasons.append('FFS_not_completed')
    replay = RUN / 'FFS/zero_API_replay/replay_result.json'
    if not replay.exists() or read(replay).get('status') != 'passed':
        reasons.append('FFS_replay_not_passed')
    analysis = RUN / 'FFS/analysis/summary.json'
    if not analysis.exists() or read(analysis).get('status') != 'completed':
        reasons.append('FFS_analysis_not_completed')
    return {'ready': not reasons, 'reasons': reasons, 'API_calls': 0}


def prepare():
    check = dependencies()
    if not check['ready']:
        raise ReplayStop('cross_dependencies_pending:' + ','.join(check['reasons']))
    if OUT.exists():
        raise ReplayStop('cross_new_bank_inputs_already_frozen')
    certificate = read(RUN / 'BUILD_C41/verified_library.json')
    bank = Path(certificate['bank_path'])
    tasks = read(RUN / 'FQ_GATE/inputs_v3/tasks.json')
    ids = list(map(str, read(RUN / 'manifest.json')['pools']['D_gate']))
    sources = [Path(p) for p in read(RUN / 'FFS/execution_index.json')['segments']]
    initials = collect(sources, ids)
    all_cells = read(RUN / 'FX_GATE/inputs/schedule.json')
    cells = [{**cell, 'condition': 'C41'} for cell in all_cells
             if cell['model_arm'] == 'V41' and cell['bank_arm'] == 'C41']
    if len(cells) != 596 or len(initials) != 596 or set(tasks) != set(ids):
        raise ReplayStop('cross_new_bank_manifest_incomplete')
    cards = base.runner.load_memory(bank)
    if len(cards) != certificate['card_count']:
        raise ReplayStop('cross_new_bank_card_count_mismatch')
    cap = {'conservative_model_and_embedding_tokens': 596 * 150000,
           'total_physical_HTTP_attempts': 596 * 40,
           'embedding_HTTP_attempts_included_in_total': 596 * 16}
    protocol = {'protocol': 'cle-weekly-cross-v41-new-bank-20261027-v1',
        'planned_P7': 596, 'card_count': len(cards), 'bank_sources': {'C41': str(bank)},
        'model_settings': base.wiring.SETTINGS, 'max_cards': 3, 'max_repairs': 1,
        'Q_updates': 0, 'Q_sorting': False, 'shared_initial_source': 'FFS task and repeat',
        'budget_proposed': cap, 'budget_basis': 'existing FQ 150000 tokens / 40 HTTP / 16 embedding per P7',
        'budget_is_actual_cost': False, 'V32_access': 'unavailable', 'paid_execution_enabled': False}
    OUT.mkdir(parents=True)
    write_json(OUT / 'tasks.json', tasks)
    write_json(OUT / 'schedule.json', cells)
    write_json(OUT / 'shared_initials.json', initials)
    write_json(OUT / 'protocol.json', protocol)
    write_json(OUT / 'bank_certificate.json', certificate)
    return {'status': 'inputs_prepared_execution_not_started', 'cells': len(cells),
            'shared_initials': len(initials), 'bank_cards': len(cards), 'API_calls': 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['check', 'prepare'])
    args = parser.parse_args()
    print(json.dumps(dependencies() if args.action == 'check' else prepare(), ensure_ascii=False))


if __name__ == '__main__':
    main()

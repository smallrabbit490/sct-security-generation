"""冻结 v4.1 全部逻辑格及新增 C41 有限预算；新库到齐前只做零 API 准备。"""
import argparse
import json
from pathlib import Path

from configs.cle_weekly_eval_20261027 import retest as base
from configs.cle_weekly_cross_20261027.prepare_new_bank import dependencies
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

RUN = base.RUN
OUT = RUN / 'FX_GATE/v41_wiring'
CAP = {'conservative_model_and_embedding_tokens': 89400000,
       'total_physical_HTTP_attempts': 23840,
       'embedding_HTTP_attempts_included_in_total': 9536}


def freeze(path, value):
    if path.exists():
        if base.read(path) != value:
            raise ReplayStop('cross_frozen_wiring_changed:' + str(path))
    else:
        write_json(path, value)


def prepare():
    cross = base.read(RUN / 'FX_GATE/inputs/protocol.json')
    tasks = base.read(Path(cross['tasks']))
    ids = list(map(str, base.read(RUN / 'manifest.json')['pools']['D_gate']))
    schedule = [c for c in base.read(RUN / 'FX_GATE/inputs/schedule.json') if c['model_arm'] == 'V41']
    if (len(ids) != 298 or set(ids) != set(tasks) or len(schedule) != 1788
            or len({c['cell_id'] for c in schedule}) != 1788):
        raise ReplayStop('cross_v41_fixed_manifest_mismatch')
    for tid in ids:
        for repeat in (1, 2):
            cells = [c for c in schedule if c['task_id'] == tid and c['repeat'] == repeat]
            if {c['bank_arm'] for c in cells} != {'E0', 'C32', 'C41'} or any(
                    str(c['family_id']) != str(tasks[tid]['family_id']) for c in cells):
                raise ReplayStop('cross_v41_cell_identity_mismatch')
    source = base.read(RUN / 'FFS/inputs/protocol.json')
    if (base.read(RUN / 'FFS/inputs/tasks.json') != tasks
            or source['model_settings'] != base.wiring.SETTINGS
            or source['max_cards'] != 3 or source['max_repairs'] != 1):
        raise ReplayStop('cross_FFS_fixed_contract_mismatch')
    if cross['max_cards'] != 3 or cross['max_repairs'] != 1 or any(
            p.get('Q_updates') or p.get('Q_sorting') for p in (source, cross)):
        raise ReplayStop('cross_original_P7_or_Q_boundary_mismatch')
    bank = Path(cross['bank_arms']['C32'])
    if bank.resolve() != Path(source['bank_sources']['BM']).resolve():
        raise ReplayStop('cross_C32_bank_mismatch')
    freeze(OUT / 'schedule.json', schedule)
    freeze(OUT / 'tasks.json', tasks)
    freeze(OUT / 'budget.json', {'package': 'FX_GATE', 'scope': 'V41_C41_only_596_new_cells',
        'budget_proposed': CAP, 'reset_on_resume': False, 'transferable': False,
        'basis': '596 x existing 150000 token / 40 physical HTTP / 16 embedding HTTP P7 engineering cap',
        'E0_C32': '1192 exact FFS cells; zero new requests, costs remain charged to FFS',
        'unknown_usage': 'retain prior physical attempts and conservative unknown bounds',
        'V32': 'unavailable; no request budget or model substitution', 'currency_cost': None})
    freeze(OUT / 'protocol.json', {'protocol': 'cle-cross-v41-wiring-20261028-v1',
        'planned': 1788, 'per_bank': 596, 'task_count': 298, 'repeats': 2,
        'model_settings': base.wiring.SETTINGS, 'max_cards': 3, 'max_repairs': 1,
        'Q_updates': 0, 'Q_sorting': False, 'method': 'P7',
        'tasks_source': cross['tasks'], 'C32_bank': str(bank),
        'C41_bank': 'BUILD_C41/verified_library.json; native primary replay required before binding',
        'reuse': {'E0': 'FFS B0', 'C32': 'FFS BM'},
        'reuse_requires': 'actual per-cell original P7 saved-response replay with matching prompts, settings, repeat, cards, code and validation',
        'new_paid_cells': 596, 'workers_max': 3, 'no_performance_stop': True,
        'execution_command': 'configs.cle_weekly_cross_readiness_20261028.execute launch --workers 3'})
    return {'status': 'prepared_zero_API', 'planned': 1788, 'new_cells': 596,
            'budget': CAP, 'dependencies': dependencies(), 'API_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare'])
    parser.parse_args()
    print(json.dumps(prepare(), ensure_ascii=False))


if __name__ == '__main__':
    main()

"""Check shared fixed inputs before attempting per-cell cross-arm reuse."""
import json
from pathlib import Path

from configs.cle_v41_relation_20261026.wiring import SETTINGS
from methods.sct_trajectory.replay_journal import write_json
from .prepare import RUN, read


def audit():
    source = read(RUN / 'FFS/inputs/protocol.json')
    cross = read(RUN / 'FX_GATE/inputs/protocol.json')
    source_tasks = read(RUN / 'FFS/inputs/tasks.json')
    target_tasks = read(Path(cross['tasks']))
    expected_bank = Path(cross['bank_arms']['C32'])
    source_bank = Path(source['bank_sources']['BM'])
    checks = {
        'tasks_exactly_equal': source_tasks == target_tasks and len(source_tasks) == 298,
        'model_settings_equal': source['model_settings'] == SETTINGS,
        'cards_cap_equal': source['max_cards'] == cross['max_cards'] == 3,
        'repair_cap_equal': source['max_repairs'] == cross['max_repairs'] == 1,
        'Q_disabled': not source['Q_updates'] and not source['Q_sorting']
                      and not cross['Q_updates'] and not cross['Q_sorting'],
        'same_existing_bank_path': source_bank.resolve() == expected_bank.resolve() and expected_bank.is_file(),
    }
    return {'status': 'static_checks_passed' if all(checks.values()) else 'static_mismatch',
            'checks': checks, 'credited_cells': 0, 'API_calls': 0,
            'not_yet_verified': ['cross executor finalized', 'per-cell model-visible prompt equivalence',
                                 'per-cell selection and repair trace', 'validation and result integrity'],
            'interpretation': 'static input compatibility only; does not authorize reuse by itself'}


def main():
    result = audit()
    write_json(RUN / 'FX_GATE/reuse_static_audit.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

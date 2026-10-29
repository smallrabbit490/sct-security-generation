"""Freeze the cross-model D_gate manifest; no model calls or score inference."""
import json
from pathlib import Path

from methods.sct_trajectory.replay_journal import write_json

RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
OUT = RUN / 'FX_GATE/inputs'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    if OUT.exists():
        raise SystemExit('cross_inputs_already_exist')
    ids = list(map(str, read(RUN / 'manifest.json')['pools']['D_gate']))
    tasks = read(RUN / 'FQ_GATE/inputs_v3/tasks.json')
    if len(ids) != 298 or len(set(ids)) != 298 or set(ids) != set(tasks):
        raise SystemExit('cross_requires_exact_v3_D_gate')
    arms = [(model, bank) for model in ('V32', 'V41') for bank in ('E0', 'C32', 'C41')]
    schedule = [{'cell_id': f'{task}_r{repeat}_{model}_{bank}', 'task_id': task,
                 'family_id': str(tasks[task]['family_id']), 'repeat': repeat,
                 'model_arm': model, 'bank_arm': bank}
                for task in ids for repeat in (1, 2) for model, bank in arms]
    if len(schedule) != 3576 or len({cell['cell_id'] for cell in schedule}) != 3576:
        raise SystemExit('cross_manifest_invalid')
    OUT.mkdir(parents=True)
    write_json(OUT / 'schedule.json', schedule)
    write_json(OUT / 'protocol.json', {
        'protocol': 'cle-weekly-cross-model-cards-20261027-v1',
        'tasks': str(RUN / 'FQ_GATE/inputs_v3/tasks.json'), 'task_count': 298,
        'repeats': 2, 'planned_cells': 3576, 'method': 'P7',
        'model_arms': {'V32': 'deepseek-v3.2', 'V41': 'deepseek-v4.1-flash-1017'},
        'model_access': {'V32': 'unavailable_user_confirmed', 'V41': 'configured'},
        'bank_arms': {'E0': 'empty', 'C32': str(RUN / 'shared_inputs/memory1939_q0.jsonl'),
                      'C41': 'await BUILD_C41 verified frozen library'},
        'Q_sorting': False, 'Q_updates': False, 'max_cards': 3, 'max_repairs': 1,
        'metric': 'functional_and_security_joint',
        'reuse_candidates': {'V41_E0': 'FFS B0', 'V41_C32': 'FFS BM'},
        'reuse_rule': 'candidate only; compare full task, protocol, prompt, model, bank and repeat before credit',
        'status': 'inputs_frozen_runner_and_budget_not_ready', 'completed_cells': 0, 'API_calls': 0,
    })
    print(json.dumps({'tasks': len(ids), 'cells': len(schedule), 'completed_cells': 0,
                      'new_API_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

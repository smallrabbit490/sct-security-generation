"""Verify native build outputs before treating the run as complete."""
import json
from pathlib import Path

from methods.sct_trajectory.replay_journal import ReplayStop


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ReplayStop('build_required_output_missing:' + str(path))
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def verify_native_outputs(output, pools, *, rounds=3):
    output = Path(output)
    phase1 = rows(output / 'phase1_results.jsonl')
    final = rows(output / 'final_eval.jsonl')
    completed_rounds = rows(output / 'completed_rounds.jsonl')
    memory = rows(output / 'frozen/m_star.jsonl')
    for actual, expected, label in ((phase1, pools['D_init'], 'phase1'),
                                    (final, pools['D_gate'], 'final_eval')):
        ids = [str(row['task_id']) for row in actual]
        if len(ids) != len(set(ids)) or set(ids) != set(map(str, expected)):
            raise ReplayStop('build_output_task_coverage_mismatch:' + label)
    round_ids = [int(row.get('round', 0)) for row in completed_rounds]
    if round_ids != list(range(1, rounds + 1)):
        raise ReplayStop('build_output_round_coverage_mismatch')
    for name in ('global_gate_report.json', 'summary.json', 'cost.json'):
        if not (output / name).is_file():
            raise ReplayStop('build_required_output_missing:' + name)
    return {'status': 'native_outputs_complete_pending_replay_and_analysis',
            'phase1_tasks': len(phase1), 'completed_rounds': round_ids,
            'final_eval_tasks': len(final), 'frozen_cards': len(memory)}

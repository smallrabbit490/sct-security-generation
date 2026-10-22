"""复算12题同题选入/采用变化、新卡奖励与停止结论；不改变原成绩。"""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_dinit_coverage as s


def main():
    summary = s.read(s.OUT / 'summary.json')
    items = s.records()
    mapping = {(r['arm'], r['task_id']): r for r in items}
    manifest = s.read(s.OUT / 'manifest.json')
    pairs, model_errors = [], []
    for identifier in manifest['probe']:
        pair = [mapping[(arm, identifier)] for arm in ('L0', 'L1')]
        selection = [{c['invariant_id'] for c in r['attempts'][0].get('generation', {}).get('retrieved_cards', [])} for r in pair]
        adoption = [{c['invariant_id'] for c in r['attempts'][0].get('generation', {}).get('cards', [])} for r in pair]
        pairs.append({'task_id': identifier, 'family_id': pair[0]['family_id'],
                      'first_selected_set_changed': selection[0] != selection[1],
                      'first_adopted_set_changed': adoption[0] != adoption[1],
                      'L0_first_selected': '|'.join(sorted(selection[0])), 'L1_first_selected': '|'.join(sorted(selection[1])),
                      'L0_first_adopted': '|'.join(sorted(adoption[0])), 'L1_first_adopted': '|'.join(sorted(adoption[1])),
                      'L0_joint': pair[0]['final']['joint'], 'L1_joint': pair[1]['final']['joint']})
    for r in items:
        for a in r['attempts']:
            g = a.get('generation', {})
            if not g.get('workflow_completed'):
                model_errors.append({'arm': r['arm'], 'task_id': r['task_id'], 'attempt': a['attempt'],
                                     'error_type': g.get('error_type'),
                                     'degraded_stages': [v['stage'] for v in g.get('stages', []) if v['status'] in {'degraded', 'failed'}],
                                     'F_S_measured': a.get('measured'), 'Q_credit_allowed': False})
    with (s.CURATED / 'paired_mechanisms.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(pairs[0]))
        writer.writeheader()
        writer.writerows(pairs)
    s.write(s.CURATED / 'model_workflow_errors.json', model_errors)
    new_rewards = {}
    for arm, stats in summary['arms'].items():
        new_rewards[arm] = {}
        for policy, c in stats['credit'].items():
            new_ids = set(c['new_card_ids'])
            path = s.OUT / arm / policy / 'memory_q_events.jsonl'
            with path.open(encoding='utf-8') as stream:
                events = [json.loads(line) for line in stream if line.strip()]
            new_events = [e for e in events if e['credited'] and e['invariant_id'] in new_ids]
            new_rewards[arm][policy] = {'new_cards': len(new_ids),
                'positive_new_cards': len({e['invariant_id'] for e in new_events if e['reward'] > 0}),
                'negative_new_cards': len({e['invariant_id'] for e in new_events if e['reward'] < 0}),
                'new_card_reward_events': dict(Counter('positive' if e['reward'] > 0 else 'negative' for e in new_events))}
    meta = s.read(s.OUT / 'run_metadata.json')
    result = {'status': 'STOP_COVERAGE_GATE_NOT_MET', 'P7_runs': len(items), 'unique_tasks': len(pairs),
              'code_attempts': sum(len(r['attempts']) for r in items),
              'first_selected_set_changed': sum(r['first_selected_set_changed'] for r in pairs),
              'first_adopted_set_changed': sum(r['first_adopted_set_changed'] for r in pairs),
              'L1_joint_rescues': sum(not r['L0_joint'] and r['L1_joint'] for r in pairs),
              'L1_joint_losses': sum(r['L0_joint'] and not r['L1_joint'] for r in pairs),
              'new_card_rewards': new_rewards, 'model_workflow_errors': model_errors,
              'LLM_usage': summary['cost']['LLM'],
              'embedding': {k: sum(e[k] for e in summary['cost']['embedding']) for k in ('calls', 'total_tokens', 'failures', 'usage_missing_calls')},
              'segments': meta['segments'], 'actual_CNY': None,
              'next60_dispatch_block_verified_no_new_API': True,
              'not_executed': ['60task_extension', '296task_extension', 'new_Dgate', 'Base/Plus'],
              'interpretation': 'L1 expands raw visits more, but new cross-family coverage below6, gain1 below3, and zero new-cross Joint families. Does not establish Q benefit or universal ineffectiveness.'}
    s.write(s.CURATED / 'experiment_closeout.json', result)
    print({k: result[k] for k in ('status', 'P7_runs', 'unique_tasks', 'code_attempts', 'first_selected_set_changed', 'first_adopted_set_changed', 'L1_joint_rescues', 'L1_joint_losses')})


if __name__ == '__main__':
    main()

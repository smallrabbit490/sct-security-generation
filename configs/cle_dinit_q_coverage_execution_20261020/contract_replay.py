"""本轮新发现的契约缺口单独屏蔽回放；原题、原分数和原协议Q库均不改写。"""
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from methods.cle_ablation import run_memory_q_dinit_coverage as study


def main():
    finding = study.read(study.OUT / 'observed_contract_defects.json')
    excluded = {r['task_id'] for r in finding['findings']}
    manifest = study.read(study.OUT / 'manifest.json')
    source = study.load_memory(study.OUT / 'input_memory.jsonl')
    origins = study.read(study.OUT / 'origins.json')
    rows = study.records()
    result = {'analysis': 'posthoc_contract_qualification_sensitivity_not_new_generation',
              'excluded_task_ids': sorted(excluded), 'old_scores_modified': False,
              'raw_protocol_banks_modified': False, 'new_API_calls': 0, 'arms': {}}
    for arm in ('L0', 'L1'):
        trusted = copy.deepcopy([r for r in rows if r['arm'] == arm and r['task_id'] not in excluded])
        for row in trusted:
            for a in row.get('attempts', []):
                if not a.get('measured') or (a['attempt'] == 0 and row.get('shared_initial_error')):
                    a.setdefault('generation', {})['workflow_completed'] = False
        result['arms'][arm] = {'retained_tasks': len(trusted), 'credit': {}}
        for policy in ('all_feedback', 'cross_family'):
            nodes, events, stats = study.credit_rows(trusted, source, origins, manifest, policy)
            folder = study.OUT / 'diagnostic_contract_screened' / arm / policy
            study._write_memory(folder / 'frozen/m_star_q.jsonl', nodes)
            for event in events:
                event.update(protocol=study.PROTOCOL, qualification='posthoc_contract_screened', arm=arm)
            study.jsonl(folder / 'memory_q_events.jsonl', events)
            study.write(folder / 'summary.json', stats)
            result['arms'][arm]['credit'][policy] = stats
    study.write(study.OUT / 'diagnostic_contract_screened/summary.json', result)
    study.write(study.CURATED / 'contract_qualification_sensitivity.json', result)
    print({a: {p: {'new_cards': s['new_cards'], 'updates': s['valid_updates']}
               for p, s in v['credit'].items()} for a, v in result['arms'].items()})


if __name__ == '__main__':
    main()

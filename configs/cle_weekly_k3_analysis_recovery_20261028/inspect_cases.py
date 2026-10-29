"""导出并展示K3代表题的题面、实际卡片、计划、代码、验证和Q证据。"""
import json
import sys

from configs.cle_weekly_analysis_20261027.analysis import RUN, collect_rows, read, write


def export():
    out = RUN / 'analysis/K3'
    tasks = read(RUN / 'shared_inputs/tasks_D_grow.json')
    ids = read(RUN / 'manifest.json')['pools']['D_grow']
    rows, paths, _ = collect_rows(read(RUN / 'execution_index.json')['FQ_LEARN_K3'], ids)
    keys = {c['task_id'] for c in read(out / 'case_review_queue.json')}
    rescues = [r['task_id'] for r in rows if not r['attempts'][0]['joint'] and r['final']['joint']]
    keys.update(rescues)
    for row in rows:
        key = row['task_id']
        if key in keys:
            write(out / 'case_evidence' / f'{key}.json', {
                'task': tasks[key], 'row': row, 'row_path': paths[key],
                'task_source': str(RUN / 'shared_inputs/tasks_D_grow.json'),
                'bank_source': str(RUN / 'FQ_LEARN/frozen/K2.jsonl')})
    print(json.dumps({'exported': sorted(keys), 'rescue_tasks': rescues}, ensure_ascii=False))


def show(keys):
    for key in keys:
        item = read(RUN / 'analysis/K3/case_evidence' / f'{key}.json')
        row = item['row']
        print('\nTASK', key, json.dumps(item['task'], ensure_ascii=False))
        seen = set()
        for attempt in row['attempts']:
            gen = attempt['generation']
            print('ATTEMPT', attempt['attempt'])
            for card in gen.get('retrieved_cards', []):
                if card['invariant_id'] in seen:
                    continue
                seen.add(card['invariant_id'])
                fields = ('invariant_id', 'high_level_invariant', 'applicability', 'fix_directive')
                print('CARD', json.dumps({k: card.get(k) for k in fields}, ensure_ascii=False))
            print('ADOPTION', json.dumps(gen.get('adoption'), ensure_ascii=False))
            print('ADAPTATIONS', json.dumps({k: gen.get('experience_analysis', {}).get(k)
                  for k in ('adaptations', 'rejected_experiences')}, ensure_ascii=False))
            print('PLAN', json.dumps({k: v for k, v in (gen.get('plan_parsed') or {}).items()
                                      if k != 'Verification_Plan'}, ensure_ascii=False))
            print('CODE\n' + attempt['code'])
            print('VALIDATION', json.dumps(attempt['validation'], ensure_ascii=False))
            print('FLAGS', {k: attempt.get(k) for k in ('functional', 'security', 'joint', 'measured')},
                  'GEN_ERROR', gen.get('error_type'), 'COMPLETED', gen.get('workflow_completed'))
        print('REWARD_ELIGIBLE', row['reward_eligible'])
        print('Q', json.dumps(row['q_credit_events'], ensure_ascii=False))


if __name__ == '__main__':
    if sys.argv[1:] == ['export']:
        export()
    else:
        show(sys.argv[1:])

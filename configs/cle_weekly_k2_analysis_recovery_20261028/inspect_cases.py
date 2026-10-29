"""展示已经导出的K2案例原生证据，去除重复的候选审计字段便于实际阅读。"""
import json
import sys

from configs.cle_weekly_analysis_20261027.analysis import RUN, read


def main():
    for key in sys.argv[1:]:
        item = read(RUN / 'analysis/K2/case_evidence' / f'{key}.json')
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
            plan = gen.get('plan_parsed') or {}
            print('PLAN', json.dumps({k: v for k,v in plan.items() if k != 'Verification_Plan'}, ensure_ascii=False))
            print('CODE\n' + attempt['code'])
            print('VALIDATION', json.dumps(attempt['validation'], ensure_ascii=False))
            print('FLAGS', {k: attempt.get(k) for k in ('functional', 'security', 'joint', 'measured')},
                  'GEN_ERROR', gen.get('error_type'), 'COMPLETED', gen.get('workflow_completed'))
        print('REWARD_ELIGIBLE', row['reward_eligible'])
        print('Q', json.dumps(row['q_credit_events'], ensure_ascii=False))


if __name__ == '__main__':
    main()

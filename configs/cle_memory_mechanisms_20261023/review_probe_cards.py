"""按已阅读的实际正文分区两题历史入选的六张卡；只审组织，不替卡片有效性背书。"""
from __future__ import annotations

import json
from pathlib import Path

from methods.cle_ablation.memory_view_study import example_spec
from methods.sct_trajectory.memory_views import draft_view, source_projection, apply_memory_view

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1/B01'
ROWS = ROOT / 'translation_work/diagnostics/20261020/cle_q_online_v1/D_grow/rows.jsonl'


def reviewed_spec(card, tid):
    identifier = card['invariant_id']
    if identifier in ['pitfall-1333-1465610006318670494', 'pitfall-179-7247804407684050276']:
        return example_spec(card, tid)
    source = source_projection(card)
    spec = draft_view(card)
    segments = []
    for item in spec['segments']:
        field = item['path'][0]
        text = source[field] if isinstance(source[field], str) else None
        def whole(role):
            segments.append({**item, 'role': role})
        def split(points):
            cursor = 0
            for end, role in points:
                segments.append({**item, 'start': cursor, 'end': end, 'role': role})
                cursor = end
            assert cursor == len(text)
        if field in ('applicability', 'language_leaf'):
            whole('context')
        elif field == 'negative_guardrail':
            whole('security' if identifier == 'cand-179-6365112243198787786' else 'functional')
        elif field in ('high_level_invariant', 'positive_principle'):
            if identifier == 'cand-1333-4003705983803461794':
                if field == 'high_level_invariant':
                    whole('security')
                else:
                    first = text.index('ensure the security')
                    second = text.index('does not reject')
                    third = text.index('through a three-layer')
                    split([(first, 'functional'), (second, 'security'),
                           (third, 'functional'), (len(text), 'security')])
            elif identifier == 'hint-1333-1962473956307884958':
                first = text.index(' This modification does not break functionality')
                split([(first, 'security'), (len(text), 'functional')])
            elif identifier == 'cand-179-6365112243198787786':
                if field == 'high_level_invariant':
                    whole('security')
                else:
                    first = text.index(', keeping')
                    split([(first, 'security'), (len(text), 'functional')])
            elif identifier == 'pitfall-179-8712527076461853948':
                whole('functional')
            else:
                raise ValueError('unreviewed card')
        elif field == 'root_cause':
            marker = ('The current approach' if identifier.startswith('hint-1333') else
                      'The failure reason' if identifier.startswith('pitfall-179') else 'The reason')
            first = text.index(marker)
            split([(first, 'context'), (len(text), 'functional' if identifier.startswith('pitfall-179') else 'security')])
        elif field == 'fix_directive':
            if identifier == 'cand-1333-4003705983803461794':
                first = text.index(' These changes must not alter')
                split([(first, 'security'), (len(text), 'functional')])
            elif identifier == 'hint-1333-1962473956307884958':
                first = text.index('If encountering')
                split([(first, 'context'), (len(text), 'security')])
            elif identifier == 'cand-179-6365112243198787786':
                first = text.index(', and do not change')
                second = text.index(' Decoding exceptions')
                split([(first, 'security'), (second, 'functional'), (len(text), 'security')])
            elif identifier == 'pitfall-179-8712527076461853948':
                first = text.index('1. Before calling')
                second = text.index('Preserve legitimate behavior:')
                split([(first, 'context'), (second, 'security'), (len(text), 'functional')])
        else:
            raise ValueError('requires content review: ' + str(item['path']))
    spec.update(segments=segments, review_status='reviewed', reviewer='Codex',
        review_note='Agent partition of original text; card assumptions and contradictions intentionally preserved',
        scope='historical probe-card presentation; not a new Q0 selection or human relevance confirmation')
    return spec


def main():
    output = OUT / 'reviewed_probe_views.json'
    if output.exists():
        raise FileExistsError('preserve reviewed views')
    specs, index = {}, {}
    for line in ROWS.open(encoding='utf-8'):
        row = json.loads(line)
        tid = str(row['task_id'])
        if tid not in ['1394', '102']:
            continue
        cards = row['attempts'][0]['generation']['retrieved_cards']
        for card in cards:
            specs[card['invariant_id']] = reviewed_spec(card, tid)
        for mode in ['BF', 'BS', 'BFS']:
            apply_memory_view(cards, mode, specs)
        index[tid] = [card['invariant_id'] for card in cards]
    assert len(specs) == 6
    output.write_text(json.dumps(specs, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (OUT / 'reviewed_probe_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'reviewed_content_partitions': len(specs), 'new_Q0_selection': False,
                      'new_model_scores': 0, 'API_calls': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()

"""按真实共享初析选出的卡片分区，严格使用原文；不把内容分区当成适用性真值。"""
from __future__ import annotations

import json

from .prepare import OUT, read, write
from methods.sct_trajectory.memory_views import draft_view, source_projection, apply_memory_view


def reviewed(card):
    source = source_projection(card)
    identifier = source['invariant_id']
    spec = draft_view(card)
    segments = []
    for item in spec['segments']:
        field = item['path'][0]
        text = source[field] if isinstance(source[field], str) else None
        def whole(role):
            segments.append({**item, 'role': role})
        def split(parts):
            cursor = 0
            for end, role in parts:
                segments.append({**item, 'start': cursor, 'end': end, 'role': role})
                cursor = end
            assert cursor == len(text)
        if field in ('applicability', 'language_leaf'):
            whole('context')
        elif identifier == 'cand-1333-7972143074757284700':
            if field == 'high_level_invariant':
                pivot = text.index('; security boundaries should be based')
                split([(pivot, 'security'), (len(text), 'functional')])
            elif field == 'positive_principle':
                first = text.index('and to maintain')
                second = text.index('; use negated')
                split([(first, 'security'), (second, 'functional'), (len(text), 'security')])
            elif field == 'negative_guardrail':
                pivot = text.index('; excessively narrowing')
                split([(pivot, 'security'), (len(text), 'functional')])
            elif field == 'root_cause':
                first = text.index('Security test passed because')
                second = text.index('; functional test passed because')
                split([(first, 'context'), (second, 'security'), (len(text), 'functional')])
            elif field == 'fix_directive':
                pivot = text.index('3. Do not change')
                split([(pivot, 'security'), (len(text), 'functional')])
            else:
                raise ValueError('unreviewed field: ' + field)
        elif identifier == 'pitfall-915-8144612929088593380':
            if field in ('high_level_invariant', 'negative_guardrail'):
                whole('functional')
            elif field == 'root_cause':
                pivot = text.index('This indicates')
                split([(pivot, 'context'), (len(text), 'security')])
            elif field == 'fix_directive':
                whole('security')
            elif field == 'prev_fix_assessment':
                pivot = text.index('Specifically:')
                split([(pivot, 'context'), (len(text), 'security')])
            else:
                raise ValueError('unreviewed field: ' + field)
        else:
            raise ValueError('fresh selection requires content review: ' + identifier)
    spec.update(segments=segments, review_status='reviewed', reviewer='Codex',
        review_note='Original source spans only; reviewed before new generated-code outcomes; no task applicability endorsement',
        source_quality_notes=(['HTML-source assumptions need adaptation to parenthesis extraction']
            if identifier.startswith('cand-1333') else
            ['Dictionary-update advice may not apply to boolean key validation',
             'Source root-cause and fix wording contain unresolved consistency questions']))
    return spec


def main():
    starts = OUT / 'B02_shared_starts'
    specs = {}
    files = sorted((starts / 'shared_starts').glob('*.json'))
    for path in files:
        row = read(path)
        for card in row['selected_cards']:
            if card['invariant_id'] not in specs:
                specs[card['invariant_id']] = reviewed(card)
        for mode in ['BF', 'BS', 'BFS']:
            apply_memory_view(row['selected_cards'], mode, specs)
    write(starts / 'reviewed_views.json', specs)
    summary = {'completed_shared_starts_reviewed': len(files), 'unique_card_partitions': len(specs),
        'review_type': 'Agent source-content partition, not human task-card relevance confirmation',
        'new_generated_code_outcomes_seen': False, 'API_calls': 0}
    write(starts / 'view_review_status.json', summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()

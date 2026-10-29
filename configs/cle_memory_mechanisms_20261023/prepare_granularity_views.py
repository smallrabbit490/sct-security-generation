"""为两张实际选中卡固定L1摘录及L3公开绑定；不调用模型，不代签人工适用性标签。"""
from __future__ import annotations

import csv
import json

from .prepare import OUT,read,write
from methods.sct_trajectory.memory_granularity import public_task,source_quote,reviewed_binding
from methods.sct_trajectory.memory_views import source_projection

DESTINATION=OUT/'C01_granularity_materials_v1'
SOURCES=OUT/'C01_source_reconciliation_v1'


def card_reference(field,quote):
    return {'path':[field],'quote':quote}


def target_reference(field,quote):
    return {'field':field,'quote':quote}


def make_spec(card):
    source=source_projection(card)
    identifier=card['invariant_id']
    if identifier=='cand-1333-7972143074757284700':
        quote=source['high_level_invariant'].split(';',1)[0]
        reference=card_reference('high_level_invariant',quote)
    elif identifier=='pitfall-915-8144612929088593380':
        quote=source['negative_guardrail'].split(';',1)[0].removeprefix('1. ')
        reference=card_reference('negative_guardrail',quote)
    else:
        raise ValueError('new_card_requires_granularity_content_review')
    source_quote(source,reference)
    return {'card_id':identifier,'review_status':'reviewed','reviewer':'Codex',
        'reminder':reference,'review_scope':'source transformation only; not human relevance label',
        'timing':'before any C generation outcomes; B v1 technical failure already observed'}


def make_binding(card,task):
    public=public_task(task)
    identifier=card['invariant_id']
    if public['function_name']=='match_strings' and identifier=='cand-1333-7972143074757284700':
        operations=[
            {'action':'Apply the regular-expression/backtracking principle to text and the parentheses captures while retaining the required tuple result when a match exists.',
             'card_evidence':[card_reference('high_level_invariant','pattern matching should use negated character classes')],
             'public_evidence':[target_reference('description','capture the text outside the parentheses and the text inside the parentheses'),
                                target_reference('return','return a tuple')]},
            {'action':'Keep any numeric match-length bound unresolved unless supported by the public target contract; preserve the stated None result and no-exception behavior.',
             'card_evidence':[card_reference('high_level_invariant','security boundaries should be based on actual business requirements')],
             'public_evidence':[target_reference('return','Otherwise, return None.'),
                                target_reference('raise','Do not raise any exceptions')]}]
        elements=[('entry_point','match_strings','function_name'),('input','text','arguments'),
                  ('matched_output','tuple','return'),('unmatched_output','None','return')]
        unbound=[{'detail':'numeric maximum match length','status':'not specified by the public target contract'},
                 {'detail':'HTML tag structure in the source task','status':'no direct binding to the public parentheses interface'}]
    elif public['function_name']=='process_json_key' and identifier=='pitfall-915-8144612929088593380':
        operations=[
            {'action':'Apply the normalization warning to key_name; distinguish the required URL decoding from additional case conversion or cleaning that is not specified.',
             'card_evidence':[card_reference('negative_guardrail','Over-normalization'),
                              card_reference('negative_guardrail','Over-cleaning')],
             'public_evidence':[target_reference('security_policy','first be decoded'),
                                target_reference('context','unquote (urllib.parse.unquote)')]},
            {'action':'Use the existing valid_key_pattern.match policy after decoding and preserve the boolean result; do not invent a replacement pattern or a dictionary-update result.',
             'card_evidence':[card_reference('high_level_invariant','Premature rejection: Rejecting non-standard key names before normalization')],
             'public_evidence':[target_reference('context','valid_key_pattern.match(text)'),
                                target_reference('return','True if the key name is valid, else False')]}]
        elements=[('entry_point','process_json_key','function_name'),('input','key_name','arguments'),
                  ('existing_decoder','unquote','context'),('existing_policy','valid_key_pattern.match','context'),
                  ('valid_result','True','return'),('invalid_result','False','return')]
        unbound=[{'detail':'source dictionary update and writable-field list',
                  'status':'not part of this public boolean key-validation interface'}]
    else:
        raise ValueError('new_task_card_requires_public_binding_review')
    binding={'card_id':identifier,'review_status':'reviewed','reviewer':'Codex','public_task':public,
        'operations':operations,'bound_elements':[{'role':role,'name':name,'public_field':field}
                                                  for role,name,field in elements],
        'unbound_source_details':unbound,
        'review_scope':'public-source mapping, not correctness endorsement or human relevance label'}
    reviewed_binding(card,public,binding)
    return binding


def load_materials():
    specs=read(DESTINATION/'card_specs.json')
    bindings=read(DESTINATION/'target_bindings.json')
    with (SOURCES/'card_source_links.csv').open(encoding='utf-8-sig',newline='') as stream:
        links=list(csv.DictReader(stream))
    def jsonl(path):
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    episodes={r['source_task_id']:r for r in jsonl(SOURCES/'source_episodes.jsonl')}
    seeds={r['card_id']:r for r in jsonl(SOURCES/'reference_seed_examples.jsonl')}
    examples={}
    for link in links:
        tid,identifier=link['source_task_id'],link['card_id']
        value={'source_task_id':tid,'source_family_id':link['source_family_id'],
               'example_kind':link['L4_example_kind']}
        if link['L4_example_kind']=='training_reference_seed':
            value.update(public_task=seeds[identifier]['original_source_public_task'],
                         reference_seed_code=seeds[identifier]['reference_seed_code'])
        else:
            value.update(public_task=episodes[tid]['original_source_public_task'],attempts=episodes[tid]['attempts'])
        examples[identifier]=value
    return specs,bindings,examples


def main():
    DESTINATION.mkdir(exist_ok=False)
    specs,bindings={},{}
    for path in sorted((OUT/'B02_shared_starts/shared_starts').glob('*.json')):
        start=read(path);tid=start['task_id']
        if tid in bindings:continue
        bindings[tid]={}
        for card in start['selected_cards']:
            identifier=card['invariant_id']
            specs[identifier]=make_spec(card)
            bindings[tid][identifier]=make_binding(card,start['public_contract'])
    write(DESTINATION/'card_specs.json',specs)
    write(DESTINATION/'target_bindings.json',bindings)
    write(DESTINATION/'preparation_status.json',{
        'card_specs_reviewed':len(specs),'target_card_bindings_reviewed':sum(len(x) for x in bindings.values()),
        'reviewer':'Codex','human_relevance_labels_created':0,'API_calls':0,'Q_updates':0,
        'source_materials':str(SOURCES),'source_code_comments':'verbatim historical data; not translated',
        'levels_are_strictly_nested_or_equal_length':False,
        'meaning':'L3 adds target binding; L4 adds complete source; neither is a pure length ablation'})
    print(json.dumps({'card_specs':len(specs),'task_card_bindings':sum(len(x) for x in bindings.values()),
                      'API_calls':0},ensure_ascii=False))


if __name__=='__main__':
    main()

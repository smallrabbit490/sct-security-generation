"""核实来源代码槽与非空代码，L4缺原件不以标准修复补造；零API。"""
from __future__ import annotations

import csv
import json

from .prepare import ROOT,OUT,read,write,write_csv
from .prepare_granularity_views import SOURCES,load_materials
from methods.sct_trajectory.memory_granularity import source_example,GranularityPreparationRequired


def main():
    destination=OUT/'C01_source_availability_v1'
    destination.mkdir(exist_ok=False)
    episodes=[json.loads(line) for line in (SOURCES/'source_episodes.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    with (SOURCES/'card_source_links.csv').open(encoding='utf-8-sig',newline='') as stream:
        links=list(csv.DictReader(stream))
    _,_,examples=load_materials()
    target_family=read(OUT/'v2/tasks_train.json')[0]['family_id']
    cases=[]
    for link in links:
        identifier=link['card_id'];example=examples[identifier]
        runtime={'source_task_id':link['source_task_id'],'kind':link['source_kind']}
        available,reason=True,''
        try:
            source_example(runtime,example,target_family)
        except GranularityPreparationRequired as exc:
            available,reason=False,str(exc)
        cases.append({'card_id':identifier,'source_task_id':link['source_task_id'],
            'example_kind':link['L4_example_kind'],'L4_source_payload_available':available,
            'reason':reason,'content_reviewed_for_C01':False})
    empties=[{'source_task_id':episode['source_task_id'],'attempt':attempt['attempt']}
        for episode in episodes for attempt in episode['attempts'] if not attempt['generated_code'].strip()]
    no_code=[e['source_task_id'] for e in episodes if not any(a['generated_code'].strip() for a in e['attempts'])]
    result={'protocol':'cle-L4-source-availability-audit-v1','source_tasks':len(episodes),
        'saved_code_slots':sum(len(e['attempts']) for e in episodes),'nonempty_generated_codes':
            sum(bool(a['generated_code'].strip()) for e in episodes for a in e['attempts']),
        'empty_code_slots':empties,'source_tasks_with_no_generated_code':no_code,
        'L4_source_payload_available_cards':sum(c['L4_source_payload_available'] for c in cases),
        'L4_unavailable_cards':[c['card_id'] for c in cases if not c['L4_source_payload_available']],
        'reference_seed_substitution_for_nonseed':False,'content_review_certified_by_this_audit':False,
        'API_calls':0,'Q_updates':0,'is_experiment_score':False,
        'correction':'553 counts saved output slots, including 7 empty; nonempty generated code count is 546'}
    write_csv(destination/'card_L4_availability.csv',cases)
    write(destination/'summary.json',result)
    write(ROOT/'results/curated/cle_memory_mechanisms_20261023/granularity_source_availability.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

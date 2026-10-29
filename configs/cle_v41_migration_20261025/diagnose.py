"""零API提取48格题面、卡片、代码与原验证证据；仅供事后诊断。"""
import hashlib
import json
from pathlib import Path
from .resume import ROOT,RUN,read,write

OUT=RUN/'diagnosis_v1'


def collect():
    rows=[json.loads(s) for s in (RUN/'final/rows.jsonl').read_text(encoding='utf-8').splitlines()]
    tasks={str(t['index']):t for t in read(RUN/'inputs/tasks.json')}
    events={}
    for base in [RUN,*map(Path,read(RUN/'recovery_segments.json'))]:
        for path in (base/'validation_events/PLT').glob('*.json'):
            d=read(path)
            key=(str(d['args'][0]['index']),hashlib.sha256(d['args'][1].encode()).hexdigest())
            events[key]=(d['result'][0],str(path))
    cards={};packets=[]
    for tid,t in tasks.items():
        packet={'task_id':tid,'family_id':t['family_id'],'CWE':t['CWE_ID'],
            'public_contract':t['task_description'],'fixture':t['unittest'],'ground_truth':t['ground_truth'],'rows':[]}
        for row in rows:
            if row['task_id']!=tid:continue
            item={k:row[k] for k in ('cell_id','migration_arm','repeat')};item['attempts']=[]
            for a in row['attempts']:
                g=a.get('generation',{});code=a.get('code','');ev,source=events.get((tid,hashlib.sha256(code.encode()).hexdigest()),({},None))
                codepath=OUT/'codes'/f"{row['cell_id']}_c{a['attempt']}.py"
                codepath.parent.mkdir(parents=True,exist_ok=True);codepath.write_text(code,encoding='utf-8')
                chosen=g.get('retrieved_cards') or [];adopted=g.get('cards') or []
                for card in chosen:
                    cards[card['invariant_id']]={k:card.get(k) for k in ('invariant_id','kind','status','cwe','source_task_id',
                        'high_level_invariant','applicability','exclusion_conditions','positive_principle','negative_guardrail',
                        'root_cause','fix_directive','prev_fix_assessment','language_leaf')}
                item['attempts'].append({'attempt':a['attempt'],'measured':a.get('measured'),
                    'functional':a.get('functional'),'security':a.get('security'),'joint':a.get('joint'),
                    'code_path':str(codepath),'code_lines':len(code.splitlines()),'evidence':ev,'evidence_path':source,
                    'selected_ids':[c['invariant_id'] for c in chosen],'adopted_ids':[c['invariant_id'] for c in adopted],
                    'adoption':g.get('adoption'),'stages':g.get('stages'),'plan':g.get('plan_parsed'),
                    'experience_analysis':g.get('experience_analysis'),'error_type':a.get('error_type')})
            packet['rows'].append(item)
        write(OUT/'tasks'/f'{tid}.json',packet);packets.append(packet)
    write(OUT/'cards.json',cards)
    write(OUT/'inventory.json',{'operation':'zero_API_posthoc_diagnosis','API_calls':0,'P7_runs':len(rows),
        'tasks':len(tasks),'selected_unique_cards':len(cards),'adopted_unique_cards':len({c for p in packets for r in p['rows'] for a in r['attempts'] for c in a['adopted_ids']}),
        'public_vs_fixture_separated':True,'saved_sources_unchanged':True})
    print(json.dumps(read(OUT/'inventory.json')))


if __name__=='__main__':collect()

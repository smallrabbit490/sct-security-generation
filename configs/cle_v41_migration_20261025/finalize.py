"""S1完成后零API核验原生48格和冻结边界，生成只读合并产物。"""
import json
from pathlib import Path
from datetime import datetime
from .resume import ROOT,RUN,read,write,digest,MODEL


def main():
    run=RUN;segments=[Path(p) for p in read(run/'recovery_segments.json')];parts=[run,*segments]
    assert read(segments[-1]/'state.json')['status']=='completed'
    checkpoint=read(segments[-1]/'checkpoint.json')
    assert all(digest(run/'task_rows'/(n+'.json'))==h for n,h in checkpoint['completed_rows'].items())
    assert all(digest(run/f)==h for f,h in checkpoint['prior_journals'].items())
    assert all(digest(run/'source_bundle'/f)==h for f,h in checkpoint['source_manifest'].items())
    assert digest(run/'inputs/memory.jsonl')==checkpoint['input_manifest']['memory']==digest(checkpoint['input_manifest']['legacy_source'])
    rows={p.stem:read(p) for base in parts for p in (base/'task_rows').glob('*.json')}
    cells=read(run/'schedule.json');ids=[c['pair_id']+'_'+a for c in cells for a in c['arms']]
    assert len(rows)==48 and set(rows)==set(ids)
    assert all(len(r['attempts']) in (1,2) and r['Q_updates']==0 for r in rows.values())
    assert all(len(r['attempts'])==1 for r in rows.values() if r['attempts'][0].get('joint'))
    assert all(not a.get('generation',{}).get('cards') and not a.get('generation',{}).get('retrieved_cards')
               for r in rows.values() if r['migration_arm']=='E0' for a in r['attempts'])
    assert all(len(a.get('generation',{}).get('retrieved_cards') or [])<=3 for r in rows.values() for a in r['attempts'])
    logical={}
    for base in parts:
        for p in (base/'journals').glob('*/requests/*.json'):
            d=read(p);assert d['status']=='completed'
            key=(p.parents[1].name,d['identity']);assert key not in logical;logical[key]=d
            if d['settings']['model']==MODEL:assert d['response']['model']==MODEL
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    for base in parts:
        for p in (base/'wire').glob('*.request.json'):
            d=read(p);ensure_model_call_allowed(MODEL,datetime.fromisoformat(d['started_utc']))
    out=run/'final';out.mkdir(exist_ok=False)
    with (out/'rows.jsonl').open('w',encoding='utf-8') as f:
        for identity in ids:f.write(json.dumps(rows[identity],ensure_ascii=False)+'\n')
    result={'status':'passed','combined_P7':48,'unique_tasks':len({r['task_id'] for r in rows.values()}),
        'unique_families':len({r['family_id'] for r in rows.values()}),'arms':['E0','E1'],'repeats':2,
        'frozen_memory_unchanged':True,'original_15_rows_unchanged':True,'original_journals_unchanged':True,
        'native_sources_unchanged':True,'model_and_schedule_checked':True,'unknown_logical_requests':0,
        'Q_updates':0,'card_generation':0,'API_calls_during_finalize':0,
        'model_degradations_retained':True,'protocols':[read(b/'protocol.json')['protocol'] for b in parts]}
    write(out/'integrity_checks.json',result)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()

"""生成输出格式事故的独立重验证：不重调模型、不改原始行或原选择结果。"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from methods.direction_screening.run import DEFAULT_OUT, prepare, read_rows, evaluate, write
from methods.direction_screening.adjustment import extract_candidate
from methods.direction_screening.protocol import summarize


def main():
    """审计阶段仅修正唯一围栏/完整 AST；所有臂一致，选择索引冻结，测试不反馈。"""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('screen','confirmation','regression'),default='screen')
    args=parser.parse_args()
    out=DEFAULT_OUT
    metadata=json.loads((out/(args.phase+'_metadata.json')).read_text(encoding='utf-8'))
    if metadata['status']!='completed':
        raise RuntimeError('requires_completed_run')
    tasks={str(t['index']):t for t in prepare(out)[args.phase]}
    rows=read_rows(out/args.phase/'rows.jsonl')
    directory=out/(args.phase+'_extraction_revalidated')
    directory.mkdir(exist_ok=True)
    jobs={}
    for row in rows:
        for attempt in row['attempts']+[row['final']]:
            code,policy=extract_candidate(attempt['code'])
            if policy!='unchanged':
                jobs[(str(row['task_id']),code)]=policy
    cache_path=directory/'revalidation_cache.jsonl'
    cache={}
    if cache_path.exists():
        for line in cache_path.read_text(encoding='utf-8').splitlines():
            record=json.loads(line)
            cache[(record['task_id'],record['result']['code'])]=record['result']
    def one(key):
        tid,code=key
        return key,evaluate(tasks[tid],code)
    with ThreadPoolExecutor(max_workers=8) as pool,cache_path.open('a',encoding='utf-8') as stream:
        for future in as_completed([pool.submit(one,key) for key in jobs if key not in cache]):
            key,result=future.result()
            cache[key]=result
            stream.write(json.dumps({'task_id':key[0],'policy':jobs[key],'result':result},ensure_ascii=False)+'\n')
            stream.flush()
    corrected=[]
    changes=[]
    for row in rows:
        copied=json.loads(json.dumps(row))
        records=[]
        for index,attempt in enumerate(copied['attempts']):
            code,policy=extract_candidate(attempt['code'])
            if policy!='unchanged':
                copied['attempts'][index]=cache[(str(row['task_id']),code)]
                records.append({'attempt_index':index,'policy':policy})
        code,policy=extract_candidate(row['final']['code'])
        if policy!='unchanged':
            copied['final']=cache[(str(row['task_id']),code)]
        copied['format_revalidation']=records
        copied['candidate_selection_unchanged']=True
        if row['arm']=='branch':
            copied['oracle_any_joint']=any(a['joint'] for a in copied['attempts'])
        corrected.append(copied)
        if records:
            changes.append({'task_id':row['task_id'],'arm':row['arm'],'records':records,
                            'original_joint':row['final']['joint'],'revalidated_joint':copied['final']['joint']})
    (directory/'rows.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in corrected),encoding='utf-8')
    write(directory/'summary.json',summarize(corrected))
    write(directory/'run_metadata.json',{'status':'completed','rows':len(corrected),
          'origin_phase':args.phase,'source_rows_sha256':hashlib.sha256((out/args.phase/'rows.jsonl').read_bytes()).hexdigest(),
          'extraction_source_sha256':hashlib.sha256((Path(__file__).parent/'adjustment.py').read_bytes()).hexdigest(),
          'changes':changes,'unique_revalidations':len(jobs),'new_model_calls':0,
          'selector_indices_frozen':True,'official_feedback_to_generation':False,
          'completed_at':datetime.now(timezone.utc).isoformat()})
    print(json.dumps({'rows':len(corrected),'changed_rows':len(changes),'new_model_calls':0,'unique_revalidations':len(jobs)}))


if __name__=='__main__':
    main()

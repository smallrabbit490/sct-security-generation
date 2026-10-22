"""补齐原镜像PyYAML后，零API复验已有全部尝试及参考，不改旧记录。"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation import run_memory_q_full_gate_v3 as old
from methods.sct_trajectory.closed_loop import validate_and_state
from methods.sct_trajectory.context_pipeline import safe_feedback
from methods.cle_ablation.retrieval_q_study import reference_check

OUT=old.OUT/'environment_recovery'
INFRA={'environment_error','plt_validator_exception','validator_exception','local_worker_error'}


def main():
    import yaml
    assert yaml.__version__=='6.0.3'
    old.verify(old.OUT)
    rows=old.read_rows(old.OUT/'rows.jsonl');_,tasks,pools=old.inputs()
    issues=old.read(old.OUT/'summary.json')['integrity_issues']
    assert len(rows)==175 and issues==[{'task_id':'1402','arm':'Q3','error':'validation_environment_error'}]
    fault=next(i for i,r in enumerate(rows) if r['task_id']=='1402' and r['arm']=='Q3')
    censored={r['task_id'] for r in rows[fault:]}
    OUT.mkdir(exist_ok=False)
    jobs=[(r,a) for r in rows for a in r['attempts'] if a.get('code') and a.get('validation')]
    def check(job):
        row,a=job;evidence,state=validate_and_state(tasks[row['task_id']],a['code'],timeout=20)
        new={'evidence':safe_feedback(evidence),'state':state}
        infra=any((new['evidence'].get(k) or {}).get('error_type') in INFRA for k in ('functional','security'))
        return {'task_id':row['task_id'],'arm':row['arm'],'attempt':a['attempt'],
            'same_feedback':new==a['validation'],'old':a['validation'],'new':new,'infrastructure_error':infra}
    checked=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for future in as_completed([pool.submit(check,j) for j in jobs]):
            item=future.result();old.append(OUT/'attempt_revalidation.jsonl',item);checked.append(item)
            if len(checked)%64==0:print({'zero_API_revalidated_attempts':len(checked),'target':len(jobs)},flush=True)
    def control(identifier):
        try:return reference_check(tasks[identifier])
        except (SyntaxError,ValueError) as exc:return {'task_id':identifier,'passed':False,'state':'unmeasured','error_type':type(exc).__name__}
    with ThreadPoolExecutor(max_workers=8) as pool:
        controls=list(pool.map(control,pools['D_gate']))
    old.write(OUT/'reference_preflight.json',{'new_API_calls':0,'PyYAML':'6.0.3','tasks':controls})
    changed={i['task_id'] for i in checked if not i['same_feedback']}
    infra={i['task_id'] for i in checked if i['infrastructure_error']}
    grouped={}
    for r in rows:grouped.setdefault(r['task_id'],set()).add(r['arm'])
    incomplete={i for i,v in grouped.items() if v!=set(old.ORDER)}
    repeat=changed|infra|censored|incomplete
    reusable=sorted(set(grouped)-repeat)
    result={'new_API_calls':0,'old_rows':175,'revalidated_code_attempts':len(checked),
        'dependency':'PyYAML==6.0.3','source':'docker/python-validator/Dockerfile',
        'module':yaml.__file__,'changed_feedback_tasks':sorted(changed),
        'remaining_infrastructure_tasks':sorted(infra),'possibly_stop_censored_tasks':sorted(censored),
        'incomplete_tasks':sorted(incomplete),'reusable_task_ids':reusable,'reusable_rows':4*len(reusable),
        'repeat_all4_task_ids':sorted(repeat),
        'rule':'Reuse only complete tasks with all recorded native feedback unchanged and no stop censoring; changed tasks repeat all4, no choice by grade direction',
        'original_preoutcome_174_mask':'preserved; new reference results do not select performance cohort'}
    old.write(OUT/'summary.json',result)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':main()

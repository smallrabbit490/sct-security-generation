"""零API重放已保存代码的原生验证器，补充失败用例位置；不回流生成。"""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation import run_memory_q_equal_k as study
from methods.sct_agent.validation_evidence import _run_local_plt_data_driven
from methods.sct_trajectory.retrieval_hit_study import read_rows


def main():
    study.verify(study.OUT)
    _,tasks,_=study.inputs()
    rows=read_rows(study.OUT/'rows.jsonl')
    assert len(rows)==48
    results=[]
    for row in rows:
        if row['task_id'] not in ('1306','1317','1341','1000'):
            continue
        task=tasks[row['task_id']]
        attempt=row['attempts'][-1]
        f,s,_,payload=_run_local_plt_data_driven(attempt['code'],task['task_description']['function_name'],
            task['unittest']['setup'],task['unittest']['testcases'],20)
        assert (f.status=='pass')==attempt['functional']
        assert (s.status=='pass')==attempt['security']
        results.append({'task_id':row['task_id'],'arm':row['arm'],'repeat':row['repeat'],
            'attempt':attempt['attempt'],'F':f.status,'S':s.status,'payload':payload})
    study.write(study.CURATED/'case_validation.json',{'new_API_calls':0,
        'purpose':'posthoc_original_validator_replay_only; never supplied to generation or blind labels',
        'raw_generation_scores_changed':False,'checks':results})
    print(json.dumps({'native_validator_replays':len(results),'all_match_saved_scores':True,'new_API_calls':0}))


if __name__=='__main__':
    main()

"""零API重核D_grow奖励资格；保留原始任务、旧资格表及本轮完整参考反馈。"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import argparse
import ast
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.cle_ablation.run_memory_q_unlimited import inputs
from methods.sct_trajectory.closed_loop import validate_and_state
from methods.sct_trajectory.run_artifacts import write_json_atomic as write

OUT=ROOT/'translation_work/diagnostics/20261019/cle_memory_q/coverage_learning_v1'
OLD=ROOT/'translation_work/diagnostics/20261018/cle_memory_q/unlimited_complete_v2'
CONFIG=ROOT/'configs/cle_q_coverage_learning_20261019'


def placeholder_paths(value, path=''):
    """只输出占位符字段位置；不把测试输入或答案转为模型上下文。"""
    if isinstance(value,str):
        return [path] if '<LOCAL_PATH>' in value else []
    if isinstance(value,dict):
        return [p for k,v in value.items() for p in placeholder_paths(v,path+'.'+str(k))]
    if isinstance(value,list):
        return [p for i,v in enumerate(value) for p in placeholder_paths(v,path+'.'+str(i))]
    return []


def bindings(task):
    """复用现参考预检的外部绑定规则；仅比较名称是否在公开字段中声明。"""
    gt=task['ground_truth'];source=gt['code_before']+gt['patched_code']+gt['code_after']
    try:
        setup=ast.parse(task['unittest'].get('setup',''));code=ast.parse(source)
    except SyntaxError as exc:
        return [],type(exc).__name__
    defined={n.id for n in ast.walk(setup) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Store)}
    used={n.id for n in ast.walk(code) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
    public=json.dumps(task['task_description'],ensure_ascii=False)
    return sorted(n for n in defined & used if not re.search(r'\b'+re.escape(n)+r'\b',public)),None


def check(task, previous):
    identifier=str(task['index']);gt=task['ground_truth']
    evidence,state=validate_and_state(task,gt['code_before']+gt['patched_code']+gt['code_after'],timeout=20)
    paths=placeholder_paths(task);undeclared,parse_error=bindings(task)
    reasons=[]
    if state!='A':reasons.append('reference_not_joint')
    if paths:reasons.append('placeholder_in_task')
    if undeclared:reasons.append('undeclared_public_binding')
    if parse_error:reasons.append('reference_or_setup_parse_error')
    return {'task_id':identifier,'family_id':task['family_id'],'cwe':str(task['CWE_ID']),
        'previous_reward_eligible':previous['reward_eligible'],
        'previous_exclusion_reasons':previous['exclusion_reasons'],
        'reference_state':state,'reference_evidence':evidence,
        'placeholder_paths':paths,'public_placeholder_paths':[p for p in paths if p.startswith('.task_description')],
        'undeclared_setup_bindings':undeclared,'parse_error':parse_error,
        'reward_eligible':not reasons,'exclusion_reasons':reasons,
        'original_data_modified':False,'API_calls':0}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',default='original')
    args=parser.parse_args()
    _,tasks,pools=inputs()
    previous={str(t['task_id']):t for t in json.loads((OLD/'reference_calibration.json').read_text(encoding='utf-8'))['tasks']}
    OUT.mkdir(parents=True,exist_ok=True)
    result_path=OUT/('qualification.'+args.version+'.json')
    if result_path.exists():
        raise ValueError('qualification_version_exists')
    old_excluded=[i for i in pools['D_grow'] if not previous[str(i)]['reward_eligible']]
    ordered=sorted(old_excluded,key=lambda i:(str(tasks[str(i)]['CWE_ID']) not in {'601','918'},str(i)))
    ordered += [i for i in pools['D_grow'] if i not in old_excluded]
    results=[]
    with ThreadPoolExecutor(max_workers=6) as executor:
        # 先复核43道排除题，再对拟学习名单进行同环境预检。
        for batch in [ordered[:43],ordered[43:]]:
            futures=[executor.submit(check,tasks[str(i)],previous[str(i)]) for i in batch]
            for future in as_completed(futures):
                result=future.result();results.append(result)
                write(OUT/('qualification_'+args.version)/('task_'+result['task_id']+'.json'),result)
            print(json.dumps({'checked':len(results),'eligible':sum(t['reward_eligible'] for t in results)},ensure_ascii=False),flush=True)
    results=sorted(results,key=lambda t:ordered.index(t['task_id']))
    summary={'protocol':'cle-q-coverage-learning-v1','API_calls':0,'tasks':results,
        'former_excluded_checked':43,'reward_eligible_tasks':sum(t['reward_eligible'] for t in results),
        'former_excluded_recovered':[t['task_id'] for t in results if not t['previous_reward_eligible'] and t['reward_eligible']],
        'reason_counts':dict(Counter(r for t in results for r in t['exclusion_reasons'])),
        'public_contract_overlays':'inherited102/136 only; no new public hints yet'}
    write(result_path,summary)
    small={k:v for k,v in summary.items() if k!='tasks'}
    small['excluded43']=[{k:v for k,v in t.items() if k!='reference_evidence'} for t in results if not t['previous_reward_eligible']]
    write(CONFIG/('qualification_summary.'+args.version+'.json'),small)
    print(json.dumps({k:v for k,v in small.items() if k!='excluded43'},ensure_ascii=False),flush=True)


if __name__=='__main__':main()

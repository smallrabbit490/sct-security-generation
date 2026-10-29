"""已保存全部响应/代码的零API回放；缺项只报告，绝不补发请求。"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from .batch import RUN,ROOT,CFG,read
from .policies import rows_for,final
from .report import report
from methods.sct_trajectory.replay_journal import write_json


def forbidden(*args,**kwargs):raise AssertionError('zero_API_replay_forbids_network')


def relation(sources,out):
    from configs.cle_v41_relation_20261026.execution import StudyExecution,review_from_directory
    from configs.cle_v41_relation_20261026 import wiring
    from methods.sct_trajectory.semantic_retrieval import EmbeddingClient
    import methods.sct_trajectory.semantic_retrieval as semantic
    from methods.cle_ablation.runner import load_memory
    latest=Path(sources[-1]);protocol=read(latest/'protocol.json');protocol['paid_execution_enabled']=False
    semantic.MAX_SELECTOR_CHARS=protocol['selector_character_limit']
    io=StudyExecution(out,protocol,read(latest/'schedule.json'),client_factory=forbidden,physical_open=forbidden,
        reviewer=review_from_directory(latest/'plan_reviews/imported'),resume_sources=sources)
    io.replay_source=out
    io.state['evidence_kind']='zero_API_saved_real_response_replay'
    cache=out/'embeddings.sqlite3'
    with sqlite3.connect(f'file:{(latest/"embeddings.sqlite3").as_posix()}?mode=ro',uri=True) as src:
        with sqlite3.connect(cache) as dst:src.backup(dst)
    embedding=EmbeddingClient(cache_path=cache);embedding._request=forbidden
    io.run(read(latest/'inputs/tasks.json')[0],wiring.native_selector(load_memory(latest/'inputs/memory.jsonl'),embedding))
    original={r['cell_id']:r for root in sources for p in (Path(root)/'task_rows').glob('*.json') for r in [read(p)]}
    differences=[r['cell_id'] for r in io.rows if any(final(r).get(k)!=final(original[r['cell_id']]).get(k) for k in ('functional','security','joint','code','measured'))]
    state={'status':'replay_passed' if len(io.rows)==8 and not differences else 'replay_incomplete_or_different',
        'completed':len(io.rows),'differences':differences,'new_HTTP':len(list((out/'wire').glob('*.request.json'))),
        'raw_status':io.state}
    write_json(out/'replay_result.json',state)
    return state


def footprints(stage,rows,tasks):
    from methods.cle_ablation.memory_footprint import compare_code
    by={(str(r['task_id']),r['repeat'],r.get('condition',r.get('relation_arm'))):r for r in rows}
    controls={'B02':'B0','S2_M1':'protect_none','S2_P13_P22':'P00','D02':'P7','C02':'L0','D03b':'Q0','B05':'empty_edit','S4':'CONTROL'}
    if stage not in controls:return []
    result=[]
    for row in rows:
        arm=row.get('condition',row.get('relation_arm'));key=(str(row['task_id']),row['repeat'],controls[stage])
        control=by.get(key)
        if arm==controls[stage] or control is None:continue
        task=tasks[str(row['task_id'])]
        outcome=compare_code(final(control).get('code',''),final(row).get('code',''),task.get('task_description',task))
        result.append({'cell_id':row['cell_id'],'control_cell_id':control['cell_id'],'footprint':outcome,
            'joint_before':final(control).get('joint'),'joint_after':final(row).get('joint'),
            'meaning':'offline structural/interface risk indicator; not a causal or semantic correctness label'})
    return result


def main():
    out=RUN/'CLOSEOUT';out.mkdir(exist_ok=True)
    write_json(out/'launch.json',{'pid':os.getpid(),'mode':'zero_API_closeout'})
    write_json(out/'state.json',{'status':'running','paid_enabled':False})
    index=read(RUN/'execution_index.json');results=[]
    try:
        for stage in read(CFG/'protocol.json')['stages']:
            name=stage['id'];sources=index.get(name,[])
            if stage['kind'] in ('classifier','report') or not sources:continue
            latest=Path(sources[-1])
            if read(latest/'state.json').get('status')!='completed':
                results.append({'stage':name,'status':'live_grid_incomplete_not_replayed'});continue
            recovery_index=RUN/'CLOSEOUT/replay_recovery_index.json'
            recovered=read(recovery_index) if recovery_index.exists() else {}
            replay=Path(recovered[name]) if name in recovered else RUN/(name+'_zero_API_replay_v1')
            result_file=replay/('replay_result.json' if name=='B03R' else 'state.json')
            if result_file.exists():result=read(result_file)
            elif name=='B03R':result=relation(sources,replay)
            else:
                args=[sys.executable,'-B','-X','utf8','-m','configs.cle_v41_completion_20261026.batch',name,'--segment',str(replay),'--offline-replay']
                for source in sources:args+=['--resume-source',source]
                # 子进程物理运输被离线请求日志拦截；不存在密钥加载/缺响应补跑路径。
                with (out/(name+'.stdout.log')).open('w') as stdout,(out/(name+'.stderr.log')).open('w') as stderr:
                    subprocess.run(args,cwd=ROOT,stdout=stdout,stderr=stderr,check=True)
                result=read(result_file)
            results.append({'stage':name,**result})
            if (latest/'inputs/tasks.json').exists():
                tasks={str(t['index']):t for t in read(latest/'inputs/tasks.json')}
                write_json(out/(name+'_footprints.json'),footprints(name,rows_for(name),tasks))
            write_json(out/'replay_results.json',results)
        from .diagnostics import run as diagnostics
        diagnostics()
        report()
        from .cases import prepare
        queue=prepare()
        state={'status':'awaiting_Codex_analysis','analysis_cases':len(queue['cases']),'zero_API_results':results,'new_paid_calls':0,
            'all_replays_passed':all(r['status']=='replay_passed' for r in results)}
    except BaseException as exc:
        state={'status':'needs_Codex_replay_fix','error_type':type(exc).__name__,'reason':str(exc),'new_paid_calls':0,'zero_API_results':results}
    write_json(out/'state.json',state)
    print(json.dumps({'status':state['status'],'new_paid_calls':0},ensure_ascii=False))


if __name__=='__main__':main()

"""旧P3无经验Agent基准：只做题，不读/生成经验，不学习Q。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from methods.sct_trajectory.replay_journal import write_json
from methods.sct_trajectory.replay_journal import ReplayStop

RUN=ROOT/'translation_work/baseline_runs/cle_P3_nomemory_v41flash1017_20261024'


def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))


class FirstTwoGate:
    """先执行名单前两题，原始行与验证可读后才放行其余题；不以得分设门。"""
    def __init__(self, ids, result_path):
        self.ids=set(map(str,ids));self.result_path=result_path
        self.rows={};self.error=None;self.lock=threading.Lock();self.ready=threading.Event()

    def wrap(self, original):
        def run(subset,task,*args,**kwargs):
            identity=str(task['index'])
            if identity not in self.ids:
                self.ready.wait()
                if self.error:raise ReplayStop('first_two_technical_gate_failed')
                return original(subset,task,*args,**kwargs)
            try:
                row=original(subset,task,*args,**kwargs)
                attempts=row.get('attempts') or []
                good=bool(attempts) and all(a.get('code') and isinstance(a.get('validation'),dict)
                    and a.get('generation',{}).get('workflow_completed')
                    and not a.get('generation',{}).get('cards')
                    and not a.get('generation',{}).get('retrieved_cards')
                    and a.get('retrieval_trace') is None
                    and all(s.get('status')=='completed' for s in a['generation'].get('stages',[]))
                    for a in attempts)
                with self.lock:
                    self.rows[identity]=row
                    if not good:self.error='incomplete_workflow_or_memory_boundary'
                    if len(self.rows)==len(self.ids) or self.error:
                        write_json(self.result_path,{'task_ids':sorted(self.ids),
                            'passed':not self.error,'reason':self.error,
                            'accuracy_is_not_a_gate':True,'rows':self.rows})
                        self.ready.set()
                if not good:raise ReplayStop('first_two_technical_gate_failed')
                return row
            except BaseException:
                with self.lock:
                    self.error=self.error or 'probe_interrupted_or_technical_failure'
                    self.ready.set()
                raise
        return run


def prepare(run):
    """仅准备原生D_gate及Base/Plus输入和源码；不读取任何经验文件。"""
    from methods.sct_trajectory.run_closed_loop import _load_tasks
    from methods.sct_trajectory.split import assign_families_atomic
    from methods.sct_trajectory.run_branch_gate_study import stratified_tasks
    if run.exists():raise SystemExit('existing_run_not_overwritten')
    if shutil.disk_usage(ROOT).free<20*1024**3:raise SystemExit('insufficient_disk_space')
    rows=_load_tasks(0);by_id={int(r['index']):r for r in rows}
    pools=assign_families_atomic(list(by_id),lambda i:by_id[i]['family_id'])
    gate=stratified_tasks([by_id[i] for i in pools['audit_pool']],0)
    assert len(gate)==298
    run.mkdir(parents=True)
    protocol={'protocol':'cle-P3-nomemory-v41flash1017-v1','model':'deepseek-v4.1-flash-1017',
        'original_project_root':str(ROOT),'arm':'P3','memory':'none','cards_read':False,
        'card_generation':False,'distillation':False,'Q_learning':False,'embedding':False,
        'counts':{'PLT':298,'Base':115,'Plus':140},'workers':4,'max_tokens':4096,
        'message_roles':['user'],'thinking':'disabled','temperature':0,
        'PLT_technical_probe_ids':[str(r['index']) for r in gate[:2]],
        'PLT':'original P3: at most2 attempts, task-local F/S feedback; firstJoint stops',
        'BasePlus':'original P3: fixed2 attempts, no hidden feedback; deliver last code',
        'control_summary':str(ROOT/'translation_work/diagnostics/20261023/cle_memory_mechanisms_v1/B02_provider_v41flash1017_add_control_v1/summary.json'),
        'supersedes':'cle-fresh-v41flash1017-baseline-v1; mistaken training stopped, never reused'}
    write_json(run/'protocol.json',protocol)
    write_json(run/'inputs/tasks_PLT.json',gate)
    for subset in ('Base','Plus'):
        write_json(run/f'inputs/tasks_{subset}.json',read(ROOT/f'data/SecEvoBasePlus/{subset}/Python_{subset}.json'))
    write_json(run/'inputs/pools.json',{'source':[{'task_id':i} for i in pools['source_pool']],
        'replay':[{'task_id':i} for i in pools['replay_pool']], 'audit':[{'task_id':i} for i in pools['audit_pool']]})
    files=[]
    for folder in ('methods','src','tools','configs/cle_nomemory_baseline_20261024','configs/cle_model_baseline_20261024'):
        files.extend((ROOT/folder).rglob('*.py'))
    files.extend(ROOT/f for f in ('data/external/secodeplt/secodeplt/data.json',
        'data/external/secodeplt/derived_metadata/family_manifest.json',
        'data/SecEvoBasePlus/Base/Python_Base.json','data/SecEvoBasePlus/Plus/Python_Plus.json'))
    manifest={}
    for p in sorted(set(files)):
        rel=p.relative_to(ROOT);target=run/'source_bundle'/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target);manifest[str(rel)]=hashlib.sha256(p.read_bytes()).hexdigest()
    write_json(run/'source_manifest.json',manifest)
    write_json(run/'state.json',{'protocol':protocol['protocol'],'status':'ready','completed':{},'pid':None})
    print(json.dumps({'prepared':str(run),'counts':protocol['counts'],'API_calls':0,'memory_files_read':0}))


def worker(run,stage):
    """直接调用原P3 runner；只注入已封存题单和记录器，不调用完整训练入口。"""
    from configs.cle_model_baseline_20261024.execute import install_recorders,record_validations
    from methods.cle_ablation import runner
    from methods.sct_trajectory.wire_recording import WireRecording
    protocol=read(run/'protocol.json');state=read(run/'state.json')
    control=read(protocol['control_summary'])
    if control.get('status')!='passed' or control.get('reported_model')!=protocol['model']:
        raise RuntimeError('new_model_control_not_passed')
    rows=read(run/f'inputs/tasks_{stage}.json')
    assert runner.arm_spec('P3').memory=='none'
    runner.load_tasks=lambda dataset,limit:[(dataset,r) for r in rows[:limit or None]]
    runner.POOLS=run/'inputs/pools.json'
    if stage=='PLT':
        gate=FirstTwoGate(protocol['PLT_technical_probe_ids'],run/'PLT_first_two_gate.json')
        runner.run_one=gate.wrap(runner.run_one)
    journals=install_recorders(run/'journals'/stage,'live',Path(protocol['original_project_root']))
    record_validations(run,stage)
    # 原生输出仍位于快照的translation_work下，便于脱离当前工作区回放。
    out=ROOT/'translation_work/nomemory'/stage
    sys.argv=['P3_nomemory','--dataset',stage,'--arms','P3','--model',protocol['model'],
        '--max-tokens','4096','--workers','4','--out',str(out)]
    state.update(status='running',stage=stage,pid=os.getpid());write_json(run/'state.json',state)
    try:
        with WireRecording(run/'wire'/stage):runner.main()
        saved=[json.loads(x) for x in (out/'rows.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
        assert len(saved)==protocol['counts'][stage] and len({r['task_id'] for r in saved})==len(saved)
        assert all(not a.get('generation',{}).get('cards') for r in saved for a in r['attempts'])
        state.setdefault('completed',{})[stage]=str(out)
        state.update(status='completed' if len(state['completed'])==3 else 'stage_completed',pid=None)
    except BaseException as exc:
        state.update(status='stopped_technical',stage=stage,pid=None,error_type=type(exc).__name__)
        raise
    finally:
        write_json(run/f'cost/{stage}.json',{'LLM':journals[0].summary(),'Embedding':journals[1].summary()})
        write_json(run/'state.json',state)


def launch(run):
    from methods.sct_trajectory.provider_policy import CURRENT_MODEL,ensure_model_call_allowed
    state=read(run/'state.json')
    if state['status'] not in ('ready','stage_completed','blocked_environment'):
        print(json.dumps(state));return
    ensure_model_call_allowed(CURRENT_MODEL)
    stage=next((s for s in ('PLT','Base','Plus') if s not in state['completed']),None)
    if not stage:return
    if stage!='PLT':
        image=subprocess.run(['docker','image','inspect','safecoder-python-validator:local'],capture_output=True,timeout=30)
        if image.returncode:
            state.update(status='blocked_environment',stage=stage,reason='original_python_validator_image_missing')
            write_json(run/'state.json',state);print(json.dumps(state));return
    with (run/'launch.lock').open('x') as f:f.write(stage)
    state.update(status='starting',stage=stage);write_json(run/'state.json',state)
    bundle=run/'source_bundle'
    cmd=[sys.executable,'-B','-X','utf8',str(bundle/'configs/cle_nomemory_baseline_20261024/run.py'),
         'worker','--run-root',str(run),'--stage',stage]
    if stage!='PLT':
        cmd=[sys.executable,'-B','-X','utf8',str(bundle/'tools/vhdx_watchdog.py'),
            '--label',f'P3_nomemory_v41_{stage}','--max-containers','4','--report',str(run/f'watchdog_{stage}.json'),'--',*cmd]
    flags=(subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
    with (run/f'{stage}.stdout.log').open('ab') as out,(run/f'{stage}.stderr.log').open('ab') as err:
        p=subprocess.Popen(cmd,cwd=bundle,stdout=out,stderr=err,creationflags=flags)
    write_json(run/'launch.json',{'pid':p.pid,'stage':stage,'command':cmd})
    (run/'launch.lock').unlink()
    print(json.dumps({'started':stage,'pid':p.pid}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','launch','worker'])
    parser.add_argument('--run-root',type=Path,default=RUN)
    parser.add_argument('--stage',choices=['PLT','Base','Plus'])
    args=parser.parse_args();run=args.run_root.resolve()
    {'prepare':lambda:prepare(run),'launch':lambda:launch(run),
     'worker':lambda:worker(run,args.stage)}[args.action]()


if __name__=='__main__':main()

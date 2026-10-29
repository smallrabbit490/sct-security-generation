"""已授权清单的串行包推进；每包内部最多4槽，时段等待不取消任务。"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime,timezone
from pathlib import Path

from .batch import CFG,RUN,ROOT,read,selector_pre_dispatch_failure
from .policies import train_classifier,freeze_validation,rows_for
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed,ModelTimeWindowError
from methods.sct_trajectory.replay_journal import write_json


def processes():
    script="Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*configs.cle_v41_completion_20261026*' -or $_.CommandLine -like '*configs.cle_v41_relation_20261026.live*' } | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,check=True)
    data=json.loads(result.stdout) if result.stdout.strip() else []
    return data if isinstance(data,list) else [data]


def roots_index():
    p=RUN/'execution_index.json'
    index=read(p) if p.exists() else {}
    for stage in read(CFG/'protocol.json')['stages']:
        identifier=stage['id']
        if identifier=='B03R':
            paths=sorted(RUN.glob('B03R_relation*'))
        else:paths=sorted(RUN.glob(identifier+'_recovery_*'))
        if (RUN/identifier/'protocol.json').exists():paths.insert(0,RUN/identifier)
        valid=[str(path.resolve()) for path in paths if (path/'protocol.json').exists()]
        if valid:index[identifier]=list(dict.fromkeys(index.get(identifier,[])+valid))
    write_json(p,index)
    return index


def launch(stage,sources):
    if shutil.disk_usage(ROOT).free<2_000_000_000:raise RuntimeError('output_disk_less_than_2GB')
    destination=RUN/(stage['id'] if not sources else stage['id']+f'_recovery_{len(sources):03d}')
    command=[sys.executable,'-B','-X','utf8','-m','configs.cle_v41_completion_20261026.batch',stage['id']]
    if sources:
        command+=['--segment',str(destination)]
        for source in sources:command+=['--resume-source',source]
    stdout=(RUN/(destination.name+'.stdout.log')).open('w',encoding='utf-8')
    stderr=(RUN/(destination.name+'.stderr.log')).open('w',encoding='utf-8')
    try:
        worker=subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    finally:stdout.close();stderr.close()
    write_json(RUN/'dispatch.json',{'stage':stage['id'],'pid':worker.pid,'destination':str(destination),
        'sources':sources,'utc':datetime.now(timezone.utc).isoformat()})
    return worker.pid


def tick():
    from .report import report
    control=RUN/'dispatch_control.json'
    if control.exists() and not read(control)['paid_execution_enabled']:
        report()
        return {'status':'paused_paid_by_user','reason':read(control)['reason']}
    index=roots_index();actual=processes();pids={item['ProcessId'] for item in actual}
    disposition=[]
    for stage in read(CFG/'protocol.json')['stages']:
        identifier=stage['id'];sources=index.get(identifier,[])
        root=Path(sources[-1]) if sources else RUN/identifier
        state=read(root/'state.json') if (root/'state.json').exists() else {}
        launch_record=read(root/'launch.json') if (root/'launch.json').exists() else {}
        if state.get('status')=='completed':
            # 旧段把未到终选的向量等待故障落成行；按原名单补执行，旧失败与用量保留。
            if identifier != 'D03a' or not any(selector_pre_dispatch_failure(row) for row in rows_for(identifier)):
                continue
        if launch_record.get('pid') in pids:
            report()
            return {'status':'running','stage':identifier,'worker_pid':launch_record['pid']}
        # 关系包的四份新计划由主Codex实际复核；不会用规则代签语义审核。
        if stage['kind']=='relation':
            if sources:
                disposition.append({'stage':identifier,'status':'needs_Codex_recovery','reason':state.get('reason')})
            continue
        if stage['kind']=='classifier':
            if len(__import__('configs.cle_v41_completion_20261026.policies',fromlist=['rows_for']).rows_for('C02'))!=480:
                disposition.append({'stage':identifier,'status':'waiting_complete_C02'})
                continue
            train_classifier();index[identifier]=[str(root.resolve())];write_json(RUN/'execution_index.json',index)
            continue
        if stage['kind']=='report':
            if state.get('status')=='awaiting_Codex_analysis':
                from .cases import finalize
                if finalize():continue
                report();return {'status':'awaiting_Codex_analysis','analysis_queue':str(root/'analysis_queue.json')}
            root.mkdir(exist_ok=True)
            with (root/'stdout.log').open('w') as stdout,(root/'stderr.log').open('w') as stderr:
                worker=subprocess.Popen([sys.executable,'-B','-X','utf8','-m','configs.cle_v41_completion_20261026.verify'],
                    cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            write_json(root/'launch.json',{'pid':worker.pid,'mode':'zero_API_closeout'})
            return {'status':'running_zero_API_closeout','worker_pid':worker.pid,'remaining':disposition}
        if stage['kind']=='granularity_confirmation' and not (RUN/'C03_C04a/model.json').exists():
            disposition.append({'stage':identifier,'status':'waiting_real_classifier_labels'});continue
        if stage['kind']=='validation' and not (RUN/'S4_selection.json').exists():freeze_validation()
        if state.get('reason')=='physical_budget_exhausted':
            disposition.append({'stage':identifier,'status':'incomplete_budget','reason':'cumulative package cap retained'});continue
        try:ensure_model_call_allowed('deepseek-v4.1-flash-1017')
        except ModelTimeWindowError:
            report();return {'status':'waiting_allowed_time','next_stage':identifier,'remaining':disposition}
        # 同一包启动还未落盘时，dispatch PID仍可防止重复派发。
        pending=read(RUN/'dispatch.json') if (RUN/'dispatch.json').exists() else {}
        if pending.get('pid') in pids:
            return {'status':'starting','stage':pending['stage'],'worker_pid':pending['pid']}
        pid=launch(stage,sources)
        return {'status':'started','stage':identifier,'worker_pid':pid,'remaining':disposition}
    report();return {'status':'completed','remaining':disposition}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['tick','daemon'])
    args=parser.parse_args();RUN.mkdir(parents=True,exist_ok=True)
    if args.action=='tick':print(json.dumps(tick(),ensure_ascii=False));return
    lock=RUN/'supervisor.lock'
    if lock.exists():
        pid=read(lock)['pid']
        if pid in {p['ProcessId'] for p in processes()}:raise RuntimeError('supervisor_already_running')
        lock.unlink()
    with lock.open('x',encoding='utf-8') as stream:json.dump({'pid':os.getpid()},stream)
    try:
        while True:
            try:state=tick()
            except Exception as exc:
                state={'status':'needs_Codex_technical_fix','error_type':type(exc).__name__,'reason':str(exc)}
            write_json(RUN/'supervisor_state.json',{**state,'pid':os.getpid(),'utc':datetime.now(timezone.utc).isoformat()})
            if state['status'] in ('completed','completed_base_dispatch','base_dispatch_with_unfinished_items','paused_paid_by_user'):break
            threading.Event().wait(30)
    finally:lock.unlink(missing_ok=True)


if __name__=='__main__':main()

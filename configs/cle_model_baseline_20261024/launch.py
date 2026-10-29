"""监控调用的单进程启动入口；不重跑已经完成或未决的阶段。"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from methods.sct_trajectory.provider_policy import CURRENT_MODEL,ensure_model_call_allowed
from methods.sct_trajectory.replay_journal import write_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-root',type=Path,default=ROOT/'translation_work/sct_runs/cle_full_v41flash1017_20261024')
    args=parser.parse_args();run=args.run_root.resolve()
    state=json.loads((run/'state.json').read_text(encoding='utf-8'))
    if state['status'] not in ('waiting_minimal_control','stage_completed','blocked_environment'):
        print(json.dumps(state,ensure_ascii=False));return
    ensure_model_call_allowed(CURRENT_MODEL)
    protocol=json.loads((run/'protocol.json').read_text(encoding='utf-8'))
    control_path=Path(protocol['control_summary'])
    control=json.loads(control_path.read_text(encoding='utf-8')) if control_path.exists() else {}
    if control.get('status')!='passed' or control.get('reported_model')!=protocol['model']:
        print('waiting_minimal_new_model_control');return
    stage=next((s for s in ('PLT','Base','Plus') if s not in state.get('completed',{})),None)
    if stage is None:
        state['status']='completed';write_json(run/'state.json',state);return
    if stage!='PLT':
        image=subprocess.run(['docker','image','inspect','safecoder-python-validator:local'],
            capture_output=True,timeout=30)
        if image.returncode:
            state.update(status='blocked_environment',stage=stage,
                         blocked_reason='original_python_validator_image_missing')
            write_json(run/'state.json',state);print(json.dumps(state));return
    # 独占占用点在Popen前建立，避免两个监控同时派发；未知失败不自动移除或重发。
    lock=run/'launch.lock'
    with lock.open('x',encoding='utf-8') as f:
        f.write(stage)
    state.update(status='starting',stage=stage);write_json(run/'state.json',state)
    bundle=run/'source_bundle'
    cmd=[sys.executable,'-B','-X','utf8',str(bundle/'configs/cle_model_baseline_20261024/execute.py'),
         '--run-root',str(run),'--stage',stage]
    if stage!='PLT':
        cmd=[sys.executable,'-B','-X','utf8',str(bundle/'tools/vhdx_watchdog.py'),
            '--label',f'cle_v41_baseline_{stage}','--max-containers','4',
            '--report',str(run/f'watchdog_{stage}.json'),'--',*cmd]
    flags=(subprocess.CREATE_NO_WINDOW|subprocess.CREATE_NEW_PROCESS_GROUP) if os.name=='nt' else 0
    with (run/f'{stage}.stdout.log').open('ab') as stdout,(run/f'{stage}.stderr.log').open('ab') as stderr:
        process=subprocess.Popen(cmd,cwd=bundle,stdout=stdout,stderr=stderr,creationflags=flags)
    write_json(run/'launch.json',{'pid':process.pid,'stage':stage,'command':cmd})
    lock.unlink()
    print(json.dumps({'launched':stage,'pid':process.pid},ensure_ascii=False))


if __name__=='__main__':
    main()

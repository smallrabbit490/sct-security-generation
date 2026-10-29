"""接续K2题1243的向量TLS断连，复用原Q流程、成功响应及累计预算。"""
import argparse
import json
import os
from pathlib import Path
import shutil

from tools.cle_live_workbench.time_policy import child_environment, install

install()

from configs.cle_weekly_q_embedding_recovery_20261028 import resume as recovery
from methods.sct_trajectory.replay_journal import ReplayStop
from tools.cle_live_workbench import app


MODULE = 'configs.cle_weekly_q_embedding_c22d_20261028.resume'
recovery.MODULE = MODULE
recovery.STAGE, recovery.POOL, recovery.CELL = 'K2', 'D_grow', 'K2_1243'
recovery.IDENTITY = 'c22d39461824e6bc7c1b7c7af5c978608fdb79182b2ebd5bcec9bc0f18d57e6c-000001'
recovery.EVIDENCE = recovery.learn.RUN / (
    'workbench_monitor/autonomy/repair_evidence/Q.run_20261028T122224_attempt15'
    '/embedding_1243')


def main():
    """核对唯一失败和零API前缀，仅在Q空闲且总容量允许时接续单worker。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    os.environ.update(child_environment(os.environ))
    recovery.EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), recovery.EVIDENCE / 'recovery_entry.py')
    if args.action == 'launch':
        snapshot = app.Collector(recovery.learn.RUN, packages={}).collect(app.process_inventory())
        if any(p['package'] == 'FQ_LEARN' for p in snapshot['processes']):
            result = {'status': 'already_running'}
        elif snapshot['workers'] + 1 > 4:
            raise ReplayStop('required_worker_slot_not_available')
        else:
            result = recovery.launch()
    else:
        result = {'probe': recovery.probe, 'run': recovery.run}[args.action]()
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

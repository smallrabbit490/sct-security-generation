"""接续K3题1152的向量TLS断连，复用原Q顺序、成功响应和累计预算。"""
import argparse
import json
import os
from pathlib import Path
import shutil

from tools.cle_live_workbench.time_policy import child_environment, install

install()

from configs.cle_weekly_q_embedding_recovery_20261028 import resume as recovery
from configs.cle_weekly_q_tls12_20261028.resume import tls12_transport
from methods.sct_trajectory.replay_journal import ReplayStop
from tools.cle_live_workbench import app


MODULE = 'configs.cle_weekly_q_embedding_a0e4_20261028.resume'
recovery.MODULE = MODULE
recovery.STAGE, recovery.POOL, recovery.CELL = 'K3', 'D_grow', 'K3_1152'
recovery.IDENTITY = 'a0e43a2a7fc65d044dae5359e3c1cb54b36ed63e3e64250bd7db74d8df7b627c-000001'
recovery.EVIDENCE = recovery.learn.RUN / (
    'workbench_monitor/autonomy/repair_evidence/Q.run_20261028_attempt35'
    '/embedding_1152')
# 沿用上一段已采用的证书及主机名校验，仅复用TLS1.2传输实现。
recovery.verified_proxy_transport = tls12_transport


def main():
    """先核对唯一失败和零API前缀，仅在Q空闲且总容量允许时接续一个worker。"""
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

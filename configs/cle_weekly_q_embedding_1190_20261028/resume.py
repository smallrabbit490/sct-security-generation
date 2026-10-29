"""接续 K2 题1190已核实的向量TLS失败；保留原Q顺序、响应和累计预算。"""
import argparse
import json
from pathlib import Path
import shutil

from configs.cle_weekly_q_embedding_recovery_20261028 import resume as recovery


MODULE = 'configs.cle_weekly_q_embedding_1190_20261028.resume'
recovery.MODULE = MODULE
recovery.STAGE, recovery.POOL, recovery.CELL = 'K2', 'D_grow', 'K2_1190'
recovery.IDENTITY = '84bd85fad30c6acb3180a72be74e8d97e6c5235d4ffb14524135e93526de27c3-000001'
recovery.EVIDENCE = recovery.learn.RUN / 'workbench_monitor/autonomy/repair_evidence/Q.run_20261028T0748_attempt9'


def main():
    """仅绑定本次故障边界；复用既有零API前缀探针和单worker原生接续。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['probe', 'launch', 'run'])
    args = parser.parse_args()
    recovery.EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), recovery.EVIDENCE / 'recovery_entry.py')
    result = {'probe': recovery.probe, 'launch': recovery.launch, 'run': recovery.run}[args.action]()
    if result is not None:
        print(json.dumps({k: v for k, v in result.items() if k != 'audit'}, ensure_ascii=False))


if __name__ == '__main__':
    main()

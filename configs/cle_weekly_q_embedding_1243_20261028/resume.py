"""接续已核实的K1题1243向量TLS失败；复用原恢复逻辑，不改冻结实验。"""
import argparse
import json
from pathlib import Path
import shutil

from configs.cle_weekly_q_embedding_recovery_20261028 import resume as recovery


MODULE = 'configs.cle_weekly_q_embedding_1243_20261028.resume'
recovery.MODULE = MODULE
recovery.STAGE, recovery.POOL, recovery.CELL = 'K1', 'D_grow', 'K1_1243'
recovery.IDENTITY = 'c6c59714446a8fc07bbd5ab1130ff86a74d3e6e8289e9d6bae960da8948fc625-000001'
recovery.EVIDENCE = recovery.learn.RUN / 'workbench_monitor/autonomy/repair_evidence/Q.run_20261028T0438_attempt5'


def main():
    """调用原零API探针和单worker接续；仅替换本次故障边界及证据位置。"""
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

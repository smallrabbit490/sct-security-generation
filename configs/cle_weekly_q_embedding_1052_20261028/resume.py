"""接续K1题1052已核实的向量TLS失败，沿用原单worker恢复及累计预算。"""
import argparse
import json
from pathlib import Path
import shutil

from configs.cle_weekly_q_embedding_recovery_20261028 import resume as recovery


MODULE = 'configs.cle_weekly_q_embedding_1052_20261028.resume'
recovery.MODULE = MODULE
recovery.STAGE, recovery.POOL, recovery.CELL = 'K1', 'D_grow', 'K1_1052'
recovery.IDENTITY = 'ef2a0a20ecbf139f0752cb89accdc362a467698987825da42030da5cf0b581d3-000001'
recovery.EVIDENCE = recovery.learn.RUN / 'workbench_monitor/autonomy/repair_evidence/Q.run_20261028T0505_attempt6'


def main():
    """只绑定本次已核实边界；探针不请求网络，运行保持原名单、Q顺序与验证器。"""
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

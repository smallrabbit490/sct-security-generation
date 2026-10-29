"""接续K3题977的终选硬超时，精确复用完成前缀并保留累计预算。"""
from pathlib import Path
import shutil

from configs.cle_weekly_q_timeout_1344_20261028 import resume as recovery


MODULE = 'configs.cle_weekly_q_timeout_977_20261028.resume'
recovery.__doc__ = __doc__
recovery.MODULE = MODULE
recovery.EVIDENCE = recovery.original.RUN / (
    'workbench_monitor/autonomy/repair_evidence/Q.run_20261028_attempt36')
recovery.CELL = 'K3_977'
recovery.IDENTITY = '3900ca84649c38123671d9e69e9065c27fef83912b4d4bb13adbd539bc75ae54-000001'
recovery.SEGMENT = recovery.original.RUN / 'FQ_LEARN/K3/segment_023'
recovery.TARGET = (recovery.SEGMENT / 'journals' / recovery.CELL / 'requests'
                   / (recovery.IDENTITY + '.json'))


def main():
    """仅绑定已观测失败；沿用原前缀回放、互斥、时段、传输和预算检查。"""
    recovery.EVIDENCE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), recovery.EVIDENCE / 'task977_entry.py')
    recovery.main()


if __name__ == '__main__':
    main()

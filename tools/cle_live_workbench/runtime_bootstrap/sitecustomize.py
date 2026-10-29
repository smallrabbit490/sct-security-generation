"""仅在工作台显式传入本轮授权记录时，为新Python进程安装临时时段。"""
import os

if os.environ.get('CLE_TIME_OVERRIDE_RECORD'):
    from pathlib import Path
    from tools.cle_live_workbench.time_policy import RECORD, install
    if Path(os.environ['CLE_TIME_OVERRIDE_RECORD']).resolve() == RECORD.resolve():
        install()

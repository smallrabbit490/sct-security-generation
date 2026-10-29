"""Prevent a four-worker build from overlapping another CLE experiment."""
import json
import os
import subprocess
import msvcrt
from contextlib import contextmanager
from pathlib import Path

MARKERS = ('configs.cle_weekly_full_20261027.learn',
           'configs.cle_weekly_recovery_20261027.recover',
           'configs.cle_weekly_eval_20261027.', 'configs.cle_weekly_gate_20261027.',
           'configs.cle_weekly_fs_20261027.', 'configs.cle_weekly_granularity_20261027.',
           'configs.cle_weekly_granularity_gate_20261027.',
           'configs.cle_weekly_retrieval_20261027.execute',
           'configs.cle_weekly_proxy_recovery_20261027.runner',
           'transport_resume_stream_20261027.py', 'transport_resume_20261027.py',
           'transport_resume_general_20261027.py', 'recover_utf8_20261027.py',
           'recovery_1020_20261027.py')


def active_experiments(processes, own_pid=None):
    own_pid = os.getpid() if own_pid is None else own_pid
    result = []
    for item in processes:
        pid, command = item.get('ProcessId'), item.get('CommandLine') or ''
        if pid != own_pid and any(marker in command for marker in MARKERS) and any(
                action in command for action in (' run', ' resume', ' launch')):
            result.append(pid)
    return result


def current_active_experiments():
    command = 'Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress'
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                            capture_output=True, text=True, check=True)
    values = json.loads(result.stdout) if result.stdout.strip() else []
    return active_experiments([values] if isinstance(values, dict) else values)


@contextmanager
def exclusive_slots(root):
    """Hold each existing package lock while a four-worker build is active."""
    root = Path(root)
    files = [root / 'learning.lock'] + [root / name / 'execution.lock' for name in
             ('FQ_RETEST', 'FQ_GATE', 'FFS', 'FG_LABELS', 'FG_GATE', 'FR')]
    streams = []
    try:
        for path in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            stream = path.open('a+b')
            if stream.tell() == 0:
                stream.write(b'0')
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                stream.close()
                raise RuntimeError('another_CLE_package_holds_worker_slots') from None
            streams.append(stream)
        yield
    finally:
        for stream in reversed(streams):
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            stream.close()

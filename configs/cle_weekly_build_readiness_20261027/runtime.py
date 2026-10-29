"""BUILD 独立维护适配；不改活动学习/冻结评价的源码或旧记录。"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
from unittest.mock import patch

from configs.cle_weekly_build_20261027 import execute as original, resume, replay
from tools.cle_live_workbench import app
from .compare import compare

MODULE = 'configs.cle_weekly_build_readiness_20261027.execute'
HASH_SEED = '20261027'
ORIGINAL_SNAPSHOT = original.snapshot_sources


def active_workers(processes=None, *, own_pid=None, registered=None):
    """使用实际 CIM，任意题号向量恢复及登记入口都纳入四 worker 独占检查。"""
    processes = app.process_inventory() if processes is None else processes
    own_pid = os.getpid() if own_pid is None else own_pid
    if registered is None:
        registered = app.read_json(original.RUN / 'workbench_monitor/autonomy/registered_workers.json', [])
    own = next((p for p in processes if p['ProcessId'] == own_pid), {})
    excluded = {own_pid, own.get('ParentProcessId')}
    candidates = []
    for item in processes:
        command = item.get('CommandLine') or ''
        package = app.process_package(command)
        if MODULE in command and any(' ' + a in command for a in ('run', 'resume')):
            package = 'BUILD_C41'
        if not package:
            for row in registered:
                if item['ProcessId'] == row['pid'] and row['command_marker'] in command:
                    package = row['package']
                    break
        if package and item['ProcessId'] not in excluded:
            candidates.append({**item, 'package': package})
    parents = {p.get('ParentProcessId') for p in candidates}
    return [p for p in candidates if p['ProcessId'] not in parents]


def current_active_experiments():
    return [p['ProcessId'] for p in active_workers()]


def snapshot_sources(segment):
    ORIGINAL_SNAPSHOT(segment)
    for source in Path(__file__).parent.glob('*.py'):
        target = Path(segment) / 'source_bundle' / source.relative_to(original.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    (Path(segment) / 'runtime_identity.json').write_text(json.dumps({
        'entry': MODULE, 'PYTHONHASHSEED': HASH_SEED,
        'reason': 'native experience IDs use Python hash; replay must use the same interpreter seed',
        'workers': 4, 'protocol_changed': False}, indent=2), encoding='utf-8')


@contextmanager
def runtime():
    """只替换真实已观测的比较错误与运行识别；原模型、提示、验证及预算照用。"""
    with patch.object(original, 'current_active_experiments', current_active_experiments), \
         patch.object(resume, 'current_active_experiments', current_active_experiments), \
         patch.object(resume, 'snapshot_sources', snapshot_sources), \
         patch.object(replay, 'compare', compare):
        yield

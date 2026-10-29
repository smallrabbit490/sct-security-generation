"""只消费2026-10-28用户授权的临时时段；午夜到期后沿用原生门控。"""
import datetime as dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORD = Path('E:/ResearchRuns/CLE/20261027_full_requirements/workbench_monitor/time_override_20261028.json')
SHANGHAI = dt.timezone(dt.timedelta(hours=8))


def override_active(at=None, record=RECORD):
    if not record.is_file():
        return False
    value = json.loads(record.read_text(encoding='utf-8'))
    local = (at or dt.datetime.now(SHANGHAI)).astimezone(SHANGHAI)
    return (value['enabled'] is True
            and dt.datetime.fromisoformat(value['starts_at']) <= local
            < dt.datetime.fromisoformat(value['expires_at']))


def child_environment(environment):
    """仅后续维护CLI及其原生子进程继承，不注入或重启已经运行的学习。"""
    result = dict(environment)
    if RECORD.is_file():
        bootstrap = Path(__file__).with_name('runtime_bootstrap')
        paths = [str(bootstrap), str(ROOT), result.get('PYTHONPATH', '')]
        result['PYTHONPATH'] = os.pathsep.join(path for path in paths if path)
        result['CLE_TIME_OVERRIDE_RECORD'] = str(RECORD)
    return result


def install(record=RECORD):
    """新进程启动时包住原函数；模型、提示、预算、验证及冻结源码均保持原样。"""
    from methods.sct_trajectory import provider_policy
    original = provider_policy.ensure_model_call_allowed
    if getattr(original, '_cle_dated_override', False):
        return

    def ensure(model, now=None):
        if model == provider_policy.CURRENT_MODEL and override_active(now, record):
            return
        return original(model, now=now)

    ensure._cle_dated_override = True
    provider_policy.ensure_model_call_allowed = ensure

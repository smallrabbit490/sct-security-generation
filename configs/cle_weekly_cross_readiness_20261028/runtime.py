"""C41 冻结消费与源快照；沿用原 P7、检索、原验证器和累计预算。"""
import hashlib
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from configs.cle_weekly_cross_20261027 import new_bank_runner as original
from configs.cle_weekly_eval_20261027 import retest as base
from methods.sct_trajectory.replay_journal import ReplayStop, write_json

MODULE = 'configs.cle_weekly_cross_readiness_20261028.execute'
PACKAGE = base.RUN / 'FX_GATE/V41_C41'


@contextmanager
def json_encoding():
    """复用活动 FFS 的已观测孤立代理项修复；仅在不能 UTF-8 编码时改用合法 JSON 转义。"""
    original_dumps = json.dumps
    def safe_dumps(*args, **kwargs):
        result = original_dumps(*args, **kwargs)
        try:
            result.encode('utf-8')
        except UnicodeEncodeError:
            if kwargs.get('ensure_ascii', True):
                raise
            result = original_dumps(*args, **{**kwargs, 'ensure_ascii': True})
        return result
    with patch.object(json, 'dumps', safe_dumps):
        yield


def snapshot_sources(destination, prior):
    directories = ('methods', 'src', 'configs/cle_weekly_full_20261027',
        'configs/cle_weekly_eval_20261027', 'configs/cle_weekly_cross_20261027',
        'configs/cle_weekly_cross_readiness_20261028', 'configs/cle_v41_relation_20261026',
        'configs/cle_v41_migration_20261025', 'configs/cle_weekly_proxy_recovery_20261027')
    paths = [p for d in directories for p in (base.ROOT / d).rglob('*.py')]
    identity = {p.relative_to(base.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    for previous in prior:
        if base.read(previous / 'source_identity.json') != identity:
            raise ReplayStop('cross_runtime_source_changed')
    for source in paths:
        target = destination / 'source_bundle' / source.relative_to(base.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    write_json(destination / 'source_identity.json', identity)


class CrossNewBank(original.NewBankRetest):
    """只更正原入口 inspect_native_row 拼写，独立保存实际源文件；不改变科学流程。"""
    worker_limit = 3
    runner_module = MODULE

    def package_directory(self):
        return PACKAGE

    def __init__(self, *args, **kwargs):
        with json_encoding(), patch.object(original, 'snapshot_sources', snapshot_sources):
            super().__init__(*args, **kwargs)

    def execute(self):
        with json_encoding():
            return super().execute()

    def validate_saved_rows(self, rows):
        base.FrozenRetest.validate_saved_rows(self, rows)
        for row in rows:
            self.inspect_native_row(row)

"""已观测Windows替换冲突的有限本地恢复，不调用API。"""
from pathlib import Path

import pytest

from configs.cle_weekly_fs_checkpoint_20261028 import resume


@pytest.mark.parametrize('failures,success', [(1, True), (3, False)])
def test_only_rename_is_retried(tmp_path, monkeypatch, failures, success):
    calls = []
    waits = []
    def replace(path, target):
        calls.append((path, target))
        if len(calls) <= failures:
            raise PermissionError('observed Windows read handle conflict')
        return target
    monkeypatch.setattr(Path, 'replace', replace)
    src, dst = tmp_path / 'rows.jsonl.tmp', tmp_path / 'rows.jsonl'
    with resume.checkpoint_replace_retry(tmp_path, waits.append):
        if success:
            assert src.replace(dst) == dst
        else:
            with pytest.raises(PermissionError):
                src.replace(dst)
    assert Path.replace is replace
    assert len(calls) == (2 if success else 3)
    assert len(waits) == (1 if success else 2)


def test_other_files_do_not_gain_retries(tmp_path, monkeypatch):
    def replace(path, target):
        raise PermissionError('unrelated file')
    monkeypatch.setattr(Path, 'replace', replace)
    with resume.checkpoint_replace_retry(tmp_path, lambda _: pytest.fail('unexpected retry')):
        with pytest.raises(PermissionError):
            (tmp_path / 'other.json.tmp').replace(tmp_path / 'other.json')

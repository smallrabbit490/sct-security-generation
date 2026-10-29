"""恢复必须逐格复用；单格内容变化不得进入付费阶段。"""
from types import SimpleNamespace

import pytest

from . import resume


@pytest.fixture
def study(tmp_path, monkeypatch):
    monkeypatch.setattr(resume, 'EXPECTED', 2)
    monkeypatch.setattr(resume, 'EVIDENCE', tmp_path / 'evidence')
    source = tmp_path / 'old'
    rows = [{'cell_id': 'a', 'code': 'old_a'}, {'cell_id': 'b', 'code': 'old_b'}]
    for row in rows:
        resume.write_json(source / 'task_rows' / (row['cell_id'] + '.json'), row)
    resume.write_json(resume.EVIDENCE / 'completed_cells_before.json',
                      [{'cell_id': row['cell_id']} for row in rows])
    return SimpleNamespace(sources=[source], rows=rows,
                           io=SimpleNamespace(save=lambda *args: None))


def test_all_completed_cells_are_compared_and_saved(study):
    resume.verify_completed(study)
    proof = resume.read(resume.EVIDENCE / 'native_reuse_verification.json')
    assert proof['matched_cells'] == 2
    assert {item['cell_id'] for item in proof['matches']} == {'a', 'b'}
    assert proof['new_HTTP_before_verification'] == 0


def test_changed_completed_code_stops_before_resume(study):
    study.rows[0]['code'] = 'changed'
    with pytest.raises(resume.ReplayStop, match='completed_row_changed'):
        resume.verify_completed(study)
    assert not (resume.EVIDENCE / 'native_reuse_verification.json').exists()

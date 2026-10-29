"""复用已授权恢复逻辑识别旧失败的成功后继，再执行原生离线回放。

只修复原入口把已解决旧journal也视为未决的问题；不更改原记录、冻结源码、
请求参数、验证器或Q规则。所有请求仍由原生offline入口禁止联网。
"""
import json
import runpy
import sys
from pathlib import Path

from configs.cle_weekly_full_20261027 import learn
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


def main():
    sources = [Path(p) for p in learn.read(learn.RUN / 'execution_index.json')['FQ_LEARN_K0']]
    if learn.read(sources[-1] / 'state.json')['status'] != 'completed':
        raise ReplayStop('K0_not_completed')
    helper = runpy.run_path(str(learn.RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'))
    pending, rejected = helper['classify'](sources)
    if pending or rejected:
        raise ReplayStop('K0_has_actual_unresolved_requests')
    # 按cell和原生请求identity核对成功记录，旧失败原样保留。
    records = [(p, learn.read(p)) for root in sources
               for p in (root / 'journals').glob('*/requests/*.json')]
    completed = {(p.parent.parent.name, row['identity'])
                 for p, row in records if row.get('status') == 'completed'}
    resolved = []
    for path, row in records:
        if row.get('status') != 'completed':
            key = (path.parent.parent.name, row['identity'])
            if key not in completed:
                raise ReplayStop('failed_record_without_successful_successor')
            resolved.append(str(path))
    out = learn.RUN / 'analysis/K0/maintenance_20261028'
    write_json(out / 'resolved_requests.json', {
        'stage': 'K0', 'old_failed_records_with_completed_successor': resolved,
        'actual_unresolved': 0, 'original_records_modified': False,
        'recovery_helper': str(learn.RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'),
        'new_HTTP': 0,
    })
    original_argv = sys.argv
    try:
        sys.argv = ['learn', 'replay', '--stage', 'K0']
        with helper['runtime']():
            learn.main()
    finally:
        sys.argv = original_argv
    result = learn.read(learn.RUN / 'FQ_LEARN/K0/zero_API_replay/replay_result.json')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

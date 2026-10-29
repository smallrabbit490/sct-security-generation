"""核对K3旧失败已有精确成功后继后，执行原生离线响应和动态验证回放。

不修改旧journal/state/source_identity，不调用模型或Embedding，不改变Q信用。
"""
import json
import os
import runpy
import sys
from pathlib import Path

from configs.cle_weekly_full_20261027 import learn
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


def main():
    sources = [Path(p) for p in learn.read(learn.RUN / 'execution_index.json')['FQ_LEARN_K3']]
    if learn.read(sources[-1] / 'state.json')['status'] != 'completed':
        raise ReplayStop('K3_not_completed')
    helper_path = learn.RUN / 'FQ_LEARN/transport_resume_stream_20261027.py'
    helper = runpy.run_path(str(helper_path))
    pending, rejected = helper['classify'](sources)
    if pending or rejected:
        raise ReplayStop('K3_has_actual_unresolved_requests')
    records = [(p, learn.read(p)) for root in sources
               for p in (root / 'journals').glob('*/requests/*.json')]
    completed = {(p.parent.parent.name, row['identity'])
                 for p, row in records if row.get('status') == 'completed'}
    resolved = []
    for path, row in records:
        if row.get('status') != 'completed':
            if (path.parent.parent.name, row['identity']) not in completed:
                raise ReplayStop('failed_record_without_successful_successor')
            resolved.append(str(path))
    out = learn.RUN / 'analysis/K3/maintenance_20261028'
    write_json(out / 'resolved_requests.json', {
        'stage': 'K3', 'old_failed_records_with_completed_successor': resolved,
        'actual_unresolved': 0, 'original_records_modified': False,
        'recovery_helper': str(helper_path), 'new_HTTP': 0,
    })
    write_json(out / 'replay_launch.json', {
        'pid': os.getpid(), 'command': [sys.executable, '-B', '-X', 'utf8', '-m',
        'configs.cle_weekly_k3_analysis_recovery_20261028.replay'],
        'started_utc': learn.now(), 'workers': 0, 'offline': True,
    })
    register = learn.RUN / 'workbench_monitor/autonomy/registered_workers.json'
    entries = learn.read(register) if register.exists() else []
    entries.append({'pid': os.getpid(), 'package': 'FQ_LEARN', 'workers': 0,
                    'command_marker': 'configs.cle_weekly_k3_analysis_recovery_20261028.replay'})
    write_json(register, entries)
    previous_argv = sys.argv
    try:
        sys.argv = ['learn', 'replay', '--stage', 'K3']
        with helper['runtime']():
            learn.main()
    finally:
        sys.argv = previous_argv
    print(json.dumps(learn.read(learn.RUN / 'FQ_LEARN/K3/zero_API_replay/replay_result.json'),
                     ensure_ascii=False))


if __name__ == '__main__':
    main()

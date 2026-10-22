"""恢复已观测的进程退出：保留未决请求原件，复用完整题前缀，不改变原P7/Q协议。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import traceback

from methods.cle_ablation import run_memory_q_online as study
from configs.cle_q_online_20261020.execute import report

RECOVERY = 'cle-q-online-process-exit-recovery-20261021-v1'
RECEIPT = study.OUT / 'recovery_20261021.json'
OriginalRequests = study.Requests


def prepare():
    """仅批准已确认退出留下的一次未决请求；未完成题无可重建中间结果，整题恢复。"""
    study.verify()
    if RECEIPT.exists():
        return study.read(RECEIPT)
    bank, events, records = study.replay('D_init')
    frozen = study.load_memory(study.OUT / 'D_init/frozen/m_star_q.jsonl')
    assert [n.to_dict() for n in bank] == [n.to_dict() for n in frozen]
    assert len(records) == 128 and records[-1]['task_id'] == '1027'
    pending = [(p, study.read(p)) for p in (study.OUT / 'D_init/requests').glob('*.json')
               if study.read(p)['status'] == 'started']
    assert len(pending) == 1 and pending[0][0].name == '00866.json'
    assert pending[0][1]['task_id'] == '1245'
    assert not (study.OUT / 'D_init/task_rows/1245.json').exists()
    receipt = {'recovery': RECOVERY, 'method_protocol': study.PROTOCOL,
        'reason': 'process exited without exception record; exact host cause unobserved',
        'complete_prefix': 128, 'restart_task': '1245', 'checkpoint_Q_replay_exact': True,
        'completed_records_reexecuted': 0, 'original_request_modified': False,
        'unresolved_requests': [{'path': str(p.relative_to(study.OUT)), 'task_id': r['task_id'],
            'status': 'interrupted_response_and_usage_unknown', 'returned_tokens': None,
            'may_have_been_billed': True} for p, r in pending],
        'partial_task_known_completed_requests': ['D_init/requests/00864.json', 'D_init/requests/00865.json'],
        'partial_task_known_tokens': 34166,
        'parameters_changed': False, 'launch': 'detached hidden process with stdout/stderr files'}
    study.write(RECEIPT, receipt)
    snapshot = study.OUT / 'source_snapshot/configs/cle_q_online_20261020/resume_after_exit.py'
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(__file__, snapshot)
    return receipt


class ReconciledRequests(OriginalRequests):
    """沿用原请求和成本接口；旧未决请求按未知用量留存，不再误作活跃请求或填零。"""
    def __init__(self, stage, workers=1):
        from methods.sct_trajectory.run_closed_loop import _requester
        self.stage, self.protocol = stage, study.read(study.OUT / 'protocol.json')
        self.lock, self.stopped = threading.Lock(), threading.Event()
        receipt = study.read(RECEIPT)
        approved = {r['path'] for r in receipt['unresolved_requests']}
        grow_receipt = study.OUT / 'process_exit_recovery_20261021_v4.json'
        if grow_receipt.exists():
            approved.update(r['path'] for r in study.read(grow_receipt)['unresolved_requests'])
        prior = [(p, study.read(p)) for p in (study.OUT / stage / 'requests').glob('*.json')]
        for path, request in prior:
            if request['status'] == 'started':
                assert str(path.relative_to(study.OUT)) in approved, 'new_unresolved_request_requires_reconciliation'
        self.count = len(prior)
        self.tokens = sum(r.get('total_tokens', 0) for _, r in prior)
        self.native = _requester('deepseek-v3.2', 60 if stage == 'D_gate' else 120,
            max_tokens=4096, max_inflight=workers, thinking='disabled')


def main():
    prepare()
    study.Requests = ReconciledRequests
    study.write(study.OUT / 'recovery_process.json', {'pid': os.getpid(), 'recovery': RECOVERY,
        'method_protocol': study.PROTOCOL})
    meta = study.read(study.OUT / 'run_metadata.json')
    meta.update(recovery=RECOVERY, status='resuming_D_init')
    study.write(study.OUT / 'run_metadata.json', meta)
    try:
        for stage in ('D_init', 'D_grow'):
            study.learn(stage)
            report()
        study.gate()
        from configs.cle_q_online_20261020.summarize_final import analyze
        analyze()
    except Exception as exc:
        meta = study.read(study.OUT / 'run_metadata.json')
        meta.update(status='stopped_technical', exception_type=type(exc).__name__, recovery=RECOVERY)
        study.write(study.OUT / 'run_metadata.json', meta)
        study.write(study.OUT / 'recovery_exception_20261021.json',
            {'type': type(exc).__name__, 'traceback': traceback.format_exc()})
        raise
    finally:
        report()


if __name__ == '__main__':
    main()

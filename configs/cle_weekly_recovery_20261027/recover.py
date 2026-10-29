"""按2026-10-27直接授权补发题437未决选卡；原请求、未知费用和成功前缀不改写。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from configs.cle_weekly_full_20261027 import learn
from methods.sct_trajectory.replay_journal import ReplayStop, write_json


IDENTITY = '6c0c3d334fe11db8ab547242286295fff03b39fc21cc84afbd588c7c17274a1d-000001'
CELL = 'K0_437'
ORIGINAL = learn.RUN/'FQ_LEARN/K0/segment_001'
FAILED_REQUEST = ORIGINAL/'journals'/CELL/'requests'/(IDENTITY+'.json')
AUTHORIZATION = learn.RUN/'FQ_LEARN/K0/authorized_reissue_20261027.json'


def authorize():
    """登记本次人类直接授权；不把未核清的旧调用标成免费或未执行。"""
    failed = learn.read(FAILED_REQUEST)
    if failed['identity'] != IDENTITY or failed['status'] != 'failed_or_unresolved' or not failed['selector']:
        raise ReplayStop('specific_original_failed_selector_no_longer_matches')
    value = {'scope': 'single_original_unresolved_selector_reissue_then_continue_original_learning',
        'authorization_source': 'direct_user_message_20261027',
        'user_instruction': '那题直接重跑了，后台我没有权限也没有账号',
        'authorized_utc': learn.now(), 'original_request': str(FAILED_REQUEST),
        'original_identity': IDENTITY, 'cell_id': CELL,
        'billing_reconciliation': 'unavailable; user has no provider account or permission',
        'old_execution_or_charge': 'unknown', 'original_failed_records_preserved': True,
        'completed_63_tasks_reused': True, 'successful_task437_prefix_reused': True,
        'model_and_scientific_rules_changed': False, 'native_retry_rules_changed': False,
        'request_window_unchanged': True, 'budget_reset': False,
        'authorization_does_not_cover_other_unresolved_requests': True}
    if AUTHORIZATION.exists():
        return learn.read(AUTHORIZATION)
    write_json(AUTHORIZATION, value)
    return value


def approved_unresolved(sources):
    """只豁免原段那一条失败；后续段再失败仍阻断，不形成无限补发。"""
    learn.read(AUTHORIZATION)
    return [path for path in ORIGINAL_UNRESOLVED(sources) if Path(path).resolve() != FAILED_REQUEST.resolve()]


ORIGINAL_UNRESOLVED = learn.unresolved_requests
ORIGINAL_STAGE = learn.LearningStage


def request_identity(journal, prompt):
    public = {'settings': learn.wiring.SETTINGS, 'prompt': str(prompt),
              'selector': type(prompt).__name__ == 'SelectorPrompt'}
    digest = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f'{digest}-{journal.counts[digest]+1:06d}', public


class AuthorizedLearningStage(ORIGINAL_STAGE):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        receipt = learn.read(AUTHORIZATION)
        source = Path(__file__).resolve()
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        for prior in self.sources:
            saved = prior/'recovery_source_identity.json'
            if saved.exists() and learn.read(saved)['sha256'] != digest:
                raise ReplayStop('authorized_recovery_source_changed_requires_review')
        target = self.out/'source_bundle/configs/cle_weekly_recovery_20261027/recover.py'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        self.io.save('recovery_source_identity', {'path': str(source), 'sha256': digest})
        self.io.save('authorized_recovery', receipt)
        if self.stage != 'K0':
            return
        failed = learn.read(FAILED_REQUEST)
        prior_reissue = [path for root in self.sources if root.resolve() != ORIGINAL.resolve()
                         for path in (root/'journals'/CELL/'requests').glob(IDENTITY+'.json')]
        self.reissue_consumed = bool(prior_reissue)
        original_request_for = self.io.request_for

        def request_for(cell):
            request = original_request_for(cell)
            if cell != CELL:
                return request

            def guarded(prompt):
                journal = self.io.journal(cell)
                identity, public = request_identity(journal, prompt)
                saved = journal.records.get(identity)
                if saved is None and not self.reissue_consumed:
                    expected = {key: failed[key] for key in ('settings', 'prompt', 'selector')}
                    if identity != IDENTITY or public != expected:
                        raise ReplayStop('first_new_task437_request_differs_from_authorized_selector')
                    self.reissue_consumed = True
                    self.io.save('authorized_reissue_boundary', {
                        'identity': identity, 'cell_id': cell, 'old_charge_status': 'unknown',
                        'authorization': str(AUTHORIZATION), 'event': 'authorized_logical_boundary_reached',
                        'not_proof_of_physical_dispatch': True})
                return request(prompt)
            return guarded
        self.io.request_for = request_for


@contextmanager
def recovery_runtime():
    """进程内临时接线，原learn.py和旧产物保持原样。"""
    previous_unresolved, previous_stage = learn.unresolved_requests, learn.LearningStage
    learn.unresolved_requests, learn.LearningStage = approved_unresolved, AuthorizedLearningStage
    try:
        yield
    finally:
        learn.unresolved_requests, learn.LearningStage = previous_unresolved, previous_stage


def prefix_probe():
    """零API运行437保存前缀，到缺失选卡边界停止；63题只重建Q，不重生成。"""
    target = learn.RUN/'FQ_LEARN/K0/authorized_prefix_probe_20261027'
    result_path = target/'prefix_probe_result.json'
    if result_path.exists():
        return learn.read(result_path)
    with recovery_runtime():
        worker = AuthorizedLearningStage('K0', 'D_init', [ORIGINAL], offline=True, destination=target)
        worker.rows = learn.restore_prefix(worker.cells, worker.sources, worker.bank, worker.eligibility)
        error = None
        try:
            worker.execute()
        except ReplayStop as exc:
            error = str(exc)
        journal = worker.io.journals.get(CELL)
        consumed = len(journal.consumed) if journal else 0
        expected = len(list((ORIGINAL/'journals'/CELL/'requests').glob('*.json')))-1
        new_http = len(list((target/'wire').glob('*.request.json')))
        passed = (len(worker.rows) == 63 and consumed == expected == 6 and new_http == 0
                  and error == 'replay_missing_request:'+IDENTITY)
        result = {'status': 'passed' if passed else 'different', 'completed_prefix_tasks': len(worker.rows),
            'Q_covered_cards': sum(node.q_visits > 0 for node in worker.bank),
            'task437_saved_logical_responses_consumed': consumed, 'stopped_at': error,
            'new_HTTP': new_http, 'original_records_modified': False,
            'authorization': str(AUTHORIZATION), 'not_a_completed_task437_result': True}
        write_json(result_path, result)
        return result


def launch():
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(learn.wiring.SETTINGS['model'])
    if prefix_probe()['status'] != 'passed':
        raise ReplayStop('saved_task437_prefix_replay_not_verified')
    script = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -match 'configs.cle_weekly_(full|recovery)_20261027.(learn|recover) (run|resume)' } | Select-Object ProcessId | ConvertTo-Json -Compress"
    actual = subprocess.run(['powershell', '-NoProfile', '-Command', script], capture_output=True, text=True, check=True)
    if actual.stdout.strip():
        return {'status': 'already_running'}
    root = learn.RUN/'FQ_LEARN'
    with (root/'authorized_resume.stdout.log').open('a', encoding='utf-8') as stdout, (root/'authorized_resume.stderr.log').open('a', encoding='utf-8') as stderr:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
            'configs.cle_weekly_recovery_20261027.recover', 'run'], cwd=learn.ROOT,
            stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    value = {'status': 'launched', 'pid': process.pid, 'started_utc': learn.now(),
             'authorization': str(AUTHORIZATION), 'completed_prefix_preserved': 63}
    write_json(root/'authorized_resume_launch.json', value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['authorize', 'prefix-probe', 'launch', 'run'])
    action = parser.parse_args().action
    if action == 'authorize':
        result = authorize()
    elif action == 'prefix-probe':
        result = prefix_probe()
    elif action == 'launch':
        result = launch()
    else:
        if prefix_probe()['status'] != 'passed':
            raise ReplayStop('saved_task437_prefix_replay_not_verified')
        with recovery_runtime():
            learn.coordinate(resume_stage='K0')
        result = {'status': 'learning_completed_pending_replay_analysis'}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

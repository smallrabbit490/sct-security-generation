"""IR02/IR03单次编辑、原验证、保存响应回放；不涉及Q或标签学习。"""
import argparse
import json
from pathlib import Path
import shutil
import urllib.request

from configs.cle_v41_relation_20261026.execution import StudyExecution
from configs.cle_v41_relation_20261026.wiring import SETTINGS
from configs.cle_weekly_full_20261027.prepare import configure_validation
from methods.sct_trajectory.agent_pipeline import _content, strip_code_fence
from methods.sct_trajectory.closed_loop import validate_and_state
from methods.sct_trajectory.replay_journal import ReplayStop, write_json
from .prepare import RUN

ROOT = RUN / 'impact_radius_20261028'


def inputs(stage):
    path = ROOT / 'prepare' / stage
    cells = json.loads((path / 'schedule.json').read_text(encoding='utf-8'))
    tasks = json.loads((path / 'tasks.json').read_text(encoding='utf-8'))
    budget = json.loads((path / 'budget.json').read_text())
    expected = 48 if stage == 'IR02' else 96
    assert len(cells) == len({c['cell_id'] for c in cells}) == expected
    for tid in tasks:
        for repeat in (1, 2):
            pair = [c for c in cells if c['task_id'] == tid and c['repeat'] == repeat]
            assert len(pair) == 2 and pair[0]['initial_cell'] == pair[1]['initial_cell']
            assert pair[0]['card_ids'] == pair[1]['card_ids']
            assert pair[1]['prompt'].startswith(pair[0]['prompt'])
    return path, cells, tasks, budget


def execute(stage, offline=False):
    path, cells, tasks, cap = inputs(stage)
    root = ROOT / stage
    index = root / 'execution_index.json'
    sources = [Path(p) for p in json.loads(index.read_text())['segments']] if index.exists() else []
    if offline and not sources:
        raise ReplayStop('no_saved_run_to_replay')
    if not offline:
        review = json.loads((ROOT / 'prepare/public_review.json').read_text(encoding='utf-8'))
        if review.get(stage, {}).get('status') != 'passed':
            raise ReplayStop('public_requirements_review_pending')
        if stage == 'IR03':
            decision = json.loads((ROOT / 'IR02/decision.json').read_text())
            if decision.get('status') != 'decided' or decision.get('advance') != 'proceed':
                raise ReplayStop('IR02_did_not_pass_confirmation_gate')
        for source in sources:
            for f in (source / 'journals').glob('*/requests/*.json'):
                if json.loads(f.read_text(encoding='utf-8'))['status'] != 'completed':
                    raise ReplayStop('unresolved_request_requires_explicit_reconciliation')
    target = root / ('zero_API_replay' if offline else f'segment_{len(sources)+1:03d}')
    if target.exists():
        raise ReplayStop('output_exists_preserve_prior_result')
    protocol = {'protocol': 'cle-impact-radius-fixed-edit-v1', 'planned_P7': len(cells),
        'paid_execution_enabled': not offline, 'model_settings': SETTINGS,
        'Q_updates': 0, 'new_cards': 0, 'repairs': 0,
        'budget_proposed': {'conservative_model_and_embedding_tokens': cap['input_utf8_byte_token_upper_bound'] + cap['output_tokens_cap'],
            'total_physical_HTTP_attempts': cap['physical_HTTP_cap'], 'embedding_HTTP_attempts_included_in_total': 0}}
    def forbidden(*args, **kwargs):
        raise ReplayStop('replay_missing_response_no_new_network')
    def factory(identity):
        if offline:
            return forbidden
        from methods.sct_trajectory.run_closed_loop import _requester
        return _requester(SETTINGS['model'], 180, 4096, 4, thinking='disabled', stream=True,
            endpoint='https://api.chatanywhere.org/v1/chat/completions', hard_timeout=300, gate_wait_timeout=600)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({'https': 'http://127.0.0.1:7897'}))
    io = StudyExecution(target, protocol, cells, client_factory=factory,
        physical_open=forbidden if offline else opener.open, live=not offline, fixed_eight=False,
        resume_sources=sources, protected_paths=[path / n for n in ('schedule.json', 'tasks.json', 'budget.json')])
    for source in sources:
        if json.loads((source/'input_identity.json').read_text()) != io.inputs_before:
            raise ReplayStop('frozen_input_changed')
    io.save('input_identity', io.inputs_before)
    shutil.copy2(__file__, target / 'runner_source.py')
    if not offline:
        write_json(index, {'segments': list(map(str, sources)) + [str(target)]})
    rows = {}
    for source in sources:
        for f in (source/'task_rows').glob('*.json'):
            r = json.loads(f.read_text(encoding='utf-8'))
            rows[r['cell_id']] = r
    saved = dict(rows)
    configure_validation()
    try:
        with io.physical_records():
            for cell in cells:
                if cell['cell_id'] in rows and not offline:
                    continue
                response = io.request_for(cell['cell_id'])(cell['prompt'])
                error = None
                try:
                    code = strip_code_fence(_content(response))
                except ValueError as exc:
                    code, error = '', str(exc)
                if code:
                    evidence, state = validate_and_state(tasks[cell['task_id']], code, timeout=20)
                else:
                    evidence, state = {}, 'unmeasured'
                row = {k: cell[k] for k in ('cell_id', 'task_id', 'family_id', 'repeat', 'condition')}
                row.update(code=code, evidence=evidence, state=state, error=error)
                if offline and row != saved.get(cell['cell_id']):
                    raise ReplayStop('native_replay_difference:' + cell['cell_id'])
                io.save('task_rows/' + cell['cell_id'], row)
                rows[cell['cell_id']] = row
                io.save('summary', {'status': 'running', 'completed': len(rows), 'planned': len(cells)})
        result = {'status': 'completed', 'completed': len(rows), 'planned': len(cells),
                  'experiment_HTTP': 0 if offline else 'see_cumulative_budget', 'budget': io.budget.snapshot()}
        io.save('summary', result)
        if offline:
            io.save('replay_result', {'status': 'passed', 'completed': len(rows), 'new_HTTP': 0})
        print(json.dumps({'status': 'completed', 'completed': len(rows)}))
    except BaseException as exc:
        io.save('state', {'status': 'needs_technical_recovery', 'completed': len(rows), 'reason': str(exc)})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['check', 'run', 'replay'])
    p.add_argument('--stage', choices=['IR02', 'IR03'], default='IR02')
    a = p.parse_args()
    if a.action == 'check':
        _, cells, _, _ = inputs(a.stage)
        print(json.dumps({'status': 'inputs_verified', 'planned': len(cells), 'new_HTTP': 0})); return
    import msvcrt
    folder = ROOT / a.stage
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'execution.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            execute(a.stage, offline=a.action == 'replay')
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == '__main__':
    main()

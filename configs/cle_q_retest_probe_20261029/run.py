"""54题冻结Q有界回测；沿用原生P7，只缩小固定名单。"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from configs.cle_weekly_reduced_20261028 import retest as base
from methods.sct_trajectory.replay_journal import write_json, ReplayStop

MODULE = 'configs.cle_q_retest_probe_20261029.run'
OUT = base.RUN / 'probe_relay_20261028/Q.retest'


def prepare():
    task = next(t for t in base.read(base.ROOT / 'tools/cle_live_workbench/autonomy_plan.json')['tasks']
                if t['id'] == 'Q.retest.probe')
    ids = task['probe_scope']['task_ids']
    source = base.RUN / 'FQ_RETEST/inputs'
    cells = [c for c in base.read(source / 'schedule.json') if c['task_id'] in ids]
    assert len(ids) == len(set(ids)) == 54
    assert len(cells) == len({c['cell_id'] for c in cells}) == 540
    assert all({c['condition'] for c in cells if c['task_id'] == t and c['repeat'] == r}
               == set(base.CONDITIONS) for t in ids for r in (1, 2))
    tasks = base.read(source / 'tasks.json')
    protocol = base.read(source / 'protocol.json')
    protocol.update(protocol='cle-q-retest-fixed54-probe-20261029-v1', planned_P7=540, task_count=54,
                    diagnostic_task_count=54, execution_scope='probe',
                    primary_comparisons=['Q2_K3-Q1'], interpretation='固定54题五条件两重复，不外推全273题')
    protocol['budget_proposed'] = {'conservative_model_and_embedding_tokens': 81000000,
        'total_physical_HTTP_attempts': 21600, 'embedding_HTTP_attempts_included_in_total': 8640}
    for name, value in [('protocol', protocol), ('tasks', {t: tasks[t] for t in ids}), ('schedule', cells)]:
        p = OUT / 'inputs' / (name + '.json')
        if p.exists():
            assert base.read(p) == value, 'frozen_probe_input_changed'
        else:
            write_json(p, value)
    return {'status': 'passed', 'task_count': 54, 'cells': 540,
            'all_five_conditions_per_repeat': True, 'new_HTTP': 0,
            'dependencies': base.dependencies()}


def configure():
    base.package_root = lambda: OUT
    base.FrozenRetest.runner_module = MODULE


def run(workers):
    import msvcrt
    configure()
    base.FrozenRetest.worker_limit = workers
    dep = base.dependencies()
    if not dep['ready']:
        raise ReplayStop(str(dep))
    with (OUT / 'execution.lock').open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            index = OUT / 'execution_index.json'
            sources = [Path(p) for p in base.read(index)['segments']] if index.exists() else []
            study = base.FrozenRetest(sources, destination=OUT / f'segment_{len(sources)+1:03d}')
            shutil.copy2(__file__, study.out / 'bounded_entry.py')
            assert len(study.cells) == 540 and len(study.tasks) == 54
            write_json(index, {'segments': list(map(str, sources)) + [str(study.out)]})
            study.execute()
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prepare', 'check', 'launch', 'run'])
    p.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    a = p.parse_args()
    result = prepare()
    if a.action in ('prepare', 'check'):
        write_json(OUT / 'bounded_offline_checks.json', result)
        print(json.dumps(result)); return
    if not result['dependencies']['ready']:
        raise ReplayStop(str(result['dependencies']))
    if a.action == 'run':
        run(a.workers); return
    from methods.sct_trajectory.provider_policy import ensure_model_call_allowed
    ensure_model_call_allowed(base.wiring.SETTINGS['model'])
    ps = "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*" + MODULE + " run*' } | Select-Object ProcessId | ConvertTo-Json -Compress"
    if subprocess.check_output(['powershell', '-NoProfile', '-Command', ps], text=True).strip():
        raise ReplayStop('probe_already_running')
    command = [sys.executable, '-B', '-X', 'utf8', '-m', MODULE, 'run', '--workers', str(a.workers)]
    with (OUT / 'stdout.log').open('a', encoding='utf-8') as out, (OUT / 'stderr.log').open('a', encoding='utf-8') as err:
        child = subprocess.Popen(command, cwd=base.ROOT, stdout=out, stderr=err,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
    write_json(OUT / 'launch.json', {'pid': child.pid, 'command': command, 'workers': a.workers})
    print(json.dumps({'status': 'launched', 'pid': child.pid, 'planned': 540}))


if __name__ == '__main__':
    main()

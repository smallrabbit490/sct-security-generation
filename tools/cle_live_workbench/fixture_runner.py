"""独立验收用的本地请求替身；不导入项目、不调用网络或真实模型。"""
import argparse
import ctypes
import datetime as dt
import importlib.util
import json
import msvcrt
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def event(kind, **values):
    with (ROOT / 'events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': now(), 'pid': os.getpid(), 'kind': kind, **values}) + '\n')


def alive(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        value = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(value))) and value.value == 259
    finally:
        kernel.CloseHandle(handle)


def folder(stage):
    return ROOT / f'SELFTEST_{stage}' / 'segment_001'


def launch(stage):
    with (ROOT / 'launch.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        try:
            previous = read(ROOT / 'active_worker.json', {})
            if previous.get('pid') and alive(previous['pid']):
                event('duplicate_launch_prevented', existing_pid=previous['pid'])
                return {'status': 'already_running', 'pid': previous['pid']}
            if stage == 'B' and not (ROOT / 'analysis/A.json').exists():
                raise RuntimeError('stage_A_analysis_required_before_B')
            out = folder(stage)
            out.mkdir(parents=True, exist_ok=True)
            with (out / 'stdout.log').open('ab') as stdout, (out / 'stderr.log').open('ab') as stderr:
                process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', str(ROOT / 'fixture_runner.py'),
                                            'run', '--stage', stage, '--workers', '1'],
                                           cwd=ROOT, stdout=stdout, stderr=stderr,
                                           creationflags=subprocess.CREATE_NO_WINDOW)
            save(ROOT / 'active_worker.json', {'pid': process.pid, 'stage': stage, 'time': now()})
            event('worker_launched', stage=stage, worker_pid=process.pid)
            return {'status': 'launched', 'pid': process.pid}
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def local_request(task):
    response = ROOT / 'responses' / (task['id'] + '.json')
    if response.exists():
        event('response_reused', cell=task['id'])
        return read(response)
    ledger = ROOT / 'mock_receipts.jsonl'
    receipts = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    if task['id'] in {r['cell'] for r in receipts}:
        raise RuntimeError('duplicate_mock_charge_rejected')
    if len(receipts) >= 5:
        raise RuntimeError('fixed_mock_budget_exceeded')
    payload = {'id': task['id'], 'value': task['a'] + task['b']}
    with ledger.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': now(), 'cell': task['id'], 'mock_units': 1, 'actual_currency': 0}) + '\n')
    save(response, payload)
    event('mock_request_completed', cell=task['id'])
    time.sleep(0.7)
    return payload


def run(stage):
    # 模拟实验没有联网能力；真实Codex CLI在另一个进程使用其正常登录。
    def forbidden_network(*args, **kwargs):
        event('forbidden_network_attempt')
        raise RuntimeError('network_disabled_in_selftest_worker')
    socket.socket = forbidden_network
    tasks = read(ROOT / 'protocol.json')['stages'][stage]
    out = folder(stage)
    with (ROOT / 'worker.lock').open('a+b') as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        try:
            spec = importlib.util.spec_from_file_location('fixture_normalizer', ROOT / 'normalizer.py')
            normalizer = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(normalizer)
            completed = 0
            for task in tasks:
                row_path = out / 'task_rows' / (task['id'] + '.json')
                if row_path.exists():
                    completed += 1
                    event('completed_cell_reused', cell=task['id'])
                    continue
                save(out / 'summary.json', {'status': 'running', 'planned': len(tasks), 'completed': completed})
                payload = local_request(task)
                value = normalizer.normalize(payload)
                if value != task['a'] + task['b']:
                    raise RuntimeError('fixture_value_mismatch')
                save(row_path, {'task_id': task['id'], 'cell_id': task['id'], 'value': value,
                                'final': {'functional': True, 'security': True, 'joint': True, 'measured': True}})
                completed += 1
                event('cell_saved', stage=stage, cell=task['id'])
            save(out / 'summary.json', {'status': 'completed', 'planned': len(tasks), 'completed': completed})
            event('stage_completed', stage=stage)
        except Exception as exc:
            completed = len(list((out / 'task_rows').glob('*.json')))
            save(out / 'summary.json', {'status': 'failed', 'planned': len(tasks), 'completed': completed,
                                      'error_type': type(exc).__name__, 'error': str(exc)})
            event('worker_failed', stage=stage, error_type=type(exc).__name__)
            raise
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def analyze(stage):
    tasks = read(ROOT / 'protocol.json')['stages'][stage]
    rows = [read(folder(stage) / 'task_rows' / (task['id'] + '.json')) for task in tasks]
    if any(row is None for row in rows):
        raise RuntimeError('analysis_requires_complete_stage')
    if any(row['value'] != task['a'] + task['b'] for task, row in zip(tasks, rows)):
        raise RuntimeError('analysis_detected_wrong_value')
    report = {'time': now(), 'stage': stage, 'completed': len(rows), 'unique_cells': len({r['cell_id'] for r in rows}),
              'sum_of_results': sum(r['value'] for r in rows), 'kind': 'synthetic_control_analysis'}
    save(ROOT / 'analysis' / (stage + '.json'), report)
    event('analysis_completed', stage=stage)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['launch', 'run', 'analyze', 'inspect'])
    parser.add_argument('--stage', choices=['A', 'B'], default='A')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args()
    if args.action == 'launch':
        print(json.dumps(launch(args.stage)))
    elif args.action == 'run':
        run(args.stage)
    elif args.action == 'analyze':
        print(json.dumps(analyze(args.stage)))
    else:
        print(json.dumps({stage: read(folder(stage) / 'summary.json', {}) for stage in ('A', 'B')}))


if __name__ == '__main__':
    main()

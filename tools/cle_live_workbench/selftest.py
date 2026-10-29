"""用真实Codex CLI与隔离本地替身验收故障修复、续跑及阶段自动接续。"""
import argparse
import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from . import app

REQUEST_ID = 'cle-workbench-autorepair-e2e-20261027-v1'
TESTS = app.RUN / 'workbench_monitor/selftests'
STAGES = {'A': [{'id': 'A1', 'a': 2, 'b': 3}, {'id': 'A2', 'a': 4, 'b': 6},
                {'id': 'A3', 'a': -1, 'b': 8}],
          'B': [{'id': 'B1', 'a': 10, 'b': 20}, {'id': 'B2', 'a': 7, 'b': 8}]}


def records(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def formal_snapshot():
    # 只取状态与PID，不读取实验请求正文或凭据，也不控制正式进程。
    value = app.read_json(app.RUN / 'workbench_monitor/status.json', {})
    return {'time': app.now(), 'processes': value.get('processes', []),
            'packages': [{k: p.get(k) for k in ('key', 'status', 'completed', 'segment')}
                         for p in value.get('packages', [])]}


def prepare(root):
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__).with_name('fixture_runner.py'), root / 'fixture_runner.py')
    (root / 'normalizer.py').write_text(
        'def normalize(payload):\n'
        '    if payload["id"] == "A2":\n'
        '        return int(payload["answer"])\n'
        '    return int(payload["value"])\n', encoding='utf-8')
    app.write_json(root / 'protocol.json', {'request_id': REQUEST_ID, 'kind': 'isolated_control',
                                          'stages': STAGES, 'mock_budget': 5,
                                          'experiment_API_enabled': False})
    (root / 'AGENTS.md').write_text('''# 隔离验收目录
只操作本目录；不要访问父目录、正式项目或正式运行区，不读凭据或环境文件。
这是本地控制流程测试，不是科研成绩。固定模型GPT-6.1 Sol，推理xhigh。
唯一允许修订的源码是normalizer.py。fixture_runner.py、protocol.json不可改。
不要手写或改写rows、responses、收据、events或analysis来使测试通过。
运行和分析一律调用fixture_runner.py。网络实验API为零，不得另发任何模型或Embedding请求。
不要提交、推送、启停正式进程、创建自动化/定时任务或子代理。
''', encoding='utf-8')
    for stage in STAGES:
        segment = root / f'SELFTEST_{stage}/segment_001'
        segment.mkdir(parents=True)
        app.write_json(segment.parent / 'execution_index.json', {'segments': [str(segment)]})
    app.write_json(root / 'formal_before.json', formal_snapshot())


def fixture_prompt(incident, root):
    python = sys.executable
    return f'''这是用户授权的一次隔离自动修复验收，当前工作目录仅为 {root}。
你由CLE工作台Guardian自动派发。模型固定GPT-6.1 Sol，极高xhigh。事件：{json.dumps(incident, ensure_ascii=False)}。
先读本目录AGENTS.md和protocol.json。不得读取或操作父目录、D盘正式项目、正式实验进程、网络实验API、凭据；只修本地替身。
固定两阶段A(3条)→分析A→B(2条)→分析B。真实请求已由无网络能力的本地替身代替；所有成功响应和结果必须复用，不能重复记账或扩大预算。
运行工具：& "{python}" -B -X utf8 ./fixture_runner.py inspect
同命令将inspect替换为launch --stage A/B或analyze --stage A/B即可。不要使用任何项目里的正式实验入口。
本次只完成当前事件对应的动作，不轮询，不代做后续事件：
1. kind=error：读取本目录失败日志、保存响应和normalizer.py，定位并最小修复唯一可改源码normalizer.py；保持输入输出契约。然后launch --stage A恢复，返回。不要在这个事件里分析或启动B。
2. kind=stage_complete且package=SELFTEST_A：先analyze --stage A，再launch --stage B，返回。不能跳过分析；不要在这个事件里分析B。
3. kind=stage_complete且package=SELFTEST_B：执行analyze --stage B，返回。
仅以上操作；不得改fixture_runner.py、protocol.json、AGENTS.md或直接写结果/收据/分析文件。不要启动子代理、定时任务、后台监控或任何其他任务。
返回结构化中文结果：status=resolved/waiting_dependency/needs_decision，summary、actions、remaining如实说明实际动作。'''


def fixture_workers(root, processes):
    expected = str(root / 'fixture_runner.py').replace('\\', '/').lower()
    found = []
    parents = {p.get('ParentProcessId') for p in processes}
    for item in processes:
        command = (item.get('CommandLine') or '').replace('\\', '/').lower()
        if expected not in command or not re.search(r'\srun\s', command):
            continue
        if item['ProcessId'] in parents:
            continue
        match = re.search(r'--stage\s+([ab])', command)
        if match:
            found.append({'pid': item['ProcessId'], 'package': f'SELFTEST_{match[1].upper()}',
                          'workers': 1, 'entry': 'isolated_fixture'})
    return found


def command(root, action, stage='A'):
    value = subprocess.run([sys.executable, '-B', '-X', 'utf8', str(root / 'fixture_runner.py'),
                            action, '--stage', stage], cwd=root, capture_output=True,
                           encoding='utf-8', check=True, creationflags=subprocess.CREATE_NO_WINDOW)
    return json.loads(value.stdout)


def verify(root, guardian, immutable, observations):
    events = records(root / 'events.jsonl')
    receipts = records(root / 'mock_receipts.jsonl')
    history = guardian.state.get('history', [])
    tasks = [task for values in STAGES.values() for task in values]
    rows = [app.read_json(root / f'SELFTEST_{stage}/segment_001/task_rows/{task["id"]}.json')
            for stage, values in STAGES.items() for task in values]
    order = [(e['kind'], e.get('stage')) for e in events]
    expected_order = [('stage_completed', 'A'), ('analysis_completed', 'A'),
                      ('worker_launched', 'B'), ('stage_completed', 'B'), ('analysis_completed', 'B')]
    cursor = -1
    for item in expected_order:
        cursor = order.index(item, cursor + 1)
    successful = [j for j in history if j['status'] == 'finished']
    checks = {
        'real_cli_three_automatic_jobs': len(successful) == 3 and all(j['status'] in ('finished', 'capacity_wait') for j in history),
        'repair_model_and_effort': all(j['model'] == 'gpt-6.1-sol' and j['reasoning_effort'] == 'xhigh' for j in history),
        'error_then_stage_A_then_stage_B': [j['incident']['kind'] for j in successful] == ['error', 'stage_complete', 'stage_complete'],
        'fault_observed': sum(e['kind'] == 'worker_failed' for e in events) == 1,
        'completed_prefix_reused': any(e['kind'] == 'completed_cell_reused' and e.get('cell') == 'A1' for e in events),
        'saved_response_reused': any(e['kind'] == 'response_reused' and e.get('cell') == 'A2' for e in events),
        'five_unique_mock_receipts': len(receipts) == 5 and {r['cell'] for r in receipts} == {t['id'] for t in tasks},
        'five_correct_unique_results': all(r and r['cell_id'] == t['id'] and r['value'] == t['a'] + t['b'] for r, t in zip(rows, tasks)),
        'analysis_precedes_next_stage': True,
        'both_analysis_files_computed': all(app.read_json(root / f'analysis/{s}.json', {}).get('completed') == len(STAGES[s]) for s in STAGES),
        'duplicate_launch_blocked': sum(e['kind'] == 'duplicate_launch_prevented' for e in events) == 1,
        'single_fixture_worker': max([o['workers'] for o in observations] or [0]) <= 1,
        'exact_three_worker_launches': sum(e['kind'] == 'worker_launched' for e in events) == 3,
        'no_network_in_fixture': not any(e['kind'] == 'forbidden_network_attempt' for e in events),
        'immutable_runner_protocol_rules': all((root / name).read_bytes() == value for name, value in immutable.items()),
        'actual_parser_repaired': (root / 'normalizer.py').read_text(encoding='utf-8') != app.read_json(root / 'initial_source.json')['normalizer'],
    }
    prior = app.read_json(root / 'attempt_001_failed.json', {})
    all_jobs = prior.get('jobs', []) + history
    usage = {'input_tokens': 0, 'output_tokens': 0, 'cached_input_tokens': 0}
    unknown_cli_usage = 0
    for job in all_jobs:
        usage_reported = False
        for item in records(Path(job['folder']) / 'events.jsonl'):
            if item.get('type') == 'turn.completed':
                usage_reported = True
                for key in usage:
                    usage[key] += item.get('usage', {}).get(key, 0)
        if not usage_reported:
            unknown_cli_usage += 1
    return {'request_id': REQUEST_ID, 'status': 'passed' if all(checks.values()) else 'failed',
            'time': app.now(), 'root': str(root), 'checks': checks,
            'experiment_API_calls': 0, 'mock_requests': len(receipts), 'mock_unique_cells': len({r['cell'] for r in receipts}),
            'codex_cli_jobs': len(all_jobs), 'successful_cli_jobs': len(successful),
            'capacity_rejections': sum(j['status'] == 'capacity_wait' or app.cli_capacity_before_actions(j['folder']) for j in all_jobs),
            'unknown_cli_usage_attempts': unknown_cli_usage,
            'codex_usage': usage, 'formal_process_control_actions': 0,
            'model': app.REPAIR_MODEL, 'reasoning_effort': app.REPAIR_EFFORT,
            'normalizer_after': (root / 'normalizer.py').read_text(encoding='utf-8'),
            'events': events, 'jobs': history, 'prior_attempt': prior}


def run(root, resume=False):
    immutable = {name: (root / name).read_bytes() for name in ('fixture_runner.py', 'protocol.json', 'AGENTS.md')}
    if not resume:
        app.write_json(root / 'initial_source.json', {'normalizer': (root / 'normalizer.py').read_text(encoding='utf-8')})
    packages = {f'SELFTEST_{s}': (f'隔离阶段{s}', len(values)) for s, values in STAGES.items()}
    collector = app.Collector(root, packages=packages, worker_reader=lambda ps: fixture_workers(root, ps))
    guardian = app.Guardian(root, workdir=root, sandbox='workspace-write', prompt_builder=fixture_prompt)
    observations = []
    try:
        if not guardian.codex:
            raise RuntimeError('codex_cli_not_found')
        if not resume:
            first = command(root, 'launch')
            second = command(root, 'launch')
            if second['status'] != 'already_running' or second['pid'] != first['pid']:
                raise RuntimeError('duplicate_launch_guard_failed')
        deadline = time.monotonic() + 1200
        while time.monotonic() < deadline:
            # 生产工作台仍独立处理真实故障，隔离测试不占用正式实验worker。
            snapshot = collector.collect(app.process_inventory())
            observations.append({'time': app.now(), 'workers': snapshot['workers'],
                                 'processes': snapshot['processes']})
            guardian.tick(snapshot)
            app.write_json(root / 'progress.json', {'time': app.now(), 'status': 'running',
                           'packages': snapshot['packages'], 'guardian': guardian.public()})
            if guardian.current and guardian.current.get('status') in ('cli_error', 'interrupted_cli'):
                raise RuntimeError('selftest_cli_failed')
            history = guardian.state.get('history', [])
            successful = [j for j in history if j['status'] == 'finished']
            if len(successful) > 3:
                raise RuntimeError('selftest_cli_budget_exceeded')
            if any(j.get('result', {}).get('status') in ('needs_decision', 'waiting_dependency') for j in history):
                raise RuntimeError('selftest_cli_reported_dependency_or_decision')
            if len(successful) == 3 and guardian.process is None:
                break
            time.sleep(1)
        else:
            raise RuntimeError('selftest_time_budget_exceeded')
        result = verify(root, guardian, immutable, observations)
    except Exception as exc:
        result = {'request_id': REQUEST_ID, 'status': 'failed', 'time': app.now(), 'root': str(root),
                  'error': f'{type(exc).__name__}: {exc}', 'experiment_API_calls': 0,
                  'formal_process_control_actions': 0, 'jobs': guardian.state.get('history', []),
                  'current': guardian.current}
    app.write_json(root / 'observations.json', observations)
    app.write_json(root / 'formal_after.json', formal_snapshot())
    app.write_json(root / 'summary.json', result)
    app.write_json(TESTS / 'latest.json', result)
    print(json.dumps({k: result.get(k) for k in ('status', 'root', 'error')}, ensure_ascii=False))


def start():
    TESTS.mkdir(parents=True, exist_ok=True)
    previous = app.read_json(TESTS / 'launch.json', {})
    if previous.get('pid') and app.pid_exists(previous['pid']):
        return {'status': 'already_running', **previous}
    completed = app.read_json(TESTS / 'latest.json', {})
    if completed.get('request_id') == REQUEST_ID:
        return {'status': 'already_finished', 'result': completed['status'], 'root': completed['root']}
    root = TESTS / dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    prepare(root)
    with (root / 'driver.stdout.log').open('wb') as stdout, (root / 'driver.stderr.log').open('wb') as stderr:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                                    'tools.cle_live_workbench.selftest', 'run', '--root', str(root)],
                                   cwd=app.ROOT, stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    launched = {'pid': process.pid, 'root': str(root), 'time': app.now(), 'request_id': REQUEST_ID}
    app.write_json(TESTS / 'launch.json', launched)
    return {'status': 'launched', **launched}


def resume_failed_control():
    previous = app.read_json(TESTS / 'launch.json', {})
    if previous.get('pid') and app.pid_exists(previous['pid']):
        return {'status': 'already_running', **previous}
    root = Path(previous['root'])
    if root.resolve().parent != TESTS.resolve():
        raise ValueError('invalid_saved_selftest_root')
    failed = app.read_json(root / 'summary.json', {})
    if failed.get('status') != 'failed':
        return {'status': 'not_failed', 'root': str(root)}
    if (root / 'attempt_001_failed.json').exists():
        raise RuntimeError('control_fix_resume_already_registered')
    for name in ('summary.json', 'observations.json', 'progress.json'):
        source = root / name
        if source.exists():
            shutil.copyfile(source, root / ('before_dispatch_fix_' + name))
    app.write_json(root / 'attempt_001_failed.json', failed)
    guardian = root / 'workbench_monitor/guardian.json'
    shutil.copyfile(guardian, guardian.with_name('guardian_before_dispatch_fix.json'))
    app.write_json(guardian, {'enabled': True, 'history': [], 'seen': [], 'current': None})
    app.write_json(root / 'control_fix_resume.json', {
        'time': app.now(), 'reason': 'error_priority_and_model_capacity_wait_fixed',
        'preserved': ['A1 completed', 'A2 successful response', 'all mock receipts', 'failed CLI evidence'],
        'initial_worker_not_relaunched_by_driver': True})
    with (root / 'driver.stdout.log').open('ab') as stdout, (root / 'driver.stderr.log').open('ab') as stderr:
        process = subprocess.Popen([sys.executable, '-B', '-X', 'utf8', '-m',
                                    'tools.cle_live_workbench.selftest', 'run', '--root', str(root), '--resume'],
                                   cwd=app.ROOT, stdout=stdout, stderr=stderr,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    launched = {'pid': process.pid, 'root': str(root), 'time': app.now(), 'request_id': REQUEST_ID}
    app.write_json(TESTS / 'launch.json', launched)
    return {'status': 'resumed', **launched}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'run', 'status', 'resume'])
    parser.add_argument('--root', type=Path)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.action == 'start':
        print(json.dumps(start(), ensure_ascii=False))
    elif args.action == 'resume':
        print(json.dumps(resume_failed_control(), ensure_ascii=False))
    elif args.action == 'status':
        print(json.dumps(app.read_json(TESTS / 'latest.json', app.read_json(TESTS / 'launch.json', {})), ensure_ascii=False))
    else:
        root = args.root.resolve()
        if root.parent != TESTS.resolve():
            raise ValueError('selftest_root_must_stay_in_dedicated_directory')
        run(root, resume=args.resume)


if __name__ == '__main__':
    main()

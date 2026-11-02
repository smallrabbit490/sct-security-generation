"""独立读取原生实验结果；进程确实退出后交给 Codex CLI 修复，不改实验协议。"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[2]
RUN = Path('E:/ResearchRuns/CLE/20261027_full_requirements')
PYTHON = ROOT / 'translation_work/temp/cle_memory_q_env/Scripts/python.exe'
STATIC = Path(__file__).with_name('static')
SHANGHAI = dt.timezone(dt.timedelta(hours=8))
REPAIR_MODEL = 'gpt-6.1-sol'
REPAIR_EFFORT = 'xhigh'
SAMPLE_SECONDS = 5
PACKAGES = {'FQ_LEARN': ('Q 学习', 1122), 'FQ_RETEST': ('冻结 Q 同题回测', 2730),
            'FQ_GATE': ('D_gate 四臂 Q 对照', 2384), 'FFS': ('功能与安全经验拆分', 2980),
            'FG_LABELS': ('五档记忆标签', 2730), 'FG_GATE': ('记忆程度分类器', 1788),
            'FR': ('检索标注', None), 'BUILD_C41': ('新模型建库', None),
            'FX_GATE': ('模型与卡库交叉', 3576), 'FX_EXTERNAL': ('Base/Plus v4.1交叉', 1530),
            'P3_EXTERNAL': ('原P3 Base/Plus', 255)}
PACKAGES.update({'FG_LABELS_EXTRA': ('记忆标签追加82题（有条件）', 820),
                 'FR_EXTRA': ('检索追加57题（有条件）', 57)})


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        # 活动进程可能正在写同一个摘要；下一次采样再读取，不写回原文件。
        return default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def now():
    return dt.datetime.now(SHANGHAI).isoformat(timespec='seconds')


def allowed(at=None):
    at = at or dt.datetime.now(SHANGHAI)
    from .time_policy import override_active
    if override_active(at):
        return True
    return at.weekday() >= 5 or not (9 <= at.hour < 12 or 14 <= at.hour < 18)


def discover_codex():
    """从 PATH 安装位置寻找实际 exe，避免 .ps1/.cmd 的命令拼接。"""
    found = shutil.which('codex.exe') or shutil.which('codex') or shutil.which('codex.cmd')
    if found and Path(found).suffix.lower() == '.exe':
        return found
    npm = Path(os.environ.get('APPDATA', '')) / 'npm/node_modules/@openai/codex'
    candidates = list(npm.glob('node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe'))
    if not candidates:
        candidates = list(npm.glob('vendor/*/codex/codex.exe'))
    return str(candidates[0]) if candidates else None


def process_inventory():
    command = ('[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); '
               'Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | '
               'Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress')
    result = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                            capture_output=True, encoding='utf-8', check=True,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.stdout is None:
        # 已观测到子线程解码失败时stdout为None；不能当作没有实验进程。
        raise ValueError('CIM_inventory_stdout_missing')
    values = json.loads(result.stdout) if result.stdout.strip() else []
    return [values] if isinstance(values, dict) else values


def process_package(command):
    text = command or ''
    # launch只负责前缀核对与派生进程；把它算作worker会让其误判自己已运行。
    if not re.search(r'\s(run|resume)(?:\s|$)', text):
        return None
    if any(marker in text for marker in ('configs.cle_weekly_closeout_20261101.resume',
                                         'configs.cle_weekly_closeout_20261101.recover_tls', 'configs.cle_weekly_closeout_20261101.switch_flash')):
        kind = re.search(r'--kind\s+(q|gr)(?:\s|$)', text)
        return {'q': 'FQ_RETEST', 'gr': 'FG_LABELS'}.get(kind[1]) if kind else None
    for marker, package in [('granularity_extra', 'FG_LABELS_EXTRA'),
                            ('granularity_gate', 'FG_GATE'), ('retrieval_extra_execute', 'FR_EXTRA'),
                            ('retrieval_execute', 'FR'), ('granularity', 'FG_LABELS'),
                            ('qgate', 'FQ_GATE'), ('retest', 'FQ_RETEST')]:
        if 'configs.cle_weekly_reduced_20261028.' + marker in text:
            return package
    if any(marker in text for marker in (
            'cle_weekly_proxy_recovery_20261027.runner',
            'cle_weekly_http403_recovery_20261028.resume',
            'cle_weekly_http403_probe_refresh_20261028.resume',
            'cle_weekly_q_tls12_20261028.resume')):
        return 'FQ_LEARN' if '--kind q' in text else 'FFS'
    if any(s in text for s in ('cle_weekly_embedding_recovery_', 'embedding_resume', 'recover_utf8')):
        return 'FFS'
    if any(s in text for s in ('transport_resume', 'recovery_1020', 'cle_weekly_recovery_')):
        return 'FQ_LEARN' if 'FQ_LEARN' in text or 'recovery_' in text else 'FFS'
    for marker, package in [('full_20261027.learn', 'FQ_LEARN'), ('eval_20261027.retest', 'FQ_RETEST'),
                            ('cle_weekly_gate_20261027.evaluate', 'FQ_GATE'), ('fs_20261027.evaluate', 'FFS'),
                            ('granularity_20261027.evaluate', 'FG_LABELS'),
                            ('granularity_gate_20261027.evaluate', 'FG_GATE'),
                            ('retrieval_20261027.execute', 'FR'), ('build_20261027.', 'BUILD_C41'),
                            ('cross_20261027.', 'FX_GATE')]:
        if marker in text:
            return package
    return None


def worker_processes(processes):
    """venv 启动器与其子 Python 是同一个 worker，不重复计数。"""
    result = []
    matched = [p for p in processes if process_package(p.get('CommandLine'))]
    parent_ids = {p.get('ParentProcessId') for p in matched}
    for p in matched:
        if p['ProcessId'] in parent_ids:
            continue
        package = process_package(p.get('CommandLine'))
        command = p.get('CommandLine') or ''
        match = re.search(r'--workers\s+(\d+)', command)
        workers = int(match[1]) if match else (1 if package in ('FQ_LEARN','FR','FR_EXTRA') else 3 if package == 'FFS' else 4)
        result.append({'pid': p['ProcessId'], 'package': package, 'workers': workers,
                       'entry': command.split(' -m ')[-1] if ' -m ' in command else Path(command).name})
    return result


def segments_for(run, package):
    if package == 'FQ_LEARN':
        index = read_json(run / 'execution_index.json', {})
        return [Path(p) for key in ('FQ_LEARN_K0', 'FQ_LEARN_K1', 'FQ_LEARN_K2', 'FQ_LEARN_K3')
                for p in index.get(key, [])]
    folder = run / package
    if package == 'FQ_RETEST' and (run / 'probe_relay_20261028/Q.retest/execution_index.json').exists():
        folder = run / 'probe_relay_20261028/Q.retest'
    index = read_json(folder / 'execution_index.json', {})
    return [Path(p) for p in index.get('segments', [])]


def latest_activity(segment):
    """只读请求状态与时间，不把完整提示词、HTTP 头或鉴权信息送入页面。"""
    if not segment:
        return None
    wire = segment / 'wire'
    if not wire.exists():
        return None
    candidates = []
    for path in wire.iterdir():
        if path.name.endswith('.tmp'):
            continue
        try:
            candidates.append((path.stat().st_mtime, path))
        except FileNotFoundError:
            # 原生写入器刚完成原子替换；下一轮采样读取正式文件。
            continue
    if not candidates:
        return None
    stamp, recent = max(candidates, key=lambda item: item[0])
    status = '接收响应中' if recent.name.endswith('.raw') else '请求已准备'
    safe = {}
    if recent.name.endswith('.status.json'):
        value = read_json(recent, {})
        safe = {k: value[k] for k in ('status', 'http_status', 'error_type', 'reason_type', 'elapsed_seconds') if k in value}
        status = '请求传输中断' if value.get('status') == 'transport_error' else '响应状态已保存'
    return {'file': recent.name, 'time': dt.datetime.fromtimestamp(stamp, SHANGHAI).isoformat(),
            'age_seconds': round(time.time() - stamp), 'state': status, **safe}


def summarize_rows(rows):
    """按唯一 cell 展示实际选卡、采用与反馈，不把卡数当作题数。"""
    items, curve, credited = [], [], set()
    for row in rows:
        selected, adopted = set(), set()
        for entry in row.get('mechanism', []):
            selected.update(str(v) for v in entry.get('selected', []))
            adopted.update(str(v) for v in entry.get('adopted', []))
        events = row.get('q_credit_events', [])
        for entry in events:
            if entry.get('credited'):
                credited.add(str(entry.get('invariant_id')))
        final = row.get('final') or {}
        items.append({'cell_id': row.get('cell_id', row.get('task_id')), 'task_id': row.get('task_id'),
                      'package': row['_package'], 'stage': row.get('learning_checkpoint'),
                      'arm': row.get('arm'), 'family': row.get('family_id'), 'cwe': row.get('cwe'),
                      'functional': final.get('functional'), 'security': final.get('security'),
                      'joint': final.get('joint'), 'measured': final.get('measured'),
                      'model_cohort': row.get('model_cohort'), 'execution_model': row.get('execution_model'),
                      'selected': sorted(selected), 'adopted': sorted(adopted),
                      'credits': sum(e.get('credited') is True for e in events),
                      'time': row['_time']})
        if row['_package'] == 'FQ_LEARN':
            curve.append({'x': len(curve) + 1, 'coverage': len(credited),
                          'joint': sum(v.get('joint') is True for v in items if v['package'] == 'FQ_LEARN')})
    return items, curve


class Collector:
    def __init__(self, run, *, packages=None, worker_reader=worker_processes):
        self.run, self.cache = Path(run), {}
        self.rows = {}
        self.row_paths = {}
        self.packages = PACKAGES if packages is None else packages
        self.worker_reader = worker_reader

    def collect(self, processes):
        workers = self.worker_reader(processes)
        registered = read_json(self.run / 'workbench_monitor/autonomy/registered_workers.json', [])
        known = {p['pid'] for p in workers}
        for entry in registered:
            matches = [p for p in processes if p.get('ProcessId') == entry['pid'] or p.get('ParentProcessId') == entry['pid']]
            matches = [p for p in matches if entry.get('command_marker') and
                       entry['command_marker'] in (p.get('CommandLine') or '')]
            if matches:
                if type(entry.get('workers')) is not int or not 0 <= entry['workers'] <= 4:
                    raise ValueError('registered_worker_count_outside_authorized_limit')
                # 离线回放也登记实际PID，但不占用实验API并发槽。
                if entry['workers'] == 0:
                    continue
                parents = {p.get('ParentProcessId') for p in matches}
                leaf = next((p for p in matches if p['ProcessId'] not in parents), matches[-1])
                if leaf['ProcessId'] not in known:
                    workers.append({'pid': leaf['ProcessId'], 'package': entry['package'],
                                    'workers': entry['workers'], 'entry': entry['command_marker']})
                    known.add(leaf['ProcessId'])
        packages = []
        for key, (label, planned) in self.packages.items():
            reduced = read_json(self.run/'scope_reduction_20261028/prepared.json', {})
            if reduced.get('status') == 'prepared':
                planned = {'FQ_RETEST': 1416, 'FG_LABELS': 820, 'FR': 57}.get(key, planned)
            segments = segments_for(self.run, key)
            latest = segments[-1] if segments else None
            summaries = [read_json(segment / 'summary.json', {}) for segment in segments]
            summary = summaries[-1] if summaries else {}
            native_state = read_json(latest / 'state.json', {}) if latest else {}
            display_summary = max(summaries, key=lambda s: s.get('completed', 0), default={})
            usage_summary = max(summaries, key=lambda s: s.get('known_reported_tokens', 0), default={})
            completed = summary.get('completed', 0)
            if key in ('FR','FR_EXTRA'):
                completed = len(list((self.run/key/'records').glob('*.json')))
            if key == 'FQ_LEARN':
                stages = {}
                for s in summaries:
                    if s.get('stage'):
                        prior = stages.get(s['stage'], {})
                        if s.get('completed', 0) >= prior.get('completed', 0):
                            stages[s['stage']] = s
                completed = sum(s.get('completed', 0) for s in stages.values())
                display_summary = stages[next(reversed(stages))] if stages else summary
            else:
                stages = {}
            for segment in segments:
                folder = segment / 'task_rows'
                if not folder.exists():
                    continue
                for path in folder.glob('*.json'):
                    stamp = path.stat().st_mtime_ns
                    if self.cache.get(path) == stamp:
                        continue
                    row = read_json(path)
                    if row is None:
                        continue
                    self.cache[path] = stamp
                    identity = (key, str(row.get('cell_id') or row.get('task_id')))
                    # 历史行含完整提示/候选/代码，全部常驻曾造成MemoryError。
                    # 列表仅保留显示字段，点击详情时再读取对应的一行原始证据。
                    compact = {k: row.get(k) for k in ('cell_id', 'task_id', 'learning_checkpoint',
                        'arm', 'family_id', 'cwe', 'model_cohort', 'execution_model')}
                    compact['final'] = {k: (row.get('final') or {}).get(k)
                        for k in ('functional', 'security', 'joint', 'measured')}
                    compact['mechanism'] = [{k: m.get(k, []) for k in ('selected', 'adopted')}
                                            for m in row.get('mechanism', [])]
                    compact['q_credit_events'] = [{k: e.get(k) for k in ('credited', 'invariant_id')}
                                                  for e in row.get('q_credit_events', [])]
                    compact['_package'] = key
                    compact['_time'] = self.rows.get(identity, {}).get('_time', path.stat().st_mtime)
                    self.rows[identity] = compact
                    self.row_paths[identity] = path
            live = [p for p in workers if p['package'] == key]
            native_status = native_state.get('status') or summary.get('status')
            if live:
                status = 'running' if allowed() else 'waiting_window'
            elif planned and completed == planned and (key not in ('FR','FR_EXTRA') or summary.get('status') == 'awaiting_human_confirmation'):
                status = 'completed'
            elif latest and not summary and not (latest / 'state.json').exists():
                status = 'not_started'
            elif latest and native_status in ('running', 'starting', 'waiting_time_window'):
                status = 'interrupted'
            elif latest:
                status = native_status or 'needs_check'
            else:
                status = 'not_started'
            packages.append({'key': key, 'label': label, 'planned': planned, 'completed': completed,
                             'status': status, 'summary': summary, 'stages': stages,
                             'display_summary': display_summary, 'usage_summary': usage_summary,
                             'display_completed': max(completed, sum(1 for identity in self.rows if identity[0] == key)),
                             'segment': str(latest) if latest else None, 'processes': live,
                             'native_state': native_state,
                             'last_saved_at': display_summary.get('updated_utc'),
                             'activity': latest_activity(latest)})
        from .current_view import extra_rows
        for row in extra_rows(self.run, read_json):
            identity = (row['_package'], str(row.get('cell_id') or row.get('task_id')))
            self.rows[identity] = row
        ordered = sorted(self.rows.values(), key=lambda r: r['_time'])
        rows, curve = summarize_rows(ordered)
        return {'time': now(), 'model': 'deepseek-v4.1-flash-1017', 'allowed': allowed(),
                'sample_interval_seconds': SAMPLE_SECONDS,
                'run_root': str(self.run), 'packages': packages, 'processes': workers,
                'workers': sum(p['workers'] for p in workers), 'worker_limit': 4,
                'rows': list(reversed(rows)), 'curve': curve}


def task_display(snapshot, autonomy):
    """仅补充展示口径，原生状态仍用于恢复、分母核验及调度。"""
    tasks = autonomy.get('tasks', [])
    for package in snapshot['packages']:
        probes = [t for t in tasks if t['package'] == package['key'] and t['kind'] == 'probe']
        runs = [t for t in tasks if t['package'] == package['key'] and t['kind'] == 'run']
        active_runs = [t for t in runs if t.get('execution') != 'not_required_by_protocol']
        if runs and not active_runs:
            package['display_status'] = runs[0]['display_status']
            package['display_planned'] = 0
            package['display_note'] = '保留原计划；本轮不执行，不生成成绩。'
        elif active_runs:
            counts = [t['expected'] for t in active_runs if isinstance(t.get('expected'), int)]
            if len(counts) == len(active_runs):
                package['display_planned'] = sum(counts)
            package['display_status'] = active_runs[0].get('display_status', active_runs[0]['status'])
        if probes:
            probe = probes[0]
            full_planned = package.get('display_planned', package.get('planned'))
            package['display_planned'] = probe['expected']
            package['display_completed'] = probe['expected'] if probe['status'] == 'completed' else min(package['completed'], probe['expected'])
            package['display_status'] = probe['status']
            package['display_note'] = f"当前：{probe['title']}；原全量{full_planned or '按协议'}先跳过，不自动启动。"
        elif any(t.get('execution_scope') == 'probe_batch' for t in runs):
            package['display_note'] = '小批探索：自动执行及分析；不自动转入排队全量。'
        elif any(t['status'] == 'deferred_full' for t in runs):
            package['display_note'] = '全量保留待做；当前自动队列跳过。'
    # 各轮summary是该轮的累计物理用量；不能只取最后一轮，也不能再加其副本。
    sources = []
    for package in snapshot['packages']:
        if package['key'] == 'FQ_LEARN' and package.get('stages'):
            sources.extend(package['stages'].values())
        elif package.get('summary'):
            sources.append(package.get('usage_summary', package['summary']))
    reported = [s for s in sources if s.get('known_reported_tokens') is not None
                and s.get('physical_HTTP') is not None]
    snapshot['usage'] = {
        'known_reported_tokens': sum(s['known_reported_tokens'] for s in reported),
        'physical_HTTP': sum(s['physical_HTTP'] for s in reported),
        'unknown_or_inflight_HTTP': sum(s.get('unknown_or_inflight_HTTP', 0) for s in reported),
    }
    return snapshot


def incident_list(snapshot):
    incidents = []
    for p in snapshot['packages']:
        if p['status'] not in ('not_started', 'completed', 'running', 'waiting_window'):
            incidents.append({'id': f"error:{p['key']}:{p['segment']}:{p['completed']}",
                              'kind': 'error', 'package': p['key'], 'segment': p['segment'],
                              'completed': p['completed'], 'status': p['status']})
        for stage, s in p.get('stages', {}).items():
            if s.get('completed') == s.get('planned') and s.get('planned'):
                incidents.append({'id': f'analysis:{stage}', 'kind': 'stage_complete',
                                  'package': p['key'], 'stage': stage})
        if p['status'] == 'completed':
            incidents.append({'id': f"complete:{p['key']}", 'kind': 'stage_complete', 'package': p['key']})
    if (not snapshot['processes'] and snapshot['allowed'] and not incidents and
            any(p['status'] != 'completed' for p in snapshot['packages'])):
        incidents.append({'id': 'dispatch:' + '|'.join(f"{p['key']}={p['completed']}" for p in snapshot['packages']),
                          'kind': 'continue_plan', 'package': 'pipeline'})
    return incidents


def cli_capacity_before_actions(folder):
    """只重试已观测到的模型容量拒绝；CLI一旦执行过操作就先重新核对现场。"""
    events = Path(folder) / 'events.jsonl'
    if not events.exists():
        return False
    capacity = False
    for line in events.read_text(encoding='utf-8').splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get('item', {}).get('type') in ('command_execution', 'mcp_tool_call', 'file_change'):
            return False
        message = event.get('message', '') or event.get('error', {}).get('message', '')
        if 'selected model is at capacity' in message.lower():
            capacity = True
    return capacity


def selftest_status():
    base = RUN / 'workbench_monitor/selftests'
    launch = read_json(base / 'launch.json', {})
    if not launch:
        return {'status': 'not_started'}
    root = Path(launch['root'])
    if root.resolve().parent != base.resolve():
        return {'status': 'invalid_root'}
    result = read_json(root / 'summary.json', {})
    if result.get('time', '') < launch.get('time', ''):
        progress = read_json(root / 'progress.json', {})
        return {'status': 'running', 'time': progress.get('time'), 'root': str(root)}
    return {key: result.get(key) for key in ('status', 'time', 'root', 'checks', 'experiment_API_calls',
            'mock_requests', 'mock_unique_cells', 'successful_cli_jobs', 'codex_cli_jobs',
            'model', 'reasoning_effort', 'error')}


def pid_exists(pid):
    if os.name == 'nt':
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def repair_prompt(incident, run):
    prompt = f'''你是 CLE 工作台独立的 Codex CLI 运行维护代理。用户已授权工作台自动调用你修复错误、恢复预定全量实验并完成每阶段分析，不依赖聊天或定时任务。现在实际处理事件：{json.dumps({k: v for k, v in incident.items() if k != 'work_item'}, ensure_ascii=False)}。
项目 {ROOT}；运行根 {run}。先读根 AGENTS、configs/cle_weekly_full_20261027/execution_plan.json、docs/research/CLE-RUN-20261027-full-requirements-v01.md 以及 tools/cle_live_workbench/README.md。按实际 CIM、index、最新 summary/state、journal/wire 判断，不凭沉默判断中断。先检查是否已有运行/修复进程；venv父子是一实例。Q单worker+冻结评价最多3，总4。不要结束正常的运行。
必须保持：deepseek-v4.1-flash-1017，thinking disabled，temperature0，4096，原单user，P7三卡/一次修复，原验证器，原名单与重复数、逐题Q顺序、候选/冻结规则与累计预算。不按低成绩重跑。工作日上海[09,12)、[14,18)禁止新模型和Embedding请求；可以随时做零API修复/分析。每个真实请求由原入口再次检查。
用户2026-10-27 18:31已授权同类TLS/网络未决请求补发：先核对同模型/提示、无可复用成功响应，零API精确重放完成前缀，再保留旧失败/未知执行用量从新段补发。HTTP200流缺结束也须实际检查raw。认证/额度/预算错误不能当传输错误补发。优先现有 configs.cle_weekly_proxy_recovery_20261027.runner launch --kind q/ffs；FFS向量错误先用 configs.cle_weekly_embedding_recovery_20261027.probe 查明题号与精确前缀，再 resume launch <题号>；识别任意题号的该模块活进程。禁止修改旧journal/state/source_identity来绕过恢复。已返回响应复用，已完成题不重复付费。
可以修复真实解析/落盘/恢复程序错误。不要修改活动source_bundle或其冻结来源；优先在独立新tools/configs目录建修复入口并离线核验，记录实际修订。如必须更改科学协议，不改，明确在结果给出具体所需决定。不要新增无关框架、校验层或重新设计实验。不要读取/输出/复制凭据、.env、auth文件、API密钥或浏览器登录；不要提交推送、发消息/邮件、创建本机/应用定时任务或子代理。
当前计划：Q学习K0 303、K1/K2/K3各273，轮末冻结/回放/分析；FQ_RETEST 2730后FQ_GATE2384。FFS2980可独立，完成回放/实际案例分析后FG_LABELS2730、真实标签训练、FG_GATE1788；FR571题与BUILD_C41空库三轮在容量允许且自身技术就绪时推进。v3.2已不可用，不尝试或用v4.1冒替；Base/Plus缺原镜像不换验证器；人工标签不代签。最新准备/参考预检不算模型实测。阶段完成必须实际读题、卡、计划、代码和验证，更新分析和登记，不把队列当分析。
本次完成事件的修复/分析/后续启动，返回简短确定的中文：status=resolved或waiting_dependency或needs_decision，summary说明实际结果，actions给真实做过的操作，remaining给确切剩余事项。写入可核对的日志/修复证据后结束，让工作台继续监控；不要在本CLI内长期轮询。'''
    if 'work_item' in incident:
        from .autonomy import work_instructions
        prompt += work_instructions(incident, run)
    return prompt


class Guardian:
    def __init__(self, run, enabled=True, *, workdir=ROOT, sandbox='danger-full-access',
                 prompt_builder=repair_prompt):
        self.run = Path(run)
        self.workdir = Path(workdir)
        self.sandbox = sandbox
        self.prompt_builder = prompt_builder
        self.control = self.run / 'workbench_monitor'
        self.control.mkdir(parents=True, exist_ok=True)
        self.state = read_json(self.control / 'guardian.json', {})
        self.enabled = self.state.get('enabled', enabled)
        self.seen = set(self.state.get('seen', []))
        self.first_seen = {}
        self.process = None
        self.current = self.state.get('current')
        self.codex = discover_codex()
        self.manual = False

    def public(self):
        attached = self.current and self.current.get('status') == 'running' and pid_exists(self.current['pid'])
        return {'enabled': self.enabled, 'codex': self.codex, 'current': self.current,
                'model': REPAIR_MODEL, 'reasoning_effort': REPAIR_EFFORT,
                'pid': self.process.pid if self.process and self.process.poll() is None else self.current['pid'] if attached else None,
                'last_check': now(), 'history': self.state.get('history', [])[-10:]}

    def save(self):
        self.state.update(enabled=self.enabled, seen=sorted(self.seen), current=self.current)
        write_json(self.control / 'guardian.json', self.state)

    def launch(self, incident):
        job_id = dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        folder = self.control / 'jobs' / job_id
        folder.mkdir(parents=True)
        prompt = self.prompt_builder(incident, self.run)
        (folder / 'task.txt').write_text(prompt, encoding='utf-8')
        schema = {'type': 'object', 'properties': {
            'status': {'type': 'string', 'enum': ['resolved', 'waiting_dependency', 'needs_decision']},
            'summary': {'type': 'string'}, 'actions': {'type': 'array', 'items': {'type': 'string'}},
            'remaining': {'type': 'array', 'items': {'type': 'string'}}},
            'required': ['status', 'summary', 'actions', 'remaining'], 'additionalProperties': False}
        write_json(folder / 'schema.json', schema)
        args = [self.codex, 'exec', '--ephemeral', '--json', '-C', str(self.workdir),
                '--model', REPAIR_MODEL, '-c', f'model_reasoning_effort="{REPAIR_EFFORT}"',
                '--sandbox', self.sandbox, '-c', 'approval_policy="never"',
                '--output-schema', str(folder / 'schema.json'),
                '--output-last-message', str(folder / 'result.json'), '-']
        if not (self.workdir / '.git').exists():
            args.insert(-1, '--skip-git-repo-check')
        from .time_policy import child_environment
        environment = child_environment(os.environ) if self.workdir == ROOT else dict(os.environ)
        with (folder / 'events.jsonl').open('wb') as stdout, (folder / 'stderr.log').open('wb') as stderr:
            self.process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                                            cwd=self.workdir, env=environment,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            self.process.stdin.write(prompt.encode('utf-8'))
            self.process.stdin.close()
        self.current = {'job_id': job_id, 'incident': incident, 'status': 'running',
                        'model': REPAIR_MODEL, 'reasoning_effort': REPAIR_EFFORT,
                        'pid': self.process.pid, 'started': now(), 'folder': str(folder)}
        self.seen.add(incident['id'])
        self.save()

    def tick(self, snapshot, incidents=None):
        if self.process is not None and self.process.poll() is not None:
            folder = Path(self.current['folder'])
            result = read_json(folder / 'result.json', {})
            self.current.update(status='finished' if self.process.returncode == 0 and result else 'cli_error',
                                exit_code=self.process.returncode, finished=now(), result=result)
            if self.current['status'] == 'cli_error' and cli_capacity_before_actions(folder):
                self.current['status'] = 'capacity_wait'
                self.state['pending_retry'] = {'incident': self.current['incident'],
                                               'not_before': time.time() + 60}
            self.state.setdefault('history', []).append(self.current)
            self.process = None
            self.save()
        if self.process or not self.enabled or not self.codex:
            return
        if self.current and self.current.get('status') == 'running':
            # 守护重启后先确认原CLI PID；不能平行启动第二个修复代理。
            if pid_exists(self.current['pid']):
                return
            result = read_json(Path(self.current['folder']) / 'result.json', {})
            self.current.update(status='finished' if result else 'interrupted_cli', result=result, finished=now())
            self.state.setdefault('history', []).append(self.current)
            self.save()
        incidents = incident_list(snapshot) if incidents is None else incidents
        pending = self.state.get('pending_retry')
        if pending:
            matching = next((e for e in incidents if e['id'] == pending['incident']['id']), None)
            if matching and time.time() < pending['not_before']:
                return
            self.state.pop('pending_retry')
            self.save()
            if matching:
                self.seen.discard(matching['id'])
                self.launch(matching)
                return
        if self.manual:
            incidents.insert(0, {'id': f'manual:{time.time()}', 'kind': 'manual_check', 'package': 'pipeline'})
            self.manual = False
        for incident in incidents:
            if incident['id'] in self.seen:
                continue
            first = self.first_seen.setdefault(incident['id'], time.monotonic())
            # 连续两次采样确认退出，避免阶段切换瞬间误判。
            if time.monotonic() - first < 20 and incident['kind'] == 'error':
                return
            self.launch(incident)
            break


class Workbench:
    def __init__(self, run, enabled=True):
        from .autonomy import AutonomousPlan
        self.collector = Collector(run)
        self.guardian = Guardian(run, enabled)
        self.autonomy = AutonomousPlan(run)
        self.snapshot = {'time': now(), 'packages': [], 'rows': [], 'curve': [], 'processes': [],
                         'workers': 0, 'worker_limit': 4, 'allowed': allowed(), 'loading': True}
        self.error = None
        self.sequence = 0
        self.stop = threading.Event()

    def loop(self):
        while not self.stop.is_set():
            try:
                started = time.monotonic()
                snapshot = self.collector.collect(process_inventory())
                incidents = self.autonomy.reconcile(snapshot, self.guardian.current,
                    history=self.guardian.state.get('history', []))
                task_display(snapshot, self.autonomy.view)
                self.guardian.tick(snapshot, incidents=incidents)
                snapshot['guardian'] = self.guardian.public()
                from .current_view import apply_current_view
                snapshot['autonomy'] = apply_current_view(snapshot, self.autonomy.view, self.collector.run, read_json)
                self.sequence += 1
                snapshot.update(time=now(), sequence=self.sequence,
                                sample_duration_seconds=round(time.monotonic()-started, 2))
                self.snapshot, self.error = snapshot, None
                write_json(self.guardian.control / 'status.json', {**snapshot, 'rows': snapshot['rows'][:100]})
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                self.error = f'{type(exc).__name__}: {exc}'
                write_json(self.guardian.control / 'monitor_error.json', {'time': now(), 'error': self.error})
                self.guardian.tick(self.snapshot, incidents=[{'id': 'workbench:' + self.error,
                                   'kind': 'error', 'package': 'workbench', 'error': self.error}])
            self.stop.wait(SAMPLE_SECONDS)


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def respond(self, value, status=200, kind='application/json; charset=utf-8'):
            body = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, (dict, list)) else value
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def valid_host(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',
                                                 f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.valid_host():
                return self.respond({'error': 'local_host_required'}, 403)
            parsed = urlsplit(self.path)
            if parsed.path == '/api/status':
                value = {**app.snapshot, 'monitor_error': app.error, 'guardian': app.guardian.public(),
                         'server_time': now(),
                         'selftest': selftest_status()}
                return self.respond(value)
            if parsed.path == '/api/task':
                package = parse_qs(parsed.query).get('package', [''])[0]
                cell = parse_qs(parsed.query).get('cell', [''])[0]
                row = app.collector.rows.get((package, cell))
                if not row:
                    return self.respond({'error': 'not_found'}, 404)
                source = app.collector.row_paths.get((package, cell))
                if source:
                    row = read_json(source, {})
                # 只提供解题证据白名单；不暴露原始HTTP或任务隐藏测试。
                attempts = [{'attempt': a.get('attempt'), 'code': a.get('code'),
                             'functional': a.get('functional'), 'security': a.get('security'),
                             'joint': a.get('joint'), 'measured': a.get('measured')}
                            for a in row.get('attempts', [])]
                mechanism = [{**{k: m.get(k) for k in ('attempt', 'candidate_count', 'learned_candidates')},
                    **{k: m.get(k) or [] for k in ('selected', 'adopted', 'selected_Q')}}
                    for m in row.get('mechanism', [])]
                return self.respond({'task_id': row.get('task_id'), 'cell_id': cell, 'attempts': attempts,
                                     'mechanism': mechanism, 'q_credit_events': row.get('q_credit_events', []),
                                     'model_cohort': row.get('model_cohort', '1017_only'),
                                     'response_models': row.get('response_models', []),
                                     'request_model_lineage': row.get('request_model_lineage', [])})
            files = {'/': ('index.html', 'text/html; charset=utf-8'),
                     '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                     '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if parsed.path not in files:
                return self.respond({'error': 'not_found'}, 404)
            name, kind = files[parsed.path]
            return self.respond((STATIC / name).read_bytes(), kind=kind)

        def do_POST(self):
            origin = self.headers.get('Origin')
            if (not self.valid_host() or origin not in (f'http://127.0.0.1:{self.server.server_port}',
                                                        f'http://localhost:{self.server.server_port}')
                    or self.headers.get('X-CLE-Control') != 'workbench'):
                return self.respond({'error': 'same_origin_required'}, 403)
            if self.path == '/api/guardian/toggle':
                app.guardian.enabled = not app.guardian.enabled
                app.guardian.save()
            elif self.path == '/api/guardian/check':
                app.guardian.manual = True
            elif self.path == '/api/guardian/reload':
                self.respond({'ok': True, 'status': 'reloading'})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else:
                return self.respond({'error': 'not_found'}, 404)
            self.respond({'ok': True, 'guardian': app.guardian.public()})
    return Handler


def serve(port=8772):
    app = Workbench(RUN)
    server = ThreadingHTTPServer(('127.0.0.1', port), handler_for(app))
    # 监听socket本身是单实例锁；先绑定再开启守护，重复启动不会产生修复代理。
    write_json(app.guardian.control / 'launch.json', {'pid': os.getpid(), 'time': now(), 'port': port,
                                                     'codex': app.guardian.codex, 'project': str(ROOT)})
    monitor_thread = threading.Thread(target=app.loop, daemon=True)
    monitor_thread.start()
    try:
        server.serve_forever()
    finally:
        app.stop.set()
        server.server_close()
        monitor_thread.join()
    # 受控重载只替换工作台，实验worker和未结束CLI均由保存PID接管。
    subprocess.Popen([str(PYTHON), '-B', '-X', 'utf8', '-m', 'tools.cle_live_workbench.app',
                      'start', '--port', str(port)], cwd=ROOT,
                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['serve', 'start', 'status'])
    parser.add_argument('--port', type=int, default=8772)
    args = parser.parse_args()
    if args.action == 'serve':
        serve(args.port)
    elif args.action == 'status':
        print(json.dumps(read_json(RUN / 'workbench_monitor/status.json', {}), ensure_ascii=False))
    else:
        from urllib.request import urlopen
        from urllib.error import URLError
        try:
            with urlopen(f'http://127.0.0.1:{args.port}/api/status', timeout=3) as response:
                existing = json.load(response)
            if existing.get('run_root') == str(RUN):
                print(json.dumps({'status': 'already_running', 'url': f'http://127.0.0.1:{args.port}'}))
                return
        except URLError:
            pass
        control = RUN / 'workbench_monitor'
        control.mkdir(parents=True, exist_ok=True)
        with (control / 'server.stdout.log').open('ab') as stdout, (control / 'server.stderr.log').open('ab') as stderr:
            process = subprocess.Popen([str(PYTHON), '-B', '-X', 'utf8', '-m',
                                        'tools.cle_live_workbench.app', 'serve', '--port', str(args.port)],
                                       cwd=ROOT, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        print(json.dumps({'pid': process.pid, 'url': f'http://127.0.0.1:{args.port}'}))


if __name__ == '__main__':
    main()

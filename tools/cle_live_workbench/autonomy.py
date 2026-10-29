"""把已批准的有限任务持续对账成可执行队列；结果由原生产物确认。"""
import json
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

from . import app

BLOCK_REASONS = {'v32_unavailable', 'original_validator_image_missing', 'human_review_pending',
                 'provider_balance_or_auth', 'budget_exhausted', 'scientific_decision_required'}
GOOD_NATIVE = {'completed', 'awaiting_agent_analysis', 'awaiting_human_confirmation',
               'native_outputs_complete_pending_replay_and_analysis', 'completed_pending_verification'}


def field(value, name):
    for part in name.split('.'):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


class AutonomousPlan:
    def __init__(self, root, plan=None, *, persist=True):
        self.root = Path(root)
        self.control = self.root / 'workbench_monitor/autonomy'
        self.control.mkdir(parents=True, exist_ok=True)
        self.plan = plan or app.read_json(Path(__file__).with_name('autonomy_plan.json'))
        self.tasks = self.plan['tasks']
        self.definitions = {t['id']: t for t in self.tasks}
        if len(self.definitions) != len(self.tasks):
            raise ValueError('duplicate_autonomy_task_id')
        for task in self.tasks:
            if any(d not in self.definitions for d in task['depends']):
                raise ValueError('unknown_autonomy_dependency:' + task['id'])
        pending, ordered = list(self.tasks), []
        while pending:
            ready = [t for t in pending if all(d in {o['id'] for o in ordered}
                                              for d in t['depends'] + ([t['order_after']] if t.get('order_after') else []))]
            if not ready:
                raise ValueError('autonomy_dependency_cycle')
            ordered.extend(ready)
            pending = [t for t in pending if t not in ready]
        self.tasks = [t for t in ordered if t['kind'] != 'closeout'] + [t for t in ordered if t['kind'] == 'closeout']
        self.state = app.read_json(self.control / 'state.json', {'tasks': {}, 'consumed_jobs': []})
        self.view = {}
        self.queue = []
        if persist:
            app.write_json(self.control / 'task_plan.json', self.plan)

    def receipt_path(self, task):
        return self.control / 'receipts' / (task['id'] + '.json')

    def receipt(self, task):
        return app.read_json(self.receipt_path(task), {})

    def evidence_path(self, text):
        path = Path(text)
        path = path.resolve() if path.is_absolute() else (self.root / path).resolve()
        if path.is_relative_to(self.root.resolve()) or path.is_relative_to((app.ROOT / 'docs').resolve()) or path.is_relative_to((app.ROOT / 'results/curated').resolve()):
            return path
        raise ValueError('autonomy_evidence_outside_scope')

    def artifact_ok(self, check):
        path = self.evidence_path(check['path'])
        if not path.is_file() or path.stat().st_size == 0:
            return False
        if 'field' in check:
            return field(app.read_json(path, {}), check['field']) == check['equals']
        return True

    def stage_finished(self, snapshot, stage):
        package = next((p for p in snapshot['packages'] if p['key'] == 'FQ_LEARN'), {})
        summary = package.get('stages', {}).get(stage, {})
        expected = 303 if stage == 'K0' else 273
        return (summary.get('status') == 'completed' and summary.get('completed') == expected
                and (self.root / 'FQ_LEARN/frozen' / (stage + '.jsonl')).is_file())

    def reviewed(self, directory):
        queue_path = directory / 'case_review_queue.json'
        if not queue_path.is_file():
            return False
        queue = app.read_json(queue_path)
        if not isinstance(queue, list):
            return False
        if not queue:
            return True
        review = app.read_json(directory / 'agent_case_review.json', {})
        if review.get('status') != 'completed' or not isinstance(review.get('cases'), list):
            return False
        expected = {str(c['task_id']) for c in queue}
        actual = set()
        for case in review['cases']:
            if not case.get('analysis') or not case.get('evidence'):
                return False
            if any(not self.evidence_path(p).is_file() for p in case['evidence']):
                return False
            actual.add(str(case.get('task_id')))
        return expected <= actual

    def receipt_complete(self, task):
        receipt = self.receipt(task)
        if receipt.get('status') != 'completed' or not receipt.get('evidence'):
            return False
        if any(not self.evidence_path(p).is_file() for p in receipt['evidence']):
            return False
        if task['kind'] == 'run':
            counters = receipt.get('native_counters', [])
            if not counters:
                return False
            identities, count = set(), 0
            for counter in counters:
                identity = (counter['path'], counter['field'])
                if identity in identities:
                    return False
                identities.add(identity)
                value = app.read_json(self.evidence_path(counter['path']), {})
                if value.get('status') not in GOOD_NATIVE:
                    return False
                number = field(value, counter['field'])
                if type(number) is not int or number < 0:
                    return False
                count += number
            if task.get('expected') is not None and count != task['expected']:
                return False
        return True

    def native_done(self, task, snapshot):
        if self.omitted_by_protocol(task):
            return True
        if not self.native_evidence_done(task, snapshot):
            return False
        delivery = task.get('narrative', {}).get('receipt')
        if not delivery:
            return True
        value = app.read_json(self.evidence_path(delivery), {})
        sections = set(task['narrative']['sections'])
        return (value.get('status') == 'completed' and value.get('task_id') == task['id']
                and set(value.get('sections', [])) == sections
                and value.get('experiment_API_calls') == 0
                and bool(value.get('evidence'))
                and all(self.evidence_path(p).is_file() for p in value['evidence']))

    def native_evidence_done(self, task, snapshot):
        """先验收原生实验/代码分析，再验收其叙事交付；文案不能替代实验。"""
        kind = task['kind']
        if kind == 'probe':
            proof = app.read_json(self.evidence_path(task['probe_report']), {})
            return (self.receipt_complete(task)
                    and proof.get('status') == 'completed'
                    and proof.get('completed') == task['expected']
                    and set(map(str, proof.get('task_ids', []))) == set(map(str, task['probe_scope']['task_ids']))
                    and proof.get('bounded_dispatch_verified') is True
                    and proof.get('replay_status') == 'passed'
                    and bool(proof.get('native_evidence'))
                    and all(self.evidence_path(p).is_file() for p in proof['native_evidence']))
        package = next((p for p in snapshot['packages'] if p['key'] == task['package']), {})
        if kind == 'run' and not task.get('custom'):
            return package.get('status') == 'completed' and package.get('completed') == task['expected']
        if kind == 'run' and task['package'] in ('FR', 'FR_EXTRA'):
            return (package.get('summary', {}).get('status') == 'awaiting_human_confirmation'
                    and package.get('summary', {}).get('inputs_unchanged') is True
                    and len(list((self.root / task['package'] / 'records').glob('*.json'))) == task.get('expected',571))
        if kind == 'run' and task['package'] == 'BUILD_C41':
            segments = app.read_json(self.root / 'BUILD_C41/execution_index.json', {}).get('segments', [])
            path = Path(segments[-1]) if segments else self.root / 'BUILD_C41/execution/segment_001'
            native = app.read_json(path / 'native_verification.json', {})
            return (app.read_json(path / 'state.json', {}).get('status') == 'completed_pending_verification'
                    and native.get('phase1_tasks') == 303 and native.get('final_eval_tasks') == 298
                    and native.get('completed_rounds') == [1, 2, 3])
        if kind == 'analysis':
            path = self.root / task['analysis_dir']
            summary = app.read_json(path / 'summary.json', {})
            replay_ok = app.read_json(self.root / task['replay'], {}).get('status') == 'passed'
            if task['id'] == 'Q.K0.analysis' and not replay_ok:
                # 2026-10-28用户授权的独立历史反馈回放；保留原动态复验分歧及失败目录。
                from configs.cle_weekly_k0_saved_feedback_20261028.certificate import accepted
                replay_ok = accepted(self.root)
            return (summary.get('status') == 'completed' and summary.get('completed') == task['expected']
                    and replay_ok
                    and (path / 'analysis.md').is_file() and self.reviewed(path))
        if kind in ('prepare', 'train'):
            if task.get('accept'):
                return all(self.artifact_ok(c) for c in task['accept'])
            return self.receipt_complete(task)
        if task.get('custom') or kind in ('custom', 'closeout'):
            if not self.receipt_complete(task):
                return False
            if kind == 'closeout':
                receipt = self.receipt(task)
                markdown = self.evidence_path(receipt.get('markdown', 'missing'))
                word = self.evidence_path(receipt.get('word', 'missing'))
                return markdown.is_file() and word.is_file() and zipfile.is_zipfile(word)
            if task['package'] == 'BUILD_C41':
                certificate = app.read_json(self.root / 'BUILD_C41/verified_library.json', {})
                return (certificate.get('status') == 'verified_native_primary_replay'
                        and Path(certificate.get('bank_path', 'missing')).is_file())
            return True
        return False

    def omitted_by_protocol(self, task):
        """预登记扩大条件决定不执行可选分支；不生成成绩或假完成计数。"""
        condition=task.get('omit_when')
        if not condition:
            return False
        value=app.read_json(self.evidence_path(condition['path']),{})
        return value.get('status')=='decided' and field(value,condition['field']) in condition['values']

    def image_ready(self):
        cached = self.state.get('image_probe', {})
        if time.time() - cached.get('checked_at', 0) < 300:
            return cached.get('ready', False)
        ready = False
        docker = shutil.which('docker')
        if docker:
            try:
                result = subprocess.run([docker, 'image', 'inspect', 'safecoder-python-validator:local', '--format', '{{.Id}}'],
                                        capture_output=True, text=True, timeout=10,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                ready = result.returncode == 0 and bool(result.stdout.strip())
            except subprocess.TimeoutExpired:
                pass
        self.state['image_probe'] = {'checked_at': time.time(), 'ready': ready}
        return ready

    def external_reason(self, task):
        if task.get('user_paused'):
            return 'scientific_decision_required'
        if task.get('requires_image') and not self.image_ready():
            return 'original_validator_image_missing'
        if task['kind'] == 'external':
            if task.get('reason') == 'human_review_pending':
                decision=app.read_json(self.root/'scope_reduction_20261028/FR_decision_57.json',{})
                packages=['FR']+(['FR_EXTRA'] if decision.get('action')=='expand' else [])
                if all(app.read_json(self.root / p / 'metrics.json', {}).get('formal_metrics') ==
                       'human_labels_complete_native_coverage_reported_separately' for p in packages):
                    return None
            return task.get('reason')
        receipt = self.receipt(task)
        if (receipt.get('status') == 'blocked_external' and receipt.get('reason_code') in BLOCK_REASONS
                and receipt.get('evidence') and all(self.evidence_path(p).is_file() for p in receipt['evidence'])):
            return receipt['reason_code']
        return None

    def consume_job(self, current):
        if not current or current.get('status') in ('running', 'capacity_wait'):
            return
        identity = current.get('job_id')
        task_id = current.get('incident', {}).get('task_id')
        if not task_id or identity in self.state['consumed_jobs']:
            return
        entry = self.state['tasks'].setdefault(task_id, {})
        entry.update(attempts=entry.get('attempts', 0) + 1, last_job=identity,
                     last_result=current.get('result', {}), next_at=time.time() + 20)
        self.state['consumed_jobs'].append(identity)

    def reconcile(self, snapshot, current=None, history=()):
        # Guardian可能在同一tick收尾旧CLI并启动新CLI；先补收历史完成项，
        # 否则遗漏的attempt会让新故障沿用已去重的事件ID，永久停在ready。
        for finished in history:
            self.consume_job(finished)
        self.consume_job(current)
        views = {}
        active = {p['package'] for p in snapshot['processes']}
        provider_blocked = any(self.external_reason(t) == 'provider_balance_or_auth' for t in self.tasks)
        for task in self.tasks:
            identity = task['id']
            entry = {'id': identity, 'title': task['title'], 'package': task['package'], 'kind': task['kind'],
                     'depends': task['depends'], 'priority': task.get('priority', 50), 'reason': None,
                     'expected': task.get('expected')}
            entry['execution_scope'] = task.get('execution_scope')
            if self.native_done(task, snapshot):
                status = 'completed'
                if self.omitted_by_protocol(task):
                    entry['reason']='omitted_by_preregistered_rule; no experiment outcome recorded'
                    entry['execution']='not_required_by_protocol'
                    entry['display_status'] = 'deferred' if identity.startswith('P3.') else 'not_required'
            elif task.get('user_paused'):
                status, entry['reason'] = 'blocked_external', 'paused_by_user'
                entry['display_status'] = 'paused'
            elif task['kind'] == 'external' and not self.external_reason(task):
                status = 'completed'
            elif task['kind'] in ('run', 'probe') and task['package'] in active and not self.full_deferred(task):
                status = 'running' if snapshot['allowed'] else 'waiting_window'
            elif self.full_deferred(task):
                status, entry['reason'] = 'deferred_full', 'probe_relay_skips_queued_full'
            elif task['kind'] in ('run', 'probe') and provider_blocked:
                status, entry['reason'] = 'blocked_external', 'provider_balance_or_auth'
            elif task['kind'] == 'external' and any(views[d]['status'] != 'completed' for d in task['depends']):
                status = 'waiting_dependency'
            elif self.external_reason(task):
                status, entry['reason'] = 'blocked_external', self.external_reason(task)
            elif task['kind'] == 'closeout':
                other = [v for v in views.values()]
                status = 'ready' if all(v['status'] in ('completed', 'blocked_external') for v in other) else 'waiting_dependency'
            else:
                deps = [views[d] for d in task['depends']]
                if any(d['status'] == 'blocked_external' for d in deps):
                    status, entry['reason'] = 'blocked_external', 'upstream:' + ','.join(d['id'] for d in deps if d['status'] == 'blocked_external')
                elif any(d['status'] != 'completed' for d in deps):
                    status = 'waiting_dependency'
                elif task.get('requires_stage') and not self.stage_finished(snapshot, task['requires_stage']):
                    status = 'waiting_dependency'
                elif task.get('order_after') and views[task['order_after']]['status'] not in ('completed', 'blocked_external', 'deferred_full'):
                    status = 'waiting_turn'
                else:
                    status = 'ready'
            if status == 'ready' and task['kind'] in ('run', 'probe'):
                free = 4 - snapshot['workers']
                other_evaluation = any(p['package'] != 'FQ_LEARN' for p in snapshot['processes'])
                if not snapshot['allowed']:
                    status = 'waiting_window'
                elif (task.get('slots') == 'exclusive' and snapshot['workers']) or free < 1:
                    status = 'waiting_capacity'
                elif task['package'] != 'FQ_LEARN' and other_evaluation:
                    status = 'waiting_capacity'
            if current and current.get('incident', {}).get('task_id') == identity:
                if current.get('status') == 'running' and status not in ('completed', 'blocked_external', 'deferred_full'):
                    status = 'running'
                elif current.get('status') == 'capacity_wait':
                    entry['reason'] = 'cli_model_capacity'
            entry['status'] = status
            if entry.get('reason') == 'v32_unavailable':
                entry['display_status'] = 'ended'
            entry['attempts'] = self.state['tasks'].get(identity, {}).get('attempts', 0)
            views[identity] = entry
        # 完成报告以后若外部依赖到位，重新推进新增可执行项并在结束后更新报告。
        closeout = next((t for t in self.tasks if t['kind'] == 'closeout'), None)
        if closeout and views[closeout['id']]['status'] == 'completed':
            saved = self.receipt(closeout).get('scope_states')
            actual = {key: value['status'] for key, value in views.items() if key != closeout['id']}
            if saved != actual:
                views[closeout['id']]['status'] = 'ready' if all(v in ('completed', 'blocked_external') for v in actual.values()) else 'waiting_dependency'
        errors = [e for e in app.incident_list(snapshot) if e['kind'] == 'error']
        self.queue = []
        error_task_ids = set()
        for incident in errors:
            task = next((t for t in self.tasks if t['kind'] in ('run', 'probe') and t['package'] == incident['package'] and not self.full_deferred(t)), None)
            if not task or views[task['id']]['status'] in ('completed', 'blocked_external', 'deferred_full'):
                continue
            if incident.get('status') in ('awaiting_human_confirmation', 'waiting_new_package_first_initials'):
                continue
            error_task_ids.add(task['id'])
            if not snapshot['allowed']:
                continue
            meta = self.state['tasks'].get(task['id'], {})
            if time.time() < meta.get('next_at', 0):
                continue
            self.queue.append(self.packet(task, snapshot, operation='repair', priority=-100))
        for entry in sorted(views.values(), key=lambda v: v['priority']):
            if entry['status'] != 'ready':
                continue
            if entry['id'] in error_task_ids:
                continue
            task = self.definitions[entry['id']]
            meta = self.state['tasks'].get(task['id'], {})
            if time.time() < meta.get('next_at', 0):
                continue
            self.queue.append(self.packet(task, snapshot))
        counts = {key: sum(v['status'] == key for v in views.values()) for key in
                  ('completed', 'running', 'ready', 'blocked_external', 'waiting_dependency', 'waiting_capacity', 'waiting_window', 'waiting_turn', 'deferred_full')}
        counts['not_required'] = sum(v.get('execution') == 'not_required_by_protocol' for v in views.values())
        counts['completed_verified'] = counts['completed'] - counts['not_required']
        terminal = all(v['status'] in ('completed', 'blocked_external') for v in views.values())
        self.view = {'plan_id': self.plan['plan_id'], 'time': app.now(), 'counts': counts,
                     'status': ('completed_with_external_wait' if counts['blocked_external'] else 'completed') if terminal else 'executing',
                     'next': self.queue[0]['work_item']['id'] if self.queue else None,
                     'tasks': list(views.values())}
        app.write_json(self.control / 'state.json', self.state)
        app.write_json(self.control / 'status.json', self.view)
        return self.queue

    def full_deferred(self, task):
        policy = self.plan.get('dispatch_policy', {})
        return (policy.get('mode') == 'probe_relay'
                and task.get('execution_scope') == 'full'
                and task['id'] not in policy.get('continue_started', []))

    def packet(self, task, snapshot, operation=None, priority=None):
        meta = self.state['tasks'].get(task['id'], {})
        workers = 1 if task.get('slots') == 1 else max(0, min(4, 4 - snapshot['workers']))
        workers = min(workers, task.get('max_workers', 4))
        return {'id': f"autonomy:{task['id']}:{meta.get('attempts', 0)}:{operation or task['kind']}",
                'kind': 'error' if operation == 'repair' else 'autonomous_task', 'package': task['package'],
                'task_id': task['id'], 'priority': priority or task.get('priority', 50),
                'work_item': {**task, 'operation': operation or task['kind'], 'allocated_workers': workers,
                              'receipt': str(self.receipt_path(task)),
                              'previous_job_folder': str(self.root / 'workbench_monitor/jobs' / meta['last_job']) if meta.get('last_job') else None,
                              'previous_result': meta.get('last_result'), 'attempt': meta.get('attempts', 0)},
                'scope_states': {v['id']: v['status'] for v in self.view.get('tasks', [])}}


def work_instructions(incident, run):
    item = incident['work_item']
    return f'''
现在进入持续任务队列模式，仅处理下面这一项，不自行启动其它节点，不长期轮询。当前任务：
{json.dumps(item, ensure_ascii=False, indent=2)}
最新调度规则：探针和探针分析自动接力；排队全量先跳过，不因探针通过自动启动全量。既有Q.run与FS.run继续及恢复。此规则优先于下文和旧note中“通过后全量”的描述。不能把被跳过的全量记完成或移除科学依赖。kind=probe时只准派发probe_scope中的题号、条件和重复，上限为expected；commands若为空，先在独立目录落实有界入口及封网测试，再执行真实探针。禁止调用父节点不受限launch，禁止先启动全量再中途杀进程冒充探针。完成后写probe_report：status=completed、completed、task_ids、bounded_dispatch_verified=true、replay_status=passed、native_evidence真实文件列表，并保存原生行、请求、成本和逐题分析；仅有CLI文字或模拟测试不能当作真实完成。探针必须沿原正式输出链保留可复用结果和累计预算；到边界自然退出。其它探针可越过排队全量的顺序位置，但不得越过冻结库、真实分类器或原验证镜像等数据依赖。
用户最新授权：2026-10-28当天允许任意时段实验，至2026-10-29 00:00北京时间自动到期。授权记录在workbench_monitor/time_override_20261028.json；本CLI的后续Python进程继承独立bootstrap，不改冻结provider_policy源码。已经运行的Q进程不注入、不重启；其原有窗口等待是正常状态，后续自然恢复进程继承临时时段。固定模型、规则、累计预算及总并发4不变。
1. 先核对实际进程、任务产物和当前预算。已活跃的运行不重复启动；恢复复用已保存响应，完成格不重发。启动后将PID和实际命令写证据，再返回工作台。付费节点只在允许时段和分配的{item['allocated_workers']}个worker内启动，每个原生请求仍检查窗口/预算。零API准备与分析可随时执行。
2. commands是现有入口线索，必须核对实际--help和协议，不能照抄失效入口。原活动source_identity列出的源文件不能改；真实接线问题用独立目录修复、离线验证后接续。prepare必须真正完成代码、有限预算、恢复/回放/锁验证，不能写passed假装就绪。用户2026-10-28已批准减量：Q中间轮54题（最终K3/Q1仍273）、记忆首批82题、检索首批57题，详见configs/cle_weekly_reduced_20261028/README.md和scope_reduction_20261028/selection.json。仅由预登记扩大条件进入互斥的新增批；不要还原旧全量规模，不因低Joint取消仍保留的主要全量比较。新入口继续累计预算、保留未知用量。
3. analysis先原生零API回放并复算完整统计，再实际读取case_review_queue所有代表题的题面、卡、计划、代码和验证，写分析目录agent_case_review.json：{{"status":"completed","cases":[{{"task_id":"...","analysis":"落实、契约/实现/Q原因的实际判断","evidence":["实际读取且存在的证据路径"]}}]}}。同题可合并类别，但不能把待审队列当已分析。分析正文和summary保留完整分母、配对、family区间、重复波动、成本；Q主两比较Holm校正。资料多时保存真实进展，下次继续未完成部分。
4. 普通原生run和analysis由工作台检查summary/回放/逐题证据完成，不以你的回复结单。custom/prepare无accept/train/closeout需要在 {item['receipt']} 写JSON收据：task_id、status=completed、evidence(已有真实文件路径)。custom run还须native_counters=[{{"path":"实际原生summary路径","field":"completed或arms.B0.completed等实际计数路径"}}]，原生状态必须完整、计数达到固定总量且不重复。复用格必须实际逐格匹配并保存复用证据。
   新实现入口若不在既有进程识别表，启动后在workbench_monitor/autonomy/registered_workers.json登记数组项{{"pid":实际PID,"package":"{item['package']}","workers":实际worker数,"command_marker":"命令中唯一的真实模块或脚本路径"}}，保留其他在用条目；工作台会用CIM再次核对，不凭登记假定运行。
5. FR完成AI材料就交付人审，不代签；BUILD须实际原CLE三轮、主动回放、全局门控和完整回放；交叉只执行v4.1可用部分，v3.2不再请求；Base/Plus必须原镜像、正向校准、常驻Docker/watchdog、隐藏反馈不回传。
6. 若确有外部依赖，收据status=blocked_external、reason_code只可为v32_unavailable/original_validator_image_missing/human_review_pending/provider_balance_or_auth/budget_exhausted/scientific_decision_required，写具体原因与证据。普通编码未完成或入口待实现属于当前任务，不能借此标外部阻塞。预算不能重置或扩大。不要把本次CLI返回当全部任务完成。
7. closeout要生成本轮综合Markdown及真正带跳转书签的Word（按现周历和宋体/TNR模板），收据加markdown/word路径及scope_states（读取workbench_monitor/autonomy/status.json内除CLOSEOUT外的任务状态）。只在所有自主项完成、或仅余已核实外部依赖时收口。外部到位后队列自动继续。
8. 若narrative中有receipt字段，原生分析完成后仍不能直接结单。按tools/cle_live_workbench/README.md的阶段交付格式写delivery_draft.json（六项解释、真实结果依据和对应图的新文字），再执行python -B -X utf8 -m tools.cle_live_workbench.delivery publish --task {item['id']} --draft <实际草稿路径>。该零API入口回写叙事、刷新指定SVG/PNG并保留本阶段副本，工作台核对收据后才放行后继。没有实测结果不能调用它伪造完成；条件省略分支不要求生成分析或图。
把本项实际结果返回既有JSON结构，完成后结束，由工作台自动安排下一项。'''

"""执行接点：原请求日志、时段、预算和计划复核；默认离线，授权live入口显式注入客户端。

原P7及重试规则保持不变；2026-10-26授权入口使用独立运行区，保存响应可精确恢复。
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from configs.cle_v41_migration_20261025.resume import RecoveryBudget, AccountedResponse
from configs.cle_v41_relation_20261026 import wiring
from methods.sct_trajectory.provider_policy import ensure_model_call_allowed, ModelTimeWindowError
from methods.sct_trajectory.replay_journal import RequestJournal, ReplayStop, write_json
from methods.sct_trajectory.wire_recording import WireRecording


class StudyStop(ReplayStop):
    """主流程的控制停止，不被原P7降级为普通模型失败。"""


class DispatchDenied(RuntimeError):
    """HTTP线程只传普通异常；主线程再停止，避免BaseException在线程内丢失。"""


def plan_from_prefix(record):
    # 输入由原生成模板产生，JSON只解码Plan段，不使用代码、分数或验证夹具。
    text = record['generation_input']['prompt'].split('\nPlan: ', 1)[1]
    return json.JSONDecoder().raw_decode(text)[0]


def review_from_directory(directory):
    """读取人工/Codex实际复核文件，不自动猜标签；原计划须逐字对应。"""
    def reviewer(item):
        path = Path(directory) / (item['prefix_id'] + '.review.json')
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    return reviewer


def route_decision(rows, kind, *, code_reviews=None, plan_labels=None):
    """冻结8格完成后的纯结果门，不派发请求或追加样本；代码关系须独立复核。"""
    pair = {suffix: {r['repeat']: r for r in rows if r['relation_arm'] == kind + '_' + suffix}
            for suffix in ('bind', 'rel')}
    result = {'route': kind, 'automatic_expansion': False, 'requires_new_authorization_for_new_runs': True}
    if any(set(items) != {1, 2} for items in pair.values()):
        return {**result, 'status': 'inconclusive_incomplete'}
    control, treated = [pair[key] for key in ('bind', 'rel')]
    final = lambda row: row['attempts'][-1]
    if any(not final(r).get('measured') for items in pair.values() for r in items.values()):
        return {**result, 'status': 'inconclusive_unmeasured'}
    rescued = [i for i in (1, 2) if final(treated[i])['joint'] and not final(control[i])['joint']]
    lost = [i for i in (1, 2) if final(control[i])['joint'] and not final(treated[i])['joint']]
    result.update(rescued_repeats=rescued, lost_repeats=lost, net_joint=len(rescued)-len(lost))
    if kind == 'K' and not any(r['attempts'][0]['generation'].get('cards') for r in treated.values()):
        return {**result, 'status': 'inconclusive_no_c0_memory_adoption'}
    if all(final(r)['joint'] for items in pair.values() for r in items.values()):
        return {**result, 'status': 'inconclusive_ceiling'}
    f_decline = sum(final(r)['functional'] for r in treated.values()) < sum(final(r)['functional'] for r in control.values())
    s_loss = any(final(control[i])['security'] and not final(treated[i])['security'] for i in (1, 2))
    if result['net_joint'] < 1 or lost or f_decline or s_loss:
        return {**result, 'status': 'stop_this_reminder_version', 'functional_decline': f_decline, 'new_security_loss': s_loss}
    reviews = code_reviews or {}
    if (not all(reviews.get(r['cell_id'], {}).get('relation_status') == 'consistent' for r in treated.values()) or
            not any(reviews.get(treated[i]['cell_id'], {}).get('verified_rescue_path') for i in rescued)):
        return {**result, 'status': 'inconclusive_missing_code_relation_evidence'}
    labels = plan_labels or {}
    explicit_rescue = any(labels.get(f'1409_r{i}_{kind}') == 'explicit' for i in rescued)
    return {**result, 'status': 'limited_development_signal',
            'scope': 'implementation_of_explicit_plan' if explicit_rescue else 'omission_or_ambiguous_plan_reminder',
            'generalization_supported': False}


class StudyExecution:
    """顺序消费固定8格；原生并发上限仍为4，不另设模型/提示/验证后端。

    所有物理尝试先准入后记录；共享回放不新计费用。缺计划复核只暂停，不按标签
    好坏筛掉前缀。技术故障保留已完成行、日志和未知预算，授权编排入口另建恢复段。
    """
    def __init__(self, root, protocol, schedule, *, client_factory, physical_open, reviewer=None,
                 now=None, wait=time.sleep, replay_source=None, protected_paths=(), live=False,
                 fixed_eight=True, review_wait=False, resume_sources=()):
        self.root, self.protocol, self.schedule = Path(root), copy.deepcopy(protocol), copy.deepcopy(schedule)
        self.live, self.review_wait = live, review_wait
        if protocol['paid_execution_enabled'] and not live:
            raise StudyStop('offline_integration_requires_paid_switch_off')
        if live and not protocol['paid_execution_enabled']:
            raise StudyStop('live_execution_requires_current_authorization')
        self.client_factory, self.physical_open, self.reviewer = client_factory, physical_open, reviewer
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.wait, self.replay_source = wait, Path(replay_source) if replay_source else None
        self.resume_sources = [Path(p) for p in resume_sources]
        self.reason, self.journals, self.rows, self.saved = None, {}, [], {}
        self.reused_cell_ids={p.stem for root in self.resume_sources for p in (root/'task_rows').glob('*.json')}
        self.entries_by_request, self.lock = {}, threading.RLock()
        self.time_denied = False
        if fixed_eight and (len(schedule) != 8 or len({c['cell_id'] for c in schedule}) != 8 or
                [c['repeat'] for c in schedule] != [1]*4 + [2]*4):
            raise StudyStop('invalid_frozen_eight_cell_schedule')
        if not fixed_eight and (len(schedule) != protocol['planned_P7'] or
                                len({c['cell_id'] for c in schedule}) != len(schedule)):
            raise StudyStop('invalid_bounded_manifest')
        self.protected = [Path(p) for p in protected_paths]
        self.inputs_before = self.input_state()
        self.root.mkdir(parents=True, exist_ok=False)
        cap = protocol['budget_proposed']
        self.budget = RecoveryBudget(self.root / 'budget.json', [p/'wire' for p in self.resume_sources],
            max_tokens=cap['conservative_model_and_embedding_tokens'],
            max_calls=cap['total_physical_HTTP_attempts'],
            max_embedding=cap['embedding_HTTP_attempts_included_in_total'])
        self.prior_physical_count=len(self.budget.entries)
        self.state = {'status': 'prepared_live' if live else 'prepared_offline_integration', 'completed_P7': 0,
                      'actual_paid_P7': 0, 'planned_P7': len(schedule),
                      'evidence_kind': 'real_model_experiment' if live else 'offline_synthetic', 'paid_enabled': live}
        self.save('protocol', protocol)
        self.save('schedule', schedule)

    def input_state(self):
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.protected}

    def save(self, name, value):
        with self.lock:
            if self.saved.get(name) == value:
                return
            snapshot=copy.deepcopy(value)
            try:
                write_json(self.root / (name + '.json'), snapshot)
            except OSError:
                self.reason = 'artifact_write_failure'
                raise StudyStop(self.reason) from None
            self.saved[name] = snapshot

    def stop(self, reason):
        self.reason = self.reason or reason
        raise StudyStop(self.reason)

    def wait_allowed(self, prompt=None):
        while True:
            if self.reason:
                raise StudyStop(self.reason)
            try:
                ensure_model_call_allowed(wiring.SETTINGS['model'], now=self.now())
                return
            except ModelTimeWindowError:
                self.state['status'] = 'waiting_time_window'
                self.save('state', self.state)
                before = time.monotonic()
                self.wait(30)
                if hasattr(prompt, 'deadline'):
                    prompt.deadline += time.monotonic() - before

    def journal(self, identity):
        with self.lock:
            return self._journal(identity)

    def _journal(self, identity):
        if identity not in self.journals:
            source = self.replay_source or self.root
            self.journals[identity] = RequestJournal(source / 'journals' / identity / 'requests',
                mode='replay' if self.replay_source else 'resume' if self.resume_sources else 'live', wait=self.journal_wait)
            journal = self.journals[identity]
            for prior in self.resume_sources:
                for path in sorted((prior/'journals'/identity/'requests').glob('*.json')):
                    item = json.loads(path.read_text(encoding='utf-8'))
                    if item['status'] == 'completed':
                        existing = journal.records.get(item['identity'])
                        if existing is not None and existing['response'] != item['response']:
                            self.stop('conflicting_saved_response')
                        journal.records[item['identity']] = item
                        journal.prior.add(item['identity'])
            if identity == 'embedding':
                # 已缓存向量不会再触发调用；新文本不能被未消费的缓存命中阻挡。
                # 相同输入仍复用原始向量响应，不额外派发。
                journal.prior.clear()
        return self.journals[identity]

    def journal_wait(self, seconds):
        if self.reason:
            raise StudyStop(self.reason)
        self.state['status'] = 'waiting_time_window'
        self.save('state', self.state)
        self.wait(seconds)

    def request_for(self, identity):
        journal = self.journal(identity)
        wrapped = journal.wrap(lambda: self.client_factory(identity), wiring.SETTINGS)
        def request(prompt):
            if self.reason:
                raise StudyStop(self.reason)
            if not self.replay_source:
                self.wait_allowed(prompt)
            try:
                response = wrapped(prompt)
            except BaseException:
                self.reason = self.reason or 'logical_request_failed_or_unresolved'
                raise
            if response.get('model') != wiring.SETTINGS['model']:
                self.stop('reported_model_mismatch')
            return response
        return request

    def embedding(self, texts, call):
        """缓存未命中的原Embedding调用由调用方包入；精确保存输入/向量，不改召回。"""
        journal = self.journal('embedding')
        def perform(_):
            self.wait_allowed()
            self.time_denied = False
            try:
                return call(texts)
            except Exception:
                if self.time_denied:
                    raise ModelTimeWindowError('embedding_not_dispatched_wait_for_allowed_window') from None
                raise
        try:
            return journal.wrap(lambda: perform, {'model': 'text-embedding-3-large', 'operation': 'embedding'})(
                json.dumps(texts, ensure_ascii=False))
        except BaseException:
            # 与模型请求使用相同的批次停止信号，避免TLS失败后排队任务反复等失效flight。
            self.reason = self.reason or 'logical_embedding_failed_or_unresolved'
            raise

    @contextmanager
    def physical_records(self):
        """准入在WireRecording外层，拒绝派发不生成伪物理HTTP记录。"""
        def transport(req, *args, **kwargs):
            entry = self.entries_by_request.pop(id(req))
            try:
                return AccountedResponse(self.physical_open(req, *args, **kwargs), self.budget, entry)
            except Exception:
                # 已到物理边界但未取得完整响应，不能假定免费。原客户端可按原规则重试。
                with self.budget.lock:
                    entry['status'] = 'failed_unknown'
                    write_json(self.budget.path, self.budget.snapshot())
                raise
        with WireRecording(self.root / 'wire', transport=transport):
            recorded = urllib.request.urlopen
            def admitted(req, *args, **kwargs):
                if self.reason:
                    raise DispatchDenied(self.reason)
                try:
                    ensure_model_call_allowed(wiring.SETTINGS['model'], now=self.now())
                except ModelTimeWindowError:
                    self.time_denied = True
                    raise
                if req.host not in ('api.chatanywhere.org', 'api.chatanywhere.tech'):
                    self.reason = 'unexpected_endpoint_before_dispatch'
                    raise DispatchDenied(self.reason)
                body = json.loads(req.data)
                if body['model'] not in (wiring.SETTINGS['model'], 'text-embedding-3-large'):
                    self.reason = 'unexpected_model_before_dispatch'
                    raise DispatchDenied(self.reason)
                try:
                    entry = self.budget.reserve(body)
                except RuntimeError:
                    self.reason = 'physical_budget_exhausted'
                    raise DispatchDenied(self.reason) from None
                self.entries_by_request[id(req)] = entry
                return recorded(req, *args, **kwargs)
            urllib.request.urlopen = admitted
            try:
                yield
            finally:
                urllib.request.urlopen = recorded

    def review_prefix(self, record):
        plan = plan_from_prefix(record)
        item = {'prefix_id': record['prefix_id'], 'plan': plan, 'status': 'pending_review',
                'allowed_labels': ['explicit', 'ambiguous', 'absent'],
                'scope': 'public file-specific signature relation; not schema/API/code correctness',
                'not_used_to_filter_or_regenerate': True, 'before_generation': True}
        self.save('plan_reviews/' + record['prefix_id'], item)
        review = self.reviewer(copy.deepcopy(item)) if self.reviewer is not None else None
        while review is None and self.live and self.review_wait:
            self.state.update(status='waiting_agent_plan_review', pending_prefix=record['prefix_id'])
            self.save('state', self.state)
            self.wait(2)
            review = self.reviewer(copy.deepcopy(item)) if self.reviewer is not None else None
        if review is None:
            self.stop('waiting_plan_review')
        if (review.get('label') not in item['allowed_labels'] or not review.get('reviewer') or
                not review.get('reason') or review.get('reviewed_plan') != plan):
            self.stop('plan_review_missing_or_mismatched')
        # 标签为absent也照常继续；只检查评审对象一致，不用结论筛前缀或挑成绩。
        item.update(status='reviewed', review=copy.deepcopy(review))
        self.save('plan_reviews/' + record['prefix_id'], item)
        return copy.deepcopy(review)

    def on_row(self, row):
        self.rows.append(row)
        self.state.update(status='running' if self.live else 'running_offline_integration',
                          completed_P7=len(self.rows), actual_paid_P7=len(self.rows) if self.live else 0,
                          reused_completed_P7=sum(r['cell_id'] in self.reused_cell_ids for r in self.rows),
                          new_completed_P7=sum(r['cell_id'] not in self.reused_cell_ids for r in self.rows))
        self.save('state', self.state)
        for attempt in row['attempts']:
            evidence = attempt.get('validation', {}).get('evidence', {})
            if any(v.get('error_type') in ('environment_error', 'TimeoutExpired')
                   for v in evidence.values() if isinstance(v, dict)):
                self.stop('validation_environment_failure')

    def technical_gate(self, expected, batches):
        if self.input_state() != self.inputs_before:
            self.stop('frozen_inputs_changed')
        if {r['cell_id'] for r in self.rows} != {c['cell_id'] for c in expected}:
            self.stop('completed_cell_identity_mismatch')
        for batch in batches:
            for kind in ('E', 'K'):
                pair = [r for r in batch['rows'] if r['relation_arm'].startswith(kind)]
                left, right = [r['attempts'][0]['generation'] for r in pair]
                if any(left[k] != right[k] for k in ('initial_analysis', 'experience_analysis',
                        'analysis_parsed', 'adoption', 'cards', 'retrieved_cards', 'plan_parsed')):
                    self.stop('shared_c0_state_mismatch')
                for row in pair:
                    if not 1 <= len(row['attempts']) <= 2:
                        self.stop('native_attempt_limit_changed')
                    if row['attempts'][0].get('joint') and len(row['attempts']) != 1:
                        self.stop('native_early_stop_changed')
                    for attempt in row['attempts']:
                        g = attempt['generation']
                        if len(g.get('retrieved_cards', [])) > 3 or (kind == 'E' and
                                (g.get('retrieved_cards') or g.get('cards'))):
                            self.stop('memory_intervention_changed')
        if any(d['status'] != 'completed' for j in self.journals.values() for d in j.records.values()):
            self.stop('unresolved_logical_request')
        expected_payloads = []
        for journal in self.journals.values():
            for record in journal.records.values():
                if record['settings']['model'] != wiring.SETTINGS['model']:
                    continue
                expected_payloads.append({'model': wiring.SETTINGS['model'],
                    'messages': [{'role': 'user', 'content': record['prompt']}], 'temperature': 0,
                    'max_tokens': 256 if record['selector'] else 4096, 'thinking': {'type': 'disabled'},
                    'stream': True, 'stream_options': {'include_usage': True}})
        for path in (self.root / 'wire').glob('*.request.json'):
            body = json.loads(path.read_text(encoding='utf-8'))['body']
            if body['model'] == wiring.SETTINGS['model'] and body not in expected_payloads:
                self.stop('physical_request_differed_from_frozen_settings')
        # 不检查Joint高低、计划标签、采用数量或原生模型格式降级。
        gate = {'status': 'passed', 'completed_cells': len(expected), 'score_used_for_progression': False}
        self.save('technical_gate' if len(expected) == 4 else 'completion_gate', gate)

    def run(self, task, select):
        batches = []
        try:
            if self.replay_source:
                for path in (self.replay_source / 'journals').glob('*/requests/*.json'):
                    if json.loads(path.read_text(encoding='utf-8'))['status'] != 'completed':
                        self.stop('replay_source_contains_unresolved_request')
            with self.physical_records():
                for repeat in (1, 2):
                    cells = [c for c in self.schedule if c['repeat'] == repeat]
                    batches.append(wiring.run_repeat(task, cells, protocol=self.protocol,
                        request_for=self.request_for, select=select, save=self.save,
                        review_prefix=self.review_prefix, on_row=self.on_row))
                    self.technical_gate(self.schedule[:4 * repeat], batches)
            self.state.update(status='completed' if self.live else 'completed_offline_integration', completed_P7=8)
        except BaseException as exc:
            self.reason = self.reason or (str(exc) if isinstance(exc, ReplayStop) else type(exc).__name__)
            self.state.update(status='waiting_plan_review' if self.reason == 'waiting_plan_review' else
                              'stopped_integration', reason=self.reason)
        self.state['inputs_unchanged'] = self.input_state() == self.inputs_before
        self.state['physical_attempts' if self.live else 'new_physical_attempts_simulated'] = len(self.budget.entries) if self.live else len(self.budget.entries)-self.prior_physical_count
        self.state['source_costs_reused_not_recharged'] = bool(self.replay_source or self.resume_sources)
        self.save('state', self.state)
        self.save('budget', self.budget.snapshot())
        self.save('logical_summary', {name: j.summary() for name, j in self.journals.items()})
        if len(self.rows) == 8:
            labels = {item['prefix_id']: item['review']['label'] for name, item in self.saved.items()
                      if name.startswith('plan_reviews/') and item['status'] == 'reviewed'}
            self.save('route_decisions', {'evidence_kind': 'real_model_experiment' if self.live else 'offline_synthetic_not_model_results',
                'routes': {kind: route_decision(self.rows, kind, plan_labels=labels) for kind in ('E', 'K')}})
        return copy.deepcopy(self.state)

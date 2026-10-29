"""新模型基准的请求记录和零API回放；不改变CLE提示、选卡或经验更新。"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from .provider_policy import ModelTimeWindowError, ensure_model_call_allowed


class ReplayStop(BaseException):
    """请求未决或回放分歧时停止全阶段，避免被任务级异常处理误记成模型失败。"""


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    content = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    # B03R离线实测：Windows快速原子替换偶发PermissionError。只重试本地落盘，
    # 不重发HTTP；持续失败仍抛出，由当前实验作为工程停止处理。
    for attempt in range(3):
        try:
            temp.write_text(content, encoding='utf-8')
            temp.replace(path)
            return
        except PermissionError:
            if attempt == 2:
                raise
            threading.Event().wait(0.02)


class RequestJournal:
    """逐次保存精确输入、返回和用量；同提示的第N次调用保留独立响应。

    live只执行新调用；resume先消费同协议已完成前缀，再允许付费；replay绝不
    构造网络客户端。未决/失败请求不能自动重发，旧文件不覆盖。不读或保存密钥。
    """
    def __init__(self, root, *, mode='live', wait=time.sleep):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.mode = mode
        self.wait = wait
        self.lock = threading.RLock()
        self.stopped = threading.Event()
        self.counts = Counter()
        self.records = {}
        self.consumed = set()
        self.prior = set()
        for p in sorted(self.root.glob('*.json')):
            d = json.loads(p.read_text(encoding='utf-8'))
            self.records[d['identity']] = d
            self.prior.add(d['identity'])
        if mode == 'live' and self.prior:
            raise ReplayStop('existing_journal_requires_explicit_resume_or_replay')

    def wrap(self, factory, settings):
        """factory仅在允许时段、确认需要新调用后求值；settings不含认证信息。"""
        settings = copy.deepcopy(settings)
        client = None

        def request(prompt):
            nonlocal client
            if self.stopped.is_set():
                raise ReplayStop('batch_stopped_after_transport_failure_no_new_request')
            public = {'settings': settings, 'prompt': str(prompt),
                      'selector': type(prompt).__name__ == 'SelectorPrompt'}
            key = hashlib.sha256(json.dumps(public, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            with self.lock:
                self.counts[key] += 1
                identity = f'{key}-{self.counts[key]:06d}'
                old = self.records.get(identity)
                if old:
                    if old['status'] != 'completed':
                        raise ReplayStop('saved_request_unresolved_or_failed_do_not_resubmit:' + identity)
                    self.consumed.add(identity)
                    return copy.deepcopy(old['response'])
                if self.mode in ('resume', 'replay') and self.prior - self.consumed:
                    # Public checks use a fresh worker directory on recovery. Reuse only
                    # when that directory name is the sole visible-input difference.
                    def stable_prompt(value):
                        return re.sub(r'case_[A-Za-z0-9_]+(?=[/\\]+worker\.py)', 'case_<temporary>', value)
                    matches=[k for k in self.prior-self.consumed
                        if self.records[k]['status']=='completed'
                        and self.records[k]['settings']==public['settings']
                        and self.records[k]['selector']==public['selector']
                        and stable_prompt(self.records[k]['prompt'])==stable_prompt(public['prompt'])]
                    if len(matches)==1:
                        self.consumed.add(matches[0])
                        return copy.deepcopy(self.records[matches[0]]['response'])
                    if self.mode == 'replay':
                        raise ReplayStop('replay_missing_request:' + identity)
                    write_json(self.root.parent / 'resume_divergence.json', {'current':public, 'remaining':[self.records[k] for k in sorted(self.prior-self.consumed)]})
                    raise ReplayStop('resume_diverged_before_consuming_saved_prefix')
                if self.mode == 'replay':
                    raise ReplayStop('replay_missing_request:' + identity)
            # 时间等待不是模型失败，也不占用HTTP槽；实际发送前原客户端还会复查。
            while True:
                try:
                    ensure_model_call_allowed(settings['model'])
                    break
                except ModelTimeWindowError:
                    before = time.monotonic()
                    self.wait(30)
                    if hasattr(prompt, 'deadline'):
                        prompt.deadline += time.monotonic() - before
            record = {**public, 'identity': identity, 'status': 'prepared',
                      'started_utc': datetime.now(timezone.utc).isoformat()}
            path = self.root / (identity + '.json')
            write_json(path, record)
            with self.lock:
                self.records[identity] = record
            started = time.monotonic()
            try:
                if client is None:
                    client = factory()
                while True:
                    try:
                        response = client(prompt)
                        break
                    except ModelTimeWindowError:
                        # 未派发的跨界请求等到下一允许窗口；选择器期限同步顺延等待时间。
                        before = time.monotonic()
                        self.wait(30)
                        if hasattr(prompt, 'deadline'):
                            prompt.deadline += time.monotonic() - before
                record.update(status='completed', response=response,
                              finished_utc=datetime.now(timezone.utc).isoformat(),
                              elapsed_seconds=round(time.monotonic() - started, 3))
                write_json(path, record)
                return response
            except Exception as exc:
                self.stopped.set()
                record.update(status='failed_or_unresolved', error_type=type(exc).__name__,
                              diagnostics=getattr(exc, 'safe_diagnostics', []),
                              elapsed_seconds=round(time.monotonic() - started, 3))
                write_json(path, record)
                raise ReplayStop('model_transport_stopped_no_automatic_resubmit:' + identity) from None
        return request

    def summary(self):
        """只从原始响应复算实际用量；回放读取不再增加调用或Token。"""
        usage = Counter()
        unknown = 0
        with self.lock:records=list(self.records.values())
        for d in records:
            u = (d.get('response') or {}).get('usage')
            if not isinstance(u, dict):
                unknown += 1
                continue
            for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                if type(u.get(k)) is int:
                    usage[k] += u[k]
        return {'logical_requests': len(records), 'known_usage': dict(usage),
                'unknown_usage_operations': unknown, 'cost_currency': None,
                'statuses': dict(Counter(d['status'] for d in records))}
